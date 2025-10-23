import io
import base64
import json 
from extraction.helper.schemas.types import ModelProvider
from pypdf import PdfReader
from extraction.helper.common import logging as logutil 
from PIL import Image, ImageFile
from openai import AzureOpenAI 


logger = logutil.get_logger("markitdown-endpoint")
class PDFToMarkdown:
    def __init__(self):
        pass

    def _convert_image_to_jpeg(self, image_data: bytes, width: int, height: int, format_type: str) -> tuple[bytes | None, str | None]:
        """Convert various image formats to JPEG for Azure OpenAI compatibility.
        
        Returns tuple of (converted_bytes, mime_type) or (None, None) if conversion fails.
        """
        try:
            if format_type == "FlateDecode":
            # Try to interpret as PNG-like data
                img = None
                try:
                    # First try to load as a direct image
                    with Image.open(io.BytesIO(image_data)) as im:
                        img = im.convert("RGBA") if im.mode in ("P", "LA") else im.copy()
                except Exception:
                    # If that fails, try to interpret as raw RGBA/RGB data
                    if not width or not height:
                        return None, None
                    
                    # Try different bit depths and color modes
                    for mode, bytes_per_pixel in [("RGBA", 4), ("RGB", 3), ("L", 1)]:
                        expected_size = width * height * bytes_per_pixel
                        if len(image_data) >= expected_size:
                            try:
                                img = Image.frombytes(mode, (width, height), image_data[:expected_size])
                                break
                            except Exception:
                                continue
                    else:
                        logger.debug(f"Could not interpret FlateDecode image data (size: {len(image_data)}, expected for {width}x{height})")
                        return None, None
                        
            elif format_type == "CCITTFaxDecode":
                # TIFF fax format - create a black and white image
                if not width or not height:
                    return None, None
                try:
                    # Try to interpret as 1-bit data
                    img = Image.frombytes("1", (width, height), image_data)
                except Exception:
                    logger.debug(f"Could not interpret CCITTFaxDecode image data")
                    return None, None
                    
            else:  # Generic
                try:
                    with Image.open(io.BytesIO(image_data)) as img:
                        # Convert to RGB if necessary (remove alpha channel, handle grayscale)
                        if img.mode in ("RGBA", "P"):
                            # Create white background for transparency
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == "P":
                                img = img.convert("RGBA")
                            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                            img = background
                        elif img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")

                        # Validate image dimensions
                        if img.width < 10 or img.height < 10:
                            logger.debug(f"Image too small: {img.width}x{img.height}")
                            return None, None
                            
                        if img.width * img.height > 4096 * 4096:  # Reasonable size limit
                            logger.debug(f"Image too large: {img.width}x{img.height}")
                            return None, None

                        # Convert to JPEG
                        output_buffer = io.BytesIO()
                        img.save(output_buffer, format="JPEG", quality=85, optimize=True)
                        jpeg_data = output_buffer.getvalue()
                        
                        logger.debug(f"Successfully converted {format_type} image to JPEG ({len(jpeg_data)} bytes)")
                        return jpeg_data, "image/jpeg"
                except Exception:
                    return None, None
            
        except Exception as e:
            logger.debug(f"Failed to convert {format_type} image: {e}")
            return None, None

    def extract_images_from_page(self, page) -> list[tuple[str, bytes]]:
        """
        Return list of (mime_type, image_bytes) for image XObjects we can pass directly. 

        ONly accept images whose filters yield file-encoded bytes (no re-encoding):
        - DCTDecode -> image/jpeg
        - JPXDecode -> image/jp2

        Skip others (e.g., FlateDecode, CCITTFaxDecode) to avoid complex wrapping/decoding 
        """
        results: list[tuple[str, bytes]] = []
        total_xobjects = 0
        image_xobjects = 0
        supported_images = 0
        unsupported_filters = set()

        try:
            resources = page.get("/Resources")
            if not resources:
                logger.debug("Page has no /Resources")
                return results
            xobjects = resources.get("/XObject")
            if not xobjects:
                logger.debug("Page has no /XObject resources")
                return results
                
            total_xobjects = len(xobjects)
            logger.debug(f"Found {total_xobjects} XObjects on page")
            
            for obj_name, obj in xobjects.items():
                try:
                    xobj = obj.get_object()
                    if xobj.get("/Subtype") != "/Image":
                        logger.debug(f"XObject {obj_name} is not an image (subtype: {xobj.get('/Subtype')})")
                        continue
                        
                    image_xobjects += 1
                    filters = xobj.get("/Filter")
                    if isinstance(filters, list):
                        filter_names = [str(f) for f in filters]
                    elif filters is not None:
                        filter_names = [str(filters)]
                    else:
                        filter_names = []

                    logger.debug(f"Image {obj_name} has filters: {filter_names}")

                    # Try to extract and convert image data
                    try:
                        data: bytes = xobj.get_data()
                        if not data:
                            logger.warning(f"Image {obj_name} has no data")
                            continue

                        # Get image dimensions for validation
                        width = xobj.get("/Width")
                        height = xobj.get("/Height")
                        logger.debug(f"Image {obj_name} dimensions: {width}x{height}")

                        mime_type: str | None = None
                        converted_data: bytes = data

                        # Handle different image encodings
                        if any("DCTDecode" in f for f in filter_names):
                            # JPEG - can use directly
                            mime_type = "image/jpeg"
                        elif any("JPXDecode" in f for f in filter_names):
                            # JPEG 2000 - can use directly
                            mime_type = "image/jp2"
                        elif any("FlateDecode" in f for f in filter_names):
                            # PNG or other compressed format - convert to JPEG
                            converted_data, mime_type = self._convert_image_to_jpeg(data, width, height, "FlateDecode")
                            if not converted_data:
                                logger.debug(f"Failed to convert FlateDecode image {obj_name}")
                                continue
                        elif any("CCITTFaxDecode" in f for f in filter_names):
                            # TIFF fax format - convert to JPEG
                            converted_data, mime_type = self._convert_image_to_jpeg(data, width, height, "CCITTFaxDecode")
                            if not converted_data:
                                logger.debug(f"Failed to convert CCITTFaxDecode image {obj_name}")
                                continue
                        else:
                            # Try generic conversion for other formats
                            try:
                                converted_data, mime_type = self._convert_image_to_jpeg(data, width, height, "Generic")
                                if not converted_data:
                                    # Track unsupported filters for logging
                                    unsupported_filters.update(filter_names)
                                    logger.debug(f"Skipping image {obj_name} - unsupported filters: {filter_names}")
                                    continue
                            except Exception:
                                # Track unsupported filters for logging
                                unsupported_filters.update(filter_names)
                                logger.debug(f"Skipping image {obj_name} - unsupported filters: {filter_names}")
                                continue

                        supported_images += 1
                        logger.debug(f"Successfully extracted image {obj_name} ({len(converted_data)} bytes, {mime_type})")
                        results.append((mime_type, converted_data))

                    except Exception as conversion_exc:
                        logger.debug(f"Failed to extract/convert image {obj_name}: {conversion_exc}")
                        continue
                except Exception as inner_exc:
                    logger.warning("Failed extracting XObject image %s: %s", obj_name, inner_exc)
                    
            # Summary logging
            if image_xobjects > 0:
                logger.info(f"Page summary: {total_xobjects} XObjects, {image_xobjects} images, {supported_images} supported, {image_xobjects - supported_images} skipped")
                if unsupported_filters:
                    logger.info(f"Unsupported image filters found: {sorted(unsupported_filters)}")
            else:
                logger.debug("No image XObjects found on page")
                
        except Exception as exc:
            logger.warning("Failed scanning page XObjects for images: %s", exc)
        return results

    def _validate_and_resize_image_for_azure(self, image_bytes: bytes, image_mime: str, request_id: str, image_num: int, page_num: int) -> tuple[bytes | None, str | None]:
        """Validate and potentially resize image before sending to Azure OpenAI.
        
        Returns tuple of (processed_image_bytes, mime_type) or (None, None) if invalid.
        """
        # Check file size limits (Azure OpenAI has a 20MB limit, but we'll be more conservative)
        MAX_SIZE_MB = 15
        if len(image_bytes) > MAX_SIZE_MB * 1024 * 1024:
            logger.warning("[%s] Skipping image %d on page %d - file too large (%d MB)", 
                        request_id, image_num, page_num, len(image_bytes) // (1024 * 1024))
            return None, None
        
        # Check minimum size (avoid tiny images that are likely artifacts)
        MIN_SIZE_BYTES = 100
        if len(image_bytes) < MIN_SIZE_BYTES:
            logger.debug("[%s] Skipping image %d on page %d - file too small (%d bytes)", 
                        request_id, image_num, page_num, len(image_bytes))
            return None, None
        
        # Process and potentially resize image using PIL
        try:
            # Load image
            with Image.open(io.BytesIO(image_bytes)) as img:
                original_size = (img.width, img.height)
                
                # Check minimum dimensions
                if img.width < 10 or img.height < 10:
                    logger.debug("[%s] Skipping image %d on page %d - dimensions too small (%dx%d)", 
                            request_id, image_num, page_num, img.width, img.height)
                    return None, None
                
                # Check aspect ratio to avoid extremely stretched images
                aspect_ratio = max(img.width, img.height) / min(img.width, img.height)
                if aspect_ratio > 50:  # More lenient than before
                    logger.debug("[%s] Skipping image %d on page %d - extreme aspect ratio (%.1f)", 
                            request_id, image_num, page_num, aspect_ratio)
                    return None, None
                
                # Resize if dimensions are too large (common for vision APIs: 2048x2048 max)
                MAX_DIMENSION = 2048
                needs_resize = img.width > MAX_DIMENSION or img.height > MAX_DIMENSION
                
                if needs_resize:
                    # Calculate new size maintaining aspect ratio
                    scale_factor = min(MAX_DIMENSION / img.width, MAX_DIMENSION / img.height)
                    new_width = int(img.width * scale_factor)
                    new_height = int(img.height * scale_factor)
                    
                    logger.info("[%s] Resizing image %d on page %d from %dx%d to %dx%d (scale: %.2f)", 
                            request_id, image_num, page_num, img.width, img.height, 
                            new_width, new_height, scale_factor)
                    
                    # Resize with high quality
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    img = img_resized
                
                # Convert to RGB if necessary (remove alpha channel, handle grayscale)
                if img.mode in ("RGBA", "P"):
                    # Create white background for transparency
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = background
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                
                # Convert to JPEG for consistency
                output_buffer = io.BytesIO()
                img.save(output_buffer, format="JPEG", quality=85, optimize=True)
                processed_bytes = output_buffer.getvalue()
                processed_mime = "image/jpeg"
                
                if needs_resize:
                    logger.debug("[%s] Image %d on page %d processed: %s -> %s, %d -> %d bytes", 
                                request_id, image_num, page_num, 
                                f"{original_size[0]}x{original_size[1]}", f"{img.width}x{img.height}",
                                len(image_bytes), len(processed_bytes))
                else:
                    logger.debug("[%s] Image %d on page %d processed: %dx%d, %d bytes", 
                                request_id, image_num, page_num, img.width, img.height, len(processed_bytes))
                
                return processed_bytes, processed_mime
            
        except Exception as e:
            logger.warning("[%s] Skipping image %d on page %d - processing failed: %s", 
                        request_id, image_num, page_num, e)
            return None, None

    def _describe_image_azure(self, client: AzureOpenAI, deployment: str, image_b64: str, image_mime: str, *, request_id: str, page_index: int) -> str:
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "If the image contains any text, information, data, or content (including posters, signs, charts, tables, diagrams, forms, screenshots, documents, or any readable material), extract and transcribe ALL visible text and information exactly word-for-word. Output only the raw extracted content without any introductory phrases like 'this image shows' or 'the image contains'. For non-text content like charts or diagrams, provide the exact data, values, labels, and structural information present. If the image is purely decorative (logos, icons, backgrounds, dividers) with no meaningful information, reply exactly with SKIP and nothing else."},
                            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}},
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=4000,
            )
            logger.info("[%s] Image description success for page %s", request_id, page_index + 1)
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.error("[%s] Image description failed for page %s: %s", request_id, page_index + 1, exc, exc_info=True)
            return ""


    def _describe_image_bedrock(self, client, model_id: str, image_b64: str, image_mime: str, *, request_id: str, page_index: int) -> str:
        try:
            # Prepare the message for Claude 3.5 Sonnet
            message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "If the image contains any text, information, data, or content (including posters, signs, charts, tables, diagrams, forms, screenshots, documents, or any readable material), extract and transcribe ALL visible text and information exactly word-for-word. Output only the raw extracted content without any introductory phrases like 'this image shows' or 'the image contains'. For non-text content like charts or diagrams, provide the exact data, values, labels, and structural information present. If the image is purely decorative (logos, icons, backgrounds, dividers) with no meaningful information, reply exactly with SKIP and nothing else."
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": image_b64
                        }
                    }
                ]
            }
            
            # Prepare the request body for Bedrock
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.2,
                "messages": [message]
            }
            
            # Invoke the model
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(body)
            )
            
            # Parse the response and add explicit timeout & streaming read close 
            try:
                response_body = json.loads(response['body'].read())
            finally:
                # Ensure that the stream is closed 
                response["body"].close()

            content = response_body.get('content', [])
            
            if content and len(content) > 0:
                text_content = content[0].get('text', '').strip()
                logger.info("[%s] Bedrock image description success for page %s", request_id, page_index + 1)
                return text_content
            else:
                logger.warning("[%s] Bedrock returned empty content for page %s", request_id, page_index + 1)
                return ""
                
        except Exception as exc:
            logger.error("[%s] Bedrock image description failed for page %s: %s", request_id, page_index + 1, exc, exc_info=True)
            return ""
        
    def convert_pdf_to_markdown_optimized(
        self,
        pdf_path: str, 
        client, 
        model_name: str, 
        model_provider: ModelProvider,
        *,
        request_id: str, 
        include_images: bool = True 
    ) -> str: 
        """
        Enriched PDF conversion:
            - Extracts per-page text via pypdf
            - Extracts embedded images and obtain AI descriptions 
            - include_images=False -> Only description will be included
        """
        reader = PdfReader(pdf_path)
        markdown_output: list[str] = []

        for i, page in enumerate(reader.pages):
            page_num = i + 1 
            logger.info("[%s] Processing Page %d", request_id, page_num)

            # Extract text from the page locally 
            try:
                text = (page.extract_text() or "").strip()
                if text:
                    markdown_output.append(text)

            except Exception as e:
                logger.warning("[%s] Could not extract text from page %d: %s", request_id, page_num, e)

            # Extract and describe only embedded images (robust: scan XObjects and only accept JPEG/JP2)
            images_info = self.extract_images_from_page(page)
            if images_info:
                logger.info("[%s] Found %d extractable images on page %d", request_id, len(images_info),page_num)
                processed_images = 0
                skipped_images = 0

                for j, (image_mime, image_bytes) in enumerate(images_info):
                    try:
                        logger.debug("[%s] Processing image %d/%d on page %d (%s, %d bytes)", request_id, j + 1, len(images_info), page_num, image_mime, len(image_bytes))

                        # Validate and potentially resize image before processing 
                        processed_bytes, processed_mime = self._validate_and_resize_image_for_azure(
                            image_bytes, image_mime, request_id, j+1, page_num
                        )

                        if not processed_bytes:
                            skipped_images += 1
                            continue 

                        image_b64 = base64.b64encode(processed_bytes).decode("utf-8")

                        # Update mime type to the processed format 
                        image_mime = processed_mime 

                        # Call appropriate description function based on provider
                        if model_provider == ModelProvider.AZURE_OPENAI:
                            description = self._describe_image_azure(
                                client, model_name, image_b64, image_mime, request_id=request_id, page_index=i
                            )
                        elif model_provider == ModelProvider.AWS_BEDROCK:
                            description = self._describe_image_bedrock(
                                client, model_name, image_b64, image_mime, request_id=request_id, page_index=i
                            )
                        else:
                            logger.error("[%s] Unsupported model provider: %s", request_id, model_provider)
                            continue
                        
                        # Skip invalid images (no description due to Azure 400 or other issues)
                        if not description:
                            logger.warning("[%s] Skipping image %d on page %d due to invalid data/description", request_id, j + 1, page_num)
                            skipped_images += 1
                            continue
                            
                        # Skip images the model tagged as non-important
                        desc_trimmed = description.strip()
                        if desc_trimmed.upper() == "SKIP" or desc_trimmed.lower().startswith("skip"):
                            logger.info("[%s] AI marked image %d on page %d as non-important (SKIP)", request_id, j + 1, page_num)
                            skipped_images += 1
                            continue
                            
                        # Image successfully processed
                        processed_images += 1
                        logger.debug("[%s] Generated description for image %d on page %d (%d chars)", 
                                request_id, j + 1, page_num, len(description))
                        
                        if include_images:
                            markdown_output.append(
                                f"\n\n![Image {j+1} on Page {page_num}](data:{processed_mime};base64,{image_b64})\n\n{description}"
                            )
                        else:
                            markdown_output.append(
                                f"\n\n{description}"
                            )
                    except Exception as e:
                        logger.error("[%s] Failed to process image %d on page %d: %s", request_id, j + 1, page_num, e, exc_info=True)
                        skipped_images += 1
                        
                logger.info("[%s] Page %d image processing complete: %d processed, %d skipped", 
                        request_id, page_num, processed_images, skipped_images)
            else:
                logger.debug("[%s] No extractable images found on page %d", request_id, page_num)

        return "\n\n".join(markdown_output).strip()




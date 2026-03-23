import os 
import shutil
import datetime
from extraction.helper.common import logging as logutil 
from extraction.helper.common.auth import validate_endpoint_api_key
from fastapi import UploadFile, Header, HTTPException, Request, Query, APIRouter
from http import HTTPStatus
from extraction.helper.schemas.types import TextExtraction, ModelProvider
from extraction.helper.common.markdown import sanitize_markdown_output
from uuid import uuid4
from markitdown import MarkItDown
from typing import Any



router = APIRouter()
logger = logutil.get_logger("markitdown-endpoint")
@router.post("/extracts/",
             status_code=int(HTTPStatus.OK),
             response_model=TextExtraction,
             include_in_schema=False)
@router.post("/extracts",
             status_code=int(HTTPStatus.OK),
             responses={
                 int(HTTPStatus.OK):{
                "description": "Succesfuly extracted text",
                "content": {
                    "application/json": {"example": []}
                },
                "model": TextExtraction
                }
            }
            )
async def convert_markdown(
    request: Request,
    file: UploadFile,
    api_key: str | None = Header(None, alias="API_KEY", description="API key for endpoint authentication"),
    enrich_pdf: bool = Query(False, description="Deprecated. Ignored in MarkItDown endpoint."),
    model_provider: ModelProvider = Query(ModelProvider.AWS_BEDROCK, description="Deprecated. Ignored in MarkItDown endpoint."),
):
    # Validate endpoint API key at router layer, independent of extraction engine.
    await validate_endpoint_api_key(request, api_key=api_key)

    # Prepare temp folder
    hash = uuid4()
    folder_path = f"/tmp/{hash}"
    try:
        os.makedirs(folder_path, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create temp directory in /tmp: %s", e)
        raise HTTPException(status_code=500,
                            detail="Unable to create temporary storage")

    try:
        if file is not None:
            # Standard multipart/form-data upload 
            # Ensure we have a valid filename 
            filename = file.filename or f"upload_{hash}"
            # Remove any path separators for security 
            filename = os.path.basename(filename)
            if not filename or filename == "." or filename == "..":
                filename = f"upload_{hash}"
            file_path = f"{folder_path}/{filename}"
            with open(file_path, "wb") as f_out:
                shutil.copyfileobj(file.file, f_out)
        else:
            # Raw binary upload 
            # Try to get filename from headers, otherwise use a default
            filename = request.headers.get("x-filename", f"upload_{hash}")
            # Remove any path separators for security
            filename = os.path.basename(filename)
            if not filename or filename == "." or filename == "..":
                filename = f"upload_{hash}"
            file_path = f"{folder_path}/{filename}"
            body = await request.body()
            with open(file_path, "wb") as f_out:
                f_out.write(body)

        # If enrichment requested and input is a PDF, run enriched pipeline
        lower_name = os.path.basename(file_path).lower()
        request_id = str(hash)
        logger.info("[%s] Received request enrich_pdf=%s file=%s content_type=%s provider=%s",
                    request_id, enrich_pdf, os.path.basename(file_path), request.headers.get("content-type"), model_provider.value)

        is_pdf_upload = lower_name.endswith(".pdf") or request.headers.get("content-type", "").startswith("application/pdf")
        if model_provider == ModelProvider.AZURE_OPENAI:
            logger.info("model_provider is deprecated and ignored by MarkItDown endpoint")
        else:
            logger.info("model_provider is deprecated and ignored by MarkItDown endpoint")

        from extraction.helper.markitdown.PdfToMarkdown import PDFToMarkdown
        pdfToMarkdownHelper = PDFToMarkdown()

        if enrich_pdf:
            logger.info("[%s] enrich_pdf is deprecated and ignored in MarkItDown endpoint", request_id)

        docintel_endpoint = os.getenv("AZURE_DOC_INTEL_ENDPOINT") or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        docintel_key = os.getenv("AZURE_DOC_INTEL_KEY") or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        docintel_api_version = os.getenv("AZURE_DOC_INTEL_API_VERSION")
        use_docintel = is_pdf_upload and bool(docintel_endpoint and docintel_key)

        try:
            if use_docintel:
                from azure.core.credentials import AzureKeyCredential

                md_kwargs: dict[str, Any] = {
                    "docintel_endpoint": docintel_endpoint,
                    "docintel_credential": AzureKeyCredential(docintel_key),
                    "keep_data_uris": True,
                }
                if docintel_api_version:
                    md_kwargs["docintel_api_version"] = docintel_api_version

                md_instance = MarkItDown(**md_kwargs)
                result = md_instance.convert(file_path)
                text = result.text_content
                logger.info("[%s] Converted with Azure Document Intelligence mode", request_id)
            else:
                if is_pdf_upload:
                    logger.info("[%s] Azure Document Intelligence credentials not set; using standard MarkItDown path", request_id)
                md_instance = MarkItDown()
                result = md_instance.convert(file_path)
                text = result.text_content
                if is_pdf_upload:
                    image_markdown = pdfToMarkdownHelper.extract_pdf_images_markdown(
                        file_path,
                        request_id=request_id,
                    )
                    if image_markdown:
                        text = f"{(text or '').strip()}\n\n---\n\n## Extracted Images\n\n{image_markdown}".strip()
        except Exception as exc:
            if is_pdf_upload:
                logger.warning(
                    "[%s] MarkItDown conversion failed; using local PDF fallback: %s",
                    request_id,
                    exc,
                )
                text = pdfToMarkdownHelper.convert_pdf_to_markdown_local(
                    file_path,
                    request_id=request_id,
                    include_images=True,
                    include_page_text=True,
                )
            else:
                raise

        if is_pdf_upload:
            text = sanitize_markdown_output(text or "")

        # Generating metadata
        metadata: dict[str, Any] = {
            "fileName": file.filename, 
            "fileSize": str(file.size),
            "creationDate": datetime.datetime.now(
                tz=datetime.timezone.utc
            )
        }

        return {
            "markdown": text, 
            "metadata": metadata
        }

    except Exception as e:
        logger.error("[Error] Unexpected failure: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

   

    
    

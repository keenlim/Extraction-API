import os 
import shutil
import base64 
import datetime
from extraction.helper.common import logging as logutil 
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request, Query, APIRouter
from http import HTTPStatus
from extraction.helper.schemas.types import TextExtraction, ModelProvider
from extraction.helper.markitdown.markitdownHelper import MarkitDownHelper
from uuid import uuid4
from markitdown import MarkItDown
from typing import Any 
from extraction.helper.markitdown.PdfToMarkdown import PDFToMarkdown



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
    enrich_pdf: bool = Query(False, description="If true and input is a PDF, include inline image descriptions"),
    include_images: bool = Query(True, description="When enrich_pdf=true for PDFs, include original images inline before their descriptions; if false, include only descriptions"),
    model_provider: ModelProvider = Query(ModelProvider.AZURE_OPENAI, description="AI model provider to use for image description"),
):
    markitdownHelper = MarkitDownHelper()

    # Validate endpoint API Key
    await markitdownHelper.validate_api_key(request, api_key=api_key)

    # Initialise AI Client
    ai_client, model_name = markitdownHelper.initialise_AI_client(model_provider)

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
        
        if model_provider == ModelProvider.AZURE_OPENAI:
            logger.info("Using Azure OpenAI endpoint")
        else:
            logger.info("Using AWS Bedrock model")

        if enrich_pdf and (lower_name.endswith(".pdf") or request.headers.get("content-type", "").startswith("application/pdf")):
            logger.info("[%s] Running OPTIMIZED PDF conversion (image-only to LLM) include_images=%s", request_id, include_images)
            pdfToMarkdownHelper = PDFToMarkdown()
            text = pdfToMarkdownHelper.convert_pdf_to_markdown_optimized(
                file_path, 
                ai_client,
                model_name,
                model_provider,
                request_id=request_id, 
                include_images=include_images
            )
        else:
            if model_provider == ModelProvider.AZURE_OPENAI:
                # For Azure OpenAI, llm_model expects the deployment name 
                md_instance = MarkItDown(llm_client=ai_client, llm_model=model_name)
                result = md_instance.convert(file_path)
                text = result.text_content
            else:
                # For Bedrock, MarkItDown maynot support it directly, use basic converstion
                md_instance = MarkItDown()
                result = md_instance.convert(file_path)
                text = result.text_content 

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

   

    
    
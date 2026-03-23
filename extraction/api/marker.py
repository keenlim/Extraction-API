import datetime
import os
import shutil
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Form, Header, HTTPException, Request, UploadFile

from extraction.helper.common import logging as logutil
from extraction.helper.common.auth import validate_endpoint_api_key
from extraction.helper.common.markdown import sanitize_markdown_output
from extraction.helper.marker.markerHelper import convert_pdf_to_markdown, extract_structured_json
from extraction.helper.schemas.types import TextExtraction
import json


router = APIRouter()
logger = logutil.get_logger("marker-endpoint")


@router.post(
    "/extracts/",
    status_code=int(HTTPStatus.OK),
    response_model=TextExtraction,
    include_in_schema=False,
)
@router.post(
    "/extracts",
    status_code=int(HTTPStatus.OK),
    response_model=TextExtraction,
    responses={
        int(HTTPStatus.OK): {
            "description": "Successfully extracted text with marker",
            "content": {
                "application/json": {"example": []},
            },
            "model": TextExtraction,
        }
    },
)
async def convert_markdown_with_marker(
    request: Request,
    file: UploadFile,
    api_key: str | None = Header(None, alias="API_KEY", description="API key for endpoint authentication"),
):
    await validate_endpoint_api_key(request, api_key=api_key)

    request_id = str(uuid4())
    folder_path = f"/tmp/{request_id}"
    try:
        os.makedirs(folder_path, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create temp directory in /tmp: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to create temporary storage") from exc

    try:
        filename = file.filename or f"upload_{request_id}.pdf"
        filename = os.path.basename(filename)
        if not filename or filename in {".", ".."}:
            filename = f"upload_{request_id}.pdf"
        file_path = f"{folder_path}/{filename}"

        with open(file_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        lower_name = filename.lower()
        content_type = request.headers.get("content-type", "")
        is_pdf_upload = lower_name.endswith(".pdf") or content_type.startswith("application/pdf")
        if not is_pdf_upload:
            raise HTTPException(status_code=400, detail="Marker endpoint only supports PDF uploads")

        marker_output_dir = os.path.join(folder_path, "marker_output")
        text = convert_pdf_to_markdown(
            input_pdf=file_path,
            output_dir=marker_output_dir,
            include_images=True,
        )
        text = sanitize_markdown_output(text or "")

        metadata: dict[str, Any] = {
            "fileName": file.filename,
            "fileSize": str(file.size),
            "creationDate": datetime.datetime.now(tz=datetime.timezone.utc),
        }
        return {
            "markdown": text,
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[Error] Marker extraction failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)


@router.post(
    "/extracts/structured",
    status_code=int(HTTPStatus.OK),
    responses={
        int(HTTPStatus.OK): {
            "description": "Successfully extracted structured JSON with marker beta extraction",
            "content": {
                "application/json": {"example": {}},
            },
        }
    },
)
async def extract_structured_with_marker(
    request: Request,
    file: UploadFile,
    schema_json: str = Form(..., description="JSON schema string for marker structured extraction"),
    api_key: str | None = Header(None, alias="API_KEY", description="API key for endpoint authentication"),
):
    await validate_endpoint_api_key(request, api_key=api_key)

    request_id = str(uuid4())
    folder_path = f"/tmp/{request_id}"
    try:
        os.makedirs(folder_path, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create temp directory in /tmp: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to create temporary storage") from exc

    try:
        try:
            schema = json.loads(schema_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid schema_json: {exc}") from exc
        if not isinstance(schema, dict):
            raise HTTPException(status_code=400, detail="schema_json must be a JSON object")

        filename = file.filename or f"upload_{request_id}.pdf"
        filename = os.path.basename(filename)
        if not filename or filename in {".", ".."}:
            filename = f"upload_{request_id}.pdf"
        file_path = f"{folder_path}/{filename}"

        with open(file_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        lower_name = filename.lower()
        content_type = request.headers.get("content-type", "")
        is_pdf_upload = lower_name.endswith(".pdf") or content_type.startswith("application/pdf")
        if not is_pdf_upload:
            raise HTTPException(status_code=400, detail="Marker structured endpoint only supports PDF uploads")

        markdown = sanitize_markdown_output(
            convert_pdf_to_markdown(
                input_pdf=file_path,
                include_images=True,
            )
            or ""
        )
        analysis, document_json = extract_structured_json(
            input_pdf=file_path,
            schema=schema,
            existing_markdown=markdown,
        )

        metadata: dict[str, Any] = {
            "fileName": file.filename,
            "fileSize": str(file.size),
            "creationDate": datetime.datetime.now(tz=datetime.timezone.utc),
        }
        return {
            "markdown": markdown,
            "structured": json.loads(document_json),
            "analysis": analysis,
            "metadata": metadata,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[Error] Marker structured extraction failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

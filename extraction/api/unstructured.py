import datetime

from unstructured.partition.auto import partition 

from fastapi import UploadFile, HTTPException, APIRouter

from http import HTTPStatus

from extraction.helper.unstructured.unstructuredHelper import UnstructuredHelper
from extraction.helper.schemas.types import TextExtraction

from typing import Any

router = APIRouter()

helper_function = UnstructuredHelper()

@router.post("/extracts/",
        status_code=int(HTTPStatus.OK),
        response_model=TextExtraction,
        include_in_schema=False)
@router.post("/extracts",
        response_model=TextExtraction,
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
async def extract_text_document(file: UploadFile):
    """
    Extract text from an uploaded file.

    Args:
        file (UploadFile): The uploaded file to extact text from

    Returns:
        TextExtraction: The extracted text, metadata and token count for the uploaded file
    """
    # Raise exception when more than 1 file is uploaded
    await helper_function.validate_max_files([file])

    # Raise exceptions if files are:
    # 1. of unsupported file type
    # 2. Oversized file 
    await helper_function.validate_uploaded_file(file)

    try:
        # retrieve parsing configuration based on file's extension
        parsing_config = await helper_function.get_parsing_config(file.filename)
        
        # Extract text with OCR 
        elements = partition(
            file=file.file,
            metadata_filename=file.filename,
            content_type=file.content_type,
            skip_infer_table_types=[],
            **parsing_config
        )

        print(elements)

        if elements is None:
            raise HTTPException(
                status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                detail="Errors when extracting text"
            )

        # Convert extracted text to Markdown to facilitate LLM readability 
        markdown: str = "\n".join(
            [
                helper_function.convert_unstructured_element_to_markdown(i)
                for i in elements
            ]
        )

        # Generating metadata 
        metadata: dict[str, Any] = {
            "fileName": file.filename,
            "fileSize": str(file.size),
            "creationDate": datetime.datetime.now(
                tz=datetime.timezone.utc
            )
        }

    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
            detail="Errors when extracting text"
        )

    return {
            "markdown": markdown,
            "metadata": metadata
        }
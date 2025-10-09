import datetime

from enum import Enum
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from typing import Optional

class APIError(BaseModel):
    """
    Model representing an API error response.

    Attributes:
        code (int): HTTP status code of the error
        message (str): Description of the error
    """

    code: int
    message: str

class Metadata(BaseModel):
    """
    Model representing the file Metadata extracted from a document.

    Attributes:
        file_name (str): Name of the file
        file_size (str): Size of the file
        creation_date (datetime): Date when the file was created
    """

    model_config = ConfigDict(alias_generator=to_camel)

    file_name: str
    file_size: str
    creation_date: datetime.datetime
    # Optional field for security classification for now
    # [For future development]
    security_classification: Optional[str] = None


class TextExtraction(BaseModel):
    """
    Model representing the Text extraction results from documents

    Attributes:
        markdown (str): Extracted text from the document. Defaults to an empty
                    string
        tokens (int): Number of tokens present in the extracted text. Default
                      to 0
        metadata (dict[str, Any]): A dictionary containing file metadata with the
                         following properties:
            fileName (str): Name of file
            fileSize (str): Size of file
            creationDate (datetime): Creation date of file, formatted as a
                                date-time string
    """

    markdown: str = ""
    metadata: Metadata

class ModelProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
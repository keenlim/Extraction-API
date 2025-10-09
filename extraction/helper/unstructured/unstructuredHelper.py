from fastapi import UploadFile, HTTPException
from pathlib import Path
from extraction.helper.schemas.types import APIError
from http import HTTPStatus
from typing import Any

import html2text
from unstructured.partition.utils.constants import PartitionStrategy
from unstructured.documents.elements import Element


class UnstructuredHelper():
    def __init__(self):
        self.MAX_FILE_SIZE: int = 10 * 1024 * 1024  
        self.VALID_FILE_TYPES: list[str] = [".pdf", ".doc", ".docx", ".xlsx", ".xls", ".csv", ".txt"]
        self.MAX_FILE: int = 1
        self.FILE_PARSING_CONFIG: dict[str, dict[str, Any]]= {
            ".pdf": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".docx": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".doc": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".xlsx": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".xls": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".csv": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            ".txt": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            },
            "default": {
                "strategy": PartitionStrategy.HI_RES,
                "hi_res_model_name": "yolox",
                "infer_table_structure": True,
                "extract_image_block_types": ["Image"],
                "extract_image_block_to_payload": True
            }
        }
        super().__init__()

    async def get_parsing_config(self, filename: str):
        """
        Returns the parsing configuration dictionary for given file extension

        If no matching pattern is found, returns a default configuration
        """
        # Get file type
        file_extension = Path(filename).suffix
        # Get configuration
        configuration = self.FILE_PARSING_CONFIG[file_extension]
        if configuration is not None:
            return configuration
        # Default return
        return self.FILE_PARSING_CONFIG["default"]
    
    @staticmethod
    def convert_unstructured_element_to_markdown(element: Element):
        """
        Convert each element dictionary to a Markdown string based on its type 

        Args:
            element (Element): Document elements extracted from parition

        Returns:
            markdown_string: String formatted in Markdown format 
        """
        # Convert the element to dictionary 
        element_dict = element.to_dict()
        element_type = element_dict.get("type", "")
        text = element_dict.get("text", "")
        metadata = element_dict.get("metadata", {})

        # Determine the Markdown formatting based on the elemen type 
        # Determine the Markdown formatting based on the element type
        match element_type:
            case "Title":
                # Determine header level from category_depth. If not provided,
                # default to level 1
                category_depth = metadata.get("category_depth", 0)
                header_level = category_depth + 1
                markdown = f"{'#' * header_level} {text}\n"

            case "Header":
                # Render as a smaller header.
                markdown = f"{text}\n---"

            case "Footer":
                # Render as italicized text.
                markdown = f"---*{text}*\n"

            case "NarrativeText":
                # Render narrative text as a paragraph
                markdown = f"{text}\n"

            case "ListItem":
                # Render list items with a bullet and indentation

                # Get the category_depth, defaulting to 0 if not provided
                depth = metadata.get("category_depth", 0)

                # Use 2 spaces per depth level for indentation
                indent = "  " * depth
                markdown = f"{indent}- {text}\n"

            case "Table":
                # pip install html2text
                # Render tables in Markdown format with pipes (|) and dash (-)
                h = html2text.HTML2Text()
                h.ignore_links = False
                markdown = h.handle(metadata.get("text_as_html", ""))
                markdown = f"{markdown}\n"

            case "Image":
                # Render image text content and the Image path
                # Image base64 is extracted in metadata instead of
                # storing the extracted image in the figures directory
                markdown = (
                    f"Image Content: {text} \n\n"
                )

            case "FigureCaption":
                # Render figure captions as italic text
                markdown = f"*{text}*\n"

            case "PageBreak":
                # Render a horizontal rule to indicate a page break.
                markdown = "\n---\n"

            case "EmailAddress":
                # Create a mailto link.
                markdown = f"[{text}](mailto:{text})\n"

            case "CodeSnippet":
                # Render as a code block.
                markdown = f"```\n{text}\n```\n"

            case "Formula":
                # Render as a centered formula (using display math notation).
                markdown = f"$$ {text} $$\n"

            case _:
                # Default: output the text without special formatting
                markdown = f"{text}\n"

        return markdown

    async def validate_max_files(
            self,
            file: list[UploadFile]
        ) -> None:
        """
        Validates if all the file sizes are less thna the maximum allowable size

        Args:
            file (list[UploadFile]): Files to be validated

        Returns:
            None
        """
        if len(file) > self.MAX_FILE:
            raise HTTPException(
                status_code=int(HTTPStatus.BAD_REQUEST),
                detail="More than one file was uploaded"
            )
    
    async def validate_uploaded_file(
            self, 
            file: UploadFile
    ) -> None: 
        """
        Validates that files uploaded are within maximum allowable file size and that they are all supported file types 

        Args:
            file (UploadFile): File to be validated
        
        Returns: 
            None
        """
        oversize_files = []
        invalid_files = []

        if file.size > self.MAX_FILE_SIZE:
            oversize_files.append(file.filename)
        
        # Check file type
        file_extension = Path(file.filename).suffix
        if file_extension not in self.VALID_FILE_TYPES:
            invalid_files.append(file.filename)

        if len(oversize_files) > 0:
            raise HTTPException(
                status_code=int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
                detail=f"File size exceeds 10mb"
            )
        
        if len(invalid_files) > 0:
            raise HTTPException(
                status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
                detail=f"Unsupported file type."
            )




from __future__ import annotations

import json
import time
from typing import Annotated, List

import boto3
import PIL
import certifi
from botocore.config import Config as BotocoreConfig
from marker.logger import get_logger
from marker.schema.blocks import Block
from marker.services import BaseService
from pydantic import BaseModel

logger = get_logger()


class BedrockClaudeService(BaseService):
    """Marker-compatible LLM service backed by AWS Bedrock Claude models."""

    bedrock_model_id: Annotated[
        str,
        "Bedrock model ID to use for structured extraction.",
    ] = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    aws_region: Annotated[str, "AWS region for Bedrock runtime."] = "us-east-1"
    aws_access_key_id = None
    aws_secret_access_key = None
    aws_session_token = None
    anthropic_version: Annotated[str, "Anthropic Bedrock protocol version."] = "bedrock-2023-05-31"

    def process_images(self, images: List[PIL.Image.Image]) -> list:
        if isinstance(images, PIL.Image.Image):
            images = [images]

        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/webp",
                    "data": self.img_to_base64(img),
                },
            }
            for img in images
        ]

    def _get_client(self):
        kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": self.aws_region,
            "verify": certifi.where(),
            "config": BotocoreConfig(
                connect_timeout=5,
                read_timeout=self.timeout,
                retries={"max_attempts": max(1, self.max_retries + 1), "mode": "standard"},
            ),
        }
        if self.aws_access_key_id and self.aws_secret_access_key:
            kwargs["aws_access_key_id"] = self.aws_access_key_id
            kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        if self.aws_session_token:
            kwargs["aws_session_token"] = self.aws_session_token
        return boto3.client(**kwargs)

    def _validate_response(self, response_text: str, schema: type[BaseModel]) -> dict:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return schema.model_validate_json(text).model_dump()
        except Exception:
            try:
                escaped = text.replace("\\", "\\\\")
                return schema.model_validate_json(escaped).model_dump()
            except Exception:
                payload = json.loads(text)
                if isinstance(payload, dict) and isinstance(payload.get("document_json"), (dict, list)):
                    payload["document_json"] = json.dumps(payload["document_json"], ensure_ascii=False)
                return schema.model_validate(payload).model_dump()

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image] | None,
        block: Block | None,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        if max_retries is None:
            max_retries = self.max_retries
        if timeout is None:
            timeout = self.timeout

        schema_example = response_schema.model_json_schema()
        system_prompt = (
            "Follow the instructions given by the user prompt. "
            "You must provide your response in JSON format matching this schema:\n\n"
            f"{json.dumps(schema_example, indent=2)}\n\n"
            "Respond only with the JSON schema, nothing else."
        )

        image_data = self.format_image_for_llm(image)
        body = {
            "anthropic_version": self.anthropic_version,
            "max_tokens": self.max_output_tokens or 4096,
            "temperature": 0,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        *image_data,
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        total_tries = max_retries + 1
        client = self._get_client()
        for tries in range(1, total_tries + 1):
            try:
                response = client.invoke_model(
                    modelId=self.bedrock_model_id,
                    body=json.dumps(body),
                )
                try:
                    payload = json.loads(response["body"].read())
                finally:
                    response["body"].close()

                content = payload.get("content", [])
                if not content:
                    raise RuntimeError("Bedrock returned empty content")

                response_text = str(content[0].get("text", ""))
                out = self._validate_response(response_text, response_schema)
                if block:
                    block.update_metadata(llm_request_count=1)
                return out
            except Exception as exc:  # noqa: BLE001
                if tries == total_tries:
                    logger.error(
                        "Bedrock structured extraction failed after retries: %s",
                        exc,
                    )
                    break
                wait_time = tries * self.retry_wait_time
                logger.warning(
                    "Bedrock structured extraction error: %s. Retrying in %s seconds... (%s/%s)",
                    exc,
                    wait_time,
                    tries,
                    total_tries,
                )
                time.sleep(wait_time)

        return {}

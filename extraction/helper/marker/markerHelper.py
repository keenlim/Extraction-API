from __future__ import annotations

import json
import os
import base64
import io
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from marker.converters.extraction import ExtractionConverter
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


_ARTIFACT_CACHE: dict[str, Any] | None = None

load_dotenv()


def _get_marker_artifacts() -> dict[str, Any]:
    global _ARTIFACT_CACHE
    if _ARTIFACT_CACHE is None:
        _ARTIFACT_CACHE = create_model_dict()
    return _ARTIFACT_CACHE

def convert_pdf_to_markdown(
    input_pdf: str | Path,
    output_dir: str | Path | None = None,
    *,
    include_images: bool = True,
) -> str:
    """Convert a PDF to markdown using marker-pdf official Python API."""
    input_pdf_path = Path(input_pdf).expanduser().resolve()
    if output_dir is not None:
        Path(output_dir).expanduser().resolve().mkdir(parents=True, exist_ok=True)

    if input_pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Marker conversion expects a PDF input file.")
    if not input_pdf_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

    config: dict[str, Any] = {"extract_images": bool(include_images)}
    converter = PdfConverter(artifact_dict=_get_marker_artifacts(), config=config)
    rendered = converter(str(input_pdf_path))
    text, _, images = text_from_rendered(rendered)
    markdown = text.strip()
    if include_images and images:
        markdown = _inline_marker_images(markdown, images)
    return markdown


def extract_structured_json(
    input_pdf: str | Path,
    schema: dict[str, Any],
    *,
    existing_markdown: str | None = None,
) -> tuple[str, str]:
    """Run marker beta structured extraction and return (analysis, document_json)."""
    input_pdf_path = Path(input_pdf).expanduser().resolve()

    if input_pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Structured extraction expects a PDF input file.")
    if not input_pdf_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

    llm_service, llm_config = _resolve_structured_llm_config()
    config: dict[str, Any] = {
        "use_llm": True,
        "page_schema": schema,
        **llm_config,
    }
    if existing_markdown:
        config["existing_markdown"] = existing_markdown

    converter = ExtractionConverter(
        artifact_dict=_get_marker_artifacts(),
        config=config,
        llm_service=llm_service,
    )
    try:
        rendered = converter(str(input_pdf_path))
    except AttributeError as exc:
        if "analysis" in str(exc):
            raise RuntimeError(
                "Marker structured extraction failed before rendering output. "
                "Check configured LLM backend credentials/connectivity."
            ) from exc
        raise
    if rendered is None or not getattr(rendered, "document_json", None):
        raise RuntimeError(
            "Marker structured extraction returned no output. "
            "Check LLM credentials/connectivity and try again."
        )

    # Validate JSON payload is parseable to fail fast on malformed model output.
    json.loads(rendered.document_json)
    return rendered.analysis.strip(), rendered.document_json.strip()


def _resolve_structured_llm_config() -> tuple[str, dict[str, Any]]:
    backend = os.getenv("MARKER_STRUCTURED_LLM_BACKEND", "auto").strip().lower()

    def _bedrock_config() -> tuple[str, dict[str, Any]]:
        return (
            "extraction.helper.marker.bedrockService.BedrockClaudeService",
            {
                "bedrock_model_id": os.getenv(
                    "MARKER_BEDROCK_MODEL_ID",
                    os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0"),
                ),
                "aws_region": os.getenv("AWS_REGION", "us-east-1"),
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "aws_session_token": os.getenv("AWS_SESSION_TOKEN"),
            },
        )

    def _azure_config() -> tuple[str, dict[str, Any]] | None:
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if not (azure_endpoint and azure_api_key and deployment_name):
            return None
        return (
            "marker.services.azure_openai.AzureOpenAIService",
            {
                "azure_endpoint": azure_endpoint,
                "azure_api_key": azure_api_key,
                "deployment_name": deployment_name,
                "azure_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
            },
        )

    def _openai_config() -> tuple[str, dict[str, Any]] | None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return None
        return (
            "marker.services.openai.OpenAIService",
            {
                "openai_api_key": openai_api_key,
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            },
        )

    def _gemini_config() -> tuple[str, dict[str, Any]] | None:
        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            return None
        return (
            "marker.services.gemini.GoogleGeminiService",
            {
                "gemini_api_key": gemini_api_key,
                "gemini_model_name": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            },
        )

    # Explicit backend selection
    if backend == "bedrock":
        return _bedrock_config()
    if backend == "azure":
        cfg = _azure_config()
        if cfg is None:
            raise RuntimeError("MARKER_STRUCTURED_LLM_BACKEND=azure but Azure env vars are missing.")
        return cfg
    if backend == "openai":
        cfg = _openai_config()
        if cfg is None:
            raise RuntimeError("MARKER_STRUCTURED_LLM_BACKEND=openai but OPENAI_API_KEY is missing.")
        return cfg
    if backend == "gemini":
        cfg = _gemini_config()
        if cfg is None:
            raise RuntimeError("MARKER_STRUCTURED_LLM_BACKEND=gemini but GEMINI_API_KEY/GOOGLE_API_KEY is missing.")
        return cfg

    # Auto mode: prefer Bedrock in this repo, then Azure, OpenAI, Gemini.
    if backend not in {"", "auto"}:
        raise RuntimeError(
            "Invalid MARKER_STRUCTURED_LLM_BACKEND. Use one of: auto, bedrock, azure, openai, gemini."
        )
    if os.getenv("AWS_BEDROCK_MODEL_ID") or (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
        return _bedrock_config()

    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    if azure_endpoint and azure_api_key and deployment_name:
        return (
            "marker.services.azure_openai.AzureOpenAIService",
            {
                "azure_endpoint": azure_endpoint,
                "azure_api_key": azure_api_key,
                "deployment_name": deployment_name,
                "azure_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
            },
        )

    openai_cfg = _openai_config()
    if openai_cfg is not None:
        return openai_cfg

    gemini_cfg = _gemini_config()
    if gemini_cfg is not None:
        return gemini_cfg

    raise RuntimeError(
        "Structured extraction requires one configured LLM backend. Set either "
        "AWS_BEDROCK_MODEL_ID (or AWS credentials), "
        "AZURE_OPENAI_ENDPOINT+AZURE_OPENAI_API_KEY+AZURE_OPENAI_DEPLOYMENT, "
        "OPENAI_API_KEY, or GEMINI_API_KEY/GOOGLE_API_KEY."
    )


def _inline_marker_images(markdown: str, images: dict[str, Any]) -> str:
    pattern = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")

    def replace(match: re.Match[str]) -> str:
        alt = match.group("alt")
        src = match.group("src").strip()
        image_key = src
        if image_key not in images:
            image_key = Path(src).name
        image_obj = images.get(image_key)
        if image_obj is None:
            return match.group(0)

        suffix = Path(image_key).suffix.lower()
        img_format = "PNG"
        mime_type = "image/png"
        if suffix in {".jpg", ".jpeg"}:
            img_format = "JPEG"
            mime_type = "image/jpeg"
        elif suffix == ".webp":
            img_format = "WEBP"
            mime_type = "image/webp"

        buffer = io.BytesIO()
        image_obj.save(buffer, format=img_format)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"![{alt}](data:{mime_type};base64,{encoded})"

    return pattern.sub(replace, markdown)


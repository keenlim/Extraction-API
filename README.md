# Extraction-API Source Code 

FastAPI server providing a Wrapper for Microsoft MarkItDown and Unstructured.io 

### MarkItDown
A simple service/library that converts many file types (PDF, DOCX, PPTX, images, HTML, etc.) into clean Markdown for downstream use.

```
/markitdown/extracts
```

MarkItDown uses Azure Document Intelligence for PDFs when `AZURE_DOC_INTEL_ENDPOINT` and `AZURE_DOC_INTEL_KEY` are set. If they are not set, it automatically falls back to standard MarkItDown conversion.

### Unstructured.io
A Python-first toolkit and hosted services for document parsing & chunking. Converts diverse formats (PDF, DOCX, PPTX, EML, HTML, images, etc.) into structured “elements” (Title, NarrativeText, Table, FigureCaption, etc.), with optional OCR and layout models.

```
/unstructured/extracts
```

## Installation

1. Clone the repository
2. Create `.env` from `.env.example`
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file with the required variables for your chosen AI provider.

### For Azure OpenAI

```
API_KEY=your_api_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-azure-openai-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment-name
PORT=8080
```

### For Azure Document Intelligence (MarkItDown doc-intel mode)

```
AZURE_DOC_INTEL_ENDPOINT=https://your-doc-intel-resource.cognitiveservices.azure.com
AZURE_DOC_INTEL_KEY=your-doc-intel-key
AZURE_DOC_INTEL_API_VERSION=2024-11-30
```

### For AWS Bedrock (Claude 3.5 Sonnet) - Default

```
API_KEY=your_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
PORT=8080
```

**Note:** `API_KEY` is endpoint authentication for this service and is separate from cloud provider credentials.

## Running the Server

Start the server with:

```bash
PORT=8080 python3 -m extraction.main
```

## Quick PDF to Markdown check

```bash
curl -sS -X POST "http://127.0.0.1:8080/markitdown/extracts?model_provider=aws_bedrock" \
	-H "API_KEY: YOUR_API_KEY" \
	-F "file=@sample_docs/sample_docs.pdf" \
	> response.json
```

To use Azure Document Intelligence mode for PDF conversion:

```bash
curl -sS -X POST "http://127.0.0.1:8080/markitdown/extracts" \
	-H "API_KEY: YOUR_API_KEY" \
	-F "file=@sample_docs/sample_docs.pdf" \
	> response_docintel.json
```

Then extract markdown:

```bash
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("response.json").read_text(encoding="utf-8"))
Path("response.md").write_text(data.get("markdown", ""), encoding="utf-8")
print("Wrote response.md")
PY
```

## Run with Docker Compose 

1. Copy `.env.example` to `.env` and fill in your values.
2. Run:

```sh
docker compose up
```


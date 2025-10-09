# Extraction-API Source Code 

FastAPI server providing a Wrapper for Microsoft MarkItDown and Unstructured.io 

### MarkItDown
A simple service/library that converts many file types (PDF, DOCX, PPTX, images, HTML, etc.) into clean Markdown for downstream use.

```
/markitdown/extracts
```

### Unstructured.io
A Python-first toolkit and hosted services for document parsing & chunking. Converts diverse formats (PDF, DOCX, PPTX, EML, HTML, images, etc.) into structured “elements” (Title, NarrativeText, Table, FigureCaption, etc.), with optional OCR and layout models.

```
unstructured/extracts
```

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file with the required variables for your chosen AI provider:

### For Azure OpenAI

```
API_KEY=your_api_key_here
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-azure-openai-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-deployment-name
```

### For AWS Bedrock (Claude 3.5 Sonnet) - Default

```
API_KEY=your_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
```

**Note:** When using AWS Bedrock, ensure that:

1. Your AWS credentials have permissions to access Amazon Bedrock
2. You have requested access to Claude 3.5 Sonnet model in your AWS region
3. The Claude 3.5 Sonnet model is available in your chosen AWS region
4. `AWS_BEDROCK_MODEL_ID` is optional and defaults to `anthropic.claude-3-5-sonnet-20240620-v1:0`

## Running the Server

Start the server with:
```bash
python3 -m extraction.main
```

## Run with Docker Compose 
1. Copy `.env.example` to `.env` and fill in your API keys.
2. Run:

```sh
docker compose up
```
## Environment Variables

- `API_KEY`: The key required for endpoint authentication.
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key.
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL.
- `AZURE_OPENAI_API_VERSION`: Azure OpenAI API version.
- `AZURE_OPENAI_DEPLOYMENT`: Azure OpenAI deployment name for the model to use.
- `PORT`: The port the API will run on (default 8080).
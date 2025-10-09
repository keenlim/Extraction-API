import os 
from fastapi import Request, HTTPException
from dotenv import load_dotenv
from extraction.helper.schemas.types import ModelProvider
from openai import AzureOpenAI
import boto3

# Load environment variables
load_dotenv()

class MarkitDownHelper():
    def __init__(self):
        pass
    
    @staticmethod
    def initialise_AI_client(model_provider: str): 
        # Initialize AI client based on provider
        if model_provider == ModelProvider.AZURE_OPENAI:
            # Get Azure OpenAI configuration from environment variables
            azure_openai_api_key = os.getenv('AZURE_OPENAI_API_KEY')
            azure_openai_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            azure_openai_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
            azure_openai_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT')

            if not azure_openai_api_key:
                raise HTTPException(status_code=500, detail="AZURE_OPENAI_API_KEY not found in environment variables")
            if not azure_openai_endpoint:
                raise HTTPException(status_code=500, detail="AZURE_OPENAI_ENDPOINT not found in environment variables")
            if not azure_openai_deployment:
                raise HTTPException(status_code=500, detail="AZURE_OPENAI_DEPLOYMENT (deployment name) not found in environment variables")
            
            # Initialize Azure OpenAI client
            ai_client = AzureOpenAI(
                api_key=azure_openai_api_key,
                azure_endpoint=azure_openai_endpoint,
                api_version=azure_openai_api_version
            )
            model_name = azure_openai_deployment
            
        elif model_provider == ModelProvider.AWS_BEDROCK:
            # Get AWS Bedrock configuration from environment variables
            aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            bedrock_model_id = os.getenv('AWS_BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
            
            if not aws_access_key_id or not aws_secret_access_key:
                raise HTTPException(status_code=500, detail="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set for Bedrock")
            
            # Initialize Bedrock client
            ai_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region
            )
            model_name = bedrock_model_id
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported model provider: {model_provider}")
        
        return ai_client, model_name
    
    async def validate_api_key(self, request: Request, api_key: str) -> None:
        # Validate endpoint API key
        expected_api_key = os.getenv('API_KEY')
        print(expected_api_key)
        if not expected_api_key:
            raise HTTPException(status_code=500, detail="Endpoint API key not configured on server")
        # Support multiple header conventions and proxy-safe names
        # Primary: explicit Header param using underscore (may be stripped by some proxies)
        provided_api_key = api_key
        if not provided_api_key:
            # Starlette lower-cases header names; prefer hyphenated variants that survive proxies
            headers = request.headers
            provided_api_key = (
                headers.get('x-api-key')
                or headers.get('api-key')
                or headers.get('api_key')
                or headers.get('x_api_key')
                or headers.get('api_key')
            )
            if not provided_api_key:
                auth_header = headers.get('authorization')
                if auth_header and auth_header.lower().startswith('bearer '):
                    provided_api_key = auth_header[7:].strip()

        if provided_api_key != expected_api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        
    
        
    



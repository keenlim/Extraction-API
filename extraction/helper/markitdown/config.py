from pydantic import BaseSettings
from typing import Optional 

class Settings(BaseSettings):
    # Endpoint auth
    API_KEY: str 

    # Azure OpenAI configuration
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_VERSION="2024-12-01-preview"
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = None 

    # AWS Bedrock Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BEDROCK_MODEL_ID: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    class Config:
        env_file = ".env"
        case_sensitive = False

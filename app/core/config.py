# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "VoiceAlert-Cloud"
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "DEVELOPMENT")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "mock_key")
    
settings = Settings()


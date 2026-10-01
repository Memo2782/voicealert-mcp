# app/core/config.py
import os
from dotenv import load_config

load_config()

class Settings:
    PROJECT_NAME: str = "VoiceAlert-5G-Core"
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "DEVELOPMENT")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "mock_key")
    
settings = Settings()


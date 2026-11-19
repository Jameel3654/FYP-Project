"""
Configuration management for the AI engine.
Loads environment variables using python-dotenv.
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings class."""
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LABSE_MODEL_NAME: str = os.getenv("LABSE_MODEL_NAME", "sentence-transformers/LaBSE")
    SPACY_MODEL: str = os.getenv("SPACY_MODEL", "en_core_web_sm")
    LLMLINGUA_MODEL: str = os.getenv("LLMLINGUA_MODEL", "NousResearch/Llama-2-7b-hf")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

# Singleton instance
settings = Settings()

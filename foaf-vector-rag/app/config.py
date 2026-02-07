"""Configuration settings for the FoaF Vector RAG application."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    API_TITLE: str = "FoaF Vector RAG API"
    API_VERSION: str = "1.0.0"
    API_PORT: int = 8001

    # LLM Settings (Google Gemini)
    GOOGLE_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.0

    # Vector Store Settings
    CHROMA_PERSIST_DIR: str = "data/chroma_store"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RETRIEVAL_TOP_K: int = 10

    # HuggingFace (optional — suppresses download warnings)
    HF_TOKEN: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Set HF_TOKEN env var so huggingface_hub picks it up automatically
if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN

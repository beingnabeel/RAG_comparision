from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_llm() -> ChatGoogleGenerativeAI:
    """Get a configured Google Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def is_llm_configured() -> bool:
    """Check if the Google Gemini API key is configured."""
    return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.strip())

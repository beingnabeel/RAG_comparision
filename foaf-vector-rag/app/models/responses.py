from pydantic import BaseModel, Field
from typing import Optional, Any


class QueryResponse(BaseModel):
    success: bool
    query: str
    intent: Optional[str] = None
    results: Optional[Any] = None
    response: str
    retrieval_count: Optional[int] = None
    execution_time_ms: Optional[float] = None


class ChatResponse(BaseModel):
    success: bool
    message: str
    response: str
    intent: Optional[str] = None
    retrieval_count: int = 0
    execution_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    vector_store_connected: bool
    llm_configured: bool
    collection_stats: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

from pydantic import BaseModel, Field
from typing import Optional, Any


class QueryResponse(BaseModel):
    success: bool
    query: str
    intent: Optional[str] = None
    results: Optional[Any] = None
    response: str
    sparql_query: Optional[str] = None
    execution_time_ms: Optional[float] = None


class AddPersonResponse(BaseModel):
    success: bool
    person_uri: Optional[str] = None
    message: str


class AddRelationshipResponse(BaseModel):
    success: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    fuseki_connected: bool
    llm_configured: bool
    graph_size: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

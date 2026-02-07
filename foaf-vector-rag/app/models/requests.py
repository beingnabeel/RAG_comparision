from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query about the FoaF network")
    include_metadata: bool = Field(False, description="Include retrieval metadata in response")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Natural language message from the user")

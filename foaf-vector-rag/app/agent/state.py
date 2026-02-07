"""Agent state definition for LangGraph."""

from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    user_query: str
    intent: str  # 'query', 'add_person', 'add_relationship', 'update', 'error'
    retrieved_context: str
    retrieved_docs: list
    retrieval_count: int
    final_response: str
    error: Optional[str]

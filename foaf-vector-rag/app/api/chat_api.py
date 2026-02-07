"""Chat API and log streaming endpoints for the chatbot web UI."""

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel, Field
from typing import Optional

from app.agent.vector_agent import run_agent
from app.utils.log_collector import log_collector, LogEntry
from app.utils.logging import get_logger

logger = get_logger(__name__)

chat_router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., description="Natural language message from the user")


class ChatResponse(BaseModel):
    success: bool
    message: str
    response: str
    intent: Optional[str] = None
    retrieval_count: int = 0
    execution_time_ms: Optional[float] = None


@chat_router.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a natural language query through the vector RAG agent."""
    user_msg = request.message.strip()
    if not user_msg:
        return ChatResponse(
            success=False, message=user_msg, response="Please enter a message.",
        )

    log_collector.add_entry(LogEntry(
        "info", "info", "User Query Received",
        f"Processing: \"{user_msg}\"", {"query": user_msg},
    ))

    try:
        result = await run_agent(user_msg)

        status = "success" if result["success"] else "error"
        log_collector.add_entry(LogEntry(
            "response", status, "Agent Response",
            f"{'Success' if result['success'] else 'Failed'} — {result.get('retrieval_count', 0)} docs retrieved in {result.get('execution_time_ms', 0):.0f}ms",
            {
                "intent": result.get("intent", ""),
                "retrieval_count": result.get("retrieval_count", 0),
                "execution_time_ms": result.get("execution_time_ms"),
            },
        ))

        return ChatResponse(
            success=result["success"],
            message=user_msg,
            response=result.get("response", "No response generated."),
            intent=result.get("intent"),
            retrieval_count=result.get("retrieval_count", 0),
            execution_time_ms=result.get("execution_time_ms"),
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        log_collector.add_entry(LogEntry(
            "error", "error", "Chat Error", str(e), {},
        ))
        return ChatResponse(
            success=False, message=user_msg, response=f"An error occurred: {str(e)}",
        )


@chat_router.get("/api/logs")
async def get_logs():
    """Return all collected log entries."""
    entries = log_collector.get_all()
    return {"count": len(entries), "logs": entries}


@chat_router.delete("/api/logs")
async def clear_logs():
    """Clear all collected log entries."""
    log_collector.clear()
    return {"success": True, "message": "Logs cleared"}


@chat_router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Stream log entries in real-time to the connected client."""
    await log_collector.ws_loop(websocket)

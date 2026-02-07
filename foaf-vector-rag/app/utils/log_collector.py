"""In-memory log collector with WebSocket broadcasting for the chatbot UI.

Captures structured log events from the vector RAG pipeline (intent classification,
document retrieval, LLM calls, errors) and streams them to connected WebSocket
clients in real-time.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Set
from uuid import uuid4

from fastapi import WebSocket


class LogEntry:
    """A single structured log event."""

    def __init__(
        self,
        log_type: str,
        status: str,
        title: str,
        message: str,
        details: Dict[str, Any] = None,
    ):
        self.id = str(uuid4())
        self.timestamp = datetime.now().isoformat()
        self.type = log_type
        self.status = status
        self.title = title
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type,
            "status": self.status,
            "title": self.title,
            "message": self.message,
            "details": self.details,
        }


class LogCollector:
    """Thread-safe in-memory log store with WebSocket streaming."""

    def __init__(self, max_entries: int = 1000):
        self._entries: List[LogEntry] = []
        self._max_entries = max_entries
        self._clients: Set[WebSocket] = set()
        self._counter = 0

    def add_entry(self, entry: LogEntry):
        self._entries.append(entry)
        self._counter += 1
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    @property
    def counter(self) -> int:
        return self._counter

    def get_entries_since(self, index: int) -> List[Dict]:
        offset = index - (self._counter - len(self._entries))
        if offset < 0:
            offset = 0
        return [e.to_dict() for e in self._entries[offset:]]

    def get_all(self) -> List[Dict]:
        return [e.to_dict() for e in self._entries]

    def clear(self):
        self._entries.clear()
        self._counter = 0

    async def register(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def unregister(self, ws: WebSocket):
        self._clients.discard(ws)

    async def ws_loop(self, ws: WebSocket):
        """Stream new log entries to a single WebSocket client."""
        await self.register(ws)
        last_seen = self._counter
        try:
            while True:
                current = self._counter
                if current > last_seen:
                    entries = self.get_entries_since(last_seen)
                    for entry in entries:
                        await ws.send_json({"type": "log", "data": entry})
                    last_seen = current
                elif current < last_seen:
                    await ws.send_json({"type": "clear"})
                    last_seen = 0
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=0.15)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break
        except Exception:
            pass
        finally:
            self.unregister(ws)


log_collector = LogCollector()


class AgentLogHandler(logging.Handler):
    """Captures Python log messages from agent modules and converts them
    into structured LogEntry objects for the UI."""

    INTENT_RE = re.compile(r"Classified intent.*?:\s*(\w+)\s+for query:\s*(.+)")
    RETRIEVAL_RE = re.compile(r"Retrieved (\d+) documents? for query: (.+)")
    HTTP_RE = re.compile(r'HTTP Request: (POST|GET)\s+(\S+)\s+"(HTTP/[\d.]+\s+\d+[^"]*)"')
    RATE_LIMIT_RE = re.compile(r"Rate limited.*?attempt (\d+)/(\d+).*?waiting (\d+)s")

    def emit(self, record: logging.LogRecord):
        try:
            self._process(record)
        except Exception:
            pass

    def _process(self, record: logging.LogRecord):
        name = record.name
        msg = record.getMessage()
        level = record.levelname
        entry = None

        # Intent classification
        if "Classified intent" in msg:
            m = self.INTENT_RE.search(msg)
            if m:
                entry = LogEntry(
                    "intent", "success",
                    "Intent Classification",
                    f"Classified as: {m.group(1)}",
                    {"intent": m.group(1), "query": m.group(2)},
                )

        # Document retrieval
        elif "Retrieved" in msg and "documents" in msg:
            m = self.RETRIEVAL_RE.search(msg)
            if m:
                entry = LogEntry(
                    "retrieval", "success",
                    "Document Retrieval",
                    f"Retrieved {m.group(1)} documents for: {m.group(2)}",
                    {"doc_count": m.group(1), "query": m.group(2)},
                )

        # LLM HTTP call
        elif "HTTP Request:" in msg and "httpx" in name:
            m = self.HTTP_RE.search(msg)
            if m:
                is_ok = "200" in m.group(3)
                entry = LogEntry(
                    "llm_call", "success" if is_ok else "error",
                    "LLM API Call",
                    f"{m.group(1)} → {m.group(3)}",
                    {"method": m.group(1), "url": m.group(2)[:120], "response": m.group(3)},
                )

        # AFC info
        elif "AFC is enabled" in msg:
            entry = LogEntry("info", "info", "LLM Config", msg, {})

        # Rate limiting
        elif "Rate limited" in msg:
            m = self.RATE_LIMIT_RE.search(msg)
            entry = LogEntry(
                "warning", "warning",
                "Rate Limited",
                msg,
                {"attempt": m.group(1) if m else "?", "wait_seconds": m.group(3) if m else "?"},
            )

        # Retrieval failures
        elif "Retrieval failed" in msg or "Vector search failed" in msg:
            entry = LogEntry("retrieval", "error", "Retrieval Failed", msg, {})

        # Agent errors
        elif "Agent execution failed" in msg:
            entry = LogEntry("error", "error", "Agent Error", msg, {})

        # Generic errors / warnings
        elif level == "ERROR" and entry is None:
            entry = LogEntry("error", "error", "Error", msg, {"logger": name})

        elif level == "WARNING" and entry is None:
            entry = LogEntry("warning", "warning", "Warning", msg, {"logger": name})

        if entry:
            log_collector.add_entry(entry)


def setup_log_capture():
    """Install the AgentLogHandler on all relevant loggers."""
    handler = AgentLogHandler()
    handler.setLevel(logging.DEBUG)

    for logger_name in [
        "app.agent.vector_agent",
        "app.vector.chroma_client",
        "app.vector.retriever",
        "app.llm.llm_client",
        "app.api.chat_api",
        "google_genai.models",
        "httpx",
    ]:
        lg = logging.getLogger(logger_name)
        lg.addHandler(handler)

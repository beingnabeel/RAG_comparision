"""FastAPI application entry point for the FoaF Graph RAG API."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.endpoints import router
from app.api.graph_viz import viz_router
from app.api.chat_api import chat_router
from app.utils.logging import setup_logging
from app.utils.log_collector import setup_log_capture

setup_logging()
setup_log_capture()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="A Graph RAG application for managing a Friends-of-a-Friend (FoaF) knowledge graph. "
    "Uses Apache Jena Fuseki as the graph database and OpenAI GPT-4 for natural language understanding.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(viz_router)
app.include_router(chat_router)

# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return {
        "message": "FoaF Graph RAG API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "visualizer": "/visualize",
        "chatbot": "/chat",
    }


@app.get("/visualize")
async def visualize():
    """Serve the interactive graph visualizer."""
    return FileResponse(os.path.join(static_dir, "visualizer.html"))


@app.get("/chat")
async def chatbot_ui():
    """Serve the interactive chatbot UI."""
    return FileResponse(os.path.join(static_dir, "chatbot.html"))

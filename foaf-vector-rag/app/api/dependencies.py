"""Dependency injection for FastAPI."""

from app.vector.chroma_client import VectorStore, vector_store


def get_vector_store() -> VectorStore:
    return vector_store

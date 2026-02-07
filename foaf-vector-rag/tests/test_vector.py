"""Tests for the FoaF Vector RAG system."""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_config_loads():
    """Settings should load without error."""
    from app.config import settings
    assert settings.API_TITLE == "FoaF Vector RAG API"
    assert settings.EMBEDDING_MODEL == "all-MiniLM-L6-v2"


def test_vector_store_connection():
    """ChromaDB should be accessible."""
    from app.vector.chroma_client import vector_store
    assert vector_store.test_connection() is True


def test_documents_collection_exists():
    """After ingestion, the documents collection should have chunks."""
    from app.vector.chroma_client import vector_store
    stats = vector_store.get_stats()
    if stats.get("documents", 0) > 0:
        assert stats["total_chunks"] > 0


def test_retriever_returns_results():
    """Retriever should return documents for a known query."""
    from app.vector.chroma_client import vector_store
    stats = vector_store.get_stats()
    if stats.get("documents", 0) == 0:
        pytest.skip("No data ingested yet")

    from app.vector.retriever import retrieve_documents
    result = retrieve_documents("Rajesh Sharma")
    assert result["total_retrieved"] > 0
    assert len(result["context"]) > 0


def test_chunk_search():
    """Chunk search should find relevant document chunks."""
    from app.vector.chroma_client import vector_store
    stats = vector_store.get_stats()
    if stats.get("documents", 0) == 0:
        pytest.skip("No data ingested yet")

    from app.vector.retriever import search_chunks
    result = search_chunks("Rajesh Sharma")
    assert result["success"] is True
    assert result["count"] > 0


def test_llm_configured():
    """LLM should be configured if API key is set."""
    from app.llm.llm_client import is_llm_configured
    # This depends on .env being present
    # Just test the function doesn't crash
    result = is_llm_configured()
    assert isinstance(result, bool)

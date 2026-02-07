"""Agent tools for interacting with the FoaF vector store."""

from langchain_core.tools import tool
from typing import Dict, Any

from app.vector.retriever import retrieve_documents, search_chunks
from app.utils.logging import get_logger

logger = get_logger(__name__)


@tool
def vector_search(query: str, top_k: int = 10) -> Dict[str, Any]:
    """Search the FoaF vector database for information related to a query.

    Args:
        query: Natural language query string
        top_k: Number of results to retrieve per collection

    Returns:
        Dictionary with retrieved documents and context
    """
    try:
        result = retrieve_documents(query, top_k=top_k)
        return {
            "success": True,
            "context": result["context"],
            "total_retrieved": result["total_retrieved"],
            "documents": result["documents"],
        }
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return {"success": False, "error": str(e), "context": "", "total_retrieved": 0}


@tool
def search_document_chunks(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Search for specific document chunks in the vector database.

    Args:
        query: Search query string
        top_k: Number of results to return

    Returns:
        Dictionary with matching chunks or error
    """
    try:
        result = search_chunks(query, top_k=top_k)
        return result
    except Exception as e:
        logger.error(f"Chunk search failed: {e}")
        return {"success": False, "error": str(e)}


ALL_TOOLS = [
    vector_search,
    search_document_chunks,
]

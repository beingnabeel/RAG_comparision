"""Semantic retrieval from the ChromaDB documents collection.

Queries the single 'documents' collection (containing chunked PDF/DOCX text)
and returns relevant chunks as context for the LLM.
"""

from typing import List, Dict, Any

from app.vector.chroma_client import vector_store
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "documents"


def retrieve_documents(query: str, top_k: int = None) -> Dict[str, Any]:
    """Retrieve relevant document chunks for a user query.

    Args:
        query: Natural language query string.
        top_k: Number of chunks to retrieve (default from settings).

    Returns:
        Dictionary with retrieved chunks and a merged 'context' string for the LLM.
    """
    if top_k is None:
        top_k = settings.RETRIEVAL_TOP_K

    all_docs: List[Dict[str, Any]] = []

    try:
        coll = vector_store.get_collection(COLLECTION_NAME)
        count = coll.count()
        if count == 0:
            logger.warning("Documents collection is empty")
            return {"documents": [], "context": "", "total_retrieved": 0}

        results = coll.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            all_docs.append({
                "document": doc,
                "metadata": meta,
                "distance": round(dist, 4),
            })

    except Exception as e:
        logger.warning(f"Failed to query collection '{COLLECTION_NAME}': {e}")

    # Build a merged context string for the LLM (deduplicated)
    context_parts = []
    seen = set()
    for doc in all_docs:
        text = doc["document"].strip()
        if text not in seen:
            seen.add(text)
            context_parts.append(text)

    context = "\n\n".join(context_parts)

    doc_count = len(all_docs)
    logger.info(f"Retrieved {doc_count} documents for query: {query}")

    return {
        "documents": all_docs,
        "context": context,
        "total_retrieved": doc_count,
    }


def search_chunks(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Search for document chunks matching a query."""
    try:
        coll = vector_store.get_collection(COLLECTION_NAME)
        count = coll.count()
        if count == 0:
            return {"success": True, "chunks": [], "count": 0}

        results = coll.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        chunks = []
        for doc, meta, dist in zip(docs, metas, dists):
            chunks.append({
                "document": doc,
                "metadata": meta,
                "distance": round(dist, 4),
            })

        return {"success": True, "chunks": chunks, "count": len(chunks)}
    except Exception as e:
        logger.error(f"Chunk search failed: {e}")
        return {"success": False, "error": str(e), "chunks": [], "count": 0}


def get_collection_stats() -> Dict[str, int]:
    """Return document counts."""
    return vector_store.get_stats()

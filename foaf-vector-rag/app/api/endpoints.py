"""FastAPI route handlers for the FoaF Vector RAG API."""

import time
import numpy as np
from fastapi import APIRouter, HTTPException
from sklearn.decomposition import PCA

from app.models.requests import QueryRequest
from app.models.responses import QueryResponse, HealthResponse
from app.agent.vector_agent import run_agent
from app.vector.chroma_client import vector_store
from app.vector.retriever import search_chunks, get_collection_stats
from app.llm.llm_client import is_llm_configured
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint showing system status."""
    vs_ok = vector_store.test_connection()
    llm_ok = is_llm_configured()
    stats = vector_store.get_stats() if vs_ok else None

    status = "healthy" if vs_ok and llm_ok else "degraded"
    return HealthResponse(
        status=status,
        vector_store_connected=vs_ok,
        llm_configured=llm_ok,
        collection_stats=stats,
    )


@router.post("/query", response_model=QueryResponse)
async def query_vector(request: QueryRequest):
    """Natural language query endpoint — the main agent interface."""
    try:
        result = await run_agent(request.query)

        response = QueryResponse(
            success=result["success"],
            query=result["query"],
            intent=result.get("intent"),
            results=result.get("results") if request.include_metadata else None,
            response=result["response"],
            retrieval_count=result.get("retrieval_count"),
            execution_time_ms=result.get("execution_time_ms"),
        )
        return response
    except Exception as e:
        logger.error(f"Query endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks")
async def list_chunks(limit: int = 50):
    """List document chunks in the vector store."""
    try:
        coll = vector_store.get_collection("documents")
        results = coll.get(
            limit=limit,
            include=["documents", "metadatas"],
        )

        chunks = []
        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        for cid, doc, meta in zip(ids, docs, metas):
            chunks.append({
                "id": cid,
                "preview": doc[:200] + "..." if len(doc) > 200 else doc,
                "source_file": meta.get("source_file", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "char_count": meta.get("char_count", len(doc)),
            })

        return {"success": True, "count": len(chunks), "total": coll.count(), "chunks": chunks}
    except Exception as e:
        logger.error(f"List chunks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search(query: str, top_k: int = 5):
    """Semantic search across document chunks."""
    try:
        result = search_chunks(query, top_k=top_k)
        return result
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get vector store statistics."""
    try:
        stats = get_collection_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/all")
async def list_all_chunks():
    """Return ALL chunks with full text and metadata (for explorer UI)."""
    try:
        coll = vector_store.get_collection("documents")
        total = coll.count()
        results = coll.get(limit=total, include=["documents", "metadatas"])

        chunks = []
        for cid, doc, meta in zip(
            results.get("ids", []),
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            chunks.append({
                "id": cid,
                "document": doc,
                "source_file": meta.get("source_file", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "total_chunks": meta.get("total_chunks", 0),
                "start_char": meta.get("start_char", 0),
                "end_char": meta.get("end_char", 0),
                "char_count": meta.get("char_count", len(doc)),
            })
        return {"success": True, "count": len(chunks), "chunks": chunks}
    except Exception as e:
        logger.error(f"List all chunks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/2d")
async def get_embeddings_2d():
    """Return 2D PCA projection of all chunk embeddings for visualization."""
    try:
        coll = vector_store.get_collection("documents")
        total = coll.count()
        if total == 0:
            return {"success": True, "count": 0, "points": []}

        results = coll.get(
            limit=total,
            include=["embeddings", "documents", "metadatas"],
        )

        ids = results.get("ids", [])
        embeddings = results.get("embeddings", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        if embeddings is None or len(embeddings) == 0:
            return {"success": False, "error": "No embeddings found"}

        emb_array = np.array(embeddings)
        n_components = min(2, emb_array.shape[0], emb_array.shape[1])
        pca = PCA(n_components=n_components)
        coords_2d = pca.fit_transform(emb_array)

        points = []
        for i, (cid, doc, meta) in enumerate(zip(ids, docs, metas)):
            points.append({
                "id": cid,
                "x": round(float(coords_2d[i][0]), 4),
                "y": round(float(coords_2d[i][1]), 4) if n_components == 2 else 0.0,
                "preview": doc[:120].replace("\n", " "),
                "source_file": meta.get("source_file", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "char_count": meta.get("char_count", len(doc)),
            })

        variance = [round(float(v), 4) for v in pca.explained_variance_ratio_]
        return {
            "success": True,
            "count": len(points),
            "points": points,
            "explained_variance": variance,
            "embedding_dim": int(emb_array.shape[1]),
        }
    except Exception as e:
        logger.error(f"Embeddings 2D error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/detailed")
async def search_detailed(query: str, top_k: int = 10):
    """Semantic search returning full documents and distances."""
    try:
        coll = vector_store.get_collection("documents")
        count = coll.count()
        if count == 0:
            return {"success": True, "results": [], "count": 0}

        results = coll.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        items = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            items.append({
                "document": doc,
                "source_file": meta.get("source_file", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "char_count": meta.get("char_count", len(doc)),
                "distance": round(float(dist), 4),
                "similarity": round(1.0 - float(dist), 4),
            })

        return {"success": True, "query": query, "count": len(items), "results": items}
    except Exception as e:
        logger.error(f"Detailed search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

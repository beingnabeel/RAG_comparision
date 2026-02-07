"""ChromaDB client for the FoaF Vector RAG application.

Provides persistent vector storage using ChromaDB with sentence-transformers
embeddings. Three collections are maintained:
  - persons: Person profile documents (one per person)
  - relationships: Relationship documents (one per relationship triple)
  - families: Aggregated family-level documents
"""

import os
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """ChromaDB-backed vector store with sentence-transformer embeddings."""

    def __init__(self):
        persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        os.makedirs(persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embed_fn = SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
        )
        logger.info(f"ChromaDB initialized at {persist_dir} with model {settings.EMBEDDING_MODEL}")

    @property
    def client(self) -> chromadb.ClientAPI:
        return self._client

    @property
    def embed_fn(self) -> SentenceTransformerEmbeddingFunction:
        return self._embed_fn

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def get_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_collection(
            name=name,
            embedding_function=self._embed_fn,
        )

    def collection_exists(self, name: str) -> bool:
        try:
            self._client.get_collection(name=name)
            return True
        except Exception:
            return False

    def delete_collection(self, name: str):
        try:
            self._client.delete_collection(name=name)
        except Exception:
            pass

    def test_connection(self) -> bool:
        """Check if ChromaDB is accessible."""
        try:
            self._client.heartbeat()
            return True
        except Exception as e:
            logger.error(f"ChromaDB connection test failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Return statistics about the vector store collections."""
        stats = {}
        try:
            coll = self.get_collection("documents")
            stats["documents"] = coll.count()
        except Exception:
            stats["documents"] = 0
        stats["total_chunks"] = stats["documents"]
        return stats


# Singleton
vector_store = VectorStore()

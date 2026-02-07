#!/usr/bin/env python3
"""Ingest PDF / DOCX documents into ChromaDB for vector RAG.

Loads documents from the documents/ directory, splits them into chunks,
embeds with sentence-transformers, and stores in a single ChromaDB collection.

Supported formats: .pdf, .docx

Usage:
    python -m data.ingest                                    # default: documents/ folder
    python -m data.ingest --dir /path/to/docs                # custom folder
    python -m data.ingest --file /path/to/doc.pdf            # single file
    python -m data.ingest --reset                            # delete existing collection first
    python -m data.ingest --chunk-size 800 --chunk-overlap 150
"""

import argparse
import os
import re
import sys
import time
from typing import List, Dict, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.vector.chroma_client import vector_store


# ── Document Loaders ─────────────────────────────────────────────────────────

def load_pdf(path: str) -> str:
    """Extract text from a PDF file."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def load_docx(path: str) -> str:
    """Extract text from a DOCX file."""
    from docx import Document
    doc = Document(path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


LOADERS = {
    ".pdf": load_pdf,
    ".docx": load_docx,
}


def load_document(path: str) -> Tuple[str, str]:
    """Load a document and return (text, filename).

    Raises ValueError for unsupported formats.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in LOADERS:
        raise ValueError(f"Unsupported file format: {ext}. Supported: {', '.join(LOADERS)}")
    text = LOADERS[ext](path)
    return text, os.path.basename(path)


# ── Text Chunking ────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[Dict[str, str]]:
    """Split text into overlapping chunks at paragraph/sentence boundaries.

    Returns a list of dicts: {text, start_char, end_char}
    """
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Split into paragraphs first
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    chunks = []
    current_chunk = ""
    current_start = 0
    char_pos = 0

    for para in paragraphs:
        # If adding this paragraph exceeds chunk_size, finalize current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > chunk_size:
            chunks.append({
                "text": current_chunk.strip(),
                "start_char": current_start,
                "end_char": current_start + len(current_chunk.strip()),
            })

            # Start new chunk with overlap from end of previous
            overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else current_chunk
            # Find a clean break point (sentence or word boundary) in the overlap
            last_period = overlap_text.rfind('. ')
            if last_period > 0:
                overlap_text = overlap_text[last_period + 2:]
            current_start = current_start + len(current_chunk) - len(overlap_text)
            current_chunk = overlap_text

        if current_chunk:
            current_chunk += "\n\n" + para
        else:
            current_start = char_pos
            current_chunk = para

        char_pos += len(para) + 2  # +2 for \n\n

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "start_char": current_start,
            "end_char": current_start + len(current_chunk.strip()),
        })

    return chunks


# ── Ingest into ChromaDB ────────────────────────────────────────────────────

COLLECTION_NAME = "documents"


def ingest(doc_paths: List[str], reset: bool = False,
           chunk_size: int = 800, chunk_overlap: int = 150):
    """Main ingestion pipeline: PDF/DOCX → chunks → embeddings → ChromaDB."""

    print("\n" + "=" * 60)
    print("  FoaF Vector RAG — Document Ingestion")
    print("=" * 60)

    # 1. Load documents
    print(f"\n[1/4] Loading {len(doc_paths)} document(s)...")
    all_chunks = []
    for path in doc_paths:
        try:
            text, filename = load_document(path)
            print(f"  ✓ {filename}: {len(text):,} characters")

            chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for i, chunk in enumerate(chunks):
                chunk["source_file"] = filename
                chunk["source_path"] = path
                chunk["chunk_index"] = i
                chunk["total_chunks"] = len(chunks)
            all_chunks.extend(chunks)
            print(f"    → {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")

        except Exception as e:
            print(f"  ✗ {path}: {e}")

    if not all_chunks:
        print("\n  No chunks generated. Nothing to ingest.")
        return

    print(f"\n  Total: {len(all_chunks)} chunks from {len(doc_paths)} file(s)")

    # 2. Reset collection if requested
    if reset:
        print(f"\n[2/4] Resetting collection '{COLLECTION_NAME}'...")
        vector_store.delete_collection(COLLECTION_NAME)
        print(f"  Deleted collection: {COLLECTION_NAME}")
    else:
        print(f"\n[2/4] Appending to collection '{COLLECTION_NAME}' (use --reset to clear)")

    # 3. Prepare documents for ChromaDB
    print("\n[3/4] Preparing documents...")
    ids = []
    documents = []
    metadatas = []

    for chunk in all_chunks:
        chunk_id = f"{chunk['source_file']}::chunk_{chunk['chunk_index']:04d}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "source_file": chunk["source_file"],
            "chunk_index": chunk["chunk_index"],
            "total_chunks": chunk["total_chunks"],
            "start_char": chunk["start_char"],
            "end_char": chunk["end_char"],
            "char_count": len(chunk["text"]),
        })

    print(f"  Prepared {len(ids)} chunks with metadata")

    # 4. Embed and insert into ChromaDB
    print(f"\n[4/4] Embedding and inserting into ChromaDB...")
    t0 = time.time()

    collection = vector_store.get_or_create_collection(COLLECTION_NAME)
    _batch_upsert(collection, ids, documents, metadatas)

    elapsed = time.time() - t0
    print(f"  ✓ {COLLECTION_NAME}: {collection.count()} documents")
    print(f"\n  Done! {collection.count()} chunks ingested in {elapsed:.1f}s")
    print("=" * 60 + "\n")


def _batch_upsert(collection, ids, documents, metadatas, batch_size=100):
    """Upsert documents in batches to avoid ChromaDB limits."""
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.upsert(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def _find_documents(directory: str) -> List[str]:
    """Find all PDF/DOCX files in a directory."""
    paths = []
    for fname in sorted(os.listdir(directory)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in LOADERS:
            paths.append(os.path.join(directory, fname))
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PDF/DOCX documents into ChromaDB")
    parser.add_argument(
        "--dir",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "documents"),
        help="Directory containing PDF/DOCX files (default: documents/)",
    )
    parser.add_argument("--file", help="Ingest a single PDF or DOCX file")
    parser.add_argument("--reset", action="store_true", help="Delete existing collection before ingesting")
    parser.add_argument("--chunk-size", type=int, default=800, help="Target chunk size in characters (default: 800)")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Overlap between chunks (default: 150)")
    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        doc_paths = [os.path.abspath(args.file)]
    else:
        doc_dir = os.path.abspath(args.dir)
        if not os.path.isdir(doc_dir):
            print(f"Error: Directory not found: {doc_dir}")
            sys.exit(1)
        doc_paths = _find_documents(doc_dir)
        if not doc_paths:
            print(f"Error: No PDF/DOCX files found in {doc_dir}")
            sys.exit(1)

    ingest(doc_paths, reset=args.reset,
           chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)

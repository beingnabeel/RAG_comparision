#!/usr/bin/env python3
"""Interactive CLI chatbot for the FoaF Vector RAG system.

Mirror of the Graph RAG CLI, but backed by ChromaDB vector retrieval
instead of SPARQL queries against Fuseki.
"""

import asyncio
import sys
import time

from app.config import settings
from app.utils.logging import setup_logging, get_logger
from app.llm.llm_client import is_llm_configured
from app.vector.chroma_client import vector_store
from app.vector.retriever import search_chunks, get_collection_stats
from app.agent.vector_agent import run_agent

logger = get_logger(__name__)

# ── ANSI Colours ─────────────────────────────────────────────────────────────
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def c(text, style=""):
    return f"{style}{text}{RESET}"


def print_divider():
    print(c("─" * 60, DIM))


# ── Banner ───────────────────────────────────────────────────────────────────

def print_banner():
    print()
    print(c("=" * 60, CYAN))
    print(c("  FoaF Vector RAG — Interactive CLI Chatbot", BOLD + CYAN))
    print(c("=" * 60, CYAN))
    print()
    print(c(f"  Vector DB : ChromaDB ({settings.CHROMA_PERSIST_DIR})", DIM))
    print(c(f"  Embeddings: {settings.EMBEDDING_MODEL}", DIM))
    print(c(f"  LLM       : {settings.LLM_MODEL}", DIM))
    print()


# ── Help ─────────────────────────────────────────────────────────────────────

def print_help():
    help_text = f"""
{c('Available Commands:', BOLD)}

  {c('Just type a question', YELLOW)}  — Ask anything in natural language
      Examples:  {c('Who is Rajesh Sharma?', DIM)}
                 {c('Who are the friends of David Chen?', DIM)}
                 {c('How many people work in Technology?', DIM)}

  {c('/search', YELLOW)}  <query>      — Search document chunks by similarity
  {c('/chunks', YELLOW)}  [limit]      — List stored document chunks (default: 10)
  {c('/stats', YELLOW)}                — Show vector store statistics
  {c('/help', YELLOW)}                 — Show this help
  {c('/quit', YELLOW)}                 — Exit
"""
    print(help_text)


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_chunks(args):
    """List document chunks stored in the vector database."""
    limit = 10
    if args.strip().isdigit():
        limit = int(args.strip())

    try:
        coll = vector_store.get_collection("documents")
        results = coll.get(
            limit=limit,
            include=["documents", "metadatas"],
        )

        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])

        if not ids:
            print(c("  No document chunks found in the vector store.", YELLOW))
            return

        print()
        for cid, doc, meta in zip(ids, docs, metas):
            source = meta.get("source_file", "?")
            idx = meta.get("chunk_index", "?")
            chars = meta.get("char_count", len(doc))
            preview = doc[:120].replace("\n", " ") + ("..." if len(doc) > 120 else "")
            print(f"  {c(f'[{source} #{idx}]', CYAN)} ({chars} chars)")
            print(f"    {preview}")
            print()
        print(c(f"  Showing {min(limit, len(ids))} of {coll.count()} chunks", DIM))

    except Exception as e:
        print(c(f"  Error: {e}", RED))


def cmd_search(args):
    """Search document chunks by semantic similarity."""
    query = args.strip()
    if not query:
        print(c("  Usage: /search <query>", YELLOW))
        return

    result = search_chunks(query, top_k=5)
    if not result.get("success"):
        print(c(f"  Error: {result.get('error', 'Unknown error')}", RED))
        return

    chunks = result.get("chunks", [])
    if not chunks:
        print(c(f"  No results for '{query}'.", YELLOW))
        return

    print()
    print(c(f"  Found {len(chunks)} matching chunk(s) for '{query}':", BOLD))
    print()
    for ch in chunks:
        meta = ch.get("metadata", {})
        dist = ch.get("distance", 0)
        doc = ch.get("document", "")[:150].replace("\n", " ")
        source = meta.get("source_file", "?")
        idx = meta.get("chunk_index", "?")
        print(f"  {c(f'[{source} #{idx}]', CYAN)} similarity: {c(f'{1-dist:.2f}', GREEN)}")
        print(f"    {doc}...")
        print()
    print()


def cmd_stats(_):
    """Show vector store statistics."""
    stats = get_collection_stats()
    print()
    print(c("  Vector Store Statistics:", BOLD))
    print(c("  " + "-" * 30, DIM))
    for key, val in stats.items():
        label = key.replace("_", " ").title()
        print(f"  {label:<22} {c(str(val), GREEN)}")
    print()


# ── Natural Language Query ───────────────────────────────────────────────────

async def cmd_natural_language(user_input):
    """Send a natural language query through the agent."""
    print()
    print(c("  Thinking...", DIM), end="", flush=True)
    start = time.time()

    result = await run_agent(user_input)
    elapsed = time.time() - start

    # Clear the "Thinking..." line
    print(f"\r{'':60}\r", end="")

    if result.get("success"):
        response = result.get("response", "No response generated.")
        print()
        for line in response.split("\n"):
            print(f"  {c('│', CYAN)} {line}")
        print()

        intent = result.get("intent", "")
        retrieval_count = result.get("retrieval_count", 0)
        print(c(f"  Intent: {intent}  |  Time: {elapsed:.1f}s  |  Docs retrieved: {retrieval_count}", DIM))
    else:
        print(c(f"  Error: {result.get('response', 'Unknown error')}", RED))


# ── Command Dispatch ─────────────────────────────────────────────────────────

COMMANDS = {
    "/chunks": cmd_chunks,
    "/search": cmd_search,
    "/stats": cmd_stats,
    "/help": lambda _: print_help(),
}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    setup_logging()
    print_banner()

    # Pre-flight checks
    print(c("  Checking connections...", DIM))

    if not vector_store.test_connection():
        print(c("  ✗ Cannot connect to ChromaDB", RED))
        sys.exit(1)
    print(c("  ✓ ChromaDB connected", GREEN))

    if not is_llm_configured():
        print(c("  ✗ LLM API key not configured in .env", RED))
        sys.exit(1)
    print(c(f"  ✓ LLM configured ({settings.LLM_MODEL})", GREEN))

    stats = vector_store.get_stats()
    total = stats.get("total_chunks", 0)
    if total == 0:
        print(c("  ⚠ Vector store is empty. Run: python -m data.ingest --reset", YELLOW))
    else:
        print(c(f"  ✓ Vector store: {total} document chunks", GREEN))
    print()

    print_help()
    print_divider()

    # REPL loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            user_input = input(f"\n{c('You', BOLD + GREEN)} > ").strip()
        except (KeyboardInterrupt, EOFError):
            print(c("\n\n  Goodbye!\n", CYAN))
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "/q", "quit", "exit"):
            print(c("\n  Goodbye!\n", CYAN))
            break

        # Check if it's a command
        parts = user_input.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in COMMANDS:
            try:
                COMMANDS[cmd](args)
            except Exception as e:
                print(c(f"  Error: {e}", RED))
        else:
            # Natural language query through the agent
            try:
                loop.run_until_complete(cmd_natural_language(user_input))
            except Exception as e:
                print(c(f"  Error: {e}", RED))

        print_divider()

    loop.close()


if __name__ == "__main__":
    main()

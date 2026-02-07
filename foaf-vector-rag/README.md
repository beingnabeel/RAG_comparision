# FoaF Vector RAG

A **Vector RAG** (Retrieval-Augmented Generation) application for exploring a Friends-of-a-Friend (FoaF) person network. Uses **ChromaDB** as the vector database with **sentence-transformers** embeddings and **Google Gemini** for natural language understanding.

This is the vector-based counterpart to the [FoaF Graph RAG](../foaf-graph-rag/) project, enabling a direct comparison between **Graph RAG** (SPARQL over knowledge graphs) and **Vector RAG** (semantic search over embeddings).

## Architecture

```
User Query → Intent Classification (rule-based)
           → Embed Query (sentence-transformers)
           → Similarity Search (ChromaDB)
           → LLM Response Generation (Gemini)
           → Natural Language Answer
```

### Key Differences from Graph RAG

| Aspect           | Graph RAG                        | Vector RAG                   |
| ---------------- | -------------------------------- | ---------------------------- |
| **Database**     | Apache Jena Fuseki (RDF triples) | ChromaDB (vector embeddings) |
| **Query Method** | LLM generates SPARQL             | Semantic similarity search   |
| **Retrieval**    | Exact structured queries         | Fuzzy semantic matching      |
| **Strengths**    | Precise relationships, reasoning | Natural language flexibility |
| **Data Format**  | RDF/OWL triples                  | Text documents + embeddings  |

## Tech Stack (All Free / Open-Source)

- **ChromaDB** — Local vector database (no server needed)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — Local embedding model
- **Google Gemini** — LLM for response generation (free tier)
- **LangChain + LangGraph** — Agent orchestration framework
- **FastAPI** — REST API + WebSocket log streaming
- **pypdf + python-docx** — Document loaders for PDF and DOCX files

## Quick Start

### 1. Install Dependencies

```bash
cd foaf-vector-rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 3. Ingest Documents

Place your PDF or DOCX files in the `documents/` directory, then run:

```bash
python -m data.ingest --reset
```

This loads all PDF/DOCX files from `documents/`, splits them into overlapping text chunks, embeds each chunk with sentence-transformers, and stores them in ChromaDB.

Options:

```bash
python -m data.ingest --file /path/to/doc.pdf    # single file
python -m data.ingest --chunk-size 800             # adjust chunk size
python -m data.ingest --chunk-overlap 150          # adjust overlap
```

### 4. Run the CLI Chatbot

```bash
python cli.py
```

### 5. Run the Web Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Available web interfaces:

| Interface    | URL                              | Description                                      |
| ------------ | -------------------------------- | ------------------------------------------------ |
| **Chat UI**  | `http://localhost:8001/chat`     | Interactive chatbot with real-time logs panel    |
| **Explorer** | `http://localhost:8001/explorer` | Browse chunks, semantic search, 2D embedding map |
| **API Docs** | `http://localhost:8001/docs`     | Swagger/OpenAPI interactive docs                 |

## Project Structure

```
foaf-vector-rag/
├── app/
│   ├── agent/           # LangGraph agent pipeline
│   │   ├── vector_agent.py   # Intent → Retrieve → Generate
│   │   ├── prompts.py        # LLM prompts
│   │   ├── state.py          # Agent state definition
│   │   └── tools.py          # Vector search tools
│   ├── api/             # FastAPI endpoints
│   │   ├── endpoints.py      # REST API
│   │   └── chat_api.py       # Chat + WebSocket logs
│   ├── llm/             # Google Gemini client
│   ├── vector/          # ChromaDB integration
│   │   ├── chroma_client.py  # Vector store singleton
│   │   └── retriever.py      # Semantic retrieval logic
│   ├── models/          # Pydantic request/response models
│   ├── utils/           # Logging, log collector
│   ├── config.py        # Settings from .env
│   └── main.py          # FastAPI app entry point
├── data/
│   ├── ingest.py        # PDF/DOCX → chunks → ChromaDB
│   └── chroma_store/    # Persistent vector storage (gitignored)
├── documents/           # Place PDF/DOCX files here
├── static/
│   ├── chatbot.html     # Chat UI (React + TailwindCSS)
│   └── explorer.html    # Vector store explorer UI
├── tests/
├── cli.py               # Interactive CLI chatbot
├── requirements.txt
└── .env.example
```

## Data Pipeline

The ingestion script (`data/ingest.py`) loads PDF/DOCX documents and stores them in a single ChromaDB collection:

1. **Load** — Extract text from PDF (pypdf) or DOCX (python-docx) files
2. **Chunk** — Split into overlapping chunks (~800 chars) at paragraph/sentence boundaries
3. **Embed** — Generate vector embeddings via sentence-transformers (`all-MiniLM-L6-v2`)
4. **Store** — Upsert chunks with metadata (source file, chunk index, char position) into ChromaDB

## API Endpoints

| Method | Endpoint           | Description                         |
| ------ | ------------------ | ----------------------------------- |
| GET    | `/health`          | System health check                 |
| POST   | `/query`           | Natural language query              |
| POST   | `/api/chat`        | Chat endpoint (for Web UI)          |
| GET    | `/api/logs`        | Get all log entries                 |
| DELETE | `/api/logs`        | Clear all logs                      |
| WS     | `/ws/logs`         | Real-time log streaming             |
| GET    | `/chunks`          | List document chunks (preview)      |
| GET    | `/chunks/all`      | All chunks with full text           |
| GET    | `/search?query=X`  | Semantic chunk search               |
| GET    | `/search/detailed` | Search with full docs + similarity  |
| GET    | `/embeddings/2d`   | PCA 2D projection for visualization |
| GET    | `/stats`           | Vector store statistics             |

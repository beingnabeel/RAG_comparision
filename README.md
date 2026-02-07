# RAG Comparison — Graph RAG vs Vector RAG

A head-to-head comparison of two Retrieval-Augmented Generation (RAG) architectures built on the same underlying dataset: a social network of **100 persons** with rich attributes (name, age, job, address, contact) and diverse relationships (spouse, parent, child, sibling, friend, colleague, neighbor).

## Architecture Overview

| | **Graph RAG** | **Vector RAG** |
|---|---|---|
| **Data Store** | Apache Jena Fuseki (SPARQL triplestore) | ChromaDB (vector database) |
| **Data Format** | RDF triples in Turtle (.ttl) | PDF/DOCX documents chunked into embeddings |
| **Retrieval** | LLM generates SPARQL → executes on graph | Semantic similarity search over embeddings |
| **Embedding Model** | N/A | `sentence-transformers/all-MiniLM-L6-v2` |
| **LLM** | Google Gemini 2.5 Flash | Google Gemini 2.5 Flash |
| **Agent Framework** | LangGraph | LangGraph |
| **API Framework** | FastAPI (port 8000) | FastAPI (port 8001) |
| **Web UI** | Chatbot + Graph Visualizer | Chatbot + Vector Store Explorer |

### How Each System Works

**Graph RAG** (`foaf-graph-rag/`): User query → Intent classification → LLM generates SPARQL query → Executes against Fuseki triplestore → LLM formats response from structured results.

**Vector RAG** (`foaf-vector-rag/`): User query → Semantic search over document chunks in ChromaDB → Top-K relevant chunks retrieved → LLM generates response from retrieved context.

---

## Benchmark Results

We ran **10 medium-to-hard queries** across 5 categories against both systems, scoring each response using an **LLM-as-judge** (Llama 3.3 70B via Groq) on three dimensions (1-10 scale):

- **Correctness** — Are the stated facts accurate?
- **Completeness** — Are all expected key facts present?
- **Relevance** — Does the answer address the question directly?

### Overall Scores

| Metric | Graph RAG | Vector RAG | Winner |
|--------|:---------:|:----------:|:------:|
| **★ Overall Score** | **7.1/10** | **8.3/10** | **Vector** |
| Success Rate | 100% | 100% | Tie |
| Avg Latency | 7,085 ms | 5,706 ms | Vector |
| Avg Correctness | 7.1/10 | 8.3/10 | Vector |
| Avg Completeness | 5.2/10 | 7.3/10 | Vector |
| Avg Relevance | 8.7/10 | 9.2/10 | Vector |

### Per-Query Results

| ID | Category | Difficulty | Query | Graph | Vector | Winner |
|----|----------|------------|-------|:-----:|:------:|:------:|
| Q06 | Relationship | Medium | Who are David Chen's friends? | 9.3 | 10.0 | Vector |
| Q08 | Relationship | Medium | Who are the neighbors of James Williams in Chicago? | 10.0 | 10.0 | Tie |
| Q09 | Aggregation | Medium | How many people work in the Healthcare industry? | 3.7 | 3.3 | Tie |
| Q12 | Multi-hop | Hard | Who are the friends of Rajesh Sharma's children? | 6.0 | 8.0 | Vector |
| Q13 | Multi-hop | Hard | What is the occupation of David Chen's wife? | 7.7 | 10.0 | Vector |
| Q15 | Multi-hop | Hard | Do any of Michael Johnson's friends work in finance? | 7.7 | 5.0 | Graph |
| Q16 | Comparison | Medium | Who is older, Rajesh Sharma or David Chen? | 5.3 | 10.0 | Vector |
| Q19 | Inference | Hard | What is the family structure of the Williams family? | 8.3 | 10.0 | Vector |
| Q22 | Aggregation | Hard | How many families are there and what cities? | 3.3 | 7.7 | Vector |
| Q23 | Relationship | Medium | Who lives near Fatima Al-Hassan? | 10.0 | 8.7 | Graph |

**Final Tally: Graph wins 2 | Vector wins 6 | Ties 2**

### Breakdown by Category

| Category | Graph RAG | Vector RAG | Winner |
|----------|:---------:|:----------:|:------:|
| Relationship | 9.8 | 9.6 | Tie |
| Multi-hop | 7.1 | 7.7 | Vector |
| Aggregation | 3.5 | 5.5 | Vector |
| Comparison | 5.3 | 10.0 | Vector |
| Inference | 8.3 | 10.0 | Vector |

### Breakdown by Difficulty

| Difficulty | Graph RAG | Vector RAG | Winner |
|------------|:---------:|:----------:|:------:|
| Medium | 7.7 | 8.4 | Vector |
| Hard | 6.6 | 8.1 | Vector |

---

## Key Findings

### Where Vector RAG Excels
- **Comparison & inference queries** — Document chunks contain full person profiles, giving the LLM rich context to compare attributes and reason about family structures
- **Completeness** — Retrieves broader context per query (top-10 chunks), surfacing more relevant facts
- **Latency** — ~24% faster on average (5.7s vs 7.1s) since it avoids the SPARQL generation step
- **Hard queries** — Better at synthesizing answers from multiple pieces of information spread across chunks

### Where Graph RAG Excels
- **Precise relationship traversal** (Q08, Q15, Q23) — SPARQL queries can exactly navigate explicit relationships (e.g., `rel:neighborOf`, `rel:friendOf`) without ambiguity
- **Structured queries** — When the LLM generates the correct SPARQL, results are precise and deterministic
- **Relationship queries** — Nearly perfect scores (9.8/10) for direct relationship lookups

### Where Both Struggle
- **Aggregation queries** (Q09, Q22) — Neither system reliably counts all entities matching a criterion; Graph RAG overcounts (72 families) while Vector RAG sometimes misses entities outside its top-K retrieval window

### Tradeoffs

| Aspect | Graph RAG | Vector RAG |
|--------|-----------|------------|
| **Setup complexity** | Higher (Fuseki + ontology + data loading) | Lower (ingest PDFs → ChromaDB) |
| **Data flexibility** | Requires structured RDF/TTL | Accepts any PDF/DOCX |
| **Query precision** | High when SPARQL is correct | Depends on embedding similarity |
| **Failure mode** | Wrong/invalid SPARQL → no results | Irrelevant chunks → hallucination |
| **Scalability** | Scales with graph complexity | Scales with chunk count |

---

## Project Structure

```
neo4j_poc/
├── foaf-graph-rag/          # Graph-based RAG using SPARQL + Fuseki
│   ├── app/                 # FastAPI app, LangGraph agent, SPARQL tools
│   ├── data/                # Ontology + sample data (TTL)
│   ├── static/              # Chatbot UI + Graph Visualizer
│   └── README.md
│
├── foaf-vector-rag/         # Vector-based RAG using ChromaDB
│   ├── app/                 # FastAPI app, LangGraph agent, vector retriever
│   ├── data/                # PDF/DOCX ingestion script
│   ├── documents/           # Source documents for ingestion
│   ├── static/              # Chatbot UI + Vector Store Explorer
│   └── README.md
│
├── benchmark/               # Comparative evaluation framework
│   ├── run_benchmark.py     # Benchmark runner with LLM-as-judge
│   ├── test_queries.json    # 25 ground-truth test queries
│   ├── requirements.txt
│   └── README.md
│
└── README.md                # This file — overview + results
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) (for Graph RAG)
- Google Gemini API key(s)

### 1. Graph RAG

```bash
cd foaf-graph-rag

# Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY

# Start Fuseki (in a separate terminal)
./path/to/fuseki-server --mem /foaf

# Load data into Fuseki
python data/load_data.py

# Start the server
uvicorn app.main:app --port 8000
```

### 2. Vector RAG

```bash
cd foaf-vector-rag

# Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY

# Ingest documents into ChromaDB
python data/ingest.py

# Start the server
uvicorn app.main:app --port 8001
```

### 3. Run Benchmark

```bash
cd benchmark
pip install -r requirements.txt

# Create .env.benchmark with your Groq API key for the LLM judge
echo 'JUDGE_API_KEY=your-groq-api-key' > .env.benchmark

# Run benchmark (both servers must be running)
python run_benchmark.py --target both --difficulty medium hard

# Or test specific queries
python run_benchmark.py --ids Q06 Q12 Q19

# Skip LLM judge (faster, just collect latency/retrieval metrics)
python run_benchmark.py --no-judge
```

---

## Web Interfaces

| Interface | URL | Description |
|-----------|-----|-------------|
| Graph RAG Chat | `http://localhost:8000/chat` | Chatbot with real-time SPARQL logs |
| Graph Visualizer | `http://localhost:8000/visualizer` | Interactive knowledge graph explorer |
| Vector RAG Chat | `http://localhost:8001/chat` | Chatbot with retrieval logs |
| Vector Explorer | `http://localhost:8001/explorer` | Chunk browser, semantic search, 2D embedding map |

---

## Tech Stack

- **LLM**: Google Gemini 2.5 Flash
- **Agent Framework**: LangGraph
- **API**: FastAPI
- **Graph Store**: Apache Jena Fuseki (SPARQL 1.1)
- **Vector Store**: ChromaDB
- **Embeddings**: HuggingFace `all-MiniLM-L6-v2`
- **Benchmark Judge**: Llama 3.3 70B (via Groq)
- **Frontend**: React + TailwindCSS (CDN)

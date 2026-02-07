# RAG Benchmark — Graph RAG vs Vector RAG

Automated evaluation framework that runs the same ground-truth queries against both RAG systems and compares accuracy, latency, and retrieval quality.

## What It Measures

| Metric | Description |
|--------|-------------|
| **Correctness** (1-10) | Are the stated facts accurate? |
| **Completeness** (1-10) | Are all expected key facts present? |
| **Relevance** (1-10) | Does the answer address the question directly? |
| **Latency** | End-to-end response time (ms) |
| **Retrieval Count** | Number of results/chunks retrieved |

Scoring uses **LLM-as-judge** (Gemini) to compare each system's response against ground-truth expected answers and key facts.

## Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| `factual_lookup` | 3 | Direct attribute retrieval (name, age, job) |
| `relationship` | 5 | Specific relationship queries (spouse, friend, neighbor) |
| `aggregation` | 4 | Counting, listing, grouping |
| `multi_hop` | 7 | Traversal across 2+ relationships |
| `comparison` | 2 | Comparing attributes of multiple persons |
| `inference` | 4 | Reasoning beyond explicit data |

## Quick Start

```bash
# 1. Install dependencies (use either RAG project's venv)
pip install httpx google-generativeai python-dotenv

# 2. Start BOTH servers in separate terminals
# Terminal 1: Graph RAG (port 8000)
cd foaf-graph-rag && uvicorn app.main:app --port 8000

# Terminal 2: Vector RAG (port 8001)
cd foaf-vector-rag && uvicorn app.main:app --port 8001

# 3. Run the benchmark
cd benchmark
python run_benchmark.py                        # both systems
python run_benchmark.py --target graph         # graph only
python run_benchmark.py --target vector        # vector only
python run_benchmark.py --category multi_hop   # filter by category
python run_benchmark.py --ids Q01 Q05 Q12      # specific queries
python run_benchmark.py --no-judge             # skip LLM scoring (faster)
```

## Output

Results are saved to `results/`:
- `benchmark_graph_vector_YYYYMMDD_HHMMSS.json` — Full results with all responses and scores
- `report_graph_vector_YYYYMMDD_HHMMSS.txt` — Human-readable comparison report

## Files

```
benchmark/
├── run_benchmark.py     # Main benchmark runner
├── test_queries.json    # 25 ground-truth test queries
├── requirements.txt     # Python dependencies
├── README.md
└── results/             # Generated reports (gitignored)
```

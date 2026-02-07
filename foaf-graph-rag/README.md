# FoaF Graph RAG - Friends-of-a-Friend Knowledge Graph Application

A proof-of-concept Graph RAG (Retrieval-Augmented Generation) application that manages relationship and biographical data for 100 individuals using a knowledge graph. The system uses Apache Jena Fuseki as the graph database and OpenAI GPT-4 for natural language understanding, ensuring zero hallucination by grounding all responses in graph data.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Graph Database | Apache Jena Fuseki (RDF/SPARQL) |
| Backend Framework | FastAPI |
| LLM | OpenAI GPT-4 |
| Agent Framework | LangGraph |
| Graph Library | RDFLib |
| Language | Python 3.12+ |

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) (download and extract)
- OpenAI API key

### 2. Setup Environment

```bash
# Clone / navigate to the project
cd foaf-graph-rag

# Create and activate virtual environment (or use existing conda env)
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### 3. Start Fuseki

```bash
# Download Fuseki if you haven't already
# https://jena.apache.org/download/

# Start Fuseki server
cd /path/to/apache-jena-fuseki
./fuseki-server --mem /foaf

# Or with persistent storage:
./fuseki-server --tdb2 --loc=./databases/foaf /foaf
```

### 4. Generate & Load Sample Data

```bash
# Generate 100 persons with relationships
python data/generate_sample_data.py

# Load data into Fuseki
curl -X POST \
  -H "Content-Type: text/turtle" \
  --data-binary @data/sample_data.ttl \
  http://localhost:3030/foaf/data
```

### 5. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with system status |
| POST | `/query` | Natural language query (main agent interface) |
| POST | `/add-person` | Add a new person to the graph |
| POST | `/add-relationship` | Add a relationship between two persons |
| GET | `/person/{id}` | Get person details by ID |
| GET | `/persons` | List all persons |

### Example Queries

```bash
# Natural language query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who are John Smith'\''s friends?", "include_metadata": true}'

# Add a person
curl -X POST http://localhost:8000/add-person \
  -H "Content-Type: application/json" \
  -d '{"name": "New Person", "age": 30, "job_title": "Developer"}'

# Add a relationship
curl -X POST http://localhost:8000/add-relationship \
  -H "Content-Type: application/json" \
  -d '{"subject": "person001", "predicate": "friendOf", "object": "person002"}'

# Health check
curl http://localhost:8000/health
```

## Docker Deployment

```bash
cd deployment
docker-compose up -d
```

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
foaf-graph-rag/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration
│   ├── models/              # Pydantic request/response models
│   ├── api/                 # API endpoints
│   ├── agent/               # LangGraph agent, tools, prompts
│   ├── graph/               # SPARQL client, query builder, validator
│   ├── llm/                 # OpenAI integration, query generator
│   └── utils/               # Logging, helpers
├── data/
│   ├── ontology.ttl         # FOAF ontology definition
│   ├── sample_data.ttl      # Generated sample data (100 persons)
│   └── generate_sample_data.py
├── tests/
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── fuseki-config.ttl
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT

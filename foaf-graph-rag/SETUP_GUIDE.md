# Complete Beginner Setup Guide — FoaF Graph RAG

This guide walks you through **every single step** from a blank machine to a fully running FoaF Graph RAG application. No prior knowledge of RDF, SPARQL, or Fuseki is assumed.

---

## Table of Contents

1. [Understanding the Architecture](#1-understanding-the-architecture)
2. [Prerequisites — What You Need Installed](#2-prerequisites--what-you-need-installed)
3. [Step 1 — Install Java (Required by Fuseki)](#3-step-1--install-java-required-by-fuseki)
4. [Step 2 — Download & Set Up Apache Jena Fuseki](#4-step-2--download--set-up-apache-jena-fuseki)
5. [Step 3 — Start Fuseki & Create the Dataset](#5-step-3--start-fuseki--create-the-dataset)
6. [Step 4 — Configure the Python Project](#6-step-4--configure-the-python-project)
7. [Step 5 — Generate Sample Data (100 Persons)](#7-step-5--generate-sample-data-100-persons)
8. [Step 6 — Load Data into Fuseki (Two Named Graphs)](#8-step-6--load-data-into-fuseki-two-named-graphs)
9. [Step 7 — Verify the Graph in Fuseki UI](#9-step-7--verify-the-graph-in-fuseki-ui)
10. [Step 8 — Start the FastAPI Application](#10-step-8--start-the-fastapi-application)
11. [Step 9 — Test the API](#11-step-9--test-the-api)
12. [Step 10 — Run Automated Tests](#12-step-10--run-automated-tests)
13. [Troubleshooting](#13-troubleshooting)
14. [Understanding the Two-Graph Architecture](#14-understanding-the-two-graph-architecture)

---

## 1. Understanding the Architecture

Before we begin, here's what we're building:

```
  You (browser / Postman / curl)
       │
       ▼
  FastAPI Server  (Python, port 8000)
       │
       ├── LangGraph Agent  (understands your natural-language questions)
       │       │
       │       ├── OpenAI GPT-4  (converts your question → SPARQL query)
       │       │
       │       └── SPARQL Client (sends the query to Fuseki)
       │
       ▼
  Apache Jena Fuseki  (Graph Database, port 3030)
       │
       ├── Ontology Graph  (the blueprint — what classes & properties exist)
       │
       └── Data Graph      (the actual 100 persons & their relationships)
```

**Key concept — Two Named Graphs:**
- **Ontology Graph** = The "blueprint". It says: "A Person can have a name, age, friends, etc."
- **Data Graph** = The actual data. It says: "John Smith is 35 years old and is friends with Jane Doe."

This separation means the LLM agent can look at the blueprint to understand what data *can* exist, and then query the data graph for actual facts.

---

## 2. Prerequisites — What You Need Installed

Before starting, make sure you have:

| Requirement | Why | Check Command |
|---|---|---|
| **Python 3.12+** | Already have via your `foafpoc` conda env | `python --version` |
| **Java 11+** (JDK or JRE) | Fuseki is a Java application | `java -version` |
| **curl** | For loading data into Fuseki | `curl --version` |
| **A text editor** | Your IDE (VS Code / Windsurf) | — |
| **OpenAI API key** | For the LLM (GPT-4) | You already added this to `.env` |

---

## 3. Step 1 — Install Java (Required by Fuseki)

Fuseki is written in Java. You need Java 11 or higher.

### Check if Java is already installed:

```bash
java -version
```

If you see output like `openjdk version "11.0.x"` or higher, **skip to Step 2**.

### Install Java on Ubuntu/Debian Linux:

```bash
sudo apt update
sudo apt install openjdk-17-jre-headless -y
```

### Verify:

```bash
java -version
```

You should see something like:
```
openjdk version "17.0.x" ...
```

---

## 4. Step 2 — Download & Set Up Apache Jena Fuseki

### 4.1 Download Fuseki

```bash
# Navigate to your project's parent directory
cd /home/nabeel/Documents/nabeel/neo4j_poc

# Download Fuseki (latest stable version)
wget https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-5.3.0.tar.gz

# Extract it
tar -xzf apache-jena-fuseki-5.3.0.tar.gz

# Rename for convenience (optional)
mv apache-jena-fuseki-5.3.0 fuseki
```

> **Note:** If the above download link is outdated, visit https://jena.apache.org/download/ and look for the latest **Apache Jena Fuseki** binary release. Download the `.tar.gz` file.

### 4.2 Verify Fuseki files

```bash
ls fuseki/
```

You should see files like:
```
fuseki-server        (the startup script)
fuseki-server.jar    (the Java application)
...
```

---

## 5. Step 3 — Start Fuseki & Create the Dataset

### 5.1 Start Fuseki with an in-memory dataset

For a quick POC, start Fuseki with an **in-memory** dataset named `foaf`:

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/fuseki

./fuseki-server --mem /foaf
```

You should see output like:
```
[2025-02-07 ...] Apache Jena Fuseki 5.x.x
[2025-02-07 ...] Started ... on port 3030
```

> **Keep this terminal open!** Fuseki needs to keep running.

### 5.2 Alternative: Persistent storage (data survives restarts)

If you want data to survive server restarts, use TDB2 storage instead:

```bash
# Create a directory for persistent data
mkdir -p /home/nabeel/Documents/nabeel/neo4j_poc/fuseki/databases/foaf

# Start with persistent storage
cd /home/nabeel/Documents/nabeel/neo4j_poc/fuseki
./fuseki-server --tdb2 --loc=./databases/foaf /foaf
```

### 5.3 Verify Fuseki is running

Open a **new terminal** (keep Fuseki running in the old one) and run:

```bash
curl http://localhost:3030/$/ping
```

Expected response:
```
Apache Jena Fuseki 5.x.x
```

### 5.4 Open Fuseki Web UI

Open your browser and go to:

```
http://localhost:3030
```

You'll see the Fuseki admin interface. You should see the `/foaf` dataset listed.

---

## 6. Step 4 — Configure the Python Project

### 6.1 Activate your conda environment

```bash
# You can activate the conda env, or just use the full path to python
# Option A: Use full path (simpler)
/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python --version

# Option B: If conda is configured
conda activate foafpoc
```

### 6.2 Navigate to the project

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag
```

### 6.3 Check the .env file

You already created this file. Verify it looks correct:

```bash
cat .env
```

It should contain:
```
OPENAI_API_KEY=sk-proj-your-actual-key-here
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.0
FUSEKI_ENDPOINT=http://localhost:3030/foaf
API_PORT=8000
LOG_LEVEL=INFO
```

### 6.4 Install dependencies (if not already done)

```bash
/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/pip install -r requirements.txt
```

---

## 7. Step 5 — Generate Sample Data (100 Persons)

This creates a file with 100 fake persons and their relationships.

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag

/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python data/generate_sample_data.py
```

Expected output:
```
Generated 100 persons
Total triples: ~2249
Saved to: .../data/sample_data.ttl

Relationship Stats:
  Friendships: ~357
  Marriages: ~44 (pairs: ~22)
  Parent-Child: ~52
  Colleagues: ~13
  Neighbors: ~9
  Siblings: ~22
```

This creates the file `data/sample_data.ttl`. You can open it in your editor to see the data — it's human-readable Turtle format.

---

## 8. Step 6 — Load Data into Fuseki (Two Named Graphs)

This is the key step that creates the two-graph architecture. We load:
- `ontology.ttl` → the **ontology graph** (blueprint)
- `sample_data.ttl` → the **data graph** (actual persons)

### Option A: Use the automated script (recommended)

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag

/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python data/load_data.py
```

Expected output:
```
============================================================
FoaF Graph RAG — Data Loader
============================================================
Fuseki endpoint: http://localhost:3030/foaf

[1/4] Checking Fuseki connectivity...
  Fuseki is reachable.

[2/4] Loading ontology (blueprint) into ontology graph...
  Loading ontology.ttl → <http://example.org/foaf-poc/ontology>
  PUT http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/ontology  (... bytes)
  SUCCESS (HTTP 200)

[3/4] Loading sample data (100 persons) into data graph...
  Loading sample_data.ttl → <http://example.org/foaf-poc/data>
  PUT http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/data  (... bytes)
  SUCCESS (HTTP 200)

[4/4] Verifying loaded graphs...
  Ontology graph: ~114 triples
  Data graph: ~2249 triples

All done! Your knowledge graph is ready.
```

### Option B: Load manually with curl

If you prefer doing it manually:

```bash
# Load ontology into the ontology named graph
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/ontology.ttl \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/ontology"

# Load sample data into the data named graph
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/sample_data.ttl \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/data"
```

---

## 9. Step 7 — Verify the Graph in Fuseki UI

### 9.1 Open Fuseki UI

Go to: **http://localhost:3030** in your browser.

1. Click on the **"foaf"** dataset
2. Click the **"query"** tab

### 9.2 Test: Count persons in the data graph

Paste this query and click "Run":

```sparql
SELECT (COUNT(?p) AS ?personCount)
WHERE {
    GRAPH <http://example.org/foaf-poc/data> {
        ?p a <http://example.org/foaf-poc/Person>
    }
}
```

Expected result: `personCount = 100`

### 9.3 Test: List the first 5 persons

```sparql
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX custom: <http://example.org/foaf-poc/>

SELECT ?name ?age ?jobTitle
WHERE {
    GRAPH <http://example.org/foaf-poc/data> {
        ?person a custom:Person ;
                foaf:name ?name .
        OPTIONAL { ?person foaf:age ?age }
        OPTIONAL { ?person <http://schema.org/jobTitle> ?jobTitle }
    }
}
LIMIT 5
```

### 9.4 Test: Check the ontology graph (blueprint)

```sparql
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?property ?label
WHERE {
    GRAPH <http://example.org/foaf-poc/ontology> {
        ?property a rdf:Property .
        OPTIONAL { ?property rdfs:label ?label }
    }
}
ORDER BY ?property
```

This should show all the properties defined in the blueprint (name, age, phone, friendOf, spouseOf, etc.)

### 9.5 Test: See which named graphs exist

```sparql
SELECT DISTINCT ?graph (COUNT(*) AS ?triples)
WHERE {
    GRAPH ?graph { ?s ?p ?o }
}
GROUP BY ?graph
```

You should see exactly two graphs:
- `http://example.org/foaf-poc/ontology` — ~114 triples
- `http://example.org/foaf-poc/data` — ~2249 triples

---

## 10. Step 8 — Start the FastAPI Application

Open a **new terminal** (keep Fuseki running in the other one):

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag

/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/uvicorn app.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process ...
INFO:     Started server process ...
```

### Open the API documentation

Go to: **http://localhost:8000/docs**

This is the **Swagger UI** — an interactive page where you can test every endpoint directly from your browser!

---

## 11. Step 9 — Test the API

### 11.1 Health Check

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

Expected:
```json
{
    "status": "healthy",
    "fuseki_connected": true,
    "openai_configured": true,
    "graph_size": {
        "persons": 100,
        "relationships": 357,
        "data_triples": 2249,
        "ontology_triples": 114,
        "total_triples": 2363
    }
}
```

### 11.2 List All Persons

```bash
curl "http://localhost:8000/persons?limit=5" | python3 -m json.tool
```

### 11.3 Get a Specific Person

```bash
curl http://localhost:8000/person/person001 | python3 -m json.tool
```

### 11.4 Natural Language Query (the main feature!)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who are the friends of person001?", "include_metadata": true}' \
  | python3 -m json.tool
```

### 11.5 More Query Examples

```bash
# Find people in a specific job
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many software engineers are in the network?"}'

# Ask about relationships
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is married to whom in the network?"}'

# Ask about the schema itself
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What types of relationships exist in the ontology?"}'
```

### 11.6 Add a New Person

```bash
curl -X POST http://localhost:8000/add-person \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice Johnson",
    "age": 28,
    "gender": "female",
    "phone": "+1-555-000-1111",
    "email": "alice.johnson@email.com",
    "city": "Boston",
    "state": "Massachusetts",
    "country": "USA",
    "job_title": "Data Scientist",
    "industry": "Technology"
  }' | python3 -m json.tool
```

### 11.7 Add a Relationship

```bash
curl -X POST http://localhost:8000/add-relationship \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Alice Johnson",
    "predicate": "friendOf",
    "object": "person001"
  }' | python3 -m json.tool
```

---

## 12. Step 10 — Run Automated Tests

```bash
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag

/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python -m pytest tests/ -v
```

Expected: All 24 tests pass. These tests use mocking so they don't need Fuseki to be running.

---

## 13. Troubleshooting

### "Cannot connect to Fuseki"
- **Is Fuseki running?** Check the terminal where you started it.
- **Is the port correct?** Default is 3030. Check with: `curl http://localhost:3030/$/ping`
- **Did you create the dataset?** The `--mem /foaf` flag creates it automatically.

### "java: command not found"
- Install Java: `sudo apt install openjdk-17-jre-headless -y`

### "Connection refused" when loading data
- Make sure Fuseki is running BEFORE you run `load_data.py`
- Make sure the endpoint in `.env` matches: `FUSEKI_ENDPOINT=http://localhost:3030/foaf`

### "OpenAI API error" or "Authentication failed"
- Check your API key in `.env` is correct and has credits
- Make sure there are no extra spaces around the key

### "Module not found" errors
- Make sure you're using the right Python: `/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python`
- Re-install dependencies: `pip install -r requirements.txt`

### Fuseki starts but data loading fails
- Check Fuseki logs in the terminal where it's running
- Try the curl commands manually (Option B in Step 6)
- Make sure the dataset name is `/foaf` (not `/foaf/`)

### "wget: command not found"
- Use curl instead: `curl -O https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-5.3.0.tar.gz`

### Data was lost after restarting Fuseki
- You used `--mem` mode (in-memory). Data is lost on restart.
- Use `--tdb2 --loc=./databases/foaf` for persistent storage (see Step 3.2)
- After restarting, re-run `python data/load_data.py` to reload

---

## 14. Understanding the Two-Graph Architecture

### Why two graphs?

Think of it like a **database schema** vs **database rows**:

| Concept | Ontology Graph (Blueprint) | Data Graph (Instances) |
|---|---|---|
| **What it holds** | "A Person CAN have a name, age, friends..." | "John Smith IS 35, IS friends with Jane Doe" |
| **Analogy** | Database schema / table definitions | Actual rows in the tables |
| **Graph URI** | `http://example.org/foaf-poc/ontology` | `http://example.org/foaf-poc/data` |
| **File** | `data/ontology.ttl` | `data/sample_data.ttl` |
| **Changes** | Rarely (only when you add new property types) | Frequently (add/update persons) |

### How queries work with named graphs

In SPARQL, you specify which graph to query using `GRAPH <uri> { ... }`:

```sparql
# Query the DATA graph (get actual persons)
SELECT ?name WHERE {
    GRAPH <http://example.org/foaf-poc/data> {
        ?person foaf:name ?name
    }
}

# Query the ONTOLOGY graph (get the blueprint)
SELECT ?property ?label WHERE {
    GRAPH <http://example.org/foaf-poc/ontology> {
        ?property a rdf:Property ;
                  rdfs:label ?label .
    }
}
```

### How the LLM agent uses this

1. When you ask "Who is John Smith?" → Agent queries the **data graph**
2. When you ask "What properties can a person have?" → Agent queries the **ontology graph**
3. The SPARQL generation prompt tells GPT-4 about both graphs so it always targets the right one

---

## Quick Reference — Command Cheat Sheet

```bash
# ─── Start Fuseki (Terminal 1) ───────────────────────────────────
cd /home/nabeel/Documents/nabeel/neo4j_poc/fuseki
./fuseki-server --mem /foaf

# ─── Load data (Terminal 2, one-time) ────────────────────────────
cd /home/nabeel/Documents/nabeel/neo4j_poc/foaf-graph-rag
/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python data/load_data.py

# ─── Start API (Terminal 2) ──────────────────────────────────────
/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/uvicorn app.main:app --reload --port 8000

# ─── Test (Terminal 3) ───────────────────────────────────────────
curl http://localhost:8000/health | python3 -m json.tool

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who are the friends of person001?"}'

# ─── Run tests ───────────────────────────────────────────────────
/home/nabeel/Documents/nabeel/neo4j_poc/foafpoc/bin/python -m pytest tests/ -v
```

---

**You're all set!** If you have questions, check the Troubleshooting section above or the `README.md` in the project root.

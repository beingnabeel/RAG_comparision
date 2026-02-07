# FoaF Graph RAG — Complete Project Documentation

> A comprehensive end-to-end explanation of every component, file, and design decision.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Configuration](#5-configuration)
6. [The Ontology](#6-the-ontology)
7. [Sample Data Generation](#7-sample-data-generation)
8. [Data Loading](#8-data-loading)
9. [Graph Layer](#9-graph-layer)
10. [LLM Layer](#10-llm-layer)
11. [Agent Layer](#11-agent-layer)
12. [API Layer](#12-api-layer)
13. [FastAPI Entry Point](#13-fastapi-entry-point)
14. [CLI Chatbot](#14-cli-chatbot)
15. [Graph Visualizer](#15-graph-visualizer)
16. [Utilities](#16-utilities)
17. [Tests](#17-tests)
18. [Deployment](#18-deployment)
19. [End-to-End Request Flow](#19-end-to-end-request-flow)
20. [Named Graph Architecture](#20-named-graph-architecture)
21. [Error Handling & Rate Limiting](#21-error-handling--rate-limiting)
22. [Appendix A — SPARQL Query Templates](#appendix-a--sparql-query-templates)
23. [Appendix B — Dependencies](#appendix-b--dependencies)
24. [Appendix C — Other Project Files](#appendix-c--other-project-files)

---

## 1. Project Overview

**FoaF Graph RAG** is a proof-of-concept **Graph RAG** (Retrieval-Augmented Generation) application. It manages biographical and relationship data for 100 individuals stored in an **RDF knowledge graph** and lets users interact with the data using **natural language**.

### What is Graph RAG?

Traditional RAG retrieves text chunks from a vector database. **Graph RAG** retrieves structured data from a **knowledge graph** using **SPARQL queries**. The LLM:

1. Translates natural language into SPARQL
2. Executes the query against the graph database
3. Formats the structured results into a natural language response

This ensures **zero hallucination** — every fact is grounded in actual graph data.

### What is FoaF?

**FoaF** = **Friend of a Friend** — a well-known RDF vocabulary for describing people and social connections. This project extends FoaF with:

- **schema.org** — addresses, job titles
- **rel:** — family relationships (spouse, parent, child, sibling)
- **custom:** — project-specific properties (industry, occupation, colleague, neighbor)

### Key Capabilities

- **Natural language querying** — "Who are the friends of Mark Johnson?" → SPARQL → execute → response
- **Add persons and relationships** — via API, CLI, or natural language
- **Ontology introspection** — view the schema blueprint
- **Graph visualization** — interactive browser-based vis.js visualizer
- **CLI chatbot** — interactive terminal interface
- **REST API** — FastAPI with auto-generated Swagger docs

---

## 2. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                     USER INTERFACES                      │
│  ┌─────────┐   ┌────────────┐   ┌───────────────────┐  │
│  │ CLI     │   │ REST API   │   │ Graph Visualizer  │  │
│  │ cli.py  │   │ /query     │   │ /visualize        │  │
│  └────┬────┘   └─────┬──────┘   └────────┬──────────┘  │
└───────┼──────────────┼───────────────────┼──────────────┘
        │              │                   │
        ▼              ▼                   │
┌────────────────────────────────┐         │
│       LangGraph AGENT          │         │
│  1. Classify Intent (regex)    │         │
│  2. Generate SPARQL (LLM #1)  │         │
│  3. Execute Query (Fuseki)     │         │
│  4. Format Response (LLM #2)  │         │
└───────────────┬────────────────┘         │
                │                          │
                ▼                          ▼
┌──────────────────────────────────────────────────┐
│          APACHE JENA FUSEKI (port 3030)           │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Ontology Graph   │  │ Data Graph           │  │
│  │ <.../ontology>   │  │ <.../data>           │  │
│  │ 2 classes        │  │ 100 persons          │  │
│  │ 29 properties    │  │ 549 relationships    │  │
│  │ 120 triples      │  │ 2249 triples         │  │
│  └──────────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Component       | Technology                           | Purpose                           |
| --------------- | ------------------------------------ | --------------------------------- |
| Graph Database  | Apache Jena Fuseki 5.x               | RDF triple store with SPARQL 1.1  |
| Storage Engine  | TDB2                                 | Persistent on-disk storage        |
| Backend         | FastAPI                              | Async Python web framework        |
| LLM Provider    | Google Gemini (`gemini-2.5-flash`)   | Free-tier LLM                     |
| LLM Integration | LangChain (`langchain-google-genai`) | LLM abstraction                   |
| Agent Framework | LangGraph                            | State machine for agent workflows |
| RDF Library     | RDFLib                               | RDF data generation/parsing       |
| SPARQL Client   | SPARQLWrapper                        | HTTP client for SPARQL endpoints  |
| Data Generation | Faker                                | Realistic fake person data        |
| Validation      | Pydantic                             | Request/response schemas          |
| Visualization   | vis.js (CDN)                         | Interactive network graphs        |
| Testing         | pytest                               | Unit testing                      |
| Language        | Python 3.12+                         | Primary language                  |

---

## 4. Project Structure

```
foaf-graph-rag/
├── app/
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Settings (env vars, graph URIs)
│   ├── agent/
│   │   ├── graph_agent.py        # LangGraph workflow (classify→generate→execute→format)
│   │   ├── prompts.py            # System prompts for LLM
│   │   ├── state.py              # Agent state schema (TypedDict)
│   │   └── tools.py              # LangChain tools (execute SPARQL, add person, etc.)
│   ├── api/
│   │   ├── endpoints.py          # REST endpoints (/health, /query, /add-person, etc.)
│   │   ├── graph_viz.py          # Visualization endpoints (/viz/data-graph, /viz/ontology-graph)
│   │   └── dependencies.py       # Dependency injection
│   ├── graph/
│   │   ├── sparql_client.py      # SPARQLWrapper client (SELECT, ASK, UPDATE)
│   │   ├── query_builder.py      # SPARQL query templates with GRAPH clauses
│   │   └── validator.py          # Input validation, SPARQL injection prevention
│   ├── llm/
│   │   ├── openai_client.py      # Google Gemini client (historical filename)
│   │   └── query_generator.py    # NL → SPARQL with retry logic
│   ├── models/
│   │   ├── requests.py           # Pydantic request models
│   │   └── responses.py          # Pydantic response models
│   └── utils/
│       ├── helpers.py            # URI conversion, predicate resolution
│       └── logging.py            # Logging configuration
├── cli.py                        # Interactive CLI chatbot
├── static/
│   └── visualizer.html           # vis.js graph visualizer
├── data/
│   ├── ontology.ttl              # RDF ontology (2 classes, 29 properties)
│   ├── sample_data.ttl           # Generated data (100 persons)
│   ├── generate_sample_data.py   # Faker-based data generator
│   ├── load_data.py              # Loads data into Fuseki named graphs
│   └── queries/templates.sparql  # Reference SPARQL examples
├── tests/
│   ├── test_api.py               # Endpoint tests (mocked)
│   └── test_graph.py             # Query builder, validator tests
├── deployment/
│   ├── Dockerfile                # API container
│   ├── docker-compose.yml        # Fuseki + API stack
│   ├── fuseki-config.ttl         # Fuseki TDB2 config
│   └── render.yaml               # Render.com deployment
├── .env / .env.example           # Environment variables
├── requirements.txt              # Python dependencies
└── SETUP_GUIDE.md                # Beginner setup guide
```

---

## 5. Configuration

### `app/config.py`

Uses **Pydantic Settings** to load from environment variables or `.env`:

```python
class Settings(BaseSettings):
    # API
    API_TITLE: str = "FoaF Graph RAG API"
    API_VERSION: str = "1.0.0"
    API_PORT: int = 8000

    # LLM (Google Gemini)
    GOOGLE_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TEMPERATURE: float = 0.0        # Deterministic for SPARQL generation

    # Fuseki
    FUSEKI_ENDPOINT: str = "http://localhost:3030/foaf"
    FUSEKI_QUERY_ENDPOINT  → "{FUSEKI_ENDPOINT}/query"   # computed property
    FUSEKI_UPDATE_ENDPOINT → "{FUSEKI_ENDPOINT}/update"  # computed property
    FUSEKI_DATA_ENDPOINT   → "{FUSEKI_ENDPOINT}/data"    # computed property

    # Named Graphs
    DEFAULT_NAMESPACE: str = "http://example.org/foaf-poc/"
    ONTOLOGY_GRAPH_URI: str = "http://example.org/foaf-poc/ontology"
    DATA_GRAPH_URI: str = "http://example.org/foaf-poc/data"

    LOG_LEVEL: str = "INFO"
```

**Key decisions:**

- Two named graph URIs separate schema from data
- Temperature 0.0 for deterministic SPARQL
- Computed properties derive sub-endpoints from base URL
- Singleton `settings = Settings()` imported everywhere

### `.env.example`

```env
GOOGLE_API_KEY=your-google-api-key-here
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.0
FUSEKI_ENDPOINT=http://localhost:3030/foaf
API_PORT=8000
LOG_LEVEL=INFO
```

---

## 6. The Ontology

### `data/ontology.ttl`

The **schema blueprint** defining what entities and properties exist. Written in Turtle format, stored in `<http://example.org/foaf-poc/ontology>`.

**Classes (2):** `custom:Person`, `schema:Organization`

**Properties (29) organized by category:**

| Category              | Properties                                                                                                                              |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Personal (8)**      | `foaf:name`, `givenName`, `familyName`, `nick`, `age`, `gender`, `phone`, `mbox`                                                        |
| **Location (5)**      | `schema:address`, `addressLocality`, `addressRegion`, `postalCode`, `addressCountry`                                                    |
| **Professional (4)**  | `schema:jobTitle`, `schema:worksFor`, `custom:occupation`, `custom:industry`                                                            |
| **Relationships (8)** | `foaf:knows`, `rel:friendOf`, `rel:spouseOf`, `rel:parentOf`, `rel:childOf`, `rel:siblingOf`, `custom:colleagueOf`, `custom:neighborOf` |
| **Metadata (3)**      | `custom:createdAt`, `custom:updatedAt`, `custom:dataSource`, `custom:closenessScore`                                                    |

Each property has `rdfs:domain` (which class), `rdfs:range` (value type), and `rdfs:label` (human-readable name).

---

## 7. Sample Data Generation

### `data/generate_sample_data.py`

Generates **100 realistic fake persons** with relationships using Faker. Seeds (`42`) ensure reproducibility.

**Per person:** name, age (18-80), gender, phone, email, full address (USA), job, industry, timestamp.

**Relationships generated:**

- **2-5 friendships** per person (one-directional `rel:friendOf`)
- **30% marriage** chance (`rel:spouseOf`, bidirectional, no polygamy)
- **60% of married couples** get 1-3 children (`rel:parentOf`/`rel:childOf`)
- **20%** colleague, **15%** neighbor, **10%** sibling

**Output:** `data/sample_data.ttl` (~2249 triples, ~549 relationships)

---

## 8. Data Loading

### `data/load_data.py`

Loads ontology and data into **separate named graphs** via Fuseki's Graph Store Protocol:

1. Check Fuseki connectivity
2. `PUT data/ontology.ttl` → `<http://example.org/foaf-poc/ontology>`
3. `PUT data/sample_data.ttl` → `<http://example.org/foaf-poc/data>`
4. Verify by counting triples in each graph

Uses HTTP PUT to `{FUSEKI_ENDPOINT}/data?graph={graph_uri}` with `Content-Type: text/turtle`.

---

## 9. Graph Layer

### 9.1 SPARQL Client — `app/graph/sparql_client.py`

Wraps `SPARQLWrapper` for clean Fuseki access:

| Method                  | SPARQL Type   | Returns                                            |
| ----------------------- | ------------- | -------------------------------------------------- |
| `execute_select(query)` | SELECT        | `List[Dict]` bindings                              |
| `execute_ask(query)`    | ASK           | `bool`                                             |
| `execute_update(query)` | INSERT/DELETE | `bool`                                             |
| `test_connection()`     | SELECT count  | `bool`                                             |
| `get_graph_stats()`     | 4× SELECT     | `Dict` with persons, relationships, triples counts |

Singleton: `sparql_client = SPARQLClient()`

### 9.2 Query Builder — `app/graph/query_builder.py`

SPARQL template functions. Every query uses the correct `GRAPH <uri>` clause.

**Data graph functions:**

- `search_person_by_name(name)` — case-insensitive FILTER(CONTAINS)
- `get_person_details(uri)` — all predicates/values for a person
- `get_person_relationships(uri)` — **UNION** for bidirectional relationships
- `get_next_person_id()` — COUNT for generating next person ID
- `insert_person(uri, triples)` — INSERT DATA into data graph
- `insert_relationship(s, p, o)` — insert one relationship triple
- `get_all_persons(limit)` — list with OPTIONAL fields, ORDER BY name

**Ontology graph functions:**

- `get_ontology_classes()` — all `rdfs:Class` with labels
- `get_ontology_properties()` — all `rdf:Property` with domain/range
- `get_full_ontology()` — every triple (for LLM context)

### 9.3 Validator — `app/graph/validator.py`

- `validate_person_data(data)` — name required, age 0-150, valid gender
- `validate_relationship(predicate)` — must be one of 8 allowed types
- `sanitize_sparql_string(value)` — escapes `\`, `"`, `'` to prevent injection

---

## 10. LLM Layer

### 10.1 LLM Client — `app/llm/openai_client.py`

> Filename kept for compatibility; now uses **Google Gemini**.

```python
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        google_api_key=settings.GOOGLE_API_KEY,
    )

def is_llm_configured() -> bool:
    return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.strip())
```

### 10.2 Query Generator — `app/llm/query_generator.py`

**`SPARQL_GENERATION_PROMPT`** (75 lines) teaches the LLM:

- Named graph architecture (ontology vs. data)
- All namespace prefixes
- Every class, property, and relationship predicate
- 12 rules: always use GRAPH clauses, FILTER for searches, LIMIT results, no markdown, etc.

**`generate_sparql(natural_language, intent)`:**

1. Sends `[SystemMessage(prompt), HumanMessage(intent + request)]` to LLM
2. **Retry logic:** 3 attempts with exponential backoff (2s, 4s, 8s) for rate limits
3. **Post-processing:** strips markdown fences, fixes truncated LIMIT clauses

---

## 11. Agent Layer

### 11.1 Agent State — `app/agent/state.py`

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]  # append-only
    user_query: str          # Original query
    intent: str              # query/add_person/add_relationship/update/error
    sparql_query: str        # Generated SPARQL
    graph_results: list      # Raw Fuseki results
    final_response: str      # NL response for user
    error: Optional[str]     # Error message
```

### 11.2 Prompts — `app/agent/prompts.py`

- **`INTENT_CLASSIFICATION_PROMPT`** — legacy (now rule-based)
- **`RESPONSE_FORMATTING_PROMPT`** — converts raw results to conversational NL

### 11.3 Tools — `app/agent/tools.py`

6 LangChain `@tool` functions:

| Tool                        | Purpose              | Key Logic                                                     |
| --------------------------- | -------------------- | ------------------------------------------------------------- |
| `execute_sparql_query`      | Run arbitrary SPARQL | Strips PREFIX to detect query type (SELECT/ASK/INSERT/DELETE) |
| `search_person_by_name`     | Name search          | Sanitizes input, calls query_builder                          |
| `get_person_relationships`  | All relationships    | Resolves names to URIs first                                  |
| `add_person_to_graph`       | Create person        | Validates → counts → builds triples → INSERT                  |
| `add_relationship_to_graph` | Create relationship  | Validates predicate → resolves names → INSERT                 |
| `get_ontology_schema`       | Schema info          | Returns classes + properties from ontology graph              |

### 11.4 Graph Agent — `app/agent/graph_agent.py`

**LangGraph state machine** with 5 nodes.

**Optimization:** Intent classification uses **regex** (no LLM call):

```python
ADD_PERSON_PATTERNS  = r"\b(add|create|insert|register|new)\b.*(person|people|...)"
ADD_REL_PATTERNS     = r"\b(add|create|make|set)\b.*(friend|spouse|parent|...)"
UPDATE_PATTERNS      = r"\b(update|change|modify|edit)\b.*(name|age|phone|...)"
# Default: "query"
```

**Workflow:**

```
classify_intent (regex, no LLM)
       │
  route_by_intent ──── intent="error" ──→ handle_error → END
       │
  intent="query" (or add_*)
       │
generate_sparql (LLM call #1)
       │
execute_query (Fuseki)
       │
format_response (LLM call #2, with fallback)
       │
      END
```

**Total: 2 LLM calls per request** (down from 3 originally).

**`llm_invoke_with_retry()`** — exponential backoff (2s, 4s, 8s) for 429/RESOURCE_EXHAUSTED errors.

**`_fallback_format()`** — if LLM formatting fails (rate limit), produces clean structured text without an LLM call.

**`run_agent(user_query)`** — async entry point returning `{success, query, intent, results, response, sparql_query, execution_time_ms}`.

---

## 12. API Layer

### 12.1 Pydantic Models — `app/models/`

**Requests:** `QueryRequest`, `AddPersonRequest` (13 fields), `AddRelationshipRequest`

**Responses:** `QueryResponse`, `AddPersonResponse`, `AddRelationshipResponse`, `HealthResponse`, `ErrorResponse`

### 12.2 Endpoints — `app/api/endpoints.py`

| Method | Path                 | Description                                      |
| ------ | -------------------- | ------------------------------------------------ |
| GET    | `/health`            | Fuseki connectivity, LLM status, graph stats     |
| POST   | `/query`             | **Main endpoint** — runs the full agent pipeline |
| POST   | `/add-person`        | Adds person via tool                             |
| POST   | `/add-relationship`  | Adds relationship via tool                       |
| GET    | `/person/{id}`       | Person details + relationships                   |
| GET    | `/persons?limit=100` | List all persons                                 |

### 12.3 Visualization API — `app/api/graph_viz.py`

| Endpoint                        | Returns                                                          |
| ------------------------------- | ---------------------------------------------------------------- |
| `GET /viz/data-graph?limit=100` | Nodes (colored by gender) + edges (colored by relationship type) |
| `GET /viz/ontology-graph`       | Nodes (shaped by type: diamond=Class, triangle=Property) + edges |

Both return `{nodes: [...], edges: [...], stats: {node_count, edge_count}}` for vis.js.

### 12.4 Dependencies — `app/api/dependencies.py`

Simple DI: `get_sparql_client() → sparql_client` singleton.

---

## 13. FastAPI Entry Point

### `app/main.py`

1. Creates FastAPI app with CORS middleware (all origins)
2. Mounts `router` (main endpoints) and `viz_router` (visualization)
3. Serves `static/` directory
4. `GET /` — API info with links to `/docs` and `/visualize`
5. `GET /visualize` — serves the vis.js HTML page

**Start:** `uvicorn app.main:app --reload --port 8000`

---

## 14. CLI Chatbot

### `cli.py` (509 lines)

Interactive terminal chatbot with colored output.

**Startup:** Banner → Fuseki check → LLM check → Graph stats → Help → REPL loop

**Commands:**

| Command           | Action                    | Backend Call                      |
| ----------------- | ------------------------- | --------------------------------- |
| `/persons [n]`    | List n persons in table   | `query_builder` → `sparql_client` |
| `/person <id>`    | All properties for person | `query_builder` → `sparql_client` |
| `/search <name>`  | Name search               | `search_person_by_name` tool      |
| `/friends <name>` | All relationships         | `get_person_relationships` tool   |
| `/add-person`     | Interactive form          | `add_person_to_graph` tool        |
| `/add-rel`        | Interactive form          | `add_relationship_to_graph` tool  |
| `/stats`          | Graph statistics          | `sparql_client.get_graph_stats()` |
| `/schema`         | Ontology blueprint        | `get_ontology_schema` tool        |
| `/sparql <q>`     | Raw SPARQL                | `execute_sparql_query` tool       |
| _(any text)_      | NL query via agent        | `run_agent()`                     |

**Features:** ANSI colors, table formatting (auto-width columns), SPARQL preview, response time, asyncio event loop for async agent calls.

---

## 15. Graph Visualizer

### `static/visualizer.html`

Single-page vis.js application (dark theme, no build step):

- **Data Graph view:** 100 person nodes + 549 relationship edges
- **Ontology Graph view:** schema classes/properties as shaped nodes
- **Search:** filters nodes, highlights matches, fades others
- **Node click:** shows details + connections in side panel
- **Physics toggle:** enable/disable ForceAtlas2 layout
- **Reset view:** fit all nodes

**Color coding:**

- Data: indigo=male, pink=female; green=friendOf, red=spouseOf, amber=parentOf, etc.
- Ontology: diamond=Class, triangle=ObjectProperty, inverted triangle=DatatypeProperty

---

## 16. Utilities

### `app/utils/helpers.py`

- `get_timestamp()` — UTC ISO format
- `uri_to_id(uri)` / `id_to_uri(id)` — URI ↔ person ID conversion
- `resolve_predicate(name)` — maps "friendOf" → full URI
- `RELATIONSHIP_MAP` — dict of all 8 relationship short names → URIs

### `app/utils/logging.py`

- `setup_logging()` — configures Python logging (level from settings, stdout)
- `get_logger(name)` — returns named logger

---

## 17. Tests

### `tests/test_graph.py` (137 lines)

- **TestValidator (7 tests):** valid/invalid person data, relationships, string sanitization
- **TestQueryBuilder (9 tests):** correct GRAPH clauses, FILTER/CONTAINS, UNION, INSERT targeting
- **TestSPARQLClient (2 tests):** mocked connection success/failure

### `tests/test_api.py` (107 lines)

- **TestRootEndpoint (1):** root returns 200
- **TestHealthEndpoint (2):** healthy and degraded states
- **TestQueryEndpoint (1):** mocked agent success
- **TestAddPersonEndpoint (1):** mocked tool success
- **TestAddRelationshipEndpoint (1):** mocked tool success

All tests mock external dependencies. Run: `pytest tests/ -v`

---

## 18. Deployment

### `deployment/Dockerfile`

Python 3.12-slim → installs requirements → copies app + data → runs uvicorn on port 8000.

### `deployment/docker-compose.yml`

Two services:

- **fuseki:** `stain/jena-fuseki` image, port 3030, TDB2 volume, health check
- **api:** builds from Dockerfile, port 8000, depends on fuseki healthy

### `deployment/fuseki-config.ttl`

TDB2 dataset named "foaf" with query/update/upload/data endpoints.

### `deployment/render.yaml`

Render.com web service config for cloud deployment.

---

## 19. End-to-End Request Flow

**Example:** User asks _"Who are the friends of Mark Johnson?"_

```
1. CLI/API receives: "Who are the friends of Mark Johnson?"
         │
2. classify_intent_node() → regex matches nothing special → intent = "query"
         │
3. generate_sparql_node() → LLM call #1:
   System prompt (75 lines of schema + rules) + "Intent: query\nUser: Who are the friends..."
   LLM returns:
     PREFIX rel: <...>
     PREFIX foaf: <...>
     SELECT ?friendName WHERE {
       GRAPH <http://example.org/foaf-poc/data> {
         ?person foaf:name "Mark Johnson" .
         ?person rel:friendOf ?friend .
         ?friend foaf:name ?friendName .
       }
     }
         │
4. execute_query_node() → strips PREFIX, detects SELECT
   → sparql_client.execute_select(query)
   → HTTP GET to http://localhost:3030/foaf/query
   → Fuseki returns JSON: [{"friendName": {"value": "John Gibson"}}, ...]
         │
5. format_response_node() → LLM call #2:
   "The user asked: Who are the friends of Mark Johnson?
    Results: [{"friendName": {"value": "John Gibson"}}, ...]
    Create a natural response..."
   LLM returns: "Mark Johnson has 2 friends: John Gibson and Sarah Williams."
         │
6. Response returned to user with metadata (intent, time, SPARQL, result count)
```

---

## 20. Named Graph Architecture

The project stores data in **two separate named graphs** within a single Fuseki dataset:

| Graph        | URI                                    | Contents                         | Purpose                           |
| ------------ | -------------------------------------- | -------------------------------- | --------------------------------- |
| **Ontology** | `http://example.org/foaf-poc/ontology` | Classes, properties, constraints | Schema blueprint — what CAN exist |
| **Data**     | `http://example.org/foaf-poc/data`     | Person instances, relationships  | Actual data — what DOES exist     |

**Why separate graphs?**

1. **Clean separation** — schema changes don't mix with data changes
2. **Targeted queries** — `GRAPH <.../data>` reads only data, `GRAPH <.../ontology>` reads only schema
3. **Independent loading** — can reload ontology without touching data and vice versa
4. **LLM context** — agent can introspect the ontology to understand the schema before generating queries

**Every SPARQL query** in the codebase uses explicit `GRAPH <uri>` clauses. The LLM is also trained (via the system prompt) to always include the correct GRAPH clause.

---

## 21. Error Handling & Rate Limiting

### Rate Limit Protection

Google Gemini free tier has rate limits. The project handles this at multiple levels:

1. **Rule-based intent classification** — saves 1 LLM call per request (was 3, now 2)
2. **`llm_invoke_with_retry()`** — retries with exponential backoff (2s, 4s, 8s) on 429/RESOURCE_EXHAUSTED
3. **`generate_sparql()` retry** — same backoff pattern for SPARQL generation
4. **`_fallback_format()`** — if response formatting LLM call fails, produces structured text without LLM

### SPARQL Error Handling

- **PREFIX stripping** — `execute_sparql_query` strips PREFIX declarations before detecting query type, so `PREFIX ... SELECT` works correctly
- **Truncated LIMIT fix** — if LLM outputs `LIMIT` without a number, post-processing adds `LIMIT 50`
- **Markdown stripping** — removes ` ```sparql ``` ` code fences from LLM output

### Input Validation

- `validate_person_data()` — prevents invalid ages, missing names
- `validate_relationship()` — rejects unknown relationship types
- `sanitize_sparql_string()` — prevents SPARQL injection via string escaping

### General Error Handling

- Every tool, endpoint, and agent node has try/except with logging
- Agent returns `{success: False, response: "error message"}` on failure
- CLI displays errors in red with helpful messages
- Health endpoint reports "degraded" if Fuseki or LLM is down

---

## Appendix A — SPARQL Query Templates

### `data/queries/templates.sparql`

A commented reference file with 7 example SPARQL queries demonstrating common patterns:

| #   | Pattern                    | Key Technique                                 |
| --- | -------------------------- | --------------------------------------------- |
| 1   | Search person by name      | `FILTER(CONTAINS(LCASE(?name), ...))`         |
| 2   | Get friends of a person    | `rel:friendOf` traversal                      |
| 3   | Friends-of-friends (2-hop) | Path traversal with `FILTER(?fof != ?person)` |
| 4   | Count by industry          | `GROUP BY ?industry ORDER BY DESC(?count)`    |
| 5   | Spouse and their friends   | Multi-hop with `OPTIONAL`                     |
| 6   | Persons in a city          | Filter by `schema:addressLocality`            |
| 7   | Count all triples          | `SELECT (COUNT(*) AS ?count)`                 |

These serve as documentation and a reference for understanding the LLM's SPARQL generation patterns.

---

## Appendix B — Dependencies

### `requirements.txt`

```
fastapi>=0.128.0            # Web framework
uvicorn[standard]>=0.40.0   # ASGI server
langchain>=1.2.0            # LLM abstraction layer
langchain-google-genai>=4.2.0  # Google Gemini integration
langgraph>=1.0.0            # Agent state machine framework
rdflib>=7.0.0               # RDF graph generation/parsing
SPARQLWrapper>=2.0.0        # HTTP client for SPARQL endpoints
pydantic>=2.12.0            # Data validation
pydantic-settings>=2.12.0   # Settings from env vars/.env
python-dotenv>=1.2.0        # .env file loading
faker>=40.0.0               # Fake data generation
httpx>=0.28.0               # Async HTTP client (used by FastAPI TestClient)
pytest>=8.0.0               # Testing framework
```

---

## Appendix C — Other Project Files

### `SETUP_GUIDE.md`

A **650-line beginner-friendly setup guide** walking through every step from a blank machine to a running application:

1. Understanding the architecture
2. Installing Java (required by Fuseki)
3. Downloading & configuring Fuseki
4. Starting Fuseki & creating the dataset
5. Configuring the Python project & `.env`
6. Generating sample data
7. Loading data into Fuseki named graphs
8. Verifying data in Fuseki UI (with sample SPARQL queries)
9. Starting the FastAPI server
10. Testing the API (health, query, add-person, add-relationship)
11. Running automated tests
12. Troubleshooting common issues
13. Named graph architecture explanation
14. Quick-reference command cheat sheet

### `README.md`

A concise quick-start readme with technology stack table, setup instructions, API endpoint reference, example curl commands, Docker deployment, and project structure overview.

### `__init__.py` Files

Standard Python package markers (empty files) exist in:

- `app/__init__.py`
- `app/agent/__init__.py`
- `app/api/__init__.py`
- `app/graph/__init__.py`
- `app/llm/__init__.py`
- `app/models/__init__.py`
- `app/utils/__init__.py`
- `tests/__init__.py`

These make each directory importable as a Python package.

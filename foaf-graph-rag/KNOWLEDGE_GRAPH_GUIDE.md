# How to Use a Different Knowledge Graph

> A step-by-step guide explaining exactly which files to modify when you want to swap the FoaF ontology/data for a completely different domain (e.g., movies, products, medical records, etc.).

---

## Table of Contents

1. [Overview — What Needs to Change](#1-overview--what-needs-to-change)
2. [Step 1 — Design Your New OWL Ontology](#2-step-1--design-your-new-owl-ontology)
3. [Step 2 — Create Your Data File](#3-step-2--create-your-data-file)
4. [Step 3 — Update Configuration](#4-step-3--update-configuration)
5. [Step 4 — Update the SPARQL Generation Prompt](#5-step-4--update-the-sparql-generation-prompt)
6. [Step 5 — Update the Query Builder](#6-step-5--update-the-query-builder)
7. [Step 6 — Update the Validator](#7-step-6--update-the-validator)
8. [Step 7 — Update the Agent Tools](#8-step-7--update-the-agent-tools)
9. [Step 8 — Update the Agent Intent Classifier](#9-step-8--update-the-agent-intent-classifier)
10. [Step 9 — Update API Endpoints & Pydantic Models](#10-step-9--update-api-endpoints--pydantic-models)
11. [Step 10 — Update the CLI](#11-step-10--update-the-cli)
12. [Step 11 — Update the Visualizer](#12-step-11--update-the-visualizer)
13. [Step 12 — Load Data into Fuseki](#13-step-12--load-data-into-fuseki)
14. [Step 13 — Update Tests](#14-step-13--update-tests)
15. [Quick Reference — File Change Summary](#15-quick-reference--file-change-summary)
16. [Worked Example — Movie Knowledge Graph](#16-worked-example--movie-knowledge-graph)
17. [How to Ingest New Ontology and Data Graphs](#17-how-to-ingest-new-ontology-and-data-graphs)

---

## 1. Overview — What Needs to Change

The system is designed around a **specific domain** (FoaF social network). When you switch to a different knowledge graph, you need to update the components that are **domain-specific**. Here's the complete map:

| Layer | File(s) | What to Change | Effort |
|---|---|---|---|
| **Ontology** | `data/ontology.ttl` | Replace entirely with your domain's OWL ontology | High |
| **Data** | `data/sample_data.ttl` | Replace with your domain's instance data | High |
| **LLM Prompt** | `app/llm/query_generator.py` | Rewrite `SPARQL_GENERATION_PROMPT` with your classes, properties, rules | High |
| **Query Builder** | `app/graph/query_builder.py` | Replace SPARQL templates with your domain's common queries | Medium |
| **Validator** | `app/graph/validator.py` | Update validation rules for your domain entities | Medium |
| **Agent Tools** | `app/agent/tools.py` | Replace domain-specific tools (e.g., `add_person_to_graph` → `add_movie_to_graph`) | Medium |
| **Agent Classifier** | `app/agent/graph_agent.py` | Update regex patterns for intent classification | Low |
| **API Models** | `app/models/requests.py`, `responses.py` | Update Pydantic schemas for your domain | Medium |
| **API Endpoints** | `app/api/endpoints.py` | Update endpoint paths and logic | Medium |
| **CLI** | `cli.py` | Update commands and help text | Low |
| **Visualizer** | `app/api/graph_viz.py` | Update SPARQL queries and color schemes | Low |
| **Config** | `app/config.py` | Update namespace and graph URIs | Low |
| **Helpers** | `app/utils/helpers.py` | Update URI patterns and predicate maps | Low |

**What does NOT need to change:**
- `app/graph/sparql_client.py` — generic SPARQL client, works with any graph
- `app/llm/openai_client.py` — generic LLM client
- `app/agent/state.py` — generic agent state schema
- `app/agent/prompts.py` — `RESPONSE_FORMATTING_PROMPT` is generic enough
- `app/utils/logging.py` — generic logging
- `app/main.py` — only needs changes if you rename routes
- `deployment/*` — infrastructure is domain-agnostic

---

## 2. Step 1 — Design Your New OWL Ontology

**File:** `data/ontology.ttl`

Replace the entire file with your domain's ontology using OWL constructs.

### Template Structure

```turtle
@prefix myns: <http://example.org/my-domain/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Ontology header
myns:my-ontology a owl:Ontology ;
    rdfs:label "My Domain Ontology" ;
    owl:versionInfo "1.0" .

# Classes
myns:MyClass a owl:Class ;
    rdfs:label "My Class" ;
    rdfs:comment "Description of this class" .

# Datatype Properties (literals: strings, integers, dates)
myns:myProperty a owl:DatatypeProperty ;
    rdfs:domain myns:MyClass ;
    rdfs:range xsd:string ;
    rdfs:label "My Property" .

# Object Properties (links between entities)
myns:relatesTo a owl:ObjectProperty ;
    rdfs:domain myns:MyClass ;
    rdfs:range myns:OtherClass ;
    rdfs:label "Relates To" .

# Symmetric properties (if A relates to B, then B relates to A)
myns:similarTo a owl:ObjectProperty, owl:SymmetricProperty ;
    rdfs:domain myns:MyClass ;
    rdfs:range myns:MyClass .

# Inverse properties
myns:contains a owl:ObjectProperty ;
    owl:inverseOf myns:containedIn .
```

### Key OWL Constructs to Use

| OWL Construct | When to Use |
|---|---|
| `owl:Class` | Define entity types (Person, Movie, Product) |
| `owl:DatatypeProperty` | Properties with literal values (name, age, price) |
| `owl:ObjectProperty` | Properties linking two entities (friendOf, directedBy) |
| `owl:SymmetricProperty` | Bidirectional relationships (spouseOf, siblingOf) |
| `owl:inverseOf` | Inverse pairs (parentOf/childOf, directedBy/directed) |
| `owl:TransitiveProperty` | If A→B and B→C then A→C (ancestorOf, locatedIn) |
| `owl:FunctionalProperty` | At most one value (birthDate, SSN) |

---

## 3. Step 2 — Create Your Data File

**File:** `data/sample_data.ttl`

Create instance data that conforms to your ontology. Use the same namespace prefixes.

```turtle
@prefix myns: <http://example.org/my-domain/> .

myns:entity001 a myns:MyClass ;
    myns:name "Entity One" ;
    myns:relatesTo myns:entity002 .
```

You can also write a `data/generate_sample_data.py` script if you want to generate data programmatically.

---

## 4. Step 3 — Update Configuration

**File:** `app/config.py`

```python
# Change these values:
DEFAULT_NAMESPACE: str = "http://example.org/my-domain/"     # was foaf-poc
ONTOLOGY_GRAPH_URI: str = "http://example.org/my-domain/ontology"
DATA_GRAPH_URI: str = "http://example.org/my-domain/data"
```

Also update `.env` and `.env.example` if your Fuseki dataset name changes (e.g., from `/foaf` to `/movies`):

```env
FUSEKI_ENDPOINT=http://localhost:3030/movies
```

---

## 5. Step 4 — Update the SPARQL Generation Prompt

**File:** `app/llm/query_generator.py`

This is the **most critical file** to update. The `SPARQL_GENERATION_PROMPT` teaches the LLM everything about your domain. Replace the entire prompt with your domain's:

1. **Named graph URIs** — update the GRAPH clause instructions
2. **Namespace prefixes** — your domain's prefixes
3. **OWL ontology summary** — classes and their descriptions
4. **All properties** — with types (string, integer, URI) and descriptions
5. **All relationship predicates** — with directionality notes
6. **Query rules** — adapted for your domain's patterns

### What the Prompt Must Include

```python
SPARQL_GENERATION_PROMPT = """You are a SPARQL query generator for a [YOUR DOMAIN] knowledge graph.

NAMED GRAPH ARCHITECTURE:
  1. ONTOLOGY GRAPH  <http://example.org/my-domain/ontology>
  2. DATA GRAPH      <http://example.org/my-domain/data>

NAMESPACES:
PREFIX myns: <http://example.org/my-domain/>
...

CLASSES:
- myns:Movie — a film in the database
- myns:Actor — a person who acts in movies
- myns:Director — a person who directs movies

PROPERTIES:
- myns:title (string) — movie title
- myns:releaseYear (integer) — year of release
- myns:actedIn (Movie → Actor) — actor appeared in movie
...

RULES:
1. Always use GRAPH <.../data> for instance data.
2. ...

Generate a valid SPARQL query for:
"""
```

---

## 6. Step 5 — Update the Query Builder

**File:** `app/graph/query_builder.py`

Replace the domain-specific query functions. Keep the same architecture (PREFIXES constant, GRAPH clauses, etc.) but change the triple patterns.

### What to Replace

| Current Function | Replace With | Example |
|---|---|---|
| `search_person_by_name(name)` | `search_movie_by_title(title)` | Search your main entity |
| `get_person_details(uri)` | `get_movie_details(uri)` | Get all properties of an entity |
| `get_person_relationships(uri)` | `get_movie_cast(uri)` | Get related entities |
| `get_next_person_id()` | `get_next_movie_id()` | Count for ID generation |
| `insert_person(uri, triples)` | `insert_movie(uri, triples)` | Insert new entity |
| `insert_relationship(s, p, o)` | Keep as-is (generic) | Insert any triple |
| `get_all_persons(limit)` | `get_all_movies(limit)` | List entities |

### What to Keep

- `PREFIXES` constant — update with your prefixes
- `ONTOLOGY_GRAPH` / `DATA_GRAPH` constants — these read from config
- `get_ontology_classes()` — generic, works with any OWL ontology
- `get_ontology_properties()` — generic, works with any OWL ontology
- `get_full_ontology()` — generic

---

## 7. Step 6 — Update the Validator

**File:** `app/graph/validator.py`

Replace:
- `VALID_RELATIONSHIPS` set — your domain's relationship predicates
- `validate_person_data()` → `validate_movie_data()` — your entity's required/optional fields
- `validate_relationship()` — update with your relationship types
- `sanitize_sparql_string()` — keep as-is (generic security function)

---

## 8. Step 7 — Update the Agent Tools

**File:** `app/agent/tools.py`

Replace the domain-specific tools:

| Current Tool | Replace With |
|---|---|
| `search_person_by_name` | `search_movie_by_title` |
| `get_person_relationships` | `get_movie_relationships` |
| `add_person_to_graph` | `add_movie_to_graph` |
| `add_relationship_to_graph` | Keep or rename |
| `get_ontology_schema` | Keep as-is (generic) |
| `execute_sparql_query` | Keep as-is (generic) |

Update the `ALL_TOOLS` list at the bottom.

---

## 9. Step 8 — Update the Agent Intent Classifier

**File:** `app/agent/graph_agent.py`

Update the regex patterns for intent classification:

```python
# Current (FoaF domain):
ADD_PERSON_PATTERNS = re.compile(r"\b(add|create)\b.*(person|people)")

# New (Movie domain):
ADD_MOVIE_PATTERNS = re.compile(r"\b(add|create|insert)\b.*(movie|film)")
ADD_ACTOR_PATTERNS = re.compile(r"\b(add|create)\b.*(actor|actress|cast)")
```

Update `classify_intent_node()` to use the new patterns.

---

## 10. Step 9 — Update API Endpoints & Pydantic Models

**File:** `app/models/requests.py`

```python
# Replace AddPersonRequest with your domain:
class AddMovieRequest(BaseModel):
    title: str
    release_year: Optional[int] = None
    genre: Optional[str] = None
    director: Optional[str] = None
    # ... your domain fields
```

**File:** `app/models/responses.py`

Update response models similarly.

**File:** `app/api/endpoints.py`

Update route paths and handler logic:
- `/add-person` → `/add-movie`
- `/person/{id}` → `/movie/{id}`
- `/persons` → `/movies`
- Update the tool imports and invocations

---

## 11. Step 10 — Update the CLI

**File:** `cli.py`

Update:
- Command names: `/persons` → `/movies`, `/person` → `/movie`
- Help text describing your domain
- Banner text
- Interactive add forms (`cmd_add_person` → `cmd_add_movie`)
- Import statements for your new tools

---

## 12. Step 11 — Update the Visualizer

**File:** `app/api/graph_viz.py`

Update the data graph endpoint:
- SPARQL query to fetch your entities and relationships
- Node colors/shapes for your entity types
- Edge colors for your relationship types

The ontology graph endpoint (`get_ontology_graph`) is **generic** and works with any OWL ontology — no changes needed.

**File:** `static/visualizer.html`

Update the legend labels and colors if needed.

---

## 13. Step 12 — Load Data into Fuseki

### Option A: Using the Load Script

Update `data/load_data.py` if your files or graph URIs changed, then run:

```bash
python data/load_data.py
```

### Option B: Manual Loading with curl

```bash
# Start Fuseki with your new dataset name
./fuseki-server --tdb2 --loc=./databases/movies /movies

# Load ontology
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/ontology.ttl \
  "http://localhost:3030/movies/data?graph=http://example.org/my-domain/ontology"

# Load data
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/sample_data.ttl \
  "http://localhost:3030/movies/data?graph=http://example.org/my-domain/data"
```

### Option C: Using the Fuseki UI

1. Go to `http://localhost:3030`
2. Select your dataset
3. Click "upload data"
4. Upload each `.ttl` file, specifying the target named graph URI

---

## 14. Step 13 — Update Tests

**File:** `tests/test_graph.py`

Update test assertions to match your new:
- Query builder function names
- Validation rules
- Graph URIs (these come from config, so may auto-update)
- Entity types and field names

**File:** `tests/test_api.py`

Update:
- Endpoint paths
- Mock return values
- Request/response field names

---

## 15. Quick Reference — File Change Summary

### Must Change (domain-specific)

| # | File | What |
|---|---|---|
| 1 | `data/ontology.ttl` | Your OWL ontology |
| 2 | `data/sample_data.ttl` | Your instance data |
| 3 | `app/llm/query_generator.py` | `SPARQL_GENERATION_PROMPT` — teaches LLM your domain |
| 4 | `app/graph/query_builder.py` | SPARQL templates for your common queries |
| 5 | `app/graph/validator.py` | Validation rules for your entities |
| 6 | `app/agent/tools.py` | LangChain tools for your domain actions |
| 7 | `app/agent/graph_agent.py` | Intent classification regex patterns |
| 8 | `app/models/requests.py` | Pydantic request schemas |
| 9 | `app/models/responses.py` | Pydantic response schemas |
| 10 | `app/api/endpoints.py` | API routes and handlers |
| 11 | `app/utils/helpers.py` | URI patterns and predicate maps |
| 12 | `cli.py` | CLI commands and help text |

### Should Update (recommended)

| # | File | What |
|---|---|---|
| 13 | `app/config.py` | `DEFAULT_NAMESPACE`, graph URIs |
| 14 | `.env` / `.env.example` | `FUSEKI_ENDPOINT` if dataset name changes |
| 15 | `app/api/graph_viz.py` | Data graph visualization queries & colors |
| 16 | `static/visualizer.html` | Legend labels |
| 17 | `tests/test_graph.py` | Test assertions |
| 18 | `tests/test_api.py` | Test assertions |

### No Change Needed (generic/reusable)

| File | Why |
|---|---|
| `app/graph/sparql_client.py` | Generic SPARQL HTTP client |
| `app/llm/openai_client.py` | Generic LLM factory |
| `app/agent/state.py` | Generic state schema |
| `app/agent/prompts.py` | `RESPONSE_FORMATTING_PROMPT` is domain-agnostic |
| `app/utils/logging.py` | Generic logging |
| `app/api/dependencies.py` | Generic DI |
| `app/main.py` | Only if you rename routes |
| `deployment/*` | Infrastructure is domain-agnostic |
| `data/load_data.py` | Only if graph URIs change |

---

## 16. Worked Example — Movie Knowledge Graph

Here's a sketch of what a Movie domain conversion would look like:

### `data/ontology.ttl` (abbreviated)

```turtle
@prefix movie: <http://example.org/movies/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

movie:movies-ontology a owl:Ontology ;
    rdfs:label "Movie Knowledge Graph Ontology" .

movie:Film a owl:Class ;
    rdfs:label "Film" .

movie:Person a owl:Class ;
    rdfs:label "Person" .

movie:Genre a owl:Class ;
    rdfs:label "Genre" .

movie:title a owl:DatatypeProperty ;
    rdfs:domain movie:Film ;
    rdfs:range xsd:string .

movie:releaseYear a owl:DatatypeProperty ;
    rdfs:domain movie:Film ;
    rdfs:range xsd:integer .

movie:directedBy a owl:ObjectProperty ;
    rdfs:domain movie:Film ;
    rdfs:range movie:Person ;
    owl:inverseOf movie:directed .

movie:actedIn a owl:ObjectProperty ;
    rdfs:domain movie:Person ;
    rdfs:range movie:Film .

movie:hasGenre a owl:ObjectProperty ;
    rdfs:domain movie:Film ;
    rdfs:range movie:Genre .
```

### `app/config.py` changes

```python
DEFAULT_NAMESPACE: str = "http://example.org/movies/"
ONTOLOGY_GRAPH_URI: str = "http://example.org/movies/ontology"
DATA_GRAPH_URI: str = "http://example.org/movies/data"
```

### `app/llm/query_generator.py` — prompt excerpt

```
CLASSES:
- movie:Film — a movie/film
- movie:Person — an actor, director, or crew member
- movie:Genre — a genre category (Action, Drama, Comedy, etc.)

PROPERTIES:
- movie:title (string) — film title
- movie:releaseYear (integer) — year of release
- movie:rating (float) — IMDb-style rating (0.0-10.0)
- movie:directedBy (Film → Person) — the director
- movie:actedIn (Person → Film) — actor appeared in film
- movie:hasGenre (Film → Genre) — genre classification
```

---

## 17. How to Ingest New Ontology and Data Graphs

### Replacing Existing Graphs

To **replace** the current ontology or data with new versions:

```bash
# Replace ontology graph (PUT = full replace)
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/new_ontology.ttl \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/ontology"

# Replace data graph
curl -X PUT \
  -H "Content-Type: text/turtle" \
  --data-binary @data/new_data.ttl \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/data"
```

`PUT` is **idempotent** — it completely replaces the graph contents.

### Appending to Existing Graphs

To **add** new triples without deleting existing ones:

```bash
# Append to data graph (POST = merge/add)
curl -X POST \
  -H "Content-Type: text/turtle" \
  --data-binary @data/additional_data.ttl \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/data"
```

`POST` **merges** the new triples into the existing graph.

### Deleting a Named Graph

```bash
curl -X DELETE \
  "http://localhost:3030/foaf/data?graph=http://example.org/foaf-poc/data"
```

### Using the `data/load_data.py` Script

The existing script handles ontology + data loading automatically:

```bash
python data/load_data.py
```

If you want to load a different ontology or data file, edit the file paths in `load_data.py`:

```python
ONTOLOGY_FILE = "data/ontology.ttl"     # ← change to your file
DATA_FILE = "data/sample_data.ttl"       # ← change to your file
ONTOLOGY_GRAPH = "http://example.org/foaf-poc/ontology"  # ← from config
DATA_GRAPH = "http://example.org/foaf-poc/data"          # ← from config
```

### Using SPARQL UPDATE to Insert Individual Triples

You can also insert data programmatically via SPARQL:

```sparql
PREFIX movie: <http://example.org/movies/>

INSERT DATA {
    GRAPH <http://example.org/movies/data> {
        movie:film001 a movie:Film ;
            movie:title "The Matrix" ;
            movie:releaseYear 1999 .
    }
}
```

Send this via the SPARQL update endpoint:

```bash
curl -X POST \
  -H "Content-Type: application/sparql-update" \
  --data 'INSERT DATA { GRAPH <http://example.org/movies/data> { ... } }' \
  "http://localhost:3030/movies/update"
```

### Verifying After Ingestion

```sparql
-- Count triples in each graph
SELECT ?graph (COUNT(*) AS ?triples)
WHERE { GRAPH ?graph { ?s ?p ?o } }
GROUP BY ?graph

-- List all named graphs
SELECT DISTINCT ?graph
WHERE { GRAPH ?graph { ?s ?p ?o } }
```

### Multiple Knowledge Graphs in Same Fuseki

You can run **multiple datasets** in Fuseki simultaneously:

```bash
# Start Fuseki with config file that defines multiple datasets
./fuseki-server --config=multi-dataset-config.ttl
```

Or start with multiple in-memory datasets:

```bash
./fuseki-server --mem /foaf --mem /movies --mem /medical
```

Each dataset gets its own endpoints:
- `http://localhost:3030/foaf/query`
- `http://localhost:3030/movies/query`
- `http://localhost:3030/medical/query`

To switch the application between datasets, just change `FUSEKI_ENDPOINT` in `.env`.

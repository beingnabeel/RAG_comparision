"""Load ontology and sample data into separate named graphs in Fuseki.

Usage:
    python data/load_data.py

This script loads:
  1. data/ontology.ttl    → named graph <http://example.org/foaf-poc/ontology>
  2. data/sample_data.ttl → named graph <http://example.org/foaf-poc/data>
"""

import os
import sys
import requests

# Defaults — override with env vars if needed
FUSEKI_ENDPOINT = os.environ.get("FUSEKI_ENDPOINT", "http://localhost:3030/foaf")
DATA_ENDPOINT = f"{FUSEKI_ENDPOINT}/data"

ONTOLOGY_GRAPH_URI = "http://example.org/foaf-poc/ontology"
DATA_GRAPH_URI = "http://example.org/foaf-poc/data"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_file_into_graph(file_path: str, graph_uri: str):
    """Load a Turtle file into a specific named graph via Fuseki's Graph Store Protocol."""
    if not os.path.exists(file_path):
        print(f"  ERROR: File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "rb") as f:
        data = f.read()

    url = f"{DATA_ENDPOINT}?graph={graph_uri}"
    print(f"  Loading {os.path.basename(file_path)} → <{graph_uri}>")
    print(f"  PUT {url}  ({len(data)} bytes)")

    resp = requests.put(
        url,
        data=data,
        headers={"Content-Type": "text/turtle"},
    )

    if resp.status_code in (200, 201, 204):
        print(f"  SUCCESS (HTTP {resp.status_code})")
    else:
        print(f"  FAILED  (HTTP {resp.status_code}): {resp.text}")
        sys.exit(1)


def verify_graphs():
    """Verify both graphs were loaded by counting triples."""
    query_url = f"{FUSEKI_ENDPOINT}/query"

    for label, graph_uri in [("Ontology", ONTOLOGY_GRAPH_URI), ("Data", DATA_GRAPH_URI)]:
        query = f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
        resp = requests.get(query_url, params={"query": query}, headers={"Accept": "application/sparql-results+json"})
        if resp.status_code == 200:
            count = resp.json()["results"]["bindings"][0]["count"]["value"]
            print(f"  {label} graph: {count} triples")
        else:
            print(f"  {label} graph: verification failed (HTTP {resp.status_code})")


def main():
    print("=" * 60)
    print("FoaF Graph RAG — Data Loader")
    print("=" * 60)
    print(f"Fuseki endpoint: {FUSEKI_ENDPOINT}")
    print()

    # 1. Check Fuseki is up
    print("[1/4] Checking Fuseki connectivity...")
    try:
        resp = requests.get(f"{FUSEKI_ENDPOINT}/query", params={"query": "ASK { ?s ?p ?o }"}, headers={"Accept": "application/sparql-results+json"})
        if resp.status_code == 200:
            print("  Fuseki is reachable.")
        else:
            print(f"  WARNING: Fuseki responded with HTTP {resp.status_code}")
    except requests.ConnectionError:
        print(f"  ERROR: Cannot connect to Fuseki at {FUSEKI_ENDPOINT}")
        print("  Make sure Fuseki is running. See SETUP_GUIDE.md for instructions.")
        sys.exit(1)

    # 2. Load ontology
    print()
    print("[2/4] Loading ontology (blueprint) into ontology graph...")
    ontology_path = os.path.join(SCRIPT_DIR, "ontology.ttl")
    load_file_into_graph(ontology_path, ONTOLOGY_GRAPH_URI)

    # 3. Load sample data
    print()
    print("[3/4] Loading sample data (100 persons) into data graph...")
    data_path = os.path.join(SCRIPT_DIR, "sample_data.ttl")
    if not os.path.exists(data_path):
        print("  sample_data.ttl not found — generating it first...")
        from generate_sample_data import generate_data
        generate_data()
    load_file_into_graph(data_path, DATA_GRAPH_URI)

    # 4. Verify
    print()
    print("[4/4] Verifying loaded graphs...")
    verify_graphs()

    print()
    print("All done! Your knowledge graph is ready.")
    print(f"  Ontology graph: <{ONTOLOGY_GRAPH_URI}>")
    print(f"  Data graph:     <{DATA_GRAPH_URI}>")
    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Interactive CLI chatbot for the FoaF Graph RAG knowledge graph.

Usage:
    python cli.py

Requires Fuseki to be running at the endpoint configured in .env
"""

import sys
import os
import json
import time
import asyncio
import textwrap

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.graph.sparql_client import sparql_client
from app.llm.openai_client import is_llm_configured
from app.agent.graph_agent import run_agent
from app.agent.tools import (
    search_person_by_name,
    get_person_relationships,
    add_person_to_graph,
    add_relationship_to_graph,
    get_ontology_schema,
    execute_sparql_query,
)
from app.graph.query_builder import get_all_persons, get_person_details
from app.utils.logging import setup_logging

# ── Colors ───────────────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def c(text, color):
    return f"{color}{text}{RESET}"


# ── Helpers ──────────────────────────────────────────────────────────────────

def print_banner():
    print()
    print(c("=" * 60, CYAN))
    print(c("  FoaF Graph RAG — Interactive CLI Chatbot", BOLD + CYAN))
    print(c("=" * 60, CYAN))
    print()
    print(f"  Graph DB : {settings.FUSEKI_ENDPOINT}")
    print(f"  LLM      : {settings.LLM_MODEL}")
    print()


def print_help():
    help_text = f"""
{c("Available Commands:", BOLD + YELLOW)}

  {c("Just type a question", GREEN)}  — Ask anything in natural language
      Examples:  Who is person001?
                 Who are the friends of Mark Johnson?
                 How many people work in Technology?

  {c("/persons", GREEN)}  [limit]      — List all persons (default: 10)
  {c("/person", GREEN)}   <id>         — View details of a specific person (e.g. person001)
  {c("/search", GREEN)}   <name>       — Search persons by name
  {c("/friends", GREEN)}  <name>       — Show relationships for a person
  {c("/add-person", GREEN)}             — Add a new person (interactive)
  {c("/add-rel", GREEN)}                — Add a relationship (interactive)
  {c("/stats", GREEN)}                  — Show graph statistics
  {c("/schema", GREEN)}                 — Show ontology schema (blueprint)
  {c("/sparql", GREEN)}   <query>      — Execute raw SPARQL query
  {c("/help", GREEN)}                   — Show this help
  {c("/quit", GREEN)}                   — Exit

"""
    print(help_text)


def print_divider():
    print(c("─" * 60, DIM))


def format_results_table(results, max_rows=20):
    """Format SPARQL result bindings as a simple table."""
    if not results:
        print(c("  No results found.", YELLOW))
        return

    # Get all keys
    keys = []
    for row in results:
        for k in row:
            if k not in keys:
                keys.append(k)

    # Extract values
    rows = []
    for row in results[:max_rows]:
        vals = []
        for k in keys:
            v = row.get(k, {})
            if isinstance(v, dict):
                val = v.get("value", "")
            else:
                val = str(v)
            # Shorten URIs
            if val.startswith("http://"):
                val = val.split("/")[-1].split("#")[-1]
            if val.startswith("mailto:"):
                val = val.replace("mailto:", "")
            vals.append(val)
        rows.append(vals)

    # Calculate column widths
    widths = [len(k) for k in keys]
    for row in rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(v))
    widths = [min(w, 35) for w in widths]

    # Print header
    header = " | ".join(k.ljust(widths[i]) for i, k in enumerate(keys))
    print(f"  {c(header, BOLD)}")
    print(f"  {'-+-'.join('-' * w for w in widths)}")

    # Print rows
    for row in rows:
        line = " | ".join(str(v)[:widths[i]].ljust(widths[i]) for i, v in enumerate(row))
        print(f"  {line}")

    if len(results) > max_rows:
        print(c(f"\n  ... and {len(results) - max_rows} more rows", DIM))

    print(f"\n  {c(f'Total: {len(results)} result(s)', DIM)}")


# ── Command Handlers ─────────────────────────────────────────────────────────

def cmd_persons(args):
    """List persons in the graph."""
    limit = 10
    if args.strip():
        try:
            limit = int(args.strip())
        except ValueError:
            pass

    query = get_all_persons(limit)
    results = sparql_client.execute_select(query)
    print()
    format_results_table(results)


def cmd_person(args):
    """Show details for a specific person."""
    person_id = args.strip()
    if not person_id:
        print(c("  Usage: /person <id>  (e.g. /person person001)", RED))
        return

    if not person_id.startswith("http"):
        person_uri = f"http://example.org/foaf-poc/{person_id}"
    else:
        person_uri = person_id

    query = get_person_details(person_uri)
    results = sparql_client.execute_select(query)

    if not results:
        print(c(f"  Person '{person_id}' not found.", RED))
        return

    print()
    print(c(f"  Details for {person_id}:", BOLD))
    print()
    for row in results:
        pred = row["predicate"]["value"]
        val = row["value"]["value"]
        key = pred.split("/")[-1].split("#")[-1]
        # Shorten mailto:
        if val.startswith("mailto:"):
            val = val.replace("mailto:", "")
        print(f"  {c(key.ljust(22), CYAN)} {val}")


def cmd_search(args):
    """Search persons by name."""
    name = args.strip()
    if not name:
        print(c("  Usage: /search <name>  (e.g. /search John)", RED))
        return

    result = search_person_by_name.invoke({"name": name})
    if result.get("success"):
        print()
        format_results_table(result["results"])
    else:
        print(c(f"  Error: {result.get('error')}", RED))


def cmd_friends(args):
    """Show relationships for a person."""
    name = args.strip()
    if not name:
        print(c("  Usage: /friends <name or URI>  (e.g. /friends Mark Johnson)", RED))
        return

    result = get_person_relationships.invoke({"person_name_or_uri": name})
    if result.get("success"):
        print()
        if result["results"]:
            format_results_table(result["results"])
        else:
            print(c("  No relationships found.", YELLOW))
    else:
        print(c(f"  Error: {result.get('error')}", RED))


def cmd_add_person(_args):
    """Interactive: add a new person."""
    print()
    print(c("  Add a New Person", BOLD + GREEN))
    print(c("  (Press Enter to skip optional fields)", DIM))
    print()

    name = input(f"  {c('Name (required):', CYAN)} ").strip()
    if not name:
        print(c("  Cancelled — name is required.", RED))
        return

    age = input(f"  {c('Age:', CYAN)} ").strip() or None
    gender = input(f"  {c('Gender (male/female/other):', CYAN)} ").strip() or None
    phone = input(f"  {c('Phone:', CYAN)} ").strip() or None
    email = input(f"  {c('Email:', CYAN)} ").strip() or None
    city = input(f"  {c('City:', CYAN)} ").strip() or None
    state = input(f"  {c('State:', CYAN)} ").strip() or None
    country = input(f"  {c('Country:', CYAN)} ").strip() or None
    job_title = input(f"  {c('Job Title:', CYAN)} ").strip() or None
    industry = input(f"  {c('Industry:', CYAN)} ").strip() or None

    params = {"name": name}
    if age:
        params["age"] = int(age)
    if gender:
        params["gender"] = gender
    if phone:
        params["phone"] = phone
    if email:
        params["email"] = email
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if country:
        params["country"] = country
    if job_title:
        params["job_title"] = job_title
    if industry:
        params["industry"] = industry

    print()
    print(c("  Adding person...", DIM))
    result = add_person_to_graph.invoke(params)

    if result.get("success"):
        print(c(f"  ✓ {result['message']}", GREEN))
        print(c(f"    URI: {result['person_uri']}", DIM))
    else:
        print(c(f"  ✗ Error: {result.get('error')}", RED))


def cmd_add_rel(_args):
    """Interactive: add a relationship."""
    print()
    print(c("  Add a Relationship", BOLD + GREEN))
    print()
    print(c("  Relationship types: friendOf, spouseOf, parentOf, childOf,", DIM))
    print(c("                      siblingOf, colleagueOf, neighborOf, knows", DIM))
    print()

    subject = input(f"  {c('Person 1 (name or URI):', CYAN)} ").strip()
    if not subject:
        print(c("  Cancelled.", RED))
        return

    predicate = input(f"  {c('Relationship type:', CYAN)} ").strip()
    if not predicate:
        print(c("  Cancelled.", RED))
        return

    obj = input(f"  {c('Person 2 (name or URI):', CYAN)} ").strip()
    if not obj:
        print(c("  Cancelled.", RED))
        return

    print()
    print(c("  Adding relationship...", DIM))
    result = add_relationship_to_graph.invoke({
        "subject_name_or_uri": subject,
        "predicate": predicate,
        "object_name_or_uri": obj,
    })

    if result.get("success"):
        print(c(f"  ✓ {result['message']}", GREEN))
    else:
        print(c(f"  ✗ Error: {result.get('error')}", RED))


def cmd_stats(_args):
    """Show graph statistics."""
    stats = sparql_client.get_graph_stats()
    print()
    print(c("  Graph Statistics:", BOLD))
    print(f"  {c('Persons:', CYAN).ljust(35)}  {stats['persons']}")
    print(f"  {c('Relationships:', CYAN).ljust(35)}  {stats['relationships']}")
    print(f"  {c('Data triples:', CYAN).ljust(35)}  {stats['data_triples']}")
    print(f"  {c('Ontology triples:', CYAN).ljust(35)}  {stats['ontology_triples']}")
    print(f"  {c('Total triples:', CYAN).ljust(35)}  {stats['total_triples']}")


def cmd_schema(_args):
    """Show the ontology schema."""
    result = get_ontology_schema.invoke({})
    if not result.get("success"):
        print(c(f"  Error: {result.get('error')}", RED))
        return

    print()
    print(c("  Ontology Classes:", BOLD))
    for cls in result["classes"]:
        label = cls.get("label", {}).get("value", "")
        uri = cls.get("class", {}).get("value", "").split("/")[-1].split("#")[-1]
        comment = cls.get("comment", {}).get("value", "")
        line = f"  • {c(uri, GREEN)}"
        if label:
            line += f" ({label})"
        if comment:
            line += f" — {comment}"
        print(line)

    print()
    print(c("  Ontology Properties:", BOLD))
    for prop in result["properties"]:
        label = prop.get("label", {}).get("value", "")
        uri = prop.get("property", {}).get("value", "").split("/")[-1].split("#")[-1]
        domain = prop.get("domain", {}).get("value", "").split("/")[-1].split("#")[-1] if "domain" in prop else ""
        rng = prop.get("range", {}).get("value", "").split("/")[-1].split("#")[-1] if "range" in prop else ""
        line = f"  • {c(uri.ljust(22), GREEN)}"
        if label:
            line += f" {label}"
        if domain or rng:
            line += f"  {c(f'({domain} → {rng})', DIM)}"
        print(line)

    cls_count = result["class_count"]
    prop_count = result["property_count"]
    print(f"\n  {c(f'{cls_count} classes, {prop_count} properties', DIM)}")


def cmd_sparql(args):
    """Execute a raw SPARQL query."""
    query = args.strip()
    if not query:
        print(c("  Usage: /sparql SELECT * WHERE { ?s ?p ?o } LIMIT 5", RED))
        return

    result = execute_sparql_query.invoke({"query": query})
    if result.get("success"):
        print()
        if "results" in result:
            format_results_table(result["results"])
        elif "answer" in result:
            print(c(f"  Answer: {result['answer']}", GREEN))
        elif "message" in result:
            print(c(f"  {result['message']}", GREEN))
    else:
        print(c(f"  Error: {result.get('error')}", RED))


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
        # Print the natural language response
        response = result.get("response", "No response generated.")
        print()
        for line in response.split("\n"):
            print(f"  {c('│', CYAN)} {line}")
        print()

        # Show metadata
        intent = result.get("intent", "")
        sparql = result.get("sparql_query", "")
        print(c(f"  Intent: {intent}  |  Time: {elapsed:.1f}s  |  Results: {len(result.get('results', []))}", DIM))

        if sparql:
            # Show first 2 lines of SPARQL
            sparql_lines = sparql.strip().split("\n")
            body_lines = [l for l in sparql_lines if not l.strip().upper().startswith("PREFIX")]
            preview = body_lines[0].strip() if body_lines else sparql_lines[0].strip()
            print(c(f"  SPARQL: {preview[:70]}...", DIM))
    else:
        print(c(f"  Error: {result.get('response', 'Unknown error')}", RED))


# ── Command Router ───────────────────────────────────────────────────────────

COMMANDS = {
    "/persons": cmd_persons,
    "/person": cmd_person,
    "/search": cmd_search,
    "/friends": cmd_friends,
    "/add-person": cmd_add_person,
    "/add-rel": cmd_add_rel,
    "/stats": cmd_stats,
    "/schema": cmd_schema,
    "/sparql": cmd_sparql,
    "/help": lambda _: print_help(),
}


# ── Main Loop ────────────────────────────────────────────────────────────────

def main():
    setup_logging()
    print_banner()

    # Pre-flight checks
    print(c("  Checking connections...", DIM))
    if not sparql_client.test_connection():
        print(c("  ✗ Cannot connect to Fuseki at " + settings.FUSEKI_ENDPOINT, RED))
        print(c("    Make sure Fuseki is running. See SETUP_GUIDE.md", RED))
        sys.exit(1)
    print(c("  ✓ Fuseki connected", GREEN))

    if not is_llm_configured():
        print(c("  ✗ LLM API key not configured in .env", RED))
        sys.exit(1)
    print(c(f"  ✓ LLM configured ({settings.LLM_MODEL})", GREEN))

    stats = sparql_client.get_graph_stats()
    print(c(f"  ✓ Graph loaded: {stats['persons']} persons, {stats['total_triples']} triples", GREEN))
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

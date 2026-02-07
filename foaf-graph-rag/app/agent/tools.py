"""Agent tools for interacting with the FoaF knowledge graph."""

from langchain_core.tools import tool
from typing import Dict, Any
from app.graph.sparql_client import sparql_client
from app.graph import query_builder
from app.graph.validator import validate_person_data, validate_relationship, sanitize_sparql_string
from app.utils.helpers import resolve_predicate, get_timestamp
from app.utils.logging import get_logger

logger = get_logger(__name__)


@tool
def execute_sparql_query(query: str) -> Dict[str, Any]:
    """Execute a SPARQL query against the FoaF knowledge graph.

    Args:
        query: Valid SPARQL query string (SELECT, ASK, INSERT, DELETE)

    Returns:
        Dictionary with query results or error message
    """
    try:
        # Strip PREFIX declarations to find the actual query type
        import re
        body = re.sub(r'(?i)^(\s*PREFIX\s+\S+\s+<[^>]+>\s*\.?\s*)+', '', query).strip().upper()

        if body.startswith("SELECT"):
            results = sparql_client.execute_select(query)
            return {"success": True, "results": results, "count": len(results)}
        elif body.startswith("ASK"):
            result = sparql_client.execute_ask(query)
            return {"success": True, "answer": result}
        elif body.startswith(("INSERT", "DELETE")):
            sparql_client.execute_update(query)
            return {"success": True, "message": "Update executed successfully"}
        else:
            return {"success": False, "error": f"Unsupported query type. Query body starts with: {body[:30]}..."}
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def search_person_by_name(name: str) -> Dict[str, Any]:
    """Search for a person by name in the FoaF knowledge graph.

    Args:
        name: Person's name (or partial name) to search for

    Returns:
        Dictionary with matching persons or error
    """
    try:
        safe_name = sanitize_sparql_string(name)
        query = query_builder.search_person_by_name(safe_name)
        results = sparql_client.execute_select(query)
        return {"success": True, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Person search failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def get_person_relationships(person_name_or_uri: str) -> Dict[str, Any]:
    """Get all relationships for a person. Accepts a name or URI.

    Args:
        person_name_or_uri: Person's name or full URI

    Returns:
        Dictionary with all relationships for the person
    """
    try:
        # If it's a name, search for the person first
        if not person_name_or_uri.startswith("http"):
            safe_name = sanitize_sparql_string(person_name_or_uri)
            search_query = query_builder.search_person_by_name(safe_name)
            search_results = sparql_client.execute_select(search_query)
            if not search_results:
                return {"success": False, "error": f"No person found with name '{person_name_or_uri}'"}
            person_uri = search_results[0]["person"]["value"]
        else:
            person_uri = person_name_or_uri

        query = query_builder.get_person_relationships(person_uri)
        results = sparql_client.execute_select(query)
        return {"success": True, "person_uri": person_uri, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Relationship query failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def add_person_to_graph(
    name: str,
    age: int = None,
    gender: str = None,
    phone: str = None,
    email: str = None,
    address: str = None,
    city: str = None,
    state: str = None,
    postal_code: str = None,
    country: str = None,
    job_title: str = None,
    occupation: str = None,
    industry: str = None,
) -> Dict[str, Any]:
    """Add a new person to the FoaF knowledge graph.

    Args:
        name: Full name of the person (required)
        age: Age of the person
        gender: Gender (male, female, other, non-binary)
        phone: Phone number
        email: Email address
        address: Full address
        city: City
        state: State/Province
        postal_code: Postal code
        country: Country
        job_title: Job title
        occupation: Occupation description
        industry: Industry sector

    Returns:
        Dictionary with success status and person URI
    """
    try:
        person_data = {"name": name, "age": age, "gender": gender}
        is_valid, error_msg = validate_person_data(person_data)
        if not is_valid:
            return {"success": False, "error": error_msg}

        # Get next person ID
        count_results = sparql_client.execute_select(query_builder.get_next_person_id())
        count = int(count_results[0]["count"]["value"]) if count_results else 0
        person_id = f"person{count + 1:03d}"
        person_uri = f"http://example.org/foaf-poc/{person_id}"

        # Build triples
        triples = []
        triples.append(f'<{person_uri}> a custom:Person')
        triples.append(f'<{person_uri}> foaf:name "{sanitize_sparql_string(name)}"')

        if age is not None:
            triples.append(f'<{person_uri}> foaf:age {int(age)}')
        if gender:
            triples.append(f'<{person_uri}> foaf:gender "{sanitize_sparql_string(gender)}"')
        if phone:
            triples.append(f'<{person_uri}> foaf:phone "{sanitize_sparql_string(phone)}"')
        if email:
            triples.append(f'<{person_uri}> foaf:mbox <mailto:{sanitize_sparql_string(email)}>')
        if address:
            triples.append(f'<{person_uri}> schema:address "{sanitize_sparql_string(address)}"')
        if city:
            triples.append(f'<{person_uri}> schema:addressLocality "{sanitize_sparql_string(city)}"')
        if state:
            triples.append(f'<{person_uri}> schema:addressRegion "{sanitize_sparql_string(state)}"')
        if postal_code:
            triples.append(f'<{person_uri}> schema:postalCode "{sanitize_sparql_string(postal_code)}"')
        if country:
            triples.append(f'<{person_uri}> schema:addressCountry "{sanitize_sparql_string(country)}"')
        if job_title:
            triples.append(f'<{person_uri}> schema:jobTitle "{sanitize_sparql_string(job_title)}"')
        if occupation:
            triples.append(f'<{person_uri}> custom:occupation "{sanitize_sparql_string(occupation)}"')
        if industry:
            triples.append(f'<{person_uri}> custom:industry "{sanitize_sparql_string(industry)}"')

        timestamp = get_timestamp()
        triples.append(f'<{person_uri}> custom:createdAt "{timestamp}"^^xsd:dateTime')

        triple_str = " .\n    ".join(triples) + " ."
        insert_query = query_builder.insert_person(person_uri, triple_str)
        sparql_client.execute_update(insert_query)

        return {"success": True, "person_uri": person_uri, "message": f"Person '{name}' added successfully"}
    except Exception as e:
        logger.error(f"Add person failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def add_relationship_to_graph(subject_name_or_uri: str, predicate: str, object_name_or_uri: str) -> Dict[str, Any]:
    """Add a relationship between two persons in the knowledge graph.

    Args:
        subject_name_or_uri: Name or URI of the first person
        predicate: Relationship type (friendOf, spouseOf, parentOf, childOf, siblingOf, colleagueOf, neighborOf, knows)
        object_name_or_uri: Name or URI of the second person

    Returns:
        Dictionary with success status
    """
    try:
        is_valid, error_msg = validate_relationship(predicate)
        if not is_valid:
            return {"success": False, "error": error_msg}

        # Resolve names to URIs if needed
        for label, value in [("subject", subject_name_or_uri), ("object", object_name_or_uri)]:
            if not value.startswith("http"):
                safe_name = sanitize_sparql_string(value)
                search_query = query_builder.search_person_by_name(safe_name)
                results = sparql_client.execute_select(search_query)
                if not results:
                    return {"success": False, "error": f"No person found with name '{value}'"}
                if label == "subject":
                    subject_uri = results[0]["person"]["value"]
                else:
                    object_uri = results[0]["person"]["value"]
            else:
                if label == "subject":
                    subject_uri = value
                else:
                    object_uri = value

        predicate_uri = resolve_predicate(predicate)
        insert_query = query_builder.insert_relationship(subject_uri, predicate_uri, object_uri)
        sparql_client.execute_update(insert_query)

        return {
            "success": True,
            "message": f"Relationship '{predicate}' added between {subject_name_or_uri} and {object_name_or_uri}",
        }
    except Exception as e:
        logger.error(f"Add relationship failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def get_ontology_schema() -> Dict[str, Any]:
    """Get the ontology schema (blueprint) that defines what classes and properties exist in the knowledge graph.

    Returns:
        Dictionary with classes and properties from the ontology graph
    """
    try:
        classes_query = query_builder.get_ontology_classes()
        classes = sparql_client.execute_select(classes_query)

        props_query = query_builder.get_ontology_properties()
        properties = sparql_client.execute_select(props_query)

        return {
            "success": True,
            "classes": classes,
            "properties": properties,
            "class_count": len(classes),
            "property_count": len(properties),
        }
    except Exception as e:
        logger.error(f"Ontology query failed: {e}")
        return {"success": False, "error": str(e)}


# Collect all tools for the agent
ALL_TOOLS = [
    execute_sparql_query,
    search_person_by_name,
    get_person_relationships,
    add_person_to_graph,
    add_relationship_to_graph,
    get_ontology_schema,
]

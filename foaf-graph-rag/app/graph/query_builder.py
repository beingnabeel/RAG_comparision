"""SPARQL query templates for common operations.

Architecture: Two named graphs inside the same Fuseki dataset.
  - ONTOLOGY_GRAPH  holds the schema/blueprint (classes, properties, constraints).
  - DATA_GRAPH      holds the actual person instances and relationships.
All SELECT queries read from the data graph; INSERT queries write into it.
A separate helper lets the agent introspect the ontology graph.
"""

from app.config import settings

ONTOLOGY_GRAPH = settings.ONTOLOGY_GRAPH_URI
DATA_GRAPH = settings.DATA_GRAPH_URI

PREFIXES = """
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rel: <http://purl.org/vocab/relationship/>
PREFIX schema: <http://schema.org/>
PREFIX custom: <http://example.org/foaf-poc/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
"""


# ── Data-graph queries ───────────────────────────────────────────────────────

def search_person_by_name(name: str) -> str:
    return f"""{PREFIXES}
SELECT ?person ?name ?age ?phone ?email ?jobTitle ?city
WHERE {{
    GRAPH <{DATA_GRAPH}> {{
        ?person a custom:Person ;
                foaf:name ?name .
        OPTIONAL {{ ?person foaf:age ?age }}
        OPTIONAL {{ ?person foaf:phone ?phone }}
        OPTIONAL {{ ?person foaf:mbox ?email }}
        OPTIONAL {{ ?person schema:jobTitle ?jobTitle }}
        OPTIONAL {{ ?person schema:addressLocality ?city }}
        FILTER (CONTAINS(LCASE(?name), LCASE("{name}")))
    }}
}}
LIMIT 10
"""


def get_person_details(person_uri: str) -> str:
    return f"""{PREFIXES}
SELECT ?predicate ?value
WHERE {{
    GRAPH <{DATA_GRAPH}> {{
        <{person_uri}> ?predicate ?value .
    }}
}}
"""


def get_person_relationships(person_uri: str) -> str:
    return f"""{PREFIXES}
SELECT ?relationship ?relatedPerson ?relatedName
WHERE {{
    GRAPH <{DATA_GRAPH}> {{
        {{
            <{person_uri}> ?relationship ?relatedPerson .
            ?relatedPerson a custom:Person .
            ?relatedPerson foaf:name ?relatedName .
            FILTER (
                STRSTARTS(STR(?relationship), "http://purl.org/vocab/relationship/") ||
                ?relationship = foaf:knows ||
                ?relationship = custom:colleagueOf ||
                ?relationship = custom:neighborOf
            )
        }}
        UNION
        {{
            ?relatedPerson ?relationship <{person_uri}> .
            ?relatedPerson a custom:Person .
            ?relatedPerson foaf:name ?relatedName .
            FILTER (
                STRSTARTS(STR(?relationship), "http://purl.org/vocab/relationship/") ||
                ?relationship = foaf:knows ||
                ?relationship = custom:colleagueOf ||
                ?relationship = custom:neighborOf
            )
        }}
    }}
}}
"""


def get_next_person_id() -> str:
    return f"""{PREFIXES}
SELECT (COUNT(?p) as ?count)
WHERE {{
    GRAPH <{DATA_GRAPH}> {{ ?p a custom:Person }}
}}
"""


def insert_person(person_uri: str, triples: str) -> str:
    return f"""{PREFIXES}
INSERT DATA {{
    GRAPH <{DATA_GRAPH}> {{
        {triples}
    }}
}}
"""


def insert_relationship(subject_uri: str, predicate_uri: str, object_uri: str) -> str:
    return f"""{PREFIXES}
INSERT DATA {{
    GRAPH <{DATA_GRAPH}> {{
        <{subject_uri}> <{predicate_uri}> <{object_uri}> .
    }}
}}
"""


def get_all_persons(limit: int = 100) -> str:
    return f"""{PREFIXES}
SELECT ?person ?name ?age ?jobTitle ?city
WHERE {{
    GRAPH <{DATA_GRAPH}> {{
        ?person a custom:Person ;
                foaf:name ?name .
        OPTIONAL {{ ?person foaf:age ?age }}
        OPTIONAL {{ ?person schema:jobTitle ?jobTitle }}
        OPTIONAL {{ ?person schema:addressLocality ?city }}
    }}
}}
ORDER BY ?name
LIMIT {limit}
"""


# ── Ontology-graph queries ───────────────────────────────────────────────────

def get_ontology_classes() -> str:
    """List all classes defined in the ontology graph (OWL classes)."""
    return f"""{PREFIXES}
SELECT ?class ?label ?comment
WHERE {{
    GRAPH <{ONTOLOGY_GRAPH}> {{
        ?class a owl:Class .
        OPTIONAL {{ ?class rdfs:label ?label }}
        OPTIONAL {{ ?class rdfs:comment ?comment }}
    }}
}}
"""


def get_ontology_properties() -> str:
    """List all properties defined in the ontology graph (OWL object & datatype properties)."""
    return f"""{PREFIXES}
SELECT ?property ?type ?label ?domain ?range
WHERE {{
    GRAPH <{ONTOLOGY_GRAPH}> {{
        VALUES ?type {{ owl:ObjectProperty owl:DatatypeProperty }}
        ?property a ?type .
        OPTIONAL {{ ?property rdfs:label ?label }}
        OPTIONAL {{ ?property rdfs:domain ?domain }}
        OPTIONAL {{ ?property rdfs:range ?range }}
    }}
}}
ORDER BY ?type ?property
"""


def get_full_ontology() -> str:
    """Return every triple in the ontology graph (for LLM context)."""
    return f"""{PREFIXES}
SELECT ?subject ?predicate ?object
WHERE {{
    GRAPH <{ONTOLOGY_GRAPH}> {{
        ?subject ?predicate ?object .
    }}
}}
"""

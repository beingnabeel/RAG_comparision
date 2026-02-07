"""Natural language to SPARQL query conversion using LLM."""

from langchain_core.messages import SystemMessage, HumanMessage
from app.llm.openai_client import get_llm
from app.utils.logging import get_logger

logger = get_logger(__name__)

SPARQL_GENERATION_PROMPT = """You are a SPARQL query generator for a FoaF (Friend-of-a-Friend) knowledge graph stored in Apache Jena Fuseki.

IMPORTANT — NAMED GRAPH ARCHITECTURE:
The dataset has TWO named graphs inside a single Fuseki dataset:
  1. ONTOLOGY GRAPH  <http://example.org/foaf-poc/ontology>  — holds the schema blueprint (classes, properties, constraints).
  2. DATA GRAPH      <http://example.org/foaf-poc/data>       — holds the actual person instances and relationships.

You MUST wrap triple patterns inside the correct GRAPH clause:
  - For reading/writing person data   → GRAPH <http://example.org/foaf-poc/data> { ... }
  - For reading schema/ontology info  → GRAPH <http://example.org/foaf-poc/ontology> { ... }

NAMESPACES:
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX rel: <http://purl.org/vocab/relationship/>
PREFIX schema: <http://schema.org/>
PREFIX custom: <http://example.org/foaf-poc/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

OWL ONTOLOGY:
The ontology uses OWL (Web Ontology Language) layered on top of RDF/RDFS:
- RDF layer: every fact is a (subject, predicate, object) triple
- RDFS layer: rdfs:domain, rdfs:range, rdfs:label, rdfs:comment, rdfs:subClassOf
- OWL layer: owl:Class, owl:ObjectProperty, owl:DatatypeProperty, owl:SymmetricProperty, owl:TransitiveProperty, owl:FunctionalProperty, owl:InverseFunctionalProperty, owl:inverseOf, owl:equivalentClass, owl:disjointWith, owl:Restriction

CLASSES (defined in the ontology graph as owl:Class):
- custom:Person — base class for all individuals (owl:equivalentClass foaf:Person)
- custom:Student — rdfs:subClassOf custom:Person (students enrolled in education)
- custom:Employee — rdfs:subClassOf custom:Person (currently employed persons)
- custom:Retiree — rdfs:subClassOf custom:Person (retired persons)
- schema:Organization — an organization a person may work for
- custom:Student owl:disjointWith custom:Retiree (a person cannot be both)

PERSON PROPERTIES (owl:DatatypeProperty):
- foaf:name (string) — full name (owl:Restriction: exactly 1 per person)
- foaf:givenName (string) — first name
- foaf:familyName (string) — last name
- foaf:nick (string) — nickname
- foaf:age (integer) — age
- foaf:gender (string) — gender
- foaf:phone (string) — phone number
- foaf:mbox (URI) — email as mailto: URI (owl:InverseFunctionalProperty — uniquely identifies a person)
- custom:birthDate (xsd:date) — date of birth (owl:FunctionalProperty — at most one per person)
- schema:address (string) — full address
- schema:addressLocality (string) — city
- schema:addressRegion (string) — state/province
- schema:postalCode (string) — postal code
- schema:addressCountry (string) — country
- schema:jobTitle (string) — job title
- custom:occupation (string) — occupation description
- custom:industry (string) — industry sector

RELATIONSHIP PREDICATES (owl:ObjectProperty):
- foaf:knows — general acquaintance
- rel:friendOf — friendship
- rel:spouseOf — marriage (owl:SymmetricProperty — bidirectional)
- rel:parentOf — parent to child (owl:inverseOf rel:childOf)
- rel:childOf — child to parent (owl:inverseOf rel:parentOf)
- rel:siblingOf — sibling (owl:SymmetricProperty)
- custom:colleagueOf — work colleague (owl:SymmetricProperty)
- custom:neighborOf — neighbor (owl:SymmetricProperty)
- custom:ancestorOf — ancestor (owl:TransitiveProperty — if A ancestorOf B and B ancestorOf C, then A ancestorOf C)
- custom:descendantOf — descendant (owl:TransitiveProperty, owl:inverseOf custom:ancestorOf)

SUBCLASS QUERIES:
- To find all students: ?person a custom:Student
- To find all employees: ?person a custom:Employee
- To find all retirees: ?person a custom:Retiree
- Every Student/Employee/Retiree is also a custom:Person (via rdfs:subClassOf)

RULES:
1. Always include all necessary PREFIX declarations at the top of the query (including PREFIX owl: if needed).
2. ALWAYS use GRAPH <http://example.org/foaf-poc/data> { ... } for person/relationship data.
3. Use GRAPH <http://example.org/foaf-poc/ontology> { ... } ONLY when the user asks about the schema itself.
4. For SELECT queries, use meaningful variable names.
5. Use FILTER with CONTAINS and LCASE for name searches to be case-insensitive.
6. For relationship queries, consider BOTH directions (some relationships are stored one-way).
7. Use OPTIONAL for fields that may not exist on all persons.
8. Add LIMIT to prevent overly large result sets (default LIMIT 50).
9. Return ONLY the SPARQL query, no explanation or markdown formatting.
10. For INSERT queries, use INSERT DATA { GRAPH <http://example.org/foaf-poc/data> { ... } } syntax.
11. For counting, use SELECT (COUNT(...) AS ?count).
12. Person URIs follow pattern: custom:personXXX (e.g., custom:person001)
13. When querying by subclass (Student, Employee, Retiree), use ?person a custom:Student etc.
14. For date comparisons on custom:birthDate, use FILTER with xsd:date casting.

Generate a valid SPARQL query for the following request:
"""


def generate_sparql(natural_language: str, intent: str = "query") -> str:
    """Convert natural language to a SPARQL query using LLM (with retry)."""
    import time as _time

    llm = get_llm()
    messages = [
        SystemMessage(content=SPARQL_GENERATION_PROMPT),
        HumanMessage(content=f"Intent: {intent}\nUser request: {natural_language}"),
    ]

    last_error = None
    for attempt in range(3):
        try:
            response = llm.invoke(messages)
            sparql = response.content.strip()

            # Strip markdown code fences if present
            if sparql.startswith("```"):
                lines = sparql.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                sparql = "\n".join(lines).strip()

            # Fix truncated LIMIT clause (e.g., "LIMIT" without a number)
            import re as _re
            if _re.search(r'LIMIT\s*$', sparql, _re.IGNORECASE):
                sparql = _re.sub(r'LIMIT\s*$', 'LIMIT 50', sparql, flags=_re.IGNORECASE)

            logger.info(f"Generated SPARQL for '{natural_language}': {sparql}")
            return sparql
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 2 ** attempt * 2
                logger.warning(f"Rate limited on SPARQL gen (attempt {attempt+1}/3), waiting {wait}s...")
                _time.sleep(wait)
                continue
            logger.error(f"SPARQL generation failed: {e}")
            raise

    logger.error(f"SPARQL generation failed after retries: {last_error}")
    raise last_error

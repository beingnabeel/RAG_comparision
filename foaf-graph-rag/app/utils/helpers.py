from datetime import datetime, timezone


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def uri_to_id(uri: str) -> str:
    """Extract person ID from a URI like http://example.org/foaf-poc/person001"""
    return uri.split("/")[-1]


def id_to_uri(person_id: str, namespace: str = "http://example.org/foaf-poc/") -> str:
    """Convert a person ID to a full URI"""
    if person_id.startswith("http"):
        return person_id
    return f"{namespace}{person_id}"


RELATIONSHIP_MAP = {
    "friendOf": "http://purl.org/vocab/relationship/friendOf",
    "spouseOf": "http://purl.org/vocab/relationship/spouseOf",
    "parentOf": "http://purl.org/vocab/relationship/parentOf",
    "childOf": "http://purl.org/vocab/relationship/childOf",
    "siblingOf": "http://purl.org/vocab/relationship/siblingOf",
    "colleagueOf": "http://example.org/foaf-poc/colleagueOf",
    "neighborOf": "http://example.org/foaf-poc/neighborOf",
    "knows": "http://xmlns.com/foaf/0.1/knows",
}


def resolve_predicate(predicate: str) -> str:
    """Resolve a short predicate name to its full URI"""
    if predicate.startswith("http"):
        return predicate
    return RELATIONSHIP_MAP.get(predicate, predicate)

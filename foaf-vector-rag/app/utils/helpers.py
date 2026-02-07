from datetime import datetime, timezone


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def uri_to_id(uri: str) -> str:
    """Extract person ID from a URI like http://example.org/foaf-poc/person001"""
    return uri.split("/")[-1]


RELATIONSHIP_MAP = {
    "friendOf": "rel:friendOf",
    "spouseOf": "rel:spouseOf",
    "parentOf": "rel:parentOf",
    "childOf": "rel:childOf",
    "siblingOf": "rel:siblingOf",
    "colleagueOf": "custom:colleagueOf",
    "neighborOf": "custom:neighborOf",
    "knows": "foaf:knows",
    "ancestorOf": "custom:ancestorOf",
    "descendantOf": "custom:descendantOf",
}


RELATIONSHIP_LABELS = {
    "friendOf": "is friends with",
    "spouseOf": "is married to",
    "parentOf": "is the parent of",
    "childOf": "is the child of",
    "siblingOf": "is a sibling of",
    "colleagueOf": "is a colleague of",
    "neighborOf": "is a neighbor of",
    "knows": "knows",
    "ancestorOf": "is an ancestor of",
    "descendantOf": "is a descendant of",
}

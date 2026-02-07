"""RDF data validation utilities."""

from typing import Dict, Any, List, Optional
from app.utils.logging import get_logger

logger = get_logger(__name__)

VALID_RELATIONSHIPS = {
    "friendOf",
    "spouseOf",
    "parentOf",
    "childOf",
    "siblingOf",
    "colleagueOf",
    "neighborOf",
    "knows",
}


def validate_person_data(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate person data before insertion."""
    if not data.get("name"):
        return False, "Name is required"

    if data.get("age") is not None:
        try:
            age = int(data["age"])
            if age < 0 or age > 150:
                return False, "Age must be between 0 and 150"
        except (ValueError, TypeError):
            return False, "Age must be a valid integer"

    if data.get("gender") and data["gender"].lower() not in ("male", "female", "other", "non-binary"):
        return False, "Gender must be male, female, other, or non-binary"

    return True, None


def validate_relationship(predicate: str) -> tuple[bool, Optional[str]]:
    """Validate a relationship predicate."""
    if predicate not in VALID_RELATIONSHIPS:
        return False, f"Invalid relationship type '{predicate}'. Valid types: {', '.join(sorted(VALID_RELATIONSHIPS))}"
    return True, None


def sanitize_sparql_string(value: str) -> str:
    """Sanitize a string value for use in SPARQL queries to prevent injection."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

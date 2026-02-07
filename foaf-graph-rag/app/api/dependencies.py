"""Dependency injection for FastAPI."""

from app.graph.sparql_client import SPARQLClient, sparql_client


def get_sparql_client() -> SPARQLClient:
    return sparql_client

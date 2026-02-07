"""Tests for the graph interface layer."""

import pytest
from unittest.mock import patch, MagicMock
from app.graph.sparql_client import SPARQLClient
from app.graph.validator import validate_person_data, validate_relationship, sanitize_sparql_string
from app.graph.query_builder import (
    search_person_by_name,
    get_person_details,
    get_person_relationships,
    get_next_person_id,
    insert_relationship,
    insert_person,
    get_all_persons,
    get_ontology_classes,
    get_ontology_properties,
    DATA_GRAPH,
    ONTOLOGY_GRAPH,
)


# ── Validator tests ──────────────────────────────────────────────────────────

class TestValidator:
    def test_validate_person_valid(self):
        data = {"name": "John Smith", "age": 30, "gender": "male"}
        is_valid, error = validate_person_data(data)
        assert is_valid is True
        assert error is None

    def test_validate_person_no_name(self):
        data = {"age": 30}
        is_valid, error = validate_person_data(data)
        assert is_valid is False
        assert "Name" in error

    def test_validate_person_invalid_age(self):
        data = {"name": "John", "age": -5}
        is_valid, error = validate_person_data(data)
        assert is_valid is False
        assert "Age" in error

    def test_validate_person_age_too_high(self):
        data = {"name": "John", "age": 200}
        is_valid, error = validate_person_data(data)
        assert is_valid is False

    def test_validate_relationship_valid(self):
        is_valid, error = validate_relationship("friendOf")
        assert is_valid is True

    def test_validate_relationship_invalid(self):
        is_valid, error = validate_relationship("enemyOf")
        assert is_valid is False
        assert "Invalid" in error

    def test_sanitize_sparql_string(self):
        result = sanitize_sparql_string('John "O\'Brien')
        assert '\\"' in result
        assert "\\'" in result


# ── Query builder tests ──────────────────────────────────────────────────────

class TestQueryBuilder:
    def test_search_person_by_name_contains_filter(self):
        query = search_person_by_name("John")
        assert "FILTER" in query
        assert "CONTAINS" in query
        assert "John" in query

    def test_search_person_uses_data_graph(self):
        query = search_person_by_name("John")
        assert f"GRAPH <{DATA_GRAPH}>" in query

    def test_get_person_details_uses_uri(self):
        uri = "http://example.org/foaf-poc/person001"
        query = get_person_details(uri)
        assert uri in query
        assert f"GRAPH <{DATA_GRAPH}>" in query

    def test_get_person_relationships_bidirectional(self):
        uri = "http://example.org/foaf-poc/person001"
        query = get_person_relationships(uri)
        assert "UNION" in query
        assert f"GRAPH <{DATA_GRAPH}>" in query

    def test_get_all_persons_limit(self):
        query = get_all_persons(50)
        assert "LIMIT 50" in query
        assert f"GRAPH <{DATA_GRAPH}>" in query

    def test_insert_person_targets_data_graph(self):
        query = insert_person("http://example.org/foaf-poc/person101", '<http://example.org/foaf-poc/person101> a custom:Person .')
        assert f"GRAPH <{DATA_GRAPH}>" in query
        assert "INSERT DATA" in query

    def test_insert_relationship_targets_data_graph(self):
        query = insert_relationship("http://example.org/foaf-poc/person001", "http://purl.org/vocab/relationship/friendOf", "http://example.org/foaf-poc/person002")
        assert f"GRAPH <{DATA_GRAPH}>" in query

    def test_ontology_classes_targets_ontology_graph(self):
        query = get_ontology_classes()
        assert f"GRAPH <{ONTOLOGY_GRAPH}>" in query
        assert "owl:Class" in query

    def test_ontology_properties_targets_ontology_graph(self):
        query = get_ontology_properties()
        assert f"GRAPH <{ONTOLOGY_GRAPH}>" in query
        assert "owl:ObjectProperty" in query
        assert "owl:DatatypeProperty" in query


# ── SPARQL Client tests (mocked) ────────────────────────────────────────────

class TestSPARQLClient:
    @patch("app.graph.sparql_client.SPARQLWrapper")
    def test_test_connection_success(self, mock_wrapper):
        mock_instance = MagicMock()
        mock_instance.query.return_value.convert.return_value = {
            "results": {"bindings": [{"count": {"value": "100"}}]}
        }
        mock_wrapper.return_value = mock_instance

        client = SPARQLClient()
        client.query_endpoint = mock_instance
        assert client.test_connection() is True

    @patch("app.graph.sparql_client.SPARQLWrapper")
    def test_test_connection_failure(self, mock_wrapper):
        mock_instance = MagicMock()
        mock_instance.query.side_effect = Exception("Connection refused")
        mock_wrapper.return_value = mock_instance

        client = SPARQLClient()
        client.query_endpoint = mock_instance
        assert client.test_connection() is False

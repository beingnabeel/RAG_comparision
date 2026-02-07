"""Tests for the FastAPI endpoints."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestRootEndpoint:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "FoaF" in data["message"]


class TestHealthEndpoint:
    @patch("app.api.endpoints.sparql_client")
    @patch("app.api.endpoints.is_llm_configured")
    def test_health_healthy(self, mock_llm, mock_sparql):
        mock_llm.return_value = True
        mock_sparql.test_connection.return_value = True
        mock_sparql.get_graph_stats.return_value = {
            "persons": 100,
            "relationships": 300,
            "total_triples": 1500,
        }

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")

    @patch("app.api.endpoints.sparql_client")
    @patch("app.api.endpoints.is_llm_configured")
    def test_health_degraded(self, mock_llm, mock_sparql):
        mock_llm.return_value = False
        mock_sparql.test_connection.return_value = False
        mock_sparql.get_graph_stats.return_value = None

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"


class TestQueryEndpoint:
    @patch("app.api.endpoints.run_agent")
    def test_query_success(self, mock_agent):
        mock_agent.return_value = {
            "success": True,
            "query": "Who is John?",
            "intent": "query",
            "results": [],
            "response": "John Smith is a 35-year-old Software Engineer.",
            "sparql_query": "SELECT ...",
            "execution_time_ms": 100.0,
        }

        response = client.post("/query", json={"query": "Who is John?"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "John" in data["response"]


class TestAddPersonEndpoint:
    @patch("app.api.endpoints.add_person_to_graph")
    def test_add_person_success(self, mock_tool):
        mock_tool.invoke.return_value = {
            "success": True,
            "person_uri": "http://example.org/foaf-poc/person101",
            "message": "Person added successfully",
        }

        response = client.post(
            "/add-person",
            json={"name": "Test Person", "age": 30, "gender": "male"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestAddRelationshipEndpoint:
    @patch("app.api.endpoints.add_relationship_to_graph")
    def test_add_relationship_success(self, mock_tool):
        mock_tool.invoke.return_value = {
            "success": True,
            "message": "Relationship added",
        }

        response = client.post(
            "/add-relationship",
            json={
                "subject": "http://example.org/foaf-poc/person001",
                "predicate": "friendOf",
                "object": "http://example.org/foaf-poc/person002",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

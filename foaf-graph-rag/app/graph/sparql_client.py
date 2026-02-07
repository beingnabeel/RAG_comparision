from SPARQLWrapper import SPARQLWrapper, JSON, POST, GET
from typing import List, Dict, Any
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SPARQLClient:
    def __init__(self):
        self.query_endpoint = SPARQLWrapper(settings.FUSEKI_QUERY_ENDPOINT)
        self.update_endpoint = SPARQLWrapper(settings.FUSEKI_UPDATE_ENDPOINT)

        self.query_endpoint.setReturnFormat(JSON)
        self.update_endpoint.setReturnFormat(JSON)
        self.update_endpoint.setMethod(POST)

    def execute_select(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return bindings."""
        try:
            self.query_endpoint.setQuery(query)
            self.query_endpoint.setMethod(GET)
            results = self.query_endpoint.query().convert()
            return results["results"]["bindings"]
        except Exception as e:
            logger.error(f"SELECT query failed: {e}")
            raise

    def execute_ask(self, query: str) -> bool:
        """Execute an ASK query."""
        try:
            self.query_endpoint.setQuery(query)
            self.query_endpoint.setMethod(GET)
            results = self.query_endpoint.query().convert()
            return results["boolean"]
        except Exception as e:
            logger.error(f"ASK query failed: {e}")
            raise

    def execute_update(self, query: str) -> bool:
        """Execute an INSERT/DELETE/UPDATE query."""
        try:
            self.update_endpoint.setQuery(query)
            self.update_endpoint.query()
            return True
        except Exception as e:
            logger.error(f"UPDATE query failed: {e}")
            raise

    def test_connection(self) -> bool:
        """Test connection to Fuseki."""
        try:
            test_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            self.execute_select(test_query)
            return True
        except Exception:
            return False

    def get_graph_stats(self) -> Dict[str, int]:
        """Get graph statistics from both ontology and data named graphs."""
        try:
            data_graph = settings.DATA_GRAPH_URI
            ontology_graph = settings.ONTOLOGY_GRAPH_URI

            persons_query = f"""
            PREFIX custom: <http://example.org/foaf-poc/>
            SELECT (COUNT(?p) as ?count) WHERE {{
                GRAPH <{data_graph}> {{ ?p a custom:Person }}
            }}
            """
            persons_result = self.execute_select(persons_query)
            persons_count = int(persons_result[0]["count"]["value"]) if persons_result else 0

            relationships_query = f"""
            PREFIX rel: <http://purl.org/vocab/relationship/>
            PREFIX foaf: <http://xmlns.com/foaf/0.1/>
            PREFIX custom: <http://example.org/foaf-poc/>
            SELECT (COUNT(*) as ?count) WHERE {{
                GRAPH <{data_graph}> {{
                    ?s ?p ?o .
                    FILTER (
                        STRSTARTS(STR(?p), "http://purl.org/vocab/relationship/") ||
                        ?p = foaf:knows ||
                        ?p = custom:colleagueOf ||
                        ?p = custom:neighborOf
                    )
                }}
            }}
            """
            rel_result = self.execute_select(relationships_query)
            rel_count = int(rel_result[0]["count"]["value"]) if rel_result else 0

            data_triples_query = f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{data_graph}> {{ ?s ?p ?o }} }}"
            data_result = self.execute_select(data_triples_query)
            data_count = int(data_result[0]["count"]["value"]) if data_result else 0

            ontology_triples_query = f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{ontology_graph}> {{ ?s ?p ?o }} }}"
            ontology_result = self.execute_select(ontology_triples_query)
            ontology_count = int(ontology_result[0]["count"]["value"]) if ontology_result else 0

            return {
                "persons": persons_count,
                "relationships": rel_count,
                "data_triples": data_count,
                "ontology_triples": ontology_count,
                "total_triples": data_count + ontology_count,
            }
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"persons": 0, "relationships": 0, "data_triples": 0, "ontology_triples": 0, "total_triples": 0}


sparql_client = SPARQLClient()

"""FastAPI route handlers for the FoaF Graph RAG API."""

import time
from fastapi import APIRouter, HTTPException

from app.models.requests import QueryRequest, AddPersonRequest, AddRelationshipRequest
from app.models.responses import (
    QueryResponse,
    AddPersonResponse,
    AddRelationshipResponse,
    HealthResponse,
    ErrorResponse,
)
from app.agent.graph_agent import run_agent
from app.agent.tools import add_person_to_graph, add_relationship_to_graph, search_person_by_name
from app.graph.sparql_client import sparql_client
from app.llm.openai_client import is_llm_configured
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint showing system status."""
    fuseki_ok = sparql_client.test_connection()
    llm_ok = is_llm_configured()
    graph_stats = sparql_client.get_graph_stats() if fuseki_ok else None

    status = "healthy" if fuseki_ok and llm_ok else "degraded"
    return HealthResponse(
        status=status,
        fuseki_connected=fuseki_ok,
        llm_configured=llm_ok,
        graph_size=graph_stats,
    )


@router.post("/query", response_model=QueryResponse)
async def query_graph(request: QueryRequest):
    """Natural language query endpoint — the main agent interface."""
    try:
        result = await run_agent(request.query)

        response = QueryResponse(
            success=result["success"],
            query=result["query"],
            intent=result.get("intent"),
            results=result.get("results") if request.include_metadata else None,
            response=result["response"],
            sparql_query=result.get("sparql_query") if request.include_metadata else None,
            execution_time_ms=result.get("execution_time_ms"),
        )
        return response
    except Exception as e:
        logger.error(f"Query endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-person", response_model=AddPersonResponse)
async def add_person(request: AddPersonRequest):
    """Add a new person to the knowledge graph."""
    try:
        result = add_person_to_graph.invoke(
            {
                "name": request.name,
                "age": request.age,
                "gender": request.gender,
                "phone": request.phone,
                "email": request.email,
                "address": request.address,
                "city": request.city,
                "state": request.state,
                "postal_code": request.postal_code,
                "country": request.country,
                "job_title": request.job_title,
                "occupation": request.occupation,
                "industry": request.industry,
            }
        )
        return AddPersonResponse(
            success=result["success"],
            person_uri=result.get("person_uri"),
            message=result.get("message", result.get("error", "")),
        )
    except Exception as e:
        logger.error(f"Add person error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add-relationship", response_model=AddRelationshipResponse)
async def add_relationship(request: AddRelationshipRequest):
    """Add a relationship between two persons."""
    try:
        result = add_relationship_to_graph.invoke(
            {
                "subject_name_or_uri": request.subject,
                "predicate": request.predicate,
                "object_name_or_uri": request.object,
            }
        )
        return AddRelationshipResponse(
            success=result["success"],
            message=result.get("message", result.get("error", "")),
        )
    except Exception as e:
        logger.error(f"Add relationship error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/person/{person_id}")
async def get_person(person_id: str):
    """Get details of a specific person by ID (e.g., person001)."""
    try:
        person_uri = f"http://example.org/foaf-poc/{person_id}"
        from app.graph.query_builder import get_person_details, get_person_relationships

        # Get person details
        details_query = get_person_details(person_uri)
        details = sparql_client.execute_select(details_query)

        if not details:
            raise HTTPException(status_code=404, detail=f"Person '{person_id}' not found")

        # Get relationships
        rel_query = get_person_relationships(person_uri)
        relationships = sparql_client.execute_select(rel_query)

        # Format results
        person_data = {}
        for row in details:
            pred = row["predicate"]["value"]
            val = row["value"]["value"]
            key = pred.split("/")[-1].split("#")[-1]
            person_data[key] = val

        rel_data = []
        for row in relationships:
            rel_data.append(
                {
                    "relationship": row["relationship"]["value"].split("/")[-1],
                    "person": row["relatedName"]["value"],
                    "uri": row["relatedPerson"]["value"],
                }
            )

        return {
            "success": True,
            "person_uri": person_uri,
            "details": person_data,
            "relationships": rel_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get person error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/persons")
async def list_persons(limit: int = 100):
    """List all persons in the knowledge graph."""
    try:
        from app.graph.query_builder import get_all_persons

        query = get_all_persons(limit)
        results = sparql_client.execute_select(query)

        persons = []
        for row in results:
            person = {"uri": row["person"]["value"], "name": row["name"]["value"]}
            if "age" in row:
                person["age"] = row["age"]["value"]
            if "jobTitle" in row:
                person["job_title"] = row["jobTitle"]["value"]
            if "city" in row:
                person["city"] = row["city"]["value"]
            persons.append(person)

        return {"success": True, "count": len(persons), "persons": persons}
    except Exception as e:
        logger.error(f"List persons error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

"""LangGraph agent for the FoaF Graph RAG system.

Optimized for free-tier LLM usage: uses rule-based intent classification
(no LLM call) and retry logic with backoff for rate limits.
Only 1 LLM call for simple queries, 2 for complex ones.
"""

import json
import re
import time
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.prompts import RESPONSE_FORMATTING_PROMPT
from app.agent.tools import execute_sparql_query
from app.llm.openai_client import get_llm
from app.llm.query_generator import generate_sparql
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ── LLM call with retry ────────────────────────────────────────────────────

def llm_invoke_with_retry(messages, max_retries=3):
    """Invoke LLM with exponential backoff for rate limits."""
    llm = get_llm()
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 2 ** attempt * 2  # 2s, 4s, 8s
                logger.warning(f"Rate limited (attempt {attempt+1}/{max_retries}), waiting {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise Exception("LLM rate limit exceeded after retries. Please wait a minute and try again.")


# ── Node functions ──────────────────────────────────────────────────────────

ADD_PERSON_PATTERNS = re.compile(
    r"\b(add|create|insert|register|new)\b.*(person|people|individual|user|member)",
    re.IGNORECASE,
)
ADD_REL_PATTERNS = re.compile(
    r"\b(add|create|make|set)\b.*(friend|spouse|parent|child|sibling|colleague|neighbor|relationship|connection)",
    re.IGNORECASE,
)
UPDATE_PATTERNS = re.compile(
    r"\b(update|change|modify|edit|set|rename)\b.*(name|age|phone|email|address|job|title)",
    re.IGNORECASE,
)


def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    """Classify intent using fast rule-based matching (no LLM call)."""
    query = state["user_query"]

    if ADD_PERSON_PATTERNS.search(query):
        intent = "add_person"
    elif ADD_REL_PATTERNS.search(query):
        intent = "add_relationship"
    elif UPDATE_PATTERNS.search(query):
        intent = "update"
    else:
        intent = "query"

    logger.info(f"Classified intent (rule-based): {intent} for query: {query}")
    return {
        "intent": intent,
        "messages": [AIMessage(content=f"Intent classified as: {intent}")],
    }


def generate_sparql_node(state: AgentState) -> Dict[str, Any]:
    """Generate a SPARQL query from natural language (1 LLM call with retry)."""
    try:
        sparql = generate_sparql(state["user_query"], state["intent"])
        logger.info(f"Generated SPARQL: {sparql[:200]}")
        return {
            "sparql_query": sparql,
            "messages": [AIMessage(content="Generated SPARQL query")],
        }
    except Exception as e:
        logger.error(f"SPARQL generation failed: {e}")
        return {
            "sparql_query": "",
            "error": f"Failed to generate SPARQL query: {e}",
            "messages": [AIMessage(content=f"SPARQL generation failed: {e}")],
        }


def execute_query_node(state: AgentState) -> Dict[str, Any]:
    """Execute the generated SPARQL query against the graph database."""
    try:
        sparql = state.get("sparql_query", "")
        if not sparql:
            error = state.get("error", "No SPARQL query to execute")
            return {
                "graph_results": [],
                "error": error,
                "messages": [AIMessage(content="No SPARQL query available")],
            }

        result = execute_sparql_query.invoke({"query": sparql})

        if result.get("success"):
            results = result.get("results", [])
            if result.get("answer") is not None:
                results = [{"answer": result["answer"]}]
            if result.get("message"):
                results = [{"message": result["message"]}]
            return {
                "graph_results": results,
                "messages": [AIMessage(content=f"Query returned {len(results)} results")],
            }
        else:
            return {
                "graph_results": [],
                "error": result.get("error", "Query execution failed"),
                "messages": [AIMessage(content=f"Query failed: {result.get('error')}")],
            }
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {
            "graph_results": [],
            "error": str(e),
            "messages": [AIMessage(content=f"Execution error: {e}")],
        }


def format_response_node(state: AgentState) -> Dict[str, Any]:
    """Format the graph results into a natural language response.

    Uses LLM for rich formatting, with a clean fallback if rate-limited.
    """
    results = state.get("graph_results", [])
    error = state.get("error")

    if error and not results:
        return {
            "final_response": f"I encountered an issue: {error}. Please try rephrasing your question.",
            "messages": [AIMessage(content="Error response generated")],
        }

    # Try LLM formatting, fall back to structured text if rate-limited
    try:
        prompt = RESPONSE_FORMATTING_PROMPT.format(
            user_query=state["user_query"],
            graph_results=json.dumps(results, indent=2, default=str),
        )
        response = llm_invoke_with_retry([HumanMessage(content=prompt)])
        return {
            "final_response": response.content.strip(),
            "messages": [AIMessage(content="Response formatted via LLM")],
        }
    except Exception as e:
        logger.warning(f"LLM response formatting failed, using fallback: {e}")
        return {
            "final_response": _fallback_format(state["user_query"], results),
            "messages": [AIMessage(content="Fallback response used")],
        }


def _fallback_format(query: str, results: list) -> str:
    """Format results without an LLM call — clean structured text."""
    if not results:
        return "No results found for your query. Please try a different question."

    lines = [f"Found {len(results)} result(s) for: \"{query}\"\n"]
    for i, row in enumerate(results[:20], 1):
        parts = []
        for key, val in row.items():
            if isinstance(val, dict):
                v = val.get("value", str(val))
            else:
                v = str(val)
            # Clean up URIs to show just the last segment
            if v.startswith("http://") or v.startswith("mailto:"):
                v = v.split("/")[-1].split("#")[-1]
            parts.append(f"{key}: {v}")
        lines.append(f"  {i}. {', '.join(parts)}")

    return "\n".join(lines)


def handle_error_node(state: AgentState) -> Dict[str, Any]:
    """Handle errors in the agent workflow."""
    error = state.get("error", "Unknown error occurred")
    return {
        "final_response": f"I'm sorry, I couldn't process your request. Error: {error}",
        "messages": [AIMessage(content=f"Error handled: {error}")],
    }


# ── Routing function ────────────────────────────────────────────────────────

def route_by_intent(state: AgentState) -> str:
    """Route to the next node based on classified intent."""
    intent = state.get("intent", "query")
    if intent == "error":
        return "handle_error"
    return "generate_sparql"


# ── Build the LangGraph workflow ────────────────────────────────────────────

def build_agent():
    """Build and compile the LangGraph agent workflow."""
    workflow = StateGraph(AgentState)

    # Define nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("generate_sparql", generate_sparql_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_response", format_response_node)
    workflow.add_node("handle_error", handle_error_node)

    # Define edges
    workflow.set_entry_point("classify_intent")

    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "generate_sparql": "generate_sparql",
            "handle_error": "handle_error",
        },
    )

    workflow.add_edge("generate_sparql", "execute_query")
    workflow.add_edge("execute_query", "format_response")
    workflow.add_edge("format_response", END)
    workflow.add_edge("handle_error", END)

    return workflow.compile()


# Singleton agent instance
agent = build_agent()


async def run_agent(user_query: str) -> Dict[str, Any]:
    """Run the agent with a user query and return structured results."""
    start_time = time.time()

    initial_state = {
        "messages": [HumanMessage(content=user_query)],
        "user_query": user_query,
        "intent": "",
        "sparql_query": "",
        "graph_results": [],
        "final_response": "",
        "error": None,
    }

    try:
        result = agent.invoke(initial_state)
        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "success": True,
            "query": user_query,
            "intent": result.get("intent", ""),
            "results": result.get("graph_results", []),
            "response": result.get("final_response", ""),
            "sparql_query": result.get("sparql_query", ""),
            "execution_time_ms": round(elapsed_ms, 2),
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"Agent execution failed: {e}")
        return {
            "success": False,
            "query": user_query,
            "intent": "",
            "results": [],
            "response": f"Agent error: {str(e)}",
            "sparql_query": "",
            "execution_time_ms": round(elapsed_ms, 2),
        }

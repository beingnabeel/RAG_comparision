"""LangGraph agent for the FoaF Vector RAG system.

Pipeline: classify_intent → retrieve_documents → generate_response
Uses rule-based intent classification (no LLM call) and semantic retrieval
from ChromaDB, then LLM generates the final response from retrieved context.
"""

import json
import re
import time
from typing import Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.prompts import RESPONSE_GENERATION_PROMPT
from app.vector.retriever import retrieve_documents
from app.llm.llm_client import get_llm
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
                wait = 2 ** attempt * 2
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


def retrieve_documents_node(state: AgentState) -> Dict[str, Any]:
    """Retrieve relevant documents from ChromaDB via semantic search."""
    try:
        query = state["user_query"]
        result = retrieve_documents(query)

        context = result.get("context", "")
        docs = result.get("documents", [])
        count = result.get("total_retrieved", 0)

        if not context:
            return {
                "retrieved_context": "",
                "retrieved_docs": [],
                "retrieval_count": 0,
                "error": "No relevant documents found in the vector store.",
                "messages": [AIMessage(content="No documents retrieved")],
            }

        return {
            "retrieved_context": context,
            "retrieved_docs": docs,
            "retrieval_count": count,
            "messages": [AIMessage(content=f"Retrieved {count} documents")],
        }
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        return {
            "retrieved_context": "",
            "retrieved_docs": [],
            "retrieval_count": 0,
            "error": f"Document retrieval failed: {e}",
            "messages": [AIMessage(content=f"Retrieval error: {e}")],
        }


def generate_response_node(state: AgentState) -> Dict[str, Any]:
    """Generate a natural language response from retrieved context using LLM.

    Falls back to structured text if rate-limited.
    """
    context = state.get("retrieved_context", "")
    error = state.get("error")

    if error and not context:
        return {
            "final_response": f"I encountered an issue: {error}. Please try rephrasing your question.",
            "messages": [AIMessage(content="Error response generated")],
        }

    try:
        prompt = RESPONSE_GENERATION_PROMPT.format(
            user_query=state["user_query"],
            context=context,
        )
        response = llm_invoke_with_retry([HumanMessage(content=prompt)])
        return {
            "final_response": response.content.strip(),
            "messages": [AIMessage(content="Response generated via LLM")],
        }
    except Exception as e:
        logger.warning(f"LLM response generation failed, using fallback: {e}")
        return {
            "final_response": _fallback_format(state["user_query"], context),
            "messages": [AIMessage(content="Fallback response used")],
        }


def _fallback_format(query: str, context: str) -> str:
    """Format results without an LLM call — return raw retrieved context."""
    if not context:
        return "No results found for your query. Please try a different question."

    lines = [f"Here is what I found for: \"{query}\"\n"]
    for para in context.split("\n\n")[:10]:
        lines.append(f"• {para.strip()}")

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
    return "retrieve_documents"


# ── Build the LangGraph workflow ────────────────────────────────────────────

def build_agent():
    """Build and compile the LangGraph agent workflow."""
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("retrieve_documents", retrieve_documents_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("handle_error", handle_error_node)

    workflow.set_entry_point("classify_intent")

    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "retrieve_documents": "retrieve_documents",
            "handle_error": "handle_error",
        },
    )

    workflow.add_edge("retrieve_documents", "generate_response")
    workflow.add_edge("generate_response", END)
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
        "retrieved_context": "",
        "retrieved_docs": [],
        "retrieval_count": 0,
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
            "results": result.get("retrieved_docs", []),
            "retrieval_count": result.get("retrieval_count", 0),
            "response": result.get("final_response", ""),
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
            "retrieval_count": 0,
            "response": f"Agent error: {str(e)}",
            "execution_time_ms": round(elapsed_ms, 2),
        }

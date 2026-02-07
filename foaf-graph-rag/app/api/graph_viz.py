"""API endpoints for graph visualization — returns nodes & edges for vis.js."""

from fastapi import APIRouter, Query
from app.graph.sparql_client import sparql_client
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

viz_router = APIRouter(prefix="/viz", tags=["visualization"])


@viz_router.get("/data-graph")
async def get_data_graph(limit: int = Query(default=100, le=500)):
    """Return the data graph as vis.js-compatible nodes and edges."""
    try:
        # Get all persons with their properties
        persons_query = f"""
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX custom: <http://example.org/foaf-poc/>
        PREFIX schema: <http://schema.org/>

        SELECT ?person ?name ?age ?gender ?jobTitle ?city
        WHERE {{
          GRAPH <{settings.DATA_GRAPH_URI}> {{
            ?person a custom:Person ;
                    foaf:name ?name .
            OPTIONAL {{ ?person foaf:age ?age }}
            OPTIONAL {{ ?person foaf:gender ?gender }}
            OPTIONAL {{ ?person schema:jobTitle ?jobTitle }}
            OPTIONAL {{ ?person schema:addressLocality ?city }}
          }}
        }}
        ORDER BY ?name
        LIMIT {limit}
        """
        persons = sparql_client.execute_select(persons_query)

        # Get all relationships between persons
        rels_query = f"""
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX rel: <http://purl.org/vocab/relationship/>
        PREFIX custom: <http://example.org/foaf-poc/>

        SELECT ?from ?to ?relType
        WHERE {{
          GRAPH <{settings.DATA_GRAPH_URI}> {{
            ?from ?rel ?to .
            ?from a custom:Person .
            ?to a custom:Person .
            FILTER(?rel IN (
              foaf:knows,
              rel:friendOf, rel:spouseOf,
              rel:parentOf, rel:childOf, rel:siblingOf,
              custom:colleagueOf, custom:neighborOf
            ))
            BIND(REPLACE(REPLACE(STR(?rel),
              "http://purl.org/vocab/relationship/", ""),
              "http://xmlns.com/foaf/0.1/", "") AS ?relType)
          }}
        }}
        """
        rels = sparql_client.execute_select(rels_query)

        # Build vis.js data
        nodes = []
        node_ids = set()
        for p in persons:
            uri = p["person"]["value"]
            pid = uri.split("/")[-1]
            if pid in node_ids:
                continue
            node_ids.add(pid)

            name = p["name"]["value"]
            age = p.get("age", {}).get("value", "")
            gender = p.get("gender", {}).get("value", "")
            job = p.get("jobTitle", {}).get("value", "")
            city = p.get("city", {}).get("value", "")

            # Color by gender
            color = "#6366f1" if gender == "male" else "#ec4899" if gender == "female" else "#8b5cf6"

            title = f"<b>{name}</b><br>ID: {pid}"
            if age:
                title += f"<br>Age: {age}"
            if job:
                title += f"<br>Job: {job}"
            if city:
                title += f"<br>City: {city}"

            nodes.append({
                "id": pid,
                "label": name,
                "title": title,
                "color": color,
                "shape": "dot",
                "size": 18,
                "font": {"size": 11, "color": "#e2e8f0"},
            })

        # Edge colors by relationship type
        edge_colors = {
            "friendOf": "#22c55e",
            "spouseOf": "#ef4444",
            "parentOf": "#f59e0b",
            "childOf": "#f97316",
            "siblingOf": "#06b6d4",
            "colleagueOf": "#8b5cf6",
            "neighborOf": "#64748b",
            "knows": "#94a3b8",
        }

        edges = []
        seen_edges = set()
        for r in rels:
            from_id = r["from"]["value"].split("/")[-1]
            to_id = r["to"]["value"].split("/")[-1]
            rel_type = r["relType"]["value"]

            # Skip if either node not in our set
            if from_id not in node_ids or to_id not in node_ids:
                continue

            edge_key = f"{from_id}-{rel_type}-{to_id}"
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            edges.append({
                "from": from_id,
                "to": to_id,
                "label": rel_type,
                "color": {"color": edge_colors.get(rel_type, "#64748b"), "opacity": 0.7},
                "arrows": "to",
                "font": {"size": 9, "color": "#94a3b8", "strokeWidth": 0},
                "smooth": {"type": "curvedCW", "roundness": 0.2},
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        }
    except Exception as e:
        logger.error(f"Data graph visualization error: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}


@viz_router.get("/ontology-graph")
async def get_ontology_graph():
    """Return the ontology graph as vis.js-compatible nodes and edges."""
    try:
        # Get all triples from ontology graph
        query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT ?s ?p ?o ?sLabel ?oLabel
        WHERE {{
          GRAPH <{settings.ONTOLOGY_GRAPH_URI}> {{
            ?s ?p ?o .
            OPTIONAL {{ ?s rdfs:label ?sLabel }}
            OPTIONAL {{ ?o rdfs:label ?oLabel }}
          }}
        }}
        """
        triples = sparql_client.execute_select(query)

        nodes = {}
        edges = []

        # Category colors
        type_colors = {
            "Class": "#6366f1",
            "ObjectProperty": "#22c55e",
            "DatatypeProperty": "#f59e0b",
            "Literal": "#64748b",
            "Resource": "#8b5cf6",
        }

        for t in triples:
            s_uri = t["s"]["value"]
            p_uri = t["p"]["value"]
            o_val = t["o"]["value"]
            o_type = t["o"].get("type", "literal")

            s_label = t.get("sLabel", {}).get("value", "") or s_uri.split("/")[-1].split("#")[-1]
            s_id = s_uri.replace("http://", "").replace("/", "_").replace("#", "_").replace(".", "_")

            # Determine node type from predicates
            p_short = p_uri.split("/")[-1].split("#")[-1]

            # Add subject node
            if s_id not in nodes:
                nodes[s_id] = {
                    "id": s_id,
                    "label": s_label,
                    "title": f"<b>{s_label}</b><br>URI: {s_uri}",
                    "uri": s_uri,
                    "color": type_colors["Resource"],
                    "shape": "dot",
                    "size": 16,
                    "font": {"size": 11, "color": "#e2e8f0"},
                    "types": set(),
                }

            # Track types
            if p_short == "type":
                type_name = o_val.split("/")[-1].split("#")[-1]
                nodes[s_id]["types"].add(type_name)
                if "Class" in type_name:
                    nodes[s_id]["color"] = type_colors["Class"]
                    nodes[s_id]["shape"] = "diamond"
                    nodes[s_id]["size"] = 28
                elif "ObjectProperty" in type_name:
                    nodes[s_id]["color"] = type_colors["ObjectProperty"]
                    nodes[s_id]["shape"] = "triangle"
                    nodes[s_id]["size"] = 20
                elif "DatatypeProperty" in type_name:
                    nodes[s_id]["color"] = type_colors["DatatypeProperty"]
                    nodes[s_id]["shape"] = "triangleDown"
                    nodes[s_id]["size"] = 20

            # Add object node if it's a URI
            if o_type == "uri":
                o_label = t.get("oLabel", {}).get("value", "") or o_val.split("/")[-1].split("#")[-1]
                o_id = o_val.replace("http://", "").replace("/", "_").replace("#", "_").replace(".", "_")

                if o_id not in nodes:
                    nodes[o_id] = {
                        "id": o_id,
                        "label": o_label,
                        "title": f"<b>{o_label}</b><br>URI: {o_val}",
                        "uri": o_val,
                        "color": type_colors["Resource"],
                        "shape": "dot",
                        "size": 14,
                        "font": {"size": 11, "color": "#e2e8f0"},
                        "types": set(),
                    }

                # Skip rdf:type edges (we handle them visually via shape/color)
                if p_short != "type":
                    edges.append({
                        "from": s_id,
                        "to": o_id,
                        "label": p_short,
                        "arrows": "to",
                        "color": {"color": "#64748b", "opacity": 0.6},
                        "font": {"size": 9, "color": "#94a3b8", "strokeWidth": 0},
                    })
            elif o_type == "literal" and p_short not in ("label", "comment"):
                # Show important literals as small nodes
                o_id = f"{s_id}_{p_short}"
                short_val = o_val if len(o_val) <= 20 else o_val[:17] + "..."
                if o_id not in nodes:
                    nodes[o_id] = {
                        "id": o_id,
                        "label": short_val,
                        "title": f"<b>{p_short}</b>: {o_val}",
                        "color": type_colors["Literal"],
                        "shape": "box",
                        "size": 10,
                        "font": {"size": 9, "color": "#94a3b8"},
                        "types": set(),
                    }
                    edges.append({
                        "from": s_id,
                        "to": o_id,
                        "label": p_short,
                        "arrows": "to",
                        "color": {"color": "#475569", "opacity": 0.4},
                        "font": {"size": 8, "color": "#64748b", "strokeWidth": 0},
                        "dashes": True,
                    })

        # Convert sets to lists for JSON serialization
        node_list = []
        for n in nodes.values():
            n_copy = dict(n)
            n_copy["types"] = list(n_copy.get("types", set()))
            node_list.append(n_copy)

        return {
            "nodes": node_list,
            "edges": edges,
            "stats": {
                "node_count": len(node_list),
                "edge_count": len(edges),
            },
        }
    except Exception as e:
        logger.error(f"Ontology graph visualization error: {e}")
        return {"nodes": [], "edges": [], "error": str(e)}

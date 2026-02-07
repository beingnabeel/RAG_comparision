#!/usr/bin/env python3
"""
RAG Benchmark Runner — Graph RAG vs Vector RAG

Runs ground-truth test queries against both RAG systems, collects metrics,
uses LLM-as-judge for accuracy scoring, and generates a comparison report.

Usage:
    python run_benchmark.py                        # run against both
    python run_benchmark.py --target graph         # graph RAG only
    python run_benchmark.py --target vector        # vector RAG only
    python run_benchmark.py --category multi_hop   # filter by category
    python run_benchmark.py --ids Q01 Q05 Q12      # run specific queries
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from groq import Groq
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────────────────

GRAPH_RAG_URL = "http://localhost:8000/api/chat"
VECTOR_RAG_URL = "http://localhost:8001/api/chat"
QUERIES_FILE = Path(__file__).parent / "test_queries.json"
RESULTS_DIR = Path(__file__).parent / "results"
TIMEOUT = 60  # seconds per query

# ── Load environment ─────────────────────────────────────────────────────────

# 1. Load benchmark-specific env (for JUDGE_API_KEY)
benchmark_env = Path(__file__).parent / ".env.benchmark"
if benchmark_env.exists():
    load_dotenv(benchmark_env)

# 2. Also load from RAG projects as fallback
for env_path in [
    Path(__file__).parent.parent / "foaf-graph-rag" / ".env",
    Path(__file__).parent.parent / "foaf-vector-rag" / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path, override=False)
        break

# Groq API key for LLM judge
JUDGE_API_KEY = os.getenv("JUDGE_API_KEY", "")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "llama-3.3-70b-versatile")
JUDGE_RETRY_ATTEMPTS = 3
JUDGE_RETRY_BASE_DELAY = 5  # seconds


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_queries(path: Path, category: str = None, ids: List[str] = None,
                 difficulties: List[str] = None) -> List[dict]:
    """Load test queries, optionally filtering by category, IDs, or difficulty."""
    with open(path) as f:
        data = json.load(f)
    queries = data["queries"]
    if ids:
        queries = [q for q in queries if q["id"] in ids]
    if category:
        queries = [q for q in queries if q["category"] == category]
    if difficulties:
        queries = [q for q in queries if q["difficulty"] in difficulties]
    return queries


def query_rag(url: str, message: str) -> Dict:
    """Send a query to a RAG system and return the result with timing."""
    t0 = time.time()
    try:
        r = httpx.post(url, json={"message": message}, timeout=TIMEOUT)
        elapsed_ms = (time.time() - t0) * 1000
        if r.status_code != 200:
            return {
                "success": False,
                "response": f"HTTP {r.status_code}: {r.text[:200]}",
                "latency_ms": elapsed_ms,
                "retrieval_count": 0,
            }
        data = r.json()
        return {
            "success": data.get("success", False),
            "response": data.get("response", ""),
            "latency_ms": elapsed_ms,
            "server_latency_ms": data.get("execution_time_ms", 0),
            "retrieval_count": data.get("retrieval_count", data.get("result_count", 0)),
            "intent": data.get("intent", ""),
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "response": "CONNECTION_ERROR: Server not running",
            "latency_ms": (time.time() - t0) * 1000,
            "retrieval_count": 0,
        }
    except httpx.ReadTimeout:
        return {
            "success": False,
            "response": "TIMEOUT: Query exceeded time limit",
            "latency_ms": TIMEOUT * 1000,
            "retrieval_count": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "response": f"ERROR: {str(e)}",
            "latency_ms": (time.time() - t0) * 1000,
            "retrieval_count": 0,
        }


# ── LLM-as-Judge ─────────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an expert evaluator comparing a RAG system's answer against ground truth.

**Question:** {question}

**Expected Answer (ground truth):** {expected_answer}

**Key Facts that MUST be present:** {expected_facts}

**System's Answer:** {system_answer}

Rate the system's answer on these dimensions (each 1-10):

1. **Correctness**: Are the stated facts accurate? (10 = all facts correct, 1 = mostly wrong)
2. **Completeness**: Are all expected key facts present? (10 = all present, 1 = most missing)
3. **Relevance**: Does the answer address the question directly? (10 = perfectly on topic, 1 = off topic)

Respond ONLY in this exact JSON format (no markdown, no extra text):
{{"correctness": <int>, "completeness": <int>, "relevance": <int>, "reasoning": "<brief explanation in 1-2 sentences>"}}"""


def judge_answer(question: str, expected_answer: str, expected_facts: List[str],
                 system_answer: str) -> Dict:
    """Use Gemini LLM to score the system's answer against ground truth."""
    if not JUDGE_API_KEY:
        return {"correctness": 0, "completeness": 0, "relevance": 0,
                "reasoning": "NO_API_KEY: Cannot judge without LLM"}

    if "CONNECTION_ERROR" in system_answer or "TIMEOUT" in system_answer:
        return {"correctness": 0, "completeness": 0, "relevance": 0,
                "reasoning": f"System failed: {system_answer[:100]}"}

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_answer=expected_answer,
        expected_facts=json.dumps(expected_facts),
        system_answer=system_answer,
    )

    client = Groq(api_key=JUDGE_API_KEY)

    for attempt in range(1, JUDGE_RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            text = response.choices[0].message.content.strip()

            # Parse JSON from response (handle potential markdown wrapping)
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            scores = json.loads(text)
            return {
                "correctness": int(scores.get("correctness", 0)),
                "completeness": int(scores.get("completeness", 0)),
                "relevance": int(scores.get("relevance", 0)),
                "reasoning": scores.get("reasoning", ""),
            }
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay = JUDGE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                if attempt < JUDGE_RETRY_ATTEMPTS:
                    print(f"\n    ⏳ Rate limited, retrying in {delay}s (attempt {attempt}/{JUDGE_RETRY_ATTEMPTS})...", end=" ", flush=True)
                    time.sleep(delay)
                    continue
            return {"correctness": 0, "completeness": 0, "relevance": 0,
                    "reasoning": f"Judge error: {err_str[:100]}"}

    return {"correctness": 0, "completeness": 0, "relevance": 0,
            "reasoning": "Judge failed after all retries"}


# ── Benchmark Runner ──────────────────────────────────────────────────────────

def run_benchmark(queries: List[dict], targets: List[str]) -> Dict:
    """Run all queries against specified targets and collect results."""
    results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "targets": targets,
            "total_queries": len(queries),
            "llm_model": JUDGE_MODEL,
        },
        "queries": [],
    }

    total = len(queries)
    for i, q in enumerate(queries, 1):
        qid = q["id"]
        print(f"\n{'='*60}")
        print(f"  [{i}/{total}] {qid}: {q['query'][:60]}...")
        print(f"  Category: {q['category']} | Difficulty: {q['difficulty']}")
        print(f"{'='*60}")

        entry = {
            "id": qid,
            "query": q["query"],
            "category": q["category"],
            "difficulty": q["difficulty"],
            "expected_facts": q["expected_facts"],
            "expected_answer": q["expected_answer"],
            "results": {},
        }

        for target in targets:
            url = GRAPH_RAG_URL if target == "graph" else VECTOR_RAG_URL
            label = "Graph RAG" if target == "graph" else "Vector RAG"

            print(f"\n  → Querying {label}...", end=" ", flush=True)
            result = query_rag(url, q["query"])
            print(f"{'✓' if result['success'] else '✗'} ({result['latency_ms']:.0f}ms)")

            if result["success"]:
                response_preview = result["response"][:120].replace("\n", " ")
                print(f"    Response: {response_preview}...")

            # LLM Judge scoring
            print(f"  → Judging {label}...", end=" ", flush=True)
            scores = judge_answer(
                q["query"], q["expected_answer"], q["expected_facts"],
                result["response"],
            )
            print(f"C={scores['correctness']} P={scores['completeness']} R={scores['relevance']}")

            # Rate limit protection — space out requests
            time.sleep(5)

            entry["results"][target] = {
                **result,
                "scores": scores,
            }

        results["queries"].append(entry)

    return results


# ── Report Generation ─────────────────────────────────────────────────────────

def generate_report(results: Dict) -> str:
    """Generate a formatted comparison report."""
    targets = results["metadata"]["targets"]
    queries = results["queries"]
    total = len(queries)

    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("  RAG BENCHMARK REPORT — Graph RAG vs Vector RAG")
    lines.append(f"  Generated: {results['metadata']['timestamp']}")
    lines.append(f"  Queries: {total} | LLM Judge: {results['metadata']['llm_model']}")
    lines.append("=" * 70)

    # Per-target aggregate metrics
    for target in targets:
        label = "GRAPH RAG" if target == "graph" else "VECTOR RAG"
        target_results = [q["results"].get(target, {}) for q in queries]
        successful = [r for r in target_results if r.get("success")]

        latencies = [r["latency_ms"] for r in successful]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        retrievals = [r.get("retrieval_count", 0) for r in successful]
        avg_retrieval = sum(retrievals) / len(retrievals) if retrievals else 0

        scores_c = [r.get("scores", {}).get("correctness", 0) for r in target_results]
        scores_p = [r.get("scores", {}).get("completeness", 0) for r in target_results]
        scores_r = [r.get("scores", {}).get("relevance", 0) for r in target_results]

        avg_c = sum(scores_c) / len(scores_c) if scores_c else 0
        avg_p = sum(scores_p) / len(scores_p) if scores_p else 0
        avg_r = sum(scores_r) / len(scores_r) if scores_r else 0
        avg_overall = (avg_c + avg_p + avg_r) / 3

        lines.append(f"\n{'─'*70}")
        lines.append(f"  {label}")
        lines.append(f"{'─'*70}")
        lines.append(f"  Success Rate:      {len(successful)}/{total} ({len(successful)/total*100:.0f}%)")
        lines.append(f"  Avg Latency:       {avg_latency:.0f} ms")
        lines.append(f"  Avg Retrieval:     {avg_retrieval:.1f} results/query")
        lines.append(f"  Avg Correctness:   {avg_c:.1f}/10")
        lines.append(f"  Avg Completeness:  {avg_p:.1f}/10")
        lines.append(f"  Avg Relevance:     {avg_r:.1f}/10")
        lines.append(f"  ★ Overall Score:   {avg_overall:.1f}/10")

    # Side-by-side comparison if both targets
    if len(targets) == 2:
        lines.append(f"\n{'═'*70}")
        lines.append("  SIDE-BY-SIDE COMPARISON")
        lines.append(f"{'═'*70}")
        lines.append(f"\n  {'ID':<5} {'Category':<18} {'Diff':<7} {'Graph':>8} {'Vector':>8} {'Winner':>8}")
        lines.append(f"  {'─'*5} {'─'*18} {'─'*7} {'─'*8} {'─'*8} {'─'*8}")

        graph_wins = 0
        vector_wins = 0
        ties = 0

        for q in queries:
            g = q["results"].get("graph", {}).get("scores", {})
            v = q["results"].get("vector", {}).get("scores", {})
            g_avg = (g.get("correctness", 0) + g.get("completeness", 0) + g.get("relevance", 0)) / 3
            v_avg = (v.get("correctness", 0) + v.get("completeness", 0) + v.get("relevance", 0)) / 3

            if abs(g_avg - v_avg) < 0.5:
                winner = "TIE"
                ties += 1
            elif g_avg > v_avg:
                winner = "Graph"
                graph_wins += 1
            else:
                winner = "Vector"
                vector_wins += 1

            lines.append(f"  {q['id']:<5} {q['category']:<18} {q['difficulty']:<7} {g_avg:>7.1f} {v_avg:>7.1f} {winner:>8}")

        lines.append(f"\n  Graph wins: {graph_wins} | Vector wins: {vector_wins} | Ties: {ties}")

        # Category breakdown
        categories = sorted(set(q["category"] for q in queries))
        lines.append(f"\n{'─'*70}")
        lines.append("  BREAKDOWN BY CATEGORY")
        lines.append(f"{'─'*70}")
        lines.append(f"\n  {'Category':<20} {'Graph Avg':>10} {'Vector Avg':>11} {'Winner':>8}")
        lines.append(f"  {'─'*20} {'─'*10} {'─'*11} {'─'*8}")

        for cat in categories:
            cat_queries = [q for q in queries if q["category"] == cat]
            g_scores = []
            v_scores = []
            for q in cat_queries:
                g = q["results"].get("graph", {}).get("scores", {})
                v = q["results"].get("vector", {}).get("scores", {})
                g_scores.append((g.get("correctness", 0) + g.get("completeness", 0) + g.get("relevance", 0)) / 3)
                v_scores.append((v.get("correctness", 0) + v.get("completeness", 0) + v.get("relevance", 0)) / 3)
            g_avg = sum(g_scores) / len(g_scores) if g_scores else 0
            v_avg = sum(v_scores) / len(v_scores) if v_scores else 0
            winner = "Tie" if abs(g_avg - v_avg) < 0.5 else ("Graph" if g_avg > v_avg else "Vector")
            lines.append(f"  {cat:<20} {g_avg:>9.1f} {v_avg:>10.1f} {winner:>8}")

        # Difficulty breakdown
        difficulties = ["easy", "medium", "hard"]
        lines.append(f"\n{'─'*70}")
        lines.append("  BREAKDOWN BY DIFFICULTY")
        lines.append(f"{'─'*70}")
        lines.append(f"\n  {'Difficulty':<12} {'Graph Avg':>10} {'Vector Avg':>11} {'Winner':>8}")
        lines.append(f"  {'─'*12} {'─'*10} {'─'*11} {'─'*8}")

        for diff in difficulties:
            diff_queries = [q for q in queries if q["difficulty"] == diff]
            if not diff_queries:
                continue
            g_scores = []
            v_scores = []
            for q in diff_queries:
                g = q["results"].get("graph", {}).get("scores", {})
                v = q["results"].get("vector", {}).get("scores", {})
                g_scores.append((g.get("correctness", 0) + g.get("completeness", 0) + g.get("relevance", 0)) / 3)
                v_scores.append((v.get("correctness", 0) + v.get("completeness", 0) + v.get("relevance", 0)) / 3)
            g_avg = sum(g_scores) / len(g_scores) if g_scores else 0
            v_avg = sum(v_scores) / len(v_scores) if v_scores else 0
            winner = "Tie" if abs(g_avg - v_avg) < 0.5 else ("Graph" if g_avg > v_avg else "Vector")
            lines.append(f"  {diff:<12} {g_avg:>9.1f} {v_avg:>10.1f} {winner:>8}")

    lines.append(f"\n{'═'*70}")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RAG Benchmark: Graph RAG vs Vector RAG")
    parser.add_argument("--target", choices=["graph", "vector", "both"], default="both",
                        help="Which RAG system(s) to benchmark")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter queries by category")
    parser.add_argument("--ids", nargs="+", type=str, default=None,
                        help="Run specific query IDs (e.g. Q01 Q05 Q12)")
    parser.add_argument("--difficulty", nargs="+", type=str, default=None,
                        help="Filter by difficulty (e.g. medium hard)")
    parser.add_argument("--no-judge", action="store_true",
                        help="Skip LLM judge scoring (faster, no API calls)")
    args = parser.parse_args()

    # Determine targets
    if args.target == "both":
        targets = ["graph", "vector"]
    else:
        targets = [args.target]

    # Load queries
    queries = load_queries(QUERIES_FILE, category=args.category, ids=args.ids,
                            difficulties=args.difficulty)
    if not queries:
        print("No queries matched the filters. Check --category or --ids.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  RAG BENCHMARK — {', '.join(t.title() for t in targets)} RAG")
    print(f"  Queries: {len(queries)} | Judge: {'OFF' if args.no_judge else JUDGE_MODEL}")
    print(f"{'='*60}")

    # Check server connectivity
    for target in targets:
        url = GRAPH_RAG_URL if target == "graph" else VECTOR_RAG_URL
        label = "Graph RAG" if target == "graph" else "Vector RAG"
        health_url = url.replace("/api/chat", "/health")
        try:
            r = httpx.get(health_url, timeout=5)
            if r.status_code == 200:
                print(f"  ✓ {label} server reachable at {url}")
            else:
                print(f"  ✗ {label} returned HTTP {r.status_code}")
        except httpx.ConnectError:
            print(f"  ✗ {label} not reachable at {url}")
            print(f"    Start it first, then re-run this benchmark.")
            sys.exit(1)

    # Override judge if --no-judge
    if args.no_judge:
        global judge_answer
        _orig = judge_answer
        judge_answer = lambda q, ea, ef, sa: {
            "correctness": -1, "completeness": -1, "relevance": -1,
            "reasoning": "SKIPPED (--no-judge)",
        }

    # Run benchmark
    results = run_benchmark(queries, targets)

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_label = "_".join(targets)

    results_file = RESULTS_DIR / f"benchmark_{target_label}_{ts}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {results_file}")

    # Generate and print report
    report = generate_report(results)
    print(report)

    report_file = RESULTS_DIR / f"report_{target_label}_{ts}.txt"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\n  Report saved: {report_file}")


if __name__ == "__main__":
    main()

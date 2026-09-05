"""BeeAI tool layer for the BeeAI backend (opt-in legacy — see beeai_agent.py).

`weather_graph_tool` exposes the Mellea-backed capability as a BeeAI tool: given a natural-language
question it generates a validated SPARQL spec (Mellea), executes it against the graph, and returns
the query + rows.

The core logic lives in `answer_question` (a plain function), so it is unit-testable with a mocked
generation backend without going through the BeeAI tool-invocation machinery. The "worth retrying"
relevance heuristic is shared with the pydantic-ai/LangGraph backends via `shared.py` rather than
duplicated here.
"""

from __future__ import annotations

import json

from beeai_framework.tools import StringToolOutput, tool

from ..sparql import run_query
from .beeai_generation import generate_spec
from .shared import relevance_retry_hint, worth_retrying


def answer_question(question: str, *, max_relevance_retries: int = 1) -> dict:
    """Generate a validated SPARQL spec, run it, and return a JSON-able payload.

    If the query looks like it hit a literal-value mismatch or a guessed subject URI but returned no
    rows, retry once with corrective feedback — these pass syntax validation but still produce a
    silently wrong answer.
    """
    spec = generate_spec(question)
    result = run_query(spec.sparql)
    attempts = 0
    while not result.rows and worth_retrying(spec.sparql) and attempts < max_relevance_retries:
        attempts += 1
        hint = relevance_retry_hint()
        spec = generate_spec(
            f"{question}\n\nThe previous query ({spec.sparql!r}) returned no results. {hint} "
            "Reconsider your literal values and city matching (they must match the data exactly) "
            "and try again."
        )
        result = run_query(spec.sparql)
    return {
        "intent": spec.intent,
        "sparql": result.sparql,
        "columns": result.columns,
        "rows": result.rows,
        "summary": result.summary(),
    }


@tool
def weather_graph_tool(question: str) -> StringToolOutput:
    """Answer a weather question by querying the weather knowledge graph.

    Generates a validated SPARQL SELECT (via Mellea), runs it against the RDF weather graph,
    and returns the executed query together with the result rows as JSON.
    """
    return StringToolOutput(result=json.dumps(answer_question(question), ensure_ascii=False))

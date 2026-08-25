"""BeeAI tool layer (principle P3 from the original main.py demo).

`weather_graph_tool` exposes the Mellea-backed capability as a BeeAI tool: given a natural-language
question it generates a validated SPARQL spec (Mellea), executes it against the graph, and returns
the query + rows. This mirrors main.py's `weather_tool`, which wrapped `fetch_mock_weather`.

The core logic lives in `answer_question` (a plain function), so it is unit-testable with a mocked
generation backend without going through the BeeAI tool-invocation machinery.
"""

from __future__ import annotations

import json
import re

from beeai_framework.tools import StringToolOutput, tool

from .generation import generate_spec
from .models import WX
from .sparql import distinct_values, run_query

# Heuristics for "this empty result is worth retrying" (as opposed to a genuinely-empty-but-correct
# answer for a query with no categorical filter at all): either a literal-value mismatch (e.g.
# "raining" vs. the data's "Rainy") on a categorical predicate, or a guessed/constructed subject URI
# (e.g. `<...#Chicago>`) instead of matching a city via its wx:name literal.
_CATEGORICAL_FILTER_RE = re.compile(r"wx:(condition|country|name)\b.*?[\"']", re.IGNORECASE | re.DOTALL)
_GUESSED_CITY_URI_RE = re.compile(rf"<{re.escape(WX)}(?!city\d+>)[A-Za-z]", re.IGNORECASE)


def _worth_retrying(sparql: str) -> bool:
    return bool(_CATEGORICAL_FILTER_RE.search(sparql) or _GUESSED_CITY_URI_RE.search(sparql))


def answer_question(question: str, *, max_relevance_retries: int = 1) -> dict:
    """Generate a validated SPARQL spec, run it, and return a JSON-able payload.

    If the query looks like it hit a literal-value mismatch or a guessed subject URI but returned no
    rows, retry once with corrective feedback — these pass syntax validation but still produce a
    silently wrong answer.
    """
    spec = generate_spec(question)
    result = run_query(spec.sparql)
    attempts = 0
    while not result.rows and _worth_retrying(spec.sparql) and attempts < max_relevance_retries:
        attempts += 1
        hint = (
            "The wx:condition values that exist in the data are exactly: "
            f'{", ".join(distinct_values("condition"))}. '
            "The wx:country values that exist in the data are exactly: "
            f'{", ".join(distinct_values("country"))}. '
            "City subjects are opaque URIs (e.g. wx:city0) — never guess or construct a subject "
            'URI from a city\'s name; always match a city via its wx:name literal, e.g. '
            '`?city wx:name "Chicago"`.'
        )
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

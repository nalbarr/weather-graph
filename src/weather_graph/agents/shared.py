"""Backend-agnostic NL -> validated SPARQL contract shared by all three agent implementations.

Every backend (pydantic-ai, LangGraph, BeeAI+Mellea) does the same three things: generate a
`WeatherSparqlSpec` from a question, hard-validate/repair it against `sparql.validate_query`, and
retry once more if the result looks like a literal-value or subject-URI mismatch rather than a
genuinely empty answer. This module owns everything about that contract that does *not* vary by
backend, so it is written once and reused rather than re-implemented per backend:

- `generate_validated_spec` / `generate_and_run` — the generic validate-then-repair and
  relevance-retry loops, parameterized over a backend-supplied async `generate(prompt) -> spec`
  callable. pydantic-ai's and LangGraph's backends use these directly. BeeAI's backend keeps its
  own repair loop (Mellea's `RejectionSamplingStrategy` drives that one differently) but reuses
  `worth_retrying`/`relevance_retry_hint` below rather than duplicating them.
- `worth_retrying` / `relevance_retry_hint` — the "is this empty result worth a retry" heuristic,
  moved here unchanged from the original BeeAI-tool-specific version.
- `GENERATION_REQUIREMENTS` / `ANSWER_INSTRUCTIONS` — shared prompt text.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Protocol

from ..models import ALLOWED_PREDICATES, WX, WeatherSparqlSpec
from ..sparql import SparqlValidationError, distinct_values, run_query, validate_query

Generate = Callable[[str], Awaitable[WeatherSparqlSpec]]


class WeatherAgent(Protocol):
    """The contract every backend's `build_agent()` returns, so `agents/__init__.py`'s dispatcher
    and `demo.py` can treat all three backends identically."""

    async def answer(self, question: str) -> str: ...

_EXAMPLE_SPARQL_LOOKUP = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { "
    "?city wx:name ?name ; wx:temperatureC ?temperatureC . "
    'FILTER(?name = "Chicago") } LIMIT 10'
)
_EXAMPLE_SPARQL_RANKING = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { "
    "?city wx:name ?name ; wx:temperatureC ?temperatureC . "
    "} ORDER BY DESC(?temperatureC) LIMIT 3"
)

GENERATION_REQUIREMENTS = (
    "Translate the user's natural-language weather question into a structured SPARQL spec.\n"
    "The graph describes cities with wx:name, wx:country, wx:temperatureC, wx:condition and "
    "wx:humidity. Every city is a subject bound to a variable (e.g. `?city`); every predicate is a "
    "triple `?city wx:<predicate> ?value` (never a bare `wx:<predicate> ?value` with no subject). "
    "Produce a SELECT query that answers the question.\n\n"
    "Example — 'What is Chicago's temperature?':\n"
    f"{_EXAMPLE_SPARQL_LOOKUP}\n\n"
    "Example — 'Which 3 cities are hottest?' (ranking questions use ORDER BY + LIMIT, never a "
    "sub-question, UNION, or a separate query per city):\n"
    f"{_EXAMPLE_SPARQL_RANKING}\n\n"
    "The `sparql` field must satisfy all of:\n"
    "- A single read-only SPARQL SELECT query, shaped like the examples above.\n"
    f"- Must declare PREFIX wx: <{WX}> .\n"
    f"- May only use these predicates: {', '.join('wx:' + p for p in ALLOWED_PREDICATES)}.\n"
    "- Every predicate use must have an explicit subject variable, as in the examples.\n"
    "- Must always include a LIMIT clause (default LIMIT 10 when the user gives no count).\n"
    "- Must never contain INSERT, DELETE, DROP, LOAD, SERVICE, UNION, or any write/federation "
    "operation.\n"
    "The `intent` field must restate the user's question in one sentence."
)

ANSWER_INSTRUCTIONS = (
    "You answer questions about city weather using only the SPARQL query rows you are given "
    "below. Never invent numbers; base your answer on the rows and mention the city values you "
    "used."
)

# Heuristics for "this empty result is worth retrying" (as opposed to a genuinely-empty-but-correct
# answer for a query with no categorical filter at all): either a literal-value mismatch (e.g.
# "raining" vs. the data's "Rainy") on a categorical predicate, or a guessed/constructed subject URI
# (e.g. `<...#Chicago>`) instead of matching a city via its wx:name literal.
_CATEGORICAL_FILTER_RE = re.compile(r"wx:(condition|country|name)\b.*?[\"']", re.IGNORECASE | re.DOTALL)
_GUESSED_CITY_URI_RE = re.compile(rf"<{re.escape(WX)}(?!city\d+>)[A-Za-z]", re.IGNORECASE)


def worth_retrying(sparql: str) -> bool:
    return bool(_CATEGORICAL_FILTER_RE.search(sparql) or _GUESSED_CITY_URI_RE.search(sparql))


def relevance_retry_hint() -> str:
    return (
        "The wx:condition values that exist in the data are exactly: "
        f'{", ".join(distinct_values("condition"))}. '
        "The wx:country values that exist in the data are exactly: "
        f'{", ".join(distinct_values("country"))}. '
        "City subjects are opaque URIs (e.g. wx:city0) — never guess or construct a subject "
        'URI from a city\'s name; always match a city via its wx:name literal, e.g. '
        '`?city wx:name "Chicago"`.'
    )


async def generate_validated_spec(
    question: str, *, generate: Generate, max_repairs: int = 1
) -> WeatherSparqlSpec:
    """Generate a spec, hard-validate it, and retry with corrective feedback on failure."""
    spec = await generate(question)
    attempts = 0
    while attempts <= max_repairs:
        try:
            validate_query(spec.sparql)
            return spec
        except SparqlValidationError as exc:
            attempts += 1
            if attempts > max_repairs:
                raise
            spec = await generate(
                f"{question}\n\nThe previous query was rejected: {exc}\n"
                "Return a corrected query."
            )
    return spec


async def generate_and_run(
    question: str,
    *,
    generate: Generate,
    max_repairs: int = 1,
    max_relevance_retries: int = 1,
) -> dict:
    """Generate a validated spec, run it, and return a JSON-able payload.

    If the query looks like it hit a literal-value mismatch or a guessed subject URI but returned
    no rows, retry once with corrective feedback — these pass syntax validation but still produce a
    silently wrong answer.
    """
    spec = await generate_validated_spec(question, generate=generate, max_repairs=max_repairs)
    result = run_query(spec.sparql)
    attempts = 0
    while not result.rows and worth_retrying(spec.sparql) and attempts < max_relevance_retries:
        attempts += 1
        hint = relevance_retry_hint()
        spec = await generate_validated_spec(
            f"{question}\n\nThe previous query ({spec.sparql!r}) returned no results. {hint} "
            "Reconsider your literal values and city matching (they must match the data exactly) "
            "and try again.",
            generate=generate,
            max_repairs=max_repairs,
        )
        result = run_query(spec.sparql)
    return {
        "intent": spec.intent,
        "sparql": result.sparql,
        "columns": result.columns,
        "rows": result.rows,
        "summary": result.summary(),
    }

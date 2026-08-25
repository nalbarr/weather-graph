"""SPARQL validation + execution against the weather graph.

These are pure-Python (no LLM), so they double as the *custom validators* that back
Mellea's instruct-validate-repair loop, and they are directly unit-testable.
"""

from __future__ import annotations

import functools
import re

from rdflib.plugins.sparql import prepareQuery

from .graph_data import get_graph
from .models import ALLOWED_PREDICATES, WX, QueryResult


class SparqlValidationError(ValueError):
    """Raised when a candidate query violates the weather-graph requirements."""


_LIMIT_RE = re.compile(r"\bLIMIT\b\s+\d+", re.IGNORECASE)
_WRITE_RE = re.compile(r"\b(INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|ADD|MOVE|COPY)\b", re.IGNORECASE)
_PREDICATE_RE = re.compile(r"wx:([A-Za-z_]\w*)")


def validate_query(sparql: str) -> None:
    """Enforce the requirements. Raises SparqlValidationError with a fixable message."""
    text = sparql.strip()
    if not text:
        raise SparqlValidationError("Query is empty.")
    if _WRITE_RE.search(text):
        raise SparqlValidationError("Only read-only SELECT queries are allowed; remove write keywords.")
    if not re.search(r"\bSELECT\b", text, re.IGNORECASE):
        raise SparqlValidationError("Query must be a SELECT query.")
    if not _LIMIT_RE.search(text):
        raise SparqlValidationError("Query must include a LIMIT clause (e.g. LIMIT 10).")

    used = set(_PREDICATE_RE.findall(text))
    unknown = used - set(ALLOWED_PREDICATES)
    if unknown:
        raise SparqlValidationError(
            f"Unknown predicate(s) {sorted(unknown)}; allowed: {sorted(ALLOWED_PREDICATES)}."
        )
    # Final gate: must parse as valid SPARQL syntax.
    try:
        prepareQuery(text)
    except Exception as exc:
        raise SparqlValidationError(f"Query is not valid SPARQL: {exc}") from exc


def is_valid(sparql: str) -> bool:
    """Boolean form of validate_query, convenient for Mellea requirement predicates."""
    try:
        validate_query(sparql)
        return True
    except SparqlValidationError:
        return False


@functools.cache
def distinct_values(predicate: str) -> tuple[str, ...]:
    """Distinct literal values used for wx:<predicate> in the current graph.

    Used to ground SPARQL generation in the data's real controlled vocabulary (e.g. wx:condition
    values like "Rainy"/"Snowy") instead of letting the model guess plausible-sounding strings that
    don't actually appear in the data.
    """
    query = f"PREFIX wx: <{WX}> SELECT DISTINCT ?v WHERE {{ ?c wx:{predicate} ?v }}"
    result = get_graph().query(query)
    return tuple(sorted(str(row["v"]) for row in result))


def run_query(sparql: str) -> QueryResult:
    """Validate then execute the query against the weather graph."""
    validate_query(sparql)
    g = get_graph()
    result = g.query(sparql)
    columns = [str(v) for v in (result.vars or [])]
    rows: list[dict[str, str]] = []
    for row in result:
        rows.append({col: str(row[col]) if row[col] is not None else "" for col in columns})
    return QueryResult(sparql=sparql, columns=columns, rows=rows)

"""Structured data models (principle P1 from the original main.py demo).

`WeatherSparqlSpec` is the "weather SPARQL spec": instead of asking the model for a
free-form answer, we ask it for a *structured, validatable* SPARQL query plus its intent.
This is what Mellea's `@generative` fills in, and what our validators/repair loop check.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Vocabulary the graph (and therefore any valid query) is allowed to use.
WX = "http://example.org/weather#"
ALLOWED_PREDICATES = ("name", "temperatureC", "condition", "humidity", "country")


class WeatherSparqlSpec(BaseModel):
    """A structured, self-describing SPARQL query over the weather graph."""

    intent: str = Field(description="One sentence: what the user is trying to find out.")
    sparql: str = Field(
        description=(
            "A single read-only SPARQL SELECT query using PREFIX "
            f"wx: <{WX}> and only these predicates: {', '.join('wx:' + p for p in ALLOWED_PREDICATES)}. "
            "It must include a LIMIT clause."
        )
    )
    rationale: str = Field(description="Why this query answers the intent.")


class QueryRow(BaseModel):
    """One result row, variable name -> string value."""

    values: dict[str, str]


class QueryResult(BaseModel):
    """The executed query plus its rows, returned by the tool."""

    sparql: str
    columns: list[str]
    rows: list[dict[str, str]]

    def summary(self) -> str:
        if not self.rows:
            return "No matching rows."
        head = ", ".join(self.columns)
        body = "; ".join(" / ".join(f"{k}={v}" for k, v in r.items()) for r in self.rows[:10])
        return f"[{head}] {body}"

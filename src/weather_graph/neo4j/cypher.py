"""Fixed Cypher queries over the weather graph (no LLM generation — see PLAN_NEO4J.md).

Mirrors `weather_graph.sparql.run_query`'s role (validate-then-execute against the configured
backend) but simplified: since queries are fixed and parameterized rather than LLM-generated,
there is no analog to `sparql.py`'s text-validation gate — parameterization is the safety
mechanism here, same as in `movies-python-bolt/movies_sync.py`.
"""

from __future__ import annotations

from textwrap import dedent

from pydantic import BaseModel

from .connection import database, get_driver


class CypherQueryResult(BaseModel):
    """The executed query plus its rows."""

    cypher: str
    columns: list[str]
    rows: list[dict[str, str]]

    def summary(self) -> str:
        if not self.rows:
            return "No matching rows."
        head = ", ".join(self.columns)
        body = "; ".join(" / ".join(f"{k}={v}" for k, v in r.items()) for r in self.rows[:10])
        return f"[{head}] {body}"


def _run(cypher: str, **params: object) -> CypherQueryResult:
    text = dedent(cypher).strip()
    records, _summary, keys = get_driver().execute_query(
        text,
        parameters_=params,
        database_=database(),
        routing_="r",
    )
    columns = list(keys)
    rows = [{col: str(record[col]) for col in columns} for record in records]
    return CypherQueryResult(cypher=text, columns=columns, rows=rows)


def city_weather(name: str = "Chicago") -> CypherQueryResult:
    """Current temperature and condition for a named city."""
    return _run(
        """
        MATCH (c:City {name: $name})
        RETURN c.name AS name, c.temperatureC AS temperatureC, c.condition AS condition
        LIMIT 1
        """,
        name=name,
    )


def hottest_cities(limit: int = 3) -> CypherQueryResult:
    """The `limit` hottest cities in the data, hottest first."""
    return _run(
        """
        MATCH (c:City)
        RETURN c.name AS name, c.temperatureC AS temperatureC
        ORDER BY c.temperatureC DESC
        LIMIT $limit
        """,
        limit=limit,
    )


def city_condition(name: str = "Chicago") -> CypherQueryResult:
    """The current weather condition for a named city (e.g. to check rain/snow)."""
    return _run(
        """
        MATCH (c:City {name: $name})
        RETURN c.name AS name, c.condition AS condition
        LIMIT 1
        """,
        name=name,
    )

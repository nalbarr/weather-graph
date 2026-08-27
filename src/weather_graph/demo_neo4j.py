"""Runnable demo: the same 3 weather questions as demo.py, answered via fixed Cypher queries
against a Neo4j instance instead of an LLM agent over SPARQL (see PLAN_NEO4J.md).

Run: `uv run weather-graph-neo4j`
(requires `make neo4j-up` and `make neo4j-migrate` first — see docs/QUICKSTART.md).
"""

from __future__ import annotations

from .neo4j import cypher


def run() -> None:
    print("\n=== Q: What is the weather like in Chicago right now, and is it warm?")
    result = cypher.city_weather("Chicago")
    print(f"A: {result.summary()}")

    print("\n=== Q: Is Chicago one of the three hottest cities in the data?")
    result = cypher.hottest_cities(3)
    hottest_names = [row["name"] for row in result.rows]
    is_hottest = "Chicago" in hottest_names
    print(f"A: Top 3 hottest: {', '.join(hottest_names)}. Chicago is hottest-3: {is_hottest}.")

    print("\n=== Q: Is it currently raining or snowing in Chicago?")
    result = cypher.city_condition("Chicago")
    condition = result.rows[0]["condition"] if result.rows else "unknown"
    print(f"A: Condition is {condition!r} (raining/snowing: {condition in ('Rainy', 'Snowy')}).")


def main() -> None:
    run()


if __name__ == "__main__":
    main()

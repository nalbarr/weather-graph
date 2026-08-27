"""Exercises the Neo4j Cypher queries against a real instance.

Skips (does not fail) when no instance is reachable, so `make test` stays offline-safe — the
same invariant tests/conftest.py enforces for the RDF backends. There is no live Neo4j in this
repo's CI/dev environment as of this writing, so these tests are expected to skip by default;
they run for real once `make neo4j-up` + `make neo4j-migrate` have been done locally.
"""

from __future__ import annotations

import pytest

neo4j = pytest.importorskip("neo4j")

from weather_graph.neo4j import cypher
from weather_graph.neo4j.connection import database, get_driver


@pytest.fixture(scope="module")
def live_neo4j():
    try:
        get_driver().verify_connectivity()
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip"
        pytest.skip(f"No reachable Neo4j instance: {exc}")
    yield
    get_driver().close()


def test_city_weather_returns_chicago(live_neo4j):
    result = cypher.city_weather("Chicago")
    assert result.rows[0]["name"] == "Chicago"
    assert result.rows[0]["condition"]


def test_hottest_cities_returns_cairo_first(live_neo4j):
    result = cypher.hottest_cities(3)
    assert len(result.rows) == 3
    assert result.rows[0]["name"] == "Cairo"


def test_city_condition_for_chicago(live_neo4j):
    result = cypher.city_condition("Chicago")
    assert result.rows[0]["condition"] == "Partly Cloudy"


def test_database_helper_reads_env(monkeypatch):
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)
    assert database() == "neo4j"

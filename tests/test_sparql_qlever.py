"""Exercises SPARQL validation + execution against a real QLever server.

Skips (does not fail) when the QLever endpoint isn't reachable, so `make test` stays
offline-safe — the same invariant tests/conftest.py enforces for the RDF backends and
tests/test_neo4j.py / tests/test_kif.py enforce for their own live backends. Runs for real once
`make qlever-index` + `make qlever-up` have been done locally.

conftest.py pins GRAPH_BACKEND=memory at import time for the whole test session (so the rest of
the suite stays network-free), which also means graph_data.get_graph()'s lru_cache(maxsize=1) is
primed with a memory-backed graph before this module ever runs. Each test here temporarily points
GRAPH_BACKEND (and QLEVER_ENDPOINT) at the live server via monkeypatch and clears that cache so the
switch actually takes effect; monkeypatch reverts the env vars at teardown, and clearing the cache
again there means the very next test elsewhere in the suite rebuilds the memory graph as normal.

Assertions mirror tests/test_sparql.py's memory-backend versions exactly (same VALID query, same
expected rows) — the point is proving the two backends agree on the same data, not just that
QLever independently "works".
"""

from __future__ import annotations

import os

import pytest

from weather_graph import graph_data
from weather_graph.models import WX
from weather_graph.sparql import distinct_values, run_query

VALID = f"""
PREFIX wx: <{WX}>
SELECT ?name ?temperatureC WHERE {{
  ?c wx:name ?name ; wx:temperatureC ?temperatureC .
}} ORDER BY DESC(?temperatureC) LIMIT 3
"""


@pytest.fixture
def live_qlever(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GRAPH_BACKEND", "qlever")
    monkeypatch.setenv("QLEVER_ENDPOINT", os.environ.get("QLEVER_ENDPOINT", "http://localhost:7011"))
    graph_data.get_graph.cache_clear()
    distinct_values.cache_clear()
    try:
        run_query(f"PREFIX wx: <{WX}> SELECT ?c WHERE {{ ?c wx:temperatureC ?t }} LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip"
        graph_data.get_graph.cache_clear()
        distinct_values.cache_clear()
        pytest.skip(f"No reachable QLever endpoint: {exc}")
    yield
    graph_data.get_graph.cache_clear()
    distinct_values.cache_clear()


def test_run_query_returns_hottest_cities_from_qlever(live_qlever):
    result = run_query(VALID)
    assert result.columns == ["name", "temperatureC"]
    assert len(result.rows) == 3
    # Cairo (33) is the hottest in the dataset — same as the memory-backend assertion.
    assert result.rows[0]["name"] == "Cairo"


def test_distinct_condition_values_match_memory_backend(live_qlever):
    # Same assertion as tests/test_sparql.py's memory-backend version — proves QLever's vocabulary
    # grounding agrees with the in-memory graph's, not just that it returns *something*.
    assert distinct_values("condition") == (
        "Clear",
        "Cloudy",
        "Partly Cloudy",
        "Rainy",
        "Snowy",
        "Sunny",
    )

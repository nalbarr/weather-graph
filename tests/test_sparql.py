"""Pure-Python tests — no LLM / no network. Exercise the validate + execute path
that also backs Mellea's repair loop."""

import pytest

from weather_graph.models import WX
from weather_graph.sparql import (
    SparqlValidationError,
    distinct_values,
    is_valid,
    run_query,
    validate_query,
)

VALID = f"""
PREFIX wx: <{WX}>
SELECT ?name ?temperatureC WHERE {{
  ?c wx:name ?name ; wx:temperatureC ?temperatureC .
}} ORDER BY DESC(?temperatureC) LIMIT 3
"""


def test_valid_query_passes():
    validate_query(VALID)
    assert is_valid(VALID)


def test_missing_limit_rejected():
    q = f"PREFIX wx: <{WX}> SELECT ?name WHERE {{ ?c wx:name ?name . }}"
    with pytest.raises(SparqlValidationError, match="LIMIT"):
        validate_query(q)


def test_write_query_rejected():
    q = f"PREFIX wx: <{WX}> DELETE WHERE {{ ?c wx:name ?name . }} LIMIT 1"
    with pytest.raises(SparqlValidationError, match="read-only"):
        validate_query(q)


def test_unknown_predicate_rejected():
    q = f"PREFIX wx: <{WX}> SELECT ?x WHERE {{ ?c wx:windSpeed ?x . }} LIMIT 5"
    with pytest.raises(SparqlValidationError, match="Unknown predicate"):
        validate_query(q)


def test_run_query_returns_hottest_cities():
    result = run_query(VALID)
    assert result.columns == ["name", "temperatureC"]
    assert len(result.rows) == 3
    # Cairo (33) is the hottest in the dataset.
    assert result.rows[0]["name"] == "Cairo"


def test_distinct_condition_values_match_checked_in_data():
    # Grounds SPARQL generation in the real vocabulary — must track model/weather.ttl exactly.
    assert distinct_values("condition") == (
        "Clear",
        "Cloudy",
        "Partly Cloudy",
        "Rainy",
        "Snowy",
        "Sunny",
    )

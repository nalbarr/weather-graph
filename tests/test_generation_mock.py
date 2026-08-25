"""Generation + tool tests using the mocked generation backend (no LLM / no network)."""

import pytest

from weather_graph.generation import generate_spec
from weather_graph.models import WX, WeatherSparqlSpec
from weather_graph.sparql import SparqlValidationError
from weather_graph.tools import answer_question

VALID_SPARQL = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { ?c wx:name ?name ; wx:temperatureC ?temperatureC . "
    'FILTER(?name = "Paris") } LIMIT 1'
)
INVALID_NO_LIMIT = f"PREFIX wx: <{WX}> SELECT ?name WHERE {{ ?c wx:name ?name . }}"
# Wrong literal form ("raining"/"snowing" vs. the data's "Rainy"/"Snowy") — syntactically valid,
# matches nothing.
CONDITION_QUERY_NO_MATCH = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?condition WHERE { ?c wx:name ?name ; wx:condition ?condition . "
    'FILTER(?condition IN ("raining", "snowing")) } LIMIT 10'
)
CONDITION_QUERY_MATCH = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?condition WHERE { ?c wx:name ?name ; wx:condition ?condition . "
    'FILTER(?condition IN ("Rainy", "Snowy")) } LIMIT 10'
)
# No categorical (string-literal) filter at all — a genuinely empty result must not trigger a retry.
NO_MATCH_NUMERIC = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { ?c wx:name ?name ; wx:temperatureC ?temperatureC . "
    "FILTER(?temperatureC > 1000) } LIMIT 10"
)
# Guessed a subject URI from the city name instead of matching via wx:name — matches nothing since
# real subjects are opaque (wx:city0, wx:city1, ...).
GUESSED_URI_QUERY_NO_MATCH = (
    f"PREFIX wx: <{WX}> "
    f"SELECT ?temperatureC WHERE {{ <{WX}Chicago> wx:temperatureC ?temperatureC . }} LIMIT 10"
)
NAME_QUERY_MATCH = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { ?c wx:name ?name ; wx:temperatureC ?temperatureC . "
    'FILTER(?name = "Chicago") } LIMIT 10'
)


def _spec(sparql: str, intent: str = "find weather") -> WeatherSparqlSpec:
    return WeatherSparqlSpec(intent=intent, sparql=sparql, rationale="test")


def test_generate_spec_returns_valid(mock_generation):
    mock_generation.queue(_spec(VALID_SPARQL))
    spec = generate_spec("What is the weather in Paris?")
    assert spec.sparql == VALID_SPARQL
    assert len(mock_generation.calls) == 1
    # Requirements are actually plumbed through to the generative call.
    assert mock_generation.calls[0]["requirements"]


def test_generate_spec_repairs_invalid_then_valid(mock_generation):
    mock_generation.queue(_spec(INVALID_NO_LIMIT), _spec(VALID_SPARQL))
    spec = generate_spec("Weather in Paris?")
    assert spec.sparql == VALID_SPARQL
    # Two calls: the initial one and one repair.
    assert len(mock_generation.calls) == 2
    # The repair prompt tells the model what was wrong.
    assert "rejected" in mock_generation.calls[1]["question"].lower()
    assert "LIMIT" in mock_generation.calls[1]["question"]


def test_generate_spec_gives_up_after_max_repairs(mock_generation):
    mock_generation.queue(_spec(INVALID_NO_LIMIT), _spec(INVALID_NO_LIMIT))
    with pytest.raises(SparqlValidationError, match="LIMIT"):
        generate_spec("Weather in Paris?", max_repairs=1)
    assert len(mock_generation.calls) == 2


def test_answer_question_end_to_end(mock_generation):
    """generation (mocked) -> validate -> execute against the real graph -> tool payload."""
    mock_generation.queue(_spec(VALID_SPARQL, intent="Paris temperature"))
    payload = answer_question("How warm is Paris?")
    assert payload["intent"] == "Paris temperature"
    assert payload["columns"] == ["name", "temperatureC"]
    assert payload["rows"] == [{"name": "Paris", "temperatureC": "18.0"}]
    assert "Paris" in payload["summary"]


def test_answer_question_retries_on_empty_categorical_result(mock_generation):
    """A literal-value mismatch (e.g. "raining" vs. "Rainy") passes validation but matches nothing
    -- answer_question should retry once with the real vocabulary as corrective feedback."""
    mock_generation.queue(
        _spec(CONDITION_QUERY_NO_MATCH, intent="rain or snow"),
        _spec(CONDITION_QUERY_MATCH, intent="rain or snow"),
    )
    payload = answer_question("List cities where it is raining or snowing.")
    assert payload["rows"]  # non-empty on the retry
    assert len(mock_generation.calls) == 2
    retry_question = mock_generation.calls[1]["question"]
    assert "Rainy" in retry_question and "Snowy" in retry_question


def test_answer_question_no_retry_without_categorical_filter(mock_generation):
    """A genuinely empty result with no categorical string filter must not trigger a retry."""
    mock_generation.queue(_spec(NO_MATCH_NUMERIC, intent="no match"))
    payload = answer_question("Any city over 1000 degrees?")
    assert payload["rows"] == []
    assert len(mock_generation.calls) == 1


def test_answer_question_retries_on_guessed_city_uri(mock_generation):
    """Guessing a subject URI from the city name (instead of matching wx:name) also matches
    nothing -- answer_question should catch this and retry with the wx:name reminder."""
    mock_generation.queue(
        _spec(GUESSED_URI_QUERY_NO_MATCH, intent="Chicago temperature"),
        _spec(NAME_QUERY_MATCH, intent="Chicago temperature"),
    )
    payload = answer_question("What is the temperature in Chicago?")
    assert payload["rows"] == [{"name": "Chicago", "temperatureC": "21.0"}]
    assert len(mock_generation.calls) == 2
    assert "wx:name" in mock_generation.calls[1]["question"]

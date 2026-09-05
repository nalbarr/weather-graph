"""Full behavioral matrix for the shared generate -> validate -> repair -> execute contract.

This is the contract `pydantic_ai_agent.py` and `langgraph_agent.py` both delegate to via
`shared.generate_and_run`/`generate_validated_spec` — tested once, here, against the shared function
directly (with a fake async `generate` callable) rather than duplicated per backend. Each backend's
own test file (`test_agents_pydantic_ai.py`, `test_agents_langgraph.py`) then only needs to prove
its own wiring calls into this contract correctly, not re-prove the contract itself.

The BeeAI backend does NOT go through this module for its main repair loop (Mellea's
`RejectionSamplingStrategy` drives that one) — see `test_agents_beeai.py`, which mirrors this exact
matrix against `beeai_generation.generate_spec`/`beeai_tools.answer_question` instead, since that
logic is genuinely separate, not shared.
"""

from __future__ import annotations

import pytest

from weather_graph.agents.shared import generate_and_run, generate_validated_spec
from weather_graph.models import WX, WeatherSparqlSpec
from weather_graph.sparql import SparqlValidationError

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


class FakeAsyncGeneration:
    """A deterministic stand-in for a backend's `generate(prompt) -> WeatherSparqlSpec` callable."""

    def __init__(self) -> None:
        self.responses: list[WeatherSparqlSpec] = []
        self.calls: list[str] = []

    def queue(self, *specs: WeatherSparqlSpec) -> None:
        self.responses.extend(specs)

    async def __call__(self, prompt: str) -> WeatherSparqlSpec:
        self.calls.append(prompt)
        if not self.responses:
            raise AssertionError("FakeAsyncGeneration ran out of queued responses")
        return self.responses.pop(0)


@pytest.fixture
def fake_generate() -> FakeAsyncGeneration:
    return FakeAsyncGeneration()


@pytest.mark.asyncio
async def test_generate_validated_spec_returns_valid(fake_generate):
    fake_generate.queue(_spec(VALID_SPARQL))
    spec = await generate_validated_spec("What is the weather in Paris?", generate=fake_generate)
    assert spec.sparql == VALID_SPARQL
    assert len(fake_generate.calls) == 1


@pytest.mark.asyncio
async def test_generate_validated_spec_repairs_invalid_then_valid(fake_generate):
    fake_generate.queue(_spec(INVALID_NO_LIMIT), _spec(VALID_SPARQL))
    spec = await generate_validated_spec("Weather in Paris?", generate=fake_generate)
    assert spec.sparql == VALID_SPARQL
    assert len(fake_generate.calls) == 2
    assert "rejected" in fake_generate.calls[1].lower()
    assert "LIMIT" in fake_generate.calls[1]


@pytest.mark.asyncio
async def test_generate_validated_spec_gives_up_after_max_repairs(fake_generate):
    fake_generate.queue(_spec(INVALID_NO_LIMIT), _spec(INVALID_NO_LIMIT))
    with pytest.raises(SparqlValidationError, match="LIMIT"):
        await generate_validated_spec("Weather in Paris?", generate=fake_generate, max_repairs=1)
    assert len(fake_generate.calls) == 2


@pytest.mark.asyncio
async def test_generate_and_run_end_to_end(fake_generate):
    """generation (fake) -> validate -> execute against the real graph -> payload."""
    fake_generate.queue(_spec(VALID_SPARQL, intent="Paris temperature"))
    payload = await generate_and_run("How warm is Paris?", generate=fake_generate)
    assert payload["intent"] == "Paris temperature"
    assert payload["columns"] == ["name", "temperatureC"]
    assert payload["rows"] == [{"name": "Paris", "temperatureC": "18.0"}]
    assert "Paris" in payload["summary"]


@pytest.mark.asyncio
async def test_generate_and_run_retries_on_empty_categorical_result(fake_generate):
    """A literal-value mismatch (e.g. "raining" vs. "Rainy") passes validation but matches nothing
    -- generate_and_run should retry once with the real vocabulary as corrective feedback."""
    fake_generate.queue(
        _spec(CONDITION_QUERY_NO_MATCH, intent="rain or snow"),
        _spec(CONDITION_QUERY_MATCH, intent="rain or snow"),
    )
    payload = await generate_and_run("List cities where it is raining or snowing.", generate=fake_generate)
    assert payload["rows"]  # non-empty on the retry
    assert len(fake_generate.calls) == 2
    assert "Rainy" in fake_generate.calls[1] and "Snowy" in fake_generate.calls[1]


@pytest.mark.asyncio
async def test_generate_and_run_no_retry_without_categorical_filter(fake_generate):
    """A genuinely empty result with no categorical string filter must not trigger a retry."""
    fake_generate.queue(_spec(NO_MATCH_NUMERIC, intent="no match"))
    payload = await generate_and_run("Any city over 1000 degrees?", generate=fake_generate)
    assert payload["rows"] == []
    assert len(fake_generate.calls) == 1


@pytest.mark.asyncio
async def test_generate_and_run_retries_on_guessed_city_uri(fake_generate):
    """Guessing a subject URI from the city name (instead of matching wx:name) also matches
    nothing -- generate_and_run should catch this and retry with the wx:name reminder."""
    fake_generate.queue(
        _spec(GUESSED_URI_QUERY_NO_MATCH, intent="Chicago temperature"),
        _spec(NAME_QUERY_MATCH, intent="Chicago temperature"),
    )
    payload = await generate_and_run("What is the temperature in Chicago?", generate=fake_generate)
    assert payload["rows"] == [{"name": "Chicago", "temperatureC": "21.0"}]
    assert len(fake_generate.calls) == 2
    assert "wx:name" in fake_generate.calls[1]

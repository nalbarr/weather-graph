"""Wiring tests for the pydantic-ai backend (no LLM / no network).

The generate -> validate -> repair -> execute contract itself is tested once, generically, in
`test_agents_shared.py`. This file only proves `pydantic_ai_agent.py`'s own wiring: that
`answer()` always runs the real query (via `shared.generate_and_run`) before the tool-free answer
agent is asked to phrase a response — the "forced tool-first by construction" guarantee — by
faking `Agent` itself so no network call happens.
"""

from __future__ import annotations

import asyncio
from typing import ClassVar

from pydantic_ai import PromptedOutput

from weather_graph.agents import pydantic_ai_agent
from weather_graph.models import WX, WeatherSparqlSpec

VALID_SPARQL = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { ?c wx:name ?name ; wx:temperatureC ?temperatureC . "
    'FILTER(?name = "Paris") } LIMIT 1'
)


class _FakeResult:
    def __init__(self, output):
        self.output = output


class _FakeAgent:
    """Stand-in for `pydantic_ai.Agent`: returns a spec for structured-output calls (identified by
    `output_type=PromptedOutput(WeatherSparqlSpec)`) and a fixed string for the tool-free answer
    call (`output_type=None`)."""

    calls: ClassVar[list[tuple[object, str]]] = []

    def __init__(self, model, output_type=None, instructions=None, model_settings=None, retries=1):
        self.output_type = output_type

    async def run(self, prompt: str):
        _FakeAgent.calls.append((self.output_type, prompt))
        if isinstance(self.output_type, PromptedOutput):
            return _FakeResult(WeatherSparqlSpec(intent="Paris temperature", sparql=VALID_SPARQL, rationale="r"))
        return _FakeResult("Paris is 18.0C.")


def test_answer_generates_and_executes_before_final_answer_call(monkeypatch):
    monkeypatch.setattr(pydantic_ai_agent, "Agent", _FakeAgent)
    _FakeAgent.calls = []

    agent = pydantic_ai_agent.build_agent()
    result = asyncio.run(agent.answer("How warm is Paris?"))

    assert result == "Paris is 18.0C."
    # Exactly two model calls: the structured-output generation, then the tool-free answer --
    # the real SPARQL query ran in between (inside generate_and_run), not chosen by the model.
    assert len(_FakeAgent.calls) == 2
    assert isinstance(_FakeAgent.calls[0][0], PromptedOutput)
    assert _FakeAgent.calls[1][0] is None
    # The answer call is grounded in the real query result, not just the raw question.
    assert "Paris" in _FakeAgent.calls[1][1] and "18.0" in _FakeAgent.calls[1][1]


def test_model_defaults_resolve_without_network():
    # Constructing the client objects should never touch the network -- only calling .run() would.
    model = pydantic_ai_agent._model()
    assert model is not None

"""Wiring tests for the LangGraph backend (no LLM / no network).

The generate -> validate -> repair -> execute contract itself is tested once, generically, in
`test_agents_shared.py`. This file only proves `langgraph_agent.py`'s own wiring: that the compiled
graph's linear shape (`START -> query -> answer -> END`) actually runs the real query before the
answer node, by faking `ChatOllama` itself so no network call happens.
"""

from __future__ import annotations

import asyncio

from weather_graph.agents import langgraph_agent
from weather_graph.models import WX, WeatherSparqlSpec

VALID_SPARQL = (
    f"PREFIX wx: <{WX}> "
    "SELECT ?name ?temperatureC WHERE { ?c wx:name ?name ; wx:temperatureC ?temperatureC . "
    'FILTER(?name = "Paris") } LIMIT 1'
)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeStructured:
    async def ainvoke(self, prompt: str) -> WeatherSparqlSpec:
        return WeatherSparqlSpec(intent="Paris temperature", sparql=VALID_SPARQL, rationale="r")


class _FakeChatOllama:
    def __init__(self, model=None, base_url=None, temperature=None) -> None:
        pass

    def with_structured_output(self, cls, method=None):
        assert cls is WeatherSparqlSpec
        return _FakeStructured()

    async def ainvoke(self, prompt: str) -> _FakeMessage:
        return _FakeMessage("Paris is 18.0C.")


def test_answer_runs_query_node_before_answer_node(monkeypatch):
    monkeypatch.setattr(langgraph_agent, "ChatOllama", _FakeChatOllama)

    agent = langgraph_agent.build_agent()
    result = asyncio.run(agent.answer("How warm is Paris?"))

    assert result == "Paris is 18.0C."

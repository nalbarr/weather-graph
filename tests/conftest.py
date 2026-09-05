"""Shared test fixtures.

`mock_beeai_generation` replaces the Mellea-backed generation seam so the BeeAI backend's
generate -> validate -> repair -> execute path can be tested with **no Ollama and no network**.

Why mock here rather than at Mellea's backend: Mellea's `@generative` uses constrained decoding, and
its `DummyBackend` explicitly rejects that ("does not support constrained decoding"), while the real
generate path asserts backend-populated internals (`_generate_log`) that can't be faked from outside
without coupling to private APIs. The stable, supported seam is the generative function itself
(`nl_to_sparql`) plus the session factory (`get_session`) — patching both gives a deterministic mock
LLM while exercising all of our own code (requirements plumbing, repair loop, validation, execution).

The pydantic-ai and LangGraph backends don't need an equivalent monkeypatching fixture: their
generation step is a plain injected `generate(prompt) -> WeatherSparqlSpec` async callable (see
`weather_graph.agents.shared.generate_and_run`), so tests exercise the shared repair/retry logic by
passing a fake `generate` callable directly — see `tests/test_agents_shared.py`.
"""

from __future__ import annotations

import os

import pytest

from weather_graph.models import WeatherSparqlSpec

# Force the offline in-memory graph backend regardless of the developer's local .env
# (which may set GRAPH_BACKEND=qlever for the running demo) — tests must stay network-free.
os.environ["GRAPH_BACKEND"] = "memory"


class FakeGeneration:
    """A deterministic stand-in for the `nl_to_sparql` generative function.

    Returns queued `WeatherSparqlSpec`s in order and records each call, so tests can assert on
    the repair loop (e.g. invalid-then-valid) and on what was asked.
    """

    def __init__(self) -> None:
        self.responses: list[WeatherSparqlSpec] = []
        self.calls: list[dict] = []

    def queue(self, *specs: WeatherSparqlSpec) -> None:
        self.responses.extend(specs)

    def __call__(self, _session, requirements=None, strategy=None, question="", **_kw):
        self.calls.append({"question": question, "requirements": requirements})
        if not self.responses:
            raise AssertionError("FakeGeneration ran out of queued responses")
        return self.responses.pop(0)


@pytest.fixture
def mock_beeai_generation(monkeypatch: pytest.MonkeyPatch) -> FakeGeneration:
    """Patch the BeeAI/Mellea generation seam: no real session, deterministic generative output.

    Imports `mellea` lazily (inside the fixture, not at module scope) and skips cleanly when it
    isn't installed — `mellea`/`beeai-framework` are the optional `beeai` extra, so importing them
    at collection time would make every test run require them, defeating the point of demoting
    this backend to opt-in.
    """
    pytest.importorskip("mellea")
    pytest.importorskip("beeai_framework")
    from weather_graph.agents import beeai_generation

    fake = FakeGeneration()
    monkeypatch.setattr(beeai_generation, "get_session", lambda: object())
    monkeypatch.setattr(beeai_generation, "nl_to_sparql", fake)
    return fake

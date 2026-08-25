"""Shared test fixtures.

`mock_generation` replaces the Mellea-backed generation seam so the generate -> validate -> repair
-> execute path can be tested with **no Ollama and no network**.

Why mock here rather than at Mellea's backend: Mellea's `@generative` uses constrained decoding, and
its `DummyBackend` explicitly rejects that ("does not support constrained decoding"), while the real
generate path asserts backend-populated internals (`_generate_log`) that can't be faked from outside
without coupling to private APIs. The stable, supported seam is the generative function itself
(`nl_to_sparql`) plus the session factory (`get_session`) — patching both gives a deterministic mock
LLM while exercising all of our own code (requirements plumbing, repair loop, validation, execution).
"""

from __future__ import annotations

import os

import pytest

from weather_graph import generation
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
def mock_generation(monkeypatch: pytest.MonkeyPatch) -> FakeGeneration:
    """Patch the generation seam: no real session, deterministic generative output."""
    fake = FakeGeneration()
    monkeypatch.setattr(generation, "get_session", lambda: object())
    monkeypatch.setattr(generation, "nl_to_sparql", fake)
    return fake

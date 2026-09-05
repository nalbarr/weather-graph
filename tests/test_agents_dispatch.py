"""Tests for `weather_graph.agents.build_agent`'s backend dispatch (no LLM / no network).

Covers: default backend when `AGENT_BACKEND` is unset, explicit selection of each backend, a clear
error on an invalid value, and — the property this whole plan depends on — that selecting
`pydantic_ai`/`langgraph` never imports `beeai_framework`/`mellea` (the optional `beeai` extra).
That last check runs in a subprocess rather than in-process: Python caches imports in
`sys.modules` for the life of the process, so if any other test in the same session has already
imported `beeai_framework`/`mellea` (e.g. `test_agents_beeai.py`, when the `beeai` extra is
installed), an in-process check would pass or fail based on test order rather than on what
`build_agent` itself actually imports.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from weather_graph.agents import build_agent
from weather_graph.agents.langgraph_agent import LangGraphWeatherAgent
from weather_graph.agents.pydantic_ai_agent import PydanticAIWeatherAgent


def test_default_backend_is_pydantic_ai(monkeypatch):
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    assert isinstance(build_agent(), PydanticAIWeatherAgent)


def test_agent_backend_env_var_selects_langgraph(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    assert isinstance(build_agent(), LangGraphWeatherAgent)


def test_explicit_backend_overrides_env_var(monkeypatch):
    monkeypatch.setenv("AGENT_BACKEND", "langgraph")
    assert isinstance(build_agent(backend="pydantic_ai"), PydanticAIWeatherAgent)


def test_invalid_backend_raises(monkeypatch):
    monkeypatch.delenv("AGENT_BACKEND", raising=False)
    with pytest.raises(ValueError, match="nonsense"):
        build_agent(backend="nonsense")


@pytest.mark.parametrize("backend", ["pydantic_ai", "langgraph"])
def test_default_and_variant_backends_never_import_beeai_dependencies(backend):
    script = (
        "import sys\n"
        "from weather_graph.agents import build_agent\n"
        f"build_agent(backend={backend!r})\n"
        "leaked = sorted(m for m in sys.modules if m in ('beeai_framework', 'mellea'))\n"
        "assert not leaked, leaked\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "GRAPH_BACKEND": "memory"},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

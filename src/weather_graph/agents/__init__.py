"""Agent-backend dispatcher.

`build_agent(backend=None)` selects and lazily imports exactly one backend module based on
`AGENT_BACKEND` (env, default `"pydantic_ai"`) or an explicit override. The import is lazy per
backend so that choosing `"pydantic_ai"` or `"langgraph"` never imports `beeai_framework`/`mellea`
— those are optional (`uv sync --extra beeai`) precisely because the `"beeai"` backend is the
demoted, opt-in one (see `beeai_agent.py`).

Every backend module exposes `build_agent() -> object with async answer(question: str) -> str`,
so callers (e.g. `demo.py`) work identically regardless of which backend is selected.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shared import WeatherAgent

BACKENDS = ("pydantic_ai", "langgraph", "beeai")


def build_agent(backend: str | None = None) -> WeatherAgent:
    """Build the agent for `backend` (or `AGENT_BACKEND`, default `"pydantic_ai"`)."""
    backend = backend or os.environ.get("AGENT_BACKEND", "pydantic_ai")
    if backend not in BACKENDS:
        raise ValueError(f"Unknown AGENT_BACKEND {backend!r}; expected one of {BACKENDS}.")
    if backend == "pydantic_ai":
        from .pydantic_ai_agent import build_agent as _build
    elif backend == "langgraph":
        from .langgraph_agent import build_agent as _build
    else:
        from .beeai_agent import build_agent as _build
    return _build()

"""BeeAI RequirementAgent backend (opt-in legacy — see module docstring below for why).

Modernized from main.py's original `BeeAgent` + `OllamaChatModel` to the current API:
  - `RequirementAgent` (was `BeeAgent`)
  - `ChatModel.from_name("ollama:granite4:micro")` (was `OllamaChatModel(...)`)
A `ConditionalRequirement` forces the graph tool to run before the agent answers.

Demoted to opt-in behind `AGENT_BACKEND=beeai` (requires `uv sync --extra beeai`): this pairing —
BeeAI's own agent loop wrapping Mellea's instruct-validate-repair generation loop
(`beeai_generation.py`) — is measurably slower than the default `pydantic_ai_agent.py`/
`langgraph_agent.py`, since Mellea's `RejectionSamplingStrategy` can issue up to 3 sequential LLM
calls before validation even starts, on top of BeeAI's own loop. Kept working and unchanged in
behavior for anyone who wants BeeAI's/Mellea's specific requirement/validation ecosystem.
"""

from __future__ import annotations

import os

from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware

from .beeai_tools import weather_graph_tool
from .shared import WeatherAgent

AGENT_MODEL = os.environ.get("AGENT_MODEL", "ollama:granite4:micro")

_INSTRUCTIONS = (
    "You answer questions about city weather. You must obtain facts only by calling "
    "weather_graph_tool, which queries the weather knowledge graph. Never invent numbers; "
    "base every answer on the tool's returned rows, and mention the city values you used."
)


class BeeAIWeatherAgent:
    """Matches the `async answer(question) -> str` contract every backend exposes to demo.py."""

    def __init__(self, agent: RequirementAgent) -> None:
        self._agent = agent

    async def answer(self, question: str) -> str:
        response = await self._agent.run(question).middleware(GlobalTrajectoryMiddleware())
        for attr in ("answer", "result", "last_message"):
            msg = getattr(response, attr, None)
            text = getattr(msg, "text", None)
            if text:
                return text
        return str(response)


def build_agent() -> WeatherAgent:
    """Construct the weather RequirementAgent bound to Ollama granite4:micro."""
    llm = ChatModel.from_name(AGENT_MODEL)
    agent = RequirementAgent(
        llm=llm,
        tools=[weather_graph_tool],
        requirements=[
            ConditionalRequirement(weather_graph_tool, force_at_step=1, only_success_invocations=False)
        ],
        role="Weather Graph Analyst",
        instructions=_INSTRUCTIONS,
    )
    return BeeAIWeatherAgent(agent)

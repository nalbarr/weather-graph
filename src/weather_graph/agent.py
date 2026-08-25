"""BeeAI RequirementAgent assembly (principle P4 from the original main.py demo).

Modernized from main.py's `BeeAgent` + `OllamaChatModel` to the current API:
  - `RequirementAgent` (was `BeeAgent`)
  - `ChatModel.from_name("ollama:granite4:micro")` (was `OllamaChatModel(...)`)
A `ConditionalRequirement` forces the graph tool to run before the agent answers — the "requirement"
theme that motivated choosing RequirementAgent over a plain ReAct agent.
"""

from __future__ import annotations

import os

from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel

from .tools import weather_graph_tool

AGENT_MODEL = os.environ.get("AGENT_MODEL", "ollama:granite4:micro")

_INSTRUCTIONS = (
    "You answer questions about city weather. You must obtain facts only by calling "
    "weather_graph_tool, which queries the weather knowledge graph. Never invent numbers; "
    "base every answer on the tool's returned rows, and mention the city values you used."
)


def build_agent() -> RequirementAgent:
    """Construct the weather RequirementAgent bound to Ollama granite4:micro."""
    llm = ChatModel.from_name(AGENT_MODEL)
    return RequirementAgent(
        llm=llm,
        tools=[weather_graph_tool],
        requirements=[
            ConditionalRequirement(weather_graph_tool, force_at_step=1, only_success_invocations=False)
        ],
        role="Weather Graph Analyst",
        instructions=_INSTRUCTIONS,
    )

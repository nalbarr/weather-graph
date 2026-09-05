"""Runnable demo: NL weather questions answered via the graph.

Run: `uv run weather-graph` (requires Ollama running with the model set for the selected backend —
see `.env.example`). `AGENT_BACKEND` selects which agent implementation answers the questions:
`"pydantic_ai"` (default), `"langgraph"` (variant), or `"beeai"` (opt-in legacy, requires
`uv sync --extra beeai`) — see `docs/QUICKSTART.md` and `src/weather_graph/agents/`.
"""

from __future__ import annotations

import asyncio

from .agents import build_agent

QUESTIONS = [
    "What is the weather like in Chicago right now, and is it warm?",
    "Is Chicago one of the three hottest cities in the data?",
    "Is it currently raining or snowing in Chicago?",
]


async def run() -> None:
    agent = build_agent()
    for question in QUESTIONS:
        print(f"\n=== Q: {question}")
        answer = await agent.answer(question)
        print(f"A: {answer}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

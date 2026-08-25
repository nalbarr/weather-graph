"""Runnable demo: NL weather questions answered via the graph.

Run: `uv run weather-graph`  (requires Ollama running with `granite4:micro` pulled).
"""

from __future__ import annotations

import asyncio

from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware

from .agent import build_agent

QUESTIONS = [
    "What is the weather like in Chicago right now, and is it warm?",
    "Is Chicago one of the three hottest cities in the data?",
    "Is it currently raining or snowing in Chicago?",
]


def _answer_text(response: object) -> str:
    """Read the agent's final text across BeeAI response shapes."""
    for attr in ("answer", "result", "last_message"):
        msg = getattr(response, attr, None)
        text = getattr(msg, "text", None)
        if text:
            return text
    return str(response)


async def run() -> None:
    agent = build_agent()
    for question in QUESTIONS:
        print(f"\n=== Q: {question}")
        response = await agent.run(question).middleware(GlobalTrajectoryMiddleware())
        print(f"A: {_answer_text(response)}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

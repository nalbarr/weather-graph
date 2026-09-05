"""Flat, single-file version of the default demo (pydantic-ai on local Ollama granite4:micro).

Walks through the same steps as `src/weather_graph/agents/pydantic_ai_agent.py` + `demo.py`,
inlined into one file for anyone who wants to read the whole default path top-to-bottom without
jumping between modules. The reusable implementation lives in `src/weather_graph/`; this file only
re-derives the pydantic-ai-specific wiring (model + two agents), reusing the shared
validate/repair/relevance-retry contract from `weather_graph.agents.shared` rather than duplicating
it.

For the LangGraph variant or the opt-in BeeAI+Mellea legacy path (`AGENT_BACKEND=langgraph` /
`AGENT_BACKEND=beeai`), see `docs/QUICKSTART.md` and `src/weather_graph/agents/`.

Run: `uv run python main.py` (requires Ollama running with `granite4:micro`, or set
PYDANTIC_AI_MODEL in .env to a model you have).
"""

from __future__ import annotations

import asyncio
import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from weather_graph.agents.shared import (
    ANSWER_INSTRUCTIONS,
    GENERATION_REQUIREMENTS,
    generate_and_run,
)
from weather_graph.models import WeatherSparqlSpec

MODEL_NAME = os.environ.get("PYDANTIC_AI_MODEL", "granite4:micro")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


# 1. Point pydantic-ai at local Ollama via its OpenAI-compatible endpoint.
def _model() -> OpenAIChatModel:
    return OpenAIChatModel(
        MODEL_NAME, provider=OpenAIProvider(base_url=f"{OLLAMA_HOST.rstrip('/')}/v1", api_key="ollama")
    )


# 2. Structured target + 3. structured-output agent: NL -> validated WeatherSparqlSpec
#    (this is pydantic-ai's replacement for Mellea's @generative/IVR loop).
async def generate(prompt: str) -> WeatherSparqlSpec:
    agent = Agent(_model(), output_type=WeatherSparqlSpec, instructions=GENERATION_REQUIREMENTS)
    result = await agent.run(prompt)
    return result.output


# 4. Second agent, tool-free: answers only from the rows generate_and_run() already fetched by
#    running the real SPARQL query — "forced tool-first" by construction, not by asking nicely.
async def answer(question: str) -> str:
    payload = await generate_and_run(question, generate=generate)
    prompt = f"Question: {question}\n\nQuery executed: {payload['sparql']}\nRows: {payload['summary']}"
    result = await Agent(_model(), instructions=ANSWER_INSTRUCTIONS).run(prompt)
    return result.output


# 5. Run
async def main() -> None:
    print(await answer("What is the weather like in Chicago right now and is it warm?"))


if __name__ == "__main__":
    asyncio.run(main())

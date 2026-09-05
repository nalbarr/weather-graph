"""pydantic-ai backend (new default) — a minimal, typed agent on local Ollama granite4:micro.

Structured NL -> SPARQL generation uses pydantic-ai's `PromptedOutput(WeatherSparqlSpec)` (see
`_generate`), replacing Mellea's `@generative`/instruct-validate-repair loop; the generic
validate/repair/relevance-retry contract lives in `shared.py` so this backend behaves identically
to the LangGraph one on that front — only how each backend gets a `WeatherSparqlSpec` out of the
model differs.

`PromptedOutput` (plain JSON-in-text, parsed and schema-validated by pydantic-ai) rather than the
default tool-call-based structured output: verified live against local `granite4:micro` that the
default repeatedly exhausts pydantic-ai's own output-retry budget (`UnexpectedModelBehavior:
Exceeded maximum output retries`) — small local models are not reliably trained on OpenAI-style
function-calling well enough to satisfy it through Ollama's `/v1` translation layer, while
`PromptedOutput` (and `NativeOutput`, Ollama's own `response_format=json_schema`, which was also
tried but hung against this model/version) is far more compatible with a small quantized model. See
`docs/learning_plan_agents.md` for the full comparison.

"Always query before answering" is enforced by construction, not by asking the model nicely:
`answer()` always calls `shared.generate_and_run()` (which runs the real SPARQL query) before the
second, tool-free agent is ever asked to phrase a final answer — there is no tool the model could
choose to skip.
"""

from __future__ import annotations

import os

from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from ..models import WeatherSparqlSpec
from .shared import ANSWER_INSTRUCTIONS, GENERATION_REQUIREMENTS, WeatherAgent, generate_and_run

MODEL_NAME = os.environ.get("PYDANTIC_AI_MODEL", "granite4:micro")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# granite4:micro is a small local model: low temperature makes its output far more consistent, and
# a larger retries budget gives it more chances to satisfy pydantic-ai's own output-conformance
# retry loop (separate from -- and upstream of -- shared.py's SPARQL-specific validate/repair loop,
# which only ever sees an already schema-valid WeatherSparqlSpec).
_MODEL_SETTINGS = ModelSettings(temperature=0)
_GENERATION_RETRIES = 3


def _model() -> OpenAIChatModel:
    """Local Ollama, addressed via pydantic-ai's OpenAI-compatible provider (Ollama's own /v1 API)."""
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(base_url=f"{OLLAMA_HOST.rstrip('/')}/v1", api_key="ollama"),
    )


async def _generate(prompt: str) -> WeatherSparqlSpec:
    agent = Agent(
        _model(),
        output_type=PromptedOutput(WeatherSparqlSpec),
        instructions=GENERATION_REQUIREMENTS,
        model_settings=_MODEL_SETTINGS,
        retries=_GENERATION_RETRIES,
    )
    result = await agent.run(prompt)
    return result.output


class PydanticAIWeatherAgent:
    """Matches the `async answer(question) -> str` contract every backend exposes to demo.py."""

    async def answer(self, question: str) -> str:
        payload = await generate_and_run(question, generate=_generate)
        prompt = (
            f"Question: {question}\n\n"
            f"Query executed: {payload['sparql']}\n"
            f"Rows: {payload['summary']}"
        )
        agent = Agent(_model(), instructions=ANSWER_INSTRUCTIONS, model_settings=_MODEL_SETTINGS)
        result = await agent.run(prompt)
        return result.output


def build_agent() -> WeatherAgent:
    return PydanticAIWeatherAgent()

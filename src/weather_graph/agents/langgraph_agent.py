"""LangGraph backend (variant) — an explicit two-node graph on local Ollama granite4:micro.

Deliberate contrast with `pydantic_ai_agent.py`: instead of two sequential Python calls, this
expresses "always query before answering" as the *shape of the graph* — a linear
`START -> query -> answer -> END` — which is the idiomatic LangGraph way to guarantee a step runs
before another, rather than relying on the model's own tool-choice. Structured NL -> SPARQL
generation uses `ChatOllama.with_structured_output(WeatherSparqlSpec, method="json_mode")`; the
generic validate/repair/relevance-retry contract is the same `shared.generate_and_run` the
pydantic-ai backend uses.

`method="json_mode"` rather than the default `"json_schema"`: verified live against local
`granite4:micro` that the default (Ollama's own constrained JSON-schema decoding) hangs
indefinitely against this model/Ollama version, while `"json_mode"` (ask for JSON via the prompt,
parse + schema-validate the response) returns in a few seconds — the same failure mode
`pydantic_ai_agent.py` hit with pydantic-ai's `NativeOutput` (also JSON-schema-based) and solved
with `PromptedOutput` (also prompt-based JSON). See `docs/learning_plan_agents.md`.
"""

from __future__ import annotations

import os
from typing import TypedDict

from langchain_core.exceptions import OutputParserException
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from ..models import WeatherSparqlSpec
from .shared import ANSWER_INSTRUCTIONS, GENERATION_REQUIREMENTS, WeatherAgent, generate_and_run

MODEL_NAME = os.environ.get("LANGGRAPH_MODEL", "granite4:micro")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# json_mode doesn't send the schema as strictly as json_schema mode (see module docstring): unlike
# pydantic-ai's PromptedOutput, langchain-ollama's json_mode does NOT inject the Pydantic schema
# into the prompt on its own, so the required JSON shape has to be spelled out explicitly here or a
# small model (verified live: granite4:micro, deterministically at temperature=0) reliably omits a
# field it was never actually told about (e.g. `rationale`). A small internal retry budget on top
# covers the model still getting it wrong occasionally; upstream of -- and separate from --
# shared.py's SPARQL-specific validate/repair loop, which only ever sees an already schema-valid
# WeatherSparqlSpec.
_JSON_SHAPE = (
    'Respond with ONLY a JSON object with exactly these keys: "intent" (string), "sparql" '
    '(string), "rationale" (string, why this query answers the intent).'
)
_GENERATION_RETRIES = 3


def _llm() -> ChatOllama:
    return ChatOllama(model=MODEL_NAME, base_url=OLLAMA_HOST, temperature=0)


async def _generate(prompt: str) -> WeatherSparqlSpec:
    # with_structured_output()'s return type is generic (dict | BaseModel) at the langchain-core
    # type level; passing a Pydantic class as the schema is documented to always return an
    # instance of it, so the runtime type is trustworthy even though mypy can't narrow it.
    structured = _llm().with_structured_output(WeatherSparqlSpec, method="json_mode")
    full_prompt = f"{GENERATION_REQUIREMENTS}\n\n{_JSON_SHAPE}\n\n{prompt}"
    last_error: OutputParserException | None = None
    for _ in range(_GENERATION_RETRIES):
        try:
            result = await structured.ainvoke(full_prompt)
        except OutputParserException as exc:
            last_error = exc
            continue
        assert isinstance(result, WeatherSparqlSpec)
        return result
    assert last_error is not None
    raise last_error


class _State(TypedDict):
    question: str
    payload: dict
    answer: str


async def _query_node(state: _State) -> dict:
    payload = await generate_and_run(state["question"], generate=_generate)
    return {"payload": payload}


async def _answer_node(state: _State) -> dict:
    payload = state["payload"]
    prompt = (
        f"{ANSWER_INSTRUCTIONS}\n\n"
        f"Question: {state['question']}\n\n"
        f"Query executed: {payload['sparql']}\n"
        f"Rows: {payload['summary']}"
    )
    result = await _llm().ainvoke(prompt)
    return {"answer": result.content}


def _build_graph():
    graph = StateGraph(_State)
    graph.add_node("query", _query_node)
    graph.add_node("answer", _answer_node)
    graph.add_edge(START, "query")
    graph.add_edge("query", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


class LangGraphWeatherAgent:
    """Matches the `async answer(question) -> str` contract every backend exposes to demo.py."""

    def __init__(self) -> None:
        self._graph = _build_graph()

    async def answer(self, question: str) -> str:
        result = await self._graph.ainvoke({"question": question})
        return result["answer"]


def build_agent() -> WeatherAgent:
    return LangGraphWeatherAgent()

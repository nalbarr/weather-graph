# pydantic-ai analysis (new default agent backend)

Written while building `src/weather_graph/agents/pydantic_ai_agent.py`. Covers the API actually
used, pinned version, and — since this backend was verified live against local `granite4:micro`,
not just written and assumed correct — the real compatibility issue found and how it was resolved.

## Version

`pydantic-ai==2.40.0` (`pydantic-ai-slim` pulled in transitively), pinned in `pyproject.toml` as
`pydantic-ai>=2.40,<3`.

## Pointing at local Ollama

pydantic-ai has no dedicated "Ollama" model class; Ollama is addressed through its OpenAI-compatible
provider, since Ollama's `/v1/*` endpoints implement the OpenAI Chat Completions API shape:

```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(
    "granite4:micro",
    provider=OpenAIProvider(base_url="http://127.0.0.1:11434/v1", api_key="ollama"),
)
```

`api_key` is required by the client but unchecked by Ollama — any non-empty string works.

## Structured output: three mechanisms, one actually reliable against `granite4:micro`

pydantic-ai supports three ways to get a `BaseModel` out of `Agent.run()`, selected via
`output_type=`:

1. **Bare `output_type=WeatherSparqlSpec`** (default: tool-call-based structured output — the
   model is asked to call a synthetic `final_result` tool with the schema as its arguments).
   **Verified live: unreliable against `granite4:micro`.** Repeatedly hit
   `pydantic_ai.exceptions.UnexpectedModelBehavior: Exceeded maximum output retries` — the model
   either didn't call the tool at all ("Please return text or include your response in a tool
   call") or called it with malformed/incomplete arguments, and pydantic-ai's own internal
   output-retry loop (governed by `Agent(retries=...)`) couldn't recover within budget.
2. **`output_type=NativeOutput(WeatherSparqlSpec)`** (Ollama's own `response_format` /
   constrained JSON-schema decoding). **Verified live: hung indefinitely** against this
   model/Ollama version — the request never returned within several minutes. Not used.
3. **`output_type=PromptedOutput(WeatherSparqlSpec)`** (schema described in the prompt as text;
   response parsed as plain JSON and schema-validated afterward — no tool-calling, no
   provider-side constrained decoding). **Verified live: fast (single-digit seconds) and reliable
   for straightforward lookup questions.** This is what `pydantic_ai_agent.py` uses.

Even with `PromptedOutput`, one genuine limitation remains, verified live and not fully resolved:
for the harder of the 3 demo questions ("Is Chicago one of the three hottest cities?" — a
ranking/comparison question), `granite4:micro` sometimes echoes the JSON *schema* itself back
(`{"properties": {...}, "type": "object"}`) instead of an instance of it, exhausting the output-retry
budget. A custom `PromptedOutput(..., template=...)` explicitly forbidding this was tried and made
things *worse* (it started failing even on the easy question) — reverted. `LANGGRAPH_MODEL`'s
`json_mode` approach (see `langgraph_analysis.md`) turned out more robust for this specific question
against this specific model; see the `docs/learning_plan_agents.md` comparison table for the
concrete side-by-side. `retries=3` and `model_settings=ModelSettings(temperature=0)` are set on
both the generation and answer agents to reduce (not eliminate) this variance.

## Tool calling / "forced tool-first"

pydantic-ai has no direct equivalent to BeeAI's `ConditionalRequirement(force_at_step=1)`. Rather
than fight the model into reliably choosing to call a tool, `pydantic_ai_agent.py` doesn't expose
the graph query as an agent *tool* at all: `PydanticAIWeatherAgent.answer()` calls
`shared.generate_and_run()` (which runs the real SPARQL query) directly in Python, then constructs a
*second*, tool-free `Agent` whose only job is to phrase the final answer from the rows it's handed.
The guarantee is structural (Python always does the query before the second agent ever runs), not
behavioral (no reliance on the model's tool-choice) — arguably a *stronger* guarantee than BeeAI's
`ConditionalRequirement`, and simpler to reason about.

## `Agent` construction used

```python
agent = Agent(
    model,
    output_type=PromptedOutput(WeatherSparqlSpec),
    instructions=GENERATION_REQUIREMENTS,
    model_settings=ModelSettings(temperature=0),
    retries=3,
)
result = await agent.run(prompt)
spec = result.output  # WeatherSparqlSpec
```

The answer-phrasing agent is the same shape with no `output_type` (defaults to `str`).

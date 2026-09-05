# weather_graph agent-layer analysis

Written ahead of the PLAN_AGENTS.md refactor (BeeAI + Mellea demoted to opt-in; pydantic-ai
default + LangGraph variant added). Covers what was actually reusable, what was BeeAI-specific vs.
Mellea-specific, and the reference inventory that drove the `agents/` package split.

## What was reusable unchanged by any backend

- `models.WeatherSparqlSpec` — the structured NL→SPARQL target. Every backend's generation step
  fills this in via its own mechanism; none of them change its shape.
- `sparql.validate_query` / `sparql.run_query` / `sparql.distinct_values` — pure-Python, no LLM.
  These are the actual correctness gate; every backend's generation output passes through them
  unchanged.
- `graph_data.py` — the in-memory/QLever graph backend, untouched by this plan (orthogonal axis).
- The "worth retrying" relevance heuristic (was `tools._worth_retrying` / `_CATEGORICAL_FILTER_RE` /
  `_GUESSED_CITY_URI_RE`) and its corrective-feedback hint — genuinely backend-agnostic logic that
  had been living inside the BeeAI tool module only because that was the only backend that existed.

## BeeAI-specific vs. Mellea-specific (in the original `agent.py`/`generation.py`/`tools.py`)

| Piece | Specific to |
|---|---|
| `RequirementAgent`, `ConditionalRequirement`, `@tool`/`StringToolOutput`, `GlobalTrajectoryMiddleware` | BeeAI |
| `@generative`, `MelleaSession`, `start_session`, `RejectionSamplingStrategy` (the IVR loop) | Mellea |
| The validate→repair retry loop wrapping the generative call (`generate_spec`) | Written against Mellea's call signature, but the *shape* of the loop (generate, validate, retry with the error as feedback) is generic — this is what got extracted into `shared.generate_validated_spec` for the two new backends. |

Mellea's `RejectionSamplingStrategy(loop_budget=3)` means a single `generate_spec()` call can
itself issue up to 3 LLM round-trips before our own validate/repair loop even runs — stacked under
BeeAI's own agent loop. This is the concrete mechanism behind "BeeAI+Mellea is slower to test" and
the reason it was demoted rather than kept as a third equal option.

## Reference inventory (before the move)

```
src/weather_graph/tools.py:18:from .generation import generate_spec
src/weather_graph/agent.py:18:from .tools import weather_graph_tool
src/weather_graph/demo.py:12:from .agent import build_agent
tests/test_generation_mock.py:5:from weather_graph.generation import generate_spec
tests/test_generation_mock.py:8:from weather_graph.tools import answer_question
main.py:27:from weather_graph.generation import generate_spec
```

Plus two callers a plain grep for `weather_graph.generation`/`.tools`/`.agent` doesn't catch:
`tests/conftest.py` (patches `weather_graph.generation.get_session`/`nl_to_sparql` by object
reference, not by name) and `src/weather_graph/__init__.py`'s docstring ("Mellea + BeeAI"), which
would have silently gone stale.

**`main.py`'s fate (decided):** `main.py` was not just a caller of `agent.py` — it did its own
independent, inline BeeAI+Mellea wiring (a second copy of the same construction). Since it exists
specifically to be "a flat, readable walkthrough of the same steps for anyone reading the demo
top-to-bottom" and the *default* steps are changing, it was rewritten to walk through the new
default (pydantic-ai) inline, reusing `agents/shared.py` for the parts that aren't
pydantic-ai-specific (the validate/repair contract) rather than re-deriving those too. The BeeAI
walkthrough is still fully available — just as real, working code — via `AGENT_BACKEND=beeai` /
`make run-beeai`, not as a second flat file.

## Package layout adopted

```
src/weather_graph/agents/
  __init__.py            # build_agent(backend) dispatcher, lazy per-backend import
  shared.py              # generate_validated_spec / generate_and_run, worth_retrying,
                          # relevance_retry_hint, GENERATION_REQUIREMENTS, ANSWER_INSTRUCTIONS,
                          # WeatherAgent protocol
  pydantic_ai_agent.py    # new default
  langgraph_agent.py      # new variant
  beeai_agent.py          # opt-in legacy (moved from agent.py)
  beeai_tools.py          # opt-in legacy (moved from tools.py, now calls shared.worth_retrying/
                          # relevance_retry_hint instead of its own copies)
  beeai_generation.py     # opt-in legacy (moved from generation.py, unchanged behavior)
```

Mirrors the existing `neo4j/`/`kif/` subpackage convention (backend-specific code in its own
subpackage under `src/weather_graph/`) rather than bolting three agent implementations onto flat,
same-named modules.

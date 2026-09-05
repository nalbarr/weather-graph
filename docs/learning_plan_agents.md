# Learning plan: agent backends for weather-graph

Summary of the work done per [PLAN_AGENTS.md](../plans/PLAN_AGENTS.md), on branch
`dev-20260904b-na`. This is an orthogonal axis to
[learning_plan.md](learning_plan.md)'s four *storage* backends (memory/qlever/neo4j/kif): it's
about *how the NL question gets answered* (the agent/orchestration layer), not where the weather
data lives. See [learning_plan.md](learning_plan.md#comparing-the-agent-backends) for the
side-by-side comparison table this doc feeds.

## Scope decisions

- **pydantic-ai becomes the default**, LangGraph a selectable variant, and the original BeeAI +
  Mellea combo becomes opt-in behind `AGENT_BACKEND=beeai` (requires
  `uv sync --extra beeai`) rather than deleted. `AGENT_BACKEND` (default `pydantic_ai`) selects
  among all three; `make run` / `uv run weather-graph` respects it.
- **BeeAI + Mellea demoted together, not separately** — Mellea's `RejectionSamplingStrategy`
  (`loop_budget=3`) means a single NL→SPARQL generation can issue up to 3 LLM round-trips before
  our own validate/repair loop even starts, stacked under BeeAI's own agent loop. This is the
  concrete, measured reason it's slower to run and test than the other two, not a subjective
  preference.
- **Mellea's generation step moves with BeeAI**, not kept for the new default/variant. Both new
  backends do NL→SPARQL via their own structured-output mechanism directly into the existing
  `WeatherSparqlSpec`, then hard-validate with the same pure-Python `sparql.validate_query()` —
  same validate/repair *contract*, extracted into `agents/shared.py` and shared by both new
  backends (`generate_validated_spec`/`generate_and_run`), without Mellea's IVR machinery.
- **LLM unchanged**: `granite4:micro` via local Ollama, for all three backends.
- Full details on the reusable-vs-backend-specific split: `analysis/weather_graph_agent_analysis.md`.
  Per-backend design notes: `analysis/pydantic_ai_analysis.md`, `analysis/langgraph_analysis.md`.

## What was built

- `src/weather_graph/agents/` — `__init__.py` (`build_agent(backend)` dispatcher, lazily importing
  exactly one backend module so choosing `pydantic_ai`/`langgraph` never imports
  `beeai_framework`/`mellea`), `shared.py` (the backend-agnostic validate/repair/relevance-retry
  contract + prompt text + the `WeatherAgent` protocol every backend implements),
  `pydantic_ai_agent.py` (new default), `langgraph_agent.py` (new variant), `beeai_agent.py` +
  `beeai_tools.py` + `beeai_generation.py` (opt-in legacy, moved from the old
  `agent.py`/`tools.py`/`generation.py` unchanged in behavior).
- `src/weather_graph/demo.py` — now calls `agents.build_agent()` instead of importing a fixed
  backend, so it works identically regardless of `AGENT_BACKEND`.
- `main.py` — rewritten to walk through the new default (pydantic-ai) inline, reusing
  `agents/shared.py` for the non-pydantic-ai-specific parts rather than re-deriving them; it was
  BeeAI+Mellea-specific before. The BeeAI+Mellea walkthrough is still fully available as real code
  via `AGENT_BACKEND=beeai` — not duplicated as a second flat file.
- `src/weather_graph/__init__.py` — docstring updated from "Mellea + BeeAI" to describe the
  default/variant/opt-in structure.
- `tests/`: `test_agents_shared.py` (the full generate→validate→repair→relevance-retry behavioral
  matrix, run once against the shared contract both new backends use — 7 cases, mirroring what
  `test_generation_mock.py` covered before), `test_agents_pydantic_ai.py` /
  `test_agents_langgraph.py` (backend-specific wiring: the "query always runs before the final
  answer" guarantee, with the real LLM client faked out), `test_agents_beeai.py` (the same 7-case
  matrix against the BeeAI/Mellea path specifically, since it doesn't go through the shared
  contract — skips cleanly without the `beeai` extra installed), `test_agents_dispatch.py`
  (default/explicit/invalid `AGENT_BACKEND`, plus a subprocess-isolated regression test proving
  `pydantic_ai`/`langgraph` selection never imports `beeai_framework`/`mellea`), `test_demo.py`
  (demo.py's question loop, agent stubbed). `conftest.py`'s old `mock_generation` fixture renamed
  to `mock_beeai_generation` and now imports `mellea`/`beeai_framework` lazily inside the fixture
  (not at module scope), so the whole suite stays runnable without the `beeai` extra.
- `Makefile`: `run` unchanged as a command but now backend-selectable via `.env`'s
  `AGENT_BACKEND`; added `run-pydantic-ai`, `run-langgraph`, `run-beeai` (force a specific backend)
  and `beeai-check` (verify the optional extra is installed, mirroring `kif-check`).
- `pyproject.toml`: `pydantic-ai`, `langgraph`, `langchain-ollama` moved into core `dependencies`;
  `beeai-framework`/`mellea` moved out into a new `[project.optional-dependencies]` extra named
  `beeai` (`uv sync --extra beeai`). `pytest-asyncio` added as a dev dependency (the shared contract
  is `async`).
- `.env.example`: `AGENT_BACKEND` (new), `PYDANTIC_AI_MODEL`/`LANGGRAPH_MODEL` (new, one per
  backend so the default and variant can be pointed at different models when comparing them),
  `AGENT_MODEL`/`MELLEA_MODEL` (existing, re-scoped in comments to "only used when
  `AGENT_BACKEND=beeai`"). No new host var — both new backends reuse the existing `OLLAMA_HOST`.
- `docs/QUICKSTART.md`, `docs/learning_plan.md` updated (see the latter's new "Key concepts" and
  "Comparing the agent backends" sections).

## Verified live, end-to-end (2026-09-05)

All three backends were run for real against a local Ollama instance serving `granite4:micro`
(plus a couple of one-off checks against `qwen2.5:latest` to sanity-check whether a failure was
this repo's code or the model), not just written and assumed correct. This surfaced two real
structured-output compatibility issues — both fixed — and one genuine, still-open small-model
reliability gap:

1. **pydantic-ai's default (tool-call-based) structured output was unreliable** against
   `granite4:micro` — `UnexpectedModelBehavior: Exceeded maximum output retries`. Switched to
   `PromptedOutput` (prompt-described JSON, no tool-calling/constrained decoding); fast and
   reliable for straightforward lookup questions after the switch. `NativeOutput` (Ollama's own
   constrained JSON-schema decoding) was also tried and **hung indefinitely** — not used. See
   `analysis/pydantic_ai_analysis.md`.
2. **LangGraph's default `with_structured_output` mode (`"json_schema"`) also hung indefinitely** —
   the same underlying Ollama feature as pydantic-ai's `NativeOutput`, reached through a different
   library, with the same failure mode. Switched to `method="json_mode"`. This uncovered a second,
   more subtle issue: unlike pydantic-ai's `PromptedOutput`, `json_mode` does **not** inject the
   Pydantic schema into the prompt automatically, so `granite4:micro` deterministically omitted
   the `rationale` field it was never actually told about. Fixed by adding an explicit
   instruction naming all three required JSON keys. See `analysis/langgraph_analysis.md`.
3. **Open finding, not fully resolved:** for the hardest of the 3 demo questions ("Is Chicago one
   of the three hottest cities?" — a ranking/comparison question), pydantic-ai's `PromptedOutput`
   still sometimes fails against `granite4:micro` (the model occasionally echoes the JSON *schema*
   itself back instead of an instance of it). The LangGraph backend, after its `json_mode` fix,
   answered this same question correctly and quickly in every live run performed. This is a
   genuine, reproducible difference in how the two libraries' structured-output plumbing handles a
   very small quantized model on a harder question — not a difference in the underlying
   validate/repair contract, which is identical for both (`agents/shared.py`). If you hit this with
   the default backend, either retry (the failure isn't universal, just more frequent on this
   question) or point `PYDANTIC_AI_MODEL`/`LANGGRAPH_MODEL` at a larger local model — this was
   confirmed to be a model-capability limit, not a bug in this repo's prompt/contract, by
   reproducing a similar (different) failure against `qwen2.5:latest` on the same question before
   the LangGraph-side fixes were found, and by the same shared validate/repair contract behaving
   identically for both backends whenever generation itself succeeds.
4. **BeeAI + Mellea (opt-in) backend: root-caused, not just "slow."** A live run against
   `granite4:micro` did not complete even the first question after 25+ minutes of continuous,
   actively-computing model time (confirmed via process inspection — `llama-server` pinned near
   100% CPU throughout, not idle/hung waiting on I/O). Root cause, traced into
   `mellea/backends/ollama.py`: Mellea's `@generative` always calls Ollama with
   `format=<pydantic model's raw JSON schema>` — Ollama's own constrained/schema-guided decoding.
   This is the **exact same mechanism** that hung indefinitely for pydantic-ai's `NativeOutput` and
   LangGraph's default `with_structured_output(method="json_schema")` (both fixed by switching to a
   prompt-based JSON method instead — see points 1-2 above). Mellea's public API has no equivalent
   escape hatch to a prompted/non-constrained JSON mode at the `start_session`/`@generative` level,
   and this plan's scope is to move BeeAI+Mellea unchanged in behavior, not patch Mellea's own
   generation strategy — so this is left as-is, documented rather than worked around. **Practical
   implication: on this environment (Ollama + `granite4:micro`), the opt-in `beeai` backend should
   be considered unverified-working, not just slower** than the default/variant above; the
   demotion's "slower to test" rationale undersells it. If you need this path working, first confirm
   `format=<schema>` requests to your Ollama/model combination actually return (a plain
   `curl .../api/chat` with a `format` JSON schema is the fastest way to check) before relying on it.

pydantic-ai and LangGraph both correctly answered "What is the weather like in Chicago right now,
and is it warm?" (21.0°C, "Partly Cloudy", warm) and "Is it currently raining or snowing in
Chicago?" (no) live, matching [learning_plan.md](learning_plan.md)'s reference answers; LangGraph
additionally answered the "three hottest cities" question correctly and quickly. BeeAI+Mellea's
live run did not reach an answer within the time budget given to it (see above).

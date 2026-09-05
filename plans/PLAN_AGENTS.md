# PLAN_AGENTS.md

## Role
You are a systems architect and want to replace weather-graph's default agent stack — the
**BeeAI `RequirementAgent`** wrapping a **Mellea** `@generative`/IVR (instruct-validate-repair) NL→SPARQL
generation loop (`src/weather_graph/agent.py`, `generation.py`, `tools.py`) — with a much simpler,
popular, open-source "client agent" approach, while keeping the BeeAI+Mellea combo available as an
explicit, `.env`-gated opt-in rather than deleting it.

## Objectives

Decisions locked in before implementation (see "Decisions" below for the reasoning):

1. **New default backend: [pydantic-ai](https://ai.pydantic.dev/)** — typed, minimal, popular agent
   library from the Pydantic team; native structured-output support maps cleanly onto the existing
   `WeatherSparqlSpec` model, and it talks to Ollama via its OpenAI-compatible endpoint. Becomes the
   new default for `make run` / `uv run weather-graph`.
2. **New variant backend: LangChain / LangGraph** — the most widely adopted agent framework, used
   here as the deliberate contrast case (heavier, different tool-calling/graph-based design) to
   `pydantic-ai`'s minimal typed approach. Selectable via `.env`, not the default.
3. **Demote BeeAI + Mellea together** — one paired legacy approach, not two independent ones. Reason
   to demote: Mellea's `RejectionSamplingStrategy` (`generation.py`, `loop_budget=3`) means every NL
   question can trigger up to 3 sequential LLM round-trips before validation even starts, on top of
   BeeAI's own agent loop — measurably slower to run/test than a single structured-output call.
   Becomes opt-in behind an explicit `.env` flag; not run by default, and its dependencies
   (`beeai-framework`, `mellea`) move out of the default install.
4. **LLM stays `granite4:micro` via local Ollama for all three backends** — this plan changes the
   *agent/orchestration layer*, not the model. No change to `ollama pull granite4:micro`.
5. **Mellea's generation step is demoted together with BeeAI**, not kept for the new default/variant.
   The two new backends do NL→SPARQL via their own structured-output mechanism (pydantic-ai's
   `result_type=`, LangChain's `.with_structured_output()`) directly into the existing
   `WeatherSparqlSpec` model, then hard-validate with the existing pure-Python `validate_query()`
   (`sparql.py`) and retry with corrective feedback on failure — the same validate/repair *contract*
   as today, just without Mellea's IVR machinery driving it.
6. **Makefile wiring**: `make run` keeps working unchanged as a command, but now dispatches on an
   `AGENT_BACKEND` `.env` var (`pydantic_ai` default if unset, `langgraph`, or `beeai`), plus explicit
   `run-pydantic-ai` / `run-langgraph` / `run-beeai` targets that force a specific backend regardless
   of `.env`. `run-beeai` depends on a new `beeai-check` target (mirrors `kif-check`) that verifies
   the `beeai-framework`/`mellea` extra is installed and fails fast with an install hint if not.

### Non-goals

- No change to `GRAPH_BACKEND` (memory/qlever), the Neo4j demo, or the KIF demo — this plan is scoped
  to the NL-question agent path (`weather-graph` / `main.py`) only.
- No change to the 3 fixed demo questions or the weather graph data model.
- Not deleting BeeAI/Mellea code — relocating and gating it.

## Agents

### Orchestrator
- Branch: this work happens on `dev-20260904b-na` (already checked out off latest `main`).
- The orchestrator manages five sub agents, each specialized on a task below, run in order (1 and 2
  and 3 can run in parallel once sub agent 1 is done; sub agent 4 depends on all three; sub agent 5
  depends on sub agent 4 having finished, since it reviews the repo — code and docs — as it will
  actually exist after implementation, not as designed up front).
- Will summarize the final design/verification as:
  - `docs/learning_plan_agents.md`
- Will update `Makefile`:
  - `run` gains the `AGENT_BACKEND` dispatch described above (default `pydantic_ai`).
  - New targets: `run-pydantic-ai`, `run-langgraph`, `run-beeai`, `beeai-check`.
- Will update `pyproject.toml`:
  - Add `pydantic-ai` and the LangGraph/LangChain-Ollama packages to core `dependencies` (required
    for the new default to work out of the box).
  - Move `beeai-framework` and `mellea` out of core `dependencies` into a new
    `[project.optional-dependencies]` extra (e.g. `beeai = ["beeai-framework>=0.1", "mellea>=0.1"]`),
    installed via `uv sync --extra beeai`.
- Will update `.env.example` — new vars, resolved now rather than deferred:
  - `AGENT_BACKEND="pydantic_ai"` (new) — selects `pydantic_ai` | `langgraph` | `beeai`; comment notes
    `beeai` requires `uv sync --extra beeai` first.
  - `PYDANTIC_AI_MODEL="granite4:micro"` (new) — plain Ollama model name for the pydantic-ai backend.
  - `LANGGRAPH_MODEL="granite4:micro"` (new) — plain Ollama model name for the LangGraph backend.
  - Both new backends reuse the existing `OLLAMA_HOST` var for where Ollama is running — no new host/
    base-URL var — even though pydantic-ai talks to Ollama's OpenAI-compatible endpoint and LangGraph
    (`ChatOllama`) talks to its native API, so the two backend modules each derive whatever URL shape
    they individually need from the one `OLLAMA_HOST` value (e.g. pydantic-ai appending `/v1`) rather
    than exposing that as separate env vars. Sub agents 2/3 confirm this derivation is correct for the
    library version pinned; if either library needs something `OLLAMA_HOST` genuinely can't express,
    that becomes a documented exception here, not a silent extra var invented later.
  - `AGENT_MODEL`/`MELLEA_MODEL` (existing) stay as-is, with their doc comments re-scoped to "only
    used when `AGENT_BACKEND=beeai`" — this plan gives every backend its own model var (mirroring the
    existing `AGENT_MODEL`/`MELLEA_MODEL` split for BeeAI/Mellea) specifically because the whole point
    of having a default + a variant is comparing them, which means being able to point them at
    different models independently rather than sharing one var.
  - No other new vars: `GRAPH_BACKEND`, `QLEVER_ENDPOINT`, `NEO4J_*` are untouched (out of scope, see
    Non-goals).
- Will update `docs/QUICKSTART.md` (`## Run` section and the "How the pieces map to the original
  demo" table) to document the three backends, how to select each via `AGENT_BACKEND`, and the
  `beeai` extra install step — mirroring how the Neo4j/KIF sections there each document their own
  setup + Makefile targets.
- Will update `docs/learning_plan.md` — the cross-backend narrative doc — since it currently
  describes the NL→SPARQL pipeline as fixed to "Mellea + BeeAI" (its `## 1. memory — the baseline`
  section) and only lists the three *storage*-backend learning plans (sparql/neo4j/kif) up top. This
  plan changes an orthogonal axis (the agent/orchestration layer sitting on top of whichever storage
  backend is configured), so `docs/learning_plan.md` needs:
  - **A new first section, `## Key concepts`**, placed before `## The driving context: Chicago's
    weather` — content supplied by sub agent 5 (see below), which reviews the full codebase and every
    `docs/learning_plan*.md` to extract the concepts a reader actually needs, checked for pedagogical
    ordering rather than assembled by guesswork.
  - Its opening paragraph and doc list to also reference `docs/learning_plan_agents.md`.
  - The "New concept" note under `## 1. memory — the baseline` (currently name-drops "Mellea +
    BeeAI") updated to describe the new default (pydantic-ai), noting the agent layer is now
    independently selectable via `AGENT_BACKEND` regardless of which storage backend (`memory`/
    `qlever`) is active.
  - **A new `## Comparing the agent backends` section**, in the same spirit and format as the
    existing `## Comparing the approaches` table (which contrasts SPARQL/RDF vs. Neo4j vs. KIF on
    data model, query language, storage owned, external service, etc.) — this plan's axis is
    orthogonal (agent/orchestration layer, not storage), so it gets its own table rather than adding
    columns to the storage-backend one. Rows sub agent 4 should fill in from what was actually built
    (not guessed up front):
    | | pydantic-ai (default) | LangGraph (variant) | BeeAI + Mellea (opt-in) |
    |---|---|---|---|
    | **Framework style** | Typed, minimal — structured output is a first-class return type | Graph-based orchestration over explicit nodes/edges | Requirement-driven agent loop + a separate structured-generation library |
    | **NL→SPARQL generation** | Native structured output (`result_type=`/`output_type=`) into `WeatherSparqlSpec` | `.with_structured_output()` into `WeatherSparqlSpec` | Mellea `@generative` + `RejectionSamplingStrategy` (IVR loop, up to 3 LLM calls before validation even starts) |
    | **Forced tool-first guarantee** | *(fill in from sub agent 2's design)* | *(fill in from sub agent 3's design — plain tool-calling vs. a small graph)* | `ConditionalRequirement(force_at_step=1)` |
    | **Dependencies installed by default** | Yes (core) | Yes (core) | No — `uv sync --extra beeai` opt-in |
    | **Relative LLM round-trips per question** | Fewest (single structured call, +1 on repair) | Comparable to pydantic-ai, framework overhead differs | Most (Mellea's own repair loop stacked under BeeAI's agent loop) — the concrete reason this approach was demoted |
    | **Where it shines in a real project** | You want the smallest, typed surface and don't need a broader agent-orchestration ecosystem | You're already invested in LangChain/LangGraph elsewhere, or need explicit multi-step graph control | You need BeeAI's/Mellea's specific requirement/validation ecosystem and can tolerate the extra latency |
    Sub agent 4 fills in the two `*(fill in ...)*` cells from what sub agents 2/3 actually designed,
    and corrects/fills any other cell where reality (post-implementation) diverges from this draft —
    the same "verified, not guessed" discipline `learning_plan_neo4j.md`/`learning_plan_kif.md` used
    for their own comparisons.
  - A `## See also` entry linking `plans/PLAN_AGENTS.md` and
    `analysis/weather_graph_agent_analysis.md`, matching the existing entries for
    PLAN_NEO4J/PLAN_KIF.
  Scope note: `docs/learning_plan.md`'s existing storage-backend comparison (`memory`/`qlever`/
  `neo4j`/`kif`) is untouched — this adds a second, independent comparison section for the
  orthogonal agent-backend axis, rather than folding one into the other.

### Sub agent 1
- Focused on understanding the *current* agent implementation end to end — what's BeeAI-specific,
  what's Mellea-specific, and what's already backend-agnostic and reusable as-is.
- Inputs:
  - `main.py`, `src/weather_graph/__init__.py`, `agent.py`, `generation.py`, `tools.py`, `demo.py`,
    `models.py`, `sparql.py` (specifically `validate_query`/`run_query`), `tests/test_generation_mock.py`,
    `tests/conftest.py`
- Outputs:
  - `analysis/weather_graph_agent_analysis.md` covering:
    - What's reusable unchanged by any backend: `models.WeatherSparqlSpec`, `sparql.validate_query`,
      `sparql.run_query`, `graph_data.py`, the "worth retrying" relevance-retry heuristic currently in
      `tools.answer_question`.
    - What's BeeAI-specific (`RequirementAgent`, `ConditionalRequirement`, `@tool`/`StringToolOutput`,
      `GlobalTrajectoryMiddleware`) vs. Mellea-specific (`@generative`, `MelleaSession`,
      `RejectionSamplingStrategy`).
    - A proposed package layout under `src/weather_graph/agents/` (mirroring how `neo4j/` and `kif/`
      are already split into backend-specific subpackages) with one module/subpackage per backend
      (`pydantic_ai_agent.py`, `langgraph_agent.py`, `beeai_agent.py` + the relocated
      `beeai_generation.py`/`beeai_tools.py`) plus a small dispatcher (e.g.
      `agents/__init__.py:build_agent(backend: str | None = None)`) that lazily imports only the
      selected backend's module, so `beeai_agent.py` never gets imported (and never needs
      `beeai-framework`/`mellea` installed) unless `AGENT_BACKEND=beeai`.
    - How `answer_question`'s relevance-retry heuristic (currently BeeAI-tool-specific in `tools.py`)
      should be shared across all three backends rather than duplicated.
    - **A full reference inventory** (`grep -rn` for `weather_graph.agent`/`.tools`/`.generation`
      and `from .agent`/`.tools`/`.generation` across `src/`, `tests/`, and `main.py`), listing every
      caller that will break or go stale once those modules move — confirmed today: `tools.py`
      (imports `generation`), `agent.py` (imports `tools`), `demo.py` (imports `agent`), `main.py`
      (imports `generation` directly, plus its own inline `beeai_framework`/`ChatModel` usage — it's
      a second, independent BeeAI+Mellea wiring, not just a caller of `agent.py`), `tests/conftest.py`
      (patches `weather_graph.generation`), `tests/test_generation_mock.py` (imports `generation` and
      `tools`), and `src/weather_graph/__init__.py`'s docstring ("Mellea + BeeAI"). Explicitly decide
      and record `main.py`'s fate — it's the flat single-file walkthrough referenced by
      `docs/QUICKSTART.md`'s `## Run` section, so leaving it silently pointed at the demoted backend
      after `weather-graph` moves to pydantic-ai would be a real (undocumented) behavior mismatch
      between the two entry points. Recommend one of: (a) update `main.py` to walk through the new
      default (pydantic-ai) instead, (b) update it to call `agents.build_agent()` like `demo.py` does,
      or (c) keep it as an explicit, clearly-labeled BeeAI+Mellea-only walkthrough gated the same way
      as `run-beeai` — pick one and say why, don't leave it ambiguous for sub agent 4.

### Sub agent 2
- Focused on researching **pydantic-ai** as the new default: its `Agent`/tool-calling API, structured
  output (`result_type=`/`output_type=`, whichever the pinned version uses), and how to point it at a
  local Ollama `granite4:micro` (OpenAI-compatible base URL vs. any native Ollama provider it ships).
- Inputs:
  - pydantic-ai docs/source (installed package or public docs)
  - `analysis/weather_graph_agent_analysis.md` (sub agent 1's output) for what shape the tool/spec
    needs to match
- Outputs:
  - `analysis/pydantic_ai_analysis.md` covering:
    - Minimal `Agent` construction pointed at Ollama `granite4:micro`, pinned version.
    - How to get `WeatherSparqlSpec` as structured output for the NL→SPARQL step (replacing Mellea's
      `@generative`), and how to expose `run_query`/`validate_query` as an `Agent` tool (replacing
      BeeAI's `@tool`).
    - Concrete proposed design for `src/weather_graph/agents/pydantic_ai_agent.py`.

### Sub agent 3
- Focused on researching **LangChain / LangGraph** as the variant backend: `ChatOllama` (or the
  OpenAI-compatible client) pointed at local `granite4:micro`, tool-calling/tool-binding, and
  structured output for `WeatherSparqlSpec`.
- Inputs:
  - LangChain/LangGraph docs/source
  - `analysis/weather_graph_agent_analysis.md` (sub agent 1's output)
- Outputs:
  - `analysis/langgraph_analysis.md` covering:
    - Whether a plain LangChain tool-calling agent suffices or a small LangGraph graph is warranted
      for "always call the weather tool before answering" (the same forced-tool-first requirement
      `ConditionalRequirement` currently enforces in BeeAI) — pick the simplest construct that
      preserves that guarantee.
    - Concrete proposed design for `src/weather_graph/agents/langgraph_agent.py`.

### Sub agent 4
- Focused on implementing the design proposed by sub agents 1-3: the actual backend split, Makefile
  wiring, dependency changes, **and a full revisit of `src/` and `tests/` coverage** — every caller
  from sub agent 1's reference inventory resolved (not just `demo.py`), and every backend carrying
  the same depth of test coverage the current BeeAI+Mellea path has today, not just a thin smoke test
  for the two new ones.
- Inputs:
  - `analysis/weather_graph_agent_analysis.md`, `analysis/pydantic_ai_analysis.md`,
    `analysis/langgraph_analysis.md`
- Outputs — `src/` (full sweep, not just the new package):
  - `src/weather_graph/agents/` package:
    - `__init__.py` — `build_agent(backend: str | None = None)` dispatcher reading `AGENT_BACKEND`
      (default `"pydantic_ai"`), lazily importing only the selected backend module, raising a clear
      error on an unrecognized `AGENT_BACKEND` value.
    - `shared.py` (or similar) — the backend-agnostic pieces sub agent 1 identified: relevance-retry
      heuristic, shared tool description/instructions text.
    - `pydantic_ai_agent.py` — new default, per sub agent 2's design.
    - `langgraph_agent.py` — new variant, per sub agent 3's design.
    - `beeai_agent.py` (+ relocated Mellea generation module) — the existing BeeAI+Mellea approach,
      moved here unchanged in behavior, only imported when `AGENT_BACKEND=beeai`.
  - `src/weather_graph/demo.py` updated to call `agents.build_agent()` instead of importing
    `agent.build_agent` directly, so it works for all three backends.
  - `main.py` updated per sub agent 1's explicit recommendation on its fate (see sub agent 1) — not
    left silently pointed at a module path that no longer exists or a demoted backend.
  - `src/weather_graph/__init__.py` docstring updated (currently "Mellea + BeeAI") to describe the
    new default + variant + opt-in structure.
  - Old `src/weather_graph/agent.py`, `generation.py`, `tools.py` removed once every caller from sub
    agent 1's inventory has been repointed at `agents/` (no dangling imports; verify with the same
    `grep -rn` sub agent 1 used, re-run clean).
- Outputs — `tests/` (full parity across all three backends, not just the two new ones):
  - `tests/conftest.py`: rename/rescope the existing `mock_generation` fixture to the BeeAI+Mellea
    seam it actually mocks (e.g. `mock_beeai_generation`), and add equivalent offline mock fixtures
    for the pydantic-ai and LangGraph generation seams identified by sub agents 2/3 — every backend's
    tests must stay LLM-free and network-free, matching the existing invariant.
  - `tests/test_agents_pydantic_ai.py`, `tests/test_agents_langgraph.py`, and the BeeAI+Mellea
    successor to `tests/test_generation_mock.py` (e.g. `tests/test_agents_beeai.py`) each carry **the
    same behavioral test matrix**, not a reduced smoke test — mirroring every case
    `tests/test_generation_mock.py` covers today: valid-on-first-try generation, invalid→valid repair,
    give-up after max repairs, end-to-end tool/agent execution against the real in-memory graph, retry
    on an empty categorical-literal mismatch, no retry on a genuinely-empty non-categorical result, and
    retry on a guessed-subject-URI. Skip cleanly (not fail) when a backend's optional dependency isn't
    installed (the `beeai` extra), mirroring how `test_neo4j.py`/`test_kif.py`/`test_sparql_qlever.py`
    skip without their live dependency.
  - `tests/test_agents_dispatch.py` (new) — covers `agents/__init__.py` itself: default backend when
    `AGENT_BACKEND` is unset, explicit selection of each of the three values, a clear error on an
    invalid value, and — importantly — a regression test proving that selecting `pydantic_ai` or
    `langgraph` never imports `beeai_framework`/`mellea` (e.g. assert those names are absent from
    `sys.modules` after dispatch, or run this test in an environment where the `beeai` extra is
    deliberately not installed), so the "optional/opt-in" property in the Objectives is actually
    enforced, not just documented.
  - `tests/test_demo.py` (new, or extend existing) — smoke-tests `demo.py`'s question loop against
    each of the three `AGENT_BACKEND` values with the agent itself mocked/stubbed (no real LLM calls),
    confirming the dispatch wiring works end-to-end from the entry point, not just from `agents/`
    directly.
  - Completion bar: `uv run pytest` and `uv run ruff check .` pass clean across the **whole repo**
    (not just the new/changed files) with no `AGENT_BACKEND` set (default path) — confirm this as an
    explicit verification step, mirroring how PLAN_NEO4J/PLAN_KIF's live-verification sections were
    recorded in their `docs/learning_plan_*.md`.
  - `Makefile`, `pyproject.toml`, `.env.example` changes as described under Orchestrator above.
  - `docs/QUICKSTART.md` `## Run` section and the "How the pieces map" table updated for the new
    default + variant + opt-in beeai path.

### Sub agent 5
- Focused on extracting a `## Key concepts` section for the *front* of `docs/learning_plan.md` — a
  reader landing there today gets the driving example and a step-by-step tour before ever being told
  what ideas they're supposed to walk away with. This closes that gap, and doubles as a pedagogy
  review of the whole `docs/learning_plan*.md` set now that a fifth backend axis (agents) exists
  alongside the four storage backends.
- Runs **last**, after sub agent 4, so it reviews the codebase and docs as they actually ended up,
  not as designed on paper — concepts and ordering get corrected against reality, not guessed from
  the plan.
- Inputs:
  - All of `src/weather_graph/` as it exists post-implementation (RDF/`memory`+`qlever`, `neo4j/`,
    `kif/`, the new `agents/` package), `model/weather.ttl`.
  - Every learning-plan doc: `docs/learning_plan.md` (its own existing "taught sequence" and
    "Comparing the approaches" table), `docs/learning_plan_sparql.md`, `docs/learning_plan_neo4j.md`,
    `docs/learning_plan_kif.md`, and the new `docs/learning_plan_agents.md`.
  - `docs/QUICKSTART.md` and the four `plans/PLAN_*.md` docs, for what each port's own stated
    objective/"new concept" was, so extracted concepts stay traceable to a real source rather than
    invented.
- Outputs:
  - The `## Key concepts` section content for `docs/learning_plan.md` (Orchestrator inserts it as the
    first section): a short, ordered list — one or two sentences per concept, each pointing at *where*
    it's taught in depth (a `## N. ...` step, a comparison-table row, or a linked learning-plan doc) —
    covering, at minimum, one concept per axis actually taught by this repo: triples/triple patterns
    (RDF), a query language bound to in-process vs. served data (`memory`→`qlever`), labeled property
    graphs vs. triples (Neo4j), a semantic-mapping layer over an existing store with no data of its
    own (KIF), structured LLM output into a typed spec (`WeatherSparqlSpec`), the
    generate→validate→repair contract that's backend-independent, and the instruct-validate-repair
    (IVR) loop specifically as the concrete case study in why an approach can be *correct* but too
    slow (BeeAI+Mellea's demotion). Order these from most foundational to most specialized, matching
    (or, if it finds a better order, deliberately revising) the existing step 0-4 sequence.
  - A short pedagogy-check note (can live inline as an HTML comment or a closing subsection in
    `docs/learning_plan.md`, sub agent 5's call) flagging anything found while reviewing that's
    genuinely out of order or unexplained-before-use across the doc set — e.g. a term used in step 2
    that's only defined in step 4 — and either fixing it directly or explicitly listing it as a
    follow-up if fixing it is out of this plan's scope (e.g. it lives in a doc this plan doesn't
    otherwise touch, like `learning_plan_sparql.md`).
  - Explicitly **not** a duplicate of the `## Comparing the approaches` / `## Comparing the agent
    backends` tables — `## Key concepts` is the short glossary/map a reader skims first; the
    comparison tables are the detailed side-by-side a reader consults once they know what they're
    comparing.

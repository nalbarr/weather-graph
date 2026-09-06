# drawio_scenarios_analysis.md — Makefile/scenario inventory + shared style guide

This is **Sub agent 1**'s output for `plans/PLAN_DRAWIO.md`. It is the catalog every other
diagram-producing sub agent (2-5) and the orchestrator build from — do not re-derive the import
chains or invent new names/colors; copy the "Shared style guide" section below verbatim.

Inputs read in full: `Makefile`, `pyproject.toml` (`[project.scripts]`), `docs/run_book.md`
(especially its "Quick reference: what needs what" table), `docs/QUICKSTART.md`, `.env.example`,
and every module under `src/weather_graph/` reachable from the six scenarios' entry points (traced
by reading actual source, not filenames — see "Import chains" per scenario below).

---

## 1. Full Makefile target inventory

21 targets total (`help` plus 20 real ones), each classified as a **scenario entry point**
(what a reader runs to *start* a scenario), a **precondition** (lifecycle/setup step a scenario
needs first), or **neither** (a general utility, e.g. `help`). `[project.scripts]` entry points
(`uv run weather-graph*`) are listed too since three of the six scenarios have no wrapping
Makefile target at all — that asymmetry matters for sub agents 3-5's diagrams.

| Target | What it does | Precondition of | Entry point for |
|---|---|---|---|
| `help` | Prints target list from `##` comments | — | — (utility only) |
| `run` | `uv run weather-graph` — `AGENT_BACKEND` from `.env` (default `pydantic_ai`) | — | Default pydantic-ai scenario |
| `run-pydantic-ai` | `AGENT_BACKEND=pydantic_ai uv run weather-graph` | — | Default pydantic-ai scenario (forced) |
| `run-langgraph` | `AGENT_BACKEND=langgraph uv run weather-graph` | — | LangGraph scenario |
| `run-beeai` | `AGENT_BACKEND=beeai uv run weather-graph` (depends on `beeai-check`) | — | BeeAI scenario |
| `beeai-check` | Verifies `beeai_framework`/`mellea` importable | BeeAI scenario | — |
| `test` | `uv run pytest` — offline test suite | — | Test scenario (excluded from sequence diagrams, objective 3) |
| `qlever-cli-check` | Verifies the `qlever` CLI is installed | `qlever-index`/`qlever-up` (transitively: KIF/QLever, KIF-LLM) | — |
| `qlever-index` | `qlever get-data && qlever index` — stage `model/*.ttl`, build local index | KIF/QLever scenario, KIF-LLM scenario | — |
| `qlever-up` | `qlever start` — starts the local SPARQL server | KIF/QLever scenario, KIF-LLM scenario | — |
| `qlever-status` | `qlever status` — shows process/server status | KIF/QLever scenario, KIF-LLM scenario (verification step) | — |
| `qlever-health` | `curl`s `QLEVER_ENDPOINT` with an ASK query (depends on `qlever-cli-check`) | KIF/QLever scenario, KIF-LLM scenario (verification step) | — |
| `qlever-down` | `qlever stop` | — (teardown, not a precondition) | — |
| `neo4j-cli-check` | Verifies `neo4j-cli` is installed | `neo4j-up`/`neo4j-health`/`neo4j-migrate` (transitively: Neo4j scenario) | — |
| `neo4j-up` | `neo4j-cli docker create ...` — starts a local Neo4j instance | Neo4j scenario | — |
| `neo4j-health` | `neo4j-cli query "RETURN 1 AS ok"` (depends on `neo4j-cli-check`) | Neo4j scenario (verification step) | — |
| `neo4j-migrate` | `neo4j-cli query --rw --env .env < data/neo4j/weather.cypher` | Neo4j scenario | — |
| `neo4j-status` | `neo4j-cli docker list \| grep ...` | Neo4j scenario (verification step) | — |
| `neo4j-down` | `neo4j-cli docker stop/delete` | — (teardown, not a precondition) | — |
| `kif-check` | Verifies `kif_lib` importable | KIF/QLever scenario | — |
| `kif-llm-check` | Verifies the vendored `kif_llm_store` package imports | KIF-LLM scenario | — |

`[project.scripts]` entry points (`pyproject.toml`), none wrapped by a dedicated Makefile target
except indirectly via `run`/`run-pydantic-ai`/`run-langgraph`/`run-beeai` (all of which invoke
`weather-graph`, never the other three):

| Script name | Module:function | Entry point for |
|---|---|---|
| `weather-graph` | `weather_graph.demo:main` | Default pydantic-ai, LangGraph, BeeAI scenarios (same script, `AGENT_BACKEND` selects the backend) |
| `weather-graph-kif` | `weather_graph.demo_kif:main` | KIF/QLever scenario — **no Makefile target wraps this**; run directly |
| `weather-graph-kif-llm` | `weather_graph.demo_kif_llm:main` | KIF-LLM scenario — **no Makefile target wraps this**; run directly |
| `weather-graph-neo4j` | `weather_graph.demo_neo4j:main` | Neo4j scenario — **no Makefile target wraps this**; run directly |

This confirms objective 3's "considered and rejected" note: `qlever-index`/`qlever-up`/
`qlever-status`/`qlever-health`/`qlever-cli-check` and `neo4j-up`/`neo4j-migrate`/`neo4j-health`/
`neo4j-status`/`neo4j-cli-check` are all lifecycle/precondition steps for their scenario, never
scenarios in their own right — no separate diagram is warranted for any of them; they appear as a
precondition note inside their scenario's sequence diagram (sub agents 4 and 5).

---

## 2. Confirmed scenario list (6)

Matches `docs/run_book.md`'s "Quick reference: what needs what" table **exactly**, minus the
`uv run pytest` row (excluded per objective 3 — no interesting runtime sequence to draw). No
deviation to justify.

1. **Default pydantic-ai run** — `uv run weather-graph`
2. **LangGraph run** — `make run-langgraph`
3. **BeeAI run** — `make run-beeai`
4. **KIF/QLever demo** — `uv run weather-graph-kif`
5. **KIF-LLM demo** — `uv run weather-graph-kif-llm`
6. **Neo4j demo** — `uv run weather-graph-neo4j`

---

## 3. Per-scenario detail (entry point, backend values, modules, services)

All import chains below were read from the actual source files listed, not inferred from names.

### 3.1 Default pydantic-ai run

- **Entry point:** `uv run weather-graph` (equivalently `make run` or `make run-pydantic-ai`)
- **Backend values:** `AGENT_BACKEND=pydantic_ai` (the `.env.example` default; `run-pydantic-ai`
  forces it explicitly), `GRAPH_BACKEND=memory` (the `.env.example` default)
- **Import chain:**
  `demo.py:run()` → `agents/__init__.py:build_agent()` (lazy-imports on `AGENT_BACKEND`) →
  `agents/pydantic_ai_agent.py:build_agent()` → `PydanticAIWeatherAgent.answer()` →
  `agents/shared.py:generate_and_run()` → `agents/pydantic_ai_agent.py:_generate()` (a
  `pydantic_ai.Agent` with `PromptedOutput(WeatherSparqlSpec)`, via `OpenAIChatModel`/
  `OpenAIProvider` pointed at `f"{OLLAMA_HOST}/v1"`) → `models.py:WeatherSparqlSpec` (schema) →
  `agents/shared.py:generate_validated_spec()` (validate/repair loop, up to 1 repair, plus
  pydantic-ai's own internal output-conformance retries, `retries=3`) → `sparql.py:run_query()`
  (`validate_query()` then execute) → `graph_data.py:get_graph()` (`GRAPH_BACKEND=memory` →
  `_load_memory_graph()` parses `model/weather.ttl`) → back in `PydanticAIWeatherAgent.answer()`,
  a second tool-free `pydantic_ai.Agent` phrases the final answer from the row summary.
- **External services touched:** Ollama only (at least 2 HTTP calls per question: spec
  generation, answer phrasing; more on repair/output-retry).
- **Notable runtime behavior for the diagram:** the documented output-retry flake
  (`pydantic_ai.exceptions.UnexpectedModelBehavior: Exceeded maximum output retries (3)`,
  `docs/run_book.md` §2) is real and observed, not hypothetical — worth an alt/loop fragment.

### 3.2 LangGraph run

- **Entry point:** `make run-langgraph`
- **Backend values:** `AGENT_BACKEND=langgraph` (forced), `GRAPH_BACKEND=memory` (default;
  unchanged by this scenario)
- **Import chain:**
  `demo.py:run()` → `agents/__init__.py:build_agent()` → `agents/langgraph_agent.py:build_agent()`
  → `LangGraphWeatherAgent.__init__` builds a compiled `StateGraph` (`START → query → answer →
  END`) → `LangGraphWeatherAgent.answer()` invokes the graph:
  - `_query_node` → `agents/shared.py:generate_and_run()` → `agents/langgraph_agent.py:_generate()`
    (`ChatOllama.with_structured_output(WeatherSparqlSpec, method="json_mode")`, up to
    `_GENERATION_RETRIES=3` internal retries) → `agents/shared.py:generate_validated_spec()` →
    `sparql.py:run_query()` → `graph_data.py:get_graph()` (memory backend, `model/weather.ttl`).
  - `_answer_node` → `ChatOllama.ainvoke()` directly (no `Agent`/tool wrapper, unlike the
    pydantic-ai backend's second `Agent`).
- **External services touched:** Ollama only.

### 3.3 BeeAI run

- **Entry point:** `make run-beeai` (Makefile dependency: `beeai-check`)
- **Backend values:** `AGENT_BACKEND=beeai` (forced); `GRAPH_BACKEND=memory` (default, unchanged)
- **Import chain:**
  `demo.py:run()` → `agents/__init__.py:build_agent()` → `agents/beeai_agent.py:build_agent()`
  (`RequirementAgent(llm=ChatModel.from_name(AGENT_MODEL), tools=[weather_graph_tool],
  requirements=[ConditionalRequirement(weather_graph_tool, force_at_step=1)])`) →
  `BeeAIWeatherAgent.answer()` calls `agent.run(question).middleware(GlobalTrajectoryMiddleware())`
  → BeeAI's `RequirementAgent` loop invokes the tool →
  `agents/beeai_tools.py:weather_graph_tool()` → `answer_question()` →
  `agents/beeai_generation.py:generate_spec()` (Mellea: `get_session()` /
  `start_session(backend_name="ollama", model_id=MELLEA_MODEL)`, `@generative nl_to_sparql`
  with `RejectionSamplingStrategy(loop_budget=3)`) → `sparql.py:validate_query()` (repair loop,
  up to 1 repair) → back in `agents/beeai_tools.py:answer_question()` →
  `sparql.py:run_query()` → `graph_data.py:get_graph()` (memory backend) → tool result returned to
  the `RequirementAgent`, which then produces the final answer via its own `ChatModel` call.
- **External services touched:** Ollama, reached through **two independent client paths** in the
  same run — `beeai_framework.backend.ChatModel` (agent loop / final answer) and Mellea's own
  `MelleaSession` (spec generation) — worth showing as two distinct Ollama-bound arrows/lifelines
  or an annotation, not collapsed into one.
- **Notable runtime behavior for the diagram:** Mellea's `@generative` always requests Ollama's
  constrained JSON-schema decoding (`format=<schema>`) — documented hang risk
  (`docs/QUICKSTART.md` Troubleshooting; verified live to hang indefinitely against this repo's
  `granite4:micro`/Ollama combination) — worth an annotation, not a fragment (it's a hang, not a
  retry loop with a defined end).

### 3.4 KIF/QLever demo

- **Entry point:** `uv run weather-graph-kif` (no Makefile target; preconditions:
  `make qlever-cli-check && make qlever-index && make qlever-up`, then `make kif-check`)
- **Backend values:** N/A — this scenario **bypasses `agents/` and `graph_data.py` entirely**; no
  `AGENT_BACKEND`/`GRAPH_BACKEND` in play. It reads `QLEVER_ENDPOINT` directly (default
  `http://localhost:7011`).
- **Import chain:**
  `demo_kif.py:run()` → `kif/kif.py:city_temperature()` / `city_condition()` /
  `hottest_cities()` → `kif/kif.py:get_store()` (`kif_lib.Store("sparql", endpoint,
  mapping=WeatherMapping())`) → `kif/mapping.py:WeatherMapping` (a `SPARQL_Mapping` bridging
  `wx:temperatureC`/`wx:condition` triples to `wd.temperature`/`wd.weather_history` statements) →
  `kb.filter(...)` compiles to a SPARQL query executed against the QLever endpoint.
  `kif/base.py:KIFBackend` (the structural Protocol) is **not** imported by this scenario —
  only `demo_kif_llm.py` uses it (§3.5).
- **External services touched:** QLever only (HTTP/SPARQL). No Ollama — fixed queries, no LLM,
  confirmed by `docs/run_book.md` §5b ("No LLM in this path at all").

### 3.5 KIF-LLM demo

- **Entry point:** `uv run weather-graph-kif-llm` (no Makefile target; preconditions:
  `uv sync --extra kif-llm`, `make kif-llm-check`, `make qlever-cli-check && make qlever-index &&
  make qlever-up` for the SPARQL column, a live Ollama with `KIF_LLM_MODEL` pulled for the LLM
  column)
- **Backend values:** N/A, same as §3.4 — no `AGENT_BACKEND`/`GRAPH_BACKEND`. Reads
  `QLEVER_ENDPOINT` (SPARQL side) and `KIF_LLM_MODEL`/`OLLAMA_HOST` (LLM side) directly.
- **Import chain:**
  `demo_kif_llm.py:run()` imports **both** `kif/kif.py` and `kif/llm_store.py` as
  `BACKENDS: list[tuple[str, KIFBackend]]`, each conforming to `kif/base.py:KIFBackend`
  (`typing.Protocol`, structural — modules themselves satisfy it, no instantiation). For each of
  the 3 fixed questions, both backends are called through the identical
  `city_temperature`/`city_condition`/`hottest_cities` shape:
  - `[SPARQL/QLever]` column → `kif/kif.py` → same chain as §3.4 (QLever).
  - `[LLM Store]` column → `kif/llm_store.py:get_store()` (lazy-imports
    `kif/_vendor/kif_llm_store` — `nest_asyncio.apply()` runs at that import, hence the lazy
    deferral) → `Store("llm", Store("empty"), Search("empty"), llm_provider=LLM_Providers.OLLAMA,
    model_id=KIF_LLM_MODEL, base_url=OLLAMA_HOST, model_params={})` →
    `kif/wikidata_mapping.py:city_item()`/`CITY_ITEMS` (real Wikidata Q-IDs, distinct from
    `kif/kif.py`'s local `wx:cityN` IRIs) → `kb.filter(...)` → vendored
    `kif/_vendor/kif_llm_store/compiler/llm/filter_compiler.py` builds a prompt → Ollama via
    `langchain_ollama` (patched by `nest_asyncio`).
- **External services touched:** **both** QLever (HTTP/SPARQL, SPARQL column) and Ollama (HTTP,
  LLM column) in the same run, per question — the side-by-side comparison is the scenario's whole
  point (`docs/run_book.md` §5c; `plans/PLAN_KIF_LLM.md` objective 5), so both lifelines must
  appear, not be collapsed to one.

### 3.6 Neo4j demo

- **Entry point:** `uv run weather-graph-neo4j` (no Makefile target; preconditions:
  `make neo4j-cli-check`, `make neo4j-up`, `make neo4j-migrate`, optionally `make neo4j-health`)
- **Backend values:** N/A — separate demo, bypasses `agents/`/`graph_data.py`/`GRAPH_BACKEND`
  entirely (confirmed: `demo_neo4j.py` never imports `agents` or `graph_data`). Reads
  `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` directly via
  `neo4j/connection.py`.
- **Import chain:**
  `demo_neo4j.py:run()` → `neo4j/cypher.py:city_weather()` / `hottest_cities()` /
  `city_condition()` → `neo4j/cypher.py:_run()` → `neo4j/connection.py:get_driver()` (
  `GraphDatabase.driver(uri, auth=basic_auth(user, password))`, `.env` loaded via
  `neo4j/connection.py`'s own `load_dotenv()` call, deliberately not relying on BeeAI's incidental
  `.env` load) and `neo4j/connection.py:database()` → `driver.execute_query(text,
  parameters_=params, database_=database(), routing_="r")` over Bolt.
- **External services touched:** Neo4j only, over Bolt. No Ollama, no QLever — fixed,
  parameterized Cypher, confirmed by `neo4j/cypher.py`'s module docstring and `demo_neo4j.py`
  (no LLM import anywhere in this chain). This matches the "no LLM in this path" shape of the
  KIF/QLever scenario, confirmed by direct source inspection, not assumed from the plan's guess.

---

## 4. Component inventory (for the structure diagram, sub agent 2)

Every module/package, external service, and the *kind* of edge connecting them, derived from the
import tracing in §3. Edge-kind vocabulary is exactly 4 strings (objective 5): `in-process call`,
`HTTP`, `Bolt`, `subprocess/CLI` — use these strings verbatim as edge labels/kind tags.

| From | To | Edge kind | Notes |
|---|---|---|---|
| `demo.py` | `agents/__init__.py` | in-process call | `build_agent()` |
| `agents/__init__.py` | `agents/pydantic_ai_agent.py` | in-process call | lazy import, `AGENT_BACKEND=pydantic_ai` |
| `agents/__init__.py` | `agents/langgraph_agent.py` | in-process call | lazy import, `AGENT_BACKEND=langgraph` |
| `agents/__init__.py` | `agents/beeai_agent.py` | in-process call | lazy import, `AGENT_BACKEND=beeai` |
| `agents/pydantic_ai_agent.py` | `agents/shared.py` | in-process call | `generate_and_run()` |
| `agents/langgraph_agent.py` | `agents/shared.py` | in-process call | `generate_and_run()`, inside `_query_node` |
| `agents/beeai_agent.py` | `agents/beeai_tools.py` | in-process call | tool invocation via `RequirementAgent` |
| `agents/beeai_tools.py` | `agents/beeai_generation.py` | in-process call | `generate_spec()` |
| `agents/beeai_tools.py` | `agents/shared.py` | in-process call | reuses `worth_retrying`/`relevance_retry_hint` |
| `agents/beeai_generation.py` | `sparql.py` | in-process call | `validate_query()` |
| `agents/shared.py` | `models.py` | in-process call | `WeatherSparqlSpec` type |
| `agents/shared.py` | `sparql.py` | in-process call | `run_query()`, `validate_query()`, `distinct_values()` |
| `agents/beeai_tools.py` | `sparql.py` | in-process call | `run_query()` |
| `sparql.py` | `graph_data.py` | in-process call | `get_graph()` |
| `graph_data.py` | `model/weather.ttl` | in-process call | file parse, `GRAPH_BACKEND=memory` |
| `graph_data.py` | QLever | HTTP | `rdflib.SPARQLStore`, `GRAPH_BACKEND=qlever` (not exercised by any of the 6 default scenarios above, but a real code path) |
| `agents/pydantic_ai_agent.py` | Ollama | HTTP | `OpenAIChatModel`/`OpenAIProvider`, `{OLLAMA_HOST}/v1` |
| `agents/langgraph_agent.py` | Ollama | HTTP | `ChatOllama` |
| `agents/beeai_agent.py` | Ollama | HTTP | `beeai_framework.backend.ChatModel` |
| `agents/beeai_generation.py` | Ollama | HTTP | Mellea `MelleaSession(backend_name="ollama")` |
| `demo_kif.py` | `kif/kif.py` | in-process call | |
| `kif/kif.py` | `kif/mapping.py` | in-process call | `WeatherMapping` |
| `kif/kif.py` | QLever | HTTP | `kif_lib.Store("sparql", endpoint, ...)` |
| `demo_kif_llm.py` | `kif/kif.py` | in-process call | SPARQL/QLever column |
| `demo_kif_llm.py` | `kif/llm_store.py` | in-process call | LLM Store column |
| `demo_kif_llm.py` | `kif/base.py` | in-process call | `KIFBackend` Protocol (structural typing) |
| `kif/llm_store.py` | `kif/wikidata_mapping.py` | in-process call | `CITY_ITEMS`/`city_item()` |
| `kif/llm_store.py` | `kif/_vendor/kif_llm_store` | in-process call | lazy import (`nest_asyncio.apply()` side effect deferred) |
| `kif/_vendor/kif_llm_store` | Ollama | HTTP | via `langchain_ollama`, patched by `nest_asyncio` |
| `demo_neo4j.py` | `neo4j/cypher.py` | in-process call | |
| `neo4j/cypher.py` | `neo4j/connection.py` | in-process call | `get_driver()`, `database()` |
| `neo4j/connection.py` | Neo4j | Bolt | `driver.execute_query(..., routing_="r")` |
| `Makefile: qlever-index/qlever-up/qlever-down/qlever-status/qlever-health/qlever-cli-check` | QLever | subprocess/CLI | via the `qlever` CLI |
| `Makefile: neo4j-up/neo4j-migrate/neo4j-down/neo4j-status/neo4j-health/neo4j-cli-check` | Neo4j | subprocess/CLI | via the `neo4j-cli` CLI |
| `neo4j/connection.py` | `data/neo4j/weather.cypher` | — | not a runtime edge — `neo4j-migrate` loads this file via `neo4j-cli`, not via `neo4j/connection.py`; listed for completeness in §5's data-file inventory only |

---

## 5. Shared style guide (objective 5) — copy verbatim into diagrams 2-5

This section is the mechanically-checkable contract every sub agent 2-5 diagram must match, and
what the orchestrator's reconciliation pass checks against. Do not paraphrase names or pick
different colors — copy the exact strings/hex values below.

### 5.1 Canonical component names

One name per module/service/data-file, used verbatim as the shape label in every diagram. The
canonical name for every in-repo module is its path relative to `src/weather_graph/` — never a
prose paraphrase (e.g. always `agents/pydantic_ai_agent.py`, never "pydantic-ai backend").

| Canonical name | Kind |
|---|---|
| `demo.py` | CLI entry point |
| `demo_kif.py` | CLI entry point |
| `demo_kif_llm.py` | CLI entry point |
| `demo_neo4j.py` | CLI entry point |
| `agents/__init__.py` | backend implementation |
| `agents/shared.py` | backend implementation |
| `agents/pydantic_ai_agent.py` | backend implementation |
| `agents/langgraph_agent.py` | backend implementation |
| `agents/beeai_agent.py` | backend implementation |
| `agents/beeai_tools.py` | backend implementation |
| `agents/beeai_generation.py` | backend implementation |
| `models.py` | backend implementation |
| `sparql.py` | backend implementation |
| `graph_data.py` | backend implementation |
| `kif/kif.py` | backend implementation |
| `kif/mapping.py` | backend implementation |
| `kif/base.py` | backend implementation |
| `kif/llm_store.py` | backend implementation |
| `kif/wikidata_mapping.py` | backend implementation |
| `kif/_vendor/kif_llm_store` | backend implementation |
| `neo4j/connection.py` | backend implementation |
| `neo4j/cypher.py` | backend implementation |
| `Ollama` | external service |
| `QLever` | external service |
| `Neo4j` | external service |
| `model/weather.ttl` | data/model file |
| `data/neo4j/weather.cypher` | data/model file |

Non-component labels used in sequence diagrams (not part of the 4-kind table above, styled
separately per §5.3):
- The human actor lifeline is always labeled exactly `Developer (terminal)`.
- The triggering command (first message from the actor) uses the exact command string from §2/§3
  (e.g. `uv run weather-graph`, `make run-langgraph`), verbatim, including flags/env prefixes.

### 5.2 Fill-color assignment per component kind

Exactly 4 kinds, each with a fixed fill/stroke/font color (all hex, all mxGraph `fillColor`/
`strokeColor`/`fontColor` style attributes):

| Kind | `fillColor` | `strokeColor` | `fontColor` |
|---|---|---|---|
| CLI entry point | `#DAE8FC` | `#6C8EBF` | `#000000` |
| backend implementation | `#D5E8D4` | `#82B366` | `#000000` |
| external service | `#FFE6CC` | `#D79B00` | `#000000` |
| data/model file | `#E1D5E7` | `#9673A6` | `#000000` |

These are the same 4 fill/stroke pairs draw.io ships as its default palette swatches (blue/green/
orange/purple), chosen deliberately so a reviewer opening the file sees familiar, distinct colors
without a custom palette — and so "external service" (orange) reads at a glance against
"backend implementation" (green), per objective 2's structure-diagram requirement.

Component diagram legend/key box (sub agent 2 only, per its Outputs) must reproduce this exact
4-row table (kind → swatch → meaning) on the same page as the diagram.

### 5.3 Actor/lifeline style and spacing (sequence diagrams, sub agents 3-5)

- **Actor lifeline** (`Developer (terminal)`, always the leftmost lifeline): `fillColor=#F5F5F5`,
  `strokeColor=#666666`, `fontColor=#333333` — a 5th style, not one of the 4 kinds above, since
  the human/terminal is not a repo component.
- **Component lifelines**: header box uses the fill/stroke/font color from §5.2 matching that
  component's kind (e.g. `demo.py`'s lifeline header is CLI-entry-point blue).
- **Lifeline header box shape**: `rounded=1;arcSize=8`, `width=160`, `height=40`,
  `whiteSpace=wrap`, `verticalAlign=middle`, `align=center`, `strokeWidth=2`.
- **Lifeline vertical line** (drawn from the bottom of each header box to the diagram's bottom
  margin): `strokeColor=#666666`, `strokeWidth=1`, `dashed=1`, `dashPattern=4 4`.
- **Horizontal spacing**: lifelines are centered 220px apart (center-to-center); the leftmost
  lifeline (`Developer (terminal)`) is centered at `x=120`.
- **Vertical spacing**: the first message arrow is 80px below the header boxes' bottom edge;
  each subsequent message arrow is 60px below the previous one.
- **Message/edge styling by kind** (edge-kind vocabulary from §4 — `in-process call`, `HTTP`,
  `Bolt`, `subprocess/CLI` — each gets its own color, independent of the endpoint node colors, so
  edge kind is legible regardless of which two components it connects):

  | Edge kind | `strokeColor` | `strokeWidth` | `dashed` | `endArrow` |
  |---|---|---|---|---|
  | in-process call | `#000000` | `1` | `0` | `block` |
  | HTTP | `#1A73E8` | `1.5` | `0` | `open` |
  | Bolt | `#9673A6` | `1.5` | `0` | `open` |
  | subprocess/CLI | `#666666` | `1` | `1` | `open` |

- **Return arrows** (response flowing back up a lifeline, when drawn explicitly): same
  `strokeColor` as the originating call's edge kind, but `dashed=1` regardless of the table above.
- **Alt/opt/loop fragments** (e.g. the pydantic-ai output-retry loop, §3.1; Mellea's repair loop,
  §3.3): a dashed frame rectangle, `rounded=0`, `dashed=1`, `strokeColor=#666666`,
  `fillColor=none`, with the fragment label (e.g. `loop [up to 3 attempts]`) in the top-left
  corner at font size 10, italic.
- **Precondition/lifecycle note** (e.g. `qlever-up`/`neo4j-migrate` steps): a single note box
  above the first message, `fillColor=#FFF2CC`, `strokeColor=#D6B656`, `fontColor=#000000`,
  listing the precondition commands verbatim from §1/§3 — not a lifeline, not a separate diagram
  (objective 3).

### 5.4 Base font and stroke settings (all diagrams)

- **Font family**: `Helvetica` (mxGraph `fontFamily=Helvetica`) for every shape and edge label in
  every diagram — component diagram and all 5 sequence diagrams alike.
- **Font sizes**: `fontSize=12` for component/lifeline box labels (bold, `fontStyle=1`);
  `fontSize=11` for sequence-diagram message/edge labels; `fontSize=10` for annotations, fragment
  labels, and the legend/key box text.
- **Stroke widths**: `strokeWidth=2` for every component/lifeline box border; edge stroke widths
  follow the per-edge-kind table in §5.3 (`in-process call`/`subprocess/CLI` = 1,
  `HTTP`/`Bolt` = 1.5); the dashed lifeline line itself is `strokeWidth=1`.
- **Canvas**: `gridSize=10`, grid-snapped shape positions/sizes (all `x`/`y`/`width`/`height`
  values in this guide and expected in the diagrams are multiples of 10 or 20 for exactly this
  reason).

---

## 6. Notes for sub agents 2-5

- Sub agent 2 (component diagram): build directly from §4's edge table and §5's style guide. Every
  row in §4 becomes one edge; every distinct "From"/"To" cell that is an in-repo module or external
  service becomes one box, styled per §5.2, labeled with the exact canonical name from §5.1.
- Sub agents 3-5 (sequence diagrams): build each scenario's lifeline sequence directly from its
  §3 subsection's import chain, in the order calls actually happen (not alphabetical, not by file
  layout) — the numbered chain in each §3.x subsection is already in call order. Precondition
  commands (from §1) become a single note box per §5.3, not their own lifeline or diagram.
- The KIF-LLM scenario (§3.5) is the one case where two component lifelines run "side by side" for
  the same question rather than one linear chain — both `kif/kif.py` and `kif/llm_store.py` receive
  the same three calls per question; draw both, not one collapsed lifeline.

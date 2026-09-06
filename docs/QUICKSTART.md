# Quick Start — weather-graph (uv + Ollama granite4:micro)

Standalone demo: natural-language weather questions → validated SPARQL over an RDF graph, answered
by a selectable **agent backend** on local **Ollama `granite4:micro`**. Default is
**pydantic-ai** (a minimal, typed agent); **LangGraph** is a selectable variant; the original
**BeeAI RequirementAgent + Mellea** combo is still available as an explicit opt-in. See
[learning_plan_agents.md](learning_plan_agents.md) for why, and the full comparison.

The running example throughout this guide — and every backend below — is the same 8-city weather
dataset (Chicago, Paris, London, Cairo, Tokyo, Oslo, Nairobi, Sydney) answering the same 3 fixed
questions: Chicago's current temperature/condition, the 3 hottest cities, and whether it's raining
or snowing in Chicago. Each backend section changes *how* those questions get answered — data
model, query language, infrastructure — never *what* is being asked. See
[learning_plan.md](learning_plan.md) for the full walkthrough and a side-by-side comparison of the
four approaches.

## Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| **uv** ≥ 0.11 | Python + package manager | `uv --version` |
| **Ollama** | Local model backend | `ollama --version` |

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv not installed
ollama pull granite4:micro                         # the model every agent backend uses by default
```

## Setup

```bash
cd weather-graph
uv sync                 # installs pydantic-ai, langgraph, langchain-ollama, rdflib (+ dev) --
                         # NOT beeai-framework/mellea, see "BeeAI + Mellea" below
cp .env.example .env    # defaults already point at the pydantic-ai backend on granite4:micro
```

`uv sync` creates `.venv/` and a reproducible `uv.lock`. `.venv/` and `.env` are gitignored.

## Run

```bash
# The packaged demo (three questions), using AGENT_BACKEND from .env (default: pydantic-ai)
uv run weather-graph

# Or the flat single-file walkthrough of the default (pydantic-ai) path
uv run python main.py

# Force a specific backend regardless of .env
make run-pydantic-ai   # default: minimal typed agent, structured output straight into
                        # WeatherSparqlSpec
make run-langgraph     # variant: explicit query -> answer graph
make run-beeai          # opt-in legacy: BeeAI RequirementAgent + Mellea (needs the beeai extra
                         # installed first -- see below)
```

Requires Ollama running with the model set for the selected backend (`PYDANTIC_AI_MODEL` /
`LANGGRAPH_MODEL` / `AGENT_MODEL`+`MELLEA_MODEL` in `.env`). Every backend does the same thing:
generate a validated `WeatherSparqlSpec` from the question, run it against the weather graph, and
answer from the rows — "query before answering" is guaranteed by construction (pydantic-ai: two
sequential calls in Python; LangGraph: the compiled graph's linear shape; BeeAI: a
`ConditionalRequirement`) rather than left to the model's own tool-choice. See
[learning_plan_agents.md](learning_plan_agents.md) for the full design and what was verified live.

### BeeAI + Mellea (opt-in legacy backend)

The original approach this repo shipped with — kept working (unchanged code), not deleted, but
demoted out of the default install and default backend. Verified live against Ollama +
`granite4:micro`: this backend did not complete even the first demo question after 25+ minutes of
continuous, actively-computing model time. Root cause (traced into
`mellea/backends/ollama.py`): Mellea's `@generative` always requests Ollama's constrained
JSON-schema decoding (`format=<schema>`), the same Ollama feature that also hung for pydantic-ai's
`NativeOutput` and LangGraph's default `with_structured_output` mode — but unlike those two
libraries, Mellea's public API has no prompt-based alternative to fall back to. See
[learning_plan_agents.md](learning_plan_agents.md#verified-live-end-to-end-2026-09-05) for the full
finding. If your Ollama/model combination handles `format=<schema>` requests without hanging, this
backend should still work as designed — check with a plain `curl .../api/chat` + a `format` JSON
schema first.

```bash
uv sync --extra beeai   # installs beeai-framework + mellea
make beeai-check        # verify the extra is actually installed
AGENT_BACKEND=beeai uv run weather-graph   # or: make run-beeai
```

## Weather graph storage backend

`GRAPH_BACKEND` in `.env` selects where the weather graph lives. `memory` and `qlever` store the
exact same RDF triples and answer with the exact same `wx:` predicates — moving from one to the
other changes *where the data lives*, not what it looks like:

- **`memory`** (default) — parses `model/*.ttl` into an in-memory `rdflib.Graph()` at process start.
  No external services; this is what `uv run pytest` always uses regardless of `.env`.
- **`qlever`** — the same triples, now served by a real [QLever](https://github.com/ad-freiburg/qlever)
  SPARQL endpoint (`QLEVER_ENDPOINT`, default `http://localhost:7011`) instead of an in-process
  graph, via rdflib's `SPARQLStore`. This is the step where "the graph" first becomes a service you
  start/stop rather than something parsed at import time.

To run against QLever:

```bash
uv tool install qlever          # the qlever CLI (see data/qlever/Qleverfile for config)
make qlever-index               # stage model/*.ttl into data/qlever/ and build the index (once, or
                                 # whenever model/*.ttl changes)
make qlever-up                  # start the local SPARQL server on QLEVER_ENDPOINT
# set GRAPH_BACKEND="qlever" in .env, then run/test as usual
make qlever-down                # stop it when done
```

`data/qlever/Qleverfile` defaults to `SYSTEM = native`, which needs the compiled `qlever-index` /
`qlever-server` binaries (`brew tap qlever-dev/qlever && brew install qlever-dev/qlever/qlever` on
macOS — note this trusts a third-party tap). Switch `SYSTEM = docker` in the Qleverfile to use
QLever's official Docker image instead, if you'd rather not trust that tap and have a working local
Docker daemon.

See [learning_plan_sparql.md](learning_plan_sparql.md) for the full design/rationale and what was
verified live against a real QLever instance.

## Neo4j backend (separate demo, fixed Cypher, no LLM)

Neo4j is the first genuine change of *shape*, not just location: the same 8 cities become labeled
property graph nodes (`(:City {name, temperatureC, condition, ...})`) instead of RDF triples, and
Cypher replaces SPARQL as the query language — see
[learning_plan.md](learning_plan.md#comparing-the-approaches) for how the two data models compare
side by side.

`uv run weather-graph-neo4j` runs the same 3 questions as `uv run weather-graph`, but answers them
with fixed, parameterized Cypher queries (`src/weather_graph/neo4j/cypher.py`) against a Neo4j
instance — no LLM, no query generation. This is a separate entry point from the RDF demo; it does
not go through `GRAPH_BACKEND`.

```bash
uv tool install neo4j-cli   # https://github.com/neo4j-labs/neo4j-cli — all neo4j-* targets below
                             # go through this, never raw docker/python
make neo4j-up                # start a local Neo4j instance (bolt://localhost:7687), password
                              # pinned to .env's NEO4J_PASSWORD
make neo4j-migrate           # load model/weather.ttl's 8 cities into it (data/neo4j/weather.cypher
                              # via neo4j-cli query)
make neo4j-health             # confirm it's actually reachable and answering queries
uv run weather-graph-neo4j
make neo4j-down               # stop and remove the instance when done
```

`NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` in `.env` point both the Python
driver (`src/weather_graph/neo4j/connection.py`, which loads `.env` itself via `python-dotenv` —
used by `demo_neo4j.py`/tests) and `neo4j-cli` itself at the instance — `NEO4J_USERNAME` (not
`NEO4J_USER`) is required because that's the exact name `neo4j-cli` reads from a `.env` file.
This whole flow (`neo4j-up` → `neo4j-health` → `neo4j-migrate` → `weather-graph-neo4j` →
`neo4j-down`) has been run for real end-to-end against a live local instance — see
[learning_plan_neo4j.md](learning_plan_neo4j.md#verified-live-end-to-end-2026-08-27) for what was
verified and the bugs that were found and fixed along the way. See also
[PLAN_NEO4J.md](../plans/PLAN_NEO4J.md) for the full design.

## KIF backend (separate demo, fixed queries, no LLM)

KIF changes the *lens*, not the storage: it reuses the exact same QLever server from the section
above — no new copy of the data, no new index — but maps `wx:` triples into Wikidata-shaped
statements (`Item`/`Property`/`Statement`) at query time. Of the four backends here, it's the one
that adds a semantic-integration layer on top of an existing store rather than owning its own.

`uv run weather-graph-kif` runs the same 3 questions as `uv run weather-graph`, but answers them
with fixed [KIF](https://github.com/IBM/kif) (IBM's Knowledge Integration Framework) queries
(`src/weather_graph/kif/kif.py`) — no LLM, no query generation. Unlike the Neo4j backend, KIF
doesn't run its own server: it reuses the *existing* QLever server via a `SPARQL_Mapping`
(`src/weather_graph/kif/mapping.py`) that bridges `wx:` triples to KIF's Wikidata-shaped statement
model, reusing real `wd.temperature`/`wd.weather_history` properties loosely.

```bash
make qlever-cli-check && make qlever-index && make qlever-up   # if not already running
make kif-check                                                  # verify kif_lib is installed
uv run weather-graph-kif
```

No new `.env` keys — KIF reads the same `QLEVER_ENDPOINT` the RDF/QLever backend already uses.
This whole flow has been run for real end-to-end against a live QLever server — see
[learning_plan_kif.md](learning_plan_kif.md) for what was verified, and
[PLAN_KIF.md](../plans/PLAN_KIF.md) / [ibm_kif_analysis.md](../analysis/ibm_kif_analysis.md) for
the full design, including two decisions that were corrected only after live-testing against the
real `kif_lib` API.

### KIF LLM Store (second KIF backend, same interface, an LLM instead of SPARQL)

Proves KIF's `Store`/`kb.filter()` interface is itself an abstraction layer: the exact same call
shape as `kif.py` above, but answered by a local Ollama model (`granite4:micro`) synthesizing
Wikidata-shaped statements instead of a SPARQL query — no local data of its own, and it will not
agree with the SPARQL answers (that mismatch is the point; see
[learning_plan_kif_llm.md](learning_plan_kif_llm.md)). Upstream `kif-llm-store` isn't
pip-installable as documented (broken package metadata, several real bugs), so a small patched
copy is vendored in-repo (`src/weather_graph/kif/_vendor/`) — the one genuinely new dependency,
`nest-asyncio`, is the `kif-llm` extra.

```bash
uv sync --extra kif-llm   # installs nest-asyncio; the LLM_Store code itself is vendored
make kif-llm-check        # verify the vendored package imports
ollama pull granite4:micro   # if you haven't already (KIF_LLM_MODEL in .env, default granite4:micro)
make qlever-cli-check && make qlever-index && make qlever-up   # for the SPARQL side of the comparison
uv run weather-graph-kif-llm
```

See [learning_plan_kif_llm.md](learning_plan_kif_llm.md) for real captured output (three runs,
showing the LLM side's answers vary run to run and never match the synthetic data) and
[PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md) for the full design, including the upstream-packaging
problem and how it was resolved.

## Test (no LLM / no network)

```bash
uv run pytest          # offline (no Ollama needed); tests/test_neo4j.py skips without a live Neo4j
uv run ruff check .
```

Coverage without a live model:
- **Validators + graph execution** (`test_sparql.py`, `test_models.py`) — the pure-Python rules in
  `sparql.py` (SELECT-only, `LIMIT` present, known predicates, parseable SPARQL) are what every
  backend's generated SPARQL is checked against, regardless of how it was generated.
- **Shared generate → validate → repair → relevance-retry contract** (`test_agents_shared.py`) —
  the full 7-case behavioral matrix (valid-first-try, invalid→valid repair, give-up after max
  repairs, end-to-end execution, retry on an empty categorical mismatch, no retry without one, retry
  on a guessed subject URI) run once against `agents/shared.py`'s `generate_and_run`, which both the
  pydantic-ai and LangGraph backends delegate to.
- **Per-backend wiring** (`test_agents_pydantic_ai.py`, `test_agents_langgraph.py`) — proves each
  backend's own "query always runs before the final answer" guarantee, with the LLM client faked out.
- **BeeAI + Mellea** (`test_agents_beeai.py` + the `mock_beeai_generation` fixture in
  `conftest.py`) — the same 7-case matrix run against the BeeAI/Mellea path specifically (it has its
  own repair loop, not the shared one above); skips cleanly without the `beeai` extra installed.
- **Dispatch** (`test_agents_dispatch.py`, `test_demo.py`) — `AGENT_BACKEND` selection, and proof
  that selecting `pydantic_ai`/`langgraph` never imports `beeai_framework`/`mellea`.

## How the pieces map (default: pydantic-ai)

| Step | File | Role |
|------|------|------|
| 1 Structured target | `models.py` | `WeatherSparqlSpec` |
| 2 Shared validate/repair/relevance-retry | `agents/shared.py` | `generate_validated_spec` / `generate_and_run` |
| 3 Structured-output generation | `agents/pydantic_ai_agent.py` | `Agent(..., output_type=PromptedOutput(WeatherSparqlSpec))` |
| 4 Tool-free answer agent | `agents/pydantic_ai_agent.py` | A second `Agent` sees only the executed query's rows |
| 5 Backend dispatch + async run | `agents/__init__.py`, `demo.py` / `main.py` | `agents.build_agent()` → `agent.answer(question)` |

The LangGraph variant (`agents/langgraph_agent.py`) and the opt-in BeeAI+Mellea legacy path
(`agents/beeai_agent.py` + `beeai_tools.py` + `beeai_generation.py`) follow the same 5-step shape
with a different mechanism at steps 3-4 — see
[learning_plan.md](learning_plan.md#comparing-the-agent-backends).

Want the visual/architectural view before running anything? See
[learning_plan_drawio.md](learning_plan_drawio.md) — a draw.io component diagram of the whole
system plus a sequence diagram per scenario above, under `diagrams/`.

## Troubleshooting

- **Model not found** → `ollama pull granite4:micro` (or set `PYDANTIC_AI_MODEL` /
  `LANGGRAPH_MODEL` / `AGENT_MODEL`+`MELLEA_MODEL` in `.env` to a model you have, e.g.
  `qwen2.5:latest` — each backend has its own model var).
- **`pydantic_ai.exceptions.UnexpectedModelBehavior: Exceeded maximum output retries`** (default
  backend) → verified live: `granite4:micro` occasionally struggles with the harder of the 3 demo
  questions ("three hottest cities") specifically. Retry, or set `AGENT_BACKEND=langgraph` /
  point `PYDANTIC_AI_MODEL` at a larger local model — see
  [learning_plan_agents.md](learning_plan_agents.md) for what was verified.
- **`beeai-check` / `run-beeai` fails with "not installed"** → run `uv sync --extra beeai` first.
- **`run-beeai` / `AGENT_BACKEND=beeai` just hangs** → verified live on this repo's own setup, not
  hypothetical: Mellea's Ollama backend always requests `format=<json schema>` (constrained
  decoding), which hung indefinitely against local `granite4:micro`. Check whether your
  Ollama/model combination handles `format=<schema>` requests at all before assuming it's just
  slow — see [learning_plan_agents.md](learning_plan_agents.md#verified-live-end-to-end-2026-09-05).
- **BeeAI/Mellea API drift** → pinned here to `beeai-framework 0.1.82`, `mellea 0.7.0`. If you bump
  them, re-check `response.answer.text` (read defensively in `agents/beeai_agent.py`) and the
  `@tool` surface.
- **`GRAPH_BACKEND=qlever` but `run_query()`/the agent can't connect** → confirm `make qlever-up` is
  actually running (`make qlever-status` or `curl $QLEVER_ENDPOINT` with a `query=` param) and that
  `QLEVER_ENDPOINT` in `.env` matches `[server] PORT` in `data/qlever/Qleverfile`.
- **`qlever index`/`qlever start` fail under `SYSTEM = docker`** → confirms nothing about your data;
  it means the local Docker daemon isn't reachable. Either start it, or switch to
  `SYSTEM = native` (see above) to avoid the Docker dependency entirely.
- **`kif-llm-check` / `uv run weather-graph-kif-llm` fails with "not installed"** → run
  `uv sync --extra kif-llm` first (installs `nest-asyncio`; the `LLM_Store` code itself is vendored,
  see the KIF LLM Store section above).
- **`weather-graph-kif-llm`'s `[LLM Store]` column prints `no answer.` or a wildly different value
  each run** → expected, not a bug: verified live, `LLM_Store`'s output parser can raise on a reply
  with no digits in it (caught and turned into `no answer.`) and its numeric answers vary run to
  run (a real, observed `1000000.0°C` alongside a plausible `32.0°C` in back-to-back runs) — see
  [learning_plan_kif_llm.md](learning_plan_kif_llm.md) for why this is the actual finding, not
  noise to fix.

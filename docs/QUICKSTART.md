# Quick Start — weather-graph (uv + Ollama granite4:micro)

Standalone demo: natural-language weather questions → validated SPARQL over an RDF graph, driven by
**Mellea** (structured generation + requirements/repair) and a **BeeAI RequirementAgent** on
**Ollama `granite4:micro`**.

## Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| **uv** ≥ 0.11 | Python + package manager | `uv --version` |
| **Ollama** | Local model backend | `ollama --version` |

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv not installed
ollama pull granite4:micro                         # the model both BeeAI and Mellea use
```

## Setup

```bash
cd weather-graph
uv sync                 # installs beeai-framework, mellea, rdflib, pydantic (+ dev)
cp .env.example .env    # defaults already point at ollama:granite4:micro
```

`uv sync` creates `.venv/` and a reproducible `uv.lock`. `.venv/` and `.env` are gitignored.

## Run

```bash
# The packaged demo (three questions)
uv run weather-graph

# Or the flat single-file walkthrough
uv run python main.py
```

Requires Ollama running with the model set in `.env` (`AGENT_MODEL`/`MELLEA_MODEL`). Expected shape:
the agent is forced to call `weather_graph_tool`, which asks Mellea for a `WeatherSparqlSpec`,
validates + repairs the SPARQL, runs it against the weather graph, and answers from the rows.

## Weather graph storage backend

`GRAPH_BACKEND` in `.env` selects where the weather graph lives:

- **`memory`** (default) — parses `model/*.ttl` into an in-memory `rdflib.Graph()` at process start.
  No external services; this is what `uv run pytest` always uses regardless of `.env`.
- **`qlever`** — queries a local [QLever](https://github.com/ad-freiburg/qlever) SPARQL endpoint
  (`QLEVER_ENDPOINT`, default `http://localhost:7011`) instead, via rdflib's `SPARQLStore`.

To run against QLever:

```bash
uv tool install qlever          # the qlever CLI (see qlever/Qleverfile for config)
make qlever-index               # stage model/*.ttl into qlever/ and build the index (once, or
                                 # whenever model/*.ttl changes)
make qlever-up                  # start the local SPARQL server on QLEVER_ENDPOINT
# set GRAPH_BACKEND="qlever" in .env, then run/test as usual
make qlever-down                # stop it when done
```

`qlever/Qleverfile` defaults to `SYSTEM = native`, which needs the compiled `qlever-index` /
`qlever-server` binaries (`brew tap qlever-dev/qlever && brew install qlever-dev/qlever/qlever` on
macOS — note this trusts a third-party tap). Switch `SYSTEM = docker` in the Qleverfile to use
QLever's official Docker image instead, if you'd rather not trust that tap and have a working local
Docker daemon.

See [PLAN_WEATHER_QLEVER.md](../PLAN_WEATHER_QLEVER.md) for the full migration design and rationale.

## Neo4j backend (separate demo, fixed Cypher, no LLM)

`uv run weather-graph-neo4j` runs the same 3 questions as `uv run weather-graph`, but answers them
with fixed, parameterized Cypher queries (`src/weather_graph/neo4j/cypher.py`) against a Neo4j
instance — no LLM, no query generation. This is a separate entry point from the RDF demo; it does
not go through `GRAPH_BACKEND`.

```bash
uv tool install neo4j-cli   # https://github.com/neo4j-labs/neo4j-cli — all neo4j-* targets below
                             # go through this, never raw docker/python
make neo4j-up                # start a local Neo4j instance (bolt://localhost:7687), password
                              # pinned to .env's NEO4J_PASSWORD
make neo4j-migrate           # load model/weather.ttl's 8 cities into it (weather.cypher via neo4j-cli query)
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

## Test (no LLM / no network)

```bash
uv run pytest          # offline (no Ollama needed); tests/test_neo4j.py skips without a live Neo4j
uv run ruff check .
```

Coverage without a live model:
- **Validators + graph execution** (`test_sparql.py`, `test_models.py`) — the pure-Python rules in
  `sparql.py` are the same ones Mellea's requirements enforce (SELECT-only, `LIMIT` present, known
  predicates, parseable SPARQL).
- **Mocked generation** (`test_generation_mock.py` + the `mock_generation` fixture in `conftest.py`)
  — patches the `nl_to_sparql` generative seam and `get_session`, so the full
  generate → validate → **repair** → execute path (including the invalid-then-valid repair loop and
  the BeeAI tool's `answer_question`) is tested deterministically without Ollama.

## How the pieces map to the original demo

| Step | File | Role |
|------|------|------|
| 1 Structured target | `models.py` | `WeatherSparqlSpec` |
| 2 Mellea generative + requirements | `generation.py` | `@generative nl_to_sparql` + `RejectionSamplingStrategy` |
| 3 BeeAI tool | `tools.py` | `@tool weather_graph_tool` |
| 4 RequirementAgent | `agent.py` | `RequirementAgent` + `ChatModel.from_name("ollama:granite4:micro")` |
| 5 Async run | `demo.py` / `main.py` | `agent.run(...).middleware(GlobalTrajectoryMiddleware())` |

## Troubleshooting

- **Model not found** → `ollama pull granite4:micro` (or set `AGENT_MODEL`/`MELLEA_MODEL` in `.env`
  to a model you have, e.g. `qwen2.5:latest`).
- **BeeAI/Mellea API drift** → pinned here to `beeai-framework 0.1.82`, `mellea 0.7.0`. If you bump
  them, re-check `response.answer.text` (read defensively in `demo.py`) and the `@tool` surface.
- **`GRAPH_BACKEND=qlever` but `run_query()`/the agent can't connect** → confirm `make qlever-up` is
  actually running (`make qlever-status` or `curl $QLEVER_ENDPOINT` with a `query=` param) and that
  `QLEVER_ENDPOINT` in `.env` matches `[server] PORT` in `qlever/Qleverfile`.
- **`qlever index`/`qlever start` fail under `SYSTEM = docker`** → confirms nothing about your data;
  it means the local Docker daemon isn't reachable. Either start it, or switch to
  `SYSTEM = native` (see above) to avoid the Docker dependency entirely.

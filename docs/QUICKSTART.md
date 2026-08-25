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

## Test (no LLM / no network)

```bash
uv run pytest          # 12 tests, all offline (no Ollama needed)
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

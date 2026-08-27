# weather-graph analysis (sub-agent 1)

Analysis of the existing `weather-graph/` implementation, as input to the Neo4j port.

## Data

`model/weather.ttl` — 8 flat `wx:City` records, no relationships:

```turtle
wx:city0 a wx:City ; wx:name "Chicago" ; wx:country "United States" ;
         wx:temperatureC 21.0 ; wx:condition "Partly Cloudy" ; wx:humidity 58 .
```

Predicates (the full controlled vocabulary, enforced by `ALLOWED_PREDICATES` in
`src/weather_graph/models.py`): `name`, `temperatureC`, `condition`, `humidity`, `country`.
`condition` values seen in the data: Clear, Cloudy, Partly Cloudy, Rainy, Snowy, Sunny.

## Backend abstraction

`src/weather_graph/graph_data.py` builds an `rdflib.Graph` for one of two backends, selected by
the `GRAPH_BACKEND` env var (default `memory`):

- `memory` — parses `model/*.ttl` directly into an in-process `rdflib.Graph()`. No external
  services. This is what tests always use, regardless of `.env`.
- `qlever` — same `rdflib.Graph` interface, but backed by `SPARQLStore` pointed at a local QLever
  server (`qlever/Qleverfile`, `make qlever-index` / `qlever-up`).

Both are exposed through the identical `Graph.query()` call, so everything above `graph_data.py`
(`sparql.py`, `generation.py`, `tools.py`) is backend-agnostic — it just executes SPARQL text
against whatever `get_graph()` returns. This only works because both backends speak SPARQL; it
does **not** extend to Neo4j, which has a different query language and data model
(labeled property graph, not RDF triples).

### QLever's Docker support (researched, not adopted)

`qlever/Qleverfile`'s `[runtime]` section already carries both settings QLever needs for
container mode:

```ini
[runtime]
SYSTEM = native
IMAGE  = docker.io/adfreiburg/qlever:latest
```

The `qlever` CLI ([qlever-control](https://github.com/ad-freiburg/qlever-control)) supports three
`SYSTEM` values ([docs.qlever.dev/qleverfile](https://docs.qlever.dev/qleverfile/)): `native`
(locally-compiled `qlever-index`/`qlever-server` binaries on `PATH` — what this repo uses),
`docker` (pulls `IMAGE` if absent, runs QLever in a container), and `podman` (same, via Podman).
Switching `SYSTEM` doesn't change any calling code — `make qlever-index`/`qlever-up`/etc. shell
out to the same `qlever` CLI either way, which transparently runs `docker run`/`podman run`
instead of the raw binaries.

**Notably, `docker` is QLever's own upstream default** for `SYSTEM` — this repo deliberately
overrides to `native`. `docs/QUICKSTART.md` explains why: native mode requires
`brew tap qlever-dev/qlever && brew install qlever-dev/qlever/qlever`, a third-party (non-core)
Homebrew tap, which is a trust tradeoff some may want to avoid by using `SYSTEM = docker` instead
(a working Docker daemon is now confirmed available in dev environments used for this project, per
the Neo4j work in [neo4j_analysis.md](neo4j_analysis.md)). Docker mode's own tradeoff, per
[docs.qlever.dev/quickstart](https://docs.qlever.dev/quickstart/): "QLever will be executed in a
container which will come with a performance penalty." **Decision: kept `SYSTEM = native`** —
this was a research question, not a change request; nothing in `qlever/Qleverfile` was touched.

## Query path (NL → validated SPARQL → execution)

1. `generation.py`: `nl_to_sparql` is a Mellea `@generative` function — LLM produces a
   `WeatherSparqlSpec` (intent + sparql + rationale), validated via Mellea's own
   instruct-validate-repair loop against natural-language `_REQUIREMENTS`, then re-checked by
   `generate_spec` against the code-level validator below (repairing once more on failure).
2. `sparql.py`: `validate_query` is the hard, non-LLM safety gate — rejects empty/non-SELECT/
   write queries, requires a `LIMIT` clause, and rejects any `wx:` predicate not in
   `ALLOWED_PREDICATES`. `run_query` validates then executes, returning a `QueryResult`
   (sparql text, columns, rows).
3. `tools.py`: `answer_question` wraps `generate_spec` + `run_query`, plus a relevance-retry
   heuristic (`_worth_retrying`) for queries that pass validation but return zero rows because of
   a literal-value mismatch or a guessed city URI. Exposed as `weather_graph_tool`, a BeeAI tool.
4. `agent.py`: `build_agent` assembles a BeeAI `RequirementAgent` that must call
   `weather_graph_tool` before answering (`ConditionalRequirement(..., force_at_step=1)`).
5. `demo.py`: runs 3 fixed NL questions through the agent —
   - "What is the weather like in Chicago right now, and is it warm?"
   - "Is Chicago one of the three hottest cities in the data?"
   - "Is it currently raining or snowing in Chicago?"

## Testing

Offline by design (`Makefile`'s `test` target: "no LLM / no network"). `tests/conftest.py` forces
`GRAPH_BACKEND=memory` regardless of `.env`, and mocks the Mellea generation seam
(`generation.get_session` / `generation.nl_to_sparql`) with a deterministic `FakeGeneration`
stand-in so the full generate→validate→repair→execute path is exercised without Ollama.
`tests/test_sparql.py` covers `validate_query`/`run_query` directly against the real in-memory
graph — no mocking needed there since it's pure Python + rdflib.

## Implication for the Neo4j port

Given the decision to use hardcoded Cypher (no LLM generation for the Neo4j path), the layers
that need a Neo4j-side equivalent are only `graph_data.py`-and-below (connection + query
execution) and `demo.py` (the runnable script). `generation.py`, `tools.py`, `agent.py` have no
Neo4j analog under this scope — there is no NL→Cypher generation step to replace them.

# Learning plan: SPARQL/QLever backend for weather-graph

Summary of the SPARQL/QLever work done per [PLAN_DATA_MIGRATIONS.md](../plans/PLAN_DATA_MIGRATIONS.md),
on branch `dev-20260904-na`. Unlike Neo4j and KIF, the RDF/QLever backend predates the
`PLAN_*.md` → `analysis/*.md` → `learning_plan_*.md` process established for those two ports — this
is its first writeup, covering both the `data/qlever/` relocation and the live-QLever test coverage
gap that writeup surfaced.

## Scope decisions

- **`data/qlever/` (formerly `qlever/`) holds both QLever's config and its generated
  artifacts together.** The `qlever` CLI resolves `Qleverfile` and writes all index/log/vocabulary
  output relative to the current working directory — there's no supported way to point the indexer
  at a data directory separate from where its `Qleverfile` lives, so config and generated output
  move as one unit rather than being split. See `PLAN_DATA_MIGRATIONS.md`'s "Scope decisions" for
  the full reasoning (and why `model/weather.ttl` itself was explicitly left in place).
- **No behavior change to `sparql.py`/`graph_data.py`** — this work only relocates where QLever's
  files live on disk and closes a *test* gap; `run_query`/`validate_query`/`distinct_values` and
  the `GRAPH_BACKEND` switch are untouched.
- **Live QLever test lives in its own file** (`tests/test_sparql_qlever.py`), not appended to
  `tests/test_sparql.py`, so the memory-backend tests (which run unconditionally, every session)
  stay visually separate from the ones that only run with a live server — mirroring how
  `test_neo4j.py`/`test_kif.py` are already separate files from the code they test.
- **Assertions mirror the existing memory-backend tests exactly** (same `VALID` query, same
  expected `distinct_values("condition")` tuple) rather than inventing new ones — the point of this
  test is proving the two backends *agree*, not independently re-validating QLever.

## What was built

- `data/qlever/` — `Qleverfile` plus all 30 previously-`qlever/`-rooted generated artifacts
  (`weather.index.*`, `weather.internal.index.*`, `weather.vocabulary.*`,
  `weather.meta-data.json`, `weather.settings.json`, staged `weather.ttl`, index/server logs),
  `git mv`'d as one unit. `Qleverfile`'s `GET_DATA_CMD` updated from `cp ../model/*.ttl .` to
  `cp ../../model/*.ttl .` for the extra directory level.
- `Makefile`: `qlever-index`/`qlever-up`/`qlever-down`/`qlever-status` now `cd data/qlever` instead
  of `cd qlever`.
- `tests/test_sparql_qlever.py` — new. Skips cleanly (`pytest.skip(...)`) when no QLever endpoint
  is reachable; temporarily flips `GRAPH_BACKEND`/`QLEVER_ENDPOINT` via `monkeypatch` and clears
  `graph_data.get_graph`'s `lru_cache`/`sparql.distinct_values`'s cache around each test, since
  `tests/conftest.py` otherwise pins the whole suite to the `memory` backend and primes that cache
  before this module ever runs.
- Path references updated in `docs/QUICKSTART.md`, `.env.example`, and
  `src/weather_graph/graph_data.py`'s docstring — the latter two also had a stale reference to a
  `PLAN_WEATHER_QLEVER.md` that never existed in `plans/` (predates the `PLAN_NEO4J.md`/
  `PLAN_KIF.md` naming convention); both now point at this document instead.

## Verified live, end-to-end (2026-09-05)

- `make qlever-index` from `data/qlever/` — `qlever get-data` correctly staged `model/*.ttl` via
  the updated `../../model/*.ttl` relative path; indexing itself refused to overwrite the
  already-`git mv`'d index files (expected — same content, not regenerated).
- A stale QLever server process from a prior session (left running against the *old* `qlever/`
  directory, per `docs/learning_plan_kif.md`) was stopped, then `make qlever-up` was started fresh
  from `data/qlever/` and `make qlever-health` confirmed `http://localhost:7011` healthy.
- `uv run pytest tests/test_sparql_qlever.py -v` — **2/2 passed** against the live, relocated
  server (hottest-3 = Cairo first; `distinct_values("condition")` matches the memory backend
  exactly).
- Same file re-run after `make qlever-down` — **2/2 skipped** cleanly, no errors.
- Full suite (`uv run pytest`) — green both with QLever up (21 passed, 3 skipped — only
  `test_neo4j.py`'s live tests skip, no Neo4j running that session) and with it down (18 passed,
  8 skipped — `test_neo4j.py` (3) + `test_kif.py` (3) + `test_sparql_qlever.py` (2) all skip
  cleanly).
- `uv run ruff check .` — clean, including the new test file.
- Grep sweep for stale `qlever/` (old path)/`src/weather_graph/neo4j/weather.cypher` references
  after the move — clean outside `analysis/*.md` (left untouched by design) and the plan doc
  itself (which necessarily describes the old paths as "current state").

## Notes for anyone extending this further

- `data/kif/` was deliberately **not** created as part of this work — KIF has no data-loading
  artifact of its own; it queries the same `data/qlever/`-hosted server via a `SPARQL_Mapping`
  (see `PLAN_KIF.md`, "QLever wiring"), so there's nothing backend-specific to relocate for it.
- If QLever's on-disk layout is ever reworked again (e.g. per-dataset subdirectories under
  `data/qlever/`), remember the coupling above: `Qleverfile` and its generated output must move
  together, and `Makefile`'s `cd data/qlever` plus `Qleverfile`'s `GET_DATA_CMD` relative path both
  need to change in lockstep.

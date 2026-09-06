# Learning plan: KIF backend for weather-graph

Summary of the work done per [PLAN_KIF.md](../plans/PLAN_KIF.md), on branch `dev-20260828b-na`.

## Scope decisions (refined through iterative clarifying questions before implementation)

- **Reuse `wd.*` properties loosely**, not custom KIF properties — but only `wd.temperature` and
  `wd.weather_history` (condition) are actually registered; `wd.relative_humidity`/`wd.country`
  were dropped once it became clear no demo question needs them (matching how `neo4j/cypher.py`
  never queries `wx:humidity`/`wx:country` either). `wd.country` also turned out not to be a clean
  fit at all — it's declared `ItemDatatype`, but `wx:country` is a plain string.
- **QLever wiring:** reuse the *existing* `make qlever-up` server via a generic
  `Store('sparql', QLEVER_ENDPOINT, mapping=...)`, not KIF's own embedded `QLeverSPARQL_Store`.
- **Query scope:** hardcoded `kb.filter(...)` calls for the 3 fixed demo questions, no LLM —
  mirrors the Neo4j port.
- **City subjects — corrected mid-implementation:** originally planned real Wikidata Q-IDs
  (Chicago=Q1297, etc.). Live testing proved `SPARQL_Mapping` binds subjects to whatever IRI is
  actually in the data (`wx:city0`, not any Q-ID), with no automatic Wikidata link. Real Q-IDs
  would have needed an explicit per-city rewrite layer for no functional gain, so subjects use the
  real local `wx:cityN` IRIs directly.

See [analysis/ibm_kif_analysis.md](../analysis/ibm_kif_analysis.md) for the full technical
grounding (all claims here were verified against the actual `kif_lib` source and live-tested, not
assumed from the README/tutorial).

## What was built

- `src/weather_graph/kif/` — `mapping.py` (`SPARQL_Mapping` for `wd.temperature`/
  `wd.weather_history`), `kif.py` (store setup + `city_temperature`/`city_condition`/
  `hottest_cities`, plus the `CITY_NAMES` lookup mirroring `model/weather.ttl`).
- `src/weather_graph/demo_kif.py` — the 3-question demo, `uv run weather-graph-kif`.
- `tests/test_kif.py` — skips cleanly when QLever isn't reachable; runs for real against one.
- `Makefile`: `kif-check` (verifies `kif_lib` is installed) — no `kif-up`/`kif-down`, since KIF
  reuses the existing `qlever-up`/`qlever-health` infrastructure rather than running its own.
- `pyproject.toml`: added `kif-lib` dependency (from PyPI, matching the local `kif/` checkout's
  version 0.13.0) and the `weather-graph-kif` script entry.
- `analysis/ibm_kif_analysis.md` (sub-agent 2 deliverable, written from direct source reading and
  live experimentation, not just the README).

## Verified live, end-to-end

- `make qlever-index` (index already existed from a prior session) → `make qlever-up` →
  `make qlever-health` confirmed the endpoint live.
- `uv run pytest tests/test_kif.py -v` (clean env, no exported vars) — **4/4 passed**, including
  all 3 previously-skip-gated live tests.
- `uv run weather-graph-kif` (clean env) — all 3 questions answered correctly, matching the Neo4j
  port's results exactly (same underlying data): Chicago 21.0°C / "Partly Cloudy"; hottest-3 =
  Cairo, Sydney, Nairobi (Chicago not among them); not raining/snowing.
- Full suite: `uv run pytest` — **21 passed, 3 skipped** (the 3 skips are `test_neo4j.py`'s live
  tests, since no Neo4j instance was running this session — unrelated to KIF).
- `uv run ruff check .` and `uv run mypy src` — clean; the only mypy errors present are 7
  pre-existing ones in `sparql.py`/`generation.py` unrelated to this work.

**QLever was left running** (unlike the Neo4j container, which was torn down after validation) —
`.env`'s `GRAPH_BACKEND="qlever"` means it's this repo's actual configured default backend, not a
one-off validation instance.

## A second KIF Store backend

Everything above is the SPARQL/QLever-backed `Store` — `kif.py`. A second, LLM-backed `Store`
(`llm_store.py`, IBM's `kif-llm-store` `LLM_Store` over local Ollama) now sits alongside it,
answering the same 3 questions from the model's own knowledge instead of `model/weather.ttl`'s
synthetic data, through the identical `Store`/`kb.filter()` call shape. See
[learning_plan_kif_llm.md](learning_plan_kif_llm.md) and
[PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md) for the design, why the answers deliberately disagree,
and a real upstream-packaging problem (not installable as documented) that was worked around by
vendoring a patched copy in-repo.

## Design corrections found only by live-testing (not guessable from docs alone)

1. `wd.country`'s declared datatype is `Item`, not `String` — despite reading as a clean fit by
   name, it can't cleanly hold `wx:country`'s plain string values. Moot once humidity/country
   were dropped from scope, but worth knowing if scope ever expands.
2. City subjects bind to real local IRIs, not Wikidata Q-IDs (see "Scope decisions" above) — this
   reversed an explicit earlier decision after `plans/PLAN_KIF.md`'s design phase.
3. `Store('sparql', data=..., ...)` (no `iri`) hits a confusing fallback-cascade bug in this
   environment; irrelevant to production (which always uses `iri=`), but worth knowing if anyone
   tries to write inline-data unit tests the way KIF's own notebooks do — use
   `Store('sparql-rdflib', data=..., format='ttl', mapping=...)` directly instead.

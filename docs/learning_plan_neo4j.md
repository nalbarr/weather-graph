# Learning plan: Neo4j backend for weather-graph

Summary of the work done per [PLAN_NEO4J.md](../plans/PLAN_NEO4J.md), on branch `dev-20260828-na`.

## Scope decisions

Two forks were resolved before implementation (see analysis docs for the reasoning):

- **Hardcoded Cypher, not LLM-generated.** `demo_neo4j.py` runs 3 fixed, parameterized Cypher
  queries — no agent, no generation loop, no Cypher validator. This mirrors
  `movies-python-bolt`'s pattern (fixed Cypher, safety via parameterization, not text validation)
  rather than `weather-graph`'s NL→SPARQL agent pattern.
- **No restructuring of the RDF modules.** `graph_data.py`/`sparql.py`/`models.py` are untouched.
  Neo4j gets its own `src/weather_graph/neo4j/` subpackage — that alone separates the two
  backends' concerns, without touching the 6 existing call sites into the RDF modules.

## What was built

- `src/weather_graph/neo4j/` — `connection.py` (driver + `NEO4J_URI`/`NEO4J_USERNAME`/
  `NEO4J_PASSWORD`/`NEO4J_DATABASE`, loading `.env` itself via `python-dotenv`), `cypher.py`
  (3 fixed queries + `CypherQueryResult`), `weather.cypher` (schema + the same 8 cities as
  `model/weather.ttl`).
- `src/weather_graph/demo_neo4j.py` — the 3-question demo, `uv run weather-graph-neo4j`.
- `tests/test_neo4j.py` — skips cleanly when no instance is reachable; runs for real against one.
- `Makefile`: `neo4j-up` / `neo4j-status` / `neo4j-migrate` / `neo4j-down` /
  `neo4j-cli-check` / `neo4j-health`, all routed through `neo4j-cli`
  (https://github.com/neo4j-labs/neo4j-cli, `uv tool install neo4j-cli`) — no raw `docker` calls,
  analogous to how `qlever-*` (plus the equivalent `qlever-cli-check`/`qlever-health`) exclusively
  use the `qlever` CLI. `neo4j-migrate` pipes `weather.cypher` straight into `neo4j-cli query`,
  which replaced the original Python-driver `migrate.py` loader (deleted).
- `.env.example`, `docs/QUICKSTART.md` updated; `analysis/weather_graph_analysis.md` and
  `analysis/neo4j_analysis.md` capture the two reference implementations this was built from.
- `pyproject.toml`: added `neo4j` and `python-dotenv` dependencies and the `weather-graph-neo4j`
  script entry.

## Verified live, end-to-end (2026-08-27)

`neo4j-cli` and a Docker daemon both turned out to be available in this environment (they weren't
earlier in the branch's history), so the full path was actually exercised against a real instance
rather than left as a documented assumption — and it surfaced four real bugs, all fixed:

1. **`make help` never listed any `neo4j-*` target.** Its regex (`^[a-zA-Z_-]+:`) excluded digits,
   and every `neo4j-*` name contains "4". Fixed to `[a-zA-Z0-9_-]+`.
2. **`NEO4J_USER` vs `NEO4J_USERNAME`.** `neo4j-cli` reads exactly `NEO4J_USERNAME` from a `.env`
   file (confirmed via `neo4j-cli query --help`) — the codebase had used `NEO4J_USER` (following
   `movies-python-bolt`'s convention). Renamed everywhere (`.env`, `.env.example`, `connection.py`,
   docs) so one `.env` serves both the CLI and the Python driver.
3. **`neo4j-up` didn't pin a password.** `neo4j-cli docker create` without `--password` generates
   a random one each time, unrelated to `.env`'s `NEO4J_PASSWORD` — every fresh instance would
   silently break both the app driver and `neo4j-health`/`neo4j-migrate`. Fixed: `neo4j-up` now
   sources `.env` and passes `--password "$NEO4J_PASSWORD"` (falling back to `neo4j`), plus
   `--no-store-credential` so it doesn't pollute the global `neo4j-cli` credential store.
4. **`neo4j-down` was missing `--yes`.** `neo4j-cli docker delete` requires both `--yes` and
   `--force` non-interactively; `--force` alone refuses. Fixed.
5. **`.env` was never actually loaded for the Neo4j Python path.** The RDF path picks up `.env` as
   an *incidental* side effect of importing `beeai_framework` (pulls in `python-dotenv`
   transitively); `demo_neo4j.py`/`connection.py` deliberately have no BeeAI/Mellea dependency (the
   hardcoded-Cypher scope decision above), so they never got that side effect — `uv run
   weather-graph-neo4j` failed with a Neo4j `AuthError` even with a fully correct `.env`. Fixed:
   `connection.py` now calls `load_dotenv()` itself and `python-dotenv` is a direct dependency.

After those fixes, run for real in this session (container created, migrated, queried, torn down):

- `make neo4j-up` → `make neo4j-health` → `make neo4j-migrate` → a live `MATCH (c:City) RETURN
  count(c)` confirmed **8** nodes → `make neo4j-status` showed it running.
- `uv run pytest` (clean env, no exported vars) — **20 passed**, including all 3 previously-skipped
  live Cypher tests in `tests/test_neo4j.py`.
- `env -i uv run weather-graph-neo4j` (fully clean environment) — all 3 questions answered
  correctly from the live instance (Chicago 21.0°C/Partly Cloudy; hottest-3 = Cairo, Sydney,
  Nairobi, Chicago not among them; not raining/snowing).
- `uv run ruff check .` and `uv run mypy` on the `neo4j/` + `demo_neo4j.py` files — clean.
- `make neo4j-down` — container removed; `make neo4j-status` then reports "not running" cleanly.

**Not yet exercised:** `qlever-health` (only its "endpoint down" failure path was confirmed —
QLever wasn't brought up in this session), and the Docker `--data-dir`/persistence flags (not
used; the verification container was ephemeral state, deleted after).

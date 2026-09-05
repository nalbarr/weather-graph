# PLAN_DATA_MIGRATIONS.md

## Role
You are a systems architect cleaning up weather-graph's data-backend footprint. Three backends
now exist (in-memory RDF, QLever, Neo4j, plus a read-only KIF client — see `PLAN_NEO4J.md`,
`PLAN_KIF.md`) and their generated/data-loading artifacts are currently scattered: QLever's
generated index lives at the repo root (`qlever/`), Neo4j's data-loading script lives inside the
importable Python package (`src/weather_graph/neo4j/weather.cypher`), and SPARQL/QLever has no
live-backend test coverage analogous to what Neo4j and KIF already have. This plan collects all of
that under a single `data/` directory and closes the SPARQL/QLever test gap, without touching
`model/weather.ttl` (the RDF source of truth, out of scope — see "Scope decisions"). It also closes
a documentation gap: `docs/QUICKSTART.md`'s four backends read as independent how-tos rather than a
taught sequence, and there is no single doc tying them together as four ways of answering the same
Chicago-weather questions — this plan adds that review and a consolidated `docs/learning_plan.md`.

## Objectives

1. Move QLever's generated/native data artifacts out of `qlever/` and into `data/qlever/`.
2. Move each backend's data-loading ("migration") artifact out of `src/weather_graph/` and into
   `data/neo4j/` / `data/kif/` respectively — keeping importable query code in `src/`.
3. Add `docs/learning_plan_sparql.md`, closing the gap that SPARQL/QLever — unlike Neo4j and KIF —
   has no live-backend test and no learning-plan writeup of its own.
4. Review `docs/QUICKSTART.md` end to end — both for the path updates from Objectives 1–2, and for
   whether its backend-by-backend sequence (`memory` → `qlever` → `neo4j` → `kif`) actually reads
   as a taught progression rather than four independent how-tos bolted together in commit order.
5. Add `docs/learning_plan.md`: a single consolidated writeup of the *whole* pedagogy sequence
   across all four backends, told through one running example — Chicago's weather — and including
   a compare/contrast of the SPARQL (RDF), Neo4j, and KIF approaches. This sits *above*
   `learning_plan_neo4j.md`/`learning_plan_kif.md`/`learning_plan_sparql.md`, linking out to each
   for backend-specific depth rather than duplicating them.

## Scope decisions

- **`model/weather.ttl` does not move.** It's the single source of truth loaded directly by the
  default `memory` backend (`graph_data.py`) and staged into QLever's working directory by
  `GET_DATA_CMD` — not itself a migration artifact. Moving it would touch far more call sites
  (`graph_data.py`, `Qleverfile`, tests, every doc that says `model/weather.ttl`) for no benefit to
  the goal here (tidying *generated*/*migration* artifacts). Revisit separately if ever needed.
- **`qlever/Qleverfile` moves together with its generated artifacts, to `data/qlever/Qleverfile`
  — it does not stay behind in `qlever/`.** The `qlever` CLI resolves `Qleverfile` and writes all
  index/log/vocabulary output relative to the current working directory (`cd qlever && qlever
  ...`, per the existing Makefile) — there's no supported way to point the indexer at a data
  directory that's separate from where its `Qleverfile` lives. Splitting them would mean either
  two directories that must stay manually in sync, or a symlink hack. Since "native data
  artifacts" and their config are one operational unit for QLever, they move together; the
  `qlever/` directory is removed once empty.
- **Neo4j's Python query modules (`connection.py`, `cypher.py`) stay in
  `src/weather_graph/neo4j/`** — they're imported by `demo_neo4j.py` and `tests/test_neo4j.py` as
  `weather_graph.neo4j.*`, and `pyproject.toml` packages `src/weather_graph` as the wheel (`[tool.
  hatch.build.targets.wheel] packages = ["src/weather_graph"]`). Only `weather.cypher` — the
  schema+data-loading script, analogous to QLever's staged `.ttl` copy — is a migration/data
  artifact and moves to `data/neo4j/weather.cypher`.
- **KIF has no migration artifact of its own, so `data/kif/` is not populated as part of this
  plan.** KIF is read-only: it queries weather-graph's *existing* QLever server rather than
  loading its own copy of the data (see `PLAN_KIF.md`, "QLever wiring") — there is no KIF-specific
  data file analogous to `weather.cypher` or QLever's index. `src/weather_graph/kif/` (`kif.py`,
  `mapping.py`) stays in place for the same import/packaging reasons as `neo4j/`. If this is
  wrong (i.e. some KIF artifact was intended), flag it before Sub agent 2 starts.
- **`analysis/*.md` are left untouched.** They're point-in-time deliverables from the `PLAN_NEO4J`/
  `PLAN_KIF` sub-agent processes (like commit history) rather than living documentation — unlike
  `docs/QUICKSTART.md` and `.env.example`, which describe the current state and must be updated.
- **`docs/QUICKSTART.md`'s existing backend order (`memory` → `qlever` → `neo4j` → `kif`) is kept,
  not reshuffled.** It already happens to be dependency-sound (KIF's walkthrough needs a running
  QLever server, so QLever must be taught first) and cost/complexity-ascending (no external
  service → one external service, same query language → a second external service, a different
  query language and data model → a client layer with no service of its own, reusing the first).
  The gap Objective 4 targets isn't ordering, it's *framing*: each section currently reads as a
  standalone how-to with no through-line connecting it to the others as "the same 8 cities, viewed
  four ways." That through-line is added to `docs/QUICKSTART.md` as brief connective text, but told
  in full in the new `docs/learning_plan.md` (Objective 5), which is where the comparison belongs.
- **`docs/learning_plan.md` (singular, new) sits above the three existing/planned per-backend
  docs** (`learning_plan_neo4j.md`, `learning_plan_kif.md`, `learning_plan_sparql.md`) rather than
  merging into or replacing them. Those three stay the detailed, backend-specific record (scope
  decisions, what was built, what broke and was fixed, live-verification logs); the new doc is the
  reader's entry point — the narrative + compare/contrast — that sends them to the right one of the
  three for depth. Naming it `learning_plan.md` (no backend suffix) signals "read this first."

## Current state (as found)

- `qlever/` — 31 git-tracked files: `Qleverfile` (source config) plus 30 generated artifacts
  (`weather.index.*`, `weather.internal.index.*`, `weather.vocabulary.*`, `weather.meta-data.json`,
  `weather.settings.json`, `weather.ttl` (staged copy), index/server logs and resource-usage TSVs
  — one of which, `weather.server.resource-usage-log.tsv`, is 1.1MB).
- `src/weather_graph/neo4j/weather.cypher` — schema + the 8 `MERGE` statements loading the same
  data as `model/weather.ttl`, run via `make neo4j-migrate`.
- `tests/test_sparql.py` — 5 tests, all against the default `memory` backend only. No test runs
  with `GRAPH_BACKEND=qlever`, unlike `tests/test_neo4j.py` / `tests/test_kif.py`, which both have
  a live-instance test that skips cleanly when unreachable (`pytest.skip(f"No reachable ...")`).
- `src/weather_graph/graph_data.py` and `.env.example` both reference a `PLAN_WEATHER_QLEVER.md`
  that does not exist in `plans/` — a stale reference from before `PLAN_NEO4J.md`/`PLAN_KIF.md`
  established the current plan/analysis/learning-plan naming convention.
- `docs/learning_plan_kif.md` and `docs/learning_plan_neo4j.md` exist; there is no
  `docs/learning_plan_sparql.md` documenting the original QLever/SPARQL backend work.
- `docs/QUICKSTART.md`'s four backend sections (`memory` implicit in "Setup"/"Run", then `##
  Weather graph storage backend` for `qlever`, `## Neo4j backend`, `## KIF backend`) each explain
  their own setup and link to their own learning plan / analysis docs, but nothing ties them
  together as one dataset (Chicago + 7 other cities) answering the same 3 fixed questions across
  four representations — a reader who only skims QUICKSTART would not come away knowing the
  backends are meant to be compared. There is also no top-level `docs/learning_plan.md` — the three
  per-backend ones are peers with no index page above them.

## Agents

### Orchestrator
- Manages the three sub agents below; runs them in order — Sub agent 2 depends on Sub agent 1's
  moves being in place before it can verify anything live, and Sub agent 3 depends on Sub agent 2's
  `docs/learning_plan_sparql.md` existing (it links to all three per-backend docs, so it must run
  last).
- Will update `Makefile`:
  - `qlever-index`/`qlever-up`/`qlever-down`/`qlever-status` (and the `cd qlever &&` shells inside
    `qlever-health`'s endpoint check, if any): `cd qlever` → `cd data/qlever`.
  - `neo4j-migrate`: `< src/weather_graph/neo4j/weather.cypher` → `< data/neo4j/weather.cypher`.
- Will update path references in living docs (not `analysis/*.md`, per scope decision):
  - `docs/QUICKSTART.md`: every `qlever/Qleverfile` / "stage model/*.ttl into qlever/" mention →
    `data/qlever/...`.
  - `.env.example`: `qlever/Qleverfile` mentions → `data/qlever/Qleverfile`; replace the dead
    `PLAN_WEATHER_QLEVER.md` reference with `docs/learning_plan_sparql.md` (Sub agent 2's output).
  - `src/weather_graph/graph_data.py` docstring: same two fixes (path + dead reference).
  - `qlever/Qleverfile` itself (now at `data/qlever/Qleverfile`): `GET_DATA_CMD = cp ../model/*.ttl
    .` → `cp ../../model/*.ttl .` (one more directory level from repo root); update its comments
    that explain the relative path.
  - `src/weather_graph/neo4j/weather.cypher`'s header comment references a `migrate.py` that no
    longer exists (per `docs/learning_plan_neo4j.md`, it was deleted in favor of piping straight
    into `neo4j-cli query`) — drop that stale mention while moving the file.
- Will confirm no other path assumptions were missed by re-running the grep sweep below after the
  moves (see "Verification").

### Sub agent 1 — relocate artifacts
- Inputs: current repo state (this document's "Current state" section).
- Actions:
  1. `git mv qlever data/qlever` (moves `Qleverfile` + all 30 generated artifacts as one unit, per
     the scope decision above).
  2. `mkdir -p data/neo4j && git mv src/weather_graph/neo4j/weather.cypher data/neo4j/weather.cypher`.
  3. Apply the Makefile / `Qleverfile` / doc path updates listed under "Orchestrator" above.
- Outputs:
  - `data/qlever/` (formerly `qlever/`), `data/neo4j/weather.cypher`.
  - Updated `Makefile`, `Qleverfile`, `docs/QUICKSTART.md`, `.env.example`, `graph_data.py`.
- Verification (must pass before Sub agent 2 starts):
  - `make qlever-index && make qlever-up && make qlever-health` — confirms the relocated
    `Qleverfile`'s `GET_DATA_CMD` and Makefile `cd data/qlever` wiring still produce a working
    index/server from the new location.
  - `make neo4j-up && make neo4j-migrate && make neo4j-health` — confirms `weather.cypher` still
    loads correctly from `data/neo4j/`.
  - `uv run pytest` — full suite still green (memory-backend tests are path-independent, but this
    catches anything missed).
  - `grep -rn "src/weather_graph/neo4j/weather.cypher\|cd qlever\|qlever/Qleverfile\| qlever/"` —
    should return nothing outside `analysis/*.md` (left untouched per scope) and this plan file.

### Sub agent 2 — close the SPARQL/QLever coverage gap
- Inputs:
  - `tests/test_neo4j.py` and `tests/test_kif.py` as the pattern to mirror (`pytest.skip(...)` on
    an unreachable live backend, otherwise exercise it for real).
  - `tests/test_sparql.py`, `src/weather_graph/sparql.py`, `src/weather_graph/graph_data.py`
    (`GRAPH_BACKEND=qlever` path) as the code under test.
  - Sub agent 1's relocated `data/qlever/` must already be indexable/runnable.
- Actions:
  1. Add a live QLever-backed test (new `tests/test_sparql_qlever.py`, or a class/section appended
     to `tests/test_sparql.py` — Sub agent 2's call, matching whichever is more readable) that sets
     `GRAPH_BACKEND=qlever` + `QLEVER_ENDPOINT`, clears `graph_data.get_graph`'s `lru_cache` between
     tests, and skips cleanly (`pytest.skip(f"No reachable QLever endpoint: {exc}")`) when the
     configured endpoint isn't up — same shape as `test_neo4j.py`/`test_kif.py`. At minimum,
     re-run `run_query(VALID)` and `distinct_values("condition")` against the live QLever backend
     and assert the same results as the existing memory-backend tests, so the two backends are
     proven to agree, not just independently "working."
  2. Write `docs/learning_plan_sparql.md` (same shape as `docs/learning_plan_kif.md` /
     `docs/learning_plan_neo4j.md`: scope/decisions, what was built, what was verified live,
     anything surprising) covering both this plan's `data/qlever/` relocation *and* the new live
     test — since no learning-plan doc for the original QLever/SPARQL work exists yet, this is
     also its first writeup, not just an addendum.
- Outputs:
  - New/updated test file under `tests/` (live QLever coverage).
  - `docs/learning_plan_sparql.md`.
- Verification:
  - `make qlever-up` then `uv run pytest tests/test_sparql*.py -v` — the new live test(s) actually
    run (not skipped) and pass.
  - `make qlever-down` (or just stop the server) then `uv run pytest tests/test_sparql*.py -v` —
    the new live test(s) skip cleanly rather than erroring.
  - `uv run pytest` — full suite still green either way.

### Sub agent 3 — pedagogy review + consolidated `docs/learning_plan.md`
- Inputs:
  - `docs/QUICKSTART.md` (post Sub agent 1's path fixes).
  - `docs/learning_plan_neo4j.md`, `docs/learning_plan_kif.md`, `docs/learning_plan_sparql.md`
    (Sub agent 2's output) — the three backend-specific records to summarize and link out to.
  - `plans/PLAN_NEO4J.md`, `plans/PLAN_KIF.md`, this document — for each backend's scope decisions
    and *why*, not just *what*.
  - The 3 fixed demo questions (`demo.py`/`demo_neo4j.py`/`demo_kif.py`: Chicago's current
    temperature/condition, the 3 hottest cities, whether it's raining/snowing in Chicago) — the
    constant across all four backends and the through-line for both deliverables below.
- Actions:
  1. **Review `docs/QUICKSTART.md`** for pedagogical sequence, not just the mechanical path fixes
     Sub agent 1 already made. Confirm/adjust:
     - The backend order stays `memory` → `qlever` → `neo4j` → `kif` (see "Scope decisions" — this
       is dependency- and complexity-ordered already).
     - Each section briefs the *concept* it's introducing before the commands (e.g. `qlever`'s
       section should say up front "same triples, same predicates, now over a real SPARQL
       endpoint instead of in-process" — not just list install steps), so a reader moving
       section-to-section is being taught something new each time, not just re-running the demo
       against a different flag.
     - Add one or two connective sentences per section (or a short intro paragraph before the
       first backend section) making explicit that all four are answering the *same* 3 questions
       over the *same* 8 cities — Chicago first among them — so the reader treats what follows as
       a comparison, not four unrelated setups.
     - Fix anything Sub agent 1 missed (re-run the grep sweep from Sub agent 1's verification).
  2. **Write `docs/learning_plan.md`**, the new top-level entry point. Required shape:
     - Opens by naming Chicago's weather (current temperature/condition, hottest-3 ranking, rain/
       snow check) as the fixed running example carried through every section — the same 3
       questions asked identically against all four backends, so results are directly comparable.
     - Walks the full sequence in taught order (`model/weather.ttl` as ground truth → `memory` →
       `qlever` → `neo4j` → `kif`), one short section each, stating what *new concept* that step
       introduces relative to the previous one (external SPARQL service; then a different data
       model + query language entirely; then a semantic-mapping client layer with no storage of
       its own) — not a re-listing of setup commands, which stay in `QUICKSTART.md`.
     - For each of the three query-backend sections, links out to its detailed doc
       (`learning_plan_sparql.md`, `learning_plan_neo4j.md`, `learning_plan_kif.md`) for scope
       decisions, what was built, and live-verification detail, rather than duplicating it.
     - **Required "Comparing the approaches" section** — a table or structured comparison of
       SPARQL/RDF (memory+QLever), Neo4j, and KIF across at least: data model (triples vs. labeled
       property graph vs. Wikidata-shaped statements), query language, external services required,
       how the same predicates/vocabulary are represented in each (`wx:temperatureC` /
       `c.temperatureC` / `wd.temperature`), and a plain-language takeaway on when each shape of
       backend is the right reach in a real project (not just "which one this repo happened to
       build first").
- Outputs:
  - Updated `docs/QUICKSTART.md` (connective framing text; any missed path fixes).
  - `docs/learning_plan.md`.
- Verification:
  - Every internal link in the new doc (to `learning_plan_sparql.md`, `learning_plan_neo4j.md`,
    `learning_plan_kif.md`, `PLAN_NEO4J.md`, `PLAN_KIF.md`, `plans/PLAN_DATA_MIGRATIONS.md`)
    resolves to a real file.
  - A read-through confirms all 3 fixed demo questions and Chicago specifically are named in the
    opening of `docs/learning_plan.md`, not just "the weather data" generically.
  - `docs/QUICKSTART.md` still reads correctly top-to-bottom after the added framing text (no
    duplicate/contradictory explanations with the setup steps it introduces).

## Verification (final, whole-plan)

- `uv run pytest` — full suite green with QLever/Neo4j both down (everything either passes or
  skips cleanly, no errors).
- `uv run pytest` again with `make qlever-up` and `make neo4j-up` both running — the previously-
  skipped live tests (Neo4j, KIF, and the new SPARQL/QLever ones) all pass.
- `uv run ruff check .` and `uv run mypy src` — clean (matching the bar set by
  `docs/learning_plan_neo4j.md` / `docs/learning_plan_kif.md`).
- `git status` shows `qlever/` gone, `data/qlever/` and `data/neo4j/weather.cypher` present, and no
  stray references to the old paths outside `analysis/*.md`.
- `docs/learning_plan.md` exists, names Chicago and the 3 fixed demo questions up front, links out
  to all three per-backend learning plans, and contains the required SPARQL-vs-Neo4j-vs-KIF
  comparison section.
- `docs/QUICKSTART.md` reads as a taught sequence (each backend section states the new concept it
  introduces before its commands) rather than four independent how-tos.

# PLAN_KIF.md

## Role
You are a systems architect and want to extend the current weather-graph to support the
open-source IBM KIF framework (Knowledge Integration Framework, https://github.com/IBM/kif) as
an additional query backend.

## Objectives

Port the 3 fixed weather demo questions (see `demo.py`) to run via KIF against weather-graph's
data, reusing the existing QLever server rather than standing up new infrastructure. This is a
demo/comparison backend alongside the existing RDF (memory/QLever) and Neo4j backends — not a
replacement for either.

**Key finding from reviewing `kif/` directly (not just KIF's README):** KIF's data model is built
around *Wikidata-shaped* statements (`Item`/`Property`/`Statement`), not raw SPARQL predicates.
Querying arbitrary local RDF like `wx:temperatureC` is not a drop-in swap of KIF's own Brazil
tutorial (`examples/quickstart.ipynb`, which queries live Wikidata via `wd.Brazil`) — it requires
a `SPARQL_Mapping` (see `examples/sparql_mapping.ipynb`, which does exactly this for a
non-Wikidata PubChem vocabulary) translating between `wx:` triples and KIF's statement model. The
following design decisions were made explicit after reading KIF's source, to remove ambiguity
that would otherwise be rediscovered mid-implementation:

### Vocabulary mapping (properties) — as implemented, corrected during build

Reuse existing `wd.*` Wikidata property IDs loosely rather than minting custom KIF properties —
accepted tradeoff: some of these are a semantic stretch for live/synthetic demo data. **Only
`wx:temperatureC` and `wx:condition` are actually mapped/registered** — those are the only two
predicates the 3 fixed demo questions need (mirrors `neo4j/cypher.py`, which likewise never
queries `wx:country`/`wx:humidity` despite `weather.cypher` loading them):

| wx: predicate      | KIF property                    | Fit                                          |
|---------------------|----------------------------------|-----------------------------------------------|
| `wx:temperatureC`   | `wd.temperature` (P2076)         | Clean match — mapped                          |
| `wx:condition`      | `wd.weather_history` (P4150)     | Stretch — P4150 means "description of historical weather," not "current condition category" (e.g. "Rainy"). Accepted per the "reuse loosely" decision; no clean alternative exists. Mapped. |
| `wx:humidity`       | *(not mapped — out of scope)*    | Would have been `wd.relative_humidity` (P5596), a clean match, but no demo question needs it. |
| `wx:country`        | *(not mapped — out of scope, and not actually a clean match)* | `wd.country` (P17) is declared `ItemDatatype` in KIF's vocabulary, but `wx:country` values are plain string literals — a real type mismatch discovered during implementation, not just a naming stretch. Moot since no demo question needs it. |
| `wx:name`           | *(none needed)*                  | See "city subjects" below — resolved via a local Python dict, not a KIF property. |

### Vocabulary mapping (city subjects) — corrected during build

**Originally planned real Wikidata Q-IDs; corrected after live testing.** Confirmed empirically:
`SPARQL_Mapping` binds city subjects to whatever IRI actually appears in the underlying data —
i.e. the real local `wx:cityN` IRIs (`http://example.org/weather#city0` for Chicago, etc.) — with
**no automatic link to Wikidata Q-IDs**. Forcing real Q-IDs (Chicago=Q1297, London=Q84, Cairo=Q85,
Tokyo=Q1490, Oslo=Q585, Nairobi=Q3870, Sydney=Q3130, Paris=Q90) would require an explicit
per-city rewrite layer in the mapping (e.g. 8 hardcoded bindings), which cuts against the
"hardcoded, simple" scope decided below — so subjects use the local `wx:cityN` IRIs directly, and
`kif.py`'s `CITY_NAMES` dict (mirroring `model/weather.ttl`) handles the name↔subject lookup in
plain Python instead of through KIF.

### QLever wiring

Reuse the **existing** QLever server (`make qlever-up`, `QLEVER_ENDPOINT` in `.env`) via a
generic KIF SPARQL store pointed at that endpoint — not KIF's own `QLeverSPARQL_Store`
(`kif_lib/store/sparql/qlever.py`, `store_name='sparql-qlever'`), which manages its own embedded
QLever index/server subprocess and would mean two independent QLever setups running side by side.
This means the Orchestrator's Makefile task is about *verifying* the dependency
(`qlever-cli-check`/`qlever-health` already exist), not standing up a second server — likely a
`kif-check` target (confirm `kif_lib` is importable / installed) rather than a `kif-up`/`kif-down`
pair, since KIF itself is a client library here, not a service.

### Query scope

Hardcoded, fixed `kb.filter(subject=..., property=...)` calls for the 3 demo questions — no LLM,
no query generation. Mirrors the Neo4j port's scope decision (see `plans/PLAN_NEO4J.md`,
`analysis/neo4j_analysis.md`) for the same reasons: smaller, consistent, testable without an LLM.

## Agents

### Orchestrator
- The orchestrator manages three sub agents each specialized on specific tasks below.
- Will summarize final plan changes as:
  - docs/learning_plan_kif.md
- Will update Makefile with a `kif-check` target verifying the `kif_lib` dependency is installed
  (mirroring `qlever-cli-check`/`neo4j-cli-check`) — KIF reuses the existing `qlever-up` server
  (see "QLever wiring" above), so no new server-lifecycle targets are needed.
- Will summarize/update existing docs/QUICKSTART.md

### Sub agent 1
- Sub agent 1 is focused on understanding existing weather-graph/ implementation which tests 3 RDF queries related to weather in Chicago, etc.
- Inputs:
  - weather-graph/ implementation
- Outputs:
  - Markdown document as intermediate analysis artifact as:
    - analysis/weather_graph_analysis.md
  - Note: this file already exists (written for the Neo4j port) and covers weather-graph's
    implementation generically — reuse it as-is unless something KIF-specific is missing.

### Sub agent 2
- Sub agent 2 is focused on understanding the KIF framework: its Wikidata-shaped statement model
  (`Item`/`Property`/`Statement`/`Store.filter`), how `SPARQL_Mapping` lets it query non-Wikidata
  local RDF (`examples/sparql_mapping.ipynb` is the closest real analog to this port — it maps a
  custom PubChem vocabulary the same way weather-graph's `wx:` vocabulary needs to be mapped), and
  how a generic SPARQL store connects to an already-running SPARQL endpoint (as opposed to KIF's
  embedded `QLeverSPARQL_Store`, which this port does not use — see "QLever wiring" above).
- Inputs:
  - kif/
- Outputs:
  - Markdown document as intermediate analysis artifact as:
    - analysis/ibm_kif_analysis.md

### Sub agent 3
- Sub agent 3 is focused on proposing design and implementation to port weather-graph's 3 fixed
  demo questions to KIF, per the vocabulary mapping and scope decisions above (reused `wd.*`
  properties for temperature/condition, local `wx:cityN` IRIs for city subjects, existing
  `qlever-up` endpoint, no LLM).
- Inputs:
  - sub agent 1 analysis at:
    - analysis/weather_graph_analysis.md
  - sub agent 2 analysis at:
    - analysis/ibm_kif_analysis.md
- Outputs:
  - weather-graph/src/weather_graph/kif/
    - `mapping.py` — the `SPARQL_Mapping` translating `wx:` triples to the `wd.*` properties above
    - `kif.py` — KIF store setup (pointed at `QLEVER_ENDPOINT`) + the 3 fixed `kb.filter(...)` queries
  - weather-graph/src/weather_graph/demo_kif.py
    - new demo asking the same 3 questions but calling the KIF backend
  - weather-graph/tests/test_kif.py
    - unit tests exercising all KIF queries (skip cleanly when QLever isn't running, mirroring
      `tests/test_neo4j.py`'s pattern for an unreachable live backend)
  - Will update `.env.example` with reasonable defaults (likely none new — KIF reuses
    `QLEVER_ENDPOINT`, already present)

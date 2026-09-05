# Learning plan: weather-graph, one dataset through four backends

This is the entry point into weather-graph's backend work. It doesn't replace
[learning_plan_sparql.md](learning_plan_sparql.md), [learning_plan_neo4j.md](learning_plan_neo4j.md), or
[learning_plan_kif.md](learning_plan_kif.md) — each of those is the detailed, backend-specific record
(scope decisions, what was built, what broke and got fixed, live-verification logs). This document
is the narrative that ties them together and the comparison none of the three attempt on their own.

## The driving context: Chicago's weather

Every section below, and every one of the three backend-specific learning plans it links to,
answers the exact same 3 fixed questions against the exact same 8-city dataset
(`model/weather.ttl`: Chicago, Paris, London, Cairo, Tokyo, Oslo, Nairobi, Sydney) — **Chicago
specifically is the city each demo checks first**:

1. **What's the current temperature and condition in Chicago?** (21.0°C, "Partly Cloudy")
2. **Which 3 cities are hottest right now?** (Cairo, Sydney, Nairobi — Chicago is not among them)
3. **Is it currently raining or snowing in Chicago?** (No — "Partly Cloudy")

Four backends answer these same three questions, in four different ways, all verified live to
return these exact answers (see each backend's learning plan for the verification transcript).
Holding the questions and the data constant while changing *how* they're answered is what makes
the four backends comparable at all — a reader who only sees one backend has no way to judge
whether SPARQL, Cypher, or KIF's statement model was the "right" choice for this problem, since
they've only seen one answer to it.

## The taught sequence

`docs/QUICKSTART.md` walks these in order; this section explains *why* that order, and what new
concept each step adds over the last.

### 0. `model/weather.ttl` — the ground truth

8 flat `wx:City` records (no relationships between cities) — see
[weather_graph_analysis.md](../analysis/weather_graph_analysis.md). Every backend below either
parses this file directly or is loaded from data that mirrors it exactly (`data/neo4j/weather.cypher`'s
`MERGE` statements, KIF's reuse of the same QLever-indexed triples).

### 1. `memory` — the baseline

Parses `model/*.ttl` into an in-process `rdflib.Graph()` at startup (`graph_data.py`). No external
service, no infrastructure decision to make yet — this is the floor every other backend is compared
against, and what the offline test suite always uses regardless of `.env`.

**New concept:** none yet — this *is* the data, unmodified. The natural-language → SPARQL pipeline
(Mellea + BeeAI, see `docs/QUICKSTART.md`'s "How the pieces map to the original demo") sits on top
of whichever backend is configured, so it's demonstrated here first before any backend-specific
complexity is introduced.

### 2. `qlever` — the same data, now a service

Same triples, same `wx:` predicates, same query language (SPARQL) — the only thing that changes is
that the graph now lives behind a real [QLever](https://github.com/ad-freiburg/qlever) SPARQL
endpoint instead of in-process. `sparql.py`'s validation and query code is *unchanged* between
`memory` and `qlever`; `graph_data.get_graph()` just returns a different `rdflib.Graph` wrapping a
`SPARQLStore` instead of a parsed file.

**New concept:** the graph becomes something you start/stop/index rather than something built at
import time. This is the first step where "is the backend actually reachable" becomes a real
question — see [learning_plan_sparql.md](learning_plan_sparql.md) for the live-QLever test that
checks exactly that (skipping cleanly rather than failing when no server is up).

### 3. `neo4j` — a genuinely different shape

The first change to the *data model*, not just its location: the same 8 cities become labeled
property graph nodes (`(:City {name, temperatureC, condition, country, humidity})`) instead of RDF
triples, and Cypher replaces SPARQL entirely. Unlike `qlever`, this isn't a drop-in swap behind the
same `sparql.py` — it's a separate demo entry point (`demo_neo4j.py`, `src/weather_graph/neo4j/`)
with its own fixed, parameterized queries and no shared code with the RDF path.

**New concept:** the same facts, represented as a graph of typed nodes/properties instead of a set
of triples — and a query language (Cypher's pattern-matching `MATCH` clauses) built around that
shape rather than around triple patterns. See
[learning_plan_neo4j.md](learning_plan_neo4j.md) for the full build (including the real
infrastructure bugs found and fixed while standing up a live Neo4j instance) and "Comparing the
approaches" below for the model-to-model comparison.

### 4. `kif` — a semantic layer, not a new store

The last step changes the *lens*, not the storage: [KIF](https://github.com/IBM/kif) (IBM's
Knowledge Integration Framework) reuses the exact same QLever server from step 2 — no new copy of
the data, no new index — but maps `wx:temperatureC`/`wx:condition` triples into Wikidata-shaped
statements (`Item`/`Property`/`Statement`, via a `SPARQL_Mapping`) at query time, reusing real
`wd.temperature`/`wd.weather_history` Wikidata property IDs loosely rather than minting new ones.

**New concept:** a query/semantic-integration layer that owns no data of its own, sitting on top of
an existing store — the opposite end of the spectrum from `neo4j`, which owns both its data *and*
its model. See [learning_plan_kif.md](learning_plan_kif.md) for the vocabulary-mapping decisions
(including two that were corrected only after live-testing against the real `kif_lib` API).

## Comparing the approaches

|                          | SPARQL/RDF (`memory` + `qlever`)                         | Neo4j                                                     | KIF                                                                 |
|--------------------------|-----------------------------------------------------------|------------------------------------------------------------|----------------------------------------------------------------------|
| **Data model**           | Triples (subject–predicate–object); a `City` is whatever subject has `wx:*` predicates attached. | Labeled property graph: typed nodes with properties, relationships (unused here — 8 flat `City` nodes, no edges). | Wikidata-shaped statements: `Item`/`Property`/`Statement`, layered over the *existing* RDF triples via a mapping — not a data model of its own. |
| **Query language**       | SPARQL (`SELECT`/`WHERE`, triple patterns).               | Cypher (`MATCH` pattern-matching over nodes/relationships). | KIF's `Store.filter(subject=..., property=...)` — a statement-level filter API, compiled down to SPARQL against the mapping. |
| **Storage owned**        | `memory`: none (in-process). `qlever`: yes — its own index (`data/qlever/`). | Yes — its own Neo4j instance/container.                    | None — reuses `qlever`'s already-running server and index.           |
| **External service?**    | `memory`: no. `qlever`: yes (QLever server).               | Yes (Neo4j server/container).                               | No new service — depends on `qlever`'s already being up.             |
| **`wx:temperatureC` shows up as** | `?c wx:temperatureC ?t` (a triple pattern)         | `c.temperatureC` (a node property)                          | `wd.temperature(Item(x), Quantity(y, wd.degree_Celsius))` (a mapped Wikidata-shaped statement) |
| **Query generation in this repo** | LLM-generated + validated (the main `weather-graph` demo, both `memory` and `qlever`) | Fixed/hardcoded, no LLM (`demo_neo4j.py`)                   | Fixed/hardcoded, no LLM (`demo_kif.py`)                               |
| **Where it shines in a real project** | Data that's naturally a web of loosely-typed facts, or that needs to interoperate with other RDF/SPARQL sources (e.g. linking into Wikidata itself) without owning a rigid schema. | Data with real, meaningful relationships between entities (which this demo dataset deliberately doesn't have) — traversals, shortest-path, recommendation-style queries where the *connections* are the point. | Aligning your own data to a shared vocabulary (Wikidata's) for interoperability, without migrating storage — e.g. exposing an existing SPARQL endpoint through a semantically richer, third-party-compatible query surface. |

The headline takeaway: **this repo didn't pick "the best" backend — it picked three points on a
spectrum from "no owned model" (KIF) through "owned model, same shape as the source data" (SPARQL/
RDF) to "owned model, different shape" (Neo4j)**, and demonstrated the same 3 Chicago-weather
questions are answerable from any of them. Which one is right for a *real* project depends on
whether your data is naturally graph-shaped with meaningful relationships (lean Neo4j), needs to
interoperate with other RDF/SPARQL data (lean SPARQL, and consider KIF-style mapping if that other
data is Wikidata-shaped), or is small/simple enough that the in-process `memory` backend is all you
ever need.

## See also

- [plans/PLAN_DATA_MIGRATIONS.md](../plans/PLAN_DATA_MIGRATIONS.md) — the plan that produced this
  document, the `data/qlever/` + `data/neo4j/` reorganization, and the SPARQL/QLever test-coverage
  fix.
- [plans/PLAN_NEO4J.md](../plans/PLAN_NEO4J.md), [plans/PLAN_KIF.md](../plans/PLAN_KIF.md) — the
  original design docs for the Neo4j and KIF ports, including the scope decisions each port made
  before implementation.
- [analysis/weather_graph_analysis.md](../analysis/weather_graph_analysis.md),
  [analysis/neo4j_analysis.md](../analysis/neo4j_analysis.md),
  [analysis/ibm_kif_analysis.md](../analysis/ibm_kif_analysis.md) — the technical grounding each
  port was built from.

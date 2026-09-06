# Learning plan: weather-graph, one dataset through four storage backends (and three agent backends)

This is the entry point into weather-graph's backend work. It doesn't replace
[learning_plan_sparql.md](learning_plan_sparql.md), [learning_plan_neo4j.md](learning_plan_neo4j.md),
[learning_plan_kif.md](learning_plan_kif.md), [learning_plan_kif_llm.md](learning_plan_kif_llm.md),
or [learning_plan_agents.md](learning_plan_agents.md) — each of those is the detailed,
backend-specific record (scope decisions, what was built, what broke and got fixed,
live-verification logs). This document is the narrative that ties them together and the
comparisons none of them attempt on their own.

Two independent axes are covered here: **where the weather data lives** (`memory`/`qlever`/`neo4j`/
`kif` — "Comparing the approaches" below) and **how an NL question gets turned into an answer**
(pydantic-ai/LangGraph/BeeAI+Mellea — "Comparing the agent backends" below). The agent axis sits on
top of whichever storage backend is configured; changing one never implies changing the other.

## Key concepts

The shortest path through everything below — one line per idea, pointing at where it's taught in
depth. Skim this first; consult the comparison tables once you know what you're comparing.

- **Triples, not rows.** The ground truth (`model/weather.ttl`) is subject–predicate–object facts,
  not a table — a `City` is just whatever subject has `wx:*` predicates attached. See
  [step 0](#0-modelweatherttl--the-ground-truth) and
  [weather_graph_analysis.md](../analysis/weather_graph_analysis.md).
- **Same data, different location.** `memory` (in-process) and `qlever` (a real SPARQL server) store
  and query the *identical* triples through the *identical* code (`sparql.py`) — moving between them
  changes nothing about the data's shape. See [step 2](#2-qlever--the-same-data-now-a-service).
- **Same facts, different shape.** Neo4j re-represents the same 8 cities as labeled property-graph
  nodes and answers with Cypher instead of SPARQL — the first point in this repo where the *data
  model* itself changes, not just where it's stored. See
  [step 3](#3-neo4j--a-genuinely-different-shape).
  and the [storage comparison table](#comparing-the-approaches).
- **A lens with no data of its own.** KIF adds a semantic-mapping layer (`wx:` triples → Wikidata-shaped
  statements) on top of the *existing* QLever server — no new store, no owned data, the opposite end
  of the spectrum from Neo4j. See [step 4](#4-kif--a-semantic-layer-not-a-new-store).
- **Structured LLM output, not free text.** Every agent backend asks the model for a typed
  `WeatherSparqlSpec` (`models.py`), never a free-form answer — this is what makes the SPARQL it
  produces validatable and repairable at all, independent of which library does the asking. See the
  [agent backends comparison](#comparing-the-agent-backends).
- **One validate/repair contract, three ways to reach it.** `sparql.validate_query()`'s rules
  (SELECT-only, `LIMIT` present, known predicates, parseable SPARQL) are backend-independent;
  `agents/shared.py` implements the generate→validate→repair→relevance-retry loop once and
  pydantic-ai/LangGraph both reuse it directly, while BeeAI+Mellea's Mellea-driven version follows
  the same contract through different machinery. See
  [learning_plan_agents.md](learning_plan_agents.md).
- **"Query before answering" as a guarantee, not a hope.** Each agent backend enforces this a
  different way — pydantic-ai: two sequential Python calls; LangGraph: a linear compiled graph;
  BeeAI: a `ConditionalRequirement` — trading a spectrum from "provable by construction" to
  "enforced by the framework" for how much of the guarantee lives in your own code vs. the library's.
  See the [agent backends comparison](#comparing-the-agent-backends).
- **Correct isn't the same as verified-working.** BeeAI+Mellea is designed to answer the same
  questions as the other two agent backends, but on Ollama + `granite4:micro` it never actually
  finished one live — Mellea's Ollama backend always requests constrained JSON-schema decoding
  (`format=<schema>`) with no escape hatch, the same Ollama feature that also hung for pydantic-ai
  and LangGraph until each switched to a prompt-based alternative. A concrete, measured reason for
  the demotion, not a preference. See
  [learning_plan_agents.md](learning_plan_agents.md#scope-decisions).

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
(an agent backend — pydantic-ai by default; see `docs/QUICKSTART.md`'s "How the pieces map" and
[learning_plan_agents.md](learning_plan_agents.md)) sits on top of whichever storage backend is
configured, and is itself independently selectable via `AGENT_BACKEND` — it's demonstrated here
first, on the simplest storage backend, before any storage-specific complexity is introduced.

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

## Comparing the agent backends

Orthogonal to the storage-backend table above: this is *how* an NL question becomes a validated
SPARQL query and a final answer, independent of where the graph data lives. All three were verified
live against local `granite4:micro` — see
[learning_plan_agents.md](learning_plan_agents.md#verified-live-end-to-end-2026-09-05) for the full
transcript, including one root-caused structural issue shared by all three backends' underlying
structured-output mechanisms, and how each one's library did or didn't offer a way around it.

| | pydantic-ai (default) | LangGraph (variant) | BeeAI + Mellea (opt-in) |
|---|---|---|---|
| **Framework style** | Typed, minimal — structured output is a first-class return type | Graph-based orchestration over explicit nodes/edges | Requirement-driven agent loop + a separate structured-generation library |
| **NL→SPARQL generation** | `Agent(output_type=PromptedOutput(WeatherSparqlSpec))` — schema described in the prompt, response parsed as JSON | `ChatOllama.with_structured_output(WeatherSparqlSpec, method="json_mode")` — same idea, schema has to be spelled out explicitly in the prompt (verified live: unlike `PromptedOutput`, `json_mode` doesn't inject it automatically) | Mellea `@generative` + `RejectionSamplingStrategy` (IVR loop, up to 3 LLM calls before validation even starts) |
| **Forced tool-first guarantee** | Enforced by construction: `answer()` always runs the real query in Python before a second, tool-free agent is asked to phrase a response — no tool for the model to skip | Enforced by the graph's shape: a linear `START -> query -> answer -> END`, so there is no path where `answer` could run first | `ConditionalRequirement(force_at_step=1)` — enforced by the framework's requirement system |
| **Dependencies installed by default** | Yes (core) | Yes (core) | No — `uv sync --extra beeai` opt-in |
| **Ollama's constrained JSON-schema decoding (`format=<schema>`)** | Tried first (`NativeOutput`) — **hung indefinitely** against this model/Ollama version. Library offers an escape hatch: switched to `PromptedOutput` (prompt-based JSON, no `format=<schema>`) — fast and reliable for straightforward questions. | Tried first (default `method="json_schema"`) — **hung indefinitely**, same root cause. Library offers an escape hatch: switched to `method="json_mode"` — fast and reliable for all 3 demo questions once the prompt explicitly named the required JSON keys. | Always uses `format=<schema>` internally (`mellea/backends/ollama.py`) — **no escape hatch in Mellea's public API**. A live run did not complete even the first question after 25+ minutes of continuous, actively-computing model time. This plan's scope keeps BeeAI+Mellea's behavior unchanged, so this is documented, not patched. |
| **Verified live, relative cost per question** | Single-digit seconds for straightforward lookups; the harder ranking question ("three hottest cities") sometimes exhausts pydantic-ai's own output-retry budget against this small model | Single-digit seconds; answered **all 3** demo questions correctly and quickly in every live run performed, including the ranking question | Did not reach an answer within the time budget given to it — see the row above. Consider this backend **unverified-working** on Ollama + `granite4:micro`, not merely slower. |
| **Where it shines in a real project** | You want the smallest, typed surface and don't need a broader agent-orchestration ecosystem | You're already invested in LangChain/LangGraph elsewhere, or need explicit multi-step graph control | You need BeeAI's/Mellea's specific requirement/validation ecosystem, on a model/Ollama combination where Mellea's constrained-decoding call actually returns |

The headline takeaway here mirrors the storage-backend one, with a sharper edge: no single agent
backend is "the best," and all three hit the *same* underlying Ollama compatibility issue with this
small model — but only two of the three libraries exposed a way around it. pydantic-ai and LangGraph
reach the *same* validate/repair contract (`agents/shared.py`) through two different structural
guarantees, both fast once routed around `format=<schema>`; BeeAI+Mellea has no equivalent escape
hatch in its public API, which is the concrete, measured (not just theorized) basis for demoting it
below the "slower" label this plan started with.

## See also

- [plans/PLAN_AGENTS.md](../plans/PLAN_AGENTS.md), [learning_plan_agents.md](learning_plan_agents.md)
  — the design and full live-verification record for the three agent backends above.
- [analysis/weather_graph_agent_analysis.md](../analysis/weather_graph_agent_analysis.md),
  [analysis/pydantic_ai_analysis.md](../analysis/pydantic_ai_analysis.md),
  [analysis/langgraph_analysis.md](../analysis/langgraph_analysis.md) — the technical grounding the
  agent-backend port was built from.
- [plans/PLAN_DATA_MIGRATIONS.md](../plans/PLAN_DATA_MIGRATIONS.md) — the plan that produced this
  document, the `data/qlever/` + `data/neo4j/` reorganization, and the SPARQL/QLever test-coverage
  fix.
- [plans/PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md), [learning_plan_kif_llm.md](learning_plan_kif_llm.md)
  — a second KIF `Store` backend, `kb.filter()` pointed at an LLM instead of SPARQL/QLever, and why
  the two backends' answers are expected to disagree.
- [plans/PLAN_NEO4J.md](../plans/PLAN_NEO4J.md), [plans/PLAN_KIF.md](../plans/PLAN_KIF.md) — the
  original design docs for the Neo4j and KIF ports, including the scope decisions each port made
  before implementation.
- [analysis/weather_graph_analysis.md](../analysis/weather_graph_analysis.md),
  [analysis/neo4j_analysis.md](../analysis/neo4j_analysis.md),
  [analysis/ibm_kif_analysis.md](../analysis/ibm_kif_analysis.md) — the technical grounding each
  port was built from.

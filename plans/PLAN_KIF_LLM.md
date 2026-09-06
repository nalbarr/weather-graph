# PLAN_KIF_LLM.md

## Role
You are a systems architect and want to extend weather-graph's existing KIF port
(`src/weather_graph/kif/`, see `plans/PLAN_KIF.md`) with a second KIF `Store` backend built on
[IBM's `kif-llm-store`](https://github.com/IBM/kif-llm-store) (the "LLM Store" plugin), to
demonstrate that KIF's `Store`/`kb.filter()` interface is itself an abstraction layer — the same
call-site code can be pointed at a hardcoded `SPARQL_Mapping` over QLever (today's `kif.py`) *or*
at an LLM synthesizing Wikidata-shaped statements on the fly, with no change to how the query is
expressed.

## Objectives

Decisions locked in before implementation (resolved via clarifying questions — see each
subsection for the reasoning):

1. **Scope: swap the Store backend, nothing more.** The new client answers the same 3 fixed demo
   questions (`demo.py`'s questions, already ported in `demo_kif.py`) using
   `kif_llm_store.LLM_Store` instead of the SPARQL-backed `Store` in `kif.py` — same
   `kb.filter(subject=..., property=...)` shape, same `city_temperature`/`city_condition`/
   `hottest_cities` function signatures. No query generation, no NL parsing.
   - **Considered and rejected (non-goals — see below):** a hybrid store that falls back from
     SPARQL to the LLM when data is missing, and a KIF QA-based NL agent (kif-llm ships a third
     component, "KIF QA," a natural-language interface — that's a different, larger integration
     point than `LLM_Store` and out of scope here).
2. **Provider: local Ollama, `granite4:micro`.** `LLM_Store` supports `LLM_Providers.OLLAMA` in
   addition to IBM WatsonX/OpenAI (or any LangChain chat model). Using Ollama keeps this consistent
   with every other LLM-touching piece of the repo (the `AGENT_BACKEND` agents from
   `plans/PLAN_AGENTS.md`, all pinned to local `granite4:micro`) — no new API keys, no external
   service.
3. **Subject mapping fork — real Wikidata items, not local `wx:cityN` IRIs.** This is the key place
   this plan diverges from `kif.py`'s existing design and must be stated explicitly, the same way
   `plans/PLAN_KIF.md` had to state its own vocabulary-mapping decisions:
   - `kif.py`'s SPARQL-backed store queries **local** `wx:` triples via a `SPARQL_Mapping`, so its
     city subjects are the local `wx:cityN` IRIs (`CITY_NAMES` dict) — there's no Wikidata Q-ID
     involved.
   - `LLM_Store` has no access to local `wx:` data at all — it *is* the knowledge source, synthesizing
     answers from the model's own training. Querying it with a local `wx:cityN` IRI as subject is
     meaningless (the LLM has never seen that IRI). The new client must instead use real Wikidata
     city items (`wd.Chicago`, `wd.Paris`, etc., or an explicit `Item(IRI("wd:Q..."))` where a
     named constant doesn't exist in `kif_lib.vocabulary.wd`) so the LLM has something real to
     answer about.
   - Sub agent 2 confirms, for each of the 8 cities in `kif.py`'s `CITY_NAMES`, whether a named
     `wd.<City>` constant exists; sub agent 3 records the final mapping (named constant vs.
     explicit Q-ID) in the new module, mirroring how `kif.py`'s own header comment documents its
     mapping choices.
4. **Property mapping stays `wd.temperature` (P2076) / `wd.weather_history` (P4150) — same
   properties `kif.py` already uses**, specifically so the two stores are queried with the *same*
   `(subject, property)` shape and only the `Store` differs. This reuses `kif.py`'s own accepted
   "loose fit" tradeoff (P2076/P4150 aren't a clean semantic match for "current weather" even in
   real Wikidata) rather than picking new properties — sub agent 2 should note in
   `analysis/kif_llm_analysis.md` what the LLM actually does when asked about a property Wikidata
   itself doesn't really use this way (answers something plausible-but-unverifiable, refuses,
   returns nothing) since that's a real, useful finding for the comparison in objective 5.
5. **Grounding mismatch is treated as the point, not a bug — the demo compares both answers.** This
   repo's weather data is synthetic (`model/weather.ttl`, loaded fresh by `make qlever-up`); an LLM
   asked "what's Chicago's temperature" will answer from real-world/training knowledge, which will
   essentially never match the synthetic value. `demo_kif_llm.py` runs each of the 3 questions
   through **both** `kif.py` (ground truth, local synthetic data) and the new LLM-backed module
   side by side and prints both answers labeled accordingly, and `docs/learning_plan_kif_llm.md`
   calls out *why* they differ — this is the concrete, hands-on illustration of "same interface,
   different epistemics" rather than something left implicit for a reader to puzzle out.
6. **Dependency: vendor a patched copy in-repo, not a pip extra — revised after real-world
   research.** The original plan (an opt-in `kif-llm` extra mirroring `beeai`) assumed
   `kif-llm-store` was pip-installable. Sub agent 2's research found it isn't, as of `IBM/kif-llm @
   cb91defc` (2026-09-06): its own `pyproject.toml` has an invalid-TOML trailing comma, it's not on
   PyPI, and five more real bugs (an absolute self-import that assumes the wrong package name; a
   `LLM_Store.__init__` the README's own example can't satisfy — `target_store`/`searcher` have no
   defaults; a `model_params=None` crash; subjects needing a registered `.label` via `wd.Q(...)`,
   not a bare `Item(IRI(...))`; an undeclared, partly-broken `kbel` runtime dependency) block even a
   from-source install. All six were confirmed reproducible from a clean clone and hand-patched to
   get real, live calls working against local Ollama — see `analysis/kif_llm_analysis.md` for the
   full evidence and captured output. Decision (confirmed with the user after presenting this
   finding and the alternatives — fork upstream, ship docs-only, or hand-roll a from-scratch store —
   see that analysis doc's "Recommended pyproject.toml extra" section for the full tradeoff table):
   - Vendor the small slice of `llm_store/` (minus `context_generator/`/`query_to_question/`, unused
     here) and `kbel/disambiguators/` (`abc.py` + `simple.py` only — *not* the
     `sentence-transformers`-based `similarity.py`, *not* `llm_disambiguator.py`) into
     `src/weather_graph/kif/_vendor/kif_llm_store/` and `src/weather_graph/kif/_vendor/kbel/`, as
     ordinary source files, not a package dependency.
   - Apply exactly the two patches sub agent 2 proved necessary: fix
     `compiler/llm/filter_compiler.py`'s absolute `from llm_store.constants import ...` to a
     relative import; fix `kbel/disambiguators/__init__.py`'s missing `SimpleDisambiguator`/
     `LLM_Disambiguator` re-exports.
   - A header comment in each vendored file's package `__init__.py` documents: the upstream source
     (`IBM/kif-llm @ cb91defc`, Apache-2.0), that it's a patched subset, and exactly what was
     patched and why — so a future update against a fixed upstream release knows what to diff
     against and can delete the vendor directory once `kif-llm-store` is genuinely pip-installable.
   - The only genuinely new `[project.optional-dependencies]` entry is `kif-llm =
     ["nest-asyncio>=1.6.0,<2.0.0"]` (`llm_store`'s other real transitive deps —
     `langchain-ollama`, `httpx`, `tenacity` — are already core dependencies at compatible
     versions). `kif-llm-check` (Makefile) verifies both the vendored package imports and
     `nest-asyncio` is installed.
   - Tests (`tests/test_kif_llm.py`) skip cleanly when `nest-asyncio` isn't installed (mirrors the
     existing extras-skip pattern) — the vendored code itself always ships with the repo, so the
     only "not installed" condition left to guard is the one real extra dependency.
7. **Architecture: a three-way split, not a one-off mirror.** Rather than having `llm_store.py`
   informally "look like" `kif.py` by eye, the two stores are made to satisfy one explicit,
   documented contract, with each concern in its own file — the same separation-of-concerns pattern
   the repo already uses elsewhere (`agents/__init__.py:build_agent`, `GRAPH_BACKEND` dispatch):
   - **Shared contract** (`src/weather_graph/kif/base.py`, new) — a `typing.Protocol` declaring the
     shape both stores must satisfy: `get_store()`, `city_temperature(name)`, `city_condition(name)`,
     `hottest_cities(limit)`. This is *structural* typing (PEP 544) — `kif.py` satisfies it by
     shape alone, with no inheritance and no code changes required, so this stays compatible with
     the "no change to the existing hardcoded SPARQL/QLever KIF backend" non-goal below. If sub
     agent 1 finds `kif.py`'s current signatures don't quite line up (e.g. a missing return type
     annotation the `Protocol` wants to be explicit about), that's a minor conformance note, not a
     rewrite.
   - **Vocabulary/subject mapping, one module per backend** — `kif/mapping.py` (existing,
     `SPARQL_Mapping` + local `wx:cityN` IRIs) stays as-is; a new `kif/wikidata_mapping.py` holds
     the LLM backend's `CITY_NAMES`→`wd.<City>`/Q-ID table from objective 3, isolated the same way.
     This keeps the "which IRI means Chicago" reasoning diffable in one small file per backend.
   - **Store wiring, one module per backend** — `kif.py` (existing) and the new `llm_store.py` each
     shrink to just `Store` construction + `kb.filter()` calls, importing their respective mapping
     module and satisfying `base.Protocol`. Neither file needs to know the other exists.
   - **Comparison, one module** — `demo_kif_llm.py` imports both backend modules through
     `base.Protocol` and iterates `[kif, llm_store]` generically (same question loop run twice)
     rather than hardcoding two separate call sequences, per objective 5.
   - Tradeoff, stated plainly: this is more scaffolding (2 new small files) than a bare "copy
     `kif.py`, swap the `Store`" approach would need for what's currently a 2-backend comparison —
     accepted because it matches the dispatch pattern already used elsewhere in the repo and gives
     any future third KIF `Store` backend the same seams to slot into.

### Non-goals

- No hybrid/fallback store composing SPARQL and LLM answers into one result — each store is
  queried and shown independently (see objective 5).
- No KIF QA-based natural-language agent — this plan is scoped to the `LLM_Store` plugin only, not
  kif-llm's separate NL-interface component.
- No *behavioral* change to the existing hardcoded SPARQL/QLever KIF backend (`kif.py`,
  `mapping.py`, `demo_kif.py`, `test_kif.py`) — it stays as the "ground truth" reference
  implementation, and satisfies the new `base.Protocol` structurally (see objective 7) with no code
  changes expected beyond a possible minor type-annotation conformance fix.
- No change to `GRAPH_BACKEND`, `AGENT_BACKEND`, the Neo4j demo, or the 3 fixed demo questions
  themselves.

## Agents

### Orchestrator
- Branch: this work happens on `dev-20260905c-na` (already checked out off latest `main`).
- The orchestrator manages three sub agents: sub agents 1 and 2 are independent (1 analyzes the
  existing KIF backend as the reference shape to mirror; 2 researches `kif-llm-store` — neither
  depends on the other) and can run in parallel; sub agent 3 depends on both.
- Will summarize the final design/verification as:
  - `docs/learning_plan_kif_llm.md` — new doc, same format as `docs/learning_plan_kif.md`, including
    the side-by-side answer comparison from objective 5 with actual output captured during
    verification (not hypothetical).
- Will update `docs/learning_plan_kif.md` — add a short pointer section (not a rewrite) noting a
  second KIF `Store` backend now exists, linking to `docs/learning_plan_kif_llm.md` for the
  LLM-backed comparison.
- Will update `docs/learning_plan.md`:
  - Add `docs/learning_plan_kif_llm.md` to the doc list / `## See also` alongside the existing
    `plans/PLAN_KIF.md` and `docs/learning_plan_kif.md` entries.
  - No new row in the existing `## Comparing the approaches` table — that table compares
    *storage* backends (memory/qlever/neo4j/kif); this plan adds a second `Store` *within* the KIF
    backend, which is a narrower, KIF-internal comparison that belongs in
    `docs/learning_plan_kif_llm.md`, not a new column there.
- Will update `Makefile` with a `kif-llm-check` target verifying the vendored
  `kif/_vendor/kif_llm_store` package imports cleanly and `nest-asyncio` is installed (mirrors
  `kif-check`/`beeai-check`), with an install hint (`uv sync --extra kif-llm`) if the latter is
  missing — KIF-LLM needs no server lifecycle target (no new service, just a local Ollama call,
  already covered by existing Ollama setup).
- Will update `pyproject.toml`: new `[project.optional-dependencies]` extra `kif-llm =
  ["nest-asyncio>=1.6.0,<2.0.0"]` (per objective 6's revised vendoring decision — the vendored code
  itself ships as ordinary source files, not a package dependency), not added to core
  `dependencies`.
- Will update `docs/QUICKSTART.md` (the KIF section) to mention the second, LLM-backed client and
  its `uv sync --extra kif-llm` install step, mirroring how the `beeai` extra is documented there.

### Sub agent 1
- Focused on analyzing the *existing* KIF backend as the reference implementation the new client
  must mirror the shape of — not the whole repo generically (that's already covered by the
  existing `analysis/weather_graph_analysis.md` from the Neo4j/KIF ports), but specifically
  `src/weather_graph/kif/`.
- Inputs:
  - `src/weather_graph/kif/kif.py`, `src/weather_graph/kif/mapping.py`, `demo_kif.py`,
    `tests/test_kif.py`, `plans/PLAN_KIF.md`, `analysis/ibm_kif_analysis.md`
- Outputs:
  - `analysis/kif_backend_analysis.md` covering:
    - The exact call-site shapes to mirror: `get_store()` (singleton via `lru_cache`),
      `city_temperature(name)`, `city_condition(name)`, `hottest_cities(limit)`, and the
      `ValueSnak`/`Quantity`/`String` assertions each makes on `kb.filter()` results.
    - The `CITY_NAMES` dict and `_city_item`/`_name_of` helpers, and which parts are
      SPARQL/`wx:`-specific (won't carry over) vs. generic KIF plumbing (will carry over
      unchanged).
    - How `demo_kif.py` and `tests/test_kif.py` are structured, so the new demo/test files can
      follow the same pattern (skip-cleanly-when-unavailable, same question set, same assertions
      style).
    - A proposed `typing.Protocol` for `src/weather_graph/kif/base.py` (objective 7) capturing
      `get_store()`/`city_temperature(name)`/`city_condition(name)`/`hottest_cities(limit)`, and
      confirmation that `kif.py`'s current signatures satisfy it structurally as-is (or a note of
      the minimal conformance fix needed if not).

### Sub agent 2
- Focused on researching `kif-llm-store`'s `LLM_Store`: package/import name, pinned version,
  `Store` construction for the Ollama provider, and what it actually returns.
- Inputs:
  - `kif-llm-store` source/docs (https://github.com/IBM/kif-llm-store)
  - `analysis/ibm_kif_analysis.md` (existing, general `kif_lib` background)
- Outputs:
  - `analysis/kif_llm_analysis.md` covering:
    - `LLM_Store` construction for `LLM_Providers.OLLAMA`: required/optional kwargs (`model_id`,
      `base_url` or equivalent — confirm whether it reuses the existing `OLLAMA_HOST` value the
      same way the `AGENT_BACKEND` agents do, per the derivation precedent in
      `plans/PLAN_AGENTS.md`), pinned package version.
    - Confirmation that `kb.filter(subject=..., property=..., limit=...)` against `LLM_Store`
      returns the same `Statement`/`ValueSnak`/`Quantity`/`String` shapes `kif.py` already asserts
      on, so sub agent 3's functions can mirror `kif.py`'s assertions rather than inventing new
      response handling.
    - For each of the 8 cities in `kif.py`'s `CITY_NAMES` (Chicago, Paris, London, Cairo, Tokyo,
      Oslo, Nairobi, Sydney): whether a named `wd.<City>` constant exists in
      `kif_lib.vocabulary.wd`, and the explicit `Item(IRI("wd:Q..."))` fallback for any that don't.
    - A quick empirical check (live call against local Ollama `granite4:micro`, if feasible) of
      what `LLM_Store` actually returns for `(wd.Chicago, wd.temperature)` and
      `(wd.Chicago, wd.weather_history)` — a plausible-but-unverifiable value, an empty result, or
      an error — recorded as a real finding, not assumed.

### Sub agent 3
- Focused on implementing the new client per sub agents 1 and 2's findings and the decisions in
  Objectives above.
- Inputs:
  - `analysis/kif_backend_analysis.md`, `analysis/kif_llm_analysis.md`
- Outputs — per the three-way split in objective 7 and the vendoring decision in objective 6 (same
  package as the existing KIF backend, not a new top-level package):
  - `src/weather_graph/kif/_vendor/kif_llm_store/` and `src/weather_graph/kif/_vendor/kbel/` (new)
    — the patched subset of upstream `llm_store/` and `kbel/disambiguators/` per
    `analysis/kif_llm_analysis.md`'s "Recommended pyproject.toml extra" §1: the relative-import fix
    to `filter_compiler.py`, the `kbel/disambiguators/__init__.py` re-export fix, a header comment
    per vendored package documenting the upstream source commit (`IBM/kif-llm @ cb91defc`,
    Apache-2.0), license, and exactly what was patched.
  - `src/weather_graph/kif/base.py` (new) — the `typing.Protocol` sub agent 1 proposed, plus a
    module docstring stating that `kif.py` and `llm_store.py` both satisfy it structurally.
  - `src/weather_graph/kif/wikidata_mapping.py` (new) — the LLM backend's `CITY_NAMES`→`wd.<City>`/
    Q-ID table from objective 3 (`wd.Paris` for the one named constant; `wd.Q(<id>, "<Label>")` for
    the other 7 — a bare `Item(IRI(...))` fails `LLM_Store`'s label assertion, confirmed in
    `analysis/kif_llm_analysis.md`), isolated from store wiring the same way `mapping.py` isolates
    the SPARQL side's vocabulary.
  - `src/weather_graph/kif/llm_store.py` (new) — store wiring only:
    - `get_store()` — builds the vendored `LLM_Store` with `Store('empty')`/`Search('empty')` as
      the required `target_store`/`searcher` no-ops, `model_params={}` (required — `None` crashes
      construction), `llm_provider=LLM_Providers.OLLAMA`, `model_id` from `KIF_LLM_MODEL`,
      `base_url` from `OLLAMA_HOST` — mirroring `kif.py`'s `lru_cache`-singleton pattern.
    - `city_temperature(name)`, `city_condition(name)` — same signatures as `kif.py` (verified
      against `base.Protocol`), querying the Wikidata city items from `wikidata_mapping.py`,
      wrapping `kb.filter()` in a `try/except` catching at least `decimal.InvalidOperation` (a
      confirmed real, non-deterministic upstream crash on answers with no digits — see
      "Confirmed live" / "Also observed" in `analysis/kif_llm_analysis.md`) and returning `None`
      on failure rather than propagating it, matching `kif.py`'s existing not-found-returns-None
      contract.
    - `hottest_cities(limit)` — first empirically confirm (per that analysis doc's open question)
      whether an unbound-subject `kb.filter(property=wd.temperature)` works against `LLM_Store`; if
      not, fall back to calling `city_temperature` once per `CITY_NAMES` entry and sorting in
      Python, same pattern `kif.py` already uses internally.
  - `src/weather_graph/demo_kif_llm.py` — imports `kif` and `llm_store` through `base.Protocol` and
    runs the same 3 fixed demo questions through **both** generically (one question loop, not two
    hardcoded call sequences), printing both answers labeled `[SPARQL/QLever]` / `[LLM Store]` side
    by side per objective 5, tolerating a `None` LLM-side answer (crash/no-answer case) without the
    demo itself crashing.
  - `tests/test_kif_llm.py` — unit tests exercising the new module's functions against real Ollama,
    skipping cleanly (not failing) when `nest-asyncio` isn't installed or Ollama isn't reachable,
    mirroring `tests/test_kif.py`'s skip pattern — assertions on *shape* (a `float`/`None` for
    temperature, a `str`/`None` for condition), not exact values, since the LLM's answers aren't
    reproducible (per objective 5, they're expected to differ from — and even vary run to run
    around — the synthetic ground truth).
  - `.env.example` additions: `KIF_LLM_MODEL="granite4:micro"` (new), reusing the existing
    `OLLAMA_HOST` var — confirmed by sub agent 2 to pass straight through to `ChatOllama(base_url=)`
    with no reshaping, identical to `langgraph_agent.py`'s existing usage.

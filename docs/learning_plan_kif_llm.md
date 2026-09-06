# Learning plan: a second KIF Store backend, LLM instead of SPARQL

Summary of the work done per [PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md), on branch
`dev-20260905c-na`, extending the existing KIF port
([learning_plan_kif.md](learning_plan_kif.md)).

## The point of this backend

[KIF](https://github.com/IBM/kif)'s `Store`/`kb.filter(subject=..., property=...)` interface is
itself an abstraction layer — the same call site can be pointed at very different knowledge
sources with no change to how the query is expressed. The existing `kif.py` backend proves this
against a hardcoded `SPARQL_Mapping` over local QLever. This second backend
(`src/weather_graph/kif/llm_store.py`) proves it again against IBM's `kif-llm-store` `LLM_Store`,
which lets `kb.filter()` query a local Ollama model (`granite4:micro`) as a Wikidata-shaped
knowledge source instead.

The two backends are not trying to agree. `kif.py` reads synthetic triples from
`model/weather.ttl`; `llm_store.py` answers from whatever the model believes about the real world.
`demo_kif_llm.py` runs both through the identical call shape and prints both answers side by side
specifically so that mismatch is visible, not hidden — see "Verified live" below for real captured
output.

## Scope decisions

- **Swap the Store, nothing more.** Same 3 fixed demo questions as `demo_kif.py`, same
  `city_temperature`/`city_condition`/`hottest_cities` function shapes. No hybrid fallback between
  the two stores, no natural-language agent (kif-llm ships a separate "KIF QA" component; this
  plan only uses `LLM_Store`) — both considered and explicitly rejected as non-goals.
- **Local Ollama, `granite4:micro`.** Consistent with every other LLM-touching part of this repo
  ([learning_plan_agents.md](learning_plan_agents.md)'s three agent backends). `LLM_Store` also
  supports IBM WatsonX/OpenAI/any LangChain chat model, unused here.
- **Real Wikidata items as subjects, not local `wx:cityN` IRIs — the one place this backend's
  design genuinely forks from `kif.py`'s.** `LLM_Store` has no access to `model/weather.ttl`'s
  local triples; it *is* the knowledge source. A local `wx:city0` IRI means nothing to it. The 8
  cities are re-expressed as real Wikidata items (`wd.Paris`, or `wd.Q(<id>, "<Label>")` for the
  other 7 — `kif_lib.vocabulary.wd` only ships one of the 8 as a named constant) in a new,
  separate `wikidata_mapping.py`, isolated from store wiring the same way `mapping.py` isolates
  the SPARQL side's vocabulary.
- **Same properties, `wd.temperature`/`wd.weather_history`, reused deliberately.** Keeping the
  `(subject, property)` shape identical to `kif.py`'s is what makes the comparison mean something
  — only the `Store` differs.
- **The grounding mismatch is the point, not a bug.** `demo_kif_llm.py` prints both backends'
  answers labeled side by side rather than picking a "winner."
- **Architecture: a three-way split** (`base.py` shared `Protocol`, per-backend mapping module,
  per-backend store-wiring module) rather than one `llm_store.py` mirroring `kif.py` by eye —
  matches the dispatch pattern this repo already uses elsewhere (`agents/__init__.py:build_agent`,
  `GRAPH_BACKEND`). `kif.py` needed zero code changes to satisfy the shared `Protocol`
  structurally (PEP 544, mypy-verified — see `analysis/kif_backend_analysis.md`).

## The dependency problem, and how it was resolved

The plan originally assumed `kif-llm-store` was an ordinary pip extra, mirroring the `beeai` extra
from [learning_plan_agents.md](learning_plan_agents.md). Research
(`analysis/kif_llm_analysis.md`) found this isn't true: as of `IBM/kif-llm @ cb91defc`
(2026-09-06), the package **cannot be installed at all**, on any branch:

- Its own `pyproject.toml` has an invalid-TOML trailing comma — `uv pip install` fails at the
  metadata-parsing step, before any code even runs.
- It isn't published to PyPI.
- Five more real code bugs block it even once the TOML is worked around: an absolute self-import
  that assumes the wrong installed package name; `LLM_Store.__init__` requiring `target_store`/
  `searcher` arguments the README's own quickstart omits; a `model_params=None` crash; subjects
  needing a registered `.label`, not a bare `Item(IRI(...))`; an undeclared, partly-broken `kbel`
  runtime dependency (missing re-exports).

Every one of these was confirmed reproducible from a clean clone, then hand-patched to get real,
live `kb.filter()` calls working against local Ollama — that patched result is what's vendored.
Presented with this finding and the alternatives (fork upstream on GitHub; ship analysis-only, no
runnable code; hand-roll a from-scratch store instead of adopting IBM's package), the chosen path
was: **vendor a small, patched copy in-repo.**

`src/weather_graph/kif/_vendor/kif_llm_store/` and `.../kbel/` hold the patched subset
(`llm_store/` minus `context_generator/`/`query_to_question/`, unused here; just
`kbel/disambiguators/abc.py`+`simple.py`, not the `sentence-transformers`-based
`similarity.py`/`llm_disambiguator.py`) as ordinary source files, not a package dependency. Three
patches, each marked in place with a `PATCH N (weather-graph vendor)` comment (see
`_vendor/kif_llm_store/__init__.py`'s header for the full account, including the upstream commit
hash and Apache-2.0 license attribution):

1. `filter_compiler.py`'s absolute `from llm_store.constants import ...` made relative.
2. `kbel/disambiguators/__init__.py`'s missing `SimpleDisambiguator` re-export added.
3. `llm.py`'s `_disambiguate()` import retargeted at the vendored `kbel` subset, dropping the
   unused `LLM_Disambiguator` name (its module isn't vendored — this repo never sets
   `entity_linking_method=LLM`, since its properties are quantity/string-valued and skip
   disambiguation entirely).

The only genuinely new `[project.optional-dependencies]` entry is `kif-llm =
["nest-asyncio>=1.6.0,<2.0.0"]` — `llm_store`'s other real transitive dependencies
(`langchain-ollama`, `httpx`, `tenacity`) were already core dependencies at compatible versions.
Delete `_vendor/` once `kif-llm-store` ships genuinely pip-installable; the PATCH markers are what
to diff against upstream then.

## Two more findings only discoverable by actually running it

- **`LLM_Store`'s failure mode for "no answer" is a crash, not an empty result.** Its output
  parser strips non-numeric characters from the model's reply and calls `Decimal()` on what's
  left, catching only `ValueError` — a hedge or refusal with no digits raises an uncaught
  `decimal.InvalidOperation`, and this is non-deterministic: the identical call can succeed on one
  run and crash on the next. `llm_store.py`'s `city_temperature`/`city_condition` catch this and
  return `None`, matching `kif.py`'s existing not-found-returns-`None` contract.
- **Unbound-subject filters don't work against `LLM_Store`.** `kif.py`'s `hottest_cities` issues
  one `kb.filter(property=wd.temperature)` with no `subject=` and sorts client-side — there's no
  entity for the LLM to build a prompt around without one. Measured directly: 4 live runs of that
  same shape against `LLM_Store` returned zero statements twice and crashed twice; never once
  returned per-city readings. `llm_store.hottest_cities` instead calls `city_temperature` once per
  city and sorts in Python — the fallback the plan anticipated, confirmed necessary by evidence
  rather than assumed up front.

## What was built

- `src/weather_graph/kif/base.py` — `typing.Protocol` (`KIFBackend`) both `kif.py` and
  `llm_store.py` satisfy structurally; `demo_kif_llm.py` treats the two imported modules
  interchangeably through it.
- `src/weather_graph/kif/wikidata_mapping.py` — the LLM backend's city vocabulary (`CITY_ITEMS`:
  display name → real Wikidata `Item`).
- `src/weather_graph/kif/llm_store.py` — store wiring: `get_store()`, `city_temperature`,
  `city_condition`, `hottest_cities`.
- `src/weather_graph/kif/_vendor/` — the patched vendor tree described above.
- `src/weather_graph/demo_kif_llm.py` — `uv run weather-graph-kif-llm`; the side-by-side demo.
- `tests/test_kif_llm.py` — two-layer skip (extra not installed / Ollama not reachable, mirroring
  `test_kif.py`'s pattern), assertions on **shape** rather than exact values (the LLM's answers
  aren't reproducible, by design — see "grounding mismatch" above).
- `pyproject.toml`: `kif-llm` extra, `weather-graph-kif-llm` script entry, an `extend-exclude` for
  the vendored tree (kept close to verbatim so it stays diffable against upstream, not held to this
  repo's lint rules).
- `.env.example`: `KIF_LLM_MODEL="granite4:micro"` — `OLLAMA_HOST` is reused as-is for the
  endpoint, no new host var (`base_url` passes straight through to `ChatOllama` unchanged, the same
  derivation `agents/langgraph_agent.py` already uses).
- `Makefile`: `kif-llm-check` — verifies the vendored package imports and `nest-asyncio` is
  installed.

## Verified live, end-to-end

- `uv run ruff check .` — clean (vendored tree excluded, see above).
- `uv run pytest` — **44 passed, 3 skipped** (the 3 skips are pre-existing `test_neo4j.py`, no
  Neo4j running this session — unrelated). `test_kif_llm.py`'s tests ran genuinely live (confirmed
  via timing: ~3.8s for `hottest_cities`' 8 sequential Ollama calls), not silently skipped.
- **Both skip layers proven for real, not just written**: `uv sync` without `--extra kif-llm` →
  `test_kif_llm.py` reports `1 skipped`; re-synced with the extra → back to 4 passed.
- Protocol conformance re-verified for *both* backends this time (mypy: `use(kif)` and
  `use(llm_store)` against `base.KIFBackend`, zero errors; runtime `isinstance` → `True` for both).
- `kif.py`, `mapping.py`, `demo_kif.py`, `tests/test_kif.py` confirmed untouched (empty diff) — the
  plan's non-goal held.

### `uv run weather-graph-kif-llm` — three real runs

```
=== Q: What is the weather like in Chicago right now, and is it warm?
A: [SPARQL/QLever] Chicago is 21.0°C and 'Partly Cloudy'.
A: [LLM Store] Chicago is -10.2°C and 'has seen some of the coldest winters'.

=== Q: Is Chicago one of the three hottest cities in the data?
A: [SPARQL/QLever] Top 3 hottest: Cairo, Sydney, Nairobi. Chicago is hottest-3: False.
A: [LLM Store] Top 3 hottest: Cairo, Oslo, London. Chicago is hottest-3: False.

=== Q: Is it currently raining or snowing in Chicago?
A: [SPARQL/QLever] Condition is 'Partly Cloudy' (raining/snowing: False).
A: [LLM Store] Condition is 'includes' (raining/snowing: False).
```

Two more runs, same questions, `[SPARQL/QLever]` column omitted since it was byte-identical every
time (`21.0°C`/`'Partly Cloudy'`, `Cairo, Sydney, Nairobi`, `'Partly Cloudy'`):

- Run 2 — `[LLM Store]`: `32.0°C` and `'climate trends'`; hottest `Cairo, Paris, London`; condition
  `'influenced'`.
- Run 1 — `[LLM Store]`: `1000000.0°C` and `'recorded by weather stations'`; hottest `Cairo,
  Nairobi, London`; condition `'temperature records'`.

This is the finding, laid out plainly: the SPARQL column never moves — it's reading the same fixed
triples every time. The LLM column moves every run, ranges from a plausible `32.0°C` down to a
parser artifact (`1000000.0°C`, likely a comma-grouped number stripped of its separators and
misread), and its `wd.weather_history` answers are consistently the *concept* "weather history"
rather than an actual condition (`'climate trends'`, `'temperature records'`, `'includes'`) — the
plausible-but-unverifiable outcome predicted for a Wikidata property that isn't really used this
way, now observed for real. `Oslo` and `London` showing up in the LLM's "hottest 3" is a clean,
self-evident demonstration that these particular numbers aren't grounded in anything — same
interface, same query shape, genuinely different epistemics.

## See also

[PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md) for the full design and the clarifying-questions
record; [analysis/kif_backend_analysis.md](../analysis/kif_backend_analysis.md) and
[analysis/kif_llm_analysis.md](../analysis/kif_llm_analysis.md) for the technical grounding (both
written from direct source reading and live experimentation, not the READMEs alone);
[learning_plan_kif.md](learning_plan_kif.md) for the first KIF backend this one sits alongside.

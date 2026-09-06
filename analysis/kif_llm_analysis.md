# kif-llm-store analysis (sub-agent 2)

Analysis of IBM's `kif-llm-store` (`LLM_Store`) for `plans/PLAN_KIF_LLM.md`, grounded in reading
the actual upstream source, a real `pip`/`uv` install attempt, and live-testing against local
Ollama (`granite4:micro`) — not just the README. **Bottom line up front: the package cannot
currently be installed or imported as documented. Every claim below that says "confirmed live" was
verified by hand-patching a local checkout to work around specific, reproducible upstream bugs; the
patches themselves are the deliverable an implementer needs.**

## Where the package actually lives (README/PyPI are stale)

- `https://github.com/IBM/kif-llm-store` **redirects** (HTTP 301, confirmed via the GitHub API,
  `repositories/827452673`) to `https://github.com/IBM/kif-llm` — a monorepo containing four
  sibling projects (`llm_store/`, `kbel/`, `kifqa/`, `kifqa-ui/`). The `LLM_Store` code itself lives
  in the `llm_store/` subdirectory of that repo, not at the repo root.
- **Not on PyPI.** `curl https://pypi.org/pypi/kif-llm-store/json` → 404. `uv pip install
  kif-llm-store` → "kif-llm-store was not found in the package registry." The `llm_store/README.md`
  itself says so under "Using PyPI (soon)" — still true as of this writing (2026-09-06, `main` @
  `cb91defc`). Installing it today means installing from git/source, which — see below — currently
  fails outright.
- Declared package metadata (`llm_store/pyproject.toml`): `name = "kif-llm-store"`, `version =
  "0.1.0"`, `requires-python = ">=3.11"`, Poetry backend. **Identical content exists on the `dev`
  branch too** — this isn't a stale `main`, it's the current state of the whole repo.

## Confirmed blocker #1: the package's own `pyproject.toml` is invalid TOML

`llm_store/pyproject.toml` line 17:

```toml
httpx = ">=0.28.1,<0.29.0",
```

A trailing comma after a plain (non-array) key/value pair is a TOML syntax error. Verified two
independent ways:
1. `python3 -c "import tomllib; tomllib.loads(open('pyproject.toml','rb').read())"` →
   `INVALID TOML: Expected newline or end of document after a statement (at line 17, column 27)`.
2. Actually tried the install this repo's `uv` would use:
   ```
   uv pip install "kif-llm-store @ git+https://github.com/IBM/kif-llm.git#subdirectory=llm_store"
   ```
   fails with:
   ```
   × Failed to download and build `kif-llm-store @ git+https://github.com/IBM/kif-llm.git#subdirectory=llm_store`
   ├─▶ Failed to parse metadata from built wheel
   ├─▶ Invalid `pyproject.toml`
   ╰─▶ TOML parse error at line 17, column 27
   ```

There is **no way to `pip`/`uv install` this package from its current source, on any branch,
today.** This is not an environment problem on our side — it reproduces identically from a clean
`git clone`.

## Confirmed blocker #2: internal import-name inconsistency (`kif_llm_store` vs `llm_store`)

The README/example notebook (`examples/kif-llm-store.ipynb`) both import the package as
`kif_llm_store` (matching the PyPI-normalized form of `kif-llm-store`):

```python
from kif_llm_store import *
from kif_llm_store.store.llm.constants import LLM_Providers, EntityResolutionMethod
```

But the source directory is named `llm_store`, and `llm_store/compiler/llm/filter_compiler.py`
line 27 has an **absolute** self-import: `from llm_store.constants import (...)` — not a relative
import like every other internal module uses. So:
- If you rename/install the `llm_store/` directory as `kif_llm_store` (as the project-name
  normalization and the README's own import both imply you should), `filter_compiler.py`'s
  `from llm_store.constants import ...` raises `ModuleNotFoundError: No module named 'llm_store'`.
- If you instead keep the directory's real name (`llm_store`) and import it as `import llm_store`,
  the internal imports are self-consistent and it works — **but that contradicts the documented
  public API** (`from kif_llm_store import LLM_Store`), and the `kif_llm_store.store.llm.constants`
  import path in the README/notebook doesn't exist either way (the real path, once importable, is
  `llm_store.constants` / `kif_llm_store.constants` depending on which name you install under).

Also note `EntityResolutionMethod`, imported by the notebook, doesn't exist in the current source
at all — the real class is `EntityLinkingMethod` (`llm_store/constants.py`). Another
README/notebook-vs-code drift.

**Verified workaround used for all live testing below:** copy `llm_store/` into a scratch
directory, keep it named `llm_store` (do not rename it), add that directory's parent to
`PYTHONPATH`, and `import llm_store` directly — bypassing the broken `pyproject.toml`/build step
entirely (no wheel is built; Python just finds the package via `sys.path`). This is the shape any
in-repo vendoring approach (see recommendation below) should also use, but renamed correctly
end-to-end (fix the one absolute import, then it's safe to call the vendored package
`kif_llm_store` throughout).

## Confirmed blocker #3: `LLM_Store.__init__` requires `target_store` and `searcher` — the README's own quickstart is broken

`llm_store/llm.py`, `LLM_Store.__init__` signature (introspected live):

```python
def __init__(self, store_name: str, target_store: Store, searcher: Search,
             model: Optional[BaseChatModel] = None,
             llm_provider: Optional[LLM_Providers] = None,
             model_id: Optional[str] = None, base_url: Optional[str] = None,
             api_key: Optional[str] = None, ..., model_params: Optional[Dict[str, Any]] = None,
             **kwargs: Any) -> None
```

`target_store` and `searcher` have **no defaults**. The README's own "Getting started" example —

```python
kb = Store(LLM_Store.store_name, llm_provider=LLM_Providers.OLLAMA, model_id=..., base_url=...)
```

— omits both and, run against the actual current source, raises:

```
TypeError: LLM_Store.__init__() missing 2 required positional arguments: 'target_store' and 'searcher'
```

(Confirmed live via `kif_lib.Store('llm', llm_provider=LLM_Providers.OLLAMA, model_id='granite4:micro', base_url='http://127.0.0.1:11434')`.)

**Verified workaround:** `kif_lib` ships harmless no-op plugins for exactly this: `Store('empty')`
and `Search('empty')`. Passing those as the two extra positional args works:

```python
from kif_lib import Store, Search
target = Store('empty')
searcher = Search('empty')
kb = Store('llm', target, searcher, llm_provider=LLM_Providers.OLLAMA,
           model_id='granite4:micro', base_url='http://127.0.0.1:11434', model_params={})
```

(`target_store`/`searcher` are used internally for entity disambiguation fallback/search — see
`_disambiguate`, below — not for the primary Ollama call path, so wiring them to no-ops is
semantically fine for this repo's fixed-question use case.)

## Confirmed blocker #4: `model_params=None` crashes `_init_model`

`LLM_Store.__init__`'s own `model_params` parameter defaults to `None`, but it's forwarded
unconditionally into `_init_model`, which does `{**llm_params, **model_params, **kwargs}` with no
`None` check:

```
TypeError: 'NoneType' object is not a mapping
```

**Verified workaround:** always pass `model_params={}` explicitly at construction (as in the
snippet above). With that, construction succeeds and `kb.model` is a real, working
`langchain_ollama.ChatOllama` instance.

## `LLM_Providers.OLLAMA` construction — confirmed exact kwargs

`llm_store/constants.py`: `LLM_Providers` is a `StrEnum` with members `IBM = auto()`, `OPEN_AI =
auto()`, `HUGGING_FACE_HUB = 'hf'`, `OLLAMA = auto()` → `LLM_Providers.OLLAMA.value == 'ollama'`.

`LLM_Store._init_model` (`llm_store/llm.py`), the `OLLAMA` branch, read directly from source:

```python
elif llm_provider == LLM_Providers.OLLAMA:
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model_id, **{**llm_params, **model_params, **kwargs})
    # where llm_params = {"base_url": base_url, "api_key": api_key}
```

So for Ollama specifically, `base_url` is passed straight through to `langchain_ollama.ChatOllama`
as its native `base_url` kwarg — **no reshaping, no `/v1` suffix** (that's the pydantic-ai-specific
derivation from `plans/PLAN_AGENTS.md`; LangGraph's `ChatOllama(base_url=OLLAMA_HOST)` in
`src/weather_graph/agents/langgraph_agent.py:50` is the exact precedent this matches, byte for
byte). `api_key=None` is also passed to `ChatOllama` — confirmed harmless: `ChatOllama` accepted it
silently in the live construction test (`langchain-ollama==1.1.0`, already this repo's exact pinned
version — no new dependency needed for the Ollama chat-model layer itself).

**Recommended `.env` var:** `OLLAMA_HOST` alone suffices, reused as-is —

```python
base_url=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
```

— exactly the derivation `plans/PLAN_AGENTS.md` (§72–78) already established as the pattern:
"each backend module derives whatever URL shape it individually needs from the one `OLLAMA_HOST`
value." For `LLM_Store`/Ollama that derivation is the identity function — no exception needed, no
new host/endpoint var. `model_id="granite4:micro"` should come from a new `KIF_LLM_MODEL` env var
(matching `PYDANTIC_AI_MODEL`/`LANGGRAPH_MODEL`'s per-backend-model pattern), not `OLLAMA_HOST`.

## Confirmed blocker #5 (only reachable after 1–4 are worked around): subjects need a registered `.label`, not just an IRI

A bare `Item(IRI("http://www.wikidata.org/entity/Q1297"))` (no registered label) fails inside the
prompt builder:

```
AssertionError: It was not possible to get the label for the entity
`Item(IRI('http://www.wikidata.org/entity/Q1297'))`
```

at `llm_store/compiler/llm/filter_compiler.py:343` (`build_task_prompt_template`, `entity.label`).
This makes sense: `LLM_Store` builds an English prompt like "What is the temperature of
`{subject}`?" and needs an actual name string for `{subject}`, whereas the SPARQL store never
needed a label at all (it only ever needs the IRI to match a SPARQL pattern).

**This confirms `plans/PLAN_KIF_LLM.md` objective 3's fallback is not just "the right style," it's
required.** `kif_lib.vocabulary.wd`'s own `Q()` helper does exactly the needed
registration — its docstring is literally `Creates a Wikidata item with the given descriptors` and
it calls `Context.top(context).entities.register(Item(iri), label=label, ...)`. The example
notebook itself hints at this (`subject = wd.Brazil # or wd.Q(155, 'Brazil')`). So the fallback for
cities without a named `wd.<City>` constant is not a bare `Item(IRI(...))` — it must be
`wd.Q(<number>, "<Label>")`, which both builds the `Item` and registers its label in one call.
Verified live: `wd.Q(1297, 'Chicago').label == Text('Chicago', 'en')`, and with that the filter call
proceeds past this assertion.

## Confirmed blocker #6: `kbel` is an undeclared, and partly broken, runtime dependency

Every `kb.filter()` call — even ones whose value is a plain quantity/string and never actually needs
entity disambiguation — unconditionally hits `_disambiguate()` (`llm_store/llm.py`), which does:

```python
from kbel.disambiguators import (
    Disambiguator, SimpleDisambiguator, LLM_Disambiguator,
)
```

Two separate problems here, both confirmed live:
1. **`kbel` isn't a dependency of `llm_store` at all** — not in `llm_store/pyproject.toml`. It's a
   *sibling* package in the same monorepo (`kif-llm/kbel/`, its own separate `pyproject.toml`,
   `packages = [{include = "kbel", from = "src"}]`, valid TOML this time). Nothing installs it
   alongside `kif-llm-store`; you must know to get it separately.
2. **Even once `kbel` is importable, this import line still fails**: `kbel/src/kbel/disambiguators/__init__.py`
   only re-exports `Disambiguator` — not `SimpleDisambiguator` (lives in
   `kbel.disambiguators.simple`) or `LLM_Disambiguator` (lives in `kbel.disambiguators.llm`). So
   `from kbel.disambiguators import (Disambiguator, SimpleDisambiguator, LLM_Disambiguator)` raises
   `ImportError: cannot import name 'SimpleDisambiguator' from 'kbel.disambiguators'` even with
   `kbel` fully present on `sys.path`.

**Verified workaround:** patch `kbel/disambiguators/__init__.py` to also export
`SimpleDisambiguator` and `LLM_Disambiguator`:

```python
from .abc import Disambiguator
from .simple import SimpleDisambiguator
from .llm import LLM_Disambiguator
__all__ = ('Disambiguator', 'SimpleDisambiguator', 'LLM_Disambiguator')
```

With that patch (and `kbel/src` on `PYTHONPATH`), `kb.filter()` finally runs end to end. Note:
`kbel`'s own `pyproject.toml` declares `sentence-transformers`/`scikit-learn`/`numpy` as its main
non-optional deps (heavy!) but our fixed weather questions never exercise the code paths that need
them (`SimpleDisambiguator` is used for quantity/string-valued properties like ours, which skip
disambiguation entirely — see next section) — `kbel.disambiguators.abc`/`simple` import cleanly
with none of those installed.

## Confirmed live: `kb.filter()` return shape matches `kif.py`'s assertions exactly

With all six blockers above worked around, two real calls against local Ollama `granite4:micro`
succeeded and returned exactly the shape `src/weather_graph/kif/kif.py` already asserts on:

```python
>>> kb.filter(subject=wd.Q(1297, 'Chicago'), property=wd.temperature, limit=1)
[Statement(Item(IRI('http://www.wikidata.org/entity/Q1297')),
           ValueSnak(Property(IRI('.../P2076'), QuantityDatatype()),
                     Quantity(Decimal('32'), None, None, None)))]

>>> kb.filter(subject=wd.Q(1297, 'Chicago'), property=wd.weather_history, limit=1)
[Statement(Item(IRI('http://www.wikidata.org/entity/Q1297')),
           ValueSnak(Property(IRI('.../P4150'), StringDatatype()),
                     String('precipitation')))]
```

Same `Statement` → `ValueSnak` → `Quantity.amount` (a `Decimal`) / `String.content` shape `kif.py`
already asserts (`isinstance(stmt.snak, ValueSnak)`, `isinstance(stmt.snak.value, Quantity)`,
`float(stmt.snak.value.amount)`, `isinstance(stmt.snak.value, String)`, `str(stmt.snak.value.content)`).
**Sub agent 3 can reuse `kif.py`'s exact assertion pattern in `llm_store.py` with no new
response-handling code.** One difference worth flagging: `Quantity`'s unit/lower/upper-bound fields
came back `None` for the LLM answer (`Quantity(Decimal('32'), None, None, None)`) — the SPARQL
store's `Quantity` may or may not populate a unit depending on `mapping.py`; `kif.py` never checks
it either way (`float(stmt.snak.value.amount)` only), so this is safe to ignore, just noted as a
concrete asymmetry between the two stores' `Quantity` payloads.

## Grounding mismatch — the actual, real answers captured (objective 5's demo data)

Ground truth from `model/weather.ttl` (`wx:city0` = Chicago): `temperatureC 21.0`, `condition
"Partly Cloudy"`.

Live `LLM_Store` (Ollama `granite4:micro`) answers, captured directly, unedited:

| Question | `kif.py` (SPARQL/QLever, synthetic ground truth) | `LLM_Store` (Ollama, live) |
|---|---|---|
| Chicago temperature | `21.0` (°C, from `weather.ttl`) | `32` (**no unit attached** — `Quantity`'s unit field is `None`; could be read as °F, in which case it's actually a *plausible* real-world Chicago temperature reading, just in the wrong unit and for an unknown/unspecified date — either way, unrelated to the synthetic value) |
| Chicago condition (`weather_history`/P4150) | `"Partly Cloudy"` | `"precipitation"` — the model answered the *concept* "weather history" is about, not an actual current condition for Chicago; a concrete instance of objective 4's predicted "plausible-but-unverifiable" outcome for a property Wikidata itself doesn't use this way |

This is exactly the "same interface, different epistemics" contrast `plans/PLAN_KIF_LLM.md`
objective 5 wants surfaced explicitly, and it's real captured output, not a hypothetical.

**Also observed, and worth documenting as a finding in its own right:** repeating the *identical*
`kb.filter(subject=wd.Q(1297,'Chicago'), property=wd.temperature, limit=1)` call a second time (no
code change, same prompt) instead **crashed**:

```
decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]
```

at `llm_store/output_parsers.py`'s `SemicolonSeparatedListOfNumbersOutputParser.parse` — it strips
all non-numeric characters from the model's raw text and tries `Decimal(cleaned_part)`, but only
catches `ValueError`, not `decimal.InvalidOperation` (the exception `Decimal('')` actually raises
when the model's answer, after stripping, contains no digits at all — e.g. a refusal or hedge like
"I don't have that information"). **`LLM_Store.filter()` is non-deterministic across identical
calls** (expected, given LLM sampling) **and crashes with an unhandled exception, rather than
returning an empty result, whenever the model's answer doesn't reduce to a clean number.** This is
itself a legitimate, concrete data point for the grounding-mismatch narrative: unlike the SPARQL
store (which either finds a row or doesn't), the LLM store's failure mode for "no real answer" is an
uncaught crash, not an empty `kb.filter()` result — sub agent 3's `city_temperature`/
`city_condition` wrappers should wrap the `kb.filter()` call in a `try/except` (catching at least
`decimal.InvalidOperation` in addition to whatever KIF-level errors `kif.py` already tolerates) if
they want a graceful `None` return instead of propagating this upstream bug.

## The 8 cities: named `wd.<City>` constants vs. explicit `wd.Q(...)` fallback

Checked directly against the installed `kif_lib` 0.13.0's `vocabulary/wd/item.py` (a small, curated
566-line file — nowhere near the full Wikidata dump):

| `kif.py` city | Named `wd.<City>` constant? | Wikidata Q-ID (verified via `wikidata.org/wiki/Special:EntityData/Q….json`) | Construction to use |
|---|---|---|---|
| Chicago | No | Q1297 | `wd.Q(1297, 'Chicago')` |
| Paris | **Yes** — `wd.Paris` (`item.py:196`, `Q(90, 'Paris')`) | Q90 | `wd.Paris` |
| London | No | Q84 | `wd.Q(84, 'London')` |
| Cairo | No | Q85 | `wd.Q(85, 'Cairo')` |
| Tokyo | No | Q1490 | `wd.Q(1490, 'Tokyo')` |
| Oslo | No | Q585 | `wd.Q(585, 'Oslo')` |
| Nairobi | No | Q3870 | `wd.Q(3870, 'Nairobi')` |
| Sydney | No | Q3130 | `wd.Q(3130, 'Sydney')` |

Only **1 of 8** (Paris) has a named constant — `kif_lib.vocabulary.wd` is a small hand-curated
subset, not a full Wikidata mirror, confirmed by grepping `item.py` for the other seven names and
finding zero hits (only unrelated *property* names like `Chicago_Landmarks_ID` matched). Per the
confirmed label requirement above (blocker #5), **`wd.Q(<id>, '<Label>')` — not a bare
`Item(IRI(...))` — is the correct fallback**, since it both builds the `Item` and registers the
label `LLM_Store` needs to build its prompt. `kif_lib.vocabulary.wd`'s own module-level docstring
example (`wd.Q(155, 'Brazil')`) already establishes this as the intended idiom for exactly this
situation, so `wikidata_mapping.py` can use it directly with no invented API.

## Recommended pyproject.toml extra

**This is the section where the research has to be blunt: there is currently no dependency string
that makes `uv sync --extra kif-llm` "just work."** Three real options, in order of how much they
cost:

1. **Vendor a locally-patched copy in-repo (recommended).** Copy `llm_store/` and the small slice
   of `kbel/disambiguators/` actually needed (`abc.py`, `simple.py` — *not* the heavy
   `sentence-transformers`-based `similarity.py`, and *not* `llm_disambiguator.py` unless
   `entity_linking_method=LLM` is ever used, which this plan's fixed-question scope never needs)
   into e.g. `src/weather_graph/kif/_vendor/kif_llm_store/` and
   `src/weather_graph/kif/_vendor/kbel/`, applying exactly the patches confirmed above: fix the one
   absolute `from llm_store.constants import ...` → relative import (blocker #2), fix
   `kbel/disambiguators/__init__.py`'s missing re-exports (blocker #6). Document the source commit
   patched from (`IBM/kif-llm @ cb91defc`, 2026-09-06) and the exact diff in a header comment, the
   same way this repo already documents "confirmed live" findings elsewhere. No extra `[project.optional-dependencies]`
   entry needed beyond the *real* transitive deps `llm_store` itself declares that aren't already
   in this repo's `dependencies` — cross-checking `llm_store/pyproject.toml`'s (broken-TOML but
   still legible) dependency list against what's already installed: `langchain-core` (pulled in
   transitively by `langgraph`/`langchain-ollama`, already present), `langchain-ollama` (already a
   core dependency, `>=1.1,<2`), `httpx` (already present, `0.28.1`, satisfies `>=0.28.1,<0.29.0`),
   `tenacity` (already present). Only genuinely new: `nest-asyncio` (`>=1.6.0,<2.0.0`). So:
   ```toml
   [project.optional-dependencies]
   kif-llm = [
       "nest-asyncio>=1.6.0,<2.0.0",
   ]
   ```
   with the vendored `kif_llm_store`/`kbel` code shipping as ordinary source files under
   `src/weather_graph/kif/_vendor/`, not as a package dependency at all. This is the only option
   verified end-to-end in this research (every empirical result above was produced this way).

2. **Point the extra at a personal fork.** Fork `IBM/kif-llm`, apply the same two patches (TOML
   syntax fix + `kbel` re-export fix) as real commits, then:
   ```toml
   kif-llm = [
       "kif-llm-store @ git+https://github.com/<you>/kif-llm.git@<fixed-branch>#subdirectory=llm_store",
       "kbel @ git+https://github.com/<you>/kif-llm.git@<fixed-branch>#subdirectory=kbel",
   ]
   ```
   Cleaner long-term (real package boundary, real version pin via branch/tag) but more upkeep (a
   fork to maintain) and untested here — I did not push a fork as part of this research; option 1's
   patches are proven, this option's exact git syntax is not.

3. **Wait for upstream.** File an issue against `IBM/kif-llm` (none of the currently-open issues
   cover these bugs — checked via the GitHub issues API) and treat the `kif-llm` demo as blocked
   until `kif-llm-store` actually reaches PyPI in installable form. Rejected for this plan: the
   whole point of objective 5 is a working side-by-side demo now, not a TODO.

**Recommendation for sub agent 3: option 1 (vendor).** It's the only one empirically proven, keeps
the new `kif-llm` extra tiny and honest (`nest-asyncio` only), and the vendored files are small
(`llm_store/` minus `context_generator/`/`query_to_question/`, which this plan doesn't use, is well
under 1000 lines; `kbel/disambiguators/abc.py` + `simple.py` is under 150 lines).

## Recommended .env var

- **`OLLAMA_HOST` alone suffices** for `LLM_Store`'s Ollama provider — confirmed above, `base_url`
  is passed straight through to `langchain_ollama.ChatOllama` with no reshaping, identical to how
  `langgraph_agent.py` already uses it. No new host/endpoint var needed; this matches
  `plans/PLAN_AGENTS.md`'s precedent exactly (the LangGraph case, not the pydantic-ai `/v1` case).
- **New var needed: `KIF_LLM_MODEL`** (e.g. `"granite4:micro"`), mirroring `PYDANTIC_AI_MODEL`/
  `LANGGRAPH_MODEL` — each backend gets its own model var so backends can be pointed at different
  models independently. This is genuinely new, not a derivation of an existing var, per the
  `.env.example` additions already anticipated in `plans/PLAN_KIF_LLM.md`'s Sub agent 3 section.

## Open questions / blockers

- **The package is unusable as documented, full stop**, as of `IBM/kif-llm @ cb91defc`
  (2026-09-06), on both `main` and `dev`. Every one of the six blockers above is independently
  reproducible from a clean clone; none is specific to this machine/environment. Anyone re-running
  this research later should re-check whether upstream has since published to PyPI and/or fixed the
  `pyproject.toml`/`kbel` re-export bugs before assuming the vendoring approach is still necessary.
- **`kif-lib` version pin risk, noted but not blocking:** `llm_store/pyproject.toml` pins
  `kif-lib = { git = "https://github.com/IBM/kif.git" }` (no version constraint — tracks upstream
  `kif` HEAD), and `kbel/pyproject.toml` pins `kif-lib = "^0.12.0"` (i.e. `>=0.12.0,<0.13.0` under
  Poetry's caret rules) — both narrower/different from this repo's own `kif-lib>=0.13,<1` (PyPI).
  Empirically, everything above ran fine against this repo's actual installed `kif_lib==0.13.0`
  (confirmed via `pip show`/`kif_lib.__file__`), so this is a latent risk (a real `poetry`/`pip`
  dependency-resolver pass on the unpatched upstream packages might pull a different `kif-lib`
  version than this repo uses) rather than an observed failure — the vendoring approach in the
  recommendation above sidesteps it entirely since vendored code doesn't get its own dependency
  resolution pass.
- **Non-determinism is real and will show up in demo runs.** The `decimal.InvalidOperation` crash
  (see grounding-mismatch section) happened on a re-run of the *exact same* filter call with no code
  changes. `demo_kif_llm.py` (sub agent 3's output) and `llm_store.py`'s wrapper functions should
  expect this and handle it gracefully (catch it, treat as "no answer", don't let one demo run's
  luck determine whether the script crashes) — this is a real, not hypothetical, failure mode to
  design around, not just a currently-observed one-off.
- I did not attempt `hottest_cities`-style multi-subject queries (`kb.filter(property=wd.temperature)`
  with no `subject`) live — `kif.py`'s `hottest_cities` iterates all 8 cities' readings from one
  unbound-subject filter call; whether `LLM_Store` supports an unbound-subject filter at all (vs.
  requiring per-city calls) is unconfirmed and should be checked empirically by sub agent 3 before
  assuming it works the same way `kif.py`'s does — the `llm_store/compiler/llm/filter_compiler.py`
  code path for `KIF_FilterTypes` (`EMPTY`/`ONE_VARIABLE`/`GENERIC`) suggests it's handled, but this
  research didn't confirm it against a live model call, and given the fixed-question scope, calling
  the same single-city function 8 times (once per `CITY_NAMES` entry) and sorting in Python — same
  pattern `kif.py` already uses internally — is a safe, already-proven-to-work fallback regardless.

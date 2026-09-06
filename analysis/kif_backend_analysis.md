# KIF backend analysis (sub agent 1)

Analysis of the *existing* SPARQL/QLever-backed KIF client (`src/weather_graph/kif/kif.py`,
`mapping.py`, `demo_kif.py`, `tests/test_kif.py`) as the reference shape the new LLM-backed client
(`llm_store.py`, sub agent 3) must mirror, per `plans/PLAN_KIF_LLM.md` objectives 1 and 7. Grounded
in reading the actual source plus live checks against the running environment (`mypy`,
`inspect.signature`), not just eyeballing the code.

## Call-site shapes to mirror

All four are plain module-level functions in `kif.py` — not a class — which matters for the
`base.py` Protocol shape below (see "Protocol conformance").

### `get_store() -> Store`

```python
@lru_cache(maxsize=1)
def get_store() -> Store:
    """Build (once) the KIF store, pointed at the configured QLever endpoint."""
    endpoint = os.environ.get("QLEVER_ENDPOINT", _DEFAULT_QLEVER_ENDPOINT)
    return Store("sparql", endpoint, mapping=WeatherMapping())
```

- Singleton via `functools.lru_cache(maxsize=1)` on a zero-argument function — not a module-level
  global assigned at import time. This defers store construction (and any connection setup) until
  first use, and every subsequent call returns the identical cached `Store` object.
- Reads config from an environment variable (`QLEVER_ENDPOINT`) with a hardcoded fallback default,
  after `load_dotenv()` at module scope.
- Constructs a KIF `Store` with a backend-specific positional shape (`"sparql", endpoint,
  mapping=...`) and a mapping instance from the sibling `mapping.py` module.

### `city_temperature(name: str = "Chicago") -> float | None`

```python
def city_temperature(name: str = "Chicago") -> float | None:
    """Current temperature (°C) for a named city, or None if not found."""
    kb = get_store()
    city = _city_item(name)
    for stmt in kb.filter(subject=city, property=wd.temperature, limit=1):
        assert isinstance(stmt.snak, ValueSnak)
        assert isinstance(stmt.snak.value, Quantity)
        return float(stmt.snak.value.amount)
    return None
```

- Calls `get_store()` fresh each time (cheap — it's the cached singleton), then `_city_item(name)`
  to resolve the display name to a KIF `Item` subject.
- `kb.filter(subject=..., property=wd.temperature, limit=1)` returns `Iterator[Statement]`
  (confirmed via `inspect.signature(Store.filter)` in this environment: return type is
  `'Iterator[Statement]'`). The function iterates it (for-loop, not indexing) and returns on the
  first result — the `limit=1` plus early `return` is the whole "get me one" pattern; no result
  means the loop body never runs and the function falls through to `return None`.
- Type assertions on the way to unwrapping the value: `isinstance(stmt.snak, ValueSnak)` then
  `isinstance(stmt.snak.value, Quantity)`. These are `assert` statements, not `if`/error-handling —
  they exist to narrow the type for the type checker and to fail loudly (an `AssertionError`, not a
  silent `None`) if the mapping ever returns a differently-shaped snak/value, which would indicate a
  mapping bug rather than "no data."
- Final unwrap: `float(stmt.snak.value.amount)` — `Quantity.amount` is a `Decimal`
  (per `analysis/ibm_kif_analysis.md`), explicitly cast to `float` for the function's declared
  return type.

### `city_condition(name: str = "Chicago") -> str | None`

```python
def city_condition(name: str = "Chicago") -> str | None:
    """Current weather condition (e.g. "Rainy") for a named city, or None if not found."""
    kb = get_store()
    city = _city_item(name)
    for stmt in kb.filter(subject=city, property=wd.weather_history, limit=1):
        assert isinstance(stmt.snak, ValueSnak)
        assert isinstance(stmt.snak.value, String)
        return str(stmt.snak.value.content)
    return None
```

- Structurally identical to `city_temperature` — same singleton, same subject resolution, same
  `limit=1`/for-loop/early-return/fallthrough-`None` pattern — differing only in the property
  (`wd.weather_history` instead of `wd.temperature`), the value type asserted (`String` instead of
  `Quantity`), and the unwrap (`String.content` is already a `str`; `str(...)` is a defensive no-op
  cast matching the `float(...)` cast in `city_temperature`, for symmetry rather than necessity).

### `hottest_cities(limit: int = 3) -> list[tuple[str, float]]`

```python
def hottest_cities(limit: int = 3) -> list[tuple[str, float]]:
    """The `limit` hottest cities in the data, as (name, temperatureC) pairs, hottest first."""
    kb = get_store()
    readings = []
    for stmt in kb.filter(property=wd.temperature):
        assert isinstance(stmt.snak, ValueSnak)
        assert isinstance(stmt.subject, Item)
        assert isinstance(stmt.snak.value, Quantity)
        readings.append((_name_of(stmt.subject), float(stmt.snak.value.amount)))
    readings.sort(key=lambda pair: pair[1], reverse=True)
    return readings[:limit]
```

- Different query shape: no `subject=`, no `limit=` on `kb.filter()` itself — it fetches **all**
  statements for `wd.temperature` across every subject, then does client-side ranking. This matches
  `analysis/ibm_kif_analysis.md`'s finding that KIF's `Store.filter()` has no `ORDER BY`/sort
  support — "hottest N" is necessarily a Python-side `sort()` + slice, not something a `Store` query
  parameter can express directly (relevant for `llm_store.py` too: an `LLM_Store` has no ordering
  primitive to lean on either, so this function's *shape* — fetch-all, sort-in-Python — carries over
  unchanged regardless of backend).
- Three assertions per statement instead of two: `ValueSnak`, `Item` (on `stmt.subject`, since this
  query has no fixed subject to already know the type of), and `Quantity`.
  `_name_of(stmt.subject)` turns the subject `Item` back into a display name for the returned
  tuples.
- The `limit` parameter here is a plain Python `list` slice (`readings[:limit]`) after sorting — a
  different mechanism from `city_temperature`/`city_condition`'s `limit=1` argument to
  `kb.filter()`. Don't conflate the two "limit" concepts when documenting/mirroring this function.

## `CITY_NAMES` and the `_city_item`/`_name_of` helpers

```python
CITY_NAMES = {
    "city0": "Chicago",
    "city1": "Paris",
    ...
}
_NAME_TO_SLUG = {name: slug for slug, name in CITY_NAMES.items()}

def _city_item(name: str) -> Item:
    return Item(IRI(f"{WX}{_NAME_TO_SLUG[name]}"))

def _name_of(item: Item) -> str:
    slug = item.iri.content.rsplit("#", 1)[-1]
    return CITY_NAMES.get(slug, slug)
```

Splitting what's SPARQL/`wx:`-specific (won't carry over verbatim to the LLM backend) from what's
generic KIF plumbing (carries over unchanged *in spirit*, per the plan's phrasing):

| Piece | SPARQL/`wx:`-specific? | Notes |
|---|---|---|
| `CITY_NAMES` dict shape (`slug -> display name`) | **Yes** — keys are local `wx:cityN` slugs, meaningful only against `model/weather.ttl`'s IRIs. | The LLM backend has no local slugs at all (objective 3): `wikidata_mapping.py` needs a *differently shaped* table — plausibly `display name -> wd.<City>` directly (no slug indirection, since there's no local IRI to slug from) — not a reuse of this dict. |
| `_NAME_TO_SLUG` reverse dict | **Yes**, derivative of the above. | Same reasoning; the LLM backend doesn't need a reverse mapping to a slug at all since it never round-trips through a slug — it likely only needs `name -> Item` and, for `hottest_cities`, `Item -> name` (see `_name_of` below). |
| `_city_item(name) -> Item` **function shape** (`str -> Item`, used to build the `subject=` argument to `kb.filter()`) | **No** — this is generic KIF plumbing: "turn a display name into the `Item` I'll query with." | Carries over *in spirit*: `llm_store.py` will need its own `name -> Item` resolver with the same signature and role, just backed by `wikidata_mapping.py`'s `wd.<City>` table instead of `IRI(f"{WX}{slug}")` construction. The `IRI(f"{WX}...")` construction itself is 100% SPARQL/`wx:`-specific and must not carry over — Wikidata items are looked up as named constants (`wd.Chicago`) or `Item(IRI("wd:Q..."))`, never built from a local namespace prefix. |
| `_name_of(item) -> str` **function shape** (`Item -> str`, used by `hottest_cities` to turn a queried subject back into a display name) | **No**, but its **implementation** is — `item.iri.content.rsplit("#", 1)[-1]` parses the local `wx:` IRI's fragment to recover the slug, then looks it up in `CITY_NAMES`. | Carries over in spirit only. A Wikidata-based reverse lookup can't parse a slug out of `wd.Chicago`'s IRI the same way (Wikidata IRIs are opaque `Qnnn` identifiers, not human-readable slugs) — it will need its own reverse table (`Item -> name`, e.g. keyed by the `Item`'s IRI string or built as the literal inverse of whatever forward table `wikidata_mapping.py` defines). |
| `Item(IRI(...))` as KIF's subject-construction pattern generally | **No** — this is the generic "wrap an IRI string as an `Item`" KIF idiom. | The LLM backend still ends up with `Item` objects as subjects; it just gets them from `wd.<City>` named constants (already `Item` instances in `kif_lib.vocabulary.wd`) rather than constructing `Item(IRI(...))` by hand for most cities — falling back to explicit `Item(IRI("wd:Q..."))` construction only for cities without a named constant (per objective 3, sub agent 2 to confirm which). |

## `demo_kif.py` and `tests/test_kif.py` structure

### `demo_kif.py`

- Single `run()` function, no CLI args, printing question/answer pairs to stdout in a fixed order
  matching `demo.py`'s original 3 questions:
  1. "What is the weather like in Chicago right now, and is it warm?" — calls
     `kif.city_temperature("Chicago")` and `kif.city_condition("Chicago")`.
  2. "Is Chicago one of the three hottest cities in the data?" — calls `kif.hottest_cities(3)`,
     derives `'Chicago' in names`.
  3. "Is it currently raining or snowing in Chicago?" — re-calls `kif.city_condition("Chicago")`
     (not cached/reused from question 1 — each question is self-contained), checks membership in
     `('Rainy', 'Snowy')`.
- `main()` is a thin wrapper calling `run()`, guarded by `if __name__ == "__main__":` — this is the
  `uv run weather-graph-kif` entry point (per the module docstring).
- No error handling in the demo itself — if the store/QLever is unreachable, `kif.city_temperature`
  etc. will raise naturally and the demo just crashes with a traceback; there is no
  skip/try-except here (that pattern lives in the test suite, not the demo).
- **For the LLM-backend equivalent (`demo_kif_llm.py`, objective 5):** per the plan, this file
  changes shape more than the others — it needs to run each question through *both* backends and
  print both answers labeled `[SPARQL/QLever]` / `[LLM Store]`, iterating `[kif, llm_store]`
  generically through `base.Protocol` rather than two hardcoded call sequences. That's a structural
  difference from today's single-backend `demo_kif.py`, not a straight copy.

### `tests/test_kif.py`

```python
kif_lib = pytest.importorskip("kif_lib")
from weather_graph.kif import kif

@pytest.fixture(scope="module")
def live_qlever():
    try:
        next(kif.get_store().filter(property=kif_lib.vocabulary.wd.temperature, limit=1))
    except StopIteration:
        pass
    except Exception as exc:  # noqa: BLE001 - any connection failure means "skip"
        pytest.skip(f"No reachable QLever endpoint: {exc}")
```

- **Two independent skip layers**, both "skip cleanly," neither "fail":
  1. Module-level `pytest.importorskip("kif_lib")` — skips the whole file if the `kif_lib` package
     itself isn't installed (the optional dependency isn't present at all).
  2. A module-scoped `live_qlever` fixture that makes one real call (`next(...filter(..., limit=1))`)
     and catches *any* exception (`except Exception`, with an explicit `noqa: BLE001` acknowledging
     the deliberately broad catch) to `pytest.skip(...)` with the exception message — this is the
     "QLever isn't running right now" case, distinct from "kif_lib isn't installed." `StopIteration`
     (empty result, not a connection failure) is caught separately and treated as fine — an empty
     result is not an unreachable-endpoint condition, so it doesn't skip.
  - Tests that need a live backend take `live_qlever` as a fixture parameter (unused inside the
    test body — it's a pure gate, only used for its skip side-effect).
- **Question/assertion set** — mirrors `demo_kif.py`'s 3 questions but as exact-value assertions
  rather than printed prose, plus one extra structural test that needs no live backend at all:
  - `test_city_temperature_returns_chicago`: `kif.city_temperature("Chicago") == 21.0` (exact
    float equality against the known synthetic fixture value).
  - `test_hottest_cities_returns_cairo_first`: length-3 result, `hottest[0][0] == "Cairo"`.
  - `test_city_condition_for_chicago`: `kif.city_condition("Chicago") == "Partly Cloudy"`.
  - `test_city_names_mirror_model_ttl` (no `live_qlever` fixture — pure data assertion, always
    runs once `kif_lib` is importable): `kif.CITY_NAMES["city0"] == "Chicago"` and
    `len(kif.CITY_NAMES) == 8`.
- **For the LLM-backend equivalent (`tests/test_kif_llm.py`, objective 6/sub agent 3):** the plan
  calls for the same two-layer skip idea but with a second skip *reason* — "isn't installed" stays
  `pytest.importorskip("kif_llm_store")`, but "not reachable" becomes "Ollama isn't reachable"
  rather than "QLever isn't reachable," and the exact-value assertions (`== 21.0`,
  `== "Partly Cloudy"`, `hottest[0][0] == "Cairo"`) **cannot** carry over as-is — per plan objective
  5, the LLM backend answers from training data, not the synthetic fixture, so its answers will
  essentially never match these values. The new tests will need to assert on *shape* (a `float` or
  `None` came back; a 3-element list of `(str, float)` tuples came back) rather than exact
  fixture-matching content — this is a real, plan-acknowledged asymmetry, not an oversight to fix.
  The one test that *can* carry over unchanged in spirit is something like
  `test_city_names_mirror_model_ttl` — a pure, no-live-backend structural check on
  `wikidata_mapping.py`'s own table (e.g. all 8 cities present, correct count) — since that doesn't
  depend on what the LLM says.

## Proposed `typing.Protocol` for `src/weather_graph/kif/base.py`

```python
"""Shared structural contract both KIF Store backends satisfy.

`kif.py` (SPARQL/QLever, hardcoded ground truth) and `llm_store.py` (kif-llm-store's `LLM_Store`
over Ollama) both satisfy `KIFBackend` below *structurally* (PEP 544) — by having functions with
matching names and signatures at module scope, with no shared base class and no inheritance.
`kif.py` needs no code changes to conform (see analysis/kif_backend_analysis.md for the
mypy-verified check); `llm_store.py` is written to satisfy it from the start.
"""

from __future__ import annotations

import typing

from kif_lib import Store


@typing.runtime_checkable
class KIFBackend(typing.Protocol):
    """The 4-function shape `demo_kif_llm.py` (and anything else that wants to treat both KIF
    backends generically) can rely on."""

    def get_store(self) -> Store:
        """Build (or return the cached) `Store` for this backend."""
        ...

    def city_temperature(self, name: str = "Chicago") -> float | None:
        """Current temperature (°C) for a named city, or None if not found."""
        ...

    def city_condition(self, name: str = "Chicago") -> str | None:
        """Current weather condition (e.g. "Rainy") for a named city, or None if not found."""
        ...

    def hottest_cities(self, limit: int = 3) -> list[tuple[str, float]]:
        """The `limit` hottest cities, as (name, temperatureC) pairs, hottest first."""
        ...
```

Design notes:

- **Protocol methods are written with a normal `self` parameter**, even though both `kif.py` and
  `llm_store.py` implement these as *module-level functions*, not class methods. This looks
  backwards at first glance but is required, not incidental — see "Protocol conformance" below.
- **`@typing.runtime_checkable` is included** so `isinstance(kif, KIFBackend)` works at runtime
  (verified — see below) in case sub agent 3 or the orchestrator wants a runtime assertion/sanity
  check somewhere (e.g. in `demo_kif_llm.py` or a test), not just static `mypy` checking. It isn't
  strictly required for `demo_kif_llm.py`'s described usage (calling functions directly through
  the imported module, typed as `KIFBackend` for static checking) — flagged as a judgment call in
  "Open questions" below since the plan doesn't specify either way.
- `CITY_NAMES` / any per-backend mapping table is **deliberately not part of this Protocol** — the
  plan's objective 7 lists only the 4 functions as the shared contract, and `mapping.py` /
  `wikidata_mapping.py` are explicitly called out as separate, per-backend, non-shared modules. See
  "Open questions" for the test-symmetry implication of this.

### Protocol conformance — confirmed empirically, not assumed

Two checks were run against this exact environment (`kif_lib` installed, `weather_graph.kif.kif`
importable):

1. **`inspect.signature` on `kif.py`'s live functions** confirms the signatures already match the
   proposed Protocol exactly, with no annotation gaps:
   ```
   get_store () -> 'Store'
   city_temperature (name: 'str' = 'Chicago') -> 'float | None'
   city_condition (name: 'str' = 'Chicago') -> 'str | None'
   hottest_cities (limit: 'int' = 3) -> 'list[tuple[str, float]]'
   ```
2. **Static check with `mypy 2.3.1`**: a scratch file defining `KIFBackend` exactly as proposed
   above (methods with `self`), a function `use(backend: KIFBackend) -> None`, and a call
   `use(kif)` (passing the imported *module* where the Protocol type is expected) type-checks with
   **zero errors** ("Success: no issues found in 1 source file"). This confirms mypy accepts a
   plain module as satisfying a `Protocol` whose methods are declared with `self` — this is
   documented mypy behavior for module-vs-protocol structural matching (the module's top-level
   functions are compared against the Protocol's methods *minus* the implicit `self`, since there's
   no instance to bind `self` to).
   - **The reverse also confirmed, and matters for anyone editing this Protocol later:** the same
     scratch check with the Protocol's methods declared *without* `self` (i.e. `def get_store() ->
     Store: ...`) fails mypy outright — `error: Method must have at least one argument. Did you
     forget the "self" argument?` plus `"self" parameter missing for a non-static method` on every
     member, and a `call-arg`/"does not accept self argument" error at the `use(kif)` call site.
     **The Protocol's methods must keep the conventional `self` signature even though both
     conforming modules are plain functions with no `self`** — dropping `self` to "match" the
     module functions more literally is the wrong instinct and actively breaks conformance.
3. **Runtime check** (not required for the static-typing goal, but confirms the
   `@runtime_checkable` decorator choice works as intended): `isinstance(kif, KIFBackend)` returns
   `True` against the live imported `kif` module. Caveat worth stating plainly: `runtime_checkable`
   Protocol `isinstance` checks only verify **attribute presence** (`hasattr`), not signature
   compatibility — so this runtime check is weaker evidence than the `mypy` static check above and
   should not be read as re-confirming the signatures line up; it only confirms the four names
   exist as attributes on the module.

**Conclusion: `kif.py` satisfies the proposed `KIFBackend` Protocol structurally as-is.** No
annotation gap, no signature mismatch, no code change needed — the plan's non-goal ("no behavioral
change to `kif.py`... beyond a possible minor type-annotation conformance fix") does not need to be
invoked; there is nothing to fix.

## Open questions

- **`CITY_NAMES`-equivalent test symmetry.** `tests/test_kif.py` has one test
  (`test_city_names_mirror_model_ttl`) that asserts directly on `kif.CITY_NAMES`, a module attribute
  *not* covered by the `base.Protocol` contract (per objective 7, mapping tables are deliberately
  per-backend and non-shared). This is fine for `test_kif.py` itself (it already imports `kif`
  directly, not through the Protocol), but it means `tests/test_kif_llm.py`'s analogous structural
  test will need to import `wikidata_mapping` directly too, rather than reaching it generically
  through whatever object `demo_kif_llm.py`/tests treat as "the backend" — worth sub agent 3 keeping
  in mind so the new test file doesn't try to force this through the Protocol and then discover it
  doesn't fit.
- **`@runtime_checkable` — included in the proposal above, but the plan doesn't say either way.**
  Objective 7 only specifies *static* structural typing ("PEP 544... no inheritance needed"); it
  doesn't call for any runtime `isinstance` check anywhere in `demo_kif_llm.py` or the tests as
  described. I included the decorator since it's low-cost and enables an optional runtime sanity
  check without forcing one, but sub agent 3 (or the orchestrator) should feel free to drop it if
  nothing ends up using `isinstance` against `KIFBackend` — it's not load-bearing for the plan's
  described usage.
- **`get_store()`'s return type is the generic `kif_lib.Store`, not a narrower backend-specific
  type**, for both `kif.py` (`Store("sparql", ...)`) and presumably `llm_store.py`
  (`kif_llm_store.LLM_Store`, per sub agent 2's naming — `LLM_Store` should itself be a `Store`
  subclass for this to type-check against the same Protocol member; sub agent 2's analysis should
  confirm this inheritance relationship explicitly, since I did not verify `kif_llm_store`'s class
  hierarchy here — out of this sub agent's input scope).

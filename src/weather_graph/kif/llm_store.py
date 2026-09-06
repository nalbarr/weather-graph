"""The second KIF Store backend: the same 3 fixed questions, answered by an LLM instead of QLever.

Store wiring only — the "which IRI means Chicago" reasoning lives next door in
`wikidata_mapping.py`, exactly as `mapping.py` isolates it for the SPARQL side. This module
satisfies `base.KIFBackend` structurally, so `demo_kif_llm.py` can call it and `kif.py`
interchangeably (see plans/PLAN_KIF_LLM.md, objective 7).

The point of this backend is *not* better answers — it is that `kb.filter(subject=..., property=...)`
is written identically here and in `kif.py`, and only the `Store` underneath changes. The answers
differ wildly, and that mismatch is the demo (objective 5): `kif.py` reads synthetic triples from
`model/weather.ttl`, this reads whatever `granite4:micro` believes about the real Chicago.

Two things about `LLM_Store` that make it un-`kif.py`-like in practice, both confirmed live:

- **Its failure mode for "no answer" is a crash, not an empty result.** Where the SPARQL store
  either matches a triple or doesn't, `LLM_Store`'s number parser strips non-numeric characters
  from the model's raw reply and calls `Decimal()` on what's left, catching only `ValueError` —
  so a hedge or refusal with no digits in it raises `decimal.InvalidOperation` straight out of
  `kb.filter()`. It is also non-deterministic: the identical call can return a value on one run
  and crash on the next. Both wrappers below therefore catch it and return `None`, matching
  `kif.py`'s existing not-found-returns-`None` contract rather than propagating an upstream bug.
- **Unbound-subject filters do not work here** — see `hottest_cities()`.

Requires the `kif-llm` extra (`uv sync --extra kif-llm`) for `nest-asyncio`; the `LLM_Store` code
itself is vendored in `_vendor/` because upstream is not pip-installable (see that package's
header).
"""

from __future__ import annotations

import decimal
import os
from functools import lru_cache

from dotenv import load_dotenv
from kif_lib import Quantity, Search, Store, String, ValueSnak
from kif_lib.vocabulary import wd

from .wikidata_mapping import CITY_ITEMS, city_item

load_dotenv()

_DEFAULT_MODEL = "granite4:micro"
_DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"

#: Raised out of `kb.filter()` by the vendored store's own output parser when the model's answer
#: contains no digits (see module docstring). Not speculative defensive coding — reproduced live.
_NO_ANSWER_ERRORS = (decimal.InvalidOperation,)


@lru_cache(maxsize=1)
def get_store() -> Store:
    """Build (once) the KIF LLM store, pointed at the configured Ollama model."""
    # Imported lazily, not at module scope: the vendored `llm.py` calls `nest_asyncio.apply()` at
    # import time, which globally monkeypatches asyncio. Deferring it keeps merely *importing*
    # this module side-effect-free (and keeps `nest-asyncio` needed only when the store is
    # actually built). The import is also what registers `LLM_Store` as KIF's 'llm' plugin.
    from ._vendor.kif_llm_store import LLM_Store  # noqa: F401 - registers the 'llm' Store plugin
    from ._vendor.kif_llm_store.constants import LLM_Providers

    model_id = os.environ.get("KIF_LLM_MODEL", _DEFAULT_MODEL)
    base_url = os.environ.get("OLLAMA_HOST", _DEFAULT_OLLAMA_HOST)
    # `base_url` is handed straight to `langchain_ollama.ChatOllama` with no reshaping — the same
    # derivation `agents/langgraph_agent.py` already uses, *not* pydantic-ai's `/v1` suffix form.
    #
    # The three odd-looking arguments are all upstream workarounds, not choices:
    #   - `target_store`/`searcher` have no defaults (the upstream README's own quickstart omits
    #     them and raises TypeError). They are only used for entity-disambiguation fallback, which
    #     quantity/string-valued properties like ours never reach, so KIF's built-in no-op
    #     'empty' plugins are wired in.
    #   - `model_params={}` is required: the parameter's own default of `None` is forwarded
    #     unconditionally into a `{**model_params}` splat and crashes with
    #     "'NoneType' object is not a mapping".
    # See analysis/kif_llm_analysis.md, blockers #3 and #4.
    return Store(
        "llm",
        Store("empty"),
        Search("empty"),
        llm_provider=LLM_Providers.OLLAMA,
        model_id=model_id,
        base_url=base_url,
        model_params={},
    )


def city_temperature(name: str = "Chicago") -> float | None:
    """Current temperature (°C) for a named city, or None if not found."""
    kb = get_store()
    city = city_item(name)
    try:
        for stmt in kb.filter(subject=city, property=wd.temperature, limit=1):
            assert isinstance(stmt.snak, ValueSnak)
            assert isinstance(stmt.snak.value, Quantity)
            return float(stmt.snak.value.amount)
    except _NO_ANSWER_ERRORS:
        return None
    return None


def city_condition(name: str = "Chicago") -> str | None:
    """Current weather condition (e.g. "Rainy") for a named city, or None if not found."""
    kb = get_store()
    city = city_item(name)
    try:
        for stmt in kb.filter(subject=city, property=wd.weather_history, limit=1):
            assert isinstance(stmt.snak, ValueSnak)
            assert isinstance(stmt.snak.value, String)
            return str(stmt.snak.value.content)
    except _NO_ANSWER_ERRORS:
        return None
    return None


def hottest_cities(limit: int = 3) -> list[tuple[str, float]]:
    """The `limit` hottest cities the model knows about, as (name, temperatureC) pairs.

    `kif.py` gets this from one unbound-subject `kb.filter(property=wd.temperature)` and sorts the
    result in Python. **That query shape does not work against `LLM_Store`**, so this walks
    `CITY_ITEMS` and issues one bound-subject query per city instead — the fallback
    plans/PLAN_KIF_LLM.md anticipated, taken on evidence rather than caution.

    What was actually measured (4 live runs of `kb.filter(property=wd.temperature, limit=8)`
    against `granite4:micro`, no `subject=`): two returned zero statements, two crashed with
    `decimal.InvalidOperation`. Not once did it return per-city readings. That is the expected
    outcome in hindsight — with no subject bound there is no entity to build a prompt around, and
    the no-op `Search('empty')` this store is constructed with has nothing to enumerate. An
    `LLM_Store` has no ordering primitive either, so the sort stays client-side exactly as in
    `kif.py`.

    Cities the model declines to answer for (a `None` from `city_temperature`) are dropped, so
    this can legitimately return fewer than `limit` pairs — another way this backend differs from
    the SPARQL one, where all 8 rows are always present.
    """
    readings: list[tuple[str, float]] = []
    for name in CITY_ITEMS:
        temperature = city_temperature(name)
        if temperature is not None:
            readings.append((name, temperature))
    readings.sort(key=lambda pair: pair[1], reverse=True)
    return readings[:limit]



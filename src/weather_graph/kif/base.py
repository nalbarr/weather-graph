"""Shared structural contract both KIF Store backends satisfy.

`kif.py` (SPARQL/QLever, hardcoded ground truth) and `llm_store.py` (kif-llm-store's `LLM_Store`
over Ollama) both satisfy `KIFBackend` below *structurally* (PEP 544) — by having functions with
matching names and signatures at module scope, with no shared base class and no inheritance.
`kif.py` needs no code changes to conform (see analysis/kif_backend_analysis.md for the
mypy-verified check); `llm_store.py` is written to satisfy it from the start.

Deliberately *not* part of this contract: each backend's city/vocabulary table (`kif.CITY_NAMES`,
`wikidata_mapping.CITY_ITEMS`). Those are per-backend by design — the SPARQL side's subjects are
local `wx:cityN` IRIs and the LLM side's are real Wikidata Q-IDs — so anything that needs to assert
on one imports that module directly rather than reaching it through this Protocol
(see plans/PLAN_KIF_LLM.md objective 7).
"""

from __future__ import annotations

import typing

from kif_lib import Store


@typing.runtime_checkable
class KIFBackend(typing.Protocol):
    """The 4-function shape `demo_kif_llm.py` (and anything else that wants to treat both KIF
    backends generically) can rely on.

    Design note, because it reads backwards at first glance: the methods below take a normal
    `self` parameter even though *both* conforming implementations are plain module-level
    functions with no `self` at all — `demo_kif_llm.py` passes the imported **modules**
    (`kif`, `llm_store`) where a `KIFBackend` is expected. That is correct and required, not an
    oversight. mypy compares a module's top-level functions against a Protocol's methods *minus*
    the implicit `self` (there is no instance to bind it to), so `self` must be present for the
    match to work. Declaring these without `self` to "match" the module functions more literally
    is the wrong instinct and actively breaks conformance — mypy rejects it outright with
    `Method must have at least one argument. Did you forget the "self" argument?` plus a
    `call-arg` error at every call site. Both directions were verified with mypy against the real
    modules; see analysis/kif_backend_analysis.md, "Protocol conformance".
    """

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

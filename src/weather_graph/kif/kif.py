"""Fixed KIF queries over the weather graph (no LLM generation — see plans/PLAN_KIF.md).

Connects to weather-graph's *existing* QLever server (`make qlever-up`, `QLEVER_ENDPOINT`) via a
generic KIF SPARQL store — not KIF's own embedded `QLeverSPARQL_Store`, which manages its own
independent QLever index/server process (see plans/PLAN_KIF.md, "QLever wiring").

City subjects are the real local `wx:cityN` IRIs (confirmed live: KIF's SPARQL_Mapping binds
subjects to whatever IRI is actually in the data, with no automatic link to Wikidata Q-IDs) —
`CITY_NAMES` mirrors `model/weather.ttl` exactly, since KIF has no `wx:name` mapping (out of
scope: none of the 3 demo questions need it as a *query* input, only as display output, and the
city-to-subject assignment is fixed/known data, not something worth a live lookup).
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from kif_lib import IRI, Item, Quantity, Store, String, ValueSnak
from kif_lib.vocabulary import wd

from .mapping import WX, WeatherMapping

load_dotenv()

_DEFAULT_QLEVER_ENDPOINT = "http://localhost:7011"

# Mirrors model/weather.ttl exactly (wx:city0 = Chicago, etc.) — see analysis/weather_graph_analysis.md.
CITY_NAMES = {
    "city0": "Chicago",
    "city1": "Paris",
    "city2": "London",
    "city3": "Cairo",
    "city4": "Tokyo",
    "city5": "Oslo",
    "city6": "Nairobi",
    "city7": "Sydney",
}
_NAME_TO_SLUG = {name: slug for slug, name in CITY_NAMES.items()}


def _city_item(name: str) -> Item:
    return Item(IRI(f"{WX}{_NAME_TO_SLUG[name]}"))


def _name_of(item: Item) -> str:
    slug = item.iri.content.rsplit("#", 1)[-1]
    return CITY_NAMES.get(slug, slug)


@lru_cache(maxsize=1)
def get_store() -> Store:
    """Build (once) the KIF store, pointed at the configured QLever endpoint."""
    endpoint = os.environ.get("QLEVER_ENDPOINT", _DEFAULT_QLEVER_ENDPOINT)
    return Store("sparql", endpoint, mapping=WeatherMapping())


def city_temperature(name: str = "Chicago") -> float | None:
    """Current temperature (°C) for a named city, or None if not found."""
    kb = get_store()
    city = _city_item(name)
    for stmt in kb.filter(subject=city, property=wd.temperature, limit=1):
        assert isinstance(stmt.snak, ValueSnak)
        assert isinstance(stmt.snak.value, Quantity)
        return float(stmt.snak.value.amount)
    return None


def city_condition(name: str = "Chicago") -> str | None:
    """Current weather condition (e.g. "Rainy") for a named city, or None if not found."""
    kb = get_store()
    city = _city_item(name)
    for stmt in kb.filter(subject=city, property=wd.weather_history, limit=1):
        assert isinstance(stmt.snak, ValueSnak)
        assert isinstance(stmt.snak.value, String)
        return str(stmt.snak.value.content)
    return None


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

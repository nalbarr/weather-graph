"""SPARQL_Mapping bridging weather-graph's `wx:` RDF vocabulary to KIF's Wikidata-shaped
statement model (Item/Property/Statement) — reusing real `wd.*` Wikidata properties loosely
rather than minting custom ones (see plans/PLAN_KIF.md, "Vocabulary mapping").

Only `wx:temperatureC` and `wx:condition` are mapped: those are the only two predicates the 3
fixed demo questions actually need (mirrors `neo4j/cypher.py`, which likewise never queries
`wx:country`/`wx:humidity` despite `weather.cypher` loading them). `wx:country` was deliberately
left unmapped too: `wd.country` (P17) is declared `ItemDatatype` in KIF's vocabulary, but
weather-graph's `wx:country` values are plain string literals — a real type mismatch, not just a
naming stretch like `condition`'s.

`wd.weather_history` (P4150, "description of historical weather") is a semantic stretch for
`wx:condition` (a live condition category like "Rainy") — the closest fit in KIF's vocabulary;
accepted per the "reuse wd.* loosely" decision.
"""

from __future__ import annotations

from kif_lib import Item, Normal, Quantity, String, Variables
from kif_lib.compiler.sparql.mapping import SPARQL_Mapping, register
from kif_lib.rdflib import Namespace
from kif_lib.vocabulary import wd

WX = Namespace('http://example.org/weather#')

x, y = Variables('x', 'y')


class WeatherMapping(SPARQL_Mapping):
    """Maps `wx:temperatureC`/`wx:condition` triples to KIF statements."""

    @register([wd.temperature(Item(x), Quantity(y, wd.degree_Celsius))], rank=Normal)
    def wd_temperature(self, c, x, y):
        c.q.triples()((x, WX.temperatureC, y))

    @register([wd.weather_history(Item(x), String(y))], rank=Normal)
    def wd_condition(self, c, x, y):
        c.q.triples()((x, WX.condition, y))

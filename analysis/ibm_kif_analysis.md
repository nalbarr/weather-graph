# IBM KIF analysis (sub-agent 2)

Analysis of `kif/` (IBM's Knowledge Integration Framework) as the reference for the port,
grounded in reading the actual source and live-testing against it — not just the README/tutorial.

## Data model

KIF's entire query surface (`Store.filter(subject=..., property=..., value=...)`) is built around
*Wikidata-shaped* statements: `Statement(Item, ValueSnak(Property, Value))`. The tutorial's Brazil
example (`examples/quickstart.ipynb`) queries `Store('wdqs')` — the live public Wikidata Query
Service — using `wd.Brazil`, `wd.continent`, etc., all real Wikidata IDs. This is *not* a
representative template for querying arbitrary local RDF like weather-graph's `wx:` vocabulary.

## Bridging non-Wikidata RDF: `SPARQL_Mapping`

`examples/sparql_mapping.ipynb` is the real template: a `SPARQL_Mapping` subclass with `@register`
decorated methods that translate a *logical* Wikidata-shaped pattern into a *physical* SPARQL
triple pattern against arbitrary RDF (there, a PubChem chemistry vocabulary with no Wikidata
connection at all):

```python
class MyPubChemMapping(SPARQL_Mapping):
    @register([wd.mass(Item(x), Quantity(y, wd.gram_per_mole))], rank=Normal)
    def wd_mass(self, c, x, y):
        c.q.triples()((x, SIO.has_attribute, ...))  # arbitrary real RDF pattern
```

`wd.mass` here is just a *logical property label* borrowed from Wikidata's vocabulary — the actual
RDF underneath (`SIO.has_attribute`, PubChem's own ontology) has nothing to do with Wikidata.
weather-graph's `mapping.py` follows this exact shape for `wd.temperature`/`wd.weather_history`.

**Confirmed live, not assumed:** the production mapping in `kif_lib/compiler/sparql/mapping/pubchem.py`
uses this same pattern with real preprocess/postprocess type coercion
(`{v: M.CheckLiteral(set_datatype=XSD.float)}`), reinforcing that this is KIF's actual intended
mechanism for non-Wikidata sources, not a toy notebook example.

## Subject identity — a finding that reversed an earlier plan assumption

Live-tested directly: when a `SPARQL_Mapping` binds a SPARQL variable to an RDF subject, the
resulting `Statement`'s `Item` wraps *whatever IRI is actually in the data* —
`http://example.org/weather#city0`, not any Wikidata Q-ID. There is no automatic connection
between a mapped property's Wikidata origin and a fabricated Wikidata identity for the subject.
Using real Wikidata Q-IDs for weather-graph's city subjects (as originally planned) would require
an explicit per-city rewrite layer inside the mapping — real extra complexity for no functional
gain given the "hardcoded, simple" scope. Resolution: subjects are the real `wx:cityN` IRIs.

## Store construction

- `Store('sparql', <http(s)-endpoint-url>, mapping=...)` — the production path. The first
  positional argument is auto-detected as an HTTP(S) IRI (`SPARQL_Store._is_http_or_https_iri`)
  and routed straight to `Store('sparql-httpx', iri, mapping=...)` — a thin HTTP SPARQL client, no
  embedded index/server management. This is what weather-graph uses, pointed at
  `QLEVER_ENDPOINT` (the *existing* `make qlever-up` server).
- `Store('sparql-qlever', ...)` (`kif_lib/store/sparql/qlever.py`) is a *different*, heavier store
  that manages its own embedded QLever index/server subprocess (`PostInitIndexBuilderArgs`,
  `PostInitServerArgs`). **Not used** — would mean two independent QLever setups.
- A quirk found but irrelevant to production use: `Store('sparql', data=<inline turtle>, ...)`
  (no `iri`) cascades through `Store('rdf', ...)`, which tries `sparql-jena` → `sparql-rdfox` →
  `sparql-qlever` → `sparql-rdflib` in order and produced a confusing path-not-found error in this
  environment (likely from the `sparql-qlever` fallback attempt). Worked around for local/offline
  testing by calling `Store('sparql-rdflib', data=..., format='ttl', mapping=...)` directly. Not
  relevant to the real `iri=`-based production path, which never touches this cascade.

## Value extraction

`Statement.subject` is an `Item` (`.iri.content` for the raw IRI string). `Statement.snak` is a
`ValueSnak` for populated properties (`.property`, `.value`); `Value` subclasses expose native
Python data: `Quantity.amount` (a `Decimal`), `String.content` (a `str`). No `ORDER BY`/sort
support in `Store.filter()` — multi-result ranking (e.g. "3 hottest cities") is done in Python
after fetching all matching statements, same as it would be with a plain `LIMIT`-less SPARQL query
processed client-side.

## Implication for the port

Given the "hardcoded queries, no LLM" scope decision, `kif.py` needs only: a `get_store()` builder
pointed at `QLEVER_ENDPOINT`, and 3 small functions (`city_temperature`, `city_condition`,
`hottest_cities`) built on `kb.filter(...)` — no query generation, no validator layer (KIF's
strict typed `Value`/`Property` construction is itself the safety mechanism, analogous to how
parameterization was the safety mechanism in the Neo4j port).

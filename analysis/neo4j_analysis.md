# movies-python-bolt analysis (sub-agent 2)

Analysis of `movies-python-bolt/` as the Cypher/driver reference for the port. Note: this example
is a Flask REST app (`movies_sync.py` / `movies_async.py`) with a browser UI (`static/`) — the
Flask/HTTP layer is out of scope for weather-graph; only the driver + Cypher patterns below are
relevant.

## Driver setup

```python
from neo4j import GraphDatabase, basic_auth

url = os.getenv("NEO4J_URI", "neo4j+s://demo.neo4jlabs.com")
username = os.getenv("NEO4J_USER", "movies")
password = os.getenv("NEO4J_PASSWORD", "movies")
database = os.getenv("NEO4J_DATABASE", "movies")

driver = GraphDatabase.driver(url, auth=basic_auth(username, password))
```

Dependency: `neo4j==6.2.0` (`requirements.txt`), optionally `neo4j-rust-ext` for performance.

## Query pattern

No query generation — every Cypher string is fixed and parameterized, executed via
`driver.execute_query`:

```python
records, _, _ = driver.execute_query(
    query("""
        MATCH (m:Movie)<-[:ACTED_IN]-(a:Person)
        RETURN m.title AS movie, collect(a.name) AS cast
        LIMIT $limit
    """),
    database_=database,
    routing_="r",       # read-only routing hint
    limit=request.args.get("limit", 100),
)
```

- `query()` is just `dedent(q).strip()` — a `LiteralString` cast for type-checking, not a safety
  mechanism (parameters, not string interpolation, are what prevent injection here).
- Named parameters (`$limit`, `$title`) are passed as kwargs to `execute_query`, not interpolated
  into the Cypher string — this is the real safety boundary, analogous to weather-graph's
  code-level `validate_query` gate but achieved structurally rather than by regex-checking text.
- `routing_="r"` marks a query as read-only for cluster routing; `result_transformer_=neo4j.Result.single`
  narrows to one record; `neo4j.Result.consume` is used for a write with no rows needed (the
  `/vote` endpoint's `SET`).

## Data model

Labeled property graph: `(:Movie {title, summary, released, duration, rated, tagline, votes})`
and `(:Person {name})`, related by typed relationships (`ACTED_IN`, `DIRECTED`, etc.), with
relationship properties (`r.roles`) for cast credits. This is richer than weather-graph's data
(a movie graph has real relationships between two node types); weather-graph's 8 flat `wx:City`
records have no relationships at all, so the port only needs a single node label, not a
relationship model.

## Implication for the port

- Use `neo4j` as the driver dependency. Env var names deliberately diverge from this reference:
  `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` (not this file's `NEO4J_USER`) —
  `NEO4J_USERNAME` is what `neo4j-cli` itself reads from a `.env` file (confirmed via
  `neo4j-cli query --help`), and one `.env` needs to serve both the CLI and weather-graph's own
  driver code consistently.
- Given the hardcoded-queries decision, weather-graph's Cypher layer should mirror this file's
  shape directly: fixed parameterized Cypher strings run via `driver.execute_query(..., routing_="r")`,
  no query-string validator needed (parameters are the safety mechanism, and there's no
  LLM-generated Cypher to validate against a predicate allowlist in this scope).
- No Flask/HTTP layer, no `static/` UI, no vote/write endpoint — weather-graph's Neo4j demo is a
  read-only CLI script (`demo_neo4j.py`), not a web app.

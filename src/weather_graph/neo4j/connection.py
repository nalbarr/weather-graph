"""Neo4j driver setup.

Defaults target the local Docker container started by `make neo4j-up`
(see weather-graph/Makefile and PLAN_NEO4J.md), not a remote/demo instance.

Uses `NEO4J_USERNAME` rather than `movies-python-bolt`'s `NEO4J_USER` — `neo4j-cli` (which the
Makefile's neo4j-* targets shell out to) reads exactly `NEO4J_URI`/`NEO4J_USERNAME`/
`NEO4J_PASSWORD`/`NEO4J_DATABASE` from a `.env` file (confirmed via `neo4j-cli query --help`), so
this matches that rather than the movies example, letting one `.env` serve both the CLI and this
driver.

Calls `load_dotenv()` itself rather than assuming it's already been called: the rest of
weather-graph only picks up `.env` as an incidental side effect of importing `beeai_framework`
(which pulls in `python-dotenv` transitively) — this module deliberately has no BeeAI/Mellea
dependency (see PLAN_NEO4J.md's hardcoded-Cypher scope decision), so without this it would
silently read empty env vars and fall back to the wrong defaults. Confirmed live: without this,
`uv run weather-graph-neo4j` fails with a Neo4j AuthError even with a correct `.env`.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, basic_auth

load_dotenv()

_DEFAULT_URI = "bolt://localhost:7687"
_DEFAULT_USER = "neo4j"
_DEFAULT_PASSWORD = "neo4j"
_DEFAULT_DATABASE = "neo4j"


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    """Build (once) a driver for the configured Neo4j instance."""
    uri = os.environ.get("NEO4J_URI", _DEFAULT_URI)
    user = os.environ.get("NEO4J_USERNAME", _DEFAULT_USER)
    password = os.environ.get("NEO4J_PASSWORD", _DEFAULT_PASSWORD)
    return GraphDatabase.driver(uri, auth=basic_auth(user, password))


def database() -> str:
    """The configured database name (Neo4j's default database unless overridden)."""
    return os.environ.get("NEO4J_DATABASE", _DEFAULT_DATABASE)

"""The weather knowledge graph: loaded from `model/*.ttl` into either an in-memory rdflib
graph or a local QLever triple store, selected by the `GRAPH_BACKEND` env var.

`GRAPH_BACKEND=memory` (default) parses `model/*.ttl` directly into an in-memory
`rdflib.Graph()` — no external services needed, which is what the offline test suite uses.
`GRAPH_BACKEND=qlever` returns a `Graph` backed by `rdflib`'s `SPARQLStore`, pointed at a local
QLever instance (see `data/qlever/Qleverfile` and `docs/learning_plan_sparql.md`). `Graph.query()`
forwards the full SPARQL text to the store either way, so `sparql.py` needs no backend-specific
code.
"""

from __future__ import annotations

import glob
import os
from functools import lru_cache

from rdflib import Graph
from rdflib.plugins.stores.sparqlstore import SPARQLStore

_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "model")


def _load_memory_graph() -> Graph:
    g = Graph()
    for path in sorted(glob.glob(os.path.join(_MODEL_DIR, "*.ttl"))):
        g.parse(path, format="turtle")
    return g


def _load_qlever_graph() -> Graph:
    endpoint = os.environ["QLEVER_ENDPOINT"]
    return Graph(store=SPARQLStore(query_endpoint=endpoint, returnFormat="json"))


@lru_cache(maxsize=1)
def get_graph() -> Graph:
    """Build (once) and return the weather RDF graph for the configured backend."""
    backend = os.environ.get("GRAPH_BACKEND", "memory")
    if backend == "memory":
        return _load_memory_graph()
    if backend == "qlever":
        return _load_qlever_graph()
    raise ValueError(f"Unknown GRAPH_BACKEND {backend!r}; expected 'memory' or 'qlever'.")

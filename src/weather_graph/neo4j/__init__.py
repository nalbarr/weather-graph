"""Neo4j backend: fixed (non-LLM-generated) Cypher queries over the weather graph.

See `movies-python-bolt/movies_sync.py` for the reference driver/query pattern this follows.
Unlike the RDF backends (`weather_graph.graph_data`, `weather_graph.sparql`), this is a distinct
labeled-property-graph data model and does not go through `GRAPH_BACKEND` / `get_graph()`.
"""

from __future__ import annotations

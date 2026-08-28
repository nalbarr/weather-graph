"""KIF backend: fixed (non-LLM-generated) queries over the weather graph via IBM's KIF framework.

Reuses weather-graph's existing QLever server (`make qlever-up`) through a KIF SPARQL store
pointed at `QLEVER_ENDPOINT` — see `mapping.py` for how KIF's Wikidata-shaped statement model is
bridged to the `wx:` RDF vocabulary, and `plans/PLAN_KIF.md` for the full design rationale.
"""

from __future__ import annotations

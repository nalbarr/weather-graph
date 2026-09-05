"""weather-graph — NL -> validated SPARQL over a weather RDF graph.

Default agent backend: pydantic-ai (`AGENT_BACKEND=pydantic_ai`). Also available: `"langgraph"`
(variant) and `"beeai"` (legacy BeeAI + Mellea, opt-in — requires `uv sync --extra beeai`). See
`src/weather_graph/agents/` and `docs/QUICKSTART.md`.
"""

__version__ = "0.1.0"

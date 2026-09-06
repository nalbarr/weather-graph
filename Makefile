.PHONY: help run run-pydantic-ai run-langgraph run-beeai beeai-check test qlever-cli-check qlever-health qlever-index qlever-up qlever-down qlever-status neo4j-cli-check neo4j-health neo4j-up neo4j-status neo4j-migrate neo4j-down kif-check kif-llm-check

export PATH := $(HOME)/.local/bin:$(PATH)

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

run: ## Run the packaged demo (uv run weather-graph); AGENT_BACKEND in .env picks the agent (default: pydantic_ai)
	uv run weather-graph

run-pydantic-ai: ## Force the default pydantic-ai agent backend, regardless of .env
	AGENT_BACKEND=pydantic_ai uv run weather-graph

run-langgraph: ## Force the LangGraph variant agent backend, regardless of .env
	AGENT_BACKEND=langgraph uv run weather-graph

run-beeai: beeai-check ## Force the opt-in legacy BeeAI + Mellea agent backend, regardless of .env
	AGENT_BACKEND=beeai uv run weather-graph

beeai-check: ## Verify the optional beeai-framework/mellea extra is installed
	@uv run python -c "import beeai_framework, mellea" >/dev/null 2>&1 || { echo "beeai-framework/mellea not installed; run: uv sync --extra beeai" >&2; exit 1; }
	@echo "beeai-framework/mellea found"

test: ## Run the offline test suite (no LLM / no network)
	uv run pytest

qlever-index: ## Stage model/*.ttl and (re)build the local QLever index
	cd data/qlever && qlever get-data && qlever index

qlever-up: ## Start the local QLever SPARQL server (requires qlever-index first)
	cd data/qlever && qlever start

qlever-down: ## Stop the local QLever SPARQL server
	cd data/qlever && qlever stop

qlever-status: ## Show QLever process/server status
	cd data/qlever && qlever status

qlever-cli-check: ## Verify the qlever CLI is installed
	@command -v qlever >/dev/null 2>&1 || { echo "qlever CLI not found; install with: uv tool install qlever" >&2; exit 1; }
	@echo "qlever CLI found: $$(command -v qlever)"

qlever-health: qlever-cli-check ## Check QLEVER_ENDPOINT (from .env) is actually up and answering
	@set -a; [ -f .env ] && . ./.env; set +a; \
	endpoint="$${QLEVER_ENDPOINT:-http://localhost:7011}"; \
	if curl -sf "$$endpoint" --data-urlencode "query=ASK{?s ?p ?o}" \
		-H "Accept: application/sparql-results+json" >/dev/null; then \
		echo "QLever endpoint healthy: $$endpoint"; \
	else \
		echo "QLever endpoint not responding: $$endpoint (is 'make qlever-up' running?)" >&2; \
		exit 1; \
	fi

# All neo4j-* targets go through neo4j-cli (uv tool install neo4j-cli) — no raw docker/python.
# CLI flags below confirmed against a real `neo4j-cli --help` / `neo4j-cli query --help`
# (v1.13.0); recheck against your installed version if it differs.

neo4j-cli-check: ## Verify the neo4j-cli tool is installed
	@command -v neo4j-cli >/dev/null 2>&1 || { echo "neo4j-cli not found; install with: uv tool install neo4j-cli" >&2; exit 1; }
	@echo "neo4j-cli found: $$(command -v neo4j-cli)"

neo4j-health: neo4j-cli-check ## Check the Neo4j instance (from .env) is actually up and answering
	neo4j-cli query "RETURN 1 AS ok" --env .env

neo4j-up: ## Start a local Neo4j instance via neo4j-cli, password pinned to .env's NEO4J_PASSWORD
	@set -a; [ -f .env ] && . ./.env; set +a; \
	neo4j-cli docker create --name weather-graph-neo4j --wait --rw \
		--password "$${NEO4J_PASSWORD:-neo4j}" --no-store-credential

neo4j-status: ## Show the local Neo4j instance's status
	@neo4j-cli docker list | grep weather-graph-neo4j || echo "weather-graph-neo4j: not running"

neo4j-migrate: ## Load model/weather.ttl's data into Neo4j (requires neo4j-up first)
	neo4j-cli query --rw --env .env < data/neo4j/weather.cypher

neo4j-down: ## Stop and remove the local Neo4j instance
	neo4j-cli docker stop weather-graph-neo4j --rw && neo4j-cli docker delete weather-graph-neo4j --yes --force --rw

# KIF (IBM's Knowledge Integration Framework) reuses the existing qlever-up server (see
# plans/PLAN_KIF.md, "QLever wiring") rather than managing its own instance — so there's no
# kif-up/kif-down here, just a dependency check. `qlever-cli-check`/`qlever-health` above cover
# the actual server.

kif-check: ## Verify the kif_lib dependency is installed
	@uv run python -c "import kif_lib" >/dev/null 2>&1 || { echo "kif_lib not installed; run: uv sync" >&2; exit 1; }
	@echo "kif_lib found: $$(uv run python -c 'import kif_lib; print(kif_lib.__version__)')"

# Second KIF Store backend (weather_graph.kif.llm_store): an LLM standing in for the SPARQL store,
# via a vendored, patched copy of kif-llm-store (upstream isn't pip-installable, see
# src/weather_graph/kif/_vendor/kif_llm_store/__init__.py) plus the one real extra dependency,
# nest-asyncio. No server lifecycle target: it's a local Ollama call, not a new service.

kif-llm-check: ## Verify the vendored kif-llm-store package imports and the kif-llm extra is installed
	@uv run python -c "from weather_graph.kif._vendor.kif_llm_store import LLM_Store" >/dev/null 2>&1 || { echo "vendored kif-llm-store failed to import (see src/weather_graph/kif/_vendor/); run: uv sync --extra kif-llm" >&2; exit 1; }
	@echo "vendored kif-llm-store found and importable"

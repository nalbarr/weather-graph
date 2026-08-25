.PHONY: help run test qlever-index qlever-up qlever-down qlever-status

export PATH := $(HOME)/.local/bin:$(PATH)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

run: ## Run the packaged demo (uv run weather-graph)
	uv run weather-graph

test: ## Run the offline test suite (no LLM / no network)
	uv run pytest

qlever-index: ## Stage model/*.ttl and (re)build the local QLever index
	cd qlever && qlever get-data && qlever index

qlever-up: ## Start the local QLever SPARQL server (requires qlever-index first)
	cd qlever && qlever start

qlever-down: ## Stop the local QLever SPARQL server
	cd qlever && qlever stop

qlever-status: ## Show QLever process/server status
	cd qlever && qlever status

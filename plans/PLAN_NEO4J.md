# PLAN_NEO4J.md

## Role
You are an systems architect and want to extend current weather-graph which support both in-memory RDF database using Qlever as default open-source implementation.

## Objectives

## Agents

### Orchestrator
- Will first checkout a new branch in weather-graph/ called dev-20260828-na.
- The orchestrator manages three sub agents each specialized on specific tasks below.
- Will summarize final plan changes as as:
  - docs/learning_plan_neo4j.md
- Will update Makefile to represent new neo4j specific tasks that are analogous to qlever tasks:
  - neo4j-up
  - neo4j-status
  - neo4j-migrate
  - neo4j-down
- Will summarize update existing docs/QUICKSTART.md

### Sub agent 1
- Sub agent 1 is focused on understanding existing weather-graph/ implementation which tests 3 RDF queries related to weather in Chicago, etc.
- Inputs:
  - weather-graph/ implementation
- Outputs:
  - Markdown document as intermediate analysis artifact as:
    - analysis/weather_graph_analysis.md

### Sub agent 2
- Sub agent 2 is focused on understand Neo4j example focus on Neo4j labeled property graph implementation and cypher queries. Assume local Neo4j instance is available.
- Inputs:
  - movies-python-bolt/
- Outputs:
  - Markdown documewnt as intermediate analysis artifact as:
    - analysis/neo4j_analysis.md

### Sub agent 3
- Sub agent 3 is focus on proposing design and implementation to port Neo4j example to weather-graph/
- Should consider whether weather_graph/src and weather_graph/tests need to be restructured to
  separate the concerns of the default RDF backends (memory + qlever, which share graph_data.py /
  sparql.py / models.py via rdflib's Graph.query()) from the new Neo4j backend (a distinct labeled
  property graph + Cypher, which cannot reuse that same abstraction). Propose a package layout
  (e.g. backend-specific subpackages/modules under src/ and tests/) rather than bolting Neo4j onto
  the existing RDF-shaped modules.
- Inputs:
  - sub agent 1 analysis at:
    - analysis/weather_graph_analysis.md
  - sub agent 2 analysis at:
    - analysis/neo4j_analysis.md
- Outputs:
  - weather-graph/src/weather_graph/neo4j
    - cypher.py as neo4j based query implementation
  - weather-graph/src/weather_graph/neo4j
    - weather.cypher as neo4j based schema to create neo4j instance
  - weather-graph/src/weather_graph/demo_neo4j.py
    - new demo asking same queries but calling neo4j backend
  - weather-graph/tests/test_neo4j.py
    - unit tests exercise all cypher queries
  - Will update .env.example with reasonable defaults


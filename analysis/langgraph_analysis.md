# LangGraph analysis (variant agent backend)

Written while building `src/weather_graph/agents/langgraph_agent.py`. Covers the API actually used,
pinned versions, the "forced tool-first via graph shape" design, and — verified live against local
`granite4:micro` — a real structured-output compatibility issue and how it was resolved (the same
class of issue found on the pydantic-ai side, but with a different fix).

## Versions

`langgraph==1.2.11`, `langchain-ollama==1.1.0` (pulls in `langchain-core==1.6.2`), pinned in
`pyproject.toml` as `langgraph>=1.2,<2` / `langchain-ollama>=1.1,<2`.

## Pointing at local Ollama

`langchain-ollama` talks to Ollama's *native* API (not the OpenAI-compatible one pydantic-ai uses):

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(model="granite4:micro", base_url="http://127.0.0.1:11434", temperature=0)
```

## Structured output: `with_structured_output`, and the same class of issue as pydantic-ai

`ChatOllama.with_structured_output(schema, method=...)` supports three `method` values:
`"json_schema"` (default — Ollama's own constrained/schema-guided decoding), `"function_calling"`
(tool-calling), and `"json_mode"` (schema described via the prompt, response parsed as plain JSON).

**Verified live: the default `method="json_schema"` hung indefinitely** against
`granite4:micro`/this Ollama version — the same failure mode `pydantic_ai_agent.py` hit with
`NativeOutput` (also Ollama's constrained JSON-schema decoding under the hood; these two are
effectively the same underlying Ollama feature, reached through two different libraries, and both
hung the same way). **Switched to `method="json_mode"`: fast and reliable.**

One real difference from pydantic-ai's `PromptedOutput` surfaced here: `PromptedOutput`
automatically injects the schema (field names, types, descriptions) into the prompt, but
`langchain-ollama`'s `json_mode` does **not** — it only sets Ollama's `format: "json"` (valid JSON,
no schema) and leaves shaping the response entirely to the caller's own prompt. Without an explicit
instruction, `granite4:micro` deterministically (at `temperature=0`, the same output every time)
omitted the `rationale` field it was never actually told about, failing
`WeatherSparqlSpec` validation on every attempt — a plain internal retry loop didn't help, since
retrying an identical prompt against a deterministic model reproduces the identical mistake.
**Fixed** by adding an explicit `_JSON_SHAPE` instruction naming all three required keys
(`intent`, `sparql`, `rationale`) directly in the generation prompt. After that fix, this backend
answered **all 3** of the demo's fixed questions correctly and quickly in a live end-to-end run —
including the ranking question ("three hottest cities") that pydantic-ai's `PromptedOutput`
sometimes still fails on against this same model (see `pydantic_ai_analysis.md`;
`docs/learning_plan_agents.md` has the side-by-side).

## "Forced tool-first" via graph shape, not a tool

Rather than exposing the graph query as a bindable tool and hoping the model calls it (which is
what LangChain's own tool-calling agents do), `langgraph_agent.py` expresses the requirement as the
*shape of the graph itself*: a linear `StateGraph` with exactly one path,
`START -> query -> answer -> END`. The `query` node always runs `shared.generate_and_run()` (the
real SPARQL query); the `answer` node only ever sees its output. There is no branch where `answer`
could run first or `query` could be skipped — this is LangGraph's idiomatic way to guarantee
ordering, and the deliberate point of contrast with pydantic-ai's two-sequential-Python-calls
approach to the same guarantee (see `pydantic_ai_analysis.md`).

```python
graph = StateGraph(_State)
graph.add_node("query", _query_node)
graph.add_node("answer", _answer_node)
graph.add_edge(START, "query")
graph.add_edge("query", "answer")
graph.add_edge("answer", END)
app = graph.compile()
result = await app.ainvoke({"question": question})
```

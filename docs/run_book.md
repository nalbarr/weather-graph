# Run book: a real weather-graph terminal session

This is a captured, real terminal session — every command below was actually run against this
repo (branch `dev-20260905c-na`, `kif-llm-store` vendored per
[learning_plan_kif_llm.md](learning_plan_kif_llm.md)), and every output block is the literal
output produced, not a hypothetical. It's more verbose than [QUICKSTART.md](QUICKSTART.md) on
purpose: QUICKSTART is the terse reference; this is the "what actually happens when you run it,
including the flaky parts" companion — read this when something QUICKSTART shows you doesn't
match what you're seeing, or when you want to know *why* a step is there before you run it.

Machine this was captured on: macOS (`darwin`), `uv 0.11.21`, `ollama 0.33.3`, models already
pulled locally: `granite4:micro`, `granite4.2:3b`, `qwen2.5:latest`, and others unrelated to this
repo.

## 0. Before you start: check prerequisites

```bash
uv --version
ollama --version
ls -la .env       # does one already exist?
ls -d .venv       # has `uv sync` ever been run here?
ollama list       # is granite4:micro already pulled?
```

Captured output:

```
uv 0.11.21 (5aa65dd7a 2026-06-11 aarch64-apple-darwin)
ollama version is 0.33.3
ls: .env: No such file or directory
.venv
NAME                       ID              SIZE      MODIFIED
granite4.2:3b              40577dc168a3    2.2 GB    27 hours ago
granite4:micro             89962fcc7523    2.1 GB    2 weeks ago
nomic-embed-text:latest    0a109f422b47    274 MB    2 weeks ago
qwen2.5:latest             845dbda0ea48    4.7 GB    2 weeks ago
...
```

Reading this before doing anything else told us: `uv`/`ollama` are installed, `.venv` already
exists from a prior session (so `uv sync` would be fast, not a from-scratch resolve), `.env`
does **not** exist yet (first real setup step needed), and `granite4:micro` — the model every
backend in this repo defaults to — is already pulled, so `ollama pull granite4:micro` could be
skipped this time. Your own first run will likely need that pull; it's in QUICKSTART's
Prerequisites block for exactly this reason.

## 1. Setup

```bash
cp .env.example .env
uv sync
```

`.env.example` → `.env` is a plain copy, not a template substitution — every default in it
(`AGENT_BACKEND="pydantic_ai"`, `GRAPH_BACKEND="memory"`, `PYDANTIC_AI_MODEL="granite4:micro"`,
etc.) is already correct for a first run against local Ollama. `.env` is gitignored, so this copy
is yours to edit freely without touching anything tracked.

`uv sync` (no `--extra` flags) installs exactly the **core** dependency set from
`pyproject.toml`: `pydantic-ai`, `langgraph`, `langchain-ollama`, `kif-lib`, `neo4j`, `rdflib`,
plus dev tooling (`pytest`, `ruff`, `mypy`). It deliberately does **not** install
`beeai-framework`/`mellea` (the opt-in `beeai` extra) or `nest-asyncio` (the opt-in `kif-llm`
extra) — those are pulled in only when you explicitly ask for them (§6 below). This matters
enough to repeat: **a bare `uv sync` at any later point silently drops both extras back out**
even if you'd previously installed them in the same `.venv` — there's no "sticky" state. If a
backend that needs one of them suddenly starts failing with an import error after you've run a
plain `uv sync`, this is almost always why.

Captured tail of the `uv sync` output from this session (abbreviated — the exact package list
will differ run to run as this repo's dependencies evolve):

```
Resolved 199 packages in ...
...
 - mellea==0.7.0
 - nest-asyncio==1.6.0
 - ...
(these being *removed* because this uv sync had neither --extra flag — they'd been
 installed in .venv by an earlier session in this environment)
```

## 2. Run the default agent demo

```bash
uv run weather-graph
```

This is the flagship demo: 3 fixed natural-language weather questions about Chicago, answered by
whichever `AGENT_BACKEND` your `.env` names (default: `pydantic_ai`) generating and running a
validated SPARQL query against the in-memory RDF graph (`GRAPH_BACKEND="memory"` by default — no
external services needed for this step).

Captured output, this session:

```
=== Q: What is the weather like in Chicago right now, and is it warm?
A: The current weather in Chicago is 21.0°C with a condition of Partly Cloudy. This temperature is considered warm.

=== Q: Is Chicago one of the three hottest cities in the data?
Traceback (most recent call last):
  ...
pydantic_ai.exceptions.UnexpectedModelBehavior: Exceeded maximum output retries (3)
```

**This is not a bug you introduced — it's a documented, known flake.** Question 1 answered
correctly. Question 2 — "is Chicago one of the three hottest cities," the one question in the
fixed set that requires the model to actually rank/compare multiple rows rather than read one
value — exhausted pydantic-ai's built-in output-retry budget (3 attempts) against `granite4:micro`
specifically. QUICKSTART.md's Troubleshooting section names this exact exception. It's a real,
observed limitation of this small local model on the harder of the 3 questions, not something
wired incorrectly in this repo. Two ways to deal with it:

- **Just retry** — `uv run weather-graph` again; small local models are stochastic enough that a
  second attempt sometimes succeeds where the first didn't.
- **Switch to the LangGraph variant** (next section) — verified more reliable on this exact
  question in [learning_plan_agents.md](learning_plan_agents.md)'s live-testing record.

## 3. Run the LangGraph variant

```bash
make run-langgraph
```

Equivalent to `AGENT_BACKEND=langgraph uv run weather-graph` — forces the LangGraph backend for
this one invocation regardless of what `.env` says, without editing the file. Same 3 questions,
different underlying agent/orchestration library (`ChatOllama.with_structured_output`, a compiled
linear graph, rather than pydantic-ai's typed `Agent`/`output_type`).

Captured output, this session — all 3 questions, first try:

```
=== Q: What is the weather like in Chicago right now, and is it warm?
A: The current weather in Chicago is partly cloudy with a temperature of 21.0 degrees Celsius. Yes, it is warm.

=== Q: Is Chicago one of the three hottest cities in the data?
A: Based on the provided SPARQL query and the data it returned, Chicago is not one of the three hottest cities in the data. The three hottest cities are Cairo with a temperature of 33.0°C, Sydney with a temperature of 29.0°C, and Nairobi with a temperature of 26.0°C.

=== Q: Is it currently raining or snowing in Chicago?
A: Based on the provided SPARQL query, there is no current data indicating that it is raining or snowing in Chicago.
```

All three correct, including the ranking question that tripped up the default backend above —
this is the concrete, observed reason [learning_plan_agents.md](learning_plan_agents.md) calls
LangGraph out as the more reliable choice on this particular model, not a claim taken on faith.

## 4. Run the offline test suite

```bash
uv run pytest -q
uv run ruff check .
```

Captured output, this session (right after the bare `uv sync` in §1 — no extras installed):

```
sssssss........................sss.........                              [100%]
33 passed, 11 skipped in 4.87s
All checks passed!
```

**11 skips, not a smaller number**, precisely because neither `beeai` nor `kif-llm` was installed
at this point in the session — every test gated behind one of those extras (`test_agents_beeai.py`
and its whole matrix, `test_kif_llm.py`) skips cleanly rather than failing or erroring, by design.
This is the offline-safe invariant this repo maintains throughout: `uv run pytest` never needs a
live Ollama, QLever, or Neo4j to pass — anything that does need one of those either mocks it or
skips cleanly without it. If you see a *different* skip count than 11, that's informative, not
alarming — it tells you which extras/live services were available in your environment at test
time (a `test_neo4j.py` skip, for instance, just means no Neo4j instance was reachable).

## 5. The KIF backend (fixed queries, no LLM, reuses QLever)

Two separate demos live under the KIF umbrella now — the original SPARQL/QLever-backed one, and
a second one built in this session's work
([PLAN_KIF_LLM.md](../plans/PLAN_KIF_LLM.md)) that swaps the `Store` for an LLM. Both need the
QLever server up for the first one's data (and for the comparison column in the second).

### 5a. Bring up QLever (if not already running)

```bash
make qlever-cli-check   # confirms the qlever CLI itself is installed
make qlever-index       # stage model/*.ttl and build the local index (once, or after model/*.ttl changes)
make qlever-up           # start the local SPARQL server
make qlever-status        # confirm it's actually running
```

This session, QLever was already running from earlier work in the same session (`qlever-index`
had already been done, so only `qlever-up`/`qlever-status` were needed):

```
PID      USER     START    RSS COMMAND
27444    nalbarr  14:15     0G qlever-server -i weather -j 8 -p 7011 -m 5G -c 2G -e 1G -k 200 -s 30s -a ...
```

If you're starting fresh, expect `qlever-index` to take noticeably longer than everything else in
this run book (it's building a real index from `model/*.ttl`), and `qlever-up` to return
immediately (it starts a background server process) — use `qlever-status`/`make qlever-health`
right after to confirm it actually came up rather than assuming a fast return means success.

### 5b. The SPARQL/QLever-backed KIF demo

```bash
make kif-check
uv run weather-graph-kif
```

`kif-check` just confirms `kif_lib` is importable (it's a core dependency, so this should always
pass once `uv sync` has run). Captured output:

```
kif_lib found: 0.13.0
---
=== Q: What is the weather like in Chicago right now, and is it warm?
A: Chicago is 21.0°C and 'Partly Cloudy'.

=== Q: Is Chicago one of the three hottest cities in the data?
A: Top 3 hottest: Cairo, Sydney, Nairobi. Chicago is hottest-3: False.

=== Q: Is it currently raining or snowing in Chicago?
A: Condition is 'Partly Cloudy' (raining/snowing: False).
```

No LLM in this path at all — fixed `kb.filter(subject=..., property=...)` calls compiled down to
SPARQL against QLever via a `SPARQL_Mapping` (`src/weather_graph/kif/mapping.py`). Same numbers
every single run, because it's reading the same fixed triples from `model/weather.ttl` every
time — worth noticing now, because it's the baseline the next demo is contrasted against.

### 5c. The LLM-backed KIF demo (the new one)

This one needs one extra install step the SPARQL-only demo above doesn't: the `kif-llm` extra
(just `nest-asyncio` — the `LLM_Store` code itself is vendored in-repo under
`src/weather_graph/kif/_vendor/`, because upstream `kif-llm-store` isn't pip-installable as
published; see [learning_plan_kif_llm.md](learning_plan_kif_llm.md) for the full story on that).

```bash
uv sync --extra kif-llm
make kif-llm-check
uv run weather-graph-kif-llm
```

Captured output:

```
Resolved 180 packages in 4ms
Installed 1 package in 2ms
 + nest-asyncio==1.6.0
---
vendored kif-llm-store found and importable
---
=== Q: What is the weather like in Chicago right now, and is it warm?
A: [SPARQL/QLever] Chicago is 21.0°C and 'Partly Cloudy'.
A: [LLM Store] Chicago is -50.0°C and 'storms'.

=== Q: Is Chicago one of the three hottest cities in the data?
A: [SPARQL/QLever] Top 3 hottest: Cairo, Sydney, Nairobi. Chicago is hottest-3: False.
A: [LLM Store] Top 3 hottest: Sydney, Paris, Nairobi. Chicago is hottest-3: False.

=== Q: Is it currently raining or snowing in Chicago?
A: [SPARQL/QLever] Condition is 'Partly Cloudy' (raining/snowing: False).
A: [LLM Store] Condition is 'weather patterns in the city' (raining/snowing: False).
```

Read the two columns side by side: `[SPARQL/QLever]` is byte-identical to §5b's output — same
fixed triples, same answer, every run. `[LLM Store]` is a **different** answer than any of the
three prior captures of this exact demo taken earlier in this session (`-10.2°C`/`'has seen some
of the coldest winters'`; `32.0°C`/`'climate trends'`; `1000000.0°C`/`'recorded by weather
stations'`; now `-50.0°C`/`'storms'`) — run-to-run variance is expected, not a sign anything is
broken. Both call sites are the *identical* `kb.filter(subject=..., property=...)` shape from
`base.KIFBackend`; only the `Store` underneath differs. That the answers disagree, and keep
disagreeing differently each run, is the entire point of this backend
([learning_plan_kif_llm.md](learning_plan_kif_llm.md), "grounding mismatch") — it's demonstrating
that the query *interface* is backend-agnostic, not that the two backends agree on facts.

## 6. Cleanup, if you're done for now

```bash
make qlever-down   # stop the local QLever server
```

Not run at the end of this particular session (QLever was deliberately left up, since
`GRAPH_BACKEND` isn't set to `"qlever"` in this repo's own `.env` default — it's a `memory`-backend
repo whose QLever/KIF paths are opt-in demos, not the default runtime path) — included here for
completeness, since a real working session eventually ends and the server should come down rather
than being left running indefinitely.

## Quick reference: what needs what

| Demo | Needs QLever up? | Needs an extra installed? | Needs live Ollama? |
|---|---|---|---|
| `uv run weather-graph` (default, `GRAPH_BACKEND=memory`) | No | No | Yes |
| `make run-langgraph` | No | No | Yes |
| `make run-beeai` | No | `beeai` (`uv sync --extra beeai`) | Yes |
| `uv run pytest` | No | No (skips cleanly without extras) | No |
| `uv run weather-graph-kif` | Yes | No | No — fixed queries, no LLM |
| `uv run weather-graph-kif-llm` | Yes (for the SPARQL column) | `kif-llm` (`uv sync --extra kif-llm`) | Yes (for the LLM Store column) |
| `uv run weather-graph-neo4j` | No (needs a Neo4j instance instead — `make neo4j-up`) | No | No — fixed queries, no LLM |

## See also

[QUICKSTART.md](QUICKSTART.md) — the terse reference this run book expands on;
[learning_plan.md](learning_plan.md) — the narrative walkthrough and cross-backend comparison
tables; [learning_plan_agents.md](learning_plan_agents.md) — the pydantic-ai output-retry flake
from §2, investigated in full; [learning_plan_kif_llm.md](learning_plan_kif_llm.md) — the §5c
grounding-mismatch finding, with more captured runs and the upstream-packaging story behind the
vendored `kif-llm-store` copy.

# PLAN_DRAWIO.md

## Role
You are a systems architect and want to produce a durable, visual companion to weather-graph's
existing prose documentation (`docs/run_book.md`, `docs/learning_plan*.md`,
`analysis/weather_graph_analysis.md`) by reviewing every `Makefile` target and the runtime
scenario each one belongs to, then summarizing the architecture as [draw.io](https://draw.io)
(diagrams.net, `.drawio` mxGraph XML) diagrams: one structural component diagram of the whole
system, plus one sequence diagram per major runtime scenario. This mirrors how
`plans/PLAN_KIF_LLM.md` used an orchestrator/sub-agent split to analyze-then-produce; this plan
reuses that shape for a documentation/diagramming deliverable instead of a code deliverable.

## Objectives

Decisions locked in before implementation (resolved via clarifying questions — see each
subsection for the reasoning):

1. **Scope: diagram what's runnable today, not aspirational architecture.** Every diagram traces
   back to an actual `Makefile` target and/or `[project.scripts]` entry point that exists on this
   branch right now (`run`, `run-langgraph`, `run-beeai`, `qlever-*`, `neo4j-*`, `kif-check`,
   `kif-llm-check`, `test`, and the four `uv run weather-graph*` entry points). No speculative
   future backends, no redrawing of code that isn't merged.
2. **Two diagram kinds, not one.** A single component diagram cannot show both "what talks to
   what, always" and "what happens, in order, for this one scenario" without becoming unreadable —
   the repo already has this exact lesson learned the hard way in prose (`docs/run_book.md` is
   deliberately more verbose than `docs/QUICKSTART.md` for the same reason: different readers need
   different altitudes). So:
   - **One structure/component diagram** (`diagrams/component_diagram.drawio`) — the static picture:
     every module/package (`agents/`, `kif/`, `neo4j/`, `sparql.py`, `graph_data.py`, the four
     `demo*.py` entry points), every external service (QLever, Neo4j, Ollama), and every backend
     dispatch point (`AGENT_BACKEND`, `GRAPH_BACKEND`), with edges labeled by *how* they connect
     (in-process import vs. HTTP vs. Bolt vs. subprocess/CLI).
   - **One sequence diagram per major scenario** (`diagrams/sequence_<scenario>.drawio`) — the
     dynamic picture: actor → CLI entry point → backend dispatch → external service → response,
     for one concrete `make`/`uv run` invocation at a time.
3. **Major scenarios = the rows of `docs/run_book.md`'s "Quick reference: what needs what" table,
   minus the offline test suite.** That table is already the canonical scenario list this repo
   maintains (six demo rows: default pydantic-ai, LangGraph, BeeAI, KIF/QLever, KIF-LLM, Neo4j) —
   reusing it instead of inventing a new taxonomy keeps this plan's output traceable to existing
   docs. `uv run pytest` is excluded from the sequence-diagram set: it has no interesting runtime
   *sequence* to draw (it's "pytest calls test functions," not a multi-service interaction) — sub
   agent 1 still inventories `make test` in the target catalog for completeness, but no diagram is
   produced for it.
   - **Considered and rejected:** one sequence diagram per individual `Makefile` target (e.g.
     separate diagrams for `qlever-index`/`qlever-up`/`qlever-status`). Rejected — those are
     lifecycle/setup steps for a scenario, not scenarios themselves; they belong as preconditions
     noted *within* the KIF/QLever sequence diagram (a "setup" lifeline or a pre-diagram note), the
     same way `docs/run_book.md` §5a treats them as a prerequisite to §5b/§5c rather than each
     getting its own numbered section.
4. **Format: valid mxGraph XML, openable and editable in draw.io/diagrams.net without any
   conversion step.** Each `.drawio` file is a plain XML document sub agents write directly (no
   image rendering, no PlantUML/Mermaid intermediate) — `<mxfile><diagram><mxGraphModel>...` — so a
   reviewer can open it at https://app.diagrams.net (File → Open) or the VS Code draw.io extension
   and immediately see/edit the real shapes, not a screenshot. One page (`<diagram>` element) per
   file; files are not bundled into a single multi-page `.drawio` because independent scenarios
   should be independently diffable/openable in git and in review, matching the
   one-file-per-concern pattern already used for e.g. `analysis/*.md`.
5. **One shared style guide, authored once, applied by every diagram-producing sub agent, and
   reconciled by the orchestrator afterward.** Sub agents 2-5 run in parallel and never see each
   other's output, so left alone they'd each invent their own box names, colors, and fonts for the
   same components (e.g. one labels a box "pydantic-ai backend," another
   "agents/pydantic_ai_agent.py") — the six diagrams would read as unrelated files rather than one
   family. Two-part fix:
   - Sub agent 1 authors a short style section in `analysis/drawio_scenarios_analysis.md` (per its
     outputs below) fixing, once: the canonical name for every module/service (so all sub agents
     cite the same string), a fill color per component *kind* (CLI entry point, backend
     implementation, external service, data file), the actor/lifeline style for sequence diagrams,
     and base font/stroke settings. Every sub agent (2-5) is required to use this section verbatim
     rather than choosing its own.
   - After sub agents 2-5 finish, the orchestrator opens and reviews all six `diagrams/*.drawio`
     files together against that same style section — checking box/lifeline names match the
     canonical strings, colors match the kind→color mapping, and fonts/stroke widths match — and
     directly edits any diagram that has drifted (a sub agent using a shape's default color, a
     slightly different label for the same module, inconsistent lifeline spacing) so the finished
     set reads as one consistent system, not six independently-styled files. This reconciliation
     pass happens before the orchestrator writes `docs/learning_plan_drawio.md`, and any diagram it
     had to correct is noted there (which file, what was inconsistent) so the record is honest about
     what needed fixing rather than implying every sub agent nailed the style guide unassisted.
6. **Automated verification is XML well-formedness only — style consistency and visual
   correctness are separate, human/orchestrator review steps, not `make diagrams-check`'s job.** The
   `make diagrams-check` target parses every `diagrams/*.drawio` file as XML (`xml.dom.minidom` or
   equivalent) and fails if any is malformed — this catches a corrupted/truncated write, which is
   the realistic failure mode for a sub agent authoring raw XML by hand. It does not and cannot
   check that a diagram is *visually* correct (shapes non-overlapping, labels legible) or styled
   consistently with the others — visual correctness stays a human review step called out
   explicitly in the orchestrator's summary doc rather than silently assumed, while style
   *consistency* against the shared guide is the orchestrator's own reconciliation pass from
   objective 5, done by direct inspection/editing of the files, not by this Makefile target.
7. **Written summary accompanies, not replaces, the diagrams.** `.drawio` files aren't readable in
   a terminal or a plain GitHub diff — so a new `docs/learning_plan_drawio.md` (same format as the
   other `docs/learning_plan_*.md` files) narrates what each diagram shows and why, with the actual
   scenario catalog table, so a reader gets the map even before opening draw.io. This is the same
   "prose companion to a generated artifact" pattern `docs/learning_plan_kif_llm.md` already
   established for the side-by-side answer comparison.

### Non-goals

- No auto-generation pipeline (no script that regenerates `.drawio` files from code on every
  commit) — these are point-in-time, hand-authored diagrams reviewed and committed like any other
  doc, refreshed manually if the architecture changes materially.
- No new runtime behavior, no changes to any `demo*.py`, agent backend, or KIF module — this plan
  is purely additive documentation/diagramming.
- No PNG/SVG export committed alongside the `.drawio` sources — the XML is the source of truth;
  anyone needing an image can export one locally from draw.io. (If the user later wants exported
  images embedded in docs, that's a follow-up, not part of this plan.)
- No new dependency — `diagrams-check`'s XML validation uses Python's stdlib
  (`xml.dom.minidom`), already available via `uv run python`, same as every other `*-check` target.

## Agents

### Orchestrator
- Branch: this work happens on `dev-20260904d-na` (created off latest `main`).
- The orchestrator manages sub agent 1 first (Makefile/scenario inventory *and* the shared style
  guide, per objective 5 — everything else reads its catalog), then sub agents 2-5 in parallel once
  sub agent 1's catalog exists: sub agent 2 (structure/component diagram) and sub agents 3-5
  (sequence diagrams, split by backend family so no single sub agent has to hold the whole repo's
  runtime detail in context at once) are mutually independent.
- **After sub agents 2-5 all finish, the orchestrator runs a style-reconciliation pass before
  writing anything else** (objective 5): read all six `diagrams/*.drawio` files back, check each
  one's component/lifeline names, fill colors, and font/stroke settings against sub agent 1's style
  section, and directly edit (via the same XML editing any sub agent used) any diagram that drifted
  — a wrong label, a default color left unset, inconsistent lifeline spacing versus the others.
  Keep a short running note of what was corrected in which file; that note becomes part of the
  summary doc below rather than being discarded once the fix is made.
- Will summarize the final design as `docs/learning_plan_drawio.md` (new, format matching
  `docs/learning_plan_kif_llm.md`): the scenario catalog table from sub agent 1, one short
  paragraph per diagram describing what it shows and any notable tradeoff/simplification made while
  drawing it, a "how to open" note (draw.io/diagrams.net or the VS Code draw.io extension), and the
  style-reconciliation note from above (which diagrams needed a consistency fix and what it was —
  or an explicit "all six matched the style guide as authored" if none did).
- Will update `docs/learning_plan.md`'s `## See also` section with a pointer to
  `docs/learning_plan_drawio.md` and `diagrams/`, alongside the existing KIF/agents/Neo4j entries —
  no changes to the existing `## Comparing the approaches` table (diagrams are a new *view* of the
  existing backends, not a new backend).
- Will update `Makefile`:
  - Add `diagrams-check` (verifies every `diagrams/*.drawio` file parses as well-formed XML; per
    objective 5), added to the `.PHONY` line alongside the other `*-check` targets.
  - No new server-lifecycle target — diagrams have no runtime process to start/stop.
- Will update `docs/QUICKSTART.md`'s Troubleshooting/See-also area with one line pointing to
  `docs/learning_plan_drawio.md` for readers who want the visual/architectural view before running
  anything, mirroring how it already links out to `learning_plan_agents.md`/`learning_plan_kif_llm.md`
  for deeper context.

### Sub agent 1
- Focused on producing the scenario catalog every other sub agent builds from — reviewing the
  `Makefile` target-by-target and grouping into the major scenarios from objective 3.
- Inputs:
  - `Makefile` (all targets), `pyproject.toml`'s `[project.scripts]`, `docs/run_book.md` (especially
    its "Quick reference: what needs what" table), `docs/QUICKSTART.md`, `.env.example`.
- Outputs:
  - `analysis/drawio_scenarios_analysis.md` covering:
    - A full target-by-target inventory table: target name, what it does, which scenario (if any)
      it's a lifecycle/precondition step for vs. a scenario entry point itself (per objective 3's
      "considered and rejected" note — e.g. `qlever-up`/`qlever-index`/`qlever-status` are
      preconditions of the KIF/QLever scenario, not scenarios on their own).
    - The final list of major scenarios to sequence-diagram (expected: default pydantic-ai run,
      LangGraph run, BeeAI run, KIF/QLever demo, KIF-LLM demo, Neo4j demo — confirm this matches
      `docs/run_book.md`'s table exactly, or note+justify any deviation).
    - For each major scenario: its entry-point command, the `AGENT_BACKEND`/`GRAPH_BACKEND` (or
      equivalent) values in play, every module/file actually exercised (traced from the entry point
      through imports — e.g. `uv run weather-graph` → `demo.py` → `agents/__init__.py:build_agent`
      → the `pydantic_ai` backend → `sparql.py`/`graph_data.py`), and every external
      service/process touched (Ollama always; QLever or Neo4j only for the scenarios that need
      them).
    - A component inventory for the structure diagram: every module/package, every external
      service, and the *kind* of edge between them (in-process call, HTTP, Bolt, subprocess/CLI),
      derived from the same import tracing above so sub agent 2 doesn't have to re-derive it.
    - **The shared style guide (objective 5)**, as its own clearly-headed section so sub agents 2-5
      can copy it verbatim rather than paraphrase: a canonical name string for every module/service
      in the inventory above (one name, used everywhere — not "pydantic-ai backend" in one diagram
      and "agents/pydantic_ai_agent.py" in another), a fill-color assignment per component *kind*
      (CLI entry point, backend implementation, external service, data/model file), the
      actor/lifeline box style and spacing convention to use in every sequence diagram, and base
      font family/size/stroke-width values. This section is what the orchestrator's later
      reconciliation pass checks every diagram against, so it needs to be unambiguous enough to
      check mechanically (exact hex colors, not "a blue-ish color").

### Sub agent 2
- Focused on the single structural component diagram — the static "what talks to what" picture.
- Inputs: `analysis/drawio_scenarios_analysis.md` (component inventory + edge kinds), the actual
  source layout (`src/weather_graph/`) to confirm module boundaries match what sub agent 1 traced.
- Outputs: `diagrams/component_diagram.drawio` — one page, per objective 4's format:
  - Boxes: the four CLI entry points (`demo.py`, `demo_kif.py`, `demo_kif_llm.py`,
    `demo_neo4j.py`), the `agents/` package with its three backend implementations
    (pydantic-ai/LangGraph/BeeAI) shown as a dispatch fan-out from `AGENT_BACKEND`, `graph_data.py`
    (in-memory) and `sparql.py` (QLever-backed) as the two `GRAPH_BACKEND` implementations, the
    `kif/` package (`kif.py` + `mapping.py` vs. `llm_store.py` + `wikidata_mapping.py` + `_vendor/`,
    sharing `base.py`'s `Protocol`), the `neo4j/` package, and the three external services (Ollama,
    QLever, Neo4j) as distinctly-styled boxes (e.g. a different fill) so "external service" reads
    at a glance.
  - Edges labeled by connection kind (import, HTTP/SPARQL, Bolt, subprocess/CLI via `qlever`/
    `neo4j-cli`), matching sub agent 1's inventory.
  - A legend/key box on the same page explaining box-color/edge-style meaning, since this is the
    one diagram meant to be read without a scenario-specific narrative alongside it.

### Sub agents 3-5 (parallel, one per backend family)
Each produces its assigned scenarios' `.drawio` sequence diagrams, per objective 2/4: an actor
lifeline (developer/terminal), the `make`/`uv run` command as the trigger, then lifelines for each
module and external service the scenario touches in the order sub agent 1 traced, ending at the
printed answer(s). Each diagram notes its scenario's lifecycle preconditions (per objective 3) as
an initial note/lifeline annotation rather than a separate diagram.

- **Sub agent 3 — agent-backend scenarios.** Inputs: `analysis/drawio_scenarios_analysis.md`,
  `analysis/weather_graph_agent_analysis.md`, `analysis/pydantic_ai_analysis.md`,
  `analysis/langgraph_analysis.md`, `docs/learning_plan_agents.md`. Outputs:
  - `diagrams/sequence_run_pydantic_ai.drawio` — `uv run weather-graph` (default `AGENT_BACKEND`),
    including the documented output-retry flake from `docs/run_book.md` §2 as an optional/alt
    fragment (retry loop up to 3 attempts), since it's a real, observed part of this sequence, not
    hypothetical.
  - `diagrams/sequence_run_langgraph.drawio` — `make run-langgraph`.
  - `diagrams/sequence_run_beeai.drawio` — `make run-beeai`, including the `beeai-check`
    precondition and noting Mellea's `format=<schema>` constrained-decoding call to Ollama
    (documented hang risk per `docs/QUICKSTART.md`'s Troubleshooting) as an annotation.

- **Sub agent 4 — KIF scenarios.** Inputs: `analysis/drawio_scenarios_analysis.md`,
  `analysis/kif_backend_analysis.md`, `analysis/kif_llm_analysis.md`, `docs/learning_plan_kif.md`,
  `docs/learning_plan_kif_llm.md`, `docs/run_book.md` §5. Outputs:
  - `diagrams/sequence_kif_sparql.drawio` — `uv run weather-graph-kif`, with the `qlever-index`/
    `qlever-up` precondition noted, through `kif.py`/`mapping.py` to the QLever SPARQL endpoint,
    fixed answers, no LLM lifeline at all (per `docs/run_book.md` §5b, this path never touches
    Ollama).
  - `diagrams/sequence_kif_llm.drawio` — `uv run weather-graph-kif-llm`, showing **both** lifelines
    side by side per question (the `[SPARQL/QLever]` and `[LLM Store]` columns from
    `docs/run_book.md` §5c) since that side-by-side comparison is the scenario's entire point per
    `plans/PLAN_KIF_LLM.md` objective 5 — collapsing it to one lifeline would misrepresent the
    scenario.

- **Sub agent 5 — Neo4j scenario.** Inputs: `analysis/drawio_scenarios_analysis.md`,
  `analysis/neo4j_analysis.md`, `docs/learning_plan_neo4j.md`. Outputs:
  - `diagrams/sequence_neo4j.drawio` — `uv run weather-graph-neo4j`, with `neo4j-up`/`neo4j-migrate`
    preconditions noted, through the `neo4j/` package to Neo4j over Bolt, fixed answers, no LLM
    lifeline (same "no LLM in this path" shape as the KIF/QLever scenario — confirm against
    `analysis/neo4j_analysis.md` before assuming, since sub agent 1's catalog is the source of
    truth here, not this plan's guess).

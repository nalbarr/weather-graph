# PLAN_EXPORT_PNG.md

## Role
You are a systems architect and want to make the seven `diagrams/*.drawio` files produced by
`plans/PLAN_DRAWIO.md` viewable without opening draw.io/diagrams.net first — exporting each to a
`.png` via the locally-installed draw.io desktop CLI, embedding those images in
`docs/learning_plan_drawio.md` so its overviews render inline, and wiring a `Makefile` dependency
check + export target so this is a repeatable `make` step, not a one-off manual export.

## Objectives

Decisions locked in before implementation (resolved via a real, live CLI test on this machine —
see each subsection for what was actually confirmed, not assumed):

1. **Tool: the locally-installed draw.io desktop app's CLI export mode — confirmed real, not
   assumed.** `/Applications/draw.io.app/Contents/MacOS/draw.io --help` was run on this machine and
   confirms a genuine CLI (`draw.io 31.4.4`) with `-x/--export`, `-f/--format <png|svg|pdf|jpg|...>`,
   `-o/--output <path>`, `-b/--border <n>`, `-t/--transparent`, `--theme <dark|light|auto>`,
   `--size <diagram|page>` (crop-to-content vs. full page), `-s/--scale`, `--width`/`--height`. A
   real test export was run end to end: `--export --format png --border 10 --output
   /tmp/test_component.png diagrams/component_diagram.drawio` completed in 3.4s, exit 0, and
   produced a valid 337KB PNG — confirmed by actually opening it, not just checking the exit code.
   - **Considered and rejected:** a Docker-based headless exporter (e.g. `rlespinasse/drawio-export`)
     or a Node/Puppeteer-based converter. Rejected — the user already has draw.io desktop installed
     locally and its CLI works correctly on the first real try; adding a Docker or Node dependency
     for a redundant capability isn't justified. Revisit only if CI-based (headless, no local
     desktop app) export is ever needed — see Non-goals.
2. **Real finding from that test export, recorded here rather than smoothed over: several edge
   labels in `component_diagram.drawio` visibly overlap/collide** where multiple edges converge
   (near `agents/__init__.py`'s three-way fan-out, and around the
   `neo4j/connection.py`→`data/neo4j/weather.cypher` reference edge and its neighboring HTTP/Bolt
   labels) — legible in isolation, crowded in those spots. Confirmed this is a content/layout
   density issue in the `.drawio` source, not an export-flag problem, by re-exporting with
   `--border 10` (no change to internal spacing). This plan does not re-layout that file (see
   Non-goals) — but it's exactly the kind of thing objective 5's human verification step exists to
   catch, and it already did, once, before any doc pointed at the image. Whoever reviews the
   verification PNG should expect to see this and can decide separately whether it's worth a
   `component_diagram.drawio` layout pass.
3. **This plan reverses `plans/PLAN_DRAWIO.md`'s stated non-goal** — "No PNG/SVG export committed
   alongside the `.drawio` sources... (If the user later wants exported images embedded in docs,
   that's a follow-up, not part of this plan.)" — stated explicitly here so a future reader of both
   plans sees the change as deliberate, not a contradiction.
4. **Output naming/location: same basename, `.png` extension, same `diagrams/` directory.**
   `diagrams/component_diagram.drawio` → `diagrams/component_diagram.png`, etc. — keeps the pairing
   obvious in a directory listing and in doc links; no new `diagrams/png/` subdirectory invented for
   a 7-file set.
5. **Verification: a two-tier check — a human checkpoint on one file, then an orchestrator visual
   pass over all seven — before any doc links to the output.** After the `Makefile` targets are
   wired and `make diagrams-export` is run once:
   - **Tier 1 (human):** send `diagrams/component_diagram.png` — chosen because it's the densest
     diagram and (per objective 2) the one already known to show a real problem — to the user via
     `SendUserFile`, and wait for their confirmation before proceeding. This is the fast, concrete
     "did the export pipeline actually work" check (corrupt file, wrong CLI flags, wrong working
     directory), the same way objective 1's live test already confirmed it once.
   - **Tier 2 (orchestrator):** the component diagram passing tier 1 does not imply the other six
     sequence diagrams are clean — they were never test-exported or viewed, and objective 2 already
     shows this exact export step can surface a real, previously-invisible layout defect. So before
     embedding any of the six sequence-diagram PNGs into `docs/learning_plan_drawio.md`, open each
     one directly (`Read`, the same way the component diagram's test export was inspected while
     writing this plan) and check for the same class of problem — overlapping/collided text,
     a lifeline or box cut off by the crop, an illegibly small label after the `--width 1600` scale
     from objective 7. Note any issue found per-file in the summary this plan's implementation
     produces, the same honest style `plans/PLAN_DRAWIO.md`'s reconciliation pass used — "all six
     matched" or "these needed a fix," not silently assumed clean.
6. **Dependency check target: `drawio-cli-check`, mirroring the existing `qlever-cli-check`/
   `neo4j-cli-check` pattern exactly** (`command -v` first, a documented install hint on failure).
   Because draw.io desktop doesn't put a `drawio` binary on `PATH` by default on macOS (there's no
   Homebrew-managed symlink the way `qlever`/`neo4j-cli` are `uv tool install`s), the check tries
   `command -v drawio` first (covers a Linux install or a manually-symlinked macOS one), then falls
   back to the known macOS app-bundle path
   (`/Applications/draw.io.app/Contents/MacOS/draw.io`) confirmed working in objective 1, and only
   fails if neither exists — with an install hint (`brew install --cask drawio`, or download from
   https://github.com/jgraph/drawio-desktop/releases). Documented as an **optional, export-only**
   dependency: never required to view or edit the `.drawio` XML sources themselves (a browser at
   app.diagrams.net or the VS Code draw.io extension is enough for that, per
   `docs/learning_plan_drawio.md`'s existing "How to open" section) — only `make diagrams-export`
   needs it.
7. **Export target: `diagrams-export`**, depending on `drawio-cli-check`, looping over
   `diagrams/*.drawio` the same way the existing `diagrams-check` target loops (bash array +
   `nullglob`, one subprocess call per file, a final success count) — not a single batched CLI
   invocation over a folder, so one bad file's failure is reported by name rather than aborting
   the whole batch silently.
   - **Flags, pinned identically for all seven files so the embedded set reads as one consistent
     family** (the same reasoning `plans/PLAN_DRAWIO.md` objective 5 applied to the `.drawio`
     sources' own style guide, extended here to the export step): `-x --format png --border 10
     --width 1600` (no `--transparent`, so images read correctly pasted into a white-background
     doc; no `--theme` override, default `auto` is fine for a static PNG). `--size diagram`
     (the CLI's own default) crops each PNG tightly to its content first, so the seven source
     diagrams — one dense component diagram, six sequence diagrams of varying length — would
     otherwise land at wildly different pixel dimensions when embedded side by side; a fixed
     `--width 1600` (the `--help` text says it "fits the generated image... into the specified
     width, preserves aspect ratio" — whether a diagram narrower than 1600px at its native size is
     scaled *up* to fill that width, or left smaller, is not yet confirmed and should be checked
     against the real output during implementation, not assumed) and a fixed 10px border give
     every embedded image the same target width and a small consistent margin instead of some
     images touching their frame edge and others not.
8. **Docs: embed, not just link, in `docs/learning_plan_drawio.md`.** Per the user's explicit ask
   ("learning plan summary should be able to link to .png files for overviews"), each diagram's
   existing description in that doc gains a markdown image embed
   (`![<name>](../diagrams/<name>.png)`) directly under its prose, with a one-line caption noting
   the `.drawio` is the editable source of truth and the `.png` is a generated preview that can go
   stale — regenerate via `make diagrams-export` after any `.drawio` edit; there is no
   auto-regeneration hook (consistent with `plans/PLAN_DRAWIO.md`'s "no auto-generation pipeline"
   non-goal, extended here to the PNGs). `docs/QUICKSTART.md`'s existing one-line pointer to
   `learning_plan_drawio.md` gets a small addition noting PNG previews are now available there.

### Non-goals

- No CI/automated regeneration on commit or on a schedule — `make diagrams-export` is a manual,
  human-run step, same trust model as `diagrams-check`.
- No Docker- or Node/Puppeteer-based headless exporter (objective 1) — depends on the user's local
  draw.io desktop install; not expected to work unmodified on a headless CI runner (Electron-based
  CLI, needs a display) — if CI-based export is wanted later, that's a new plan, not this one.
- No SVG/PDF/JPG export in this pass — PNG only, per the user's explicit ask. The CLI supports the
  others (confirmed in objective 1's `--help` output) if a future plan wants them.
- No re-layout or content edit to any `.drawio` file, including the overlapping-labels issue found
  in objective 2 — flagged for a human decision, not silently fixed here.
- No change to the existing `diagrams-check` target — it still only validates `.drawio` XML
  well-formedness and is not extended to validate the generated `.png` files (that's what
  objective 5's human verification step is for; a `.png` isn't XML, there's nothing structural to
  parse-check).

## Agents

### Orchestrator (no sub agents)
This is a small, inherently sequential task — one CLI to wire, one export loop, one human
checkpoint, then doc updates that depend on that checkpoint passing — with no independent chunks
that would benefit from parallel sub agents the way `plans/PLAN_DRAWIO.md`'s six diagrams did. The
orchestrator does all of it directly:

1. Add `drawio-cli-check` to the `Makefile` (objective 6), added to the `.PHONY` line.
2. Add `diagrams-export` to the `Makefile` (objective 7), depending on `drawio-cli-check`, also
   added to `.PHONY`.
3. Run `make diagrams-export` once, locally, to actually generate all seven `.png` files (not a
   hypothetical — confirm the real exit code and file sizes, the same way objective 1's standalone
   test was verified before being written into this plan).
4. **Tier-1 verification checkpoint (objective 5):** send `diagrams/component_diagram.png` to the
   user via `SendUserFile` and wait for their response before proceeding to step 5. If they flag a
   problem (a bad export, or the known overlapping-labels issue from objective 2 turning out worse
   than expected), stop and resolve that first rather than embedding a known-bad image in the docs.
5. **Tier-2 verification pass (objective 5):** once tier 1 is confirmed, open each of the remaining
   six sequence-diagram `.png` files directly (`Read`) and check for overlapping/collided text, a
   lifeline or box cut off by the crop, or illegible labels post-scale. Record the outcome per file
   (clean, or what was wrong) — this becomes a short section in the implementation summary, not a
   silent assumption that "component diagram was fine, so the rest must be too."
6. Once both tiers pass (or any found issue is resolved): update `docs/learning_plan_drawio.md`
   (objective 8) — one embedded image per diagram, under its existing description, plus the "source
   of truth vs. generated preview, can go stale" caption once near the top of the doc rather than
   repeated seven times.
7. Update `docs/QUICKSTART.md`'s existing pointer line to `learning_plan_drawio.md` (small addition
   noting PNG previews).
8. Commit the seven new `.png` files alongside the `.drawio` sources they're generated from (per
   objective 3's reversal of the earlier non-goal) — check each file's size is reasonable for a
   diagram export (low hundreds of KB, per objective 1's real 337KB sample) before staging, same
   general size-hygiene as any binary asset added to a git repo.

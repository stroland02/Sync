# Sync's own console, 2026-08-07

Seven of the nine specification levels, captured from the running console so the substrate rebuild
can be compared against the reference material in `docs/superpowers/references/direction/` rather
than argued about from memory.

**These are ours.** `references/direction/` is the owner's captures of other products;
`references/screenshots/` is the fenced competitor set that `.claude/rules/interface-originality.md`
governs. This directory is the thing those exist to be measured against, and it is the only one of
the three that may be regenerated at will.

## Capture conditions, because a screenshot without them is not evidence

- **Commit `25a4a10`** — every substrate level port through `M7-W180`, on `console-identity` and
  `main`, which were identical at capture time.
- **1920×889, the real browser window.** No CDP device-metrics override was applied at any point.
  That matters: an override left from 2026-08-05 made every screenshot the owner took show a
  windowed console for most of a day, and `.claude/rules/console-dev-loop.md` carries the rule that
  came out of it.
- **Full page**, not viewport — so a screen's whole vertical extent is visible, which is what the
  prose-weight question below is about.
- Served from the coordinator's worktree on `localhost:5173` with the API on 8789, against
  `scripts/seed_console.py`'s fixture: four repositories, seven vendors, one of them synthetic at
  `--scale`, and four checkpoint threads.

## What is here

| File | Level | Route |
|---|---|---|
| `01-fleet.png` | Fleet | `/` |
| `02-detectors.png` | Errors & Incidents | `/detectors` |
| `03-codebase.png` | Codebase | `/repositories/seed-console-repo-a` |
| `04-api-service.png` | API Service | `/vendors/seed-console-stripe` |
| `05-finding.png` | Finding | `/findings/9f176dea…` |
| `06-workflow.png` | Solution Workflow | `/findings/9f176dea…/workflow` |
| `07-binding-surface.png` | Binding surface | `/bindings/vendors/seed-console-stripe/operations/PostCharges` |

Two levels are not here: Signals and Pull Request. Both need a subject the fixture does not carry a
convenient instance of, and inventing one would make the capture unrepresentative.

## Two composition gaps these make visible, neither of them a correctness problem

Recorded here rather than filed, because `M7-W182` — the fidelity pass — was already open against
the measured gaps when these were taken, and a duplicate entry is worth less than a pointer.

- **Fleet carries more prose than data.** The *"What this screen cannot tell you"* panel runs four
  paragraphs down the right rail, and the vendor panel spends three before its table. Every one of
  those sentences is protected and none may be deleted — but the honesty-sentence guard is not
  file-pinned precisely so they can be **re-placed**. As drawn, the explanatory text out-weighs the
  fact tiles that should be the focal point.
- **The fact-tile row leaves roughly a third of the width empty** at 1920: four tiles, then nothing
  to the right of them.

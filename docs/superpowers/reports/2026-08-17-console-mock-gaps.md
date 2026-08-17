# Mock-gap baseline — the nine routes measured against the mock stills

**2026-08-17.** This is mock-to-build Task 1, run five days late as Task 3 of
`2026-08-17-console-mock-parity`. No product code changed. It measures the console as built today
against `docs/console-mock/screens/` and records what Phase 2–4 tasks will be checked against, and
what the closing walk (Task 15) will be compared to.

**A note on the mock's fixtures, stated once rather than per row below:** `acme/payments-api` and
pull request `#4127` are the mock's own invented subjects — `docs/console-mock/README.md` says so
directly ("several of its facts are invented fixtures... Read a number here as a layout weight,
never as a measurement"). Nothing in this report treats them as data. Every number attributed to the
*built* console below came from the seeded fixture actually running — repository
`seed-console-repo-a`, vendor `seed-console-stripe`, operation `PostCharges`, finding
`9f176dea35907f95beb29553e574a037` (outcome `opened`, pull request `#101` on branch
`sync/fix-post-charges-param`) — never from the mock's invented ones.

## How this was run

Postgres was already up (`sync-postgres-1`, shared across worktrees, healthy). Port 8787 was held by
a foreign process answering `Internal Server Error` — the zombie-process failure mode
`console-dev-loop.md` describes — so the console's own API ran on 8788 instead
(`SYNC_API_PORT=8788`, `SYNC_API_RELOAD=true`, `SYNC_GRAPH_DSN=postgresql://sync:sync@localhost:5433/sync`),
with the dev server pointed at it via `SYNC_API_ORIGIN` rather than editing `vite.config.ts`. The
console ran on the worker port the brief specified, `5199 --strictPort`. `scripts/seed_console.py`
was run once against that DSN (owned by another session; used, not edited) and produced 6 call
sites, 2 vendor changes, 4 findings, 4 checkpointer threads across 2 repositories and 2 vendors —
merged with one pre-existing repository (`r1`) already in the graph.

The automation browser was set to `1440×900`, `deviceScaleFactor: 1` — the mock's own declared
capture condition — and the brief's snippet was evaluated verbatim in the page for each route. The
viewport override was cleared and both servers were stopped before this report was written; the full
per-route raw output, the process-tree kill evidence, and the socket-free confirmation are in
`.superpowers/sdd/2026-08-17-console-mock-parity/task-3-report.md`.

## The nine routes, measured

| # | Route (subject used) | Level | Mock still | `typeMax`/`typeMin` | `typeRange` (bar ≥ 3.4) | `sideBySideRegions` (bar ≥ 1) | `framePx` |
|---|---|---|---|---|---|---|---|
| 1 | `/` | Fleet | `01-fleet.png` | 28 / 9 | **3.11 — below bar** | 15 | 40 |
| 2 | `/repositories/seed-console-repo-a` | Codebase | `02-codebase.png` | 46 / 12 | 3.83 | 10 | 40 |
| 3 | `/vendors/seed-console-stripe` | API Services | `03-vendor.png` | 46 / 12 | 3.83 | 10 | 40 |
| 4 | `/repositories/seed-console-repo-a/observed` | Signals | `04-signals.png` | 46 / 12 | 3.83 | 4 | 40 |
| 5 | `/bindings/vendors/seed-console-stripe/operations/PostCharges` | Binding surface | `05-binding-surface.png` | 46 / 12 | 3.83 | 7 | 40 |
| 6 | `/detectors` | Errors & Incidents | `09-detectors.png` | 46 / 12 | 3.83 | 5 | 40 |
| 7 | `/findings/9f176dea35907f95beb29553e574a037` | Finding | `06-finding.png` | 46 / 12 | 3.83 | 5 | 40 |
| 8 | `/findings/9f176dea…/workflow` | Solution Workflow | `07-workflow.png` | 46 / 12 | 3.83 | 21 | 40 |
| 9 | `/findings/9f176dea…/workflow/pull-request` | Pull Request | `08-pull-request.png` | 46 / 12 | 3.83 | 8 | 40 |

`framePx` is flat at 40 on every route — the console frame itself is consistent, and that consistency
is not in question anywhere below. `typeRange` clears the 3.4 bar on eight of nine routes at an
identical 3.83, which is a single oversized page title (`typeMax` 46) sitting over a single small
label (`typeMin` 12) on every detail screen — worth reading as "one route failed to earn the ratio it
reports" rather than "eight routes match the mock's type scale," see below.

## Per-route verdicts

**1 — Fleet (`/`), mock `01-fleet.png`. Verdict: adapt.**
Two deltas, not one. First, `typeRange` genuinely misses the bar (3.11 against 3.4) — this route's
type scale is flatter than the mock's own Fleet screen, which is the opposite direction of the
"oversized title" problem every other route has. Second, and larger: the mock's Fleet grain is one
row per *vendor change × repository set*, expandable to call sites — `docs/console-mock/README.md`
calls this out by name as "a product decision the mock makes on screen," citing
`plans/2026-08-08-console-mock-to-build.md` Decision 1 as where it gets ruled on. The built `/`
route renders a repository directory instead (`Monitored Codebases` cards, `Open findings by vendor`)
— a different grain entirely, not a restyling of the same one. This report does not rule on Decision
1; it records that the built route has not adopted it and that the type-scale bar is separately
missed on this specific screen.

**2 — Codebase (`/repositories/seed-console-repo-a`), mock `02-codebase.png`. Verdict: adapt.**
The mock leads with a four-tile metric row (`FILES INDEXED`, `VENDOR CLIENTS`, `OPERATIONS BOUND`,
`DIRECTORIES SKIPPED`) before its two side-by-side panels. The built screen has no tile row; it
spends the equivalent vertical space on a single oversized `<h1>` (the repository id, at `typeMax`)
above the same two-panel structure. Adopt the tile row — "a fact rendered as a tile" is an explicitly
permitted convention, not a copy of the mock's screen — and refuse the oversized single-headline
treatment, which reports information density the mock earns from four tiles instead of one line.

**3 — Vendor (`/vendors/seed-console-stripe`), mock `03-vendor.png`. Verdict: adapt.**
Structurally closer: both put two panels side by side above a full table. The mock's right panel
(`Where it was read from`) is grouped by evidence source with its own sub-heading per source
(deprecations page, pinned spec, watched traffic); the built right panel is a flat key-value list
covering similar facts without that grouping. Adopt the per-source grouping; the oversized headline
recurs here too.

**4 — Signals (`/repositories/seed-console-repo-a/observed`), mock `04-signals.png`. Verdict: adopt.**
This is the sharpest structural miss of the nine. The mock renders the three signal roles — Vendor,
Signal source, Human surface — as three cards in one row, genuinely side by side
(`sideBySideRegions` reads far higher on the still than the built page's measured 4). The built page
collapses the same three roles into stacked prose paragraphs in a two-column layout; the tri-column
role comparison is gone, not restyled. There is no honesty-rule conflict in adopting it — the
three-role split is Sync's own vocabulary (per `console-mock/README.md`, "the vocabulary is ours,
verbatim"), and a card grid comparing three roles is squarely the "fact rendered as a tile" /
side-by-side convention the interface-originality rule permits taking from the form of a control
plane. Recommend adopting this layout in a later phase task.

**5 — Binding surface, mock `05-binding-surface.png`. Verdict: adapt.**
Same tile-row gap as Codebase: the mock leads with four tiles (`CALL SITES`, `BINDING RUNG`,
`DETECTOR`, `VENDOR CHANGE`); the built screen covers the same four facts in an eight-row key-value
table instead. Adopt the tile row for the headline facts; the table below it already carries
comparable density to the mock's own table and needs no change.

**6 — Detectors (`/detectors`), mock `09-detectors.png`. Verdict: refuse, and flagged as a concern
below.** The mock's per-detector rung breakdown is five grey, uncoloured horizontal bars — the rung
carries no colour anywhere on this screen, consistent with its own caption ("a rung is a class of
evidence, not a position on a good-to-bad scale, so no colour is assigned to one"). The built screen
renders the same breakdown as colour-coded stacked bars (green/orange/blue/pink by rung, with a
legend). `.claude/rules/console-surface.md` states "the provenance rung stays monochrome at both
levels and is never a hideable column." This built pattern should not be adopted as-is; see Concerns.

**7 — Finding, mock `06-finding.png`. Verdict: adapt.**
Reasonably close in structure — both are a two-column layout with a key-value block and stacked
cards — but the built screen still carries the oversized single-line headline seen on routes 2, 3, 5
and 7–9. No content gap found beyond that; the finding's honesty sentences (rung, attribution,
standing) are all present.

**8 — Solution workflow, mock `07-workflow.png`. Verdict: adapt.**
The mock fits all eight nodes plus a full activity feed in the 900px viewport via a compact node
list and a dense event table. The built screen expands every node into its own tall card; only two
of eight nodes (`locate`, `prepare`) are visible without scrolling in the same viewport. The
underlying content is not missing — each node's evidence is present, and the "Reasoning & Strategy"
detail is already correctly gated behind a disclosure rather than always shown — so this is a density
gap, not an honesty gap. Adopt a more compact collapsed-node presentation; do not touch the
disclosure that already exists correctly.

**9 — Pull request, mock `08-pull-request.png`. Verdict: adapt.**
The mock shows the actual diff hunks and an `Approve` / `Request changes` / `Abandon` action bar
directly on this screen. The built screen, captured at the same viewport-not-fullpage convention the
mock itself uses, shows only metadata and evidence-summary panels above the fold — no diff, no
action controls visible. This report does not claim the diff view is entirely absent from the route;
it states only what rendered inside the captured viewport, which is what the mock's own capture
methodology also does. Adopt showing the diff and the review actions above the fold if they are not
already reachable by scrolling below what was captured here.

## Concerns

**The Detectors screen's colour-coded rung bars are a likely violation of the monochrome-rung rule,
not a styling choice to leave alone.** `CLAUDE.md`'s console section and `console-surface.md` both
state the provenance rung must never carry a colour channel; this is the one place in the nine routes
where the built console appears to do exactly that. This report does not fix it — Task 3 is
measurement-only — but it should be the first thing a later phase task checks, ahead of any
type-scale or tile-row work above.

**The oversized single-headline pattern recurs on seven of nine detail routes** (all but Fleet and
Signals, which have their own distinct problems). It is internally consistent — `typeMax` 46 on every
one of those seven — which is why the `typeRange` bar reads as passed on all of them; a single
recurring oversized title against a small label is not the same claim as "the type scale matches the
mock's own range," and a later task should look at whether 46px is the intended display step from
`DESIGN.md` reused correctly, or a default that has not been designed at all.

## Evidence

Full raw per-route snippet output, the subject lookups against the running API, server start/stop
logs, the process-tree kill chain, and the socket-free confirmation are recorded in
`.superpowers/sdd/2026-08-17-console-mock-parity/task-3-report.md`.

---

## Task 15: the closing measured walk

**2026-08-17, later the same day.** Fourteen tasks of `2026-08-17-console-mock-parity.md` landed
between the baseline above and this walk. This repeats Task 3's method exactly — viewport
1440×900, `deviceScaleFactor: 1`, the same `getComputedStyle` snippet, evaluated verbatim over the
same nine routes plus `/settings` — against a freshly seeded database (the fixture was re-seeded
for this walk; `seed-console-repo-a`, `seed-console-stripe`, `PostCharges`, finding
`9f176dea35907f95beb29553e574a037` all reappear because `scripts/seed_console.py` is deterministic
over the same tag, not because the same rows survived). No product code changed in this task. Full
per-route raw output, subjects read off the running API, server start/stop evidence and the
viewport-cleared confirmation are in
`.superpowers/sdd/2026-08-17-console-mock-parity/task-15-report.md`.

One environmental difference from the baseline worth stating before the numbers: this run's
database held no pre-existing `r1` repository, so `/api/repositories` returns exactly the two
seeded repositories rather than three. It does not change any figure below — no route measured
here reads `r1`.

### The closing table

| # | Route | Mock still | Baseline `typeMax`/`typeMin` → closing | Baseline `typeRange` → closing (bar ≥ 3.4) | Baseline `sideBySideRegions` → closing (bar ≥ 1) | `framePx` |
|---|---|---|---|---|---|---|
| 1 | `/` (Fleet) | `01-fleet.png` | 28/9 → 46/9 | 3.11 (below bar) → **5.11 (clears)** | 15 → 10 | 40 → 40 |
| 2 | `/repositories/seed-console-repo-a` | `02-codebase.png` | 46/12 → 46/12 | 3.83 → 3.83 | 10 → 12 | 40 → 40 |
| 3 | `/vendors/seed-console-stripe` | `03-vendor.png` | 46/12 → 46/12 | 3.83 → 3.83 | 10 → 12 | 40 → 40 |
| 4 | `/repositories/seed-console-repo-a/observed` | `04-signals.png` | 46/12 → 46/12 | 3.83 → 3.83 | 4 → 4 (unchanged) | 40 → 40 |
| 5 | `/bindings/vendors/seed-console-stripe/operations/PostCharges` | `05-binding-surface.png` | 46/12 → 46/12 | 3.83 → 3.83 | 7 → 7 (unchanged) | 40 → 40 |
| 6 | `/detectors` | `09-detectors.png` | 46/12 → 46/12 | 3.83 → 3.83 | 5 → 5 (unchanged) | 40 → 40 |
| 7 | `/findings/9f176dea…` | `06-finding.png` | 46/12 → 46/12 | 3.83 → 3.83 | 5 → 5 (unchanged) | 40 → 40 |
| 8 | `/findings/9f176dea…/workflow` | `07-workflow.png` | 46/12 → 46/12 | 3.83 → 3.83 | 21 → **25** | 40 → 40 |
| 9 | `/findings/9f176dea…/workflow/pull-request` | `08-pull-request.png` | 46/12 → 46/12 | 3.83 → 3.83 | 8 → 8 (unchanged) | 40 → 40 |
| 10 | `/settings` (not a `GRAPH_LEVELS` member; measured for the first time) | `10-settings.png` | — → 46/12 | — → 3.83 | — → **0 (below bar)** | — → 40 |

`typeRange` now clears the 3.4 bar on all ten routes, including Fleet, which was the one baseline
failure — Fleet's `typeMax` rose from 28 to 46 (the display step every other route already carried)
while `typeMin` held at 9, so the ratio moved from 3.11 to 5.11. `sideBySideRegions` clears the ≥1
bar on all nine `GRAPH_LEVELS` routes; `/settings` measures 0, addressed under its own verdict
below since it is explicitly not a level (`web/src/lib/routes.ts`: "`Settings` is deliberately
absent... it is not a member of this union"). Raw-utility count: zero — the baseline file
(`tests/console_raw_utilities_baseline.txt`) is empty and `tests/test_console_raw_utilities.py`
passes, so nothing here regressed.

### Per-route verdicts, against the baseline's own verdict

**1 — Fleet. Baseline: adapt (type-scale miss + grain question). Closing: adapt, narrower.**
The type-scale miss is resolved: the route now leads with a `FleetFacts` tile row — Open findings,
Runs, Repositories indexed, Repair attempts — reading `/api/overview`, `/api/runs`,
`/api/repositories` and `/api/corpus` respectively (verified field-by-field against the running
API in the Gate 3 report below), which is what pushed `typeMax` to the shared 46px display step.
Below it: `Monitored Codebases` cards, an `Open findings by vendor` panel, and a `Health score
policy` tile stating in words why no composite figure exists. **The mock's Decision-1 grain
question — a change-unit table instead of a repository directory — is still not adopted**; the
route renders `Monitored Codebases` cards exactly as the baseline described. This report does not
rule on Decision 1, same as the baseline; it records that the type-scale half of the Fleet gap is
closed and the grain half is not.

**2 — Codebase. Baseline: adapt (missing tile row). Closing: unchanged — still open.**
Still a two-panel `Open findings` / `Index coverage` layout under an oversized `<h1>`, not the
mock's four-tile row (`FILES INDEXED`, `VENDOR CLIENTS`, `OPERATIONS BOUND`, `DIRECTORIES
SKIPPED`). `sideBySideRegions` rose 10 → 12, but that is more side-by-side content inside the
existing two panels, not the tile row the baseline named. Gap open.

**3 — Vendor. Baseline: adapt (flat list vs. grouped-by-source). Closing: unchanged — still open.**
The right panel is still a flat `VENDOR` / `REPOSITORY SCOPE` / `FINDINGS COUNTED OVER` /
`CHANGES COUNTED OVER` list, confirmed against `03-vendor.png` again in this walk — the mock groups
the same kind of fact under three named sources (`Deprecations page`, `Pinned specification`,
`Watched traffic`) and the built page does not. Gap open.

**4 — Signals. Baseline: adopt (tri-column card row recommended). Closing: unchanged — still open.**
`sideBySideRegions` is identical to the baseline, 4, and the screenshot shows the same stacked
two-column prose rather than a Vendor / Signal source / Human surface card row. Gap open; no task
in this plan's list picked it up.

**5 — Binding surface. Baseline: adapt (missing tile row). Closing: unchanged — still open.**
`sideBySideRegions` identical to baseline, 7. Still an eight-row key-value table (`VENDOR`,
`OPERATION`, `REPOSITORY SCOPE`, `CALL SITES BOUND`, `REPOSITORIES`, `VENDOR CHANGES`, `BINDING
RUNG`) rather than the mock's four-tile row. Gap open.

**6 — Detectors. Baseline: refuse, flagged as a likely monochrome-rung violation. Closing: refuse
stands, and the flag is resolved rather than fixed.** The rung-composition bars are still
colour-coded live (green/blue/orange stacked segments with a legend), confirmed again in this
walk against `09-detectors.png`'s uncoloured grey bars. Task 9 of this plan inspected the
baseline's flag directly and refused the fix: both fleet-facing rung charts are stacked bars where
segment length carries the open-finding count and hue carries which rung a segment is, and the
corpus chart's single y-category renders with its axis label suppressed — hue is the only channel
naming a segment there, but the detectors chart carries a legend, axis labels and inline counts
alongside the colour, so colour is never the only channel identifying a rung, which is what
`console-surface.md`'s rule actually forbids. The visual delta against the mock's monochrome
still-image is real and unresolved; the rule violation the baseline suspected is not. Both
statements are recorded rather than one standing in for the other.

**7 — Finding. Baseline: adapt (oversized headline, otherwise close). Closing: unchanged — minor,
still open.** Same two-column key-value-plus-cards structure, same 46px `<h1>`. No content gap.

**8 — Solution workflow. Baseline: adapt (every node expanded into a tall card; only 2 of 8 nodes
visible). Closing: adopt (composition), adapt (density) — substantially resolved.**
`sideBySideRegions` rose 21 → 25. The route now renders the mock's two-pane shape directly: a left
`Node by node` panel listing all eight nodes as compact one-line rows (checkmark, name, standing,
timestamp) each with a collapsed "How this node works" disclosure, and a right `Activity` panel
holding a chronological event log assembled from the checkpoint. This is
`M14-W274`'s stated change ("the workflow route takes the mock's two-pane trajectory shape"),
confirmed live rather than taken from the ledger alone. One gap remains: a static, always-visible
opening entry ("What arrived") precedes the node list and is not in the mock, and its three
paragraphs of prose are tall enough that not every one of the eight nodes is visible in the initial
900px viewport without scrolling — smaller than the baseline's "only 2 of 8 visible," but not zero.
The composition gap the baseline named is closed; a residual density gap is not.

**9 — Pull request. Baseline: adapt (no diff, no action bar above the fold). Closing: unchanged,
and the gap may be structurally blocked rather than merely undone.** `sideBySideRegions` identical
to baseline, 8. The screen still leads with metadata and two evidence panels (`What the compiler
said`, `What replay found`) rather than the mock's diff hunks and `Approve` / `Request changes` /
`Abandon` action bar. Worth stating plainly: `console-dev-loop.md` holds "no route mutates the
graph, triggers a run, or touches a customer repository" as a standing invariant, and an action bar
that approves or abandons a patch would need a write path M4 does not have. The diff itself has no
such obstacle and its absence is an open gap; the action bar's absence may be a scope question for
whoever owns the write path rather than a restyling task. This report does not resolve which.

**10 — Settings. Not in the baseline; measured for the first time. Verdict: adopt (the refusal),
open question on the bar.** The mock's Settings screen (`10-settings.png`) draws two panels this
route does not build: a `Merge policy` panel offering three named strategies (`Merge when CI is
green`, `Open the pull request only`, `Per repository`) and a `Repository overrides` table naming
specific repositories and their merge behaviour — none of which exist anywhere in Sync's data
model (confirmed against `settings-page.tsx`'s own docstring: "There is no merge policy in Sync...
Rendering a panel reading 'Squash and merge' would be the console asserting a fact about the system
that the system does not hold"). The built route renders a single `Adapters` table, sourced
entirely from `GET /api/adapters` (verified in the Gate 3 report below), followed by two paragraphs
of prose stating plainly that no merge policy exists and why. That is the correct refusal, not a
missing panel. Structurally this means the route has one full-width table and one full-width prose
block, stacked — `sideBySideRegions` measures 0, below the closing table's bar. Whether that bar
should apply here is genuinely open: `routes.ts` declares Settings "deliberately absent" from
`GRAPH_LEVELS`, so it may not owe the per-level "regions beside regions" bar at all. This report
states the raw number and the reason it might not bind, rather than picking one reading.

### Success criteria, checked one by one

- **Display step on every route:** yes. `typeMax` is 46 on all ten routes measured in this walk.
- **Regions beside regions on every level:** yes for all nine `GRAPH_LEVELS` routes (minimum 4, on
  Signals). `/settings` is not a level and measures 0 — see its verdict above.
- **Raw utilities zero:** yes, confirmed both by the empty baseline file and a green
  `tests/test_console_raw_utilities.py`.
- **No colour-carried judgement outside the three channels (status colour, error state, absence):**
  no new instance found on any of the ten routes walked. The one existing colour use inspected
  closely — the detectors rung chart — was checked against the actual rule text (identity, not
  judgement; colour never the only channel) and found compliant, per Task 9's ruling above. This is
  not a pixel-exhaustive audit of every screen; it is what ten routes' screenshots show.
- **Workflow route matches mock 07's composition:** yes, confirmed live (verdict 8 above).
- **Ledgers agree with the tree:** spot-checked rather than exhaustively reconciled. `M14-W274`'s
  ledger claim ("the workflow route takes the mock's two-pane trajectory shape") was verified
  against the running screen, not just the commit message, and matches. A full ledger-to-tree
  reconciliation across all fifteen tasks was outside this walk's scope.

### What this walk did not check

This is still measurement against the nine-plus-one routes and the two-dimensional snippet Task 3
used. It does not re-run the mock-fidelity comparison pixel-for-pixel, does not check routes
outside the ten measured (the drawer, the palette), and does not re-litigate Decision 1's grain
question for Fleet, which both the baseline and this walk deliberately leave to whoever owns that
decision. The Gate 3 evidence in
`docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md` covers a different question — whether
any number on these screens is asserted rather than sourced — and should be read alongside this
table, not instead of it.

---

## M14-W278: the grid layout, closed on this table's own number

**2026-08-17, later still.** The owner's 2026-08-07 complaint — "the console's layout is one
vertical stack where it should be a grid" — had a sibling half (Fleet's prose-to-data ratio) land
as M14-W277 just before this item started. This is the surviving half. The instruction was to
measure first and change only what the measurement justified, using this file's own snippet
verbatim rather than a new one. Full raw output, the RED/GREEN test evidence, and the
viewport/server-stop confirmations are in
`.superpowers/sdd/2026-08-17-console-mock-parity/m12-grid-report.md`.

### Before table (re-measured, prior to any change this item made)

| # | Route | Task 15 closing `sideBySideRegions` | Re-measured | Clears >= 1? |
|---|---|---|---|---|
| 1 | `/` (Fleet) | 10 | 11 | yes |
| 2 | `/repositories/seed-console-repo-a` (Codebase) | 12 | 9 | yes |
| 3 | `/vendors/seed-console-stripe` (Vendor) | 12 | 12 | yes |
| 4 | `/repositories/seed-console-repo-a/observed` (Signals) | 4 | 4 | yes |
| 5 | `/bindings/.../PostCharges` (Binding surface) | 7 | 7 | yes |
| 6 | `/detectors` | 5 | 5 | yes |
| 7 | `/findings/9f176dea…` (Finding) | 5 | 5 | yes |
| 8 | `/findings/9f176dea…/workflow` (Workflow) | 25 | 25 | yes |
| 9 | `/findings/9f176dea…/workflow/pull-request` (PR) | 8 | 8 | yes |
| 10 | `/settings` | 0 | **0** | **no** |

Fleet's 10→11 and Codebase's 12→9 are both traced to `ChangeUnitsTable` row counts, not to any
layout change: Fleet's move is ordinary data-volume noise on a metric that counts DOM containers,
and Codebase's drop is the direct, correct consequence of W277 scoping `GET /api/change-units` to
one repository (fewer rows for one repository than for the whole fleet is what scoping means) —
confirmed against `git show c2162cf -- web/src/features/repositories/codebase-page.tsx`, a
one-line diff passing `repoId` through. Neither is a regression and neither was touched here.

### Decision

Routes 1–9 already clear the bar and were left alone — restyling any of them "to look busier"
is exactly the failure the brief warned against, and a route that already clears the bar is
reported with its number rather than forced into a new shape. `/settings` still measured 0, same
as Task 15's first reading. Ruled (`.claude/rules/autonomous-development.md`): fix it. `routes.ts`
declaring Settings outside `GRAPH_LEVELS` governs which hierarchy test applies to it, not whether
the console's one other structural convention — regions beside regions — should. Its two blocks
(`Adapters`, a wide table; `Merge policy`, two short paragraphs) were already independently
meaningful content with no synthetic tile required to pair them, so `settings-page.tsx` was wired
onto the existing `DetailGrid` (`web/src/layouts/detail-grid.tsx`) rather than a sixth grid
literal: `PageHeader` in the `header` slot, `Merge policy` as the rail, `Adapters` keeping the
wide column for its table. No sentence was reworded — both refusal paragraphs and the Adapters
intro are guarded verbatim by `settings-page.test.tsx`, which also proves the wiring itself: RED
before the change (`expected 543 to be less than 141` — Adapters preceded Merge policy in DOM
order under the old stack), GREEN after.

### After table

| # | Route | Before | After | Changed? |
|---|---|---|---|---|
| 1 | `/` | 11 | 11 | no — already clears |
| 2 | `/repositories/seed-console-repo-a` | 9 | 9 | no — already clears |
| 3 | `/vendors/seed-console-stripe` | 12 | 12 | no — already clears |
| 4 | `/repositories/seed-console-repo-a/observed` | 4 | 4 | no — already clears |
| 5 | `/bindings/.../PostCharges` | 7 | 7 | no — already clears |
| 6 | `/detectors` | 5 | 5 | no — already clears |
| 7 | `/findings/9f176dea…` | 5 | 5 | no — already clears |
| 8 | `/findings/9f176dea…/workflow` | 25 | 25 | no — already clears |
| 9 | `/findings/9f176dea…/workflow/pull-request` | 8 | 8 | no — already clears |
| 10 | `/settings` | **0** | **1** | **yes — fixed** |

All ten routes now clear the `>= 1` bar. Re-measured live after the fix:
`{"typeMax":46,"typeMin":12,"typeRange":"3.83","sideBySideRegions":1,"framePx":40}`.

### Gate

`cd web && npm test` — 329 tests passed (327 base + 2 new), none went red. `npm run build` clean.
`npm run lint` — zero new warnings. `uv run pytest tests/test_console_raw_utilities.py -q` — 1
passed, baseline still empty. This item touched no Python.

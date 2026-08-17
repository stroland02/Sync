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

# Console Information-Architecture Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Read the whole of *Rulings already settled*, *Global
> constraints* and *Corrections to stale citations* before opening a file — every one of them
> exists because something was already got wrong once.

**Goal.** Rebuild the console's navigation and page composition around the repository as the control
unit, on the owner's instruction of 2026-08-17. One full-height sidebar with a repository switcher
and every scoped screen nested beneath it; an Overview that answers one question; a Codebase page
that carries what a repository's own landing screen owes; API service and vendor screens at equal
stage beneath it; and the solution workflow reachable from every place a reader meets a finding.
The graph hierarchy does not change — `GRAPH_LEVELS` stays at nine, in the specification's order,
and every new screen is a route at a level that already exists.

**Architecture.** Four phases, strictly ordered, and each task inside a phase is independently
landable and independently reviewable.

- *Phase 0 — truth and instruments.* Correct the stale citations three separate documents carry,
  close the two holes in the protected-sentence guard, and repair the two mispaired rows in
  `web/scripts/visual-eval.mjs`. Nothing after this phase can be measured honestly until it lands.
- *Phase 1 — the shell.* Invert the chassis so the sidebar is full height and the top bar sits
  inside the content column beside it. Replace the six-area partition with two regions, move the
  repository switcher out of the top bar and into the sidebar between them, and build the
  expand/minimise control.
- *Phase 2 — the addresses.* Nest the API service and binding-surface addresses under the
  repository, add the two list screens the owner asked for, and retire the one address that goes.
- *Phase 3 — the pages.* One page anatomy applied everywhere, the fact row the mock draws and the
  build does not, the regions the owner named on each screen, and the type ramp's unspent middle.
- *Phase 4 — the closing walk.* Re-measure and record.

**Tech stack.** React 18 + Vite + TypeScript under `web/`; vitest over jsdom (`cd web && npm test`);
vendored Supabase primitives under `web/src/vendor/supabase/` (Apache-2.0, attributed in
`web/NOTICE`); pytest guards in `tests/`; Chrome measurement through `web/scripts/visual-eval.mjs`,
`web/scripts/prose-audit.mjs` and `web/scripts/capture-console.mjs`.

**Spec.** `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:429-443` is the
authority for the hierarchy — the *second*, amended fenced block, the one the section labels
authoritative. `DESIGN.md` (repository root) is the token contract. This plan is neither.

---

## Rulings already settled

Reproduced verbatim from the owner's answers of 2026-08-17. **Do not re-open any of these.** A fresh
subagent that finds one of them inconvenient should record a note and continue, not ask.

### Second round, 2026-08-17 evening — answers to this plan's own open questions

These four settle questions 1, 2, 3 and 5 of *Open questions for the owner* below. That section is
left standing as the record of what was asked; these answers supersede it.

> **A. Two detail screens, split on the payload's own seam.** A *service* page answers what this
> repository does with a vendor — call sites, findings, bindings, telemetry, all repository-scoped.
> A *vendor* page answers what the vendor is — published changes, adapter delivery, sources, traces,
> none of which take a `repo_id`. Question 1 is closed in favour of the split, and the seam that
> justifies it is `/changes` and `/api/adapters` taking no repository parameter.
>
> **B. Build the fleet-wide findings screen: new route plus payload change.** Question 2 is closed
> in favour of building it. **This corrects ruling 4 of the first round, which said the fleet-wide
> findings screen "stays".** It could not stay, because it never existed — no route has ever served
> one, and `/api/detectors` discards the finding rows as it aggregates. The first ruling was given
> on a false premise supplied by me. Triage starts fleet-wide and today there is nowhere to do it,
> so the screen is built rather than folded into Detectors.
>
> **C. Keep the repository Signals screen for now.** Question 3 is closed against dismantling it.
> Per-service telemetry appears on each API service page once the observed route accepts a vendor
> and operation filter; until then Signals stays where it is and works. Client-side narrowing is
> forbidden, and not as a matter of taste: `/observed` paginates *before* any filter is applied, so
> narrowing in the browser returns a subset of a page rather than a page of the subset, and the
> screen would state a wrong count while looking correct.
>
> **D. Overview gains a setup and onboarding region.** Question 5 is closed toward more, against
> this plan's own recommendation of staying lean. The owner's two instructions genuinely pull apart
> — "more simple, get rid of junk info" and "should include how to set everything up and dashboards
> about that workspace/repo codebase" — and the owner resolved them toward the second. The
> repository list stays the screen's primary region and its answer to "which repository do I open";
> setup guidance is a second region on the same screen, not a replacement for it and not a modal.
> The protected absence footnote's referent — "the repository list below" — must survive this, which
> means the setup region may not be placed between that sentence and the list it names.

> 1. RUNS AND REPAIRS ON THE CODEBASE PAGE: fix the payload first. The owner chose to add repository scoping
>    to the run and repair payloads (B149) rather than render them fleet-wide with a caveat or omit them. So
>    the plan treats repo-scoped runs and repairs as a named BLOCKED PREREQUISITE owned by another lane, and
>    the Codebase page is designed with those regions present in the layout and implemented last, once B149
>    lands. Do not design a fleet-wide-with-a-label fallback; the owner rejected it.
>
> 2. VENDOR PAGE CONTENT: build the page from what exists. Render spec versions, vendor changes, operations,
>    adapter delivery and observed traces. The categories that no stage captures - rate limits, API rules,
>    call structures - are named as a backlog item, NOT rendered as empty panels carrying the never-measured
>    marker. The owner explicitly rejected scaffolding panels that have no data.
>
> 3. VENDORS: both, in that order. Build the per-repository vendors page against the vendors already tracked,
>    and separately queue new vendor adapters as follow-on work in another lane so the page has more to show
>    later. The console plan owns the first; the second is a pointer, not a task in this plan.
>
> 4. GLOBAL SCREENS SURVIVE. The fleet-wide Detectors screen and the fleet-wide findings screen stay, reachable
>    from the sidebar ABOVE the repository switcher, because a fleet-wide detector view answers a question the
>    scoped copies cannot - which detector is producing false positives across every repository. Scoped copies
>    of detectors, bindings and findings are ADDED inside each API service and vendor page; they do not replace
>    the global ones. The sidebar therefore has a root region (global screens) and a repository region
>    (everything scoped), and the plan must say how those two regions are visually separated.
>
> 5. THE DRAWN MOCK AND THE DEMO ARE THE LAYOUT AND SPACING REFERENCE. The owner's words: "the demo and
>    reference do a great job with layout and spacing and we need to reference that." This is an explicit
>    instruction to argue the layout from those artifacts rather than from taste.
>
>    How to use them, and this part is load-bearing because it has already been got wrong once:
>    - The mock lives under docs/console-mock/ and it is a QUERYABLE DOCUMENT, not a picture. Open it and
>      read the actual markup and computed values. Do not describe it from memory and do not infer its
>      spacing from a screenshot.
>    - There are two versions. v1 is the APPEARANCE target. v2 supersedes v1 only on VOCABULARY - the words
>      and labels - and not on look. This was established by measurement: v2 is light-theme against a
>      recorded dark-only decision, has no border-radius at all, has a type range of 1.45, and shows 6
>      side-by-side regions against v1's 17. Three contradictions against recorded rulings. If your reading
>      of v2 disagrees, say so with numbers rather than quietly following it.
>    - web/scripts/visual-eval.mjs already measures the built console against the mock property by property.
>      Read it to learn which properties are comparable, and express your layout proposals in those same
>      properties so the result is measurable rather than asserted. The eval deliberately refuses to produce
>      a score; do not invent one.
>    - This is NOT permission to copy a competitor. .claude/rules/interface-originality.md still binds, and
>      nothing under docs/superpowers/references/screenshots/ may be opened. The mock and the demo are ours.

### One qualification on ruling 5, carried from a measurement rather than an opinion

v1 is the appearance and shell-geometry target. It is **not** the type-scale target and it is **not**
the between-panel spacing target, and both refusals are arithmetic rather than taste:

- v1's `h1` takes 22px over a 12px floor, a type range of **1.83**. `DESIGN.md:513-521` sets the bar
  at 3.4 and at a display step of at least 3× body; the build measures 3.83 on nine routes and 5.11
  on the Overview. Matching the drawing here would regress the console below a bar it was rebuilt to
  pass. v1's six type steps are otherwise *exactly* `DESIGN.md`'s — same sizes, same line boxes, same
  weights, same tracking — it simply never spends `--text-display`.
- v1 uses `gap:16px` both between top-level panels and inside a panel. `DESIGN.md:656-686` records the
  between-panel gap at **32px**, spelled `gap-8` and deliberately unnamed, and records `40 : 32 : 16 :
  8 : 4` as four levels with a 2× floor at every inner step — noting that one shared value was "the
  sharpest defect that slice measured".
- v1's table body rows are `padding:10px 16px`. 10px is off the 4px base and is the exact defect
  `docs/superpowers/reports/2026-08-06-console-conformance.md:70-74` filed.

What v1 *is* the target for, and what this plan takes from it: the full-height navigation column at
x=0 with the header inset beside it, the four-tile fact row, the three-role card row, the table card
with a tinted header strip and a footer range inside the card, the two radii, the two weights, the
three tracking values, and the 40px page frame.

**v2 is the target for navigation structure and vocabulary only.** Its rail holds a per-codebase tree
with a separate "Across every codebase" group and a 264px/68px expand/minimise toggle, which is
close to what the owner described. Nothing in v2's palette, radius, spacing or type may be taken —
its spacing scale is sub-pixel (`--space-1: 3.4px`, `--space-6: 20.4px`) and maps onto nothing in
`DESIGN.md`. Its child vocabulary — *Integrations*, *Incidents & errors*, *Tickets* — is **not** the
specification's and must not reach `GRAPH_LEVELS`.

---

## Global constraints

Copied verbatim from the binding authorities. These are not this plan's inventions and this plan
cannot relax them.

**From `CLAUDE.md`, the console section:**

> **One rule sits here rather than in a path rule, because it binds a Python view model exactly as
> much as a React component: no composite score, no health figure, no traffic light, no green dot,
> no liveness pulse.** Rejected on the record three times. A scalar that averaged three gates would
> collapse "we could not check" onto the same axis as "we checked and it passed", which is the
> failure this console exists to replace.

> Four distinctions follow from the same position, and each is rendered rather than assumed:
> provenance at two levels, absence apart from zero, staleness apart from liveness, and
> never-measured apart from nothing-here. Twenty-four sentences on screen carry them, reproduced with
> file and line in that plan's *Establish 2* (`:102-207`). **Restyling one is allowed. Deleting one,
> shortening one, collapsing one behind a disclosure, or moving one into a tooltip is not.**

**From `.claude/rules/console-hierarchy.md`:**

> **Every value in `GRAPH_LEVELS` cites the specification line that defines it.** A level with no such
> line does not go in the array. It goes in the specification first — as a dated amendment inside that
> section, carrying the argument for why the graph gained an entity the document did not have — and
> only then into the console.

> - **A screen may exist without being a level.** An aggregate over a level is not a new level.
>   `/codebase` aggregates over API Services; detector attribution aggregates over Errors &
>   Incidents. Neither is a rung on the ladder, and adding one to `GRAPH_LEVELS` claims it is.

**From `.claude/rules/console-surface.md`:**

> Every colour, type step, spacing value, radius, row height and elevation level is declared there
> with the arithmetic that proves it safe. **A new token, a third elevation level, a fourth spacing
> value or a seventh type step is a decision argued in that file — never a value added here.** The
> contrast floor is 5.05:1.

> - **The surface ramp is indexed by job, not by depth.** Two steps carry depth and two carry
>   interaction state, and no step does both. State is always a named step, never an alpha overlay.
> - **Type is assigned by role, not by size.** Weight, line height and tracking travel with the step.

> Dark-only as of 2026-08-05, on the owner's explicit instruction.

> Colour claims a judgement, motion claims a time, depth claims a relationship. Three channels may
> carry a claim, because the data holds one: the run outcome, the error state, and absence. A status
> colour never travels alone — it ships with an icon and a word.

**From `.claude/rules/interface-originality.md`:**

> **The interface is ours. Every screen, every layout, every component, every word on it.**

> A control plane has a grammar, the same way a form has one. **These are conventions, not
> inventions, and learning them from anything is permitted** — a persistent navigation rail and a
> second contextual level inside it; a breadcrumb or scope switcher; a page header; a control bar; a
> footer bar owning pagination and the record count; a detail that opens in a drawer; a fact rendered
> as a tile; a metric panel whose value sits above its own evidence; a type ramp with a display step.

**Nothing under `docs/superpowers/references/screenshots/` is opened by any task in this plan.**

**From `.claude/rules/autonomous-development.md`:** while executing this plan, decide and continue.
Write the ruling into this file's SDD ledger, keep going, and surface it in the next report as a
decision the owner can reverse. Stop only for an irreversible action outside the repository, a
decision that invalidates the plan's architecture, or a credential or spend.

**Toolchain and process:**

- Python is `python`, never `python3`. Packages through `uv` only. Postgres is on port **5433**.
- Always pass `encoding="utf-8"` to every `read_text`, `write_text`, `open` and
  `subprocess.run(..., text=True)`, and set `PYTHONIOENCODING=utf-8` in a Python child's environment.
- **Test first, in both languages.** Write the failing test, run it, watch it fail for the reason you
  expect, then implement. Every new vitest guard is shown RED against a deliberately broken subject
  before it is trusted.
- vitest scope is classification, derivation and structural invariants. **Never class names. Never
  snapshots.** Anything about rendered pixels is measured in Chrome and written into `DESIGN.md`.
- **Gates before any task reports done:** `cd web && npm run build && npm run lint && npm test`, plus
  `uv run pytest tests/ -q` when a Python file changed. Say which ran. `-n auto` is the current
  guidance (`M0-W267` retired `-n 4`).
- **Integration branch is `console-parity`.** Branch from it, gate on it, push your own branch. A
  worker never opens a pull request and never merges into `main`. A worker may fast-forward `main`
  only when `git merge-base --is-ancestor origin/main HEAD` passes.
- **Work item register:** `docs/superpowers/WORKLOG.md`. The highest number on the register at the
  time of writing is **W362**; take the next free number, add the row *before* starting, and carry
  the identifier in every commit subject. The milestone prefix for this plan is **M14**.
- **Never `git stash`** — `refs/stash` is one stack shared across every worktree of this repository.
- The API stays read-only apart from `POST /api/repos/{repo_id}/context`, which already exists.
  `test_no_route_reaches_past_the_read_surface` (`tests/test_api_routes.py:1101`) holds it.
- Dev loop per `.claude/rules/console-dev-loop.md`. A worker's dev server runs on a free port and is
  stopped before reporting. Every `set_viewport` is paired with a `clear_viewport`.

---

## Corrections to stale citations, verified against the tree on 2026-08-17

Four documents this plan's readers will open carry a statement that is no longer true. Task 1 fixes
them in the repository; they are listed here so nobody acts on the stale form in the meantime.

1. **`DESIGN.md` is at the repository root.** There is no `web/DESIGN.md`, and a plan that writes one
   creates a second token contract beside the real one. `.claude/rules/console-surface.md`'s own
   frontmatter lists `DESIGN.md` unqualified.
2. **`.claude/rules/console-surface.md:31-33` says "Three spacing tokens, and exactly two named
   exceptions".** `DESIGN.md:641-661` and `tests/test_console_design_tokens.py:97-118` both say
   **four tokens and one exception** — the second exception retired when `--spacing-frame` became a
   token at 40px in M7-W160. `DESIGN.md` is the declared authority; follow four-and-one and do not
   cite the rule's count.
3. **The Establish 2 catalogue's file:line anchors are stale.** It cites
   `features/repositories/overview-page.tsx:56` and `features/bindings/bindings-page.tsx:90-91`;
   **both files were deleted** in `17aa3bb`, and `features/bindings/repository-coverage-page.tsx` was
   renamed to `features/repositories/codebase-page.tsx` in the same commit. `features/telemetry/
   observed-telemetry-page.tsx` was deleted in `b39dcde`. Every other cited line number has moved.
   The *Protected sentences that move* section below carries the current locations.
4. **`src/sync/dashboard/adapters.py:47-53` and `web/src/api/types.ts:753-755` both assert that
   "nothing records an intake attempt, only its result".** That is false: `intake_attempt` exists at
   `src/sync/graph/schema.sql:514-531` with a closed seventeen-member reason vocabulary, and
   `GraphStore.intake_attempts()` reads it (`store.py:2136-2139`). The console is being told a limit
   that no longer exists. No route exposes the table yet — that half is filed as **B178**.
5. **`B150` is a duplicate identifier.** `BACKLOG.md:1165` is "CI was red on `main`" and
   `BACKLOG.md:4266` is "Viewing the code means call sites". This plan means the second one every
   time and says so as `B150 (BACKLOG.md:4266)`.

---

## What already landed, so nobody rebuilds it

- **`M14-W362` (`61d0470`) already turned the landing screen into the Overview.** `fleet-page.tsx`
  is titled Overview, the fleet-wide change-unit table and vendor distribution were removed from it,
  the page-level action was removed, and the repository list is rows rather than cards. `routes.ts`
  still labels the route `"Codebases"` at `:186` and `AREAS[0]` at `:110`; that rename is one line in
  Task 12 of this plan, not a screen rebuild.
- **`--color-surface-scope` already exists and already has exactly one consumer**, `layouts/
  app-frame.tsx`. It is the token for the scope an address is *inside*, distinct from the current-page
  mark. The new sidebar's two-region structure is what it was declared for.
- **`ErrorState` already takes an optional `onRetry`** (`M14-W349`), wired at twenty call sites.
- **`main` already takes focus on a route change** (`M14-W352`) and the sidebar footer already carries
  the deployment sentence (`M14-W351`). Both survive the chassis inversion and both have tests.

---

## The hierarchy, unchanged

`GRAPH_LEVELS` stays at **nine values, in the specification's order, with their existing citations**:

```
Fleet (:430) > Codebase (:433) > API Services (:434)
                                   ├── Signals (:435)
                                   ├── Binding surface (:437)
                                   └── Errors & Incidents (:439)
                                         └── Finding (:440)
                                               └── Solution Workflow (:441)
                                                     └── Pull Request (:442)
```

**No task in this plan adds, removes, renames or reparents a level.** Three things the owner asked
for look like hierarchy changes and are not, and the reasoning is recorded here so a reviewer does
not have to re-derive it:

- **"A vendors page at an equal stage to api services"** is not a tenth level. In the specification,
  *API Services* **is** the vendor level — the authoritative block annotates it "vendors the indexer
  found in this repository", and `/vendors/:vendorId` already carries `level: "API Services"` with
  `label: "Vendor"`. Both new list screens carry `level: "API Services"`. Adding a `"Vendors"` level
  would fail `tests/test_console_hierarchy.py:140-153` on its first run and would need a dated
  amendment to the specification first.
- **"The solution workflow should be part of the codebase page"** is a placement, not a reparent. The
  level's specification parent is *Finding*, and `/findings/:findingId/workflow` binds `findingId` —
  a workflow cannot be addressed without a finding. This plan renders **links and summary panels** to
  the workflow from the Codebase page, from each findings table and from each API page. It does not
  move the level. `tests/test_console_hierarchy.py:94-118` would not catch a reparent that preserved
  depth-first order — `_parse_levels` never inspects indentation — so the reviewer is the only guard
  here, which is exactly the failure `.claude/rules/console-hierarchy.md:44-49` records.
- **"Detectors and bindings should be part of the api and vendor pages"** is a placement too.
  *Detector attribution* is deliberately **not** a level (`routes.ts:26-28`, citing the specification
  at `:445`); `/detectors` carries `Errors & Incidents`. *Binding surface* is already a level and
  already vendor-and-operation addressed.

**Multiple routes at one level are licensed explicitly** by `.claude/rules/console-hierarchy.md:36-38`
and by `routes.test.tsx:127-134`, which checks membership rather than uniqueness.

---

## The route table after this plan

Twelve level routes plus one destination. `region` replaces `area`.

| Path | Label | Level | Region | Params |
|---|---|---|---|---|
| `/` | Overview | Fleet | root | — |
| `/detectors` | Detectors | Errors & Incidents | root | — |
| `/vendors/:vendorId` | Vendor | API Services | root | `vendorId` |
| `/repositories/:repoId` | Codebase | Codebase | repository | `repoId` |
| `/repositories/:repoId/services` | API services | API Services | repository | `repoId` |
| `/repositories/:repoId/services/:vendorId` | API service | API Services | repository | `repoId`, `vendorId` |
| `/repositories/:repoId/services/:vendorId/operations/:operationId` | Binding surface | Binding surface | repository | `repoId`, `vendorId`, `operationId` |
| `/repositories/:repoId/vendors` | Vendors | API Services | repository | `repoId` |
| `/repositories/:repoId/observed` | Signals | Signals | repository | `repoId` |
| `/findings/:findingId` | Finding | Finding | repository | `findingId` |
| `/findings/:findingId/workflow` | Solution workflow | Solution Workflow | repository | `findingId` |
| `/findings/:findingId/workflow/pull-request` | Pull request | Pull Request | repository | `findingId` |
| `/settings` | Settings | *(a destination, not a level)* | root | — |

### Retired addresses

| Old address | Answer | Mechanism |
|---|---|---|
| `/bindings/vendors/:vendorId/operations/:operationId?repo_id=R` | `/repositories/R/services/:vendorId/operations/:operationId` | `<Navigate replace>` reading the `repo_id` search key |
| `/bindings/vendors/:vendorId/operations/:operationId` *(no `repo_id`)* | `/vendors/:vendorId` | `<Navigate replace>`. The operation is dropped because the nested address cannot be constructed without a repository, and this is stated in the commit rather than hidden |
| `/vendors/:vendorId` | **not retired** — kept as the root-region vendor record | — |
| `/repositories/:repoId/observed` | **not retired** — Signals stays repository-grain, see ruling below | — |

### Why `/vendors/:vendorId` survives, and why the vendor list is repository-scoped while the vendor
### detail is not

The seam is the payload's, not a preference. `GET /api/vendors/{id}?repo_id=` narrows *findings* to a
repository; `GET /api/vendors/{id}/changes` and `GET /api/adapters` take **no** `repo_id` at all, and
`src/sync/api/app.py:76-79` records that as a deliberate decision. A vendor's published changes and
its adapter's delivery record are vendor-wide facts. Rendering them under a repository heading would
be the scope collapse this console refuses everywhere else.

So: **`/repositories/:repoId/vendors` is a repository-scoped list** — which vendors this repository
calls — and each row opens **`/vendors/:vendorId`, the vendor's own record**, which says on its face
that it is vendor-wide rather than repository-scoped. That satisfies ruling 4's requirement that the
fleet-wide findings surface survive (reached with no `repo_id`, `/vendors/:vendorId` *is* that
surface today), and it avoids building two vendor detail screens that would disagree.

### Why Signals stays a repository screen

The owner asked for sources and signals to pertain to each API service.
`GET /api/repositories/{repo_id}/observed` takes **no vendor and no operation filter**
(`graph_views.py:310-320`), and its three sets are paginated **server-side before any filter**, so
narrowing client-side would silently drop rows. The narrowing exists one layer down —
`store.observed_shapes(vendor_id, operation_id, ...)` at `store.py:1948-1949` — and is discarded at
the view.

Until **B173** lands, the API service page carries a *link* into the repository's Signals screen and
no telemetry panel. A link is not a scaffolded empty panel; it is the honest answer, and it preserves
the referent of the protected pointer at `codebase-page.tsx:150-156` ("see it grouped with the other
two roles, on the Signals screen"), which would otherwise point at a screen that no longer exists.

### The region invariant, which is a test rather than a claim

`AREAS`, `Area`, `AreaEntry`, `areaForPathname`, `AREA_ICON` and `AreaRail` are **deleted**, not kept
alongside the new grouping. `RouteEntry` gains `region: "root" | "repository"`, and the sidebar's two
visual regions read that field directly — one mechanism, nothing to drift. The contiguity argument in
the old docstring (`routes.ts:75-88`) goes with it; nothing asserted it anyway
(`routes.test.tsx:145-150` checks a sorted-set partition, which any partition satisfies).

Two assertions replace it, in `web/src/lib/routes.test.tsx`:

1. **No `root` route declares `repoId`.**
2. **Every `repository` route declares `repoId` as its first parameter** — with one named exemption:
   a route whose `params` equal exactly `["findingId"]`, spelled as a literal three-path allow-list in
   the test so growing it costs an edit.

The exemption exists because `RiskRow` — the row a findings table renders — **carries no `repo_id`**
(`web/src/api/types.ts:135-145`, built at `src/sync/dashboard/graph_views.py:439-452`). A findings row
therefore cannot construct a nested href, and an address that asserted one would be claiming a
containment the payload cannot confirm. `FindingIdentity.repo_id` *does* exist
(`types.ts:236`) — the detail payload knows its repository — but the **list** row does not, and it is
the list that has to build the link. **B177** is what retires the exemption.

---

## The page anatomy, applied everywhere

One anatomy, top to bottom, so the composition gain is reproducible on screens nobody has drawn yet
rather than being eleven separate layout decisions. Every value below is a token that exists.

| Band | What it holds | Tokens |
|---|---|---|
| Top bar | breadcrumb, command-palette trigger. **Inside the content column**, right of the sidebar | `h-12` (page-layout raw, `layouts/` only), `border-b border-line`, `px-section` |
| `PageHeader` | the `h1` at `--text-display`, **once per route and nowhere else**; the level chip; the question at `--text-body text-ink-muted max-w-prose`; at most one action | `gap-section` between blocks, `gap-field` within |
| `ControlBar` | scope, filter, search, and the grain statement pushed right | `gap-section` between groups; controls at `row-sm` (`h-8`) or `row-lg` (`h-10`), `--radius-control`, `--color-border-control`, `--color-ring` at full strength |
| Fact row | three or four `FactTile`s side by side — the mock's four-tile row | `--text-figure` value over a `.furniture text-meta text-ink-muted` label, `--text-meta` evidence line beneath, `gap-section` |
| Primary beside secondary | the screen's main table or panel spanning two columns with a supporting panel in the third | `gap-8` (the recorded unnamed 32px page-layout value), `--color-card`, `--radius-surface`, `--shadow-flat` only where a surface must be told from a neighbour at the same depth |
| `FooterBar` | the record count, pagination if the payload pages, and the scope caveat in the `left` slot | `border-t border-line`, `pt-section`, `gap-section` across, `gap-field` in the left column |

**Type: spend the middle of the ramp.** The measured census across seven routes found 18px on
**exactly one heading in the whole application**, with almost every other `h2`/`h3` at 12px uppercase
furniture — so a section heading renders the same size as a table column header. The boundary rule is
`DESIGN.md:523-543` and it is not a matter of taste: **a heading that names a region a reader enters
takes `--text-section`; a label that names a value beside or beneath it stays `.furniture text-meta`.**
Being scanned is necessary and not sufficient. A card's own title inside a repeating grid takes
`--text-emphasis`. `.furniture` beside `text-section` is banned.

**Whitespace posture, which this plan is measured against** (`DESIGN.md:135-138`): *"Whitespace is
what is being spent, not what is being bought… every unit of vertical space is a row that fell off the
viewport. Contrast carries hierarchy. Space separates only two things a reader must not confuse. What
grows is the RANGE — the page title, the value-versus-label distinction — not the average."* **A task
that raises average padding is arguing against a recorded decision and must say so.**

### Values this plan needs that `DESIGN.md` does not declare

Named here explicitly rather than spelled quietly as a raw utility. Task 7 argues each of them into
`DESIGN.md` before spending it, or the task does not land.

1. **The sidebar's expanded width, proposed 15rem / 240px.** The vendored constant is
   `SIDEBAR_WIDTH = '13rem'` (208px), injected as an inline CSS variable rather than declared as a
   token. 208px truncates "Solution workflow" at the current row padding. 240px is a page-layout
   number used once per view, which is the same carve-out that keeps `gap-8` unnamed
   (`DESIGN.md:657-661`) — but it is written in `layouts/`, which the raw-spacing guard does not scan
   (`tests/test_console_design_tokens.py:305-309`), so it must be argued rather than merely permitted.
2. **The sidebar's collapsed width, proposed 3rem / 48px.** This settles a live contradiction:
   `DESIGN.md:177` argues for `--color-surface-scope` on the grounds that the mark "has to read from a
   **48px** column with no label in it", while the shipped rail renders `w-10` (**40px**) and
   `73b7654`'s own commit body says "a 40px icon rail". One of the two figures is stale. Adopting 48px
   makes the doc's own argument true and matches the vendored `SIDEBAR_WIDTH_ICON = '3rem'`.
3. **The top bar's height, 48px, spelled `h-12`.** Already spelled that way in `layouts/app-frame.tsx`
   today and legitimate under the same carve-out. Named for completeness so a reviewer does not
   mistake it for a new value.

**No other value in this plan is new.** If a task finds it needs one, it stops and argues it in
`DESIGN.md` in its own commit rather than reaching for a raw utility.

---

## Measured targets, in `visual-eval.mjs`'s own properties

`web/scripts/visual-eval.mjs` measures fourteen properties through one probe and prints twelve.
Express every layout claim in these and nothing else. **The eval refuses to produce a score
(`:15-17`, `:421-424`) and this plan does not invent one.** Two of its properties may never be used
here: `sideBySide` compares markup technique — the mock holds zero `<table>` elements and 33
`grid-template-columns`, so each mock data row scores as a placement while a semantic `<tr>` scores
nothing — and `framePadding` reads `padding-left` on `main` while the mock pads an inner container,
so it reports 0px for a mock that plainly has a 40px frame. Use **`regionsBeside`**, which excludes
anything inside a `table` and counts a child only when it is a landmark, carries its own heading, or
is drawn as a card.

Settled baselines (`reports/2026-08-17-visual-eval-first-run.md:343-356`) and this plan's targets:

| Screen | `regionsBeside` today | Mock v1 | Target | Why |
|---|---|---|---|---|
| Overview (`/`) | 12 | 0 | **no increase** | the owner asked for a *simpler* landing page. The two-column repair in Task 12 re-arranges an existing band; it does not add one |
| Codebase | 1 | 2 | **≥ 3** | fact row + primary-beside-secondary band. The mock-gap report names the missing four-tile row explicitly |
| API service *(new)* | — | 1 | **≥ 3** | |
| API services list *(new)* | — | — | **≥ 2** | |
| Vendors list *(new)* | — | — | **≥ 2** | |
| Vendor (`/vendors/:id`) | 4 | 1 | **≥ 4** | already ahead; ruling 2's three evidence groups keep it there |
| Signals | 0 | 1 | **≥ 2** | the mock's three-role card row is the named gap |
| Binding surface | 0 | 1 | **≥ 3** | fact row is the named gap |
| Detectors (`/detectors`) | 0 | 1 | **≥ 2** | |
| Remediation | 1 | 1 | 1 | no change asked for |
| Settings | 1 | 1 | 1 | no change asked for |

Other properties, all of which must hold unchanged: `typeRange` **≥ 3.4** on every route (measures
3.83 today, 5.11 on the Overview); `radii` exactly `{6, 8}`; `weights` exactly `{400, 600}`;
`bodyBackground` and `bodyColor` unchanged. **`proseChars` is report-only** — the settled ruling
(`reports/2026-08-17-visual-eval-what-ci-needs.md:33-54`) is that colour, radius, font-size and
font-weight may gate CI because they are token-derived and discrete, while region counts, prose
characters and density may not, because gating a count makes this a snapshot test that gets deleted
within a week by whoever it blocks.

**A prose cut is only made after a `prose-audit.mjs` run separates protected from discretionary
characters on that screen.** Three screens have been audited and the excess was mostly protected
prose in every one; `api-services`, `remediation` and `settings` have never been audited.

---

## File structure

```
web/src/
  lib/
    routes.ts                     MODIFIED — region replaces area; twelve level routes
    routes.test.tsx               MODIFIED — the two region invariants and the three-path allow-list
  layouts/
    app-frame.tsx                 MODIFIED — chassis inverted; AreaRail deleted
    app-frame.test.tsx            MODIFIED — banner-inside-content, sidebar-precedes-banner
    app-sidebar.tsx               NEW      — the one full-height sidebar: brand, root region,
                                             switcher, repository region, footer
    app-sidebar.test.tsx          NEW
    sidebar-collapse.ts           NEW      — the two widths, the persisted choice, no viewport read
    sidebar-collapse.test.ts      NEW
    scope-switchers.tsx           MODIFIED — ScopeTrail loses the repository picker to the sidebar
    page-anatomy.tsx              NEW      — FactRow, the primary/secondary band
    page-anatomy.test.tsx         NEW
    command-palette.tsx           MODIFIED — groups by level; DESTINATIONS heading unchanged
  features/
    fleet/fleet-page.tsx          MODIFIED — the two-column footer band repair
    fleet/runs-table.tsx          MODIFIED — remounted on Codebase (blocked on B149)
    fleet/corpus-summary.tsx      MODIFIED — remounted on Codebase (blocked on B149); :89-94 rewritten
    fleet/repositories-table.tsx  MODIFIED — remounted on Overview
    fleet/detectors-summary.tsx   MODIFIED — remounted on /detectors
    repositories/codebase-page.tsx        MODIFIED — the owner's five regions
    repositories/repo-context-card.tsx    NEW      — the setup region
    services/services-list-page.tsx       NEW
    services/service-page.tsx             NEW
    vendors/vendors-list-page.tsx         NEW
    vendors/vendor-page.tsx               MODIFIED — ruling 2's three evidence groups
    bindings/binding-surface-page.tsx     MODIFIED — nested address
    workflows/workflow-link-card.tsx      NEW      — the workflow summary that travels
  api/
    client.ts                     MODIFIED — repoContext(); the first consumer of that route
    types.ts                      MODIFIED — RepoContext; the false intake sentence corrected
tests/
  test_console_honesty_sentences.py       MODIFIED — the two holes closed
  test_console_hierarchy.py               UNCHANGED — it must stay green untouched
web/scripts/
  visual-eval.mjs                 MODIFIED — the two mispaired rows; the new routes
docs/superpowers/
  BACKLOG.md                      MODIFIED — B173..B178 filed
  WORKLOG.md                      MODIFIED — one row per task
```

---

## Blocked prerequisites

**None of these is a task in this plan.** Each is a payload or backend change owned by another lane.
A task that depends on one names it and is implemented last; no task fakes the data, scaffolds an
empty panel, or ships a fleet-wide figure under a repository heading.

### B149 — runs and repairs cannot be scoped to a repository *(already filed, `BACKLOG.md:4241`)*

`RunRow` carries no `repo_id` (`src/sync/dashboard/fleet.py:40-48`), and `/api/corpus` accepts no
query parameter (`app.py:305-306`). **Owner ruling 1 settles the answer: fix the payload.** Blocks
Task 17 entirely.

Two facts that make B149 smaller than it reads, both verified, and worth passing to the owning lane:
the checkpoint's own state already carries the repository (`queries.py:217`,
`'repo_id': _extract_repo_id(values)`), and `GraphStore.repo_ids_for_findings()` already exists and
is unused by `fleet.runs` (`store.py:1578-1591`). For repairs, `migration_outcome` deliberately holds
no repository column and **must keep it that way** (`schema.sql:184-186`: "Nothing here identifies a
customer… which is what makes the table safe to aggregate across customers") — but it holds
`finding_id` and `vendor_id`, so repository scoping is a **join, not a column addition**.

### B147 — a repository with no telemetry 404s *(already filed, `BACKLOG.md:4182`)*

**The filed cause is wrong and the filed fix would not close it.** The cause is the path converter,
not an empty payload: `app.py:422-423` use `{repo_id}`, the default `str` converter, which does not
match a `/`, while `:426-429` already use `{repo_id:path}` with a comment saying exactly why. Real
repository ids are `host/owner/name`, and `encodeURIComponent`'s `%2F` is decoded before routing.
Verified live: `/api/repositories/github.com%2Fstripe%2Fx/coverage` → 404,
`/api/repositories/r1/coverage` → 200. Every existing test uses the slashless fixture id `r1`
(`tests/test_api_routes.py:1055`, `:1084`, `:1433-1434`, `:2143-2144`), which is why nothing caught it.
Both readers already return well-formed empty payloads for an unknown repository
(`graph_views.py:249-258`, `:353-377`), so the absence-versus-zero half is already satisfied at the
view layer. **The fix is `{repo_id:path}` on both routes and a test with a slash in the id.**

Blocks Tasks 14 and 16 from being *observed*; they can still be built and unit-tested.

### B173 — `/api/repositories/{id}/observed` takes no vendor or operation filter *(new)*

Blocks a per-service telemetry region. `graph_views.py:310-320` has no vendor or operation parameter,
and pagination is applied server-side before any filter, so client-side narrowing would silently drop
rows. The narrowing exists one layer down and is discarded:
`store.observed_shapes(vendor_id, operation_id, ...)` (`store.py:1948-1949`) and
`observed_shapes_for_operations(pairs, ...)` (`:2001-2007`). Shapes are a parameter away; calls and
error windows need a new `WHERE` clause (`store.py:1765-1766`, `:1900-1901`).

### B174 — a fleet-wide findings list has no payload *(new)*

Ruling 4 says the fleet-wide findings screen stays; today it exists only de facto, as
`/vendors/:vendorId` reached with no `repo_id`. There is no route that lists findings across every
vendor. `/api/detectors` looks like the place and is not: `detector_accountability`
(`graph_views.py:614-660`) reads `store.open_findings_page(repo_id=...)` and then **discards the
rows**, returning per-detector aggregates only. A findings list on `/detectors` is a payload change,
not a free re-render. Blocks a dedicated `/findings` route. Surfaced as open question 2.

### B175 — detectors cannot be scoped to a vendor *(new)*

`/api/detectors` accepts `repo_id` only (`app.py:353-354`), and `store.open_findings_page`
(`store.py:1047-1049`) takes `repo_id` and no `vendor_id`. Putting a detector region on the API
service page needs a parameter through three layers. Also: **findings rows carry no detector at all**
(`graph_views.py:439-450`, `types.ts:136-146`), so a findings table cannot group or filter by detector
even client-side. Blocks the detectors region on the API service page.

### B176 — nothing enumerates a repository's call sites, and nothing lists a vendor's operations *(new)*

This is **beyond `B150` (`BACKLOG.md:4266`) and `B150` does not name it.** B150 records that Sync
stores no customer source text. The sharper constraint is that Sync cannot enumerate *locations*
either: every call-site read requires **both** a vendor and an operation
(`store.py:709-717`, both positional and required), and `call_site_counts(repo_id)` /
`call_site_coverage(repo_id)` return per-vendor counts only (`:854`, `:889`). No store method takes a
`repo_id` alone and returns rows. Consequently a file-tree view, a "where does this repository call
vendors" view, and "all bindings for this vendor" all have no query behind them. Blocks any
code-structure region beyond per-vendor counts.

### B177 — `RiskRow` carries no `repo_id`, so a findings row cannot build a nested address *(new)*

`types.ts:135-145`, built at `graph_views.py:439-452`. This is what makes the three-path exemption in
the region invariant necessary. `FindingIdentity.repo_id` exists (`types.ts:236`), so the detail
payload knows its repository — it is the list row that does not. Retires the exemption when closed.

### B178 — `intake_attempt` is recorded and unreachable, and two files assert it is not recorded *(new)*

`schema.sql:514-531` holds one row per attempt with a closed seventeen-member reason vocabulary;
`GraphStore.intake_attempts()` reads it (`store.py:2136-2139`); **no route exposes it** and
`adapters.py:60-72` does not read it. Separately, `adapters.py:47-53` and `types.ts:753-755` both
still assert "nothing records an intake attempt, only its result" — Task 1 corrects those two
sentences, which needs no backend work; the route does. Blocks an intake-history group on the vendor
page (ruling 2's *Delivered* group renders without it).

### Not a blocker, a pointer (ruling 3, second half)

New vendor adapters so the vendors list has more to show are **follow-on work in another lane**. This
plan owns the per-repository vendors page against the vendors already tracked, and nothing more.

---

## Protected sentences that move

Eighteen rows. Ten of the twenty-four protected sentences appear here, plus eight surrounding
qualifications structurally bound to them. **Every row is a move or a repair. None is a deletion, a
shortening, a collapse behind a disclosure, or a move into a tooltip, and a reviewer diffs against
this table.** Current locations were verified against the tree on 2026-08-17; the Establish 2
catalogue's own line numbers are stale and are corrected by Task 1.

| # | Sentence (distinguishing fragment) | Source today | Destination | Movement |
|---|---|---|---|---|
| 1 | *"There is no composite health figure here on purpose…"* **(#1)** | `web/src/features/fleet/fleet-page.tsx:118-123` | stays on the Overview | **REPAIR.** Its closing clause — *"the panel beside them names what none of these figures can tell you at all"* — **is already false.** `fleet-page.tsx:112-127` renders `<div className="grid gap-section xl:grid-cols-2">` containing **one** child, a `flex flex-col` holding `FactTile` then `ScreenLimitsCard` **stacked**. Task 12 makes the band genuinely two-column so the words become true. The text is not edited |
| 2 | *"…'last checkpoint' is staleness, not liveness…"* **(#2)** | `web/src/features/fleet/runs-table.tsx:203-212` | Codebase page, runs region | **MOVE.** `RunsCard` has zero non-test importers today, so this renders **nowhere**. Task 17, blocked on B149 |
| 3 | *"One row per checkpoint thread, not one per finding…"* **(#3)** | `web/src/features/fleet/runs-table.tsx:100-104` | Codebase page, runs region | **MOVE.** Same orphaned card. Task 17 |
| 4 | *"Counted across the {N} runs shown below, not the fleet…"* *(surrounding)* | `web/src/features/fleet/runs-table.tsx:124-127` | Codebase page, **above** the runs table | **MOVE.** Its scope claim is bound to the table's position. Task 17 |
| 5 | *"This is an answer about the run, not a failure of the console…"* **(#24, runs instance)** | `web/src/features/fleet/runs-table.tsx:110` | Codebase page, runs region | **MOVE.** Task 17 |
| 6 | *"Every repair attempt the graph has recorded, one row of migration_outcome per attempt…"* **(#4)** | `web/src/features/fleet/corpus-summary.tsx:83-88` | Codebase page, repairs region | **MOVE.** `CorpusSummaryCard` is orphaned. Task 17, blocked on B149 |
| 7 | *"This one cannot be narrowed to a repository, and no screen below this level renders it…"* *(surrounding, #4's qualification)* | `web/src/features/fleet/corpus-summary.tsx:89-94` | Codebase page | **REWRITE, in the same commit as B149's landing and no earlier.** The sentence is a claim about the hierarchy and it becomes **false** the moment a repair figure renders under a repository. The rewrite keeps both facts it carries — that `migration_outcome` stores no repository, and that nothing in it identifies a customer, which is the decision that makes it safe to aggregate across them — and replaces the *"no screen below this level renders it"* clause with the join the payload now performs. It is not shortened |
| 8 | *"This is an answer about the run…"* **(#24, corpus instance)** | `web/src/features/fleet/corpus-summary.tsx:101` | Codebase page, repairs region | **MOVE.** Task 17 |
| 9 | *"Every repository the API Dependency Graph holds at least one call site from…"* **(#5)** | `web/src/features/fleet/repositories-table.tsx:48-53` | Overview, **mounted** | **MOVE from an orphan to a rendered screen.** `RepositoriesCard` has zero non-test importers; the live Overview carries only a compressed footnote at `fleet-page.tsx:136`, which is the shortening the rule forbids, already shipped. Task 4 |
| 10 | *"This is an answer about the …, not a failure of the console…"* **(#24, repositories instance)** | `web/src/features/fleet/repositories-table.tsx:59` | Overview | **MOVE.** Task 4 |
| 11 | *"This is an answer about the …, not a failure of the console…"* **(#24, detectors instance)** | `web/src/features/fleet/detectors-summary.tsx:70` | `/detectors`, **mounted** | **MOVE from an orphan.** `DetectorsSummaryCard` has zero non-test importers. Task 4 |
| 12 | *"…or nothing indexed does — the index cannot tell the two apart."* **(#8)** | `web/src/features/bindings/binding-surface-page.tsx:323` | same file, new nested address | **CARRIED.** Task 8 changes the route the file serves, not the file's prose |
| 13 | *"…or this repository has not been indexed at all — the index cannot tell the two apart."* **(#9)** | `web/src/features/bindings/binding-surface-page.tsx:324` | same file, new nested address | **CARRIED.** Task 8 |
| 14 | *"Either this operation has never had a call site here, or it had one that was later retracted…"* **(#10)** | `web/src/features/bindings/binding-surface-page.tsx:517-520`, the `FooterBar` `left` slot | same file, new nested address, **still the `left` slot of a `FooterBar` above a paginated table** | **CARRIED, with a structural constraint.** A layout that replaces the footer bar, or moves the call-site table into a drawer or a tab, drops this sentence silently. Task 8 must keep the footer |
| 15 | *"…is a separate kind of evidence on the repository's own coverage page, never blended into this row"* *(surrounding, part of #19's prose form)* | `web/src/features/bindings/binding-surface-page.tsx:269-270` | same file | **REFERENT RENAME.** *"the repository's own coverage page"* names a screen that no longer exists — `repository-coverage-page.tsx` became `codebase-page.tsx` in `17aa3bb`. The phrase becomes *"the repository's own Codebase page"*. Nothing else in the block is touched; the two other spatial references in it (`:252` *"the repositories above"*, `:260-261` *"see below for what that absence does and does not mean"*) constrain Task 8's layout and must stay true |
| 16 | *"Rung sits ahead of the call site so it stays on screen at 1280px without a sideways scroll…"* **(#19)** | `web/src/features/vendors/vendor-findings-table.tsx:354-357` | same file; **gains a second mount** on the API service page | **SECOND MOUNT.** The component is reused; the sentence travels with it. Task 14 |
| 17 | *"…the runs table above still names them through an abandon reason"* *(surrounding)* | `web/src/features/fleet/screen-limits.tsx:22` | Overview | **REPAIR, already false today.** `RunsCard` is unmounted, so the claim points at nothing. Task 4 rewords it to name the Codebase screen where the runs table will live; when B149 lands and Task 17 mounts it there, the wording is checked again |
| 18 | *"…the vendor panel above orders by open finding count, not by how severe those findings are"* *(surrounding)* | `web/src/features/fleet/screen-limits.tsx:38` | Overview | **REPAIR, already false today.** `VendorDistributionCard` is unmounted. Task 4 rewords it to name the per-repository Vendors list |

### Surroundings that constrain a layout without moving

These are not moves and are not in the count. Every one is a protected sentence whose truth depends
on where something else sits, so a task that re-arranges the screen must check it.

- **`fleet-page.tsx:136` and `screen-limits.tsx:14` both say *"the repository list below"***. The list
  stays on the Overview and stays physically below them. `fleet-page.tsx:29-34` already records this
  as the reason the list does not move into the sidebar — **the sidebar's repository switcher must not
  be allowed to replace the on-page list.**
- **`codebase-page.tsx:184-189`: *"scoped to the vendor/operation pairs this repository's own calls
  above name"***. The Shapes region stays **below** the Calls region on the Codebase page.
- **`codebase-page.tsx:150-156` links to the Signals screen by name.** Signals stays; see the ruling
  above.
- **`index-coverage-card.tsx:63-66` and `subject-catalogue.tsx:123-127` both say *"A vendor name below
  opens that vendor's own page"***, each directly above the grid it describes. Both still open
  `/vendors/:vendorId`, which this plan keeps.
- **`finding-page.tsx:436`: *"this finding's own rung is in the facts beside this panel"***. The
  provenance panel and the `FactList` stay siblings; neither may move into a drawer or a tab alone.
- **`provenance.tsx:9-10`: the envelope rung *"describes the whole page"***, and every `bindingNullLabel`
  says *"the findings on this page"*. Merging two findings tables onto one screen, or splitting one
  into tabs, changes that claim's truth without changing its words. Task 14 must supply a per-page
  `bindingNullLabel` for each new mount rather than reusing another screen's.
- **`format.ts:62` and `change-units-table.tsx:96` hold the same *"a rung this console does not
  recognise"* string, and the two copies are NOT interchangeable** —
  `change-units-table.test.ts:63` asserts the change-unit path must *not* reach the "does not
  recognise" branch. Deduplicating them would make that test vacuous.

---

# Tasks

Eighteen tasks. Each is independently landable and independently reviewable. Take the next free work
item number from `docs/superpowers/WORKLOG.md` (highest at the time of writing: **W362**), add the row
before the first commit, and carry `M14-W<n>` in every commit subject for the task.

---

## Phase 0 — truth and instruments

### Task 1: Make the citations true and file the six new backlog items

**Files**
- Modify: `.claude/rules/console-surface.md` (the spacing count at `:31-33`)
- Modify: `docs/superpowers/plans/2026-08-05-sync-console-architecture.md` (**anchors only**, `:102-207`)
- Modify: `src/sync/dashboard/adapters.py` (`:47-53`)
- Modify: `web/src/api/types.ts` (`:753-755`)
- Modify: `docs/superpowers/BACKLOG.md` (B173–B178; a note on the B150 id collision; a correction to
  B147's stated cause)
- Test: none — this is a documentation and comment task. Verification is re-reading the diff against
  the facts in *Corrections to stale citations* above.

**Interfaces**
- Consumes: the verified facts in this plan's *Corrections* section.
- Produces: backlog identifiers B173–B178 that later tasks cite by name.

- [ ] **Step 1:** Fix `.claude/rules/console-surface.md:31-33` to read four spacing tokens and one
      named exception, and point at `DESIGN.md:641-661` rather than restating the values. Do not add a
      copy of the values — a fact written twice will disagree with itself.
- [ ] **Step 2:** In `2026-08-05-sync-console-architecture.md:102-207`, update **only the file:line
      anchors**, using the current locations in this plan's *Protected sentences that move* table.
      **Do not edit a single quoted sentence.** Add a dated line under the section heading saying the
      anchors were reconciled on 2026-08-17 and that the sentences themselves are unchanged.
- [ ] **Step 3:** Replace the false intake claim in `adapters.py:47-53` and `types.ts:753-755` with the
      truth: the attempt record exists at `schema.sql:514-531` and `GraphStore.intake_attempts()`
      reads it; what is missing is a route, filed as B178. Keep both comments the same length or
      longer — neither is one of the twenty-four, but shortening a limitation note is the habit this
      repository is trying to break.
- [ ] **Step 4:** File B173, B174, B175, B176, B177 and B178 in `BACKLOG.md`, each with the file:line
      evidence from the *Blocked prerequisites* section above and the condition that closes it.
- [ ] **Step 5:** Correct B147's entry: the cause is the `{repo_id}` path converter at `app.py:422-423`,
      not an empty payload, and the proposed 200-with-empty-payload fix would not close it because the
      reader is never reached. Include the live verification (`/api/repositories/r1/coverage` → 200,
      the URL-encoded real id → 404) and the reason no test caught it (every fixture uses `r1`).
- [ ] **Step 6:** Add a note beside `BACKLOG.md:4266` recording that `B150` is a duplicate identifier.
- [ ] **Step 7:** Re-read the whole diff for a deleted qualification. Run `uv run pytest tests/ -q`.
- [ ] **Step 8:** Commit: `docs: M14-W<n> reconcile the console's citations with the tree`

---

### Task 2: Close the two holes in the protected-sentence guard

**Files**
- Modify: `tests/test_console_honesty_sentences.py`
- Test: the file is its own test.

**Interfaces**
- Consumes: `web/src/**/*.ts`, `web/src/**/*.tsx`, and `web/src/lib/routes.ts`'s element imports.
- Produces: a guard that fails when a protected fragment survives only in an unmounted module or only
  in a test file.

The guard as written proves a fragment exists **in a file**, not **on screen** — and it is green right
now while four protected sentences render nowhere, under a test named `..._is_still_on_screen`. That
is a test that cannot fail for the defect that has already occurred. Its exclusion filter is
`not path.name.endswith(".test.ts")`, which does not exclude `.test.tsx`.

- [ ] **Step 1:** Write the failing test first: assert that every fragment appears in a module
      **transitively reachable** from a `RouteEntry.element` or `DestinationEntry.element` import in
      `routes.ts`. Build the reachability set by parsing `import … from "@/…"` specifiers and walking
      from the registry's element imports; treat an unresolvable specifier as a hard failure rather
      than as unreachable, so a parser gap cannot silently widen the set.
- [ ] **Step 2:** Run it. Watch it go **RED** naming the four orphaned modules — `runs-table.tsx`,
      `corpus-summary.tsx`, `repositories-table.tsx`, `detectors-summary.tsx`. Record the exact
      failure output in the commit body; it is the evidence the guard bites.
- [ ] **Step 3:** Change the source filter to exclude `.test.ts`, `.test.tsx` and any file under a
      `__tests__` directory. Prove it bites by temporarily moving one fragment into a `.test.tsx` file
      and watching the test go red.
- [ ] **Step 4:** Mark the four currently-unreachable modules with an explicit, dated, **expiring**
      allow-list naming Task 4 and Task 17 as what removes each entry, so the guard can land before the
      remounts do. `.claude/rules/console-hierarchy.md:39-40` is the rule the expiry obeys: *"a stated
      exception is a licence with a scope, and the scope decays."* Assert the allow-list is non-growing
      by pinning its length.
- [ ] **Step 5:** Run green. Run `uv run pytest tests/ -q`.
- [ ] **Step 6:** Commit: `test: M14-W<n> the honesty guard proves a sentence is on screen, not in a file`

---

### Task 3: Repair the visual eval's two mispaired rows and teach it the new routes

**Files**
- Modify: `web/scripts/visual-eval.mjs` (the `PAGES` array at `:363-371`)
- Test: two consecutive runs must be byte-identical; that is the instrument's own acceptance test and
  it has failed before.

**Interfaces**
- Consumes: `docs/console-mock/Sync Console.dc.html`, the running console and API.
- Produces: a per-property delta table that later tasks are measured against.

Two of the seven rows compare non-corresponding screens. The mock's nav index 4 (`observe`) opens the
**binding surface** and index 5 (`remediation`) opens the **finding** screen
(`docs/console-mock/Sync Console.dc.html:692-694`), while the eval routes the console side to
`/detectors` and `/findings/:id/workflow` (`visual-eval.mjs:368-369`). Confirmed live: nav 4 yields the
heading `chat.completions.create` and nav 5 yields `max_tokens removed`.

- [ ] **Step 1:** Re-point nav 4 at the binding surface route and nav 5 at `/findings/:findingId`. Add
      the mock's remaining drawn screens that now have a console counterpart. **The mock draws ten
      screens and the eval measures seven** — say which three are still unmeasured rather than
      pretending the set is complete.
- [ ] **Step 2:** Add rows for the three new routes as they land (`/repositories/:repoId/services`,
      `/repositories/:repoId/services/:vendorId`, `/repositories/:repoId/vendors`), each paired against
      the mock screen that draws the nearest thing, or marked as having no drawn counterpart. A row
      with no counterpart reports the console side alone; it does not invent a mock number.
- [ ] **Step 3:** Add a one-line comment beside `framePadding` recording that it is a measurement
      artifact — it reads `padding-left` on `main` while the mock pads an inner container
      (`Sync Console.dc.html:97`, `padding:16px 40px 40px`), so it reports 0px for a 40px frame — and
      that it must not order work. Do **not** delete it; a known-artifact row that is labelled is
      cheaper than a row somebody re-adds.
- [ ] **Step 4:** Run the eval twice. Assert byte-identical output. If it is not, the readiness check
      has regressed and that is the finding, not the numbers.
- [ ] **Step 5:** Record the corrected baseline in
      `docs/superpowers/reports/2026-08-17-visual-eval-first-run.md` as a dated appendix. Do not
      rewrite the settled numbers at `:343-360`; append.
- [ ] **Step 6:** Commit: `fix: M14-W<n> the visual eval compares the screens it says it compares`

---

## Phase 1 — the shell

### Task 4: Remount the four orphaned cards and repair the two false spatial claims

**Files**
- Modify: `web/src/features/fleet/fleet-page.tsx`, `web/src/features/fleet/screen-limits.tsx`
- Modify: `web/src/features/detectors/detectors-page.tsx`
- Modify: `web/src/features/fleet/repositories-table.tsx`,
  `web/src/features/fleet/detectors-summary.tsx` (mount only; prose untouched)
- Modify: `tests/test_console_honesty_sentences.py` (remove two allow-list entries)
- Test: `web/src/features/fleet/fleet-page.test.tsx`,
  `web/src/features/detectors/detectors-page.test.tsx`

**Interfaces**
- Consumes: `/api/repositories`, `/api/detectors`.
- Produces: rows 9, 10, 11, 17 and 18 of the protected-sentence table.

`RepositoriesCard` and `DetectorsSummaryCard` have zero non-test importers, so three protected
sentences render nowhere. `RunsCard` and `CorpusSummaryCard` stay orphaned until Task 17, because
their destination is blocked on B149 and mounting them fleet-wide on a repository screen is exactly
what ruling 1 rejected.

- [ ] **Step 1:** Write the failing vitest assertions: the Overview's rendered text contains
      *"Every repository the API Dependency Graph holds at least one call site from"*, and `/detectors`
      contains its `#24` instance. Run them, watch both go **RED**.
- [ ] **Step 2:** Mount `RepositoriesCard` on the Overview and `DetectorsSummaryCard` on `/detectors`.
      **The compressed footnote at `fleet-page.tsx:136` stays** — it is a second copy of the same fact
      in a different register, and deleting it while the full sentence lands elsewhere is a judgement
      this task is not making. Flag it for the reviewer instead.
- [ ] **Step 3:** Reword `screen-limits.tsx:22` and `:38` so each names a screen that exists. `:22`
      names the Codebase screen; `:38` names the per-repository Vendors list. Neither may get shorter.
- [ ] **Step 4:** Remove exactly two entries from Task 2's allow-list and re-run
      `uv run pytest tests/test_console_honesty_sentences.py -q`.
- [ ] **Step 5:** Gates: `npm run build`, `npm run lint`, `npm test`, `uv run pytest tests/ -q`.
- [ ] **Step 6:** Commit: `fix: M14-W<n> three protected sentences render again`

---

### Task 5: Invert the chassis — one full-height sidebar, the top bar inside the content column

**Files**
- Modify: `web/src/layouts/app-frame.tsx`
- Create: `web/src/layouts/app-sidebar.tsx`
- Delete: the `AreaRail` component from `app-frame.tsx`
- Test: `web/src/layouts/app-frame.test.tsx`, `web/src/layouts/app-sidebar.test.tsx`

**Interfaces**
- Consumes: `ROUTES`, `DESTINATIONS`, `boundParams`, `destinationHref` from `lib/routes.ts`.
- Produces: the chassis every screen renders inside.

Today `AppFrame` renders a full-width `<header role="banner">` as a **sibling before** the
`SidebarProvider` (`app-frame.tsx:352-374`), and the rail and sidebar are pushed under it with
`sticky top-12 h-[calc(100vh-3rem)]`. The owner's instruction is that the top bar must not sit in
front of the sidebar. Mock v1 already renders exactly this: its `<nav>` measures `{x:0, y:0, 246×900}`
and its `<header>` starts at `x:246`, `1194×121`.

**This breaks a tested structural invariant on purpose.** `app-frame.test.tsx:169-180` asserts the
banner does not contain the rail *and* that the rail follows the banner in document order, under the
name *"puts the bar above the rail rather than inside the scrolling column"*. The inversion reverses
the second assertion. The replacement invariant must be at least as strong.

- [ ] **Step 1:** Rewrite `app-frame.test.tsx:169-180` as its inverse **first**, and run it: the
      sidebar must **precede** the banner in document order; the banner must **not** contain the
      sidebar; the banner must be inside the element that also contains `<main>`; and the sidebar's
      computed height must not be reduced by the banner. Watch it go **RED** against the current tree.
- [ ] **Step 2:** Add the assertion that no destination is lost: every parameterless route and every
      `DESTINATIONS` entry renders as a real `<a href>` from the chassis at `/`. This is the
      reachability guarantee `routes.test.tsx:86-98` already holds; restate it here because the
      component that satisfied it is being deleted.
- [ ] **Step 3:** Extract the sidebar into `app-sidebar.tsx`. Delete `AreaRail` and its icon map. The
      new tree is `<div class="flex min-h-svh">` → `<AppSidebar/>` (full height, `x:0`) → a content
      column holding `<ErrorSurface/>`, `<header role="banner">` and `<main>`.
- [ ] **Step 4:** **Record the `ErrorSurface` decision explicitly in the SDD ledger.** Today it renders
      above the header and displaces the whole chassis including the rail; inside the content column it
      displaces only the content. `app-frame.test.tsx:215-230` passes either way, so the change is
      invisible to CI. It is correct with a full-height sidebar — the navigation should survive a
      panel's failure — but it is a decision, not a side effect.
- [ ] **Step 5:** Fix the two token violations already sitting in this file while it is open:
      `text-emerald-400` at `:281-283` is a stock Tailwind palette colour that is not in the ramp (the
      colour guard only catches hex and colour-function literals, so nothing fails on it), and
      `text-base` is a substrate step where `DESIGN.md:595` says code this project writes uses the seven
      role names.
- [ ] **Step 6:** Sidebar surface, all existing tokens: `bg-sidebar` (which resolves to the page plane),
      right edge `border-r border-line`, rows at `row-sm`/`row-md`, hover `--color-surface-subtle`,
      current page `--color-surface-emphasis`, containing scope `--color-surface-scope`, icons
      `--color-graphics`, labels `--text-body`, group labels `.furniture text-meta text-ink-muted`,
      padding `px-row`/`py-section`/`gap-field`, row radius `--radius-control`. **No elevation token** —
      a sidebar does not occlude and it has a border.
- [ ] **Step 7:** Run the suite green. Gates: `npm run build`, `npm run lint`, `npm test`.
- [ ] **Step 8:** Commit: `feat: M14-W<n> one full-height sidebar, the bar inside the content column`

---

### Task 6: Two regions replace six areas in the registry

**Files**
- Modify: `web/src/lib/routes.ts` (delete `AREAS`, `Area`, `AreaEntry`, `areaForPathname`; add `region`)
- Modify: `web/src/layouts/app-sidebar.tsx`, `web/src/layouts/command-palette.tsx`
- Test: `web/src/lib/routes.test.tsx`

**Interfaces**
- Consumes: nothing new.
- Produces: `RouteEntry.region`, read directly by the sidebar. One grouping, nothing to drift.

`routes.test.tsx:48-55` pins `AREA_IDS` as a literal and `:123-125`, `:127-134`, `:136-143`,
`:145-150` assert the partition. All of that goes. `GRAPH_LEVELS` and
`tests/test_console_hierarchy.py` are **untouched** and must stay green without editing.

- [ ] **Step 1:** Write the two new invariants as failing tests: no `root` route declares `repoId`;
      every `repository` route declares `repoId` as `params[0]`, except for the three-path literal
      allow-list whose `params` equal `["findingId"]`. Run them, watch them go **RED**.
- [ ] **Step 2:** Add the `region` field to every entry, delete the area machinery, and delete
      `areaForPathname`'s consumers. `area.purpose` disappears with `AREAS`; it is not one of the
      twenty-four and was added by M7-W171's own pass, so it is deleted rather than relocated
      (`CLAUDE.md`: *delete rather than deprecate*).
- [ ] **Step 3:** Update `command-palette.tsx` — it already groups by `GRAPH_LEVEL` (`:207-209`) and
      keeps `DESTINATIONS` under its own "Deployment" heading (`:84`), so it needs the import change and
      nothing structural. Confirm every route still appears in the palette.
- [ ] **Step 4:** Add a comment beside the allow-list naming **B177** as what retires it, and citing
      `types.ts:135-145` for why `RiskRow` cannot build a nested href.
- [ ] **Step 5:** Run green. Run `uv run pytest tests/test_console_hierarchy.py -q` and confirm it passes
      **without having been edited** — that is the proof the hierarchy did not move.
- [ ] **Step 6:** Commit: `refactor: M14-W<n> the sidebar's regions are the registry's regions`

---

### Task 7: The repository switcher moves into the sidebar, between the two regions

**Files**
- Modify: `web/src/layouts/scope-switchers.tsx`, `web/src/layouts/app-sidebar.tsx`
- Test: `web/src/layouts/scope-switchers.test.tsx`, `web/src/layouts/app-sidebar.test.tsx`

**Interfaces**
- Consumes: `GET /api/repositories` (a bare `{repo_ids: string[]}` — no display name, no counts,
  `fleet.py:203-207`), `boundParams(pathname)`.
- Produces: the sidebar's containment mark and the repository region's subject.

**Ruling 4 sets the order and it beats the owner's literal "switcher at the top":** the brand block is
at the very top, then the **root region**, then the switcher, then the **repository region**. The
owner's words and ruling 4 conflict by one row; ruling 4 is the later and more specific instruction,
and it carries a reason — a fleet-wide detector view answers a question the scoped copies cannot, so
it must not be reachable only by first picking a repository.

**Visual separation of the two regions**, all existing tokens: a `.furniture text-meta text-ink-muted`
group label over each (*"Across every codebase"* and the selected repository's own name), a
`border-t border-line` hairline above the switcher, and **`--color-surface-scope` painting the
repository region's containing mark** — which is precisely the job that token was declared for
(`DESIGN.md:171-185`), and it currently has exactly one consumer. The current-page mark stays at
`--color-surface-emphasis`, so the two tiers are carried by two different steps rather than by
position alone.

- [ ] **Step 1:** Write the failing test: the switcher's rendered value equals the `repoId` bound by the
      address and **nothing else**; navigating to a route with no `repoId` clears it. The governing rule
      is `scope-switchers.tsx:10-18` — *"a bar that remembered a repository would eventually name one
      while another repository's screen rendered beneath it."* The value comes from the URL; the options
      come from a query.
- [ ] **Step 2:** Assert the sidebar renders the root region **before** the switcher in document order,
      and the repository region after it.
- [ ] **Step 3:** Move the repository picker out of `ScopeTrail` into the sidebar. `ScopeTrail` keeps the
      breadcrumb it is for and stays in the top bar; it stops owning the repository popover.
- [ ] **Step 4:** **The on-page repository list stays on the Overview.** `fleet-page.tsx:29-34` records
      why: the absence footnote points at *"the repository list below"*. Assert it is still there.
- [ ] **Step 5:** Run green. Gates.
- [ ] **Step 6:** Commit: `feat: M14-W<n> the repository switcher sits between the sidebar's two regions`

---

### Task 8: Expand and minimise

**Files**
- Create: `web/src/layouts/sidebar-collapse.ts`, `web/src/layouts/sidebar-collapse.test.ts`
- Modify: `web/src/layouts/app-sidebar.tsx`, `DESIGN.md`
- Test: `web/src/layouts/app-sidebar.test.tsx`

**Interfaces**
- Consumes: `localStorage` under one key.
- Produces: two widths and a `data-state`.

**Keep `collapsible="none"` and own the two widths here.** The vendored `Sidebar`'s `collapsible="icon"`
path carries `transition-[width]` (`web/src/vendor/supabase/ui/sidebar.tsx:226`) and is **exempt from
`test_nothing_transitions_geometry_anywhere` by path**, so adopting it would animate the width for a
default user while CI stayed green. `DESIGN.md:786-833`'s motion test is **frequency, not duration**: a
surface the operator crosses repeatedly takes no transition at all. `layouts/` is outside the
raw-spacing guard's scope (`tests/test_console_design_tokens.py:305-309`), so the two widths are
legitimately spelled there — but they are argued in `DESIGN.md` first, not assumed.

The binding constraint, carried from M7-W160's own commit body (`0543341`) and the reason M7-W171
(`73b7654`) deleted the previous attempt: **collapsing changes density, not navigation.** Every
destination reachable expanded stays reachable collapsed; an icon must not move vertically across the
state change; prose that renders at one width and not the other is banned, because it changes the
height of every row beneath it.

- [ ] **Step 1:** Argue the three values into `DESIGN.md` in their own commit, before spending them: the
      expanded width (15rem/240px), the collapsed width (**3rem/48px, which settles the standing
      contradiction between `DESIGN.md:177`'s "48px column" and the shipped rail's `w-10`**), and the
      top bar's 48px `h-12`. Say plainly that these are page-layout numbers used once per view under the
      `DESIGN.md:657-661` carve-out, and that they live in `layouts/` for that reason.
- [ ] **Step 2:** Write the failing structural test first: the ordered list of row identities the
      sidebar renders is **identical** in both states, and each row's vertical offset is unchanged. This
      is M7-W160's own guard shape (`app-frame.test.tsx:103-124`, `:354-366`) and it was proved red
      twice. Watch it go **RED**.
- [ ] **Step 3:** Restore the **reserved group-heading row**: at the collapsed width the heading's text
      goes `sr-only` and the row keeps its height, rather than the row going to zero height. That is
      what keeps every icon at the same vertical offset.
- [ ] **Step 4:** Build the control. It is an explicit button carrying `aria-expanded`, a `title`, and
      an `sr-only` label. **No `window.innerWidth` read and no auto-collapse** — M7-W171 deleted a
      `collapsed` state initialised from a viewport width read once at mount with no resize listener,
      which meant an operator's choice did not survive a resize. The operator's explicit choice persists
      in `localStorage`; nothing infers one.
- [ ] **Step 5:** Assert no CSS transition on width in the non-vendored path, and that `prefers-reduced-motion`
      is irrelevant here because there is nothing to reduce.
- [ ] **Step 6:** Run green. Gates.
- [ ] **Step 7:** Commit: `feat: M14-W<n> the sidebar expands and minimises without moving a row`

---

## Phase 2 — the addresses

### Task 9: Nest the binding surface under the repository and the service

**Files**
- Modify: `web/src/lib/routes.ts`, `web/src/App.tsx`
- Modify: `web/src/features/bindings/binding-surface-page.tsx`
- Modify: every in-app link to the old path (`vendor-findings-table.tsx`, `change-units-table.tsx`,
  `finding-page.tsx` — grep before assuming the list)
- Test: `web/src/lib/routes.test.tsx`, `web/src/features/bindings/binding-surface-page.test.tsx`

**Interfaces**
- Consumes: `GET /api/vendors/{vendorId}/operations/{operationId}/bindings?repo_id=&path_prefix=&binding_rung=`
  — the richest scoped route in the API (`app.py:317-335`), already taking `repo_id` as a query
  parameter.
- Produces: `/repositories/:repoId/services/:vendorId/operations/:operationId`.

The scope moves out of the `?repo_id=` search key and into the path. `REPO_SCOPED_PATHS`
(`scope-switchers.tsx:65-69`) loses this entry, and the "a path parameter wins over the search key"
rule at `:111-118` stops having to arbitrate for it.

- [ ] **Step 1:** Write the failing route test: the new path resolves to `BindingSurfacePage`, declares
      `repoId` first, and satisfies Task 6's region invariant. Watch it go **RED**.
- [ ] **Step 2:** Write the failing redirect tests, both branches: the old path with `?repo_id=R` lands
      on the nested address with `replace`; the old path without it lands on `/vendors/:vendorId`.
- [ ] **Step 3:** Implement. Delete the old `RouteEntry` and add the redirect as a plain `<Route>` in
      `App.tsx` — it is not a registry entry, because it is not a destination.
- [ ] **Step 4:** **Keep the `FooterBar`.** Protected sentence #10 is rendered as its `left` slot
      (`binding-surface-page.tsx:508-522`), so it is structurally bound to a paginated table. Assert the
      fragment is still present after the change.
- [ ] **Step 5:** Rename the *"the repository's own coverage page"* referent at `:269-270` to name the
      Codebase page. Check that `:252` (*"the repositories above"*) and `:260-261` (*"see below…"*) are
      still true of the rendered order.
- [ ] **Step 6:** Run green. Gates, plus `uv run pytest tests/test_console_honesty_sentences.py -q`.
- [ ] **Step 7:** Commit: `feat: M14-W<n> the binding surface is addressed inside its repository`

---

### Task 10: The API services list

**Files**
- Create: `web/src/features/services/services-list-page.tsx`, `…/services-list-page.test.tsx`
- Modify: `web/src/lib/routes.ts`
- Test: as above, plus `web/src/lib/routes.test.tsx`

**Interfaces**
- Consumes: `GET /api/repositories/{repo_id}/coverage` → `{repo_id, by_vendor: Tally,
  last_indexed: Record<string,string>, total_call_sites}` (`graph_views.py:249-258`,
  `types.ts:620-625`); `GET /api/overview?repo_id=` for the per-vendor open-finding counts.
- Produces: rows linking to `/repositories/:repoId/services/:vendorId`.

**Depends on B147 to be observable.** The route 404s for every real repository id because of the path
converter; the reader itself already returns a well-formed empty payload for a repository with no rows
(`graph_views.py:249-258`), so the screen can be built and unit-tested against the `r1`-shaped fixture
id now and observed once B147 lands. **Say that in the commit rather than reporting a screen you could
not open.**

- [ ] **Step 1:** Write the failing test: the page renders one row per vendor in `by_vendor`, each with
      its call-site count and its own `last_indexed` timestamp; a repository with an empty `by_vendor`
      renders the never-indexed sentence rather than `0 services`.
- [ ] **Step 2:** The empty state reuses the existing protected sentence at `index-coverage-card.tsx:73`
      — *"This repository was never indexed, or it was indexed and nothing bound to a vendor was
      found…"* Import it rather than writing a third copy; a fact written twice will disagree with
      itself.
- [ ] **Step 3:** Page anatomy: `PageHeader`, `ControlBar` with the grain statement, a fact row
      (services, call sites, newest index), the table, a `FooterBar` with the count. `regionsBeside`
      target **≥ 2**.
- [ ] **Step 4:** Run green. Gates. Note in the commit which panels could not be observed and why.
- [ ] **Step 5:** Commit: `feat: M14-W<n> a repository's API services, listed`

---

### Task 11: The vendors list

**Files**
- Create: `web/src/features/vendors/vendors-list-page.tsx`, `…/vendors-list-page.test.tsx`
- Modify: `web/src/lib/routes.ts`
- Test: as above

**Interfaces**
- Consumes: `GET /api/overview?repo_id=` → `vendors` (**scoped to vendors with an open finding** —
  `scope-switchers.tsx:293-296` already carries this caveat), `GET /api/adapters` (unpaginated, one row
  per vendor, each carrying its own `sources` array — `adapters.py:37-74`, `types.ts:736-760`).
- Produces: rows linking to `/vendors/:vendorId`.

Ruling 3's first half. **The list is repository-scoped; each row opens the vendor's own vendor-wide
record.** The row must say which of its figures are repository-scoped and which are vendor-wide, in
prose, because they sit in the same row.

- [ ] **Step 1:** Write the failing test: a vendor with **no** open finding is absent from
      `overview.vendors` but is still present in `/api/adapters` — assert the page renders it and says
      so, rather than reporting a shorter list as the whole truth. This is the absence-versus-zero rule
      applied to a list, and it is the defect the caption at `scope-switchers.tsx:293-296` already names.
- [ ] **Step 2:** Implement, sourcing the vendor set from `/api/adapters` and the per-vendor open-finding
      counts from the scoped overview, with a sentence stating that the count is this repository's and
      the delivery record is the vendor's.
- [ ] **Step 3:** Page anatomy as Task 10. `regionsBeside` target **≥ 2**.
- [ ] **Step 4:** Run green. Gates.
- [ ] **Step 5:** Commit: `feat: M14-W<n> the vendors this repository calls`

---

## Phase 3 — the pages

### Task 12: The Overview stays the Overview, and sentence #1 becomes true

**Files**
- Modify: `web/src/features/fleet/fleet-page.tsx`, `web/src/lib/routes.ts` (the two `"Codebases"`
  labels at `:110` and `:186`)
- Test: `web/src/features/fleet/fleet-page.test.tsx`

**Interfaces**
- Consumes: unchanged.
- Produces: row 1 of the protected-sentence table.

**Ruling, recorded because the instructions pull in two directions.** The owner asked for *"a more
simple landing page with the list of different repos"* and, in the same breath, that *"the overview
should include how to set everything up and dashboards about that workspace/repo codebase"*. The
second sentence's subject is *that* workspace/repo codebase — the selected one — so the setup content
belongs on the **Codebase** page (Task 13), where one context fetch is one repository and where B148's
N+1 shape is avoided entirely. **The Overview gains no region.** That is the only reading in which
"more simple" is true, and it is surfaced as open question 5 for the owner to reverse cheaply.

- [ ] **Step 1:** Write the failing assertion: `FactTile` and `ScreenLimitsCard` are **siblings in a
      two-column grid**, not stacked in one column. Today `fleet-page.tsx:112-127` renders
      `grid gap-section xl:grid-cols-2` with exactly **one** child. Watch it go **RED**.
- [ ] **Step 2:** Fix the band so the words *"the panel beside them names what none of these figures
      can tell you at all"* describe the rendered layout. **The sentence's text is not edited.** Record
      in the commit body that this is a repair of an already-false claim, not the preservation of a true
      one.
- [ ] **Step 3:** Rename the route label at `routes.ts:186` from `"Codebases"` to `"Overview"`,
      finishing what M14-W362 started at the screen level. `GRAPH_LEVELS` keeps `"Fleet"` — a display
      rename is not a hierarchy change, and `tests/test_console_hierarchy.py` must stay green untouched.
- [ ] **Step 4:** Re-run `prose-audit.mjs` on `/` and confirm `proseChars` did not grow.
      `regionsBeside` target: **no increase**.
- [ ] **Step 5:** Run green. Gates.
- [ ] **Step 6:** Commit: `fix: M14-W<n> the panel beside them is beside them`

---

### Task 13: The Codebase page's setup region

**Files**
- Create: `web/src/features/repositories/repo-context-card.tsx`, `…/repo-context-card.test.tsx`
- Modify: `web/src/api/client.ts`, `web/src/api/types.ts`,
  `web/src/features/repositories/codebase-page.tsx`
- Test: as above

**Interfaces**
- Consumes: `GET /api/repos/{repo_id:path}/context` → `{repo_id, body, source, updated_at}` where
  `source` is `"seeded-file"` or `"operator"` (`graph_views.py:590-612`, `schema.sql:495-509`).
- Produces: the "how to set everything up" content the owner asked for.

**This route has never been called by the console.** It is one of three the client does not know
(`/api/corpus/health` and `/api/corpus/abandonment` are the others). It is also **the one
repository-scoped route that already models absence correctly** — it returns an empty body rather than
a 404 when nothing is recorded — and it uses `{repo_id:path}`, so it works for real repository ids
where the two B147 routes do not.

`POST /api/repos/{repo_id}/context` is **the only write on the entire API**
(`app.py:373-403`). Any "set everything up" affordance is limited to this one field; nothing else can
be configured through the transport, and this task does not add a write.

- [ ] **Step 1:** Write the failing test: an absent context renders the never-measured distinction — *no
      context has been written* is not *this repository has none to write* — and a present one names its
      `source`, because an operator's note and a customer-committed `.sync/context.md` are different
      facts and an operator edit to a seeded row is overwritten on the next index.
- [ ] **Step 2:** Add `repoContext()` to `client.ts` and `RepoContext` to `types.ts`. Do **not** add the
      POST; this plan does not add a write.
- [ ] **Step 3:** Implement the card and mount it on the Codebase page. **No composite readiness score,
      no green tick, no progress ring** — a setup panel is exactly the place somebody reaches for one.
      Each step is a recorded value from a closed vocabulary, legible without its colour.
- [ ] **Step 4:** Run green. Gates.
- [ ] **Step 5:** Commit: `feat: M14-W<n> a repository says what it has been told about itself`

---

### Task 14: The API service page

**Files**
- Create: `web/src/features/services/service-page.tsx`, `…/service-page.test.tsx`
- Modify: `web/src/lib/routes.ts`
- Test: as above

**Interfaces**
- Consumes: `GET /api/vendors/{vendorId}?repo_id=&severity=&path=&order=&limit=&offset=`
  (`app.py:218-252`) and the severity option list, which is **already scopable to repository and vendor
  together** (`app.py:245`, `graph_views.py:471-473`, `store.py:1160-1161`).
- Produces: the screen the owner meant by *"all the api services page that list all the different
  services and their code and logs and findings and telemetries for each service"*.

**What this page renders now, and what it does not.** Findings, scoped to this repository and this
vendor: **yes**. Bindings: **yes, bounded** — a bindings region lists the operations that appear in
this service's findings and change units, with a sentence saying that is the bound, because **nothing
lists a vendor's operations** (B176). Call sites, as locations: **only through an operation**, for the
same reason. Telemetry and logs: **not yet** (B173) — a link into the repository's Signals screen,
which is honest and preserves the referent at `codebase-page.tsx:150-156`. Detectors: **not yet**
(B175). Source text: **never** (B150, `BACKLOG.md:4266`).

- [ ] **Step 1:** Write the failing tests: the findings table is scoped to both ids; the severity filter
      options come from the scoped rollup; the ordering vocabulary is the server's closed set of two
      (`FindingOrder = "first-seen" | "severity"`, `types.ts:184`) and **the table offers no column
      sorting beyond it**.
- [ ] **Step 2:** Reuse `VendorFindingsTable`. Protected sentence #19 travels with it
      (`vendor-findings-table.tsx:354-357`) — assert the fragment renders here too.
- [ ] **Step 3:** Supply a **page-specific `bindingNullLabel`**. `provenance.tsx:9-10` says the envelope
      rung describes *the whole page*, and every existing call site names its own page's composition.
      Reusing the vendor page's label here would be a claim about a different page. Write both branches
      — `none:` and `mixed:` — and keep them distinguishable.
- [ ] **Step 4:** Page anatomy: fact row (open findings, call sites bound, operations at risk, newest
      change), then the findings table beside the bindings region. `regionsBeside` target **≥ 3**.
- [ ] **Step 5:** Add the workflow link region (Task 16's component) beneath the findings table.
- [ ] **Step 6:** Run green. Gates.
- [ ] **Step 7:** Commit: `feat: M14-W<n> what this repository does with one API service`

---

### Task 15: The vendor page, built from what exists

**Files**
- Modify: `web/src/features/vendors/vendor-page.tsx`
- Test: `web/src/features/vendors/vendor-page.test.tsx`

**Interfaces**
- Consumes: `GET /api/vendors/{id}/changes` (`app.py:285-291` — operation, change kind, path pointer,
  severity, from/to version, published at); `GET /api/adapters` (`sources` per vendor);
  `GET /api/vendors/{id}` for findings.
- Produces: ruling 2's page.

**Ruling 2 is the whole specification for this page.** Three evidence groups, and nothing else:

| Group | What it holds | Source |
|---|---|---|
| **Published** | spec versions and vendor changes: operation, change kind, path pointer, severity, from/to version, published at | `/api/vendors/{id}/changes` |
| **Delivered** | the adapter's own record — kind, source, change count, operation count, newest change, and the `sources` array | `/api/adapters` |
| **Observed** | traces this deployment recorded, at the grain the schema keeps them | `observed_call`, reached through the repository-scoped observed route |

**What is deliberately absent, and is a backlog item rather than an empty panel** (ruling 2, verbatim:
*"The categories that no stage captures — rate limits, API rules, call structures — are named as a
backlog item, NOT rendered as empty panels carrying the never-measured marker"*): rate limits, quotas,
auth rules, and any vendor spec document. Grep confirms nothing anywhere stores them; the nine tables
in `schema.sql` include no spec or document table.

Two honest limits this page must state rather than imply:

- **`VendorChange.raw` is not forwarded to the console.** `src/sync/mcp/tools.py:261-272` drops it. So
  the page shows *what the vendor published*, never the vendor's raw diff body.
- **`observed_call` never stores a URL.** `schema.sql:363-368`: *"The request URL never reaches a
  column"* — only the vendor's published template and a salted digest of the target. A "data traces"
  region that implied otherwise would be asserting something the schema deliberately refuses to hold.

- [ ] **Step 1:** Write the failing tests: three named groups render; a vendor with no adapter row
      renders the absence rather than an empty *Delivered* group; the changes table is **not**
      repository-scoped and says so (`types.ts:157-159` already records that decision).
- [ ] **Step 2:** Implement the three groups on the page anatomy. `regionsBeside` target **≥ 4** (it
      measures 4 today; the grouping must not cost a pairing).
- [ ] **Step 3:** Keep the vendor-changes `bindingNullLabel` at `vendor-changes-table.tsx:167`
      (*"none: this answer is built from vendor changes and holds no binding"*) — it is protected and it
      is correct for this page.
- [ ] **Step 4:** Add a sentence saying the page is **vendor-wide, not repository-scoped**, and that the
      repository's own view of this vendor is on its API service page. Do not restate any of the
      twenty-four; write a new sentence.
- [ ] **Step 5:** Run green. Gates.
- [ ] **Step 6:** Commit: `feat: M14-W<n> the vendor's own record, from what the graph actually holds`

---

### Task 16: The solution workflow, reachable from everywhere it is owed

**Files**
- Create: `web/src/features/workflows/workflow-link-card.tsx`, `…/workflow-link-card.test.tsx`
- Modify: `web/src/features/repositories/codebase-page.tsx`,
  `web/src/features/findings/finding-page.tsx`, `web/src/features/services/service-page.tsx`,
  `web/src/features/vendors/vendor-page.tsx`
- Test: as above

**Interfaces**
- Consumes: `GET /api/workflows/{finding_id}` (`app.py:293-298`) — which **already carries `repo_id`**
  (`queries.py:217`), so a workflow can legitimately be rendered under a repository heading, unlike the
  runs list.
- Produces: the summary card that travels, carrying the pull request link.

**The level does not move.** This is links and summary panels only; `/findings/:findingId/workflow`
still binds `findingId` and its specification parent is still Finding.

**One limit the card must state, because placing the workflow in four screens multiplies it:** the
route serves **only the newest generation**, and older attempts have no address at all
(`queries.py:94-103`; the `generations[]` array carries `thread_id`, `generation`, `outcome`,
`abandon_reason`, `report_reason` and nothing more). A retried finding's abandoned attempt is one
unlinked line. That is **B146**, and the card names it rather than rendering a link that would 404.

- [ ] **Step 1:** Write the failing test: the card renders the newest generation's node sequence and
      outcome, links to the workflow and, when one exists, to the pull request; a superseded generation
      renders as an unlinked line naming B146's limit.
- [ ] **Step 2:** Implement. The three protected workflow sentences travel with the components already:
      `node-sequence.tsx:69-70` (#22), `run-outcome.tsx:174-180` (#23), and the fullest form of #24 at
      `workflow-page.tsx:346`. Assert each fragment is still reachable.
- [ ] **Step 3:** Mount on the Codebase page, the Finding page, the API service page and the vendor
      page. **No composite progress figure and no liveness indicator** — `run-outcome` is one of the
      three channels a colour may carry, and it ships with an icon and a word.
- [ ] **Step 4:** Run green. Gates, plus `uv run pytest tests/test_console_honesty_sentences.py -q`.
- [ ] **Step 5:** Commit: `feat: M14-W<n> the solution workflow is reachable from every screen that owes it`

---

### Task 17: The Codebase page's runs and repairs regions — **BLOCKED ON B149**

**Files**
- Modify: `web/src/features/repositories/codebase-page.tsx`,
  `web/src/features/fleet/runs-table.tsx`, `web/src/features/fleet/corpus-summary.tsx`
- Modify: `tests/test_console_honesty_sentences.py` (remove the last two allow-list entries)
- Test: `web/src/features/repositories/codebase-page.test.tsx`

**Interfaces**
- Consumes: a repository-scoped `/api/runs` and `/api/corpus`, **neither of which exists yet**.
- Produces: rows 2–8 of the protected-sentence table.

**Do not start this task until B149 has landed.** Owner ruling 1: *"Do not design a fleet-wide-with-a-
label fallback; the owner rejected it."* The layout grid these two regions occupy is built by Task 12's
anatomy pass and left empty until then; that is the ruling's *"designed with those regions present in
the layout and implemented last"*.

- [ ] **Step 1:** Confirm B149 has landed and that `RunRow` carries `repo_id` and `/api/corpus` accepts a
      repository parameter. If either is false, stop and report; do not build against a payload that
      does not exist.
- [ ] **Step 2:** Write the failing tests: both regions render only rows for the addressed repository;
      `RunsCard`'s five protected fragments and `CorpusSummaryCard`'s two render on the Codebase page.
- [ ] **Step 3:** Mount both cards. Keep *"Counted across the {N} runs shown below, not the fleet"*
      (`runs-table.tsx:124-127`) **above** the table — its scope claim is bound to that position.
- [ ] **Step 4:** **Rewrite `corpus-summary.tsx:89-94` in this same commit and no earlier.** Its claim
      *"This one cannot be narrowed to a repository, and no screen below this level renders it"* becomes
      false the instant a repair figure renders here. The rewrite keeps both underlying facts —
      `migration_outcome` stores no repository, and nothing in it identifies a customer, which is what
      makes it safe to aggregate across them — and replaces the hierarchy clause with the join the
      payload now performs. **It is not shortened.** Quote the before and after in the commit body.
- [ ] **Step 5:** Re-check `screen-limits.tsx:22`'s reworded claim (Task 4) now that the runs table has
      a home.
- [ ] **Step 6:** Remove the last two entries from Task 2's allow-list; assert it is now empty and that
      the guard still runs.
- [ ] **Step 7:** Run green. Gates, plus `uv run pytest tests/ -q`.
- [ ] **Step 8:** Commit: `feat: M14-W<n> a repository's own runs and repairs, scoped by the payload`

---

### Task 18: The type ramp's middle, and the closing measured walk

**Files**
- Modify: every screen touched by Phase 3 (headings only)
- Modify: `docs/superpowers/reports/2026-08-17-console-mock-gaps.md` (a dated closing appendix)
- Test: `tests/test_console_design_tokens.py` must stay green untouched

**Interfaces**
- Consumes: `visual-eval.mjs`, `prose-audit.mjs`, `capture-console.mjs`.
- Produces: the recorded numbers this plan is judged on.

The measured gap: **18px appears on exactly one heading in the whole application**, while almost every
other `h2`/`h3` is 12px uppercase furniture — so a section heading renders at the same size as a table
column header. `--text-section` and `--text-emphasis` both exist and neither reaches a panel heading.

- [ ] **Step 1:** Apply the boundary rule from `DESIGN.md:523-543`, screen by screen: a heading that
      names a region a reader enters takes `--text-section`; a label that names a value beside or
      beneath it stays `.furniture text-meta text-ink-muted`. A card's own title inside a repeating grid
      takes `--text-emphasis`. `.furniture` beside `text-section` stays banned.
- [ ] **Step 2:** Confirm `test_exactly_one_component_spends_the_display_step` still holds —
      `--text-display` is `PageHeader`'s and nothing else's, once per route.
- [ ] **Step 3:** Run `visual-eval.mjs` **twice** and require byte-identical output before reading a
      number. Record every property against the targets table in this plan.
- [ ] **Step 4:** Run `prose-audit.mjs` on every screen this plan touched, **including the three that
      have never been audited** (`api-services`, `remediation`, `settings`). A prose cut is proposed only
      where discretionary characters exceed the mock's count for that screen; protected characters are
      never cut.
- [ ] **Step 5:** Run `capture-console.mjs`. Note that the 2026-08-17 capture set **skips the binding
      surface** — there is no `05`, while the mock's still set has `05-binding-surface.png` — and close
      that gap.
- [ ] **Step 6:** Write the closing appendix: every target met, every target missed with its number, and
      every blocked prerequisite still outstanding. **No score.**
- [ ] **Step 7:** Gates: `npm run build`, `npm run lint`, `npm test`, `uv run pytest tests/ -q`.
- [ ] **Step 8:** Commit: `feat: M14-W<n> the middle of the ramp, and the closing walk`

---

## SDD ledger

Rulings taken while writing this plan, each reversible by the owner at the cost of one fix round.
A controller executing this plan appends here rather than asking.

| # | Ruling | Decided against | Why |
|---|---|---|---|
| 1 | **Two lists, one vendor detail.** `/repositories/:repoId/vendors` is repository-scoped; `/vendors/:vendorId` stays the vendor-wide record | building a second, repository-scoped vendor detail screen | the seam is the payload's: `/changes` and `/api/adapters` take no `repo_id` (`app.py:76-79`). Two detail screens would disagree, and one would render vendor-wide facts under a repository heading. Also keeps ruling 4's fleet-wide findings surface alive |
| 2 | **Signals stays a repository screen** | dissolving it into the API service pages now | per-service narrowing is blocked (B173) and pagination is applied before any filter, so client-side narrowing would silently drop rows. Also preserves `codebase-page.tsx:150-156`'s referent |
| 3 | **`/detectors` is unchanged and a dedicated `/findings` list is not built** | inventing a fleet-wide findings screen | `detector_accountability` discards the finding rows (`graph_views.py:637-660`). Ruling 4 is satisfied because both global screens survive above the switcher; a new one needs B174 |
| 4 | **The Overview gains no region; the setup content lives on the Codebase page** | adding a setup panel and dashboards to `/` | *"a more simple landing page"* and *"how to set everything up"* pull opposite ways; the second sentence's subject is the selected codebase. This also avoids a second N+1 of B148's shape. Surfaced as open question 5 |
| 5 | **The root region sits above the switcher, contradicting the owner's literal "switcher at the top"** | putting the switcher in the first row | ruling 4 is the later, more specific instruction and carries a reason: a fleet-wide detector view must not require picking a repository first |
| 6 | **`collapsible="none"` with two widths owned in `layouts/`** | the vendored `collapsible="icon"` | that path animates width (`vendor/supabase/ui/sidebar.tsx:226`) and is exempt from the geometry-transition guard **by path**, so CI would stay green while the surface animated. Surfaced as open question 6 |
| 7 | **The collapsed width is 48px, not 40px** | keeping the shipped `w-10` | it settles a live contradiction between `DESIGN.md:177` and the rail, and matches the vendored `SIDEBAR_WIDTH_ICON` |
| 8 | **`ErrorSurface` moves into the content column** | keeping it above the chassis | with a full-height sidebar the navigation should survive a panel's failure. `app-frame.test.tsx:215-230` passes either way, so this is recorded rather than discovered |
| 9 | **`fleet-page.tsx:136`'s compressed footnote stays alongside the remounted full sentence** | deleting the footnote as a duplicate | it is a second register of the same fact, and deleting a protected qualification is not a call a task makes in passing. Flagged for the reviewer instead |

---

## Open questions for the owner

Reproduced from the adjudicated synthesis, ranked by what the wrong guess costs. **Each already has a
ruling in the ledger above so no task is blocked on an answer** — these are the decisions most worth
reversing early if the ruling is wrong.

1. **One vendor detail screen, or two?** minimal-move keeps a single `/vendors/:vendorId?repo_id=`
   serving both lists, arguing a second is an abstraction with one caller. layout-first and
   full-nesting split it into a *service* page (what this repo does with the vendor: call sites,
   findings, bindings, telemetry) and a *vendor* page (what the vendor is: published changes, adapter
   delivery, sources, traces), arguing the seam already exists in the payload — `/changes` and
   `/api/adapters` take no `repo_id`. The owner asked for services and vendors "at an equal stage" as
   two *lists*; whether each gets its own detail is genuinely undecided. Guessing wrong costs two
   screens and a sidebar section either way.

2. **Does a fleet-wide findings screen exist?** Ruling 4 says it "stays" — but no route has ever served
   one. `/api/detectors` returns per-detector aggregates with the finding rows discarded, and every
   findings page requires a vendor. The three answers are: build `/findings` (new route + B174), fold
   it into `/detectors` as detector attribution and say so, or keep today's de-facto answer
   (`/vendors/:vendorId` with no `repo_id`). Wrong guess costs a route, a payload change and a sidebar
   row.

3. **Signals: a repository screen, a per-service screen, or both?** The instruction is *"sources and
   signals should pertain to each of its api service"*, but per-service narrowing is blocked
   (`/observed` takes no vendor or operation filter, and pagination is applied before any filter so
   client-side narrowing is wrong). Shipping both means building a screen that later gets dismantled;
   shipping only the per-service one means Signals is dark until B173 lands.

4. **Does the unscoped vendor address survive?** layout-first and full-nesting delete it, so a service
   is always reached inside a repository. That removes the console's only fleet-wide findings surface
   and the sentence at `vendor-page.tsx:138-144` (which I confirmed is *not* one of the protected
   twenty-four, so the rule does not decide it). Interacts with question 2.

5. **How much belongs on Overview?** "More simple" and "should include how to set everything up and
   dashboards about that workspace/repo codebase" pull opposite ways, and all three proposals resolved
   it toward more. Cheap to move a region later, expensive to build the setup flow twice.

6. **Is an animated sidebar collapse acceptable?** *"just like how supabase has it"* most literally
   means the vendored `collapsible="icon"`, which animates width and is exempt from the
   geometry-transition guard by path. DESIGN.md's motion posture says a surface crossed repeatedly
   takes no transition. Cheapest to reverse of the six — one prop and two width constants.

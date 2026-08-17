# Console Mock to Build — Implementation Plan

> **Status, 2026-08-17:** Tasks 2 (frontend ChangeUnitsTable) partially shipped. Tasks 1 (mock gaps report), 3 (shared drawer), 5 (settings route), and 6 (palette test) remain open; these are absorbed into the new `2026-08-17-console-mock-parity.md` plan. Phases 1-6 structure migrated to that plan for reconciliation against what the tree actually contains.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the ten-screen mock in `docs/console-mock/` into shipped console, without letting a drawing overrule a specification.

**Input artifact:** `docs/console-mock/` — the mock, its twelve stills, its tour, and the provenance that says which of its facts are fixtures. That README is the description; this plan does not restate it.

**Architecture:** Six tasks. One measures, three are console-only, two are full-stack because the panel the mock draws needs an aggregate `sync.dashboard` does not compute. Nothing here adds a level: the nine in `web/src/lib/routes.ts` are the nine in the specification and this plan does not touch that count.

**Tech Stack:** unchanged — React 19, Vite, Tailwind v4, vendored Supabase components, vitest, pytest guards.

## Global Constraints

Identical to `plans/2026-08-07-console-fidelity-pass.md` — branch, gates, seam, vendored-files rule, honesty sentences, no score/dot/pulse, dark-only, Conventional Commits with the next WORKLOG number. Four additions, all specific to building from a mock:

- **The mock is the lowest authority in the room.** Where it disagrees with
  `specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445` (hierarchy), `DESIGN.md` (every
  visual value) or `.claude/rules/console-surface.md` (what may be said on screen), the mock loses
  and the disagreement is recorded in this plan's ledger rather than resolved silently.
- **A mock value that is not already in `DESIGN.md` is a proposal, not a measurement.** It gets
  added to `DESIGN.md` with its contrast arithmetic against the 5.05:1 floor in the same commit that
  first uses it, or it does not get used.
- **The mock's prose is not the shipped prose.** It paraphrases several of the twenty-four protected
  sentences. Porting a screen never shortens one to match the drawing;
  `tests/test_console_honesty_sentences.py` is the arbiter and it is deliberately not file-pinned.
- **No task in this plan is finished on a screenshot.** Rendered-pixel claims are measured in Chrome
  through `getComputedStyle`, per `.claude/rules/console-dev-loop.md`.

## What was measured before this plan was written

Three things, so the tasks below rest on facts rather than on a reading of a picture:

- **The mock is already on our token contract.** Its literal OKLCH values are the values
  `web/src/index.css` declares — background `oklch(0.19 0.0025 159)`, card `0.215`, popover
  `0.2275`, secondary `0.24`, foreground `oklch(0.95 0.00275 159)`. The colour work in porting a
  screen is therefore approximately zero, and any colour that *is* new is conspicuous.
- **`routes.ts` holds exactly nine `path:` entries** and the mock draws ten screens. The tenth,
  Settings & adapters, has **no route**, and the mock's own sidebar calls it "Not a level". That is a
  real gap rather than a mock error — see Task 5.
- **Fleet is nine components today** (`fleet-facts`, `repositories-table`, `runs-table`,
  `corpus-chart`, `corpus-summary`, `detectors-summary`, `vendor-distribution`, `cardinality`,
  `screen-limits`) and one dense table in the mock. That is the largest single delta in the set and
  the one with a backend dependency — see Task 2.

**What was not measured, and Task 1 exists to measure it:** the per-screen arrangement delta. This
plan does not assert that any specific shipped screen is wrong, because nobody has put the two side
by side under `getComputedStyle`.

## The screen map

Ten mock screens against what exists. **Delta** is the claim to be checked in Task 1, not a finding.

| Mock still | Level | Route | Shipped component | Delta to check |
|---|---|---|---|---|
| `01-fleet.png` | Fleet | `/` | `features/fleet/fleet-page.tsx` + 8 more | One change-unit table vs. nine panels (Task 2) |
| `02-codebase.png` | Codebase | `/repositories/:repoId` | `features/repositories/codebase-page.tsx` | Four fact tiles over a two-column split; "What Sync cannot see here" as a named panel |
| `03-vendor.png` | API Services | `/vendors/:vendorId` | `features/vendors/vendor-page.tsx` | Two panels above the findings table; "Where it was read from" has no shipped equivalent |
| `04-signals.png` | Signals | `/repositories/:repoId/observed` | `features/signals/signals-page.tsx` | Three role columns, each with its own caveat footer |
| `05-binding-surface.png` | Binding surface | `/bindings/vendors/:vendorId/operations/:operationId` | `features/bindings/binding-surface-page.tsx` | Shared-directory prefix strip above the rows (`lib/format.ts` `pathAfter` already does the halves) |
| `06-finding.png` | Finding | `/findings/:findingId` | `features/findings/finding-page.tsx` | Two rungs shown side by side with what each answers |
| `07-workflow.png` | Solution Workflow | `/findings/:findingId/workflow` | `features/workflows/workflow-page.tsx` | Node list beside an assembled activity timeline |
| `08-pull-request.png` | Pull Request | `…/workflow/pull-request` | `features/pullrequests/pull-request-page.tsx` | Policy action bar above a diff/evidence split |
| `09-detectors.png` | Errors & Incidents | `/detectors` | `features/detectors/detectors-page.tsx` | Per-detector rung breakdown plus a cross-detector tally (Task 4) |
| `10-settings.png` | **Not a level** | — none — | — none — | The destination does not exist (Task 5) |

Two mock surfaces are not screens and must not become routes: the **drawer** (`11-drawer.png`) opens
over a level, and the **command palette** (`12-palette.png`) is `layouts/command-palette.tsx`.

## Decisions this plan needs, and the ruling it takes by default

Per `.claude/rules/autonomous-development.md`, these are rulings a worker takes and records, not
questions that block. The owner can reverse any of them at the cost of one fix round.

1. **Is a change unit the Fleet's grain?** The mock says one row per vendor change × repository set,
   expandable to call sites. Today `migration_outcome`'s grain is one *attempt*.
   **Ruling: adopt it as a read-model grain only.** A change unit is computed in `sync.dashboard`,
   declared as a grain comment where it is computed, and no table changes. Collapsing at write time
   would destroy the attempt grain that routing learns from.
2. **Does Settings & adapters get a route?** **Ruling: yes, as a destination and not a level** —
   `/settings`, absent from the level count, absent from the breadcrumb trail's level positions, and
   listed in the palette under its own group. It renders read-only until M4's write path exists.
3. **Does the mock's "Review proposed patch" button ship?** **Ruling: no, not yet.** It is a write
   action on a read-only console. It ports as a *navigation* to the pull request level, which is
   what the mock's own handler does, and the write path stays M4's.
4. **The mock's fixtures do not ship.** `acme/payments-api`, `#4127` and the 1.2M-span window are
   layout weights. Every ported screen renders from `scripts/seed_console.py` or states its absence.

---

### Task 1: Measure the mock against what ships — no code

**Files:**
- Create: `docs/superpowers/reports/2026-08-08-console-mock-gaps.md`

**Interfaces:**
- Produces one row per mock screen: the arrangement shipped, the arrangement drawn, the measured
  numbers behind the difference (type range, frame ratio, side-by-side placements per screen, tile
  row width usage), and a verdict of **adopt / adapt / refuse** with a reason.
- Reads the same bars the substrate rebuild was judged against (type range against the 3.4 bar,
  frame ratio) so this report is comparable to `reports/2026-08-07-console-fidelity-gaps.md` rather
  than a fresh scale.
- **Refusals are first-class.** A mock panel that asserts something our data cannot support is
  recorded as a refusal with the sentence that replaces it.

- [ ] Step 1: Serve the mock (`docs/console-mock/README.md` has the command) and the console side by
      side at 1440×900; capture both per screen. Never port 5173.
- [ ] Step 2: Chrome-measure both through `getComputedStyle` — type sizes present, frame vs. gap,
      count of side-by-side placements. Numbers, not impressions.
- [ ] Step 3: Write the report; every row cites a file and a measurement. `clear_viewport`.
- [ ] Step 4: WORKLOG row; commit. **No `web/src` file changes in this task.**

### Task 2: Fleet's change-unit grain — full-stack (M12)

**Files:**
- Modify: `src/sync/dashboard/fleet.py`, `src/sync/dashboard/queries.py`
- Modify: `src/sync/api/` route module owning `/`; `web/src/api/`, `web/src/features/fleet/fleet-page.tsx`
- Create: `web/src/features/fleet/change-units-table.tsx`
- Test: `tests/test_dashboard_fleet.py`, `web/src/features/fleet/change-units-table.test.tsx`

**Interfaces:**
- Produces a `ChangeUnit` read model: vendor, operation, change kind, repository count, call-site
  count, **the rung the unit rests on**, standing, and last checkpoint age. The grain is declared as
  a comment where it is computed, per `.claude/rules/graph-grain.md`.
- **The rung is a column on the unit and every row still carries its own.** The mock's own drawer
  says two call sites inside a unit carry a weaker rung and say so; a unit-level rung that hid that
  would be exactly the collapse this console refuses.
- Checkpoint age renders as staleness, never liveness. No dot, no pulse.
- The nine existing Fleet panels are **not deleted by this task.** Which of them the table replaces
  is Task 1's verdict to make, and a panel removed before that report exists is a guess.

- [ ] Step 1: Failing pytest for the aggregate — a unit spanning three repositories counts once;
      an unattributed finding is refused; a unit with no run has no standing rather than a zero. RED.
- [ ] Step 2: Implement the aggregate; grain comment in the same commit.
- [ ] Step 3: Failing vitest for the table's derivations — classification and absence states only,
      never class names, never snapshots. RED.
- [ ] Step 4: Implement; wire behind the existing query client.
- [ ] Step 5: Chrome-measure at 1440×900 and 1280×800; full gate; WORKLOG; commit.

### Task 3: The drawer as one surface, not five (M7)

**Files:**
- Modify: `web/src/features/bindings/binding-drawer.tsx` → generalise, or extract to `web/src/components/detail-drawer.tsx`
- Modify: consumers on Fleet, binding surface and workflow
- Test: `web/src/components/detail-drawer.test.tsx`

**Interfaces:**
- One drawer: kicker, title, lede, label/value rows, a foot sentence, one call to action. The mock
  opens the identical shape from a fleet row, a call site and a workflow node, which is the argument
  for extracting it rather than writing it three times — *factor at the second use*.
- The foot sentence is per-caller and is where the honesty line lives (the mock's call-site drawer
  ends on the vendor edge carrying no rung, and that absence is the point).
- Escape closes; focus returns to the opener; `prefers-reduced-motion` honoured — the mock declares
  the media query and the port keeps it.

- [ ] Step 1: Failing vitest — opens with the caller's rows, closes on Escape, restores focus. RED.
- [ ] Step 2: Extract and adopt at all three call sites; delete the superseded path rather than
      deprecating it.
- [ ] Step 3: Gate; WORKLOG; commit.

### Task 4: Detector attribution's rung tally — full-stack (M12)

**Files:**
- Modify: `src/sync/dashboard/queries.py`; `web/src/features/detectors/detectors-page.tsx`,
  `features/detectors/rung-composition-chart.tsx`, `features/detectors/detector-accountability.tsx`
- Test: `tests/test_dashboard_detectors.py`, `web/src/features/detectors/*.test.tsx`

**Interfaces:**
- Produces the cross-detector tally the mock's lower panel draws: open findings by rung, **counted
  once per finding**, so a finding two detectors agree on is one row and not two.
- A rung with zero renders its zero and its sentence. The mock is explicit that nothing resting on
  `unresolved` is not the same fact as a rung this console does not have, and both must be
  distinguishable on screen.
- **No colour is assigned to a rung.** A rung is a class of evidence, not a position on a
  good-to-bad scale, and colouring the bars would smuggle in the ranking the rung exists to refuse.

- [ ] Step 1: Failing pytest — the once-per-finding count; a zero rung present; RED.
- [ ] Step 2: Implement the aggregate with its grain comment.
- [ ] Step 3: Failing vitest for the derivation and the two absence states; RED; implement.
- [ ] Step 4: Chrome-measure; gate; WORKLOG; commit.

### Task 5: Settings & adapters, read-only (M4)

**Files:**
- Create: `web/src/features/settings/settings-page.tsx`, `adapter-table.tsx`, `merge-policy-panel.tsx`
- Modify: `web/src/lib/routes.ts`, `layouts/app-frame.tsx`, `layouts/command-palette.tsx`
- Test: `web/src/features/settings/*.test.tsx`, `web/src/lib/routes.test.tsx`

**Interfaces:**
- `/settings` is a **destination, not a level.** `routes.test.tsx` gains a case asserting the level
  count is still nine, so this route cannot quietly become a tenth.
- The adapter table renders each adapter's source, operation count and last intake — and **an
  adapter that declined says why**, which is the screen's reason for existing. The mock's Cloudflare
  row (a catalogue that served an HTML error page) is the shape to build against.
- The merge policy renders **read-only** with the option in force named, per Decision 3. No control
  on this page mutates anything until M4's write path lands.

- [ ] Step 1: Failing vitest — level count unchanged at nine; a declined adapter renders its reason;
      policy renders the option in force. RED.
- [ ] Step 2: Implement against `sync.api`'s existing read surface; state absence where the API has
      no field yet rather than inventing one.
- [ ] Step 3: Reach it from the rail and the palette; walk all nine levels plus this one.
- [ ] Step 4: Gate; WORKLOG; commit.

### Task 6: The palette lists destinations honestly (M7)

**Files:**
- Modify: `web/src/layouts/command-palette.tsx`
- Test: `web/src/layouts/command-palette.test.tsx` (new if absent)

**Interfaces:**
- Groups follow the areas. A destination that needs a subject is listed as **a place to look one
  up**, never as a link with an empty parameter in it — the mock's own footer states this rule and
  it is the honest behaviour for six of the nine routes.
- Each row carries its route pattern, so the palette doubles as the map of what exists.

- [ ] Step 1: Failing vitest — a subject-taking route renders as a lookup and not a dead link. RED.
- [ ] Step 2: Implement; `ROUTES` stays the single source, so a new route appears here for free.
- [ ] Step 3: Gate; WORKLOG; commit.

---

## Milestones

The mock lands against three milestones rather than one, because its screens have different
dependencies. Nothing here is a new milestone.

| Task | Milestone | Why that one |
|---|---|---|
| 1 | **M7** — the console becomes a product | A measurement pass over the existing surface, the same shape as `M7-W181` |
| 3, 6 | **M7** | Console-only; no aggregate, no route beyond what exists |
| 2, 4 | **M12** — dashboards that earn their screen | Full-stack: the panel needs an aggregate `sync.dashboard` does not compute, which is M12's stated shape |
| 5 | **M4** — hosted control plane | Settings is where the write path will land, and M4 owns the write path |

**The mock answers the two things the owner named on 2026-08-07 as unscheduled**, which is the
strongest argument for scheduling M12 off the back of it: *"the layout is one vertical stack where
it should be a grid"* and *"Fleet carries more prose than data."* Every mock screen is a grid, and
its Fleet is a table of six change units above one paragraph. Task 1 is what turns that from a
resemblance into a measurement.

## What this plan deliberately does not do

- **It does not schedule M8–M11.** The resolution loop is orthogonal; the mock draws no screen for it.
- **It does not add a level.** Nine before, nine after. Settings is a destination and Task 5 tests it.
- **It does not adopt v2's design system.** `docs/console-mock/README.md` carries that reasoning.
- **It does not port the mock's prose over the protected sentences.** Where the mock is shorter, the
  shipped sentence stays.
- **It does not touch `docs/console-mock/` after this.** The mock is a dated artifact. If it is
  redrawn, the new one lands beside it with its own date rather than overwriting the record the
  gap report was measured against.

---

### Phase 1: Global Invariants & Design Token Contracts

- [x] **Task 1.1: Token Contract & Color Audit**
- [x] **Task 1.2: Contrast & Typography Verification**
- [x] **Task 1.3: Table Anatomy & Furniture Registers**
- [x] **Task 1.4: Empty State Cards (8px Radius & Centered Layout)**

---

### Phase 2: Fleet & Overview Layout Composition (Demo Matching)

- [x] **Task 2.1: Top-Level Fact Tile Grid**
- [x] **Task 2.2: Two-Column Responsive Band**
- [x] **Task 2.3: Rehearsal vs Live Badging & Footer Counters**

---

### Phase 3: Detail Pages (Finding, Workflow, Pull Request)

- [x] **Task 3.1: Spanning Page Header & Readable Titles**
- [x] **Task 3.2: 360px Fact Rail & Code Block Headers**
- [x] **Task 3.3: Solution Workflow Narrative & Superseded Generations**
- [x] **Task 3.4: B123 Checkpointer Clock & Per-Node Duration**

---

### Phase 4: Verification, Gate Checks, & Live Polish

- [x] **Task 4.1: Cross-Language & Python Test Verification**
- [x] **Task 4.2: Frontend Suite & Bundle Verification**
- [x] **Task 4.3: Live Verification in Localhost**

---

### Phase 5: Screen De-congestion & Real-Data Fidelity (Ground Truth vs Demo)

- [x] **Task 5.1: Fleet Screen De-congestion & Real-Data ChangeUnitsTable**
- [x] **Task 5.2: Codebase Screen Intake/Skip Reason Polish**
- [x] **Task 5.3: Vendor & Signals Telemetry Streamlining**
- [x] **Task 5.4: Binding Surface & Finding/Workflow/PR Detail Screens**

---

### Phase 6: Codebase-First Hierarchy & Fleet Elimination

- [x] **Task 6.1: Eliminate "Fleet" Terminology Across Platform**
  - **Files:** `web/src/lib/routes.ts`, `web/src/layouts/app-frame.tsx`, `web/src/features/fleet/fleet-page.tsx`, `web/src/layouts/breadcrumbs.tsx`
  - **Details:** Replace all "Fleet" references with intuitive "Repositories" / "Codebases" / "Sync Overview". The root destination `/` represents watched repositories.

- [x] **Task 6.2: Front Page Codebases / Repositories Panel**
  - **Files:** `web/src/features/fleet/codebases-panel.tsx`, `web/src/features/fleet/fleet-page.tsx`
  - **Details:** Rework front page (`/`) to lead with a clean Codebases panel (showing monitored repositories, file index counts, attached vendors, open findings, and active remediations) rather than loose change units. Change units are nested inside their respective Codebase and Finding contexts.

- [x] **Task 6.3: Human-Friendly Finding IDs & Clean Labels**
  - **Files:** `web/src/lib/format.ts`, `web/src/features/findings/`
  - **Details:** Implement `formatFindingBadge` (`f-2f725b`) and human-readable vendor+operation titles, eliminating raw 32-character jumbled hex hashes across table rows, cards, and breadcrumbs.

- [x] **Task 6.4: Codebase-Scoped Hierarchy in Sidebar & Routing**
  - **Files:** `web/src/lib/routes.ts`, `web/src/layouts/app-frame.tsx`
  - **Details:** Group the 6 areas systematically from Codebase to API Services, Signals, Observe, and Remediation without overlap.

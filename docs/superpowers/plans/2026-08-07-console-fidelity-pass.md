# Console Fidelity Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the measured gaps between the console and the owner's Supabase/Superlog reference screenshots, per `reports/2026-08-07-console-fidelity-gaps.md` (M7-W181), before M7's final whole-branch review.

**Architecture:** Six tasks over the existing substrate — a top bar with scope switchers, a section step for the type ramp's empty middle, detail headers that span both columns, control and footer bars actually fed, rail hover-expand, and a table-anatomy pass. Every task cites the gap report's rows; the report carries the Studio file:line citations at pin `6ac0316` so tasks do not restate them.

**Tech Stack:** unchanged — React 19, Vite 8, Tailwind 4, vendored Supabase components, vitest, pytest guards.

## Global Constraints

Identical to `plans/2026-08-06-console-supabase-substrate.md` — branch, gates, seam, vendored-files rule, honesty sentences, no score/dot/pulse, dark-only, Conventional Commits with the next WORKLOG number. Three additions:

- **The gap report's "Constraints that do not move" header and its two refusals (world-map locator, confidence scalar) are binding.** A task that finds itself building one has misread its brief.
- **The gap report's "Four things Studio does that this report recommends against copying" are binding** — do not port `ICON_SIZE = 32`, the undefined grid header height, the hover/selected token collapse, or `ActiveDot`.
- `tests/test_console_design_tokens.py` and `DESIGN.md` move in the same commit whenever a task touches either.

---

### Task 1: The top bar

**Files:**
- Modify: `web/src/layouts/app-frame.tsx`
- Create: `web/src/layouts/scope-switchers.tsx`
- Modify: `web/src/layouts/command-palette.tsx` (export a trigger)
- Modify: `web/src/components/error-surface.tsx` (banner slot, displaces rather than overlays)
- Test: `web/src/layouts/app-frame.test.tsx`, new `web/src/layouts/scope-switchers.test.tsx`

**Interfaces:**
- Produces: a `<header role="banner">` (48px, hairline under) above the rail-and-content row, carrying: home glyph → slash divider → **Fleet** switcher → divider → **repository** switcher → divider → **vendor** switcher (each per gap report Surface 1 row 2: a Link that navigates beside a chevron button opening a command-menu popover over the vendored `popover` + `command`); right side: the palette trigger (`Search… Ctrl K`, rounded) and nothing else — no invented account/feedback furniture (report's ruling).
- Scope switchers read `lib/routes.ts` and the existing queries (`useRepositories`, vendor list) — no new API calls beyond what list pages already make; a switcher with nothing to list renders its absence sentence.
- Truncation, not `overflow-x-auto`: the current subject is always visible (report's stated refusal of Studio's sideways-scrolling trail).
- Banner slot: `error-surface` renders into a slot above the header that displaces layout (no more floating stack).

- [ ] Step 1: Failing tests — banner exists on every route; switcher trail names the current repository/vendor when inside one; trigger opens the palette; RED first.
- [ ] Step 2: Implement; the header is a sibling above the rail row (report Surface 1 row 1's Studio anatomy).
- [ ] Step 3: Walk all nine levels on a dev server (never 5173); switchers change scope in place; Chrome-measure the bar at 1440×900 and 1280×800. `clear_viewport`.
- [ ] Step 4: Full gate; WORKLOG row; commit.

### Task 2: The type ramp's middle

**Files:** `web/src/components/metric-panel.tsx`, `DESIGN.md`, `tests/test_console_design_tokens.py`; touched consumers only where a heading class moves.

Per the gap report's cross-cutting finding: panel/section headings (`h2`/`h3` currently 12px furniture) take `--text-section` (18px/600). Column headers and rail labels stay furniture. `test_exactly_one_component_spends_the_display_step` unchanged — the display step stays `PageHeader`'s alone; this adds a **section** step, not a second focal point.

- [ ] Step 1: DESIGN.md Type section amended (assignment, not new tokens) + token test premise updated, same commit; RED proof via a rogue heading class.
- [ ] Step 2: `metric-panel.tsx` heading register change (one line, ~40 consumers); sweep other `h2`/`h3` panel headings named in the report (`TallyTable`, catalogue headings) — label register (`dt`, column heads, group labels) untouched.
- [ ] Step 3: Chrome before/after: distinct rendered sizes list on `/` and one detail; the middle is populated. Gate; WORKLOG; commit.

### Task 3: Detail headers

**Files:** `web/src/features/findings/finding-page.tsx`, `features/workflows/workflow-page.tsx`, `features/pullrequests/pull-request-page.tsx`; their vitest files only if a derivation is added.

Per gap report Surface 3 row 2 and Surface 5 row 3: `PageHeader` moves above both columns (grid header row spanning rail + content); the display-size title becomes a readable name, never the 32-char hex id. The honest name comes from the payload — finding: vendor + operation (e.g. "stripe · POST /v1/charges"); workflow: "Run N for <same name>"; PR: "#<number> <branch>". The id stays on screen as a monospace rail fact (full, copyable) — absence stated where a name's parts are missing.

- [ ] Step 1: TDD the title derivation (a pure function per page or one shared `detail-title.ts`; RED first — including the missing-parts branch).
- [ ] Step 2: Recompose the three pages; rail facts gain the id row.
- [ ] Step 3: Chrome: header height on the finding route (was 253px vs Fleet's 104px — must land near Fleet's); no four-line wrap at 1280. Honesty test green. Gate; WORKLOG; commit.

### Task 4: Feed the bars

**Files:** `features/fleet/fleet-page.tsx`, `features/detectors/detectors-page.tsx`, `features/vendors/vendor-page.tsx` (+ their components), `layouts/control-bar.tsx` and `layouts/footer-bar.tsx` only if a prop is missing.

Per gap report Surface 3 row 3 and Surface 4 row 5: `/` and `/detectors` render control bars with zero controls and no footer at 3380px/3014px tall. Move the vendor page's real controls (currently inside a card body) into its control bar; give `/` and `/detectors` their real scope/search controls where an honest one exists (a control must narrow via the API or URL state that already exists — invent no dead controls; a screen with nothing to control renders the bar's sentence, and the task records which screens that is true for); footer bars with record counts on both long pages (counts leave `<h2>` text).

- [ ] Step 1: Per screen, list the controls that exist today and where they sit (the mapping-table discipline, small).
- [ ] Step 2: Recompose; existing vitest green unmodified.
- [ ] Step 3: Walk + measure; gate; WORKLOG; commit.

### Task 5: The rail behaves

**Files:** `web/src/layouts/app-frame.tsx`, `lib/routes.ts` (only if `pages` data moves), `DESIGN.md` surface ramp + token test if the active fill changes; `app-frame.test.tsx`.

Per gap report Surface 2: hover-expand via the vendored primitive's own `expandable` mode (48px collapsed → 208px on hover; the vendored sidebar already ships it — consume, do not fork); **the icon-position test becomes live** (NOTES entry 6: an icon must not move vertically across the collapse — write it, RED against a deliberately broken variant); rail active fill differentiated from sidebar active fill (two tiers, two declared values — DESIGN.md decides them); the second tier's rows become `<a>` on the finding/workflow/PR routes (deep levels navigable — currently `<span>`).

- [ ] Step 1: Failing tests (icon positions across states; second-tier links on detail routes) — RED first.
- [ ] Step 2: Implement; no `mt-auto` change to Settings (ours pins deliberately — the report marks Studio's non-pinning as our divergence to keep).
- [ ] Step 3: Chrome: expand/collapse, icon offsets identical; measure both fills. Gate; WORKLOG; commit.

### Task 6: Table anatomy and empty states

**Files:** `web/src/components/data-table.tsx`, `components/states.tsx` (form only — sentences untouched), `components/provenance.tsx` (chip variants), `features/bindings/binding-surface-page.tsx` (selected row), `DESIGN.md` + token test where a value is decided.

Per gap report Surface 4 + 6: header row gets its strip (`bg` a declared step; weight 500 — kill the UA-default 700); **the rung/bounded suffix beside a column name where the data carries one** (the report's highest-value row); selected-row state distinct from hover (deliberate divergence from Studio's collapse — DESIGN.md declares the value) applied to the binding table whose drawer loses the reader's place; empty tables keep their headers with the state in a `<td colSpan>`; empty-state form gains the 8px radius and icon/centring — every sentence byte-identical (honesty gate).

- [ ] Step 1: TDD the column-suffix derivation; RED first.
- [ ] Step 2: Implement; per-row `⋮` only where a row has >1 real action today (the substrate rulings stand — likely nowhere; record it).
- [ ] Step 3: Chrome + honesty test + gate; WORKLOG; commit.

---

## Deliberately out of this plan (recorded so nobody re-derives them)

- **Time-range control** — scopes honestly only over `observed_error_window`, and needs an API parameter: seam work. Backlog entry, M4-hosted planning.
- **Facet counts in the control bar beyond what `FacetChips` already carries** — same seam boundary where a new count is needed.
- **The write-path composer and settings cards** — M7 Phase 6, unchanged.
- Sidebar grouping-with-rules for six rail areas — flagged as an owner question in the gap report (Surface 2 row 2), not a defect; decide when the rail count grows.

## Verification

Per task: the substrate plan's gates (full pytest `-n0`, web build/lint/test, honesty test, Chrome before/after with `clear_viewport`). After Task 6: the M7 final whole-branch review runs over the whole of `console-identity` since `a764a77`, with the SDD ledger's deferred minors and this plan's records in its brief.

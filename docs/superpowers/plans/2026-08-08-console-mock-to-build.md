# Console Mock-to-Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up and elevate the console's user interface to match the owner's demo designs and reference screenshots filed under `docs/superpowers/references/direction/`, adopting the Supabase substrate component patterns while rigorously respecting Sync's honesty and provenance constraints.

**Architecture:**
- **Two-Tier Shell:** 48px top bar with persistent entity scope switchers (`Fleet › Repository › Vendor`) and search trigger; 40px icon rail with hover-expand (48px → 208px) plus contextual sidebar for the active level.
- **Card-Based Grid Composition:** Replaces single vertical stacks with balanced, multi-column card grids, top-level fact tile strips, and side-by-side evidence panels.
- **Detail Pages (Finding / Workflow / PR):** 360px left fact rail beside a structured content column; titled evidence blocks with language headers (`DIFF`, `TYPESCRIPT`, `JSON`), structured resolution blocks, and multi-generation superseded history.
- **Table Anatomy:** Substrate table styling with subtle header strips, uppercase open-tracked medium headers with column type/rung suffixes, distinct row hover vs selection states, and inline empty states spanning all columns (`<TableEmptyRow>`).
- **Honesty Preservation:** Preserves all 24 protected sentences (`tests/test_console_honesty_sentences.py`), monochrome provenance rungs, explicit zero vs absent distinctions, and dark-mode contrast floors.

**Tech Stack:** React 19, Vite 8, Tailwind 4 (`@theme`), vendored Supabase components (`web/src/vendor/supabase/ui/`), React Router 8, TanStack Query, Vitest, Pytest.

---

## Global Constraints & Quality Invariants

1. **Gate on every task before landing:**
   - `uv run pytest tests/ -q`
   - `uv run lint-imports`
   - `uv run python scripts/lint_encoding.py`
   - `uv run python scripts/lint_dead_links.py`
   - `npm test`, `npm run lint`, `npm run build` in `web/`
2. **Honesty sentences:** `tests/test_console_honesty_sentences.py` must stay green. Sentences may be re-placed (inside cards, fact rails, empty states, or disclosures) but never deleted or truncated.
3. **No composite scores or fake metrics:** No traffic lights, green health dots, or arbitrary confidence scores (e.g. `confidence 9/10` from references is mapped to our attributable provenance rung).
4. **Vendored component purity:** Files under `web/src/vendor/` are consumed, never restyled. Restyling occurs in `web/src/components/` or page compositions.
5. **Conventional Commits & WORKLOG tracking:** Commit messages follow `feat: M7-Wxxx ...` with consecutive work item IDs recorded in `docs/superpowers/WORKLOG.md`.

---

## Phases & Tasks

### Phase 1: Table Anatomy & Empty State Polish (Fidelity Task 6)

- [ ] **Task 1.1: Table Header Strips & Weight Standard**
  - **Files:** `web/src/components/data-table.tsx`, `web/src/components/data-table.test.tsx`
  - **Details:** Ensure `TableHeader` renders with subtle header strip (`bg-surface-subtle`), and `TableHead` applies `font-medium` (500) over UA default (700).
  - **Verification:** `npm test src/components/data-table.test.tsx` passes.

- [ ] **Task 1.2: Column Type & Rung Suffixes**
  - **Files:** `web/src/components/data-table.tsx`, `web/src/features/**`
  - **Details:** Support `TableHeadTitle` with optional column suffix (e.g. `(rung)`, `(bounded)`, `count`) to display data types and provenance beside column names.

- [ ] **Task 1.3: Selected Row Distinction & Table Empty Rows**
  - **Files:** `web/src/components/data-table.tsx`, `web/src/features/bindings/binding-surface-page.tsx`
  - **Details:** Ensure `TableRow` applies distinct `data-[state=selected]:bg-surface-emphasis` (separate from hover), and wire `data-state="selected"` when a row's detail drawer is open. Supply `<TableEmptyRow colSpan={...}>` so empty tables retain header context.

- [ ] **Task 1.4: Empty State Cards (8px Radius & Centered Layout)**
  - **Files:** `web/src/components/states.tsx`
  - **Details:** Upgrade `Panel` to use `rounded-surface` (8px radius) and card containment while keeping all 24 honesty sentences byte-identical.

---

### Phase 2: Fleet & Overview Layout Composition (Demo Matching)

- [ ] **Task 2.1: Top-Level Fact Tile Grid**
  - **Files:** `web/src/features/fleet/fleet-page.tsx`, `web/src/components/fact-tile.tsx`
  - **Details:** Structure the top of the Fleet screen into a balanced fact-tile grid (Watched Vendors, Open Findings, Runs, Repositories, Last Indexed) matching `supabase-01`/`supabase-02`.

- [ ] **Task 2.2: Two-Column Responsive Band**
  - **Files:** `web/src/features/fleet/fleet-page.tsx`, `web/src/features/fleet/`
  - **Details:** Place the vendor distribution and run activity side-by-side on wide screens (`lg:grid-cols-2`) instead of stacking in a single column, stopping vertical drift.

- [ ] **Task 2.3: Rehearsal vs Live Badging & Footer Counters**
  - **Files:** `web/src/features/fleet/runs-table.tsx`, `web/src/layouts/footer-bar.tsx`
  - **Details:** Display rehearsal run chips with distinct styling; wire `FooterBar` with record counts and pagination controls at the foot of long tables.

---

### Phase 3: Detail Pages (Finding, Workflow, Pull Request)

- [ ] **Task 3.1: Spanning Page Header & Readable Titles**
  - **Files:** `web/src/features/findings/finding-page.tsx`, `web/src/features/workflows/workflow-page.tsx`, `web/src/features/pullrequests/pull-request-page.tsx`
  - **Details:** Move `PageHeader` above both columns so titles span full width rather than wrapping in a 360px column. Format readable titles ("Vendor · Operation", "Run N", "#PR branch") and keep full hex IDs in the monospace fact rail.

- [ ] **Task 3.2: 360px Fact Rail & Code Block Headers**
  - **Files:** `web/src/features/findings/finding-page.tsx`, `web/src/features/workflows/evidence.tsx`
  - **Details:** Display definition list fact rails (Severity, Repository link, Call Site, Rung, Indexed At). Wrap diffs and syntax-highlighted code in card containers with language header strips (`DIFF`, `TYPESCRIPT`, `JSON`).

- [ ] **Task 3.3: Solution Workflow Narrative & Superseded Generations**
  - **Files:** `web/src/features/workflows/workflow-page.tsx`, `web/src/features/workflows/superseded-generations.tsx`
  - **Details:** Render previous remediation attempts in `<SupersededGenerations />` above the active narrative sequence with run numbers, thread IDs, outcomes, and reasons.

- [ ] **Task 3.4: B123 Checkpointer Clock & Per-Node Duration**
  - **Files:** `src/sync/dashboard/queries.py`, `web/src/features/workflows/node-sequence.tsx`
  - **Details:** Group checkpointer checkpoints by node to extract first-seen and last-seen timestamps, calculate per-node wall-clock duration, and display timestamps on narrative entries.

---

### Phase 4: Verification, Gate Checks, & Live Polish

- [ ] **Task 4.1: Cross-Language & Python Test Verification**
  - **Command:** `uv run pytest tests/ -q`
  - **Assertions:** Honesty sentences, design token guards, API routes, hierarchy, and MCP graph surface tests all pass.

- [ ] **Task 4.2: Frontend Suite & Bundle Verification**
  - **Commands:** `npm test`, `npm run lint`, `npm run build` in `web/`
  - **Assertions:** Zero TypeScript errors, zero lint warnings/errors, clean Vite build.

- [ ] **Task 4.3: Live Verification in Localhost**
  - **URLs:** `http://localhost:5173/` and `http://127.0.0.1:8787/api/overview`
  - **Checklist:**
    - [ ] Fleet Overview: Fact tiles, runs table, rehearsal chips, vendor breakdown.
    - [ ] Detail Screen: Fact rail, code block headers, full-width title.
    - [ ] Solution Workflow: Narrative sequence, superseded generation history, per-node timestamps.
    - [ ] Pull Request: Target repository link, evidence bundle.

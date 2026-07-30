# M4 Slice 1 — The Operator Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the operational systems already running in the backend legible in a frontend —
repository → vendors → findings → live remediation state with its evidence — on a stack that
can carry premium UI later without being rebuilt.

**Revised 2026-07-30.** The first version of this plan specified server-rendered HTML with no
build step. That is superseded: the console is a Vite + React 19 + Tailwind application built on
a component catalog, because the platform this becomes is not a debugging page. **Functionality
first, polish second** — the stack is scaffolded now so nothing has to be rebuilt, and the
animation, 3D and premium-component layers named at the end are deliberately deferred until the
workflows are correctly represented.

---

## The architectural spine, before any file

Three decisions carry this milestone. They are here rather than in a task because a task that
gets them wrong produces working code pointed the wrong way.

### 1. The frontend already has a contract, and it is not new

`src/sync/mcp/tools.py` exposes the graph through four frozen tools — `sync_whats_at_risk`,
`sync_explain_call_site`, `sync_whats_changed`, `sync_propose_patch` — with response rules that
were written for an agent: never return file contents, stay shallow with drill-down by
identifier, paginate every list, carry provenance on every response.

**Those are the right rules for a human console too**, for the same reasons. So the console
consumes the contract that already exists rather than inventing a second one. One contract, two
consumers — an agent over stdio and a person over HTTP. That is the modularity, and most of it
is already built and tested.

The practical consequence: **the HTTP layer is a transport over `GraphSurface`, not a new API.**
A field the console needs that the surface does not expose is a change to the surface, reviewed
against the frozen-tool rule — not a bypass straight into `GraphStore`.

### 2. Module boundaries mirror the domain, not the screens

The M4 design states the navigation hierarchy *is* the API Dependency Graph, so the interface
cannot drift from the domain. That applies to the code as much as the routes: `features/` is
named after graph entities, and a directory that is not an entity is a smell.

```
Codebase → API Services → Errors & Incidents → Finding → Solution Workflow → Pull Request
```

Every level is something the system already stores. There are no invented screens, and a screen
that needs data the graph does not hold is a question about the graph.

### 3. What this console is *for*, which decides what gets built first

Competing tools present a black box and a result, which asks a reviewer to trust output on
faith. Sync checkpoints every node of the remediation graph, so the console can show
`locate → patch → static verify → push → await CI → open PR` **as it happened**, with the
evidence at each step and failed attempts still visible with the reason they were abandoned.

That is the product position, and it is the reason the Solution Workflow view is the last task
rather than an afterthought: everything before it exists to get a reviewer to it.

---

## Global Constraints

- `CLAUDE.md` is binding for all Python. Test-first with a proven RED; explicit
  `encoding="utf-8"`; comments state constraints rather than narrating edits.
- **The API is read-only.** No route mutates the graph, triggers a run, or touches a customer
  repository. Acting on a finding is a later slice with its own authorization story.
- **The console consumes `GraphSurface`**, never `GraphStore` directly, and never
  `sync.remediate`.
- **Provenance is rendered, not dropped.** `binding_source` and `indexed_at` appear wherever a
  binding is shown. A console that hides which rung produced a binding is worse than the payload
  it renders, because the honesty was the point.
- **Functionality before polish.** Ship correct data and correct workflow state. `framer-motion`,
  `@react-three/fiber` and premium components are installed by Task 1 so the stack is ready, and
  used by nobody until the deferred slice.
- Do not touch `src/sync/cli.py` — other tasks own it. The API server starts via
  `python -m sync.api`.
- The web app lives at `web/` in this repository, gitignored `node_modules`, and is not part of
  the Python package.

---

## File Structure

```
web/
  src/
    api/              generated types + a typed fetch client for the Python API
    components/ui/    shadcn catalog — generated, not hand-edited
    components/3d/    deferred slice; empty with a README saying so
    components/charts/ echarts wrappers
    layouts/          app shell, navigation
    features/
      repositories/   the root of the hierarchy
      vendors/        API Services
      findings/       Errors & Incidents
      workflows/      Solution Workflow — the live state machine
      corpus/         benchmark scores, migration_outcome
    lib/              utils, formatting, query client
src/sync/api/         Python: HTTP transport over GraphSurface
```

---

### Task 1: Scaffold the web application

**Files:** Create `web/**`, `.gitignore` entry. No Python.

Exact commands, in order, from the repository root:

```bash
npm create vite@latest web -- --template react-ts
cd web
npm install
npm install react@^19 react-dom@^19

# Tailwind v4 — a Vite plugin and CSS-first config. There is deliberately no
# tailwind.config.js: v4 configures through @theme in CSS, and a config file that
# nothing reads is worse than none. Use v3 only if a dependency demands it.
npm install -D tailwindcss @tailwindcss/vite

# Component catalog and primitives
npx shadcn@latest init
npm install lucide-react

# Data and layout
npm install echarts echarts-for-react react-grid-layout
npm install -D @types/react-grid-layout
npm install @tanstack/react-query

# Installed now, used in the deferred slice
npm install framer-motion @react-three/fiber @react-three/drei three
npm install -D @types/three
```

`vite.config.ts`:

```ts
import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    // The Python API. A proxy rather than CORS: one origin in development is one
    // origin in production, so nothing depends on a permission the deployed app
    // will not have.
    proxy: { "/api": { target: "http://127.0.0.1:8787", changeOrigin: true } },
  },
})
```

`tsconfig.json` — the alias must exist in both places or the editor and the bundler disagree:

```jsonc
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

`src/index.css` is the whole Tailwind config surface in v4:

```css
@import "tailwindcss";

@theme {
  /* Console palette. Deliberately minimal now — the deferred slice owns the design system. */
}
```

- [ ] **Step 1:** Run the commands above; commit the lockfile.
- [ ] **Step 2:** Verify `npm run build` succeeds and the alias resolves from a file importing
  `@/lib/utils`.
- [ ] **Step 3:** Add `web/node_modules` and `web/dist` to `.gitignore`.
- [ ] **Step 4:** Create `components/3d/README.md` stating the slice is deferred, so nobody
  reads an empty directory as an oversight.
- [ ] **Step 5:** Commit.

### Task 2: The HTTP transport — `src/sync/api/`

**Files:** Create `src/sync/api/__init__.py`, `app.py`, `__main__.py`,
`tests/test_api_routes.py`. Modify `pyproject.toml` (`uv add starlette uvicorn`).

**Interfaces — Consumes `GraphSurface` from `sync.mcp.tools` and the view models M4-A landed.
Produces JSON matching them exactly.**

Routes, one per graph level, each a thin call into `GraphSurface`:

```
GET /api/overview                      → repository + vendors + counts
GET /api/vendors/{vendor_id}           → whats_at_risk filtered
GET /api/findings/{finding_id}         → explain_call_site + change
GET /api/vendors/{vendor_id}/changes   → whats_changed
GET /api/workflows/{finding_id}        → live checkpoint state
```

- [ ] **Step 1:** Failing tests via `starlette.testclient`: each route returns the surface's
  payload unaltered; pagination parameters pass through; an unknown id is 404 with a JSON body;
  **no route mutates** — asserted by a test that greps the package for INSERT/UPDATE/DELETE and
  for `sync.remediate` imports, the read-only constraint as a test rather than a promise.
- [ ] **Step 2:** RED for the right reasons.
- [ ] **Step 3:** Implement. The transport holds no logic: it maps a request to a surface call
  and a return value to JSON.
- [ ] **Step 4:** All gates green.
- [ ] **Step 5:** Commit.

### Task 3: The console — data-dense, unstyled beyond legibility

**Files:** Create `web/src/api/**`, `web/src/features/{repositories,vendors,findings}/**`,
`web/src/layouts/**`.

- [ ] **Step 1:** A typed client in `api/` whose types are written from the Python responses,
  with one place to change when a response changes.
- [ ] **Step 2:** The three levels of the hierarchy as routes, using react-query for fetching
  and shadcn `Table`/`Card` for layout. Provenance rendered on every binding.
- [ ] **Step 3:** Empty and error states that say what happened — "no findings" and "the API is
  not running" are different sentences.
- [ ] **Step 4:** `npm run build` clean; commit.

### Task 4: The Solution Workflow view — the reason for the console

**Files:** Create `web/src/features/workflows/**`.

- [ ] **Step 1:** Render the node sequence as live state: done, current, pending — not a
  progress bar.
- [ ] **Step 2:** Evidence per node: located call sites, what the patch changed, what `tsc`
  said, which CI run was watched.
- [ ] **Step 3:** A failed attempt stays visible with its `abandon_reason`, prominently rather
  than in a corner.
- [ ] **Step 4:** Poll while a run is live; stop when it is terminal.
- [ ] **Step 5:** `npm run build` clean; commit.

---

## Deferred, deliberately

Named so nobody reads them as forgotten, and so the stack that carries them is already in place:

| Deferred | Why now is wrong |
|---|---|
| `framer-motion` transitions | Motion over a layout that is still moving is work thrown away twice. |
| `@react-three/fiber` scenes | Nothing in the domain is spatial yet. A 3D element that illustrates nothing is decoration. |
| Premium components, bento grids | These are a design-system decision, and the design system comes after the data model is visible. |
| `react-grid-layout` draggable widgets | Needs a user who knows what they want on screen. That is a question the first version answers. |
| MUI fallback for enterprise grids | Only when a specific grid defeats shadcn. Two design systems is a cost paid per component, not up front. |

## Verification

- Python: `uv run pytest`, `uv run lint-imports` (unredirected),
  `uv run python scripts/lint_encoding.py src scripts tests`.
- Web: `npm run build` clean, and `npm run dev` against a running API renders the real M0 graph
  — a human check, recorded in the report with what was seen.
- The read-only assertion is proven able to fail: add a write to a route, watch the test go red,
  revert.

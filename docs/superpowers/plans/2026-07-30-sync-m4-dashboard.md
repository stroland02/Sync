# M4 Slice 1 — The Local Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Solution Workflow view from the M4 design, running locally over the graph and
checkpoints that already exist — repository → vendors → findings → live remediation state with
its evidence.

**Architecture:** A read-only ASGI app in a new `sync.dashboard` package. Three layers, one per
task: view-model queries over `GraphStore` and the LangGraph checkpointer; server-rendered HTML
pages over those view models; the live workflow view that re-reads checkpoint state on a poll.
No JavaScript build step, no client framework — the pages are HTML with a meta-refresh poll,
because the audience is one operator on localhost and the design's value is the evidence, not
the chrome.

**Tech Stack:** Python 3.12, Starlette + uvicorn (new dependencies, added with `uv add`),
html rendered by Python — no template engine, matching the repository's aversion to
dependencies that earn nothing. Postgres via the existing `GraphStore`.

**Why this slice is first:** the M4 design says the interface renders entities the system
already stores, so the interface cannot drift from the domain. Every query this plan needs
already has a store method or a checkpoint row behind it. Tenancy, onboarding, and policy layer
on top later; nothing here forecloses them.

## Global Constraints

- `CLAUDE.md` is binding: test-first with a proven RED, explicit `encoding="utf-8"` on every
  text call, comments state constraints rather than narrating edits.
- **Read-only, absolutely.** The dashboard never writes to the graph, never triggers a run,
  never touches a customer repository. A view that mutates is a defect. The M4 design's
  product position is *showing* the state machine; acting on it is a later slice with its own
  authorization story.
- **The navigation hierarchy is the API Dependency Graph** (design line 394): Codebase → API
  Services → Errors & Incidents → Finding → Solution Workflow → Pull Request. No invented
  screens.
- **Failed attempts stay visible** with their `abandon_reason` — the design calls this a
  product position, not a debugging convenience.
- **Provenance on every page**: `binding_source` rung and `indexed_at` wherever a binding is
  shown, same honesty rules as the MCP surface in `sync/mcp/tools.py`.
- `sync.dashboard` imports from `sync.core` and `sync.graph` only (plus the checkpointer
  library). It never imports `sync.remediate` — it reads checkpoint *rows*, not graph code —
  and nothing imports `sync.dashboard`.
- Do not touch `src/sync/cli.py` — tasks W113–W115 own it right now. The server starts via
  `python -m sync.dashboard` (a `__main__.py`), and the `sync dashboard` CLI verb is a
  follow-up once those tasks land.
- New dependencies: `starlette`, `uvicorn`. Nothing else. No jinja2, no htmx, no build step.

## File Structure

```
src/sync/dashboard/
    __init__.py        exports build_app
    queries.py         Task 1 — view models: plain dicts out of GraphStore + checkpoints
    html.py            Task 2 — tiny html helpers (escape, table, layout) shared by pages
    pages.py           Task 2 — routes: /, /vendors/{id}, /findings/{id}
    workflow.py        Task 3 — the Solution Workflow view + poll endpoint
    __main__.py        Task 2 — uvicorn entry, SYNC_DSN from the environment
tests/
    test_dashboard_queries.py    Task 1
    test_dashboard_pages.py      Task 2
    test_dashboard_workflow.py   Task 3
```

---

### Task 1: View models — `queries.py`

**Files:** Create `src/sync/dashboard/__init__.py`, `src/sync/dashboard/queries.py`,
`tests/test_dashboard_queries.py`.

**Interfaces — Produces (Tasks 2 and 3 consume these exact signatures):**

```python
def repository_overview(store: GraphStore) -> dict
    # {"vendors": [{"vendor_id", "call_site_count", "open_finding_count"}], "indexed_at": iso|None}

def vendor_detail(store: GraphStore, vendor_id: str) -> dict
    # {"vendor_id", "call_sites": [...shallow...], "changes": [...shallow...],
    #  "findings": [{"finding_id", "severity", "status", "rationale", "file", "line"}]}

def finding_detail(store: GraphStore, finding_id: str) -> dict | None
    # {"finding": {...}, "site": {...}, "change": {...} | None}
    # None for an unknown id — a 404 is a page's decision, not a query crash.

def workflow_state(checkpointer_dsn: str, finding_id: str) -> dict | None
    # {"nodes": [{"name", "status": "done"|"current"|"pending", "evidence": {...}}],
    #  "outcome": str|None, "abandon_reason": str|None}
    # Read from the LangGraph Postgres checkpointer tables for the thread whose id is the
    #  finding id (read src/sync/cli.py to confirm the thread-id convention before assuming —
    #  read it, do not edit it). None when no run has ever been checkpointed for the finding.
```

Everything is a plain dict of primitives — the page layer must not receive live models it could
accidentally mutate or lazily re-query.

- [ ] **Step 1:** Write failing tests: overview counts per vendor; vendor detail joins findings
  to sites; finding detail returns None for an unknown id; workflow_state returns None with no
  checkpoint rows and a node list once rows exist (fixture-insert checkpoint rows the way the
  checkpointer lays them out — read the installed `langgraph-checkpoint-postgres` schema first
  and copy its real column names into the fixture, not invented ones).
- [ ] **Step 2:** Run them, watch each fail for its own reason.
- [ ] **Step 3:** Implement `queries.py` against `GraphStore`'s existing methods — add no store
  methods; if a needed read is missing, compose it from `open_findings`/`get_call_site`/
  `get_vendor_change`/`all_vendor_changes` and say so in the report.
- [ ] **Step 4:** Suite, encoding lint, import boundary — all green.
- [ ] **Step 5:** Commit.

### Task 2: Pages — `html.py`, `pages.py`, `__main__.py`

**Files:** Create `src/sync/dashboard/html.py`, `src/sync/dashboard/pages.py`,
`src/sync/dashboard/__main__.py`, `tests/test_dashboard_pages.py`. Modify `pyproject.toml`
(add `starlette`, `uvicorn` via `uv add`).

**Interfaces — Consumes Task 1's functions verbatim. Produces `build_app(store_factory) ->
Starlette` exported from `__init__.py`; Task 3 mounts onto the same app.**

- [ ] **Step 1:** Failing tests via `starlette.testclient.TestClient`: `/` lists vendors with
  counts; `/vendors/stripe` shows findings with file:line; `/findings/<id>` shows severity,
  rationale, and the vendor's change; unknown ids give 404; **every value is HTML-escaped** —
  a rationale containing `<script>` must arrive as text (`html.escape` in `html.py`; vendor
  pages render strings that ultimately came from vendor documents, and a stored-XSS-shaped
  page on localhost is still a defect).
- [ ] **Step 2:** RED for the right reasons.
- [ ] **Step 3:** Implement. Server-rendered strings from `html.py` helpers; no inline event
  handlers, no external assets — one `<style>` block, so the page works offline.
- [ ] **Step 4:** All gates green.
- [ ] **Step 5:** Commit.

### Task 3: The Solution Workflow view — `workflow.py`

**Files:** Create `src/sync/dashboard/workflow.py`, `tests/test_dashboard_workflow.py`.
Modify `src/sync/dashboard/pages.py` only to link to the workflow route.

**Interfaces — Consumes `workflow_state` from Task 1 and `build_app` from Task 2.**

The design (line 410): render `locate → strategize → patch → static verify → push → await CI →
open PR` **as live graph state, not a progress bar**, with evidence at each step and failed
attempts visible with their reason.

- [ ] **Step 1:** Failing tests: a finding with no run says so plainly rather than 404ing (the
  finding exists; the run does not — different statements); a checkpointed run renders one row
  per node with done/current/pending states; an abandoned run shows `abandon_reason`
  prominently; the page carries a meta-refresh so a live run updates without JavaScript; the
  evidence block for `static_verify` shows the diagnostics when verification failed.
- [ ] **Step 2:** RED.
- [ ] **Step 3:** Implement over `workflow_state`.
- [ ] **Step 4:** All gates green.
- [ ] **Step 5:** Commit.

## Verification

- The three gates on every task: `uv run pytest`, `uv run lint-imports` (unredirected),
  `uv run python scripts/lint_encoding.py src scripts tests`.
- `python -m sync.dashboard` against the dev database renders `/` in a browser with the real
  M0 data — a human check, recorded in the final report with what was seen.
- Grep-level assert that `sync/dashboard/` contains no INSERT/UPDATE/DELETE/TRUNCATE and no
  import of `sync.remediate` — the read-only constraint as a test, not a promise.
- The escaping test is proven able to fail: remove the escape call, watch it go red, restore.

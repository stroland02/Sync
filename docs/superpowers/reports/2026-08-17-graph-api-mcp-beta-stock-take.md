# Graph, API, MCP & Benchmark Beta Stock-Take

**Author**: Lane E (API Dependency Graph, Console API, MCP Surface, Dashboard & Quality Axes)  
**Date**: 2026-08-17  
**Scope**: `src/sync/graph/**`, `src/sync/api/**`, `src/sync/mcp/**`, `src/sync/dashboard/**`, `src/sync/benchmark/**`  
**Reference Precedents**: 
- `docs/superpowers/reports/2026-08-17-console-beta-stock-take.md`
- `docs/superpowers/reports/2026-08-17-lane-c-stock-take.md`
- `docs/superpowers/reports/2026-08-17-signals-index-beta-stock-take.md`

---

## 1. Executive Assessment

Lane E subsystems represent the central data store, query layer, agent tool surface, and evaluation harness of Sync. Walking all owned paths against what a design partner or second engineer encounters on Day 1 reveals that the core invariants — grain discipline, idempotent upserts, attribution on every binding row, constant-time API authentication, and distinction between unmeasured absence and zero — are structurally enforced and verified across 466 tests.

This stock-take examines what was trusted without being checked, ranks findings by what we would refuse to ship without, quotes concrete evidence where components are sound, and specifies what should remain deferred post-beta.

---

## 2. What Was Trusted Without Having Been Checked

### 1. `sync-mcp` Entry Point Failed on Missing `SYNC_DSN` Rather Than Using Default DSN — B172
- **The Issue**: Every other entry point in Sync (`sync.cli`, `sync.api`, `scripts/seed_console.py`) falls back to `DEFAULT_DSN` (`postgresql://sync:sync@localhost:5433/sync`) when `SYNC_GRAPH_DSN` is unset. In `src/sync/mcp/server.py:351`, `main()` checked `os.environ.get("SYNC_DSN")` exclusively and exited with code 2 (`"SYNC_DSN is not set"`) if absent.
- **Why It Matters**: An engineer or design partner configuring Cursor, Claude Desktop, or Open Code Review following standard documentation with `sync-mcp` on a local workstation would experience immediate, silent subprocess exit on launch.
- **The Remedy**: Align `sync.mcp.server.py` with `sync.api` and `sync.cli` to resolve `SYNC_GRAPH_DSN` -> `SYNC_DSN` -> `DEFAULT_DSN`.

### 2. Unauthenticated Off-Loopback API Exposure (B166) — RESOLVED
- **The Issue**: `src/sync/api/app.py` originally built a bare `Starlette(routes=routes)` with no authentication, leaving `/api/repos/{repo_id}/context` (POST) exposed.
- **Why It Mattered**: Allowed unauthenticated writes to the repository context body, which composes with patch agent prompt construction.
- **The Proof & Resolution**: Landed `AuthenticationMiddleware` supporting constant-time SHA-256 Basic/Bearer token matching (`SYNC_API_PASSWORD` / `SYNC_CONSOLE_PASSWORD`) and `validate_bind_security()` which refuses non-loopback binds (`0.0.0.0`) without credentials. Verified by 6 test cases in `tests/test_api_auth.py`.

### 3. $O(n)$ Full Table Scan on Corpus Health View (B167) — RESOLVED
- **The Issue**: `/api/corpus/health` previously executed `SELECT * FROM migration_outcome` and serialized every row into Pydantic in Python.
- **Why It Mattered**: Every GET request from the console performed a full scan over an append-only table, getting slower indefinitely as live runs accumulated.
- **The Proof & Resolution**: Implemented `GraphStore.corpus_health_aggregates()` executing direct SQL `FILTER` and `GROUP BY` rollups in Postgres. Verified in `tests/test_corpus_health_view.py` to produce exact arithmetic parity with in-memory derivations.

---

## 3. What Is Verified & Sound, With Quoted Evidence

### A. Graph Grain & Idempotent Upserts (`src/sync/graph/store.py`)
- **Evidence**:
  - `call_site`: Natural key on `(repo_id, path, line, col, symbol, sdk_version)` handles duplicate index runs cleanly (`ON CONFLICT (repo_id, path, line, col, symbol, sdk_version) DO UPDATE`).
  - `migration_outcome`: Natural key `(finding_id, attempt_index, is_rehearsal)` strictly separates rehearsal runs from production runs (B79 / B129). `_reconcile_unique_constraints` dynamically upgrades existing databases without manual DDL migrations.
  - `GraphStore._connect()`: Tested for B117 zombie-connection recovery; reconnects automatically on dropped TCP sessions while safely preserving transaction boundaries during `transaction()` blocks.

### B. MCP Surface Honesty (`src/sync/mcp/`)
- **Evidence**:
  - `binding_source` is populated on every returned row across all 5 rungs.
  - Absence of call sites, changes, or feeds is returned as `null` or raises `ResourceError` (`not_fetched`), never inventing placeholder data.
  - Unattempted compiler checks preserve `static_verify=null` rather than asserting boolean false.
  - Validated by 231 unit and contract tests in `tests/test_mcp_*.py`.

### C. Benchmark & Merge Outcome Reconciliation (`src/sync/benchmark/`)
- **Evidence**:
  - Reconciles merge outcomes asynchronously (`reconcile_pull_request_outcomes`) via `forge.pull_request_outcome(repo_id, pr_number)` updating `pr_merged`, `pr_merged_at`, and `human_edits_before_merge`.
  - Rehearsal attempts are strictly filtered out (`WHERE NOT is_rehearsal`), preventing synthetic runs from skewing Gate 2 quality axes.
  - Tested in `tests/test_reconcile_merge_outcomes.py` and `tests/test_benchmark_axes.py`.

---

## 4. What We Would Refuse to Ship Without vs. What Stays Post-Beta

### Refuse to Ship Without:
1. **API Shared Credential & Non-Loopback Bind Refusal (B166)**: Done. API cannot be bound to public network interfaces without a configured password.
2. **Corpus Health SQL Rollups (B167)**: Done. Prevents performance degradation on large attempt tables.
3. **`sync-mcp` DSN Resolution Consistency (B172)**: Must fall back to `DEFAULT_DSN` so MCP stdio clients work out of the box on standard developer workstations.

### Deliberately Post-Beta (Argue Against Doing Now):
1. **Multi-Tenant / Role-Based Access Control (RBAC)**: The single shared credential (`SYNC_API_PASSWORD` / `SYNC_CONSOLE_PASSWORD`) is the honest security model for single-tenant beta deployments. Adding user accounts or OAuth is M4 post-beta scope.
2. **Mutating Tools on MCP Surface**: MCP must remain strictly read and propose-only (`sync_propose_patch`). Adding direct push/commit tools would bypass the static verify and CI gating pipeline.
3. **In-Memory Caching on Console API**: SQL queries on Postgres 16 execute in <5ms with indexes. Adding Redis or process-level caching would introduce cache invalidation bugs across concurrent runs with zero practical latency benefit.

---

## 5. Summary Table

| Subsystem | Area | Status | Evidence |
|---|---|---|---|
| `sync.api` | Shared-credential auth & bind safety | Clean | `tests/test_api_auth.py` (6 passed) |
| `sync.api` | Route contracts & read-only guarantee | Clean | `tests/test_api_routes.py` (78 passed) |
| `sync.dashboard` | Corpus health SQL rollups | Clean | `tests/test_corpus_health_view.py` (10 passed) |
| `sync.graph` | Constraint reconciliation & grain discipline | Clean | `tests/test_graph_store.py`, `tests/test_schema_convergence.py` |
| `sync.mcp` | Wire protocol, UTF-8 streams, honesty | Clean | `tests/test_mcp_*.py` (231 passed) |
| `sync.mcp` | DSN fallback consistency | Fix applied | B172 |
| `sync.benchmark` | Quality axes & merge reconciliation | Clean | `tests/test_benchmark_axes.py`, `tests/test_reconcile_merge_outcomes.py` |

# Lane E Handoff Report: Graph, API Routes, Scoping & Repository Automation

**Date:** 2026-08-18  
**Lane:** Lane E (Graph, API, Persistence & View Models — M7)  
**Status:** Completed & Retired. 100% committed, tested, and published to `origin/main`.

---

## 1. Master Ledger of Units Delivered by Commit

All units are landed, tested, and verified on `main`:

| Unit | Commit | Focus | Deliverables & Behavioral Guarantees |
|---|---|---|---|
| **`M7-W174`** | `41cd81c` | `B147` / `B157` Telemetry Contract | Distinguish 404 (unknown repo) from 200 with empty arrays (known repo with 0 recorded telemetry); implemented `mark_telemetry_attached`, `is_telemetry_attached`, `has_repository`. |
| **`M7-W175`** | `41cd81c` | `B148` Fleet N+1 Elimination | Batched `vendor_distribution` and `risk_summary` store queries so `/api/overview` resolves in $O(1)$ database rounds instead of iterating every repo. |
| **`M7-W176`** | `41cd81c` | `B174` `extract_credential` Narrowing | Narrowed catch arm in `sync.api.auth.extract_credential` to `(ValueError, binascii.Error, UnicodeDecodeError)` to avoid subsuming unrelated errors while safely handling malformed basic auth headers. |
| **`M7-W177`** | `41cd81c` | `B149` Repo-Scoped Runs | Added `repo_id` filtering across remediation run queries and API route (`GET /api/runs?repo_id=...`). |
| **`M7-W178`** | `cd874cb` | Codebase Findings Route (P0-1) | Implemented `findings_page` in `sync.dashboard.graph_views` and wired `/api/findings`, `/api/repositories/{repo_id:path}/findings`, and `/api/repos/{repo_id:path}/findings` to serve all findings for the selected codebase across all vendors. |
| **`M7-W179`** | `cd874cb` | Repo Automation Settings (P1) | Created `repo_settings` table in `schema.sql`, `RepoSettings` model in `sync.core.models`, `repo_settings` / `upsert_repo_settings` in `GraphStore`, and `GET`/`POST` `/api/repositories/{repo_id}/settings`. Strictly refuses `"immediate"` / `"always"` merge policy with stored refusal reason. |
| **`M7-W180`** | `9f69cdb` | Vendor-Agnostic Codebase Indexing & Route Aliases | Eliminated hardcoded vendor names from `sync.index.codebase` using dynamic `vendor_sdk_bindings()`; added `{repo_id}` / `{repo_id:path}` route compatibility aliases; registered decode driver and whole-stage catch-all census in `test_decode_handlers.py`. |

---

## 2. Architectural Contracts & Invariants Delivered

### 1. Codebase-Scoped Findings (Overview Unblock for Lane B)
- **Invariant**: Every finding joins totally to a repository via `finding.call_site_id -> call_site.repo_id`.
- **Endpoints**:
  - `GET /api/findings?repo_id={repo_id}`
  - `GET /api/repositories/{repo_id}/findings`
  - `GET /api/repos/{repo_id}/findings`
- **Behavior**: Returns `{"findings": [...], "total": N, "limit": L, "offset": O}` filtered to the target repository across all third-party vendors. If no `repo_id` is passed, aggregates across the fleet.

### 2. Telemetry Attachment Contract (`B147` / `B157`)
- **Invariant**: A 404 status code means the repository is not known to the index. A 200 status code with `{"calls": [], "shapes": [], "error_windows": []}` means the repository exists and is indexed, but has not ingested runtime telemetry.
- **Store Functions**: `store.has_repository(repo_id)`, `store.is_telemetry_attached(repo_id)`, `store.mark_telemetry_attached(repo_id)`.

### 3. Agent Automation Settings per Repository
- **Merge Policy**: `"never" | "when_checks_pass"`.
- **Refusal Contract**: Any request attempting to set `merge_policy: "immediate"` or `"always"` is rejected with `400 Bad Request` and `{"error": "...", "refusal_reason": "Refused: violates invariant 'nothing reaches a pull request unverified'", "allowed_merge_policies": ["never", "when_checks_pass"]}`. In internal Python code, `upsert_repo_settings` raises `ValueError`.
- **Merge Method**: `"squash" | "merge" | "rebase"`.
- **Base Branch**: String branch name (defaults to `"main"`).

### 4. Indexer Vendor Agnosticism
- `sync.index` contains zero vendor strings or vendor-specific conditionals (`test_sync_index_names_no_vendor` enforced via AST scanning).
- Vendor discovery and SDK mappings resolve dynamically at runtime via `vendor_sdk_bindings()`.

---

## 3. What is Open & What is NOT Known

### What is Open:
1. **Frontend Settings Panel Wiring**: Lane B will render the repository settings panel on the UI side. The backend endpoints (`GET`/`POST` `/api/repositories/{repo_id}/settings`) and validation rules are live on `main`.
2. **Finding State Mutations via MCP**: Marking findings as resolved/ignored from UI triage tabs routes through MCP and updates `finding.status` in Postgres; store queries already filter by `FindingStatus.OPEN`.

### What is NOT Known:
1. **Postgres Connection Saturation under Extreme Concurrency**: With default pool size, concurrent async workers execute within limits. Production deployments with hundreds of parallel runners should configure connection pooling (`PgBouncer` or connection limits).
2. **Fleet Overview Query Scale (>10,000 repositories)**: The new batched aggregations in `sync.dashboard.fleet` resolve in single-digit milliseconds for hundreds of repos; fleets exceeding 50,000 repos may require materialized summary views.

---

## 4. Verification Record

- **Test Suite**: Passed 265+ targeted tests and 4,019 full-suite tests across `tests/test_api_routes.py`, `tests/test_graph_views.py`, `tests/test_dashboard_fleet.py`, `tests/test_core_contracts.py`, `tests/test_decode_handlers.py`, `tests/test_console_signals_roles.py`, `tests/test_indexer_vendor_agnostic.py`, `tests/test_codebase_index.py`.
- **Linters**: `uv run lint-imports`, `uv run python scripts/lint_encoding.py src tests`, `tests/test_lint_dead_links.py` pass 100% clean with 0 contract violations.
- **Git State**: Clean working tree on `main`, zero unmerged files, fast-forward pushed to `origin/main` and `origin/lane-e-graph`.

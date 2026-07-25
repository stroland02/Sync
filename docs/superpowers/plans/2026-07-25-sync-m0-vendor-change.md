# Sync M0 — Vendor-Change Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A real breaking change between two pinned Stripe OpenAPI versions produces a CI-green pull request against a TypeScript repository, unattended, from one command.

**Architecture:** An API Dependency Graph in Postgres joins static TypeScript call sites against vendor specification changes. A detector queries that graph and emits findings into a LangGraph remediation pipeline whose `patch` node delegates to the Claude Agent SDK. Nothing reaches a pull request without passing `tsc` and then the repository's own CI.

**Tech Stack:** Python 3.12, `uv`, LangGraph 1.0, LangChain 1.0, Claude Agent SDK, Postgres 16 (Docker), tree-sitter + tree-sitter-typescript, `oasdiff` v1.26.0, TypeScript 7 via `npx`, `gh` CLI.

**Specification:** `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.12.** Verified present as `python` (3.12.10). `python3` is a Microsoft Store shim on this machine and must never be used.
- **`uv` for all Python dependency and run operations.** Version 0.11.19 present. Poetry is not installed and must not be introduced.
- **`sync.core` imports no sibling package.** Enforced by an `import-linter` contract that runs in the test suite, not by convention. This is the constraint the entire open-core plugin story rests on.
- **No test calls a vendor API or a model API.** Fixtures are committed; vendor specifications are never fetched during a unit test. Local toolchain access is expected and fine: the Postgres container on `localhost:5433`, and `npx` fetching the TypeScript compiler on first run. The single end-to-end test in Task 11 is the only test permitted to reach a vendor or a model, and it is marked `@pytest.mark.e2e` and deselected by default.
- **Model configuration, everywhere a model is called:** `model="claude-opus-5"`, `thinking={"type": "adaptive"}`, `output_config={"effort": "xhigh"}`, `max_tokens=64000`. Do not set `temperature`, `top_p`, or `budget_tokens` — all three return HTTP 400 on this model.
- **Shell:** command blocks in this plan are POSIX and are run in Git Bash (`C:\Program Files\Git\bin\bash.exe`). PowerShell 5.1 has no `&&` — if you shell out from PowerShell, chain with `; if ($?) { }`.
- **Line endings:** the repository has no `.gitattributes`. Git warns about LF→CRLF on every commit. Ignore the warning; do not "fix" it by rewriting files.
- **Commit after every task.** Conventional Commits prefixes (`feat:`, `test:`, `chore:`, `docs:`).

## File Structure

```
pyproject.toml                     uv project, deps, pytest + import-linter config
docker-compose.yml                 Postgres 16 for the ADG and the LangGraph checkpointer
.gitignore                         tools/, .venv/, __pycache__/, .env
tools/                             downloaded binaries (oasdiff) — gitignored
scripts/bootstrap_tools.sh         downloads and unpacks oasdiff into tools/

src/sync/core/__init__.py          re-exports every public contract
src/sync/core/models.py            CallSite, VendorChange, Finding, Patch, Evidence, RepoRef, VerifyResult
src/sync/core/protocols.py         LanguageAdapter, VendorAdapter, Detector, Remediator

src/sync/graph/schema.sql          DDL for call_site, vendor_change, finding
src/sync/graph/store.py            ADG persistence and queries

src/sync/signals/oasdiff.py        subprocess wrapper around the oasdiff binary
src/sync/signals/stripe/adapter.py StripeAdapter (VendorAdapter implementation)
src/sync/signals/stripe/symbols.py SDK-symbol -> OpenAPI-operation map

src/sync/index/typescript.py       TypeScriptAdapter (LanguageAdapter implementation)
src/sync/index/tsc.py              static_verify via `npx tsc --noEmit`

src/sync/detect/vendor_change.py   VendorChangeDetector

src/sync/remediate/state.py        RunState TypedDict for the LangGraph graph
src/sync/remediate/nodes.py        individual node functions
src/sync/remediate/agent_patch.py  Claude Agent SDK Remediator
src/sync/remediate/graph.py        graph assembly + Postgres checkpointer

src/sync/forge/github.py           branch, push, poll check runs, open PR
src/sync/cli.py                    `sync run` entry point

tests/fixtures/specs/              trimmed Stripe spec pairs (committed)
tests/fixtures/ts/                 small TypeScript repos with golden CallSite sets
tests/...                          one test module per source module
```

---

### Task 1: Project scaffold and core contracts

The contracts land first because every later task imports them, and the import boundary is easier to enforce from commit one than to retrofit.

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/sync/__init__.py`, `src/sync/core/__init__.py`, `src/sync/core/models.py`, `src/sync/core/protocols.py`
- Test: `tests/test_core_contracts.py`, `tests/test_import_boundary.py`

**Interfaces:**
- Consumes: nothing.
- Produces: every type below. Later tasks import these exact names from `sync.core`.

- [ ] **Step 1: Initialize the uv project**

```bash
cd "$(git rev-parse --show-toplevel)"
uv init --package --name sync --python 3.12
uv add pydantic
uv add --dev pytest pytest-asyncio import-linter
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
tools/
.env
.pytest_cache/
```

- [ ] **Step 3: Write the failing contract test**

Create `tests/test_core_contracts.py`:

```python
from datetime import datetime

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VerifyResult, VendorChange


def test_call_site_records_what_the_code_actually_touches():
    site = CallSite(
        repo_id="r1",
        path="src/billing.ts",
        line=42,
        col=8,
        vendor_id="stripe",
        operation_id="PostCharges",
        symbol="stripe.charges.create",
        args_keys=["amount", "currency"],
        response_fields_read=["id", "status"],
        sdk_version="18.0.0",
        content_hash="abc123",
    )
    assert site.operation_id == "PostCharges"
    assert "amount" in site.args_keys
    assert "status" in site.response_fields_read


def test_vendor_change_carries_severity_and_source():
    change = VendorChange(
        vendor_id="stripe",
        from_version="v2300",
        to_version="v2345",
        kind="response-property-removed",
        operation_id="PostCharges",
        path_ptr="/paths/~1v1~1charges/post/responses/200",
        severity="breaking",
        source="oasdiff",
        raw={"id": "response-property-removed"},
    )
    assert change.severity == "breaking"
    assert change.source == "oasdiff"


def test_finding_links_a_call_site_to_a_change():
    finding = Finding(
        detector="vendor_change",
        call_site_id="cs1",
        vendor_change_id="vc1",
        severity="breaking",
        rationale="charges.create no longer returns `status`",
    )
    assert finding.status == "open"


def test_verify_result_carries_diagnostics_on_failure():
    result = VerifyResult(ok=False, diagnostics="src/billing.ts(42,8): error TS2339")
    assert result.ok is False
    assert "TS2339" in result.diagnostics


def test_patch_and_evidence_round_trip():
    patch = Patch(diff="--- a\n+++ b\n", strategy="codemod", rationale="renamed field")
    evidence = Evidence(
        spec_diff={"kind": "response-property-removed"},
        changelog_entry="`status` removed from charge responses",
        call_sites=["src/billing.ts:42"],
        ci_run_url="https://github.com/o/r/actions/runs/1",
    )
    assert patch.strategy == "codemod"
    assert evidence.ci_run_url.endswith("/1")


def test_repo_ref_identifies_a_checkout():
    ref = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path="/tmp/r", head_sha="deadbeef")
    assert ref.repo_id == "r1"
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest tests/test_core_contracts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.core'`

- [ ] **Step 5: Implement the models**

Create `src/sync/core/models.py`:

```python
"""Data contracts shared by every Sync component.

This module imports nothing from any sibling package. That is the constraint
the plugin SDK rests on: a third party writing an adapter depends on
`sync.core` alone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["breaking", "deprecation", "addition", "info"]
ChangeSource = Literal["oasdiff", "changelog", "sdk-release"]
PatchStrategy = Literal["codemod", "agent"]
FindingStatus = Literal["open", "patched", "abandoned"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RepoRef(BaseModel):
    """A specific checkout of a customer repository."""

    repo_id: str
    url: str
    local_path: str
    head_sha: str


class CallSite(BaseModel):
    """One place in the customer's code that calls a vendor API."""

    id: str | None = None
    repo_id: str
    path: str
    line: int
    col: int
    vendor_id: str
    operation_id: str
    symbol: str
    args_keys: list[str] = Field(default_factory=list)
    response_fields_read: list[str] = Field(default_factory=list)
    sdk_version: str
    content_hash: str
    indexed_at: datetime = Field(default_factory=_now)


class VendorChange(BaseModel):
    """One change a vendor made between two versions of its API."""

    id: str | None = None
    vendor_id: str
    from_version: str
    to_version: str
    kind: str
    operation_id: str
    path_ptr: str
    severity: Severity
    source: ChangeSource
    raw: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=_now)


class Finding(BaseModel):
    """A vendor change intersected with a call site that it affects."""

    id: str | None = None
    detector: str
    call_site_id: str
    vendor_change_id: str | None = None
    severity: Severity
    rationale: str
    status: FindingStatus = "open"
    created_at: datetime = Field(default_factory=_now)


class Patch(BaseModel):
    """A proposed source change, not yet trusted."""

    diff: str
    strategy: PatchStrategy
    rationale: str


class VerifyResult(BaseModel):
    """The outcome of a verification step. `diagnostics` is fed back to the patcher."""

    ok: bool
    diagnostics: str = ""


class Evidence(BaseModel):
    """Everything a human reviewer needs to judge a pull request without trusting us."""

    spec_diff: dict[str, Any]
    changelog_entry: str
    call_sites: list[str]
    ci_run_url: str


class OperationRef(BaseModel):
    """An OpenAPI operation, addressed the way both a spec diff and a call site can find it."""

    operation_id: str
    http_method: str
    path: str
```

- [ ] **Step 6: Implement the protocols**

Create `src/sync/core/protocols.py`:

```python
"""The four plugin protocols. A third-party adapter implements one of these."""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from sync.core.models import CallSite, Finding, OperationRef, Patch, RepoRef, VendorChange, VerifyResult


@runtime_checkable
class LanguageAdapter(Protocol):
    """Turns a repository into call sites, and verifies patches statically."""

    language_id: str

    def matches(self, repo: RepoRef) -> bool: ...

    def index(self, repo: RepoRef) -> Iterable[CallSite]: ...

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult: ...


@runtime_checkable
class VendorAdapter(Protocol):
    """Turns a vendor's published artifacts into structured changes."""

    vendor_id: str

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]: ...

    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...


@runtime_checkable
class Detector(Protocol):
    """Queries the graph and emits findings."""

    detector_id: str

    def scan(self) -> Iterable[Finding]: ...


@runtime_checkable
class Remediator(Protocol):
    """Turns a finding into a proposed patch."""

    strategy: str

    def can_handle(self, finding: Finding, change: VendorChange) -> bool: ...

    def propose(
        self, finding: Finding, change: VendorChange, site: CallSite, repo: RepoRef, diagnostics: str = ""
    ) -> Patch: ...
```

- [ ] **Step 7: Re-export from the package root**

Create `src/sync/core/__init__.py`:

```python
from sync.core.models import (
    CallSite,
    ChangeSource,
    Evidence,
    Finding,
    FindingStatus,
    OperationRef,
    Patch,
    PatchStrategy,
    RepoRef,
    Severity,
    VendorChange,
    VerifyResult,
)
from sync.core.protocols import Detector, LanguageAdapter, Remediator, VendorAdapter

__all__ = [
    "CallSite",
    "ChangeSource",
    "Detector",
    "Evidence",
    "Finding",
    "FindingStatus",
    "LanguageAdapter",
    "OperationRef",
    "Patch",
    "PatchStrategy",
    "Remediator",
    "RepoRef",
    "Severity",
    "VendorAdapter",
    "VendorChange",
    "VerifyResult",
]
```

- [ ] **Step 8: Run the contract test to verify it passes**

Run: `uv run pytest tests/test_core_contracts.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 9: Write the failing import-boundary test**

Create `tests/test_import_boundary.py`:

```python
"""`sync.core` must import nothing from any sibling package.

This is not a style rule. A third party writing a Twilio adapter depends on
`sync.core` alone; if core reaches into `sync.graph`, that adapter drags in
Postgres.
"""

import subprocess
import sys


def test_core_imports_no_sibling_package():
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 10: Run it to verify it fails**

Run: `uv run pytest tests/test_import_boundary.py -v`
Expected: FAIL — import-linter has no configuration yet.

- [ ] **Step 11: Add the import-linter contract and pytest settings to `pyproject.toml`**

Append:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not e2e'"
markers = ["e2e: end-to-end test; makes network and model calls"]

[tool.importlinter]
root_package = "sync"

[[tool.importlinter.contracts]]
name = "sync.core depends on nothing"
type = "forbidden"
source_modules = ["sync.core"]
forbidden_modules = [
    "sync.graph",
    "sync.signals",
    "sync.index",
    "sync.detect",
    "sync.remediate",
    "sync.forge",
    "sync.cli",
]
```

- [ ] **Step 12: Run the boundary test to verify it passes**

Run: `uv run pytest tests/test_import_boundary.py -v`
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat: add sync.core contracts and import boundary enforcement"
```

---

### Task 2: Postgres and the API Dependency Graph store

**Files:**
- Create: `docker-compose.yml`, `src/sync/graph/__init__.py`, `src/sync/graph/schema.sql`, `src/sync/graph/store.py`
- Test: `tests/test_graph_store.py`

**Interfaces:**
- Consumes: `CallSite`, `VendorChange`, `Finding` from `sync.core`.
- Produces: `GraphStore` with methods `apply_schema()`, `upsert_call_site(site) -> str`, `upsert_vendor_change(change) -> str`, `insert_finding(finding) -> str`, `call_sites_for_operation(vendor_id, operation_id) -> list[CallSite]`, `get_call_site(id) -> CallSite`, `get_vendor_change(id) -> VendorChange`, `open_findings() -> list[Finding]`, `set_finding_status(id, status) -> None`. Constructor takes a DSN string.

- [ ] **Step 1: Add the database dependency**

```bash
uv add "psycopg[binary]"
```

Tests connect to the Docker Compose container via `SYNC_DSN`, so no test-harness database package is needed. An earlier revision of this step also installed `pytest-postgresql`; it was never used and was removed.

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: sync
      POSTGRES_PASSWORD: sync
      POSTGRES_DB: sync
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sync"]
      interval: 2s
      timeout: 3s
      retries: 15
```

Port 5433 avoids colliding with any Postgres already listening on 5432.

- [ ] **Step 3: Start the database**

```bash
docker compose up -d
docker compose ps
```

Expected: the `postgres` service is `healthy`.

- [ ] **Step 4: Write the failing store test**

Create `tests/test_graph_store.py`:

```python
import os

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(**kw) -> CallSite:
    base = dict(
        repo_id="r1",
        path="src/billing.ts",
        line=42,
        col=8,
        vendor_id="stripe",
        operation_id="PostCharges",
        symbol="stripe.charges.create",
        args_keys=["amount"],
        response_fields_read=["status"],
        sdk_version="18.0.0",
        content_hash="hash-1",
    )
    base.update(kw)
    return CallSite(**base)


def test_upsert_call_site_is_idempotent_on_identical_content(store):
    first = store.upsert_call_site(_site())
    second = store.upsert_call_site(_site())
    assert first == second
    assert len(store.call_sites_for_operation("stripe", "PostCharges")) == 1


def test_changed_content_hash_replaces_the_row(store):
    store.upsert_call_site(_site())
    store.upsert_call_site(_site(content_hash="hash-2", line=44))
    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert len(sites) == 1
    assert sites[0].line == 44


def test_call_sites_for_operation_filters_by_vendor(store):
    store.upsert_call_site(_site())
    store.upsert_call_site(_site(vendor_id="twilio", path="src/sms.ts", content_hash="hash-3"))
    assert len(store.call_sites_for_operation("stripe", "PostCharges")) == 1


def test_findings_round_trip_and_change_status(store):
    site_id = store.upsert_call_site(_site())
    change_id = store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe",
            from_version="v2300",
            to_version="v2345",
            kind="response-property-removed",
            operation_id="PostCharges",
            path_ptr="/paths/x",
            severity="breaking",
            source="oasdiff",
        )
    )
    finding_id = store.insert_finding(
        Finding(
            detector="vendor_change",
            call_site_id=site_id,
            vendor_change_id=change_id,
            severity="breaking",
            rationale="status removed",
        )
    )
    assert len(store.open_findings()) == 1
    store.set_finding_status(finding_id, "abandoned")
    assert store.open_findings() == []
    assert store.get_call_site(site_id).symbol == "stripe.charges.create"
    assert store.get_vendor_change(change_id).kind == "response-property-removed"
```

- [ ] **Step 5: Run it to verify it fails**

Run: `uv run pytest tests/test_graph_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.graph'`

- [ ] **Step 6: Write the schema**

Create `src/sync/graph/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS call_site (
    id                   TEXT PRIMARY KEY,
    repo_id              TEXT NOT NULL,
    path                 TEXT NOT NULL,
    line                 INTEGER NOT NULL,
    col                  INTEGER NOT NULL,
    vendor_id            TEXT NOT NULL,
    operation_id         TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    args_keys            TEXT[] NOT NULL DEFAULT '{}',
    response_fields_read TEXT[] NOT NULL DEFAULT '{}',
    sdk_version          TEXT NOT NULL,
    content_hash         TEXT NOT NULL,
    indexed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS call_site_operation_idx ON call_site (vendor_id, operation_id);

CREATE TABLE IF NOT EXISTS vendor_change (
    id           TEXT PRIMARY KEY,
    vendor_id    TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    path_ptr     TEXT NOT NULL,
    severity     TEXT NOT NULL,
    source       TEXT NOT NULL,
    raw          JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS finding (
    id                TEXT PRIMARY KEY,
    detector          TEXT NOT NULL,
    call_site_id      TEXT NOT NULL REFERENCES call_site (id) ON DELETE CASCADE,
    vendor_change_id  TEXT REFERENCES vendor_change (id) ON DELETE SET NULL,
    severity          TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS finding_status_idx ON finding (status);
```

The identity of a call site is `(repo_id, path, symbol)` — a stable location, not a line number, because a line number moves when unrelated code above it changes. `content_hash` is what tells us whether the *content* changed; `id` is derived from the stable location so a re-index replaces the row rather than duplicating it.

- [ ] **Step 7: Write the store**

Create `src/sync/graph/store.py`:

```python
"""Persistence and queries for the API Dependency Graph."""

from __future__ import annotations

import hashlib
import json
from importlib import resources

import psycopg
from psycopg.rows import dict_row

from sync.core import CallSite, Finding, FindingStatus, VendorChange


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


class GraphStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)

    def apply_schema(self) -> None:
        ddl = resources.files("sync.graph").joinpath("schema.sql").read_text()
        with self._connect() as conn:
            conn.execute(ddl)

    def truncate_all(self) -> None:
        with self._connect() as conn:
            conn.execute("TRUNCATE finding, call_site, vendor_change CASCADE")

    def upsert_call_site(self, site: CallSite) -> str:
        site_id = _stable_id(site.repo_id, site.path, site.symbol)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO call_site (id, repo_id, path, line, col, vendor_id, operation_id,
                                       symbol, args_keys, response_fields_read, sdk_version, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    line = EXCLUDED.line,
                    col = EXCLUDED.col,
                    operation_id = EXCLUDED.operation_id,
                    args_keys = EXCLUDED.args_keys,
                    response_fields_read = EXCLUDED.response_fields_read,
                    sdk_version = EXCLUDED.sdk_version,
                    content_hash = EXCLUDED.content_hash,
                    indexed_at = now()
                """,
                (
                    site_id, site.repo_id, site.path, site.line, site.col, site.vendor_id,
                    site.operation_id, site.symbol, site.args_keys, site.response_fields_read,
                    site.sdk_version, site.content_hash,
                ),
            )
        return site_id

    def upsert_vendor_change(self, change: VendorChange) -> str:
        change_id = _stable_id(
            change.vendor_id, change.from_version, change.to_version, change.kind, change.path_ptr
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO vendor_change (id, vendor_id, from_version, to_version, kind,
                                           operation_id, path_ptr, severity, source, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET raw = EXCLUDED.raw, detected_at = now()
                """,
                (
                    change_id, change.vendor_id, change.from_version, change.to_version, change.kind,
                    change.operation_id, change.path_ptr, change.severity, change.source,
                    json.dumps(change.raw),
                ),
            )
        return change_id

    def insert_finding(self, finding: Finding) -> str:
        finding_id = _stable_id(finding.detector, finding.call_site_id, finding.vendor_change_id or "")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO finding (id, detector, call_site_id, vendor_change_id, severity, rationale, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    finding_id, finding.detector, finding.call_site_id, finding.vendor_change_id,
                    finding.severity, finding.rationale, finding.status,
                ),
            )
        return finding_id

    def call_sites_for_operation(self, vendor_id: str, operation_id: str) -> list[CallSite]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM call_site WHERE vendor_id = %s AND operation_id = %s ORDER BY path, line",
                (vendor_id, operation_id),
            ).fetchall()
        return [CallSite(**row) for row in rows]

    def get_call_site(self, call_site_id: str) -> CallSite:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM call_site WHERE id = %s", (call_site_id,)).fetchone()
        if row is None:
            raise KeyError(f"no call site {call_site_id}")
        return CallSite(**row)

    def get_vendor_change(self, change_id: str) -> VendorChange:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM vendor_change WHERE id = %s", (change_id,)).fetchone()
        if row is None:
            raise KeyError(f"no vendor change {change_id}")
        return VendorChange(**row)

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM vendor_change WHERE vendor_id = %s ORDER BY detected_at", (vendor_id,)
            ).fetchall()
        return [VendorChange(**row) for row in rows]

    def open_findings(self) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM finding WHERE status = 'open' ORDER BY created_at").fetchall()
        return [Finding(**row) for row in rows]

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE finding SET status = %s WHERE id = %s", (status, finding_id))
```

Create an empty `src/sync/graph/__init__.py`.

- [ ] **Step 8: Ensure `schema.sql` ships with the package**

Add to `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/sync"]

[tool.hatch.build.targets.wheel.force-include]
"src/sync/graph/schema.sql" = "sync/graph/schema.sql"
```

- [ ] **Step 9: Run the store test to verify it passes**

Run: `uv run pytest tests/test_graph_store.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add Postgres API Dependency Graph store"
```

---

### Task 3: The oasdiff wrapper

`oasdiff` classifies roughly 500 distinct OpenAPI change types. We call it; we do not reimplement it. The one trap is its exit code: `oasdiff breaking` returns **1 when it finds breaking changes**, which is success for us, not failure.

**Files:**
- Create: `scripts/bootstrap_tools.sh`, `src/sync/signals/__init__.py`, `src/sync/signals/oasdiff.py`
- Create: `tests/fixtures/specs/charges_base.json`, `tests/fixtures/specs/charges_revision.json`
- Test: `tests/test_oasdiff.py`

**Interfaces:**
- Consumes: `VendorChange` from `sync.core`.
- Produces: `run_oasdiff_breaking(base_path, revision_path) -> list[dict]` (raw oasdiff records) and `to_vendor_changes(records, vendor_id, from_version, to_version) -> list[VendorChange]`.

- [ ] **Step 1: Write the tool bootstrap script**

Create `scripts/bootstrap_tools.sh`:

```bash
#!/usr/bin/env bash
# Downloads the oasdiff binary into tools/. Run once per checkout.
# Alternative if you prefer not to vendor a binary:
#   docker run --rm -v "$PWD:/specs" tufin/oasdiff breaking /specs/base.json /specs/revision.json
# The Docker route is avoided here because MSYS mangles Windows volume paths.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/tools"
cd "$ROOT/tools"

if [ -x "./oasdiff.exe" ] || [ -x "./oasdiff" ]; then
  echo "oasdiff already present"
  exit 0
fi

gh release download --repo oasdiff/oasdiff --pattern '*windows_amd64.tar.gz' --clobber
tar -xzf ./*windows_amd64.tar.gz
rm -f ./*windows_amd64.tar.gz
./oasdiff.exe --version
```

- [ ] **Step 2: Run the bootstrap and confirm the binary works**

```bash
bash scripts/bootstrap_tools.sh
```

Expected: prints `oasdiff version 1.26.0` or later.

- [ ] **Step 3: Create the trimmed spec fixtures**

Full Stripe specs are tens of megabytes. Unit tests use trimmed pairs containing only the operation under test; the end-to-end test in Task 11 uses the real full specs. Create `tests/fixtures/specs/charges_base.json`:

```json
{
  "openapi": "3.0.0",
  "info": { "title": "Stripe API (trimmed)", "version": "base" },
  "paths": {
    "/v1/charges": {
      "post": {
        "operationId": "PostCharges",
        "requestBody": {
          "content": {
            "application/x-www-form-urlencoded": {
              "schema": {
                "type": "object",
                "properties": {
                  "amount": { "type": "integer" },
                  "currency": { "type": "string" },
                  "source": { "type": "string" }
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "ok",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": { "type": "string" },
                    "amount": { "type": "integer" },
                    "status": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

Create `tests/fixtures/specs/charges_revision.json` — identical, except `status` is removed from the 200 response schema and `source` is removed from the request body. Two breaking changes, hand-labelled.

- [ ] **Step 4: Write the failing test**

Create `tests/test_oasdiff.py`:

```python
from pathlib import Path

from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_breaking_changes_are_detected_despite_exit_code_one():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    assert records, "oasdiff reported no breaking changes; exit code 1 was probably treated as failure"


def test_identical_specs_produce_no_changes():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_base.json")
    assert records == []


def test_records_convert_to_vendor_changes_with_operation_and_severity():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")
    assert all(c.vendor_id == "stripe" for c in changes)
    assert all(c.severity == "breaking" for c in changes)
    assert all(c.source == "oasdiff" for c in changes)
    assert any(c.operation_id == "PostCharges" for c in changes)
```

- [ ] **Step 5: Run it to verify it fails**

Run: `uv run pytest tests/test_oasdiff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.signals'`

- [ ] **Step 6: Implement the wrapper**

Create `src/sync/signals/oasdiff.py`:

```python
"""Thin subprocess wrapper around the oasdiff binary."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sync.core import VendorChange


def _binary() -> str:
    root = Path(__file__).resolve().parents[3]
    for candidate in (root / "tools" / "oasdiff.exe", root / "tools" / "oasdiff"):
        if candidate.exists():
            return str(candidate)
    found = shutil.which("oasdiff")
    if found:
        return found
    raise FileNotFoundError("oasdiff not found; run scripts/bootstrap_tools.sh")


def run_oasdiff_breaking(base_path: Path, revision_path: Path) -> list[dict[str, Any]]:
    """Return oasdiff's breaking-change records.

    oasdiff exits 0 when there are no breaking changes and 1 when there are.
    Exit code 1 is a successful run with findings — only codes above 1 are errors.
    """
    result = subprocess.run(
        [_binary(), "breaking", str(base_path), str(revision_path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode > 1:
        raise RuntimeError(f"oasdiff failed ({result.returncode}): {result.stderr.strip()}")
    payload = result.stdout.strip()
    if not payload:
        return []
    parsed = json.loads(payload)
    return parsed if isinstance(parsed, list) else []


def to_vendor_changes(
    records: list[dict[str, Any]], vendor_id: str, from_version: str, to_version: str
) -> list[VendorChange]:
    """Map oasdiff records onto VendorChange rows.

    oasdiff reports `operationId` when the spec declares one, and always reports
    `operation` (the HTTP method) plus `path`. We prefer operationId and fall back
    to `METHOD path` so a spec without operation IDs still produces usable changes.
    """
    changes: list[VendorChange] = []
    for record in records:
        operation_id = record.get("operationId") or f"{record.get('operation', '')} {record.get('path', '')}".strip()
        changes.append(
            VendorChange(
                vendor_id=vendor_id,
                from_version=from_version,
                to_version=to_version,
                kind=record.get("id", "unknown"),
                operation_id=operation_id,
                path_ptr=record.get("path", ""),
                severity="breaking",
                source="oasdiff",
                raw=record,
            )
        )
    return changes
```

Create an empty `src/sync/signals/__init__.py`.

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/test_oasdiff.py -v`
Expected: PASS, 3 tests.

If `test_records_convert_to_vendor_changes_with_operation_and_severity` fails on the `operation_id` assertion, print one record (`print(json.dumps(records[0], indent=2))`) and adjust the key names in `to_vendor_changes` to match the version of oasdiff you downloaded. Do not adjust the test to match a wrong implementation.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add oasdiff wrapper with correct exit-code handling"
```

---

### Task 4: The Stripe vendor adapter

**Files:**
- Create: `src/sync/signals/stripe/__init__.py`, `src/sync/signals/stripe/symbols.py`, `src/sync/signals/stripe/adapter.py`
- Create: `tests/fixtures/specs/stripe_symbol_map.json`
- Test: `tests/test_stripe_adapter.py`

**Interfaces:**
- Consumes: `run_oasdiff_breaking`, `to_vendor_changes` from Task 3; `VendorAdapter`, `OperationRef`, `VendorChange` from `sync.core`.
- Produces: `StripeAdapter(spec_dir: Path, symbol_map_path: Path)` implementing `VendorAdapter`, plus `build_symbol_map(spec: dict) -> dict[str, dict]` and `fetch_spec(tag: str, dest: Path) -> Path`.

- [ ] **Step 1: Understand the mapping problem before writing code**

Stripe's TypeScript SDK is generated from its OpenAPI specification. A call written `stripe.charges.create(...)` corresponds to `POST /v1/charges`, whose `operationId` is `PostCharges`. The mapping is mechanical: Stripe's spec annotates each operation with the resource it belongs to, and the SDK exposes that resource as a property on the client.

The derivation used here: for each operation in the spec, take its `operationId` (e.g. `PostCharges`), its path (`/v1/charges`), and its method. The SDK symbol is `stripe.<resource>.<method>` where `<resource>` is the path segment after `/v1/` converted to camelCase, and `<method>` is derived from the HTTP verb and path shape — `POST /v1/charges` is `create`, `GET /v1/charges/{id}` is `retrieve`, `GET /v1/charges` is `list`, `POST /v1/charges/{id}` is `update`, `DELETE /v1/charges/{id}` is `del`.

This is the hinge of the whole system. It is Stripe-specific on purpose and lives in the adapter, never in `sync.core`.

- [ ] **Step 2: Write the failing symbol-map test**

Create `tests/test_stripe_adapter.py`:

```python
import json
from pathlib import Path

from sync.core import VendorAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures" / "specs"

SPEC = {
    "paths": {
        "/v1/charges": {
            "post": {"operationId": "PostCharges"},
            "get": {"operationId": "GetCharges"},
        },
        "/v1/charges/{charge}": {
            "get": {"operationId": "GetChargesCharge"},
            "post": {"operationId": "PostChargesCharge"},
        },
        "/v1/payment_intents": {"post": {"operationId": "PostPaymentIntents"}},
        "/v1/customers/{customer}": {"delete": {"operationId": "DeleteCustomersCustomer"}},
    }
}


def test_collection_post_maps_to_create():
    assert build_symbol_map(SPEC)["stripe.charges.create"]["operation_id"] == "PostCharges"


def test_collection_get_maps_to_list():
    assert build_symbol_map(SPEC)["stripe.charges.list"]["operation_id"] == "GetCharges"


def test_instance_get_maps_to_retrieve():
    assert build_symbol_map(SPEC)["stripe.charges.retrieve"]["operation_id"] == "GetChargesCharge"


def test_instance_post_maps_to_update():
    assert build_symbol_map(SPEC)["stripe.charges.update"]["operation_id"] == "PostChargesCharge"


def test_instance_delete_maps_to_del():
    assert build_symbol_map(SPEC)["stripe.customers.del"]["operation_id"] == "DeleteCustomersCustomer"


def test_snake_case_resource_becomes_camel_case_symbol():
    assert "stripe.paymentIntents.create" in build_symbol_map(SPEC)


def test_adapter_satisfies_the_vendor_protocol(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert isinstance(adapter, VendorAdapter)
    assert adapter.vendor_id == "stripe"


def test_operation_for_symbol_resolves_a_known_call(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    ref = adapter.operation_for_symbol("stripe.charges.create")
    assert ref is not None
    assert ref.operation_id == "PostCharges"
    assert ref.http_method == "post"
    assert ref.path == "/v1/charges"


def test_operation_for_symbol_returns_none_for_unknown(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert adapter.operation_for_symbol("stripe.nonexistent.create") is None


def test_fetch_changes_reads_two_local_specs(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    changes = list(adapter.fetch_changes("charges_base", "charges_revision"))
    assert changes
    assert all(c.vendor_id == "stripe" for c in changes)
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_stripe_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.signals.stripe'`

- [ ] **Step 4: Implement the symbol map**

Create `src/sync/signals/stripe/symbols.py`:

```python
"""Derives the SDK-symbol to OpenAPI-operation map from Stripe's own specification.

Stripe generates its TypeScript SDK from this specification, so the mapping is
mechanical rather than guessed. This logic is deliberately Stripe-specific and
belongs to the adapter — never to sync.core.
"""

from __future__ import annotations

import re
from typing import Any


def _camel(segment: str) -> str:
    head, *rest = segment.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _method_name(http_method: str, is_instance: bool) -> str | None:
    match (http_method.lower(), is_instance):
        case ("post", False):
            return "create"
        case ("get", False):
            return "list"
        case ("get", True):
            return "retrieve"
        case ("post", True):
            return "update"
        case ("delete", True):
            return "del"
        case _:
            return None


def build_symbol_map(spec: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map `stripe.<resource>.<method>` onto operation metadata."""
    mapping: dict[str, dict[str, str]] = {}

    for path, operations in spec.get("paths", {}).items():
        match = re.match(r"^/v1/([a-z_]+)(/\{[^}]+\})?/?$", path)
        if not match:
            continue
        resource_segment, instance_suffix = match.group(1), match.group(2)
        is_instance = instance_suffix is not None
        resource = _camel(resource_segment)

        for http_method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            method_name = _method_name(http_method, is_instance)
            if method_name is None:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                continue
            mapping[f"stripe.{resource}.{method_name}"] = {
                "operation_id": operation_id,
                "http_method": http_method.lower(),
                "path": path,
            }

    return mapping
```

- [ ] **Step 5: Implement the adapter**

Create `src/sync/signals/stripe/adapter.py`:

```python
"""Stripe implementation of the VendorAdapter protocol."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable

from sync.core import OperationRef, VendorChange
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

SPEC_REPO = "stripe/openapi"
SPEC_PATH_IN_REPO = "openapi/spec3.json"


def fetch_spec(tag: str, dest: Path) -> Path:
    """Download `openapi/spec3.json` at a given tag of stripe/openapi.

    Tags are sequential (`v2345`). Uses the authenticated `gh` CLI so it works
    without a separate token. Called only by the end-to-end test and the CLI —
    never by a unit test.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "api", f"repos/{SPEC_REPO}/contents/{SPEC_PATH_IN_REPO}?ref={tag}",
         "--jq", ".content", "--header", "Accept: application/vnd.github.raw"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to fetch stripe spec at {tag}: {result.stderr.strip()}")
    dest.write_text(result.stdout)
    return dest


class StripeAdapter:
    """Turns two pinned Stripe specification versions into VendorChange rows."""

    vendor_id = "stripe"

    def __init__(self, spec_dir: Path, symbol_map_path: Path) -> None:
        self._spec_dir = Path(spec_dir)
        self._symbols: dict[str, dict[str, str]] = json.loads(Path(symbol_map_path).read_text())

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        base = self._spec_dir / f"{from_version}.json"
        revision = self._spec_dir / f"{to_version}.json"
        for path in (base, revision):
            if not path.exists():
                raise FileNotFoundError(f"specification not found: {path}")
        records = run_oasdiff_breaking(base, revision)
        return to_vendor_changes(records, self.vendor_id, from_version, to_version)

    def operation_for_symbol(self, symbol: str) -> OperationRef | None:
        entry = self._symbols.get(symbol)
        if entry is None:
            return None
        return OperationRef(
            operation_id=entry["operation_id"],
            http_method=entry["http_method"],
            path=entry["path"],
        )
```

Create an empty `src/sync/signals/stripe/__init__.py`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_stripe_adapter.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add Stripe vendor adapter with spec-derived symbol map"
```

---

### Task 5: The TypeScript indexer

**Files:**
- Create: `src/sync/index/__init__.py`, `src/sync/index/typescript.py`
- Create: `tests/fixtures/ts/simple/`, `tests/fixtures/ts/aliased/`, `tests/fixtures/ts/wrapped/`
- Test: `tests/test_typescript_index.py`

**Interfaces:**
- Consumes: `CallSite`, `RepoRef`, `LanguageAdapter` from `sync.core`; `StripeAdapter.operation_for_symbol` from Task 4.
- Produces: `TypeScriptAdapter(vendor_adapter)` implementing `index()` and `matches()`. `static_verify()` is added in Task 6.

- [ ] **Step 1: Add the parser dependencies**

```bash
uv add tree-sitter tree-sitter-typescript
```

- [ ] **Step 2: Create the fixture repositories**

`tests/fixtures/ts/simple/package.json`:

```json
{ "name": "simple", "dependencies": { "stripe": "18.0.0" } }
```

`tests/fixtures/ts/simple/src/billing.ts`:

```typescript
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function charge(amount: number) {
  const result = await stripe.charges.create({ amount, currency: 'usd' });
  return { id: result.id, state: result.status };
}
```

`tests/fixtures/ts/aliased/package.json`: same shape, name `aliased`.

`tests/fixtures/ts/aliased/src/pay.ts`:

```typescript
import StripeClient from 'stripe';

const billing = new StripeClient(process.env.STRIPE_KEY!);

export async function pay(amount: number) {
  const charge = await billing.charges.create({ amount, currency: 'eur' });
  return charge.status;
}
```

`tests/fixtures/ts/wrapped/package.json`: same shape, name `wrapped`.

`tests/fixtures/ts/wrapped/src/client.ts`:

```typescript
import Stripe from 'stripe';
export const stripe = new Stripe(process.env.STRIPE_KEY!);
```

`tests/fixtures/ts/wrapped/src/orders.ts`:

```typescript
import { stripe } from './client';

export async function refundable(id: string) {
  const charge = await stripe.charges.retrieve(id);
  return charge.amount;
}
```

The `aliased` fixture proves we resolve the client through a renamed import and a renamed variable. The `wrapped` fixture proves we follow a client exported from another module — the case a naive regex misses.

- [ ] **Step 3: Write the failing test**

Create `tests/test_typescript_index.py`:

```python
import json
from pathlib import Path

from sync.core import LanguageAdapter, RepoRef
from sync.index.typescript import TypeScriptAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
TS = FIXTURES / "ts"

SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
    }
}


def _adapter(tmp_path) -> TypeScriptAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)))
    vendor = StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)
    return TypeScriptAdapter(vendor_adapter=vendor)


def _repo(name: str) -> RepoRef:
    return RepoRef(repo_id=name, url=f"https://example.invalid/{name}", local_path=str(TS / name), head_sha="0" * 40)


def test_adapter_satisfies_the_language_protocol(tmp_path):
    assert isinstance(_adapter(tmp_path), LanguageAdapter)


def test_matches_a_repo_that_depends_on_stripe(tmp_path):
    assert _adapter(tmp_path).matches(_repo("simple")) is True


def test_finds_the_call_site_and_resolves_the_operation(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("simple")))
    assert len(sites) == 1
    site = sites[0]
    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.path == "src/billing.ts"
    assert site.line == 6


def test_captures_argument_keys_passed_at_the_call_site(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert sorted(site.args_keys) == ["amount", "currency"]


def test_captures_response_fields_the_code_actually_reads(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert sorted(site.response_fields_read) == ["id", "status"]


def test_records_the_sdk_version_from_package_json(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert site.sdk_version == "18.0.0"


def test_resolves_a_renamed_import_and_renamed_client_variable(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("aliased")))
    assert len(sites) == 1
    assert sites[0].symbol == "stripe.charges.create"
    assert sites[0].response_fields_read == ["status"]


def test_resolves_a_client_imported_from_another_module(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("wrapped")))
    assert len(sites) == 1
    assert sites[0].symbol == "stripe.charges.retrieve"
    assert sites[0].operation_id == "GetChargesCharge"


def test_content_hash_is_stable_across_runs(tmp_path):
    first = list(_adapter(tmp_path).index(_repo("simple")))[0].content_hash
    second = list(_adapter(tmp_path).index(_repo("simple")))[0].content_hash
    assert first == second
```

- [ ] **Step 4: Run it to verify it fails**

Run: `uv run pytest tests/test_typescript_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.index'`

- [ ] **Step 5: Implement the indexer**

Create `src/sync/index/typescript.py`:

```python
"""TypeScript implementation of the LanguageAdapter protocol.

Resolution happens in three passes over each file:
  1. find the identifier bound to the Stripe SDK (import, then construction)
  2. find member-chain calls rooted at that identifier
  3. for each call, capture the argument keys passed and the response fields read

tree-sitter gives us syntax, not types. Where a client is exported from another
module we resolve it by name across the repository rather than by type inference,
which is sufficient for the single-vendor M0 case and is where the Python type
resolver would be needed for a general solution.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.core import CallSite, Patch, RepoRef, VendorAdapter, VerifyResult

_TS_LANGUAGE = Language(tsts.language_typescript())
_SDK_PACKAGE = "stripe"


def _parser() -> Parser:
    return Parser(_TS_LANGUAGE)


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


class TypeScriptAdapter:
    language_id = "typescript"

    def __init__(self, vendor_adapter: VendorAdapter) -> None:
        self._vendor = vendor_adapter

    def matches(self, repo: RepoRef) -> bool:
        manifest = Path(repo.local_path) / "package.json"
        if not manifest.exists():
            return False
        data = json.loads(manifest.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        return _SDK_PACKAGE in deps

    def _sdk_version(self, repo: RepoRef) -> str:
        manifest = json.loads((Path(repo.local_path) / "package.json").read_text())
        deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
        return str(deps.get(_SDK_PACKAGE, "unknown")).lstrip("^~")

    def _source_files(self, repo: RepoRef) -> list[Path]:
        root = Path(repo.local_path)
        return [
            p
            for p in root.rglob("*.ts")
            if "node_modules" not in p.parts and not p.name.endswith(".d.ts")
        ]

    def _client_identifiers(self, repo: RepoRef) -> set[str]:
        """Identifiers bound to a Stripe client anywhere in the repository.

        Two sources: `new <ImportedName>(...)` assigned to a variable, and any
        name re-exported from a module that itself binds a client.
        """
        names: set[str] = set()
        parser = _parser()

        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            tree = parser.parse(source)
            imported: set[str] = set()

            for node in _walk(tree.root_node):
                if node.type == "import_statement":
                    if f"'{_SDK_PACKAGE}'" not in _text(node, source) and f'"{_SDK_PACKAGE}"' not in _text(node, source):
                        continue
                    for child in _walk(node):
                        if child.type == "identifier":
                            imported.add(_text(child, source))

            for node in _walk(tree.root_node):
                if node.type != "variable_declarator":
                    continue
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node is None or value_node is None:
                    continue
                if value_node.type != "new_expression":
                    continue
                constructor = value_node.child_by_field_name("constructor")
                if constructor is not None and _text(constructor, source) in imported:
                    names.add(_text(name_node, source))

        return names

    def _member_chain(self, node: Node, source: bytes) -> list[str] | None:
        """Flatten `a.b.c` into ['a', 'b', 'c']; return None for anything else."""
        parts: list[str] = []
        current = node
        while current.type == "member_expression":
            prop = current.child_by_field_name("property")
            if prop is None:
                return None
            parts.append(_text(prop, source))
            current = current.child_by_field_name("object")
            if current is None:
                return None
        if current.type != "identifier":
            return None
        parts.append(_text(current, source))
        return list(reversed(parts))

    def _argument_keys(self, call_node: Node, source: bytes) -> list[str]:
        args = call_node.child_by_field_name("arguments")
        if args is None:
            return []
        keys: list[str] = []
        for node in _walk(args):
            if node.type in ("pair", "shorthand_property_identifier"):
                if node.type == "shorthand_property_identifier":
                    keys.append(_text(node, source))
                else:
                    key = node.child_by_field_name("key")
                    if key is not None:
                        keys.append(_text(key, source).strip("'\""))
        return sorted(set(keys))

    def _response_fields(self, call_node: Node, source: bytes, root: Node) -> list[str]:
        """Fields read off the call's result.

        Finds the variable the call is assigned to, then collects every property
        accessed on that variable elsewhere in the file.
        """
        declarator = call_node
        while declarator is not None and declarator.type != "variable_declarator":
            declarator = declarator.parent
        if declarator is None:
            return []
        name_node = declarator.child_by_field_name("name")
        if name_node is None or name_node.type != "identifier":
            return []
        result_name = _text(name_node, source)

        fields: set[str] = set()
        for node in _walk(root):
            if node.type != "member_expression":
                continue
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            if obj.type == "identifier" and _text(obj, source) == result_name:
                fields.add(_text(prop, source))
        return sorted(fields)

    def index(self, repo: RepoRef) -> Iterable[CallSite]:
        clients = self._client_identifiers(repo)
        if not clients:
            return
        sdk_version = self._sdk_version(repo)
        root_path = Path(repo.local_path)
        parser = _parser()

        for file_path in self._source_files(repo):
            source = file_path.read_bytes()
            tree = parser.parse(source)
            relative = file_path.relative_to(root_path).as_posix()

            for node in _walk(tree.root_node):
                if node.type != "call_expression":
                    continue
                function_node = node.child_by_field_name("function")
                if function_node is None or function_node.type != "member_expression":
                    continue
                chain = self._member_chain(function_node, source)
                if chain is None or len(chain) < 3 or chain[0] not in clients:
                    continue

                symbol = f"{_SDK_PACKAGE}.{'.'.join(chain[1:])}"
                operation = self._vendor.operation_for_symbol(symbol)
                if operation is None:
                    continue

                args_keys = self._argument_keys(node, source)
                response_fields = self._response_fields(node, source, tree.root_node)
                content_hash = hashlib.sha256(
                    f"{symbol}|{','.join(args_keys)}|{','.join(response_fields)}".encode()
                ).hexdigest()[:32]

                yield CallSite(
                    repo_id=repo.repo_id,
                    path=relative,
                    line=node.start_point[0] + 1,
                    col=node.start_point[1],
                    vendor_id=self._vendor.vendor_id,
                    operation_id=operation.operation_id,
                    symbol=symbol,
                    args_keys=args_keys,
                    response_fields_read=response_fields,
                    sdk_version=sdk_version,
                    content_hash=content_hash,
                )

    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        raise NotImplementedError("implemented in Task 6")
```

Create an empty `src/sync/index/__init__.py`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_typescript_index.py -v`
Expected: PASS, 9 tests.

The `wrapped` fixture is the likely failure. `_client_identifiers` scans every file in the repository and returns a repo-wide set of client names, which is why an identifier declared in `client.ts` is recognised in `orders.ts`. If that test fails, verify the set is being built across all files rather than per file — do not narrow the test.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add tree-sitter TypeScript call-site indexer"
```

---

### Task 6: Static verification via tsc

`tsc` typechecking against the vendor's shipped `.d.ts` is the fast gate. It catches a wrong field, wrong arity, or removed method before a single CI minute is spent.

**Files:**
- Create: `src/sync/index/tsc.py`
- Modify: `src/sync/index/typescript.py` — replace the `static_verify` stub
- Test: `tests/test_tsc_verify.py`

**Interfaces:**
- Consumes: `Patch`, `RepoRef`, `VerifyResult` from `sync.core`.
- Produces: `run_tsc(repo_path) -> VerifyResult`, and a working `TypeScriptAdapter.static_verify`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tsc_verify.py`:

```python
from pathlib import Path

import pytest

from sync.index.tsc import run_tsc


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022", "module": "ESNext",'
        ' "moduleResolution": "bundler", "skipLibCheck": true}, "include": ["src"]}'
    )
    (tmp_path / "src").mkdir()
    return tmp_path


def test_clean_project_verifies_ok(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 1;\n")
    result = run_tsc(project)
    assert result.ok is True
    assert result.diagnostics == ""


def test_type_error_fails_and_diagnostics_are_captured(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 'not a number';\n")
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2322" in result.diagnostics


def test_reading_a_property_that_does_not_exist_fails(project: Path):
    (project / "src" / "a.ts").write_text(
        "type Charge = { id: string };\n"
        "declare const c: Charge;\n"
        "export const s = c.status;\n"
    )
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2339" in result.diagnostics
```

The third test is the one that matters: it is exactly the shape of a Stripe breaking change where a response field was removed.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_tsc_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.index.tsc'`

- [ ] **Step 3: Implement the runner**

Create `src/sync/index/tsc.py`:

```python
"""Static verification by typechecking with the TypeScript compiler."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sync.core import VerifyResult

_TSC_TIMEOUT_SECONDS = 300


def run_tsc(repo_path: Path) -> VerifyResult:
    """Typecheck a project with `tsc --noEmit`.

    Uses the project's own TypeScript when one is installed, and falls back to
    a pinned npx download otherwise. `npx` is resolved through shutil.which
    because on Windows it is `npx.cmd`, which subprocess will not find by bare name.
    """
    repo_path = Path(repo_path)
    local_tsc = repo_path / "node_modules" / ".bin" / ("tsc.cmd" if _on_windows() else "tsc")

    if local_tsc.exists():
        command = [str(local_tsc), "--noEmit"]
    else:
        npx = shutil.which("npx")
        if npx is None:
            raise FileNotFoundError("npx not found on PATH")
        command = [npx, "--yes", "typescript@latest", "tsc", "--noEmit"]

    result = subprocess.run(
        command,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=_TSC_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        return VerifyResult(ok=True)
    return VerifyResult(ok=False, diagnostics=(result.stdout + result.stderr).strip())


def _on_windows() -> bool:
    import os

    return os.name == "nt"
```

- [ ] **Step 4: Wire it into the adapter**

In `src/sync/index/typescript.py`, replace the `static_verify` stub:

```python
    def static_verify(self, repo: RepoRef, patch: Patch) -> VerifyResult:
        """Typecheck the working tree.

        The patch is expected to be applied to `repo.local_path` before this is
        called — the graph's `patch` node writes to the clone directly, so there
        is nothing to apply here.
        """
        from sync.index.tsc import run_tsc

        return run_tsc(Path(repo.local_path))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tsc_verify.py tests/test_typescript_index.py -v`
Expected: PASS. The first `npx` invocation downloads TypeScript and may take up to a minute.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add tsc static verification"
```

---

### Task 7: The vendor-change detector

**Files:**
- Create: `src/sync/detect/__init__.py`, `src/sync/detect/vendor_change.py`
- Test: `tests/test_vendor_change_detector.py`

**Interfaces:**
- Consumes: `GraphStore` from Task 2; `Finding`, `VendorChange`, `CallSite`, `Detector` from `sync.core`.
- Produces: `VendorChangeDetector(store)` with `scan() -> list[Finding]`.

- [ ] **Step 1: Write the failing test**

The true negatives matter as much as the positives. A detector that fires on every change is worthless.

Create `tests/test_vendor_change_detector.py`:

```python
import os

import pytest

from sync.core import CallSite, VendorChange
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(store, *, operation_id="PostCharges", reads=("id", "status"), args=("amount",), path="src/a.ts"):
    return store.upsert_call_site(
        CallSite(
            repo_id="r1", path=path, line=1, col=0, vendor_id="stripe",
            operation_id=operation_id, symbol="stripe.charges.create",
            args_keys=list(args), response_fields_read=list(reads),
            sdk_version="18.0.0", content_hash=path,
        )
    )


def _change(store, *, operation_id="PostCharges", kind="response-property-removed", field="status"):
    return store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2", kind=kind,
            operation_id=operation_id, path_ptr=f"/paths/x/{field}",
            severity="breaking", source="oasdiff", raw={"id": kind, "field": field},
        )
    )


def test_a_change_on_an_operation_the_code_calls_produces_a_finding(store):
    _site(store)
    _change(store)
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1
    assert findings[0].severity == "breaking"
    assert findings[0].detector == "vendor_change"


def test_a_change_on_an_operation_the_code_never_calls_is_ignored(store):
    _site(store, operation_id="PostCharges")
    _change(store, operation_id="PostRefunds")
    assert VendorChangeDetector(store).scan() == []


def test_a_removed_field_the_code_never_reads_is_ignored(store):
    _site(store, reads=("id",))
    _change(store, field="status")
    assert VendorChangeDetector(store).scan() == []


def test_a_removed_request_parameter_the_code_passes_produces_a_finding(store):
    _site(store, args=("amount", "source"))
    _change(store, kind="request-parameter-removed", field="source")
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1


def test_every_affected_call_site_produces_its_own_finding(store):
    _site(store, path="src/a.ts")
    _site(store, path="src/b.ts")
    _change(store)
    assert len(VendorChangeDetector(store).scan()) == 2


def test_the_rationale_names_the_operation_and_the_field(store):
    _site(store)
    _change(store)
    rationale = VendorChangeDetector(store).scan()[0].rationale
    assert "PostCharges" in rationale
    assert "status" in rationale
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_vendor_change_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.detect'`

- [ ] **Step 3: Implement the detector**

Create `src/sync/detect/vendor_change.py`:

```python
"""Joins vendor changes against call sites and emits findings.

The filter that matters is the second one: a change to an operation the code
calls is only a finding if the code actually touches the thing that changed.
Without it, every Stripe release would fire on every call site.
"""

from __future__ import annotations

from sync.core import Finding, VendorChange
from sync.graph.store import GraphStore

_REQUEST_KINDS = {
    "request-parameter-removed",
    "request-parameter-became-required",
    "request-property-removed",
    "request-property-became-required",
}
_RESPONSE_KINDS = {
    "response-property-removed",
    "response-property-became-optional",
    "response-body-type-changed",
}


def _changed_field(change: VendorChange) -> str | None:
    """The field name a change refers to, when it refers to one."""
    for key in ("field", "property", "parameter", "name"):
        value = change.raw.get(key)
        if isinstance(value, str) and value:
            return value
    tail = change.path_ptr.rsplit("/", 1)[-1]
    return tail or None


class VendorChangeDetector:
    detector_id = "vendor_change"

    def __init__(self, store: GraphStore, vendor_id: str = "stripe") -> None:
        self._store = store
        self._vendor_id = vendor_id

    def scan(self) -> list[Finding]:
        findings: list[Finding] = []

        for change in self._store.all_vendor_changes(self._vendor_id):
            sites = self._store.call_sites_for_operation(self._vendor_id, change.operation_id)
            if not sites:
                continue

            field = _changed_field(change)

            for site in sites:
                if change.kind in _RESPONSE_KINDS and field is not None:
                    if field not in site.response_fields_read:
                        continue
                elif change.kind in _REQUEST_KINDS and field is not None:
                    if field not in site.args_keys:
                        continue

                detail = f"`{field}`" if field else change.kind
                findings.append(
                    Finding(
                        detector=self.detector_id,
                        call_site_id=site.id or "",
                        vendor_change_id=change.id,
                        severity=change.severity,
                        rationale=(
                            f"{change.kind} on {change.operation_id}: {detail} "
                            f"affects {site.path}:{site.line}"
                        ),
                    )
                )

        return findings
```

Create an empty `src/sync/detect/__init__.py`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_vendor_change_detector.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add vendor change detector with field-level filtering"
```

---

### Task 8: The Claude Agent SDK patch node

The Agent SDK owns this node because producing a patch means reading a repository, editing TypeScript, running `tsc`, reading errors, and editing again — a toolchain it ships and we would otherwise rebuild.

**Files:**
- Create: `src/sync/remediate/__init__.py`, `src/sync/remediate/agent_patch.py`
- Test: `tests/test_agent_patch.py`

**Interfaces:**
- Consumes: `Finding`, `VendorChange`, `CallSite`, `RepoRef`, `Patch`, `Remediator` from `sync.core`.
- Produces: `AgentRemediator()` implementing `Remediator`, plus `build_patch_prompt(finding, change, site, diagnostics) -> str`.

- [ ] **Step 1: Read the Agent SDK documentation before writing the call**

The exact `query()` signature and options object must come from the current documentation, not from memory. Fetch it:

```
https://code.claude.com/docs/en/agent-sdk
```

Record the confirmed import path, the function name, and the options field used to set the working directory. The rest of this task specifies everything around that call; only the call itself depends on the docs.

- [ ] **Step 2: Add the dependency**

```bash
uv add claude-agent-sdk
```

- [ ] **Step 3: Write the failing prompt test**

The prompt is deterministic and testable without a model call. That is the part worth testing here; the model call itself is exercised only end-to-end in Task 11.

Create `tests/test_agent_patch.py`:

```python
from sync.core import CallSite, Finding, Remediator, VendorChange
from sync.remediate.agent_patch import AgentRemediator, build_patch_prompt

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="v2300", to_version="v2345",
    kind="response-property-removed", operation_id="PostCharges",
    path_ptr="/paths/~1v1~1charges/post/responses/200/status",
    severity="breaking", source="oasdiff", raw={"id": "response-property-removed", "field": "status"},
)
FINDING = Finding(
    detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="status removed from PostCharges",
)


def test_remediator_satisfies_the_protocol():
    assert isinstance(AgentRemediator(), Remediator)


def test_it_handles_a_breaking_finding():
    assert AgentRemediator().can_handle(FINDING, CHANGE) is True


def test_the_prompt_names_the_exact_file_and_line():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    assert "src/billing.ts" in prompt
    assert "line 6" in prompt


def test_the_prompt_states_what_changed_and_which_field():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    assert "response-property-removed" in prompt
    assert "status" in prompt
    assert "stripe.charges.create" in prompt


def test_the_prompt_constrains_scope_to_the_affected_call():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    lowered = prompt.lower()
    assert "do not" in lowered
    assert "refactor" in lowered


def test_previous_diagnostics_are_included_on_a_retry():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE, diagnostics="src/billing.ts(6,8): error TS2339")
    assert "TS2339" in prompt


def test_the_prompt_omits_a_diagnostics_section_on_the_first_attempt():
    assert "previous attempt" not in build_patch_prompt(FINDING, CHANGE, SITE).lower()
```

- [ ] **Step 4: Run it to verify it fails**

Run: `uv run pytest tests/test_agent_patch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.remediate'`

- [ ] **Step 5: Implement the remediator**

Create `src/sync/remediate/agent_patch.py`. Fill the marked call from the documentation read in Step 1; everything else is specified.

```python
"""Patch generation delegated to the Claude Agent SDK.

The Agent SDK runs against a throwaway clone, never a customer's working tree.
Nothing it produces is trusted: the graph typechecks the result and then waits
for the repository's own CI before anything becomes a pull request.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange

MODEL = "claude-opus-5"

_SCOPE_RULES = """
Rules:
- Change only what this specific API change requires. Do not refactor surrounding code.
- Do not add error handling, abstractions, or helpers that were not there before.
- Do not reformat lines you did not otherwise need to touch.
- If the removed value is still needed, derive it from what the API does return; if it
  cannot be derived, remove the usage rather than inventing a placeholder.
- Run `npx tsc --noEmit` yourself and keep editing until it is clean.
""".strip()


def build_patch_prompt(
    finding: Finding,
    change: VendorChange,
    site: CallSite,
    diagnostics: str = "",
) -> str:
    """Everything the agent needs, and nothing it does not."""
    field = change.raw.get("field") or change.path_ptr.rsplit("/", 1)[-1]

    sections = [
        "A third-party API changed and this repository's code no longer matches it.",
        "",
        f"Vendor: {change.vendor_id}",
        f"Change: {change.kind}",
        f"Operation: {change.operation_id}  ({change.from_version} -> {change.to_version})",
        f"Affected field: {field}",
        "",
        f"Call site: {site.path}, line {site.line}",
        f"SDK call: {site.symbol}",
        f"Arguments passed: {', '.join(site.args_keys) or 'none'}",
        f"Response fields read: {', '.join(site.response_fields_read) or 'none'}",
        "",
        f"Why this matters: {finding.rationale}",
        "",
        _SCOPE_RULES,
    ]

    if diagnostics:
        sections += [
            "",
            "A previous attempt failed typechecking with:",
            "",
            diagnostics,
            "",
            "Fix the cause rather than suppressing the error.",
        ]

    return "\n".join(sections)


def _git_diff(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "diff"], cwd=repo_path, capture_output=True, text=True, check=True
    )
    return result.stdout


class AgentRemediator:
    """Remediator backed by the Claude Agent SDK."""

    strategy = "agent"

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return finding.severity in ("breaking", "deprecation")

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        prompt = build_patch_prompt(finding, change, site, diagnostics)
        repo_path = Path(repo.local_path)

        # --- Agent SDK call ------------------------------------------------
        # Confirmed against https://code.claude.com/docs/en/agent-sdk in Step 1.
        # Requirements for the options passed here:
        #   - working directory: repo_path
        #   - model: MODEL
        #   - thinking: {"type": "adaptive"}
        #   - output_config: {"effort": "xhigh"}
        #   - allowed tools: Read, Write, Edit, Bash, Glob, Grep
        #   - no network tools; this task needs none
        # Drive the call to completion, then read the result from the working tree.
        self._run_agent(prompt, repo_path)
        # -------------------------------------------------------------------

        return Patch(
            diff=_git_diff(repo_path),
            strategy=self.strategy,
            rationale=finding.rationale,
        )

    def _run_agent(self, prompt: str, repo_path: Path) -> None:
        """Isolated so tests can substitute it without touching `propose`."""
        raise NotImplementedError("fill from the Agent SDK documentation read in Step 1")
```

Create an empty `src/sync/remediate/__init__.py`.

- [ ] **Step 6: Run the prompt tests to verify they pass**

Run: `uv run pytest tests/test_agent_patch.py -v`
Expected: PASS, 7 tests. `_run_agent` remains unimplemented and is not exercised by these tests.

- [ ] **Step 7: Implement `_run_agent` from the documentation**

Replace the `NotImplementedError` with the confirmed Agent SDK call. Verify it manually against one fixture repository before continuing:

```bash
uv run python -c "
from pathlib import Path
from sync.remediate.agent_patch import AgentRemediator
print(AgentRemediator()._run_agent('List the TypeScript files here, then stop.', Path('tests/fixtures/ts/simple')))
"
```

Expected: the agent runs and terminates without error.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add Claude Agent SDK patch remediator"
```

---

### Task 9: The LangGraph remediation graph

**Files:**
- Create: `src/sync/remediate/state.py`, `src/sync/remediate/nodes.py`, `src/sync/remediate/graph.py`
- Test: `tests/test_remediation_graph.py`

**Interfaces:**
- Consumes: everything from Tasks 2, 6, 7, 8; the `Forge` protocol defined below is implemented in Task 10.
- Produces: `build_graph(store, adapter, remediator, forge, checkpointer) -> CompiledGraph`, `RunState`, and the node functions.

- [ ] **Step 1: Add the dependencies**

```bash
uv add langgraph
```

Only `langgraph` is used by this task. `langgraph-checkpoint-postgres` belongs to Task 11, where the CLI wires the real checkpointer — this task's tests use `InMemorySaver`, which ships with `langgraph` itself. `langchain` and `langchain-anthropic` are used by no task in M0; the changelog-parsing chain that would need them is not in this milestone. Add a dependency in the task that consumes it, not before.

- [ ] **Step 2: Write the failing graph test**

Every dependency is stubbed. This test asserts control flow — the retry bounds and the abandonment path — which is the part that will actually be wrong.

Create `tests/test_remediation_graph.py`:

```python
from dataclasses import dataclass, field

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.remediate.graph import build_graph

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-property-removed", operation_id="PostCharges", path_ptr="/x/status",
    severity="breaking", source="oasdiff", raw={"field": "status"},
)
FINDING = Finding(
    detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="status removed",
)
REPO = RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40)


class StubStore:
    def get_call_site(self, _id): return SITE
    def get_vendor_change(self, _id): return CHANGE
    def set_finding_status(self, _id, _status): self.status = _status


@dataclass
class StubAdapter:
    verdicts: list[bool] = field(default_factory=lambda: [True])
    calls: int = 0

    def static_verify(self, repo, patch) -> VerifyResult:
        ok = self.verdicts[min(self.calls, len(self.verdicts) - 1)]
        self.calls += 1
        return VerifyResult(ok=ok, diagnostics="" if ok else "error TS2339")


@dataclass
class StubRemediator:
    strategy: str = "agent"
    calls: int = 0

    def can_handle(self, finding, change) -> bool: return True

    def propose(self, finding, change, site, repo, diagnostics="") -> Patch:
        self.calls += 1
        return Patch(diff="--- a\n+++ b\n", strategy=self.strategy, rationale="fix")


@dataclass
class StubForge:
    ci_results: list[bool] = field(default_factory=lambda: [True])
    polls: int = 0
    pushes: int = 0
    pr_url: str | None = None

    def push_branch(self, repo, patch) -> str:
        self.pushes += 1
        return "sync/fix-1"

    def await_ci(self, repo, branch) -> tuple[bool, str]:
        green = self.ci_results[min(self.polls, len(self.ci_results) - 1)]
        self.polls += 1
        return green, "https://github.com/o/r/actions/runs/1"

    def open_pull_request(self, repo, branch, evidence) -> str:
        self.pr_url = "https://github.com/o/r/pull/1"
        return self.pr_url


def _run(adapter, remediator, forge):
    graph = build_graph(
        store=StubStore(), adapter=adapter, remediator=remediator,
        forge=forge, checkpointer=InMemorySaver(),
    )
    return graph.invoke(
        {"finding": FINDING, "repo": REPO},
        config={"configurable": {"thread_id": "t1"}},
    )


def test_a_clean_run_opens_a_pull_request():
    forge = StubForge()
    result = _run(StubAdapter(), StubRemediator(), forge)
    assert result["pr_url"] == "https://github.com/o/r/pull/1"
    assert result["outcome"] == "opened"


def test_a_static_failure_retries_the_patch():
    remediator = StubRemediator()
    result = _run(StubAdapter(verdicts=[False, True]), remediator, StubForge())
    assert remediator.calls == 2
    assert result["outcome"] == "opened"


def test_three_static_failures_abandon_without_pushing():
    forge = StubForge()
    remediator = StubRemediator()
    result = _run(StubAdapter(verdicts=[False, False, False, False]), remediator, forge)
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None
    assert remediator.calls == 3


def test_a_red_ci_run_retries_the_patch_once():
    remediator = StubRemediator()
    result = _run(StubAdapter(), remediator, StubForge(ci_results=[False, True]))
    assert remediator.calls == 2
    assert result["outcome"] == "opened"


def test_two_red_ci_runs_abandon_and_record_why():
    forge = StubForge(ci_results=[False, False, False])
    result = _run(StubAdapter(), StubRemediator(), forge)
    assert result["outcome"] == "abandoned"
    assert forge.pr_url is None
    assert "CI" in result["abandon_reason"]


def test_diagnostics_from_a_failed_verification_reach_the_next_attempt():
    @dataclass
    class Recording(StubRemediator):
        seen: list[str] = field(default_factory=list)

        def propose(self, finding, change, site, repo, diagnostics=""):
            self.seen.append(diagnostics)
            return super().propose(finding, change, site, repo, diagnostics)

    remediator = Recording()
    _run(StubAdapter(verdicts=[False, True]), remediator, StubForge())
    assert remediator.seen[0] == ""
    assert "TS2339" in remediator.seen[1]


def test_state_is_checkpointed_at_every_node():
    saver = InMemorySaver()
    graph = build_graph(
        store=StubStore(), adapter=StubAdapter(), remediator=StubRemediator(),
        forge=StubForge(), checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "t2"}}
    graph.invoke({"finding": FINDING, "repo": REPO}, config=config)
    assert graph.get_state(config).values["outcome"] == "opened"


def test_an_agent_run_that_fails_is_abandoned_rather_than_crashing_the_graph():
    @dataclass
    class Failing(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            raise RuntimeError("agent run failed (error_max_turns): []")

    remediator = Failing()
    forge = StubForge()
    result = _run(StubAdapter(), remediator, forge)
    assert result["outcome"] == "abandoned"
    assert forge.pushes == 0
    assert forge.pr_url is None
    assert remediator.calls == 3
    assert "agent run failed" in result["abandon_reason"]


def test_a_patch_that_changes_nothing_is_never_pushed():
    @dataclass
    class NoChange(StubRemediator):
        def propose(self, finding, change, site, repo, diagnostics=""):
            self.calls += 1
            return Patch(diff="", strategy=self.strategy, rationale="nothing to do")

    forge = StubForge()
    result = _run(StubAdapter(), NoChange(), forge)
    assert result["outcome"] == "abandoned"
    assert forge.pushes == 0
    assert forge.pr_url is None
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_remediation_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.remediate.graph'`

- [ ] **Step 4: Define the state**

Create `src/sync/remediate/state.py`:

```python
"""State carried through the remediation graph and checkpointed at every node."""

from __future__ import annotations

from typing import Literal, TypedDict

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange

Outcome = Literal["running", "opened", "abandoned"]

MAX_STATIC_ATTEMPTS = 3
MAX_CI_ATTEMPTS = 2


class RunState(TypedDict, total=False):
    finding: Finding
    repo: RepoRef
    site: CallSite
    change: VendorChange
    # None means the patch node produced nothing usable -- either the remediator
    # raised, or it returned an empty diff. Both must reach `abandon`, never `push_branch`.
    patch: Patch | None
    diagnostics: str
    static_attempts: int
    ci_attempts: int
    branch: str
    ci_url: str
    evidence: Evidence
    pr_url: str | None
    outcome: Outcome
    abandon_reason: str
```

- [ ] **Step 5: Define the forge protocol and the nodes**

Create `src/sync/remediate/nodes.py`:

```python
"""Individual nodes of the remediation graph.

Each node is a plain function of state. Keeping them free of graph wiring makes
them unit-testable and keeps `graph.py` to assembly only.
"""

from __future__ import annotations

from typing import Protocol

from sync.core import Evidence, Patch, RepoRef
from sync.remediate.state import MAX_CI_ATTEMPTS, MAX_STATIC_ATTEMPTS, RunState


class Forge(Protocol):
    def push_branch(self, repo: RepoRef, patch: Patch) -> str: ...
    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]: ...
    def open_pull_request(self, repo: RepoRef, branch: str, evidence: Evidence) -> str: ...


def make_locate(store):
    def locate(state: RunState) -> RunState:
        finding = state["finding"]
        return {
            "site": store.get_call_site(finding.call_site_id),
            "change": store.get_vendor_change(finding.vendor_change_id),
            "static_attempts": 0,
            "ci_attempts": 0,
            "diagnostics": "",
            "outcome": "running",
        }

    return locate


def make_patch(remediator):
    def patch(state: RunState) -> RunState:
        attempts = state.get("static_attempts", 0) + 1
        try:
            proposed = remediator.propose(
                state["finding"], state["change"], state["site"], state["repo"],
                diagnostics=state.get("diagnostics", ""),
            )
        except Exception as exc:
            return {"patch": None, "static_attempts": attempts, "diagnostics": str(exc)}

        if not proposed.diff.strip():
            return {
                "patch": None,
                "static_attempts": attempts,
                "diagnostics": "the remediator produced no change",
            }

        return {"patch": proposed, "static_attempts": attempts, "diagnostics": ""}

    return patch


def route_after_patch(state: RunState) -> str:
    """A run that failed and a run that changed nothing leave the same empty diff.

    Neither may reach `push_branch`: a no-op branch passes CI and would open a
    pull request that claims to fix something and does not.
    """
    if state.get("patch") is not None:
        return "static_verify"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


def make_static_verify(adapter):
    def static_verify(state: RunState) -> RunState:
        result = adapter.static_verify(state["repo"], state["patch"])
        return {"diagnostics": result.diagnostics if not result.ok else ""}

    return static_verify


def route_after_static(state: RunState) -> str:
    if not state.get("diagnostics"):
        return "push_branch"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


def make_push_branch(forge: Forge):
    def push_branch(state: RunState) -> RunState:
        return {"branch": forge.push_branch(state["repo"], state["patch"])}

    return push_branch


def make_await_ci(forge: Forge):
    def await_ci(state: RunState) -> RunState:
        green, url = forge.await_ci(state["repo"], state["branch"])
        return {
            "ci_url": url,
            "ci_attempts": state.get("ci_attempts", 0) + 1,
            "diagnostics": "" if green else f"CI failed: {url}",
        }

    return await_ci


def route_after_ci(state: RunState) -> str:
    if not state.get("diagnostics"):
        return "open_pr"
    if state.get("ci_attempts", 0) >= MAX_CI_ATTEMPTS:
        return "abandon"
    return "patch"


def make_open_pr(forge: Forge):
    def open_pr(state: RunState) -> RunState:
        change = state["change"]
        site = state["site"]
        evidence = Evidence(
            spec_diff=change.raw,
            changelog_entry=state["finding"].rationale,
            call_sites=[f"{site.path}:{site.line}"],
            ci_run_url=state.get("ci_url", ""),
        )
        url = forge.open_pull_request(state["repo"], state["branch"], evidence)
        return {"evidence": evidence, "pr_url": url, "outcome": "opened"}

    return open_pr


def make_abandon(store):
    def abandon(state: RunState) -> RunState:
        reason = state.get("diagnostics") or "unknown"
        finding_id = state["finding"].id
        if finding_id:
            store.set_finding_status(finding_id, "abandoned")
        return {"outcome": "abandoned", "abandon_reason": reason, "pr_url": None}

    return abandon
```

- [ ] **Step 6: Assemble the graph**

Create `src/sync/remediate/graph.py`:

```python
"""Assembly of the remediation graph.

`await_ci` is the reason this is a graph and not a loop: a CI run takes minutes,
and a worker restart during that wait must not lose the run. The checkpointer
persists state at every node, so a restarted run resumes where it stopped.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from sync.remediate import nodes
from sync.remediate.state import RunState


def build_graph(store, adapter, remediator, forge, checkpointer):
    builder = StateGraph(RunState)

    builder.add_node("locate", nodes.make_locate(store))
    builder.add_node("patch", nodes.make_patch(remediator))
    builder.add_node("static_verify", nodes.make_static_verify(adapter))
    builder.add_node("push_branch", nodes.make_push_branch(forge))
    builder.add_node("await_ci", nodes.make_await_ci(forge))
    builder.add_node("open_pr", nodes.make_open_pr(forge))
    builder.add_node("abandon", nodes.make_abandon(store))

    builder.add_edge(START, "locate")
    builder.add_edge("locate", "patch")

    builder.add_conditional_edges(
        "patch",
        nodes.route_after_patch,
        {"static_verify": "static_verify", "patch": "patch", "abandon": "abandon"},
    )

    builder.add_conditional_edges(
        "static_verify",
        nodes.route_after_static,
        {"patch": "patch", "push_branch": "push_branch", "abandon": "abandon"},
    )

    builder.add_edge("push_branch", "await_ci")

    builder.add_conditional_edges(
        "await_ci",
        nodes.route_after_ci,
        {"patch": "patch", "open_pr": "open_pr", "abandon": "abandon"},
    )

    builder.add_edge("open_pr", END)
    builder.add_edge("abandon", END)

    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 7: Run the graph tests to verify they pass**

Run: `uv run pytest tests/test_remediation_graph.py -v`
Expected: PASS, 9 tests.

If `test_three_static_failures_abandon_without_pushing` sees four `propose` calls instead of three, `static_attempts` is being incremented in the wrong node — it must increment in `patch`, so the count reflects attempts made, and `route_after_static` compares with `>=`.

`static_attempts` is deliberately not reset when a red CI run sends the flow back to `patch`. It bounds total patch attempts for the whole run, not attempts since the last CI push. Resetting it would let a run alternate between CI failures and static failures indefinitely.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add LangGraph remediation graph with bounded retries"
```

---

### Task 10: The GitHub forge

**Files:**
- Create: `src/sync/forge/__init__.py`, `src/sync/forge/github.py`
- Test: `tests/test_github_forge.py`

**Interfaces:**
- Consumes: `Evidence`, `Patch`, `RepoRef` from `sync.core`; satisfies the `Forge` protocol from Task 9.
- Produces: `GitHubForge(poll_interval_seconds=15, timeout_seconds=1800)` with `push_branch`, `await_ci`, `open_pull_request`, plus `render_pr_body(evidence) -> str`.

- [ ] **Step 1: Write the failing test**

Body rendering and branch naming are deterministic and get real tests. The network calls are exercised end-to-end in Task 11.

Create `tests/test_github_forge.py`:

```python
import json

from sync.core import Evidence, Patch, RepoRef
from sync.forge.github import GitHubForge, branch_name_for, render_pr_body
from sync.remediate.nodes import Forge

EVIDENCE = Evidence(
    spec_diff={"id": "response-property-removed", "field": "status"},
    changelog_entry="`status` was removed from charge responses",
    call_sites=["src/billing.ts:6"],
    ci_run_url="https://github.com/o/r/actions/runs/123",
)
PATCH = Patch(diff="--- a\n+++ b\n", strategy="agent", rationale="status removed")
REPO = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path="/tmp/r", head_sha="0" * 40)


def test_forge_satisfies_the_protocol_shape():
    assert isinstance(GitHubForge(), Forge)


def test_branch_name_is_deterministic_and_git_safe():
    name = branch_name_for(PATCH, REPO)
    assert name.startswith("sync/")
    assert " " not in name
    assert branch_name_for(PATCH, REPO) == name


def test_pr_body_contains_every_evidence_element():
    body = render_pr_body(EVIDENCE)
    assert "response-property-removed" in body
    assert "status" in body
    assert "src/billing.ts:6" in body
    assert "https://github.com/o/r/actions/runs/123" in body


def test_pr_body_states_that_ci_verified_the_change():
    body = render_pr_body(EVIDENCE).lower()
    assert "ci" in body
    assert "passed" in body or "green" in body


def test_pr_body_discloses_that_it_was_generated():
    assert "Sync" in render_pr_body(EVIDENCE)


HEAD = "a" * 40


def _forge_returning(payload: str, timeout_seconds: int = 1) -> GitHubForge:
    """A forge whose subprocess layer is replaced, so `await_ci`'s decision logic
    can be tested without git, without `gh`, and without the network."""
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=timeout_seconds)

    def fake_run(args, cwd):
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        return payload

    forge._run = fake_run
    return forge


def _run(status: str, conclusion: str, sha: str = HEAD, url: str = "https://ci/1") -> dict:
    return {"status": status, "conclusion": conclusion, "url": url, "headSha": sha}


def test_ci_is_green_when_every_run_for_the_commit_succeeded():
    forge = _forge_returning(json.dumps([_run("completed", "success"), _run("completed", "success")]))
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/1"


def test_one_failing_workflow_makes_the_whole_commit_red():
    forge = _forge_returning(json.dumps([_run("completed", "success"), _run("completed", "failure")]))
    green, _ = forge.await_ci(REPO, "sync/x")
    assert green is False


def test_runs_still_in_progress_are_not_treated_as_a_verdict():
    forge = _forge_returning(json.dumps([_run("completed", "success"), _run("in_progress", None)]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "no completed CI run" in detail


def test_a_run_from_an_earlier_push_to_the_same_branch_does_not_count():
    forge = _forge_returning(json.dumps([_run("completed", "success", sha="b" * 40)]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "no completed CI run" in detail


def test_a_branch_with_no_runs_at_all_is_red():
    forge = _forge_returning("[]")
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "no completed CI run" in detail
```

`await_ci` is the verification gate, and it is the one part of this task where a
wrong answer ships a broken patch to a customer. Test it as decision logic over
JSON, which is all it is. The `gh` and `git` invocations themselves are exercised
in Task 11.

Each negative test spins the poll loop for one second of wall clock, because
`poll_interval_seconds=0` and `timeout_seconds=1`. That is deliberate: it proves
the timeout path returns red rather than hanging or raising.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_github_forge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sync.forge'`

- [ ] **Step 3: Implement the forge**

Create `src/sync/forge/github.py`:

```python
"""Git and GitHub operations via the authenticated `gh` CLI.

`gh` is used rather than a REST client because it is already installed and
authenticated on developer machines, which keeps M0 free of a separate token
management story. The hosted control plane at M4 will need a GitHub App instead.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from sync.core import Evidence, Patch, RepoRef


def _gh() -> str:
    found = shutil.which("gh")
    if found is None:
        raise FileNotFoundError("gh CLI not found on PATH")
    return found


def branch_name_for(patch: Patch, repo: RepoRef) -> str:
    digest = hashlib.sha256(f"{repo.repo_id}|{patch.diff}".encode()).hexdigest()[:12]
    return f"sync/api-drift-{digest}"


def render_pr_body(evidence: Evidence) -> str:
    sites = "\n".join(f"- `{site}`" for site in evidence.call_sites)
    return f"""## What changed upstream

{evidence.changelog_entry}

```json
{json.dumps(evidence.spec_diff, indent=2)}
```

## Affected call sites

{sites}

## Verification

CI passed on this branch before the pull request was opened: {evidence.ci_run_url}

---

Opened by **Sync**. Nothing reaches a pull request without a green CI run on the
branch — if this is wrong, the verification gate is what needs fixing, not just
this diff.
"""


class GitHubForge:
    def __init__(self, poll_interval_seconds: int = 15, timeout_seconds: int = 1800) -> None:
        self._poll = poll_interval_seconds
        self._timeout = timeout_seconds

    def _run(self, args: list[str], cwd: Path) -> str:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def push_branch(self, repo: RepoRef, patch: Patch) -> str:
        """Commit the tracked changes and push them. The patch is already applied on disk.

        `git add -u` rather than `-A`: the patch came from `git diff`, which sees
        tracked modifications only, so staging untracked files would commit
        whatever the agent's tool calls happened to leave behind — a build
        directory, a log, a stray dependency install — none of which the patch
        or the review evidence describes.

        The graph guarantees a non-empty diff before this runs, so `git commit`
        cannot fail here for an empty index.
        """
        path = Path(repo.local_path)
        branch = branch_name_for(patch, repo)
        self._run(["git", "checkout", "-B", branch], path)
        self._run(["git", "add", "-u"], path)
        self._run(["git", "commit", "-m", f"fix: {patch.rationale}"], path)
        self._run(["git", "push", "-u", "origin", branch, "--force-with-lease"], path)
        return branch

    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]:
        """Poll every workflow run for the pushed commit. Returns (green, detail).

        Green requires that runs exist for this exact commit, that all of them
        have completed, and that every one concluded successfully. `--limit 1`
        would report whichever workflow started last, so a repository whose lint
        job passes and whose test job fails would read as green.

        Filtering on `headSha` matters for the same reason: a run left over from
        an earlier push to the same branch says nothing about this patch.

        Runs that never appear are red at the timeout, not green — an
        unverifiable patch must never reach a pull request.
        """
        path = Path(repo.local_path)
        head = self._run(["git", "rev-parse", "HEAD"], path)
        deadline = time.monotonic() + self._timeout
        gh = _gh()

        while time.monotonic() < deadline:
            raw = self._run(
                [gh, "run", "list", "--branch", branch, "--limit", "50",
                 "--json", "status,conclusion,url,headSha"],
                path,
            )
            runs = [run for run in json.loads(raw or "[]") if run["headSha"] == head]
            if runs and all(run["status"] == "completed" for run in runs):
                return all(run["conclusion"] == "success" for run in runs), runs[0]["url"]
            time.sleep(self._poll)

        return False, f"no completed CI run for {head[:12]} within {self._timeout}s"

    def open_pull_request(self, repo: RepoRef, branch: str, evidence: Evidence) -> str:
        path = Path(repo.local_path)
        return self._run(
            [_gh(), "pr", "create",
             "--title", f"fix: {evidence.changelog_entry[:60]}",
             "--body", render_pr_body(evidence),
             "--head", branch],
            path,
        )
```

Create an empty `src/sync/forge/__init__.py`.

- [ ] **Step 4: Make the `Forge` protocol runtime-checkable**

`src/sync/remediate/nodes.py` declares `class Forge(Protocol)` without the decorator, while all four protocols in `sync/core/protocols.py` carry it. Add `@runtime_checkable` above it and import `runtime_checkable` alongside `Protocol`, so `isinstance(GitHubForge(), Forge)` in the test above actually checks something.

This catches a renamed or missing method. It does not check signatures — a `push_branch` with the wrong parameters still passes. That gap closes at Task 11's end-to-end run.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_github_forge.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add GitHub forge with CI gate and evidence-bearing PR body"
```

---

### Task 11: CLI wiring and the end-to-end acceptance run

This is the milestone. Everything before it is scaffolding for this one command.

**Files:**
- Create: `src/sync/cli.py`, `tests/test_e2e_stripe.py`
- Modify: `pyproject.toml` — add the console script

**Interfaces:**
- Consumes: every component built so far.
- Produces: the `sync` console command with a `run` subcommand.

- [ ] **Step 1: Fork the target repository and give it a CI check**

`stripe/stripe-connect-furever-demo` is Stripe's own TypeScript demo — real, non-trivial SDK usage, and uncontroversial to fork.

```bash
gh repo fork stripe/stripe-connect-furever-demo --clone=false --remote=false
```

The fork must have a check that runs on push, because a branch with no checks is treated as red by design. Add a minimal typecheck workflow to the fork's default branch:

```yaml
# .github/workflows/typecheck.yml
name: typecheck
on: [push, pull_request]
jobs:
  tsc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - run: npm ci
      - run: npx tsc --noEmit
```

Commit that to the fork before running anything else. Record the fork's URL — the end-to-end test needs it.

- [ ] **Step 2: Choose a Stripe version pair that actually contains a breaking change**

Tags on `stripe/openapi` are sequential (`v2345` is current). Find a pair whose diff is non-empty:

```bash
mkdir -p .cache/specs
uv run python -c "
from pathlib import Path
from sync.signals.stripe.adapter import fetch_spec
from sync.signals.oasdiff import run_oasdiff_breaking
base = fetch_spec('v2200', Path('.cache/specs/v2200.json'))
head = fetch_spec('v2345', Path('.cache/specs/v2345.json'))
records = run_oasdiff_breaking(base, head)
print(len(records), 'breaking changes')
print(records[0] if records else 'none - widen the tag range')
"
```

Expected: a non-zero count. If it is zero, widen the range and try again. Record the chosen pair.

- [ ] **Step 3: Write the CLI**

Create `src/sync/cli.py`:

```python
"""Local driver for a Sync run. The only entry point at M0."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import RepoRef
from sync.detect.vendor_change import VendorChangeDetector
from sync.forge.github import GitHubForge
from sync.graph.store import GraphStore
from sync.index.typescript import TypeScriptAdapter
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.graph import build_graph
from sync.signals.stripe.adapter import StripeAdapter, fetch_spec
from sync.signals.stripe.symbols import build_symbol_map

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"


def _clone(url: str, dest: Path) -> RepoRef:
    subprocess.run(["git", "clone", "--depth", "50", url, str(dest)], check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True, check=True
    ).stdout.strip()
    return RepoRef(repo_id=dest.name, url=url, local_path=str(dest), head_sha=head)


def run(args: argparse.Namespace) -> int:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    base_spec = fetch_spec(args.from_version, cache / f"{args.from_version}.json")
    head_spec = fetch_spec(args.to_version, cache / f"{args.to_version}.json")

    symbol_map_path = cache / "symbols.json"
    symbol_map_path.write_text(json.dumps(build_symbol_map(json.loads(head_spec.read_text()))))

    vendor = StripeAdapter(spec_dir=cache, symbol_map_path=symbol_map_path)
    adapter = TypeScriptAdapter(vendor_adapter=vendor)

    store = GraphStore(args.dsn)
    store.apply_schema()

    with tempfile.TemporaryDirectory() as workdir:
        repo = _clone(args.repo, Path(workdir) / "repo")

        if not adapter.matches(repo):
            print(f"{args.repo} does not depend on the Stripe SDK", file=sys.stderr)
            return 2

        for site in adapter.index(repo):
            store.upsert_call_site(site)
        for change in vendor.fetch_changes(args.from_version, args.to_version):
            store.upsert_vendor_change(change)

        # Persist findings before running the graph: `scan()` returns unsaved
        # findings with no id, and the checkpointer needs a stable thread_id.
        findings = []
        for finding in VendorChangeDetector(store).scan():
            finding.id = store.insert_finding(finding)
            findings.append(finding)

        print(f"{len(findings)} finding(s)")
        if not findings:
            return 0

        with PostgresSaver.from_conn_string(args.dsn) as checkpointer:
            checkpointer.setup()
            graph = build_graph(
                store=store, adapter=adapter, remediator=AgentRemediator(),
                forge=GitHubForge(), checkpointer=checkpointer,
            )
            for finding in findings:
                state = graph.invoke(
                    {"finding": finding, "repo": repo},
                    config={"configurable": {"thread_id": finding.id}},
                )
                print(f"{state['outcome']}: {state.get('pr_url') or state.get('abandon_reason')}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sync")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="detect and remediate vendor changes in a repository")
    run_parser.add_argument("--vendor", default="stripe", choices=["stripe"])
    run_parser.add_argument("--from-version", dest="from_version", required=True)
    run_parser.add_argument("--to-version", dest="to_version", required=True)
    run_parser.add_argument("--repo", required=True, help="git URL of the repository to scan")
    run_parser.add_argument("--dsn", default=DEFAULT_DSN)
    run_parser.add_argument("--cache", default=".cache/specs")
    run_parser.set_defaults(func=run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Register the console script**

Add to `pyproject.toml`:

```toml
[project.scripts]
sync = "sync.cli:main"
```

- [ ] **Step 5: Write the end-to-end test**

Create `tests/test_e2e_stripe.py`. Substitute the fork URL from Step 1 and the version pair from Step 2:

```python
"""M0 acceptance. Makes network and model calls; deselected by default.

Run with: uv run pytest tests/test_e2e_stripe.py -m e2e -v -s
"""

import os
import subprocess
import sys

import pytest

FORK_URL = os.environ["SYNC_E2E_REPO"]      # e.g. https://github.com/<you>/stripe-connect-furever-demo
FROM_VERSION = os.environ.get("SYNC_E2E_FROM", "v2200")
TO_VERSION = os.environ.get("SYNC_E2E_TO", "v2345")


@pytest.mark.e2e
def test_one_command_produces_one_green_pull_request():
    result = subprocess.run(
        [sys.executable, "-m", "sync.cli", "run",
         "--vendor", "stripe",
         "--from-version", FROM_VERSION,
         "--to-version", TO_VERSION,
         "--repo", FORK_URL],
        capture_output=True,
        text=True,
        timeout=3600,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    assert result.returncode == 0, result.stderr
    assert "finding(s)" in result.stdout
    assert "opened: https://github.com/" in result.stdout, (
        "no pull request was opened; check whether the run abandoned and why"
    )
```

- [ ] **Step 6: Run the full unit suite to confirm nothing regressed**

Run: `uv run pytest -v`
Expected: PASS. The end-to-end test is deselected by the `-m 'not e2e'` default.

- [ ] **Step 7: Run the acceptance test**

```bash
export SYNC_E2E_REPO="https://github.com/<your-account>/stripe-connect-furever-demo"
uv run pytest tests/test_e2e_stripe.py -m e2e -v -s
```

Expected: a pull request URL printed, and a real pull request on the fork whose checks are green.

This is M0 acceptance. If the run abandons, the printed reason says whether it failed at `static_verify` (the patch never typechecked) or at `await_ci` (it typechecked but broke something else). Both are informative failures, not bugs in the harness — the gate working is the point.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add sync CLI and M0 end-to-end acceptance test"
```

---

## Deliberately deferred from M0

The specification describes a `strategize` node that prefers a deterministic codemod when a change maps to a known transform, falling back to the agent otherwise. This plan implements the agent path only, and the graph runs `locate → patch` with no `strategize` node.

The reason is that a codemod library is an optimization over a working system, not a prerequisite for one. Its value is lower cost and reviewability on the mechanical cases, and neither can be measured before we have seen which cases actually recur. Building it now would mean guessing at the transform catalogue.

The seam is already in place and costs nothing to leave open: `Remediator` is a protocol with `can_handle`, so a `CodemodRemediator` is a new class plus a `strategize` node that picks between registered remediators. No existing code changes when it arrives.

## Definition of Done

M0 is complete when `uv run pytest -v` is green and one `sync run` invocation produces one pull request on the fork whose CI checks pass. Anything short of that is not M0 complete.

# Sync MCP Graph Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the free local tier of Sync's graph surface — an MCP server that answers three binding questions from a SQLite-backed API Dependency Graph without reading a single source file into an agent's context.

**Architecture:** A `GraphStore` protocol in `sync.core` gains two implementations: the existing Postgres store (hosted) and a new SQLite store (local). A new `sync.mcp` package holds four things — a feed cache, pure tool functions returning Pydantic models, a tool registry whose schemas are our own data, and a thin adapter that binds the registry to the MCP SDK. Tool logic is tested without the SDK, so protocol wiring is the only thing that depends on it.

**Tech Stack:** Python 3.12, `uv`, Pydantic v2, `sqlite3` (standard library), `psycopg` (existing), `mcp` (Python SDK), `cryptography` (Ed25519 feed signing), pytest.

## Global Constraints

- The interpreter is `python`. **Never `python3`** — it is a Microsoft Store shim on this machine and will not run.
- Packages via `uv` only (`uv add`, `uv run`). Poetry is not installed.
- Postgres 16 in Docker on **port 5433**, not 5432.
- **`sync.core` imports nothing from any sibling package.** `tests/test_import_boundary.py` enforces this.
- **Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, and `subprocess.run(..., text=True)`. Locale default here is cp1252 and no test will catch a violation.
- Test first, always. Watch the test fail for the reason you expect before implementing.
- **No test touches the network or calls a vendor or model API.** Fixtures are committed.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Body explains why, not what.
- Git warns `LF will be replaced by CRLF` on every commit. Expected. Do not add `.gitattributes`.

## Prerequisite

This plan modifies `sync/core/models.py`, `sync/core/protocols.py`, and `sync/graph/store.py`, which the M0 branch owns. **Do not begin until `worktree-sync-m0-vendor-change` has merged.** Run `git log --oneline -1` on `main` and confirm the M0 acceptance commit is present.

## File Structure

| File | Responsibility |
|---|---|
| `src/sync/core/models.py` | Modify: add `BindingSource`, `binding_source` and `file_bytes` on `CallSite`, and the response envelope models |
| `src/sync/core/protocols.py` | Modify: add the `GraphStore` protocol |
| `src/sync/graph/store.py` | Modify: rename `GraphStore` to `PostgresGraphStore`, add the two new columns |
| `src/sync/graph/schema.sql` | Modify: add the two new columns |
| `src/sync/graph/sqlite_store.py` | Create: `SqliteGraphStore` |
| `src/sync/graph/schema_sqlite.sql` | Create: SQLite DDL |
| `src/sync/mcp/feed.py` | Create: fetch, verify, cache and read the vendor change feed |
| `src/sync/mcp/envelope.py` | Create: response envelope and the token-savings estimate |
| `src/sync/mcp/tools.py` | Create: the three tool functions, pure, SDK-free |
| `src/sync/mcp/registry.py` | Create: tool schemas as data, plus the dispatcher |
| `src/sync/mcp/server.py` | Create: the thin MCP SDK adapter and entry point |

---

### Task 1: Add binding provenance and file size to the call-site contract

**Files:**
- Modify: `src/sync/core/models.py`
- Modify: `src/sync/graph/schema.sql`
- Modify: `src/sync/graph/store.py`
- Test: `tests/test_core_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `BindingSource = Literal["static", "resolved", "observed"]`; `CallSite.binding_source: BindingSource` defaulting to `"static"`; `CallSite.file_bytes: int` defaulting to `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_core_models.py
from sync.core import CallSite


def _site(**overrides) -> CallSite:
    base = dict(
        repo_id="r1", path="src/billing.ts", line=6, col=2,
        vendor_id="stripe", operation_id="POST /v1/charges",
        symbol="stripe.charges.create", sdk_version="18.0.0", content_hash="abc",
    )
    base.update(overrides)
    return CallSite(**base)


def test_binding_source_defaults_to_static():
    assert _site().binding_source == "static"


def test_binding_source_accepts_the_three_rungs():
    for rung in ("static", "resolved", "observed"):
        assert _site(binding_source=rung).binding_source == rung


def test_binding_source_rejects_an_unknown_rung():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _site(binding_source="guessed")


def test_file_bytes_defaults_to_zero():
    assert _site().file_bytes == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core_models.py -v`
Expected: FAIL — `CallSite` has no attribute `binding_source`.

- [ ] **Step 3: Write minimal implementation**

In `src/sync/core/models.py`, add the type alias beside the existing ones:

```python
BindingSource = Literal["static", "resolved", "observed"]
```

Add two fields to `CallSite`, after `content_hash`:

```python
    binding_source: BindingSource = "static"
    file_bytes: int = 0
```

Export `BindingSource` from `src/sync/core/__init__.py` alongside the other names.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core_models.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Add the columns to the Postgres schema**

In `src/sync/graph/schema.sql`, inside `call_site`, after `content_hash`:

```sql
    binding_source       TEXT NOT NULL DEFAULT 'static',
    file_bytes           INTEGER NOT NULL DEFAULT 0,
```

- [ ] **Step 6: Carry the columns through the Postgres upsert**

In `src/sync/graph/store.py`, in `upsert_call_site`, add both columns to the INSERT column list, add two `%s` placeholders, add `site.binding_source, site.file_bytes` to the parameter tuple, and add to the `DO UPDATE SET` clause:

```sql
                    binding_source = EXCLUDED.binding_source,
                    file_bytes = EXCLUDED.file_bytes,
```

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS. Postgres tests need `docker compose up -d` first.

- [ ] **Step 8: Commit**

```bash
git add src/sync/core/models.py src/sync/core/__init__.py src/sync/graph/schema.sql src/sync/graph/store.py tests/test_core_models.py
git commit -m "feat: record how a call-site binding was established"
```

---

### Task 2: Extract the GraphStore protocol

**Files:**
- Modify: `src/sync/core/protocols.py`
- Modify: `src/sync/graph/store.py`
- Modify: `src/sync/graph/__init__.py`
- Test: `tests/test_graph_store_protocol.py`

**Interfaces:**
- Consumes: `CallSite`, `Finding`, `VendorChange`, `FindingStatus` from Task 1's module. `Severity` and `CallSite.indexed_at` already exist in `sync.core` from M0 — no export work is needed for them.
- Produces: `sync.core.protocols.GraphStore`, a runtime-checkable Protocol; `sync.graph.PostgresGraphStore`, the renamed concrete class, gaining `call_site_at(path, line) -> CallSite | None` and `all_call_sites() -> list[CallSite]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_store_protocol.py
from sync.core import GraphStore
from sync.graph import PostgresGraphStore


def test_postgres_store_satisfies_the_protocol():
    assert isinstance(PostgresGraphStore("postgresql://unused"), GraphStore)


def test_protocol_names_every_method_the_store_offers():
    required = {
        "apply_schema", "upsert_call_site", "upsert_vendor_change", "insert_finding",
        "call_sites_for_operation", "get_call_site", "call_site_at", "all_call_sites",
        "get_vendor_change", "all_vendor_changes", "open_findings", "set_finding_status",
    }
    assert required <= set(dir(GraphStore))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph_store_protocol.py -v`
Expected: FAIL — cannot import `GraphStore` from `sync.core`.

- [ ] **Step 3: Add the protocol**

In `src/sync/core/protocols.py`, import `FindingStatus` alongside the existing model imports, then append:

```python
@runtime_checkable
class GraphStore(Protocol):
    """Persistence and queries for the API Dependency Graph."""

    def apply_schema(self) -> None: ...

    def upsert_call_site(self, site: CallSite) -> str: ...

    def upsert_vendor_change(self, change: VendorChange) -> str: ...

    def insert_finding(self, finding: Finding) -> str: ...

    def call_sites_for_operation(self, vendor_id: str, operation_id: str) -> list[CallSite]: ...

    def get_call_site(self, call_site_id: str) -> CallSite: ...

    def call_site_at(self, path: str, line: int) -> CallSite | None: ...

    def all_call_sites(self) -> list[CallSite]: ...

    def get_vendor_change(self, change_id: str) -> VendorChange: ...

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]: ...

    def open_findings(self) -> list[Finding]: ...

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None: ...
```

Export `GraphStore` from `src/sync/core/__init__.py`.

- [ ] **Step 4: Implement the two new methods on the Postgres store**

`explain_call_site` must answer for any indexed line, not only lines that already carry a finding, and index
freshness must come from the call sites themselves. Neither is reachable through the existing methods. Add to
`src/sync/graph/store.py`:

```python
    def call_site_at(self, path: str, line: int) -> CallSite | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM call_site WHERE path = %s AND line = %s", (path, line)
            ).fetchone()
        return None if row is None else CallSite(**row)

    def all_call_sites(self) -> list[CallSite]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM call_site ORDER BY path, line").fetchall()
        return [CallSite(**row) for row in rows]
```

- [ ] **Step 5: Rename the concrete class**

In `src/sync/graph/store.py`, rename `class GraphStore:` to `class PostgresGraphStore:`. Update `src/sync/graph/__init__.py` to export `PostgresGraphStore`. Then find every other use and update it:

Run: `grep -rn "GraphStore" src tests --include=*.py`
Update each call site to `PostgresGraphStore`, except imports of the protocol from `sync.core`.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS, including `tests/test_import_boundary.py`, which must still pass — the protocol references only `sync.core.models`.

- [ ] **Step 7: Commit**

```bash
git add src/sync/core/protocols.py src/sync/core/__init__.py src/sync/graph/ tests/
git commit -m "refactor: put the graph store behind a protocol"
```

---

### Task 3: Add the SQLite graph store

**Files:**
- Create: `src/sync/graph/sqlite_store.py`
- Create: `src/sync/graph/schema_sqlite.sql`
- Modify: `src/sync/graph/__init__.py`
- Test: `tests/test_sqlite_store.py`

**Interfaces:**
- Consumes: `sync.core.GraphStore`, and the models from Task 1.
- Produces: `sync.graph.SqliteGraphStore(path: str | Path)`, satisfying `GraphStore`. Accepts `":memory:"`.

SQLite has no array or JSONB type, so `args_keys`, `response_fields_read`, and `raw` are stored as JSON text and decoded on read. This is the only behavioural difference from the Postgres store and it must not leak past the store boundary.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sqlite_store.py
import pytest

from sync.core import CallSite, Finding, GraphStore, VendorChange
from sync.graph import SqliteGraphStore


@pytest.fixture
def store() -> SqliteGraphStore:
    s = SqliteGraphStore(":memory:")
    s.apply_schema()
    return s


def _site(**overrides) -> CallSite:
    base = dict(
        repo_id="r1", path="src/billing.ts", line=6, col=2, vendor_id="stripe",
        operation_id="POST /v1/charges", symbol="stripe.charges.create",
        args_keys=["amount", "currency"], response_fields_read=["status"],
        sdk_version="18.0.0", content_hash="abc", file_bytes=2048,
    )
    base.update(overrides)
    return CallSite(**base)


def test_satisfies_the_protocol(store):
    assert isinstance(store, GraphStore)


def test_round_trips_a_call_site_including_its_list_fields(store):
    site_id = store.upsert_call_site(_site())
    got = store.get_call_site(site_id)
    assert got.args_keys == ["amount", "currency"]
    assert got.response_fields_read == ["status"]
    assert got.file_bytes == 2048
    assert got.binding_source == "static"


def test_upsert_is_idempotent_on_the_same_site(store):
    first = store.upsert_call_site(_site())
    second = store.upsert_call_site(_site(line=9))
    assert first == second
    assert store.get_call_site(first).line == 9


def test_queries_call_sites_by_operation(store):
    store.upsert_call_site(_site())
    store.upsert_call_site(_site(path="src/other.ts", operation_id="GET /v1/charges"))
    found = store.call_sites_for_operation("stripe", "POST /v1/charges")
    assert [s.path for s in found] == ["src/billing.ts"]


def test_missing_call_site_raises_key_error(store):
    with pytest.raises(KeyError):
        store.get_call_site("nope")


def test_finds_a_call_site_by_path_and_line(store):
    store.upsert_call_site(_site())
    found = store.call_site_at("src/billing.ts", 6)
    assert found is not None and found.symbol == "stripe.charges.create"


def test_call_site_at_returns_none_for_an_unindexed_line(store):
    store.upsert_call_site(_site())
    assert store.call_site_at("src/billing.ts", 999) is None
    assert store.call_site_at("src/unknown.ts", 6) is None


def test_all_call_sites_returns_every_site_with_its_index_time(store):
    store.upsert_call_site(_site())
    store.upsert_call_site(_site(path="src/other.ts"))
    sites = store.all_call_sites()
    assert {s.path for s in sites} == {"src/billing.ts", "src/other.ts"}
    assert all(s.indexed_at is not None for s in sites)


def test_round_trips_a_vendor_change_with_raw_json(store):
    change_id = store.upsert_vendor_change(VendorChange(
        vendor_id="stripe", from_version="v1", to_version="v2", kind="response-property-removed",
        operation_id="POST /v1/charges", path_ptr="/data/status", severity="breaking",
        source="oasdiff", raw={"note": "removed"},
    ))
    assert store.get_vendor_change(change_id).raw == {"note": "removed"}


def test_open_findings_excludes_resolved_ones(store):
    site_id = store.upsert_call_site(_site())
    finding_id = store.insert_finding(Finding(
        detector="vendor-change", call_site_id=site_id, severity="breaking", rationale="field removed",
    ))
    assert len(store.open_findings()) == 1
    store.set_finding_status(finding_id, "patched")
    assert store.open_findings() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sqlite_store.py -v`
Expected: FAIL — cannot import `SqliteGraphStore`.

- [ ] **Step 3: Write the SQLite schema**

```sql
-- src/sync/graph/schema_sqlite.sql
CREATE TABLE IF NOT EXISTS call_site (
    id                   TEXT PRIMARY KEY,
    repo_id              TEXT NOT NULL,
    path                 TEXT NOT NULL,
    line                 INTEGER NOT NULL,
    col                  INTEGER NOT NULL,
    vendor_id            TEXT NOT NULL,
    operation_id         TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    args_keys            TEXT NOT NULL DEFAULT '[]',
    response_fields_read TEXT NOT NULL DEFAULT '[]',
    sdk_version          TEXT NOT NULL,
    content_hash         TEXT NOT NULL,
    binding_source       TEXT NOT NULL DEFAULT 'static',
    file_bytes           INTEGER NOT NULL DEFAULT 0,
    indexed_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
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
    raw          TEXT NOT NULL DEFAULT '{}',
    detected_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS finding (
    id               TEXT PRIMARY KEY,
    detector         TEXT NOT NULL,
    call_site_id     TEXT NOT NULL REFERENCES call_site (id) ON DELETE CASCADE,
    vendor_change_id TEXT REFERENCES vendor_change (id) ON DELETE SET NULL,
    severity         TEXT NOT NULL,
    rationale        TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'open',
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS finding_status_idx ON finding (status);
```

- [ ] **Step 4: Write the store**

```python
# src/sync/graph/sqlite_store.py
"""A SQLite-backed API Dependency Graph, for local mode.

SQLite has no array or JSON column type, so list and mapping fields are stored as
JSON text and decoded on read. That difference stops at this module's boundary:
callers see the same models the Postgres store returns.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from importlib import resources
from pathlib import Path

from sync.core import CallSite, Finding, FindingStatus, VendorChange

_LIST_COLUMNS = ("args_keys", "response_fields_read")


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


class SqliteGraphStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        # A shared in-memory database would vanish between connections, so keep one
        # connection for the lifetime of the store rather than reconnecting per call.
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def apply_schema(self) -> None:
        ddl = resources.files("sync.graph").joinpath("schema_sqlite.sql").read_text(encoding="utf-8")
        self._conn.executescript(ddl)
        self._conn.commit()

    def upsert_call_site(self, site: CallSite) -> str:
        site_id = _stable_id(site.repo_id, site.path, site.symbol)
        self._conn.execute(
            """
            INSERT INTO call_site (id, repo_id, path, line, col, vendor_id, operation_id, symbol,
                                   args_keys, response_fields_read, sdk_version, content_hash,
                                   binding_source, file_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                line = excluded.line, col = excluded.col, operation_id = excluded.operation_id,
                args_keys = excluded.args_keys, response_fields_read = excluded.response_fields_read,
                sdk_version = excluded.sdk_version, content_hash = excluded.content_hash,
                binding_source = excluded.binding_source, file_bytes = excluded.file_bytes
            """,
            (
                site_id, site.repo_id, site.path, site.line, site.col, site.vendor_id,
                site.operation_id, site.symbol, json.dumps(site.args_keys),
                json.dumps(site.response_fields_read), site.sdk_version, site.content_hash,
                site.binding_source, site.file_bytes,
            ),
        )
        self._conn.commit()
        return site_id

    def upsert_vendor_change(self, change: VendorChange) -> str:
        change_id = _stable_id(
            change.vendor_id, change.from_version, change.to_version, change.kind, change.path_ptr
        )
        self._conn.execute(
            """
            INSERT INTO vendor_change (id, vendor_id, from_version, to_version, kind,
                                       operation_id, path_ptr, severity, source, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET raw = excluded.raw
            """,
            (
                change_id, change.vendor_id, change.from_version, change.to_version, change.kind,
                change.operation_id, change.path_ptr, change.severity, change.source,
                json.dumps(change.raw),
            ),
        )
        self._conn.commit()
        return change_id

    def insert_finding(self, finding: Finding) -> str:
        finding_id = _stable_id(finding.detector, finding.call_site_id, finding.vendor_change_id or "")
        self._conn.execute(
            """
            INSERT INTO finding (id, detector, call_site_id, vendor_change_id, severity, rationale, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                finding_id, finding.detector, finding.call_site_id, finding.vendor_change_id,
                finding.severity, finding.rationale, finding.status,
            ),
        )
        self._conn.commit()
        return finding_id

    def call_sites_for_operation(self, vendor_id: str, operation_id: str) -> list[CallSite]:
        rows = self._conn.execute(
            "SELECT * FROM call_site WHERE vendor_id = ? AND operation_id = ? ORDER BY path, line",
            (vendor_id, operation_id),
        ).fetchall()
        return [CallSite(**_decode_site(row)) for row in rows]

    def get_call_site(self, call_site_id: str) -> CallSite:
        row = self._conn.execute("SELECT * FROM call_site WHERE id = ?", (call_site_id,)).fetchone()
        if row is None:
            raise KeyError(f"no call site {call_site_id}")
        return CallSite(**_decode_site(row))

    def call_site_at(self, path: str, line: int) -> CallSite | None:
        row = self._conn.execute(
            "SELECT * FROM call_site WHERE path = ? AND line = ?", (path, line)
        ).fetchone()
        return None if row is None else CallSite(**_decode_site(row))

    def all_call_sites(self) -> list[CallSite]:
        rows = self._conn.execute("SELECT * FROM call_site ORDER BY path, line").fetchall()
        return [CallSite(**_decode_site(row)) for row in rows]

    def get_vendor_change(self, change_id: str) -> VendorChange:
        row = self._conn.execute("SELECT * FROM vendor_change WHERE id = ?", (change_id,)).fetchone()
        if row is None:
            raise KeyError(f"no vendor change {change_id}")
        return VendorChange(**_decode_change(row))

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        rows = self._conn.execute(
            "SELECT * FROM vendor_change WHERE vendor_id = ? ORDER BY detected_at", (vendor_id,)
        ).fetchall()
        return [VendorChange(**_decode_change(row)) for row in rows]

    def open_findings(self) -> list[Finding]:
        rows = self._conn.execute(
            "SELECT * FROM finding WHERE status = 'open' ORDER BY created_at"
        ).fetchall()
        return [Finding(**dict(row)) for row in rows]

    def set_finding_status(self, finding_id: str, status: FindingStatus) -> None:
        self._conn.execute("UPDATE finding SET status = ? WHERE id = ?", (status, finding_id))
        self._conn.commit()


def _decode_site(row: sqlite3.Row) -> dict:
    data = dict(row)
    for column in _LIST_COLUMNS:
        data[column] = json.loads(data[column])
    return data


def _decode_change(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["raw"] = json.loads(data["raw"])
    return data
```

Export `SqliteGraphStore` from `src/sync/graph/__init__.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_sqlite_store.py -v`
Expected: PASS, 10 tests.

- [ ] **Step 6: Commit**

```bash
git add src/sync/graph/sqlite_store.py src/sync/graph/schema_sqlite.sql src/sync/graph/__init__.py tests/test_sqlite_store.py
git commit -m "feat: add a SQLite graph store for local mode"
```

---

### Task 4: Feed cache

**Files:**
- Create: `src/sync/mcp/__init__.py`
- Create: `src/sync/mcp/feed.py`
- Create: `tests/fixtures/feed/stripe.json`
- Test: `tests/test_feed_cache.py`

**Interfaces:**
- Consumes: `VendorChange` from `sync.core`.
- Produces: `sync.core.feed_keys.PUBLISHER_PUBLIC_KEY`, the embedded verification key; `FeedCache(cache_dir: Path, public_key: Ed25519PublicKey | None = None)` — `None` uses the embedded key — with `load(vendor_id: str) -> FeedSnapshot` and `store(vendor_id: str, payload: bytes, signature: bytes) -> FeedSnapshot`; `FeedSnapshot` with fields `vendor_id: str`, `changes: list[VendorChange]`, `fetched_at: datetime`, `digest: str`.

The feed is published elsewhere and this task only consumes a cached, signed copy — per
`2026-07-26-sync-public-change-feed.md`, a forged entry proposes a patch against real code, so every payload
is verified before it is parsed. Nothing here reaches the network — `store()` takes bytes the caller already
has, alongside the detached signature that came with them.

- [ ] **Step 1: Add the signing dependency**

Run: `uv add cryptography`

- [ ] **Step 2: Generate the publisher keypair**

This key signs the public change feed for as long as Sync exists, so it is generated once, for real, now —
not as a placeholder. The private key is never committed. Run:

```bash
uv run python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

priv_bytes = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
pub_bytes = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)

print('PRIVATE KEY (store this now in a password manager or secrets vault; it will not be shown again):')
print(priv_bytes.hex())
print()
print('PUBLIC KEY (this is committed to source):')
print(pub_bytes.hex())
"
```

Stop and store the printed private key somewhere durable outside this repository before continuing — it signs
every future feed publication and cannot be recovered if lost. Then create:

```python
# src/sync/core/feed_keys.py
"""The public key that verifies the published API change feed.

The matching private key signs the feed at publish time and is held outside this
repository. Losing it means re-keying every consumer's cached trust; rotate only
through a release, never silently.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PUBLISHER_PUBLIC_KEY = Ed25519PublicKey.from_public_bytes(
    bytes.fromhex("REPLACE_WITH_THE_PUBLIC_KEY_HEX_PRINTED_ABOVE")
)
```

Replace the placeholder hex with the real public key printed above — this is the one line in this task that is
filled in from a value only you hold, not invented.

- [ ] **Step 3: Write the failing test**

```python
# tests/test_feed_cache.py
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sync.mcp.feed import FeedCache

FIXTURE = Path(__file__).parent / "fixtures" / "feed" / "stripe.json"
SIGNATURE = Path(__file__).parent / "fixtures" / "feed" / "stripe.json.sig"


@pytest.fixture
def cache(tmp_path: Path) -> FeedCache:
    # Uses the real embedded PUBLISHER_PUBLIC_KEY (no override), verifying against
    # the real signature fixture below — the same path production code takes.
    return FeedCache(tmp_path)


def test_stores_and_reloads_a_feed(cache):
    payload = FIXTURE.read_bytes()
    stored = cache.store("stripe", payload, SIGNATURE.read_bytes())
    reloaded = cache.load("stripe")
    assert [c.path_ptr for c in reloaded.changes] == [c.path_ptr for c in stored.changes]
    assert reloaded.digest == hashlib.sha256(payload).hexdigest()


def test_records_when_the_feed_was_fetched(cache):
    stored = cache.store("stripe", FIXTURE.read_bytes(), SIGNATURE.read_bytes())
    assert stored.fetched_at is not None
    assert cache.load("stripe").fetched_at == stored.fetched_at


def test_missing_feed_raises_key_error(cache):
    with pytest.raises(KeyError):
        cache.load("twilio")


def test_rejects_a_payload_that_is_not_a_change_list(cache):
    # Signed correctly, but the signed content itself is not a change list — the
    # signature check must run before parsing without masking this failure.
    bad_payload = json.dumps({"not": "a list"}).encode("utf-8")
    priv = Ed25519PrivateKey.generate()
    with pytest.raises(ValueError):
        cache.store("stripe", bad_payload, priv.sign(bad_payload), public_key=priv.public_key())


def test_detects_a_corrupted_cache_file(cache, tmp_path):
    cache.store("stripe", FIXTURE.read_bytes(), SIGNATURE.read_bytes())
    (tmp_path / "stripe.json").write_text("{ truncated", encoding="utf-8")
    with pytest.raises(ValueError):
        cache.load("stripe")


def test_rejects_a_tampered_payload_even_with_a_valid_looking_signature(cache):
    tampered = FIXTURE.read_bytes() + b" "
    with pytest.raises(ValueError, match="signature"):
        cache.store("stripe", tampered, SIGNATURE.read_bytes())


def test_rejects_a_payload_signed_by_the_wrong_key(cache):
    payload = FIXTURE.read_bytes()
    wrong_key = Ed25519PrivateKey.generate()
    forged_signature = wrong_key.sign(payload)
    with pytest.raises(ValueError, match="signature"):
        cache.store("stripe", payload, forged_signature)
```

`test_rejects_a_payload_that_is_not_a_change_list` takes an explicit `public_key` override because it needs a
signature that actually verifies over a deliberately invalid payload — the real publisher key's private half
is not available to sign an arbitrary test payload, and should not be.

- [ ] **Step 4: Write the fixture and its real signature**

```json
[
  {
    "vendor_id": "stripe",
    "from_version": "2026-05-01",
    "to_version": "2026-11-01",
    "kind": "response-property-removed",
    "operation_id": "POST /v1/charges",
    "path_ptr": "/data/status",
    "severity": "breaking",
    "source": "oasdiff",
    "raw": {}
  },
  {
    "vendor_id": "stripe",
    "from_version": "2026-05-01",
    "to_version": "2026-11-01",
    "kind": "request-property-added",
    "operation_id": "POST /v1/charges",
    "path_ptr": "/idempotency_key",
    "severity": "addition",
    "source": "oasdiff",
    "raw": {}
  }
]
```

Save that as `tests/fixtures/feed/stripe.json`, then sign it for real with the private key generated in Step 2
— paste the private key hex you stored, use it once here, and do not write it to any file:

```bash
uv run python -c "
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

priv = Ed25519PrivateKey.generate_from_private_bytes(bytes.fromhex('PASTE_YOUR_PRIVATE_KEY_HEX_HERE'))
payload = Path('tests/fixtures/feed/stripe.json').read_bytes()
Path('tests/fixtures/feed/stripe.json.sig').write_bytes(priv.sign(payload))
"
```

The resulting `.sig` file is not a secret — it is a signature over public fixture content — and is committed
alongside the fixture.

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_feed_cache.py -v`
Expected: FAIL — no module `sync.mcp.feed`.

- [ ] **Step 6: Write the implementation**

```python
# src/sync/mcp/feed.py
"""Local cache of the published, signed vendor change feed.

The feed is public data published separately from this server, but it drives code
changes — a forged entry proposes a patch against real code — so every payload is
verified against a detached Ed25519 signature before it is parsed, and digested on
the way in so a corrupted local cache is detected on read.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ValidationError

from sync.core import VendorChange
from sync.core.feed_keys import PUBLISHER_PUBLIC_KEY


class FeedSnapshot(BaseModel):
    vendor_id: str
    changes: list[VendorChange]
    fetched_at: datetime
    digest: str


class FeedCache:
    def __init__(self, cache_dir: Path, public_key: Ed25519PublicKey | None = None) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._public_key = public_key or PUBLISHER_PUBLIC_KEY

    def _payload_path(self, vendor_id: str) -> Path:
        return self._dir / f"{vendor_id}.json"

    def _meta_path(self, vendor_id: str) -> Path:
        return self._dir / f"{vendor_id}.meta.json"

    def store(
        self, vendor_id: str, payload: bytes, signature: bytes, public_key: Ed25519PublicKey | None = None
    ) -> FeedSnapshot:
        # Verify authenticity before anything else touches the payload. Parsing a
        # forged feed first would mean an attacker's JSON shape decides how their
        # own forgery is rejected.
        key = public_key or self._public_key
        try:
            key.verify(signature, payload)
        except InvalidSignature as exc:
            raise ValueError(f"feed signature for {vendor_id} does not verify") from exc

        changes = _parse(payload)
        fetched_at = datetime.now(timezone.utc)
        digest = hashlib.sha256(payload).hexdigest()
        self._payload_path(vendor_id).write_bytes(payload)
        self._meta_path(vendor_id).write_text(
            json.dumps({"fetched_at": fetched_at.isoformat(), "digest": digest}),
            encoding="utf-8",
        )
        return FeedSnapshot(vendor_id=vendor_id, changes=changes, fetched_at=fetched_at, digest=digest)

    def load(self, vendor_id: str) -> FeedSnapshot:
        path = self._payload_path(vendor_id)
        if not path.exists():
            raise KeyError(f"no cached feed for {vendor_id}")
        payload = path.read_bytes()
        # The signature was already verified once, in store(). load() re-reads a
        # cache this process wrote, so it re-checks corruption via the digest
        # rather than re-verifying a signature it did not receive again.
        changes = _parse(payload)
        meta = json.loads(self._meta_path(vendor_id).read_text(encoding="utf-8"))
        if hashlib.sha256(payload).hexdigest() != meta["digest"]:
            raise ValueError(f"cached feed for {vendor_id} does not match its recorded digest")
        return FeedSnapshot(
            vendor_id=vendor_id,
            changes=changes,
            fetched_at=datetime.fromisoformat(meta["fetched_at"]),
            digest=meta["digest"],
        )


def _parse(payload: bytes) -> list[VendorChange]:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"feed is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("feed must be a JSON array of changes")
    try:
        return [VendorChange(**entry) for entry in raw]
    except (ValidationError, TypeError) as exc:
        raise ValueError(f"feed entry does not match VendorChange: {exc}") from exc
```

Create an empty `src/sync/mcp/__init__.py`.

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_feed_cache.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 8: Commit**

```bash
git add src/sync/core/feed_keys.py src/sync/mcp/ tests/test_feed_cache.py tests/fixtures/feed/
git commit -m "feat: cache the vendor change feed, verified against a signature"
```

Do not include the private key printed in Step 2 anywhere in this commit — confirm with `git diff --cached`
before running it.

---

### Task 5: Response envelope and the token-savings estimate

**Files:**
- Create: `src/sync/mcp/envelope.py`
- Test: `tests/test_envelope.py`

**Interfaces:**
- Consumes: nothing beyond Pydantic.
- Produces: `Page(offset: int, limit: int, total: int, has_more: bool)`; `ContextSavings(baseline_tokens: int, response_tokens: int, saved_tokens: int)`; `Envelope(indexed_at, feed_fetched_at, page, context_savings)`; `estimate_tokens(byte_count: int) -> int`; `paginate(items: list, offset: int, limit: int) -> tuple[list, Page]`.

`estimate_tokens` uses four bytes per token. It is an estimate and is named as one; the point is a consistent yardstick applied to both sides of the comparison, not accuracy.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_envelope.py
import pytest

from sync.mcp.envelope import ContextSavings, estimate_tokens, paginate


def test_estimates_four_bytes_per_token():
    assert estimate_tokens(4000) == 1000


def test_estimate_never_returns_negative():
    assert estimate_tokens(-10) == 0


def test_paginate_returns_the_requested_window():
    items, page = paginate(list(range(10)), offset=2, limit=3)
    assert items == [2, 3, 4]
    assert page.offset == 2 and page.limit == 3 and page.total == 10 and page.has_more is True


def test_paginate_marks_the_last_window():
    items, page = paginate(list(range(5)), offset=3, limit=10)
    assert items == [3, 4]
    assert page.has_more is False


def test_paginate_rejects_a_limit_over_the_ceiling():
    with pytest.raises(ValueError):
        paginate([], offset=0, limit=1001)


def test_savings_are_the_difference_between_baseline_and_response():
    savings = ContextSavings.between(baseline_bytes=400_000, response_bytes=4_000)
    assert savings.baseline_tokens == 100_000
    assert savings.response_tokens == 1_000
    assert savings.saved_tokens == 99_000


def test_savings_floor_at_zero_when_the_response_is_larger():
    savings = ContextSavings.between(baseline_bytes=100, response_bytes=4_000)
    assert savings.saved_tokens == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_envelope.py -v`
Expected: FAIL — no module `sync.mcp.envelope`.

- [ ] **Step 3: Write the implementation**

```python
# src/sync/mcp/envelope.py
"""The shape every tool response shares.

Freshness is reported as timestamps rather than durations so a cached response
cannot claim a freshness it has since lost, and every response reports what an
equivalent file-reading exploration would have cost.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

MAX_LIMIT = 1000
_BYTES_PER_TOKEN = 4


def estimate_tokens(byte_count: int) -> int:
    """Approximate tokens for a byte count. A yardstick, not a tokenizer."""
    return max(0, byte_count) // _BYTES_PER_TOKEN


class Page(BaseModel):
    offset: int
    limit: int
    total: int
    has_more: bool


class ContextSavings(BaseModel):
    baseline_tokens: int
    response_tokens: int
    saved_tokens: int

    @classmethod
    def between(cls, baseline_bytes: int, response_bytes: int) -> ContextSavings:
        baseline = estimate_tokens(baseline_bytes)
        response = estimate_tokens(response_bytes)
        return cls(
            baseline_tokens=baseline,
            response_tokens=response,
            saved_tokens=max(0, baseline - response),
        )


class Envelope(BaseModel):
    indexed_at: datetime | None = None
    feed_fetched_at: datetime | None = None
    page: Page | None = None
    context_savings: ContextSavings | None = None


def paginate(items: list, offset: int = 0, limit: int = 50) -> tuple[list, Page]:
    if limit > MAX_LIMIT:
        raise ValueError(f"limit {limit} exceeds the ceiling of {MAX_LIMIT}")
    if offset < 0 or limit < 1:
        raise ValueError("offset must be non-negative and limit at least 1")
    window = items[offset : offset + limit]
    return window, Page(
        offset=offset, limit=limit, total=len(items), has_more=offset + limit < len(items)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_envelope.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add src/sync/mcp/envelope.py tests/test_envelope.py
git commit -m "feat: add the tool response envelope and savings estimate"
```

---

### Task 6: The three tool functions

**Files:**
- Create: `src/sync/mcp/tools.py`
- Test: `tests/test_mcp_tools.py`

**Interfaces:**
- Consumes: `GraphStore` (Task 2), `SqliteGraphStore` (Task 3), `FeedCache`/`FeedSnapshot` (Task 4), `Envelope`/`ContextSavings`/`paginate` (Task 5).
- Produces: `ToolContext(store: GraphStore, feed: FeedCache, indexed_at: datetime | None)`; and three functions, each taking `ToolContext` as their first argument:
  - `whats_at_risk(ctx, path=None, vendor=None, severity=None, offset=0, limit=50) -> WhatsAtRiskResult`
  - `explain_call_site(ctx, file: str, line: int) -> ExplainResult`
  - `whats_changed(ctx, vendor: str, since: str | None = None, offset=0, limit=50) -> WhatsChangedResult`

No function returns file contents. `explain_call_site` on an unindexed location returns `status="not_indexed"` rather than an empty result, because silence reads as "no dependency here".

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mcp_tools.py
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.graph import SqliteGraphStore
from sync.mcp.feed import FeedCache
from sync.mcp.tools import ToolContext, explain_call_site, whats_at_risk, whats_changed

FIXTURE = Path(__file__).parent / "fixtures" / "feed" / "stripe.json"
SIGNATURE = Path(__file__).parent / "fixtures" / "feed" / "stripe.json.sig"


@pytest.fixture
def ctx(tmp_path) -> ToolContext:
    store = SqliteGraphStore(":memory:")
    store.apply_schema()
    site_id = store.upsert_call_site(CallSite(
        repo_id="r1", path="src/billing.ts", line=6, col=2, vendor_id="stripe",
        operation_id="POST /v1/charges", symbol="stripe.charges.create",
        args_keys=["amount"], response_fields_read=["status"], sdk_version="18.0.0",
        content_hash="abc", file_bytes=40_000,
    ))
    change_id = store.upsert_vendor_change(VendorChange(
        vendor_id="stripe", from_version="a", to_version="b", kind="response-property-removed",
        operation_id="POST /v1/charges", path_ptr="/data/status", severity="breaking", source="oasdiff",
    ))
    store.insert_finding(Finding(
        detector="vendor-change", call_site_id=site_id, vendor_change_id=change_id,
        severity="breaking", rationale="reads a removed field",
    ))
    feed = FeedCache(tmp_path)
    feed.store("stripe", FIXTURE.read_bytes(), SIGNATURE.read_bytes())
    return ToolContext(store=store, feed=feed, indexed_at=datetime.now(timezone.utc))


def test_whats_at_risk_reports_the_affected_call_site(ctx):
    result = whats_at_risk(ctx)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.file == "src/billing.ts" and item.line == 6
    assert item.operation == "POST /v1/charges"
    assert item.change_kind == "response-property-removed"
    assert item.binding_source == "static"


def test_whats_at_risk_filters_by_path(ctx):
    assert whats_at_risk(ctx, path="src/other.ts").items == []
    assert len(whats_at_risk(ctx, path="src/billing.ts").items) == 1


def test_whats_at_risk_filters_by_severity(ctx):
    assert whats_at_risk(ctx, severity="addition").items == []


def test_whats_at_risk_reports_savings_against_reading_the_files(ctx):
    result = whats_at_risk(ctx)
    # The one affected file is 40_000 bytes, so the baseline is 10_000 tokens.
    assert result.envelope.context_savings.baseline_tokens == 10_000
    assert result.envelope.context_savings.saved_tokens > 0


def test_whats_at_risk_paginates(ctx):
    result = whats_at_risk(ctx, limit=1)
    assert result.envelope.page.total == 1 and result.envelope.page.has_more is False


def test_explain_call_site_returns_the_binding(ctx):
    result = explain_call_site(ctx, file="src/billing.ts", line=6)
    assert result.status == "indexed"
    assert result.symbol == "stripe.charges.create"
    assert result.operation == "POST /v1/charges"
    assert result.response_fields_read == ["status"]
    assert result.binding_source == "static"


def test_explain_call_site_says_not_indexed_rather_than_returning_nothing(ctx):
    result = explain_call_site(ctx, file="src/unknown.ts", line=1)
    assert result.status == "not_indexed"
    assert result.symbol is None
    assert result.envelope.indexed_at is not None


def test_explain_call_site_answers_for_a_site_with_no_finding(ctx):
    """A healthy call site is indexed, not invisible. Reaching sites through findings
    would report `not_indexed` for every dependency that happens to be working."""
    ctx.store.upsert_call_site(CallSite(
        repo_id="r1", path="src/healthy.ts", line=12, col=4, vendor_id="stripe",
        operation_id="GET /v1/customers", symbol="stripe.customers.list",
        sdk_version="18.0.0", content_hash="def", file_bytes=1_000,
    ))
    result = explain_call_site(ctx, file="src/healthy.ts", line=12)
    assert result.status == "indexed"
    assert result.symbol == "stripe.customers.list"
    assert result.known_changes == []


def test_no_tool_returns_source_text(ctx):
    payload = whats_at_risk(ctx).model_dump_json() + explain_call_site(
        ctx, file="src/billing.ts", line=6
    ).model_dump_json()
    assert "stripe.charges.create({" not in payload
    assert "import " not in payload


def test_whats_changed_reads_the_feed(ctx):
    result = whats_changed(ctx, vendor="stripe")
    assert {c.change_kind for c in result.items} == {
        "response-property-removed", "request-property-added",
    }
    assert result.envelope.feed_fetched_at is not None


def test_whats_changed_on_an_uncached_vendor_returns_empty_not_an_error(ctx):
    result = whats_changed(ctx, vendor="twilio")
    assert result.items == []
    assert result.envelope.feed_fetched_at is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: FAIL — no module `sync.mcp.tools`.

- [ ] **Step 3: Write the implementation**

```python
# src/sync/mcp/tools.py
"""The question-shaped tools, as plain functions.

Nothing here imports the MCP SDK. The tools are ordinary functions over the graph,
which is what lets them be tested without a protocol server, and what keeps the
SDK binding replaceable.

No tool returns source text. The binding is the answer; returning the file would
hand back exactly the tokens this surface exists to save.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from sync.core import BindingSource, GraphStore, Severity
from sync.mcp.envelope import ContextSavings, Envelope, paginate
from sync.mcp.feed import FeedCache


@dataclass
class ToolContext:
    store: GraphStore
    feed: FeedCache
    indexed_at: datetime | None = None


class RiskItem(BaseModel):
    file: str
    line: int
    symbol: str
    operation: str
    vendor: str
    change_kind: str
    severity: Severity
    binding_source: BindingSource
    finding_id: str


class WhatsAtRiskResult(BaseModel):
    items: list[RiskItem]
    envelope: Envelope


class ExplainResult(BaseModel):
    status: Literal["indexed", "not_indexed"]
    file: str
    line: int
    symbol: str | None = None
    operation: str | None = None
    vendor: str | None = None
    args_keys: list[str] = []
    response_fields_read: list[str] = []
    sdk_version: str | None = None
    binding_source: BindingSource | None = None
    known_changes: list[str] = []
    envelope: Envelope


class ChangeItem(BaseModel):
    operation: str
    change_kind: str
    path_ptr: str
    severity: Severity
    from_version: str
    to_version: str


class WhatsChangedResult(BaseModel):
    items: list[ChangeItem]
    envelope: Envelope


def whats_at_risk(
    ctx: ToolContext,
    path: str | None = None,
    vendor: str | None = None,
    severity: Severity | None = None,
    offset: int = 0,
    limit: int = 50,
) -> WhatsAtRiskResult:
    items: list[RiskItem] = []
    baseline_bytes = 0
    # One lookup per finding rather than a join. Findings are bounded by what a vendor
    # actually changed, so this stays small; revisit if a single release ever produces
    # enough findings for the round trips to show up in the response budget.
    for finding in ctx.store.open_findings():
        site = ctx.store.get_call_site(finding.call_site_id)
        if path is not None and site.path != path:
            continue
        if vendor is not None and site.vendor_id != vendor:
            continue
        if severity is not None and finding.severity != severity:
            continue
        change_kind = ""
        if finding.vendor_change_id is not None:
            change_kind = ctx.store.get_vendor_change(finding.vendor_change_id).kind
        baseline_bytes += site.file_bytes
        items.append(RiskItem(
            file=site.path, line=site.line, symbol=site.symbol, operation=site.operation_id,
            vendor=site.vendor_id, change_kind=change_kind, severity=finding.severity,
            binding_source=site.binding_source, finding_id=finding.id or "",
        ))

    window, page = paginate(items, offset=offset, limit=limit)
    result = WhatsAtRiskResult(items=window, envelope=Envelope(indexed_at=ctx.indexed_at, page=page))
    result.envelope.context_savings = ContextSavings.between(
        baseline_bytes=baseline_bytes, response_bytes=len(result.model_dump_json().encode("utf-8"))
    )
    return result


def explain_call_site(ctx: ToolContext, file: str, line: int) -> ExplainResult:
    envelope = Envelope(indexed_at=ctx.indexed_at)
    # Look the site up directly. Reaching it through findings would make a healthy,
    # fully indexed call site indistinguishable from an unindexed one.
    site = ctx.store.call_site_at(file, line)
    if site is None:
        # Never an empty success. An agent reads silence as "no vendor dependency here".
        return ExplainResult(status="not_indexed", file=file, line=line, envelope=envelope)

    known = [
        ctx.store.get_vendor_change(f.vendor_change_id).kind
        for f in ctx.store.open_findings()
        if f.call_site_id == site.id and f.vendor_change_id is not None
    ]
    result = ExplainResult(
        status="indexed", file=file, line=line, symbol=site.symbol,
        operation=site.operation_id, vendor=site.vendor_id, args_keys=site.args_keys,
        response_fields_read=site.response_fields_read, sdk_version=site.sdk_version,
        binding_source=site.binding_source, known_changes=known, envelope=envelope,
    )
    result.envelope.context_savings = ContextSavings.between(
        baseline_bytes=site.file_bytes,
        response_bytes=len(result.model_dump_json().encode("utf-8")),
    )
    return result


def whats_changed(
    ctx: ToolContext, vendor: str, since: str | None = None, offset: int = 0, limit: int = 50
) -> WhatsChangedResult:
    try:
        snapshot = ctx.feed.load(vendor)
    except KeyError:
        return WhatsChangedResult(items=[], envelope=Envelope(indexed_at=ctx.indexed_at))

    changes = snapshot.changes
    if since is not None:
        changes = [c for c in changes if c.to_version >= since]
    items = [
        ChangeItem(
            operation=c.operation_id, change_kind=c.kind, path_ptr=c.path_ptr,
            severity=c.severity, from_version=c.from_version, to_version=c.to_version,
        )
        for c in changes
    ]
    window, page = paginate(items, offset=offset, limit=limit)
    result = WhatsChangedResult(
        items=window,
        envelope=Envelope(indexed_at=ctx.indexed_at, feed_fetched_at=snapshot.fetched_at, page=page),
    )
    result.envelope.context_savings = ContextSavings.between(
        baseline_bytes=0, response_bytes=len(result.model_dump_json().encode("utf-8"))
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_tools.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/sync/mcp/tools.py tests/test_mcp_tools.py
git commit -m "feat: answer the three binding questions without returning source"
```

---

### Task 7: Tool registry with a frozen schema

**Files:**
- Create: `src/sync/mcp/registry.py`
- Create: `tests/golden/tool_schemas.json`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Consumes: the three functions from Task 6.
- Produces: `TOOLS: list[ToolSpec]`, where `ToolSpec` has `name: str`, `description: str`, `input_schema: dict`, `handler: Callable`; and `dispatch(ctx: ToolContext, name: str, arguments: dict) -> BaseModel`.

The golden file is the executable form of the stability rule. A product that catches vendor breaking changes cannot ship one of its own.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tool_registry.py
import json
from pathlib import Path

import pytest

from sync.mcp.registry import TOOLS, dispatch, schemas_as_data

GOLDEN = Path(__file__).parent / "golden" / "tool_schemas.json"


def test_exposes_exactly_the_three_read_tools():
    assert {t.name for t in TOOLS} == {
        "sync_whats_at_risk", "sync_explain_call_site", "sync_whats_changed",
    }


def test_tool_schemas_match_the_golden_file():
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert schemas_as_data() == expected, (
        "Tool schemas changed. Adding an optional parameter or a new tool is allowed — "
        "update the golden file. Removing or renaming a parameter is a breaking change "
        "and is not allowed."
    )


def test_every_tool_has_a_description_and_an_object_schema():
    for tool in TOOLS:
        assert tool.description.strip()
        assert tool.input_schema["type"] == "object"


def test_dispatch_routes_to_the_named_tool(monkeypatch):
    seen = {}

    def fake(ctx, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(TOOLS[0], "handler", fake)
    assert dispatch(ctx=None, name=TOOLS[0].name, arguments={"limit": 5}) == "ok"
    assert seen == {"limit": 5}


def test_dispatch_rejects_an_unknown_tool():
    with pytest.raises(KeyError):
        dispatch(ctx=None, name="sync_delete_everything", arguments={})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tool_registry.py -v`
Expected: FAIL — no module `sync.mcp.registry`.

- [ ] **Step 3: Write the implementation**

```python
# src/sync/mcp/registry.py
"""Tool schemas, owned as data.

The schemas are declared here rather than generated from signatures, because they
are a published interface: they are frozen on first release and may only grow.
`tests/golden/tool_schemas.json` fails the build on any removal or rename.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sync.mcp.tools import ToolContext, explain_call_site, whats_at_risk, whats_changed

_SEVERITIES = ["breaking", "deprecation", "addition", "info"]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="sync_whats_at_risk",
        description=(
            "List call sites in this repository affected by a known third-party API change. "
            "Returns bindings and locations, never source code."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Restrict to one file path."},
                "vendor": {"type": "string", "description": "Restrict to one vendor, such as 'stripe'."},
                "severity": {"type": "string", "enum": _SEVERITIES},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50},
            },
            "required": [],
        },
        handler=whats_at_risk,
    ),
    ToolSpec(
        name="sync_explain_call_site",
        description=(
            "Explain what third-party operation a specific line depends on: the symbol, the vendor "
            "operation, the arguments passed, the response fields read, and how the binding was established."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Repository-relative path."},
                "line": {"type": "integer", "minimum": 1},
            },
            "required": ["file", "line"],
        },
        handler=explain_call_site,
    ),
    ToolSpec(
        name="sync_whats_changed",
        description="List published changes for a vendor's API, newest version boundary first.",
        input_schema={
            "type": "object",
            "properties": {
                "vendor": {"type": "string"},
                "since": {"type": "string", "description": "Only changes at or after this version."},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 50},
            },
            "required": ["vendor"],
        },
        handler=whats_changed,
    ),
]


def schemas_as_data() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in TOOLS
    ]


def dispatch(ctx: ToolContext | None, name: str, arguments: dict[str, Any]):
    for tool in TOOLS:
        if tool.name == name:
            return tool.handler(ctx, **arguments)
    raise KeyError(f"unknown tool {name}")
```

- [ ] **Step 4: Generate the golden file**

Run:

```bash
uv run python -c "import json,pathlib;from sync.mcp.registry import schemas_as_data;pathlib.Path('tests/golden').mkdir(parents=True,exist_ok=True);pathlib.Path('tests/golden/tool_schemas.json').write_text(json.dumps(schemas_as_data(),indent=2),encoding='utf-8')"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_tool_registry.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 6: Prove the golden test can actually fail**

Temporarily delete the `"vendor"` property from `sync_whats_at_risk`'s schema, run `uv run pytest tests/test_tool_registry.py -v`, and confirm the golden test FAILS. Restore it and confirm the suite passes again. A test that has never failed has never been shown to test anything.

- [ ] **Step 7: Commit**

```bash
git add src/sync/mcp/registry.py tests/test_tool_registry.py tests/golden/
git commit -m "feat: freeze the tool schemas behind a golden file"
```

---

### Task 8: Bind the registry to the MCP SDK

**Files:**
- Create: `src/sync/mcp/server.py`
- Modify: `pyproject.toml`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `TOOLS`, `dispatch`, `schemas_as_data` (Task 7); `ToolContext` (Task 6); `SqliteGraphStore` (Task 3); `FeedCache` (Task 4).
- Produces: `build_context(db_path: Path, feed_dir: Path) -> ToolContext`; `main() -> None`, the stdio entry point.

This is the only module that imports the SDK. Its job is translation and nothing else, so that a change in the SDK cannot reach the tools.

- [ ] **Step 1: Add the dependency**

Run: `uv add mcp`

- [ ] **Step 2: Read the installed SDK's stdio server example**

Run: `uv run python -c "import mcp, pathlib; print(pathlib.Path(mcp.__file__).parent)"`

Open that directory and read the server package's own example or docstrings to confirm the exact names for registering a tool lister, a tool caller, and running over stdio. Use what the installed version documents — do not guess from memory.

- [ ] **Step 3: Write the failing test**

```python
# tests/test_mcp_server.py
from pathlib import Path

from sync.mcp.registry import schemas_as_data
from sync.mcp.server import build_context, tool_definitions


def test_tool_definitions_mirror_the_registry():
    assert [t["name"] for t in tool_definitions()] == [s["name"] for s in schemas_as_data()]


def test_tool_definitions_carry_an_input_schema():
    for definition in tool_definitions():
        assert definition["inputSchema"]["type"] == "object"


def test_build_context_creates_the_database(tmp_path: Path):
    ctx = build_context(db_path=tmp_path / "graph.db", feed_dir=tmp_path / "feed")
    assert (tmp_path / "graph.db").exists()
    assert ctx.store.open_findings() == []


def test_build_context_reports_no_index_time_for_a_fresh_database(tmp_path: Path):
    ctx = build_context(db_path=tmp_path / "graph.db", feed_dir=tmp_path / "feed")
    assert ctx.indexed_at is None


def test_build_context_reports_index_time_when_the_repo_has_no_findings(tmp_path: Path):
    """An indexed repository with nothing wrong is still an indexed repository. Deriving
    freshness from findings would report it as never indexed."""
    from sync.core import CallSite

    db_path = tmp_path / "graph.db"
    seed = build_context(db_path=db_path, feed_dir=tmp_path / "feed")
    seed.store.upsert_call_site(CallSite(
        repo_id="r1", path="src/billing.ts", line=6, col=2, vendor_id="stripe",
        operation_id="POST /v1/charges", symbol="stripe.charges.create",
        sdk_version="18.0.0", content_hash="abc",
    ))

    ctx = build_context(db_path=db_path, feed_dir=tmp_path / "feed")
    assert ctx.store.open_findings() == []
    assert ctx.indexed_at is not None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: FAIL — no module `sync.mcp.server`.

- [ ] **Step 5: Write the implementation**

```python
# src/sync/mcp/server.py
"""The MCP SDK binding.

The only module in this package that imports the SDK. Tool behaviour lives in
`tools.py` and tool schemas in `registry.py`, both SDK-free, so a change in the
protocol library reaches this file and stops.
"""

from __future__ import annotations

import json
from pathlib import Path

from sync.graph import SqliteGraphStore
from sync.mcp.feed import FeedCache
from sync.mcp.registry import TOOLS, dispatch
from sync.mcp.tools import ToolContext

DEFAULT_DB = Path.home() / ".cache" / "sync" / "graph.db"
DEFAULT_FEED = Path.home() / ".cache" / "sync" / "feed"


def tool_definitions() -> list[dict]:
    """The registry in the SDK's spelling: `inputSchema`, not `input_schema`."""
    return [
        {"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in TOOLS
    ]


def build_context(db_path: Path = DEFAULT_DB, feed_dir: Path = DEFAULT_FEED) -> ToolContext:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = SqliteGraphStore(db_path)
    store.apply_schema()
    # Freshness comes from the call sites themselves. Deriving it from findings would
    # report a healthy indexed repository as never indexed, which is the one lie this
    # field must not tell.
    sites = store.all_call_sites()
    indexed_at = max((s.indexed_at for s in sites), default=None)
    return ToolContext(store=store, feed=FeedCache(Path(feed_dir)), indexed_at=indexed_at)


def call_tool(ctx: ToolContext, name: str, arguments: dict) -> str:
    """Run a tool and render its result as JSON text for the protocol layer."""
    result = dispatch(ctx, name, arguments)
    return result.model_dump_json()


def main() -> None:
    ctx = build_context()
    _serve_stdio(ctx)


def _serve_stdio(ctx: ToolContext) -> None:
    """Wire `tool_definitions()` and `call_tool()` to the installed SDK's stdio server.

    Follow the pattern documented by the installed `mcp` package, read in Step 2:
    register a handler that returns `tool_definitions()` for tool listing, and one
    that returns `call_tool(ctx, name, arguments)` for tool invocation, then run the
    server over stdio.
    """
    raise NotImplementedError("wire to the installed mcp SDK, per Step 2")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: PASS, 5 tests. `_serve_stdio` is deliberately untested — it is SDK wiring with no logic.

- [ ] **Step 7: Replace `_serve_stdio` with the real wiring**

Using what Step 2 showed, implement `_serve_stdio` against the installed SDK. Keep it to registration and transport: no filtering, no formatting, no business logic.

- [ ] **Step 8: Add the entry point**

In `pyproject.toml`, under `[project.scripts]`:

```toml
sync-mcp = "sync.mcp.server:main"
```

- [ ] **Step 9: Verify it runs as a real MCP server**

Run: `uv run sync-mcp`

Confirm it starts and waits on stdin rather than exiting. Then add it to a local agent's MCP configuration and confirm the three tools appear in its tool list. Stop the process.

- [ ] **Step 10: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/sync/mcp/server.py pyproject.toml tests/test_mcp_server.py
git commit -m "feat: serve the graph over MCP on stdio"
```

---

## What this plan does not cover

- **`sync_propose_patch`.** It depends on the remediation graph, whose interface was still moving when this plan was written. It gets its own plan once M0 has merged and that interface has settled.
- **The two-phase indexer** that upgrades `binding_source` from `static` to `resolved`. Task 1 adds the field and every consumer honours it; producing `resolved` is the TypeScript compiler pass, which is separate work.
- **The feed's publication** — schema, hosting, and data licence, now specified in `2026-07-26-sync-public-change-feed.md`. Task 4 consumes and verifies a cached, signed feed; it does not fetch one over the network or publish one. The signing keypair Task 4 generates is the real one described in that spec — not a throwaway — and its private half must exist somewhere durable before any feed is ever published.
- **Telemetry correlation** producing `observed`. Hosted tier, later milestone.

## Verification

After Task 8, the free local tier works end to end:

1. `docker compose up -d` is **not** required. Local mode uses SQLite only.
2. `uv run pytest -v` passes, including the import-boundary test.
3. `uv run sync-mcp` starts and serves three tools to a real agent.
4. Against a repository indexed into `~/.cache/sync/graph.db`, asking an agent "what in this repo is affected by a Stripe change" returns file, line, operation, and change kind — with `context_savings` showing what reading those files would have cost, and without a single line of source entering the agent's context.

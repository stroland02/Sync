# Per-Repository Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the patch agent durable, per-repository facts through the prompt's cacheable prefix, writable by an operator and seedable from a file the customer commits.

**Architecture:** A `repo_context` table in the graph store holds one row per repository. `sync.context` — a new package that touches no database — reads an optional `.sync/context.md` from a checkout and renders the prompt section. `build_patch_prompt` gains a defaulted parameter, so a repository with no context produces a byte-identical prompt to today's. The MCP server gains an `instructions` field and a resource template, neither of which is a tool.

**Tech Stack:** Python 3.12, `uv`, psycopg 3, Pydantic 2, Starlette, pytest with xdist.

**Design:** `docs/superpowers/specs/2026-08-06-sync-repo-context-design.md`

## Global Constraints

- **Read `CLAUDE.md` first.** It is binding and this plan layers on top of it.
- Python interpreter is `python`. **Never `python3`** — a Microsoft Store shim on this machine.
- Packages via `uv` only: `uv add`, `uv run`. Poetry is not installed.
- Postgres 16 in Docker on **port 5433**. `docker compose up -d`.
- **Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, and `subprocess.run(..., text=True)`. Every fixture here is ASCII, so no test catches the omission by accident.
- **`sync.core` imports nothing from any sibling package.** `tests/test_import_boundary.py` enforces it.
- **`sync.mcp.tools` is frozen.** No task adds, renames, or removes a tool. `tests/golden/tool_schemas.json` must never be regenerated.
- **Nothing writes to the customer's checkout.** Not in any task.
- Declare a table's grain as a comment in `schema.sql` before adding a column or a table.
- Every stage is idempotent: natural key plus an explicit conflict clause.
- Git warns `LF will be replaced by CRLF`. Expected. Do not add `.gitattributes`.
- The body cap is **8000 characters**, counted on the decoded string.
- Run the suite with `uv run pytest`. Default `addopts` is `-m 'not e2e' -n auto`.

## File Structure

| File | Responsibility |
|---|---|
| `src/sync/core/models.py` | `RepoContext` — the type. Modified. |
| `src/sync/graph/schema.sql` | `repo_context` DDL with its grain comment. Modified. |
| `src/sync/graph/store.py` | `upsert_repo_context`, `repo_context`. Modified. |
| `src/sync/context/__init__.py` | Package exports. Created. |
| `src/sync/context/seed.py` | `read_seed` — the `.sync/context.md` reader. Created. |
| `src/sync/context/prompt.py` | `render_section` — context to prompt text. Created. |
| `src/sync/remediate/agent_patch.py` | `build_patch_prompt` gains `repo_context`. Modified. |
| `src/sync/cli.py` | Seeding in `run`; `context` subcommand. Modified. |
| `src/sync/dashboard/graph_views.py` | `repo_context` view. Modified. |
| `src/sync/api/app.py` | `GET`/`POST /api/repos/{repo_id}/context`. Modified. |
| `src/sync/mcp/resources.py` | Context URI template and read. Modified. |
| `src/sync/mcp/server.py` | `instructions` on initialize; wire the context reader. Modified. |
| `pyproject.toml` | `sync.context` in `forbidden_modules`. Modified. |

Seven tasks. Task 1 is the foundation every later task consumes; tasks 5, 6 and 7 are independent of each other.

---

### Task 1: The table, the model, and the two store methods

**Files:**
- Modify: `src/sync/core/models.py`
- Modify: `src/sync/graph/schema.sql`
- Modify: `src/sync/graph/store.py`
- Test: `tests/test_repo_context_store.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `sync.core.models.RepoContext` with fields `repo_id: str`, `body: str`, `source: str`, `updated_at: datetime | None = None`
  - `sync.core.models.CONTEXT_BODY_MAX = 8000`
  - `sync.core.models.CONTEXT_SOURCES: frozenset[str]` = `{"seeded-file", "operator"}`
  - `GraphStore.upsert_repo_context(context: RepoContext) -> None`
  - `GraphStore.repo_context(repo_id: str) -> RepoContext | None`

**Note:** `truncate_all` derives its table list from `schema.sql`, so it needs no edit. `apply_schema` issues `ADD COLUMN IF NOT EXISTS` for every declared column, so a database that already exists gains this table on the next run.

- [ ] **Step 1: Write the failing test**

Create `tests/test_repo_context_store.py`:

```python
import os
from datetime import datetime, timezone

import pytest

from sync.core.models import CONTEXT_SOURCES, RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_repository_with_no_context_reads_as_none(store):
    assert store.repo_context("github.com/acme/storefront") is None


def test_an_upserted_context_reads_back(store):
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="Package manager is pnpm.",
            source="operator",
        )
    )
    found = store.repo_context("github.com/acme/storefront")
    assert found is not None
    assert found.body == "Package manager is pnpm."
    assert found.source == "operator"
    assert found.updated_at is not None


def test_a_second_upsert_replaces_rather_than_duplicating(store):
    for body, source in (("first", "operator"), ("second", "seeded-file")):
        store.upsert_repo_context(
            RepoContext(repo_id="github.com/acme/storefront", body=body, source=source)
        )
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "second"
    assert found.source == "seeded-file"
    rows = store._connect().execute(
        "SELECT count(*) AS n FROM repo_context WHERE repo_id = %s",
        ["github.com/acme/storefront"],
    ).fetchone()
    assert rows["n"] == 1


def test_context_is_scoped_to_one_repository(store):
    store.upsert_repo_context(
        RepoContext(repo_id="github.com/acme/one", body="one", source="operator")
    )
    store.upsert_repo_context(
        RepoContext(repo_id="github.com/acme/two", body="two", source="operator")
    )
    assert store.repo_context("github.com/acme/one").body == "one"
    assert store.repo_context("github.com/acme/two").body == "two"


def test_the_declared_sources_are_the_two_this_ships_with():
    """A third source added without a decision is the failure this guards.

    `sync.graph.sources` keeps membership positive for the same reason: a mechanism added and
    left unclassified must be loud rather than silently inside a baseline. Adding `agent` here
    is a deliberate edit that fails this test first.
    """
    assert CONTEXT_SOURCES == frozenset({"seeded-file", "operator"})
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /c/Users/strol/orca/workspaces/Sync/repo-context
docker compose up -d
uv run pytest tests/test_repo_context_store.py -v
```

Expected: FAIL — `ImportError: cannot import name 'CONTEXT_SOURCES' from 'sync.core.models'`.

- [ ] **Step 3: Add the model**

In `src/sync/core/models.py`, after the `ObservedShape` class:

```python
CONTEXT_BODY_MAX = 8000
"""Longest context body accepted, counted on the decoded string rather than on bytes.

Counting characters rather than bytes so a body of accented prose is not silently shorter than
an ASCII one. Over the cap is refused everywhere and truncated nowhere: prose cut mid-sentence
and handed to an agent that edits code reads as a complete statement and is not one.
"""

CONTEXT_SOURCES: frozenset[str] = frozenset({"seeded-file", "operator"})
"""Which mechanisms may produce a context body.

`seeded-file` is the customer's own committed `.sync/context.md`. `operator` is a human through
the console or the CLI. Membership is positive, as in `sync.graph.sources`: a mechanism added to
the system and not added here is absent from the prompt rather than quietly inside it. An agent
writing its own context is memory rather than context and is deliberately not a member.
"""


class RepoContext(BaseModel):
    """What stays true of a customer's repository while the code changes underneath it.

    The grain is one row per repository -- not per run and not per revision. A row per revision
    would make the prompt's context a function of when the last index ran rather than of what
    the repository is.

    `source` attributes the body without claiming a rung. A rung describes how a binding between
    code and a vendor operation was established; context establishes no binding, and putting
    prose on a scale built for evidence would make `CLAUDE.md`'s attribution rule mean less
    everywhere it is enforced.
    """

    repo_id: str
    body: str
    source: str
    updated_at: datetime | None = None
```

Export it from `src/sync/core/__init__.py` alongside the existing model exports, following whatever form that file already uses.

- [ ] **Step 4: Add the table**

Append to `src/sync/graph/schema.sql`:

```sql
-- Grain: one row per repository. Not per run, and not per revision -- context is what stays
-- true of a checkout while the code changes underneath it, and a row per revision would make
-- the prompt's context a function of when the last index ran rather than of what the
-- repository is.
--
-- `source` names the mechanism that produced the body, as `observed_shape.source` does and for
-- the same reason: a patch traceable to bad context must be traceable to *which* bad context.
-- `seeded-file` is the customer's own committed `.sync/context.md`. `operator` is a human
-- through the console or the CLI. Membership is positive -- a source added and left
-- unclassified is absent from the prompt rather than silently inside it.
--
-- Sync never writes `.sync/context.md` back. A `seeded-file` row is a copy, the file is the
-- original, and every index re-seeds. An operator edit to a seeded row is therefore overwritten
-- on the next index. That precedence is deliberate: when Sync and the customer disagree about
-- what is true of the customer's repository, the customer wins.
--
-- No foreign key to `call_site`. Context may precede an index, and a repository Sync has never
-- indexed is one an operator may still describe.
CREATE TABLE IF NOT EXISTS repo_context (
    repo_id     TEXT PRIMARY KEY,
    body        TEXT NOT NULL,
    source      TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 5: Add the store methods**

In `src/sync/graph/store.py`, import `RepoContext` alongside the other models, then add both methods to `GraphStore`:

```python
    def upsert_repo_context(self, context: RepoContext) -> None:
        """Write one repository's context, replacing whatever it held.

        Last write wins, and there is no counter to lose. The natural key is `repo_id` and the
        table holds one row per repository, so re-running a seed converges on the row it already
        has -- which is what `2026-07-27-sync-pipeline-discipline.md` asks of every stage.

        `updated_at` is taken from the database rather than from the caller. Two writers on two
        machines disagreeing about the clock would otherwise make "which of these is later" a
        question about their clocks instead of about the writes.
        """
        self._connect().execute(
            """
            INSERT INTO repo_context (repo_id, body, source)
            VALUES (%s, %s, %s)
            ON CONFLICT (repo_id) DO UPDATE SET
                body = EXCLUDED.body,
                source = EXCLUDED.source,
                updated_at = now()
            """,
            [context.repo_id, context.body, context.source],
        )

    def repo_context(self, repo_id: str) -> RepoContext | None:
        """One repository's context, or None when it has none.

        None rather than an empty `RepoContext`, because absence and emptiness must not reach a
        prompt as two states. A caller that renders a section for an empty body would put an
        empty heading in front of an agent, which reads as a statement that there is nothing
        worth knowing rather than as nothing at all.
        """
        row = self._connect().execute(
            "SELECT * FROM repo_context WHERE repo_id = %s",
            [repo_id],
        ).fetchone()
        return RepoContext(**row) if row is not None else None
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
uv run pytest tests/test_repo_context_store.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Run the schema and boundary suites**

```bash
uv run pytest tests/test_schema_convergence.py tests/test_import_boundary.py tests/test_graph_store.py -v
```

Expected: all pass. `test_schema_convergence` proves an aged database gains `repo_context`.

- [ ] **Step 8: Commit**

```bash
git add src/sync/core/models.py src/sync/core/__init__.py src/sync/graph/schema.sql src/sync/graph/store.py tests/test_repo_context_store.py
git commit -m "feat: a repository may carry context, and the store holds one row of it"
```

---

### Task 2: `sync.context` — the seed reader and the prompt section

**Files:**
- Create: `src/sync/context/__init__.py`
- Create: `src/sync/context/seed.py`
- Create: `src/sync/context/prompt.py`
- Modify: `pyproject.toml` (import-linter contract)
- Test: `tests/test_context_package.py` (create)

**Interfaces:**
- Consumes: `sync.core.models.CONTEXT_BODY_MAX` from Task 1.
- Produces:
  - `sync.context.SEED_RELATIVE_PATH = Path(".sync") / "context.md"`
  - `sync.context.read_seed(local_path: str | Path) -> str | None`
  - `sync.context.render_section(body: str) -> str`

This package touches no database. Every write goes through `GraphStore`, and the caller holds both — that split is what keeps `sync.context` free of Postgres and keeps the import-linter contract meaningful.

- [ ] **Step 1: Write the failing test**

Create `tests/test_context_package.py`:

```python
from pathlib import Path

from sync.context import SEED_RELATIVE_PATH, read_seed, render_section


def _seed(root: Path, contents: bytes) -> None:
    target = root / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)


def test_no_file_is_none(tmp_path):
    assert read_seed(tmp_path) is None


def test_a_file_is_its_stripped_contents(tmp_path):
    _seed(tmp_path, b"\n  Package manager is pnpm.\n\n")
    assert read_seed(tmp_path) == "Package manager is pnpm."


def test_an_empty_file_is_none(tmp_path):
    _seed(tmp_path, b"")
    assert read_seed(tmp_path) is None


def test_a_whitespace_only_file_is_none(tmp_path):
    """Absence and emptiness must not reach a prompt as two states."""
    _seed(tmp_path, b"   \n\t\n  ")
    assert read_seed(tmp_path) is None


def test_a_file_over_the_cap_is_none_rather_than_truncated(tmp_path):
    _seed(tmp_path, b"x" * 8001)
    assert read_seed(tmp_path) is None


def test_a_file_exactly_at_the_cap_is_read(tmp_path):
    _seed(tmp_path, b"x" * 8000)
    assert read_seed(tmp_path) == "x" * 8000


def test_the_cap_counts_characters_rather_than_bytes(tmp_path):
    """8000 accented characters is 16000 bytes in UTF-8 and is still under the cap.

    Counting bytes would make a body of French or Polish prose silently half the length of an
    English one, which is a limit nobody was told about.
    """
    _seed(tmp_path, ("é" * 8000).encode("utf-8"))
    assert read_seed(tmp_path) == "é" * 8000


def test_bytes_that_are_not_utf_8_are_none_rather_than_raising(tmp_path):
    """A customer's optional file being malformed must never abandon a run.

    0xFF is not a valid UTF-8 start byte. Under the locale codepage on Windows it decodes to
    'ÿ' instead of raising, which is exactly why `encoding="utf-8"` is passed explicitly and
    why this test uses real bytes rather than an ASCII fixture.
    """
    _seed(tmp_path, b"valid text \xff more text")
    assert read_seed(tmp_path) is None


def test_a_directory_where_the_file_should_be_is_none(tmp_path):
    (tmp_path / SEED_RELATIVE_PATH).mkdir(parents=True)
    assert read_seed(tmp_path) is None


def test_a_rendered_section_names_the_repository_and_carries_the_body():
    rendered = render_section("Package manager is pnpm.")
    assert "What is true of this repository:" in rendered
    assert "Package manager is pnpm." in rendered


def test_an_empty_body_renders_nothing_at_all(tmp_path):
    """Not an empty heading -- nothing.

    A prompt built for a repository with no context must be byte-identical to the prompt built
    before this feature existed, which is what makes the change provably additive.
    """
    assert render_section("") == ""
    assert render_section("   \n  ") == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_context_package.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'sync.context'`.

- [ ] **Step 3: Write the seed reader**

Create `src/sync/context/seed.py`:

```python
"""Reading the optional context file a customer may commit to their own repository.

`.sync/context.md` is the customer's, not Sync's. It is read and never written: a `seeded-file`
row in the graph is a copy and this file is the original, which is what makes re-indexing a
refresh rather than a conflict.

Every failure here returns None. A malformed optional file must not abandon a remediation run --
context improves a run and is not a precondition for one, and a feature whose broken input
stopped repairs would be riskier to adopt than to ignore.
"""

from __future__ import annotations

from pathlib import Path

from sync.core.models import CONTEXT_BODY_MAX

SEED_RELATIVE_PATH = Path(".sync") / "context.md"


def read_seed(local_path: str | Path) -> str | None:
    """The checkout's context file as text, or None when there is nothing usable to read.

    None covers absent, empty, whitespace-only, unreadable, not valid UTF-8, and over the cap.
    A caller cannot distinguish them and does not need to: every one of them means this
    repository supplied no context, and the log is where the difference belongs.

    Over the cap returns None rather than a truncation. Prose cut mid-sentence and handed to an
    agent that edits code reads as a complete statement and is not one.
    """
    target = Path(local_path) / SEED_RELATIVE_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        # OSError covers absent, a directory in the file's place, and permissions.
        # UnicodeDecodeError is a subclass of ValueError; both are named so the intent survives
        # a reader who does not remember that.
        return None
    body = raw.strip()
    if not body or len(body) > CONTEXT_BODY_MAX:
        return None
    return body
```

- [ ] **Step 4: Write the prompt renderer**

Create `src/sync/context/prompt.py`:

```python
"""Turning a context body into the prompt section that carries it.

Kept beside the seed reader rather than in `sync.remediate` so that the text an agent sees and
the file a customer writes are described in one package. Neither of them knows about Postgres.
"""

from __future__ import annotations

_HEADING = "What is true of this repository:"


def render_section(body: str) -> str:
    """The prompt section for one context body, or the empty string for no body.

    The empty string rather than an empty heading. A heading with nothing under it tells an
    agent that somebody looked and found nothing worth saying, which is a claim; no section at
    all is the absence of a claim, and it is also what keeps the prompt byte-identical to the
    one built before this feature existed.
    """
    stripped = body.strip()
    if not stripped:
        return ""
    return f"{_HEADING}\n{stripped}"
```

- [ ] **Step 5: Write the package exports**

Create `src/sync/context/__init__.py`:

```python
"""Per-repository context: the file a customer may commit, and the prompt section it becomes.

This package knows a file format and a prompt section. It knows nothing about Postgres and
imports no sibling that does -- the same shape as `sync.telemetry`, which knows OTLP and HTTP
and no vendor. It returns data and persists nothing; every write goes through `GraphStore`, and
the caller holds both.
"""

from sync.context.prompt import render_section
from sync.context.seed import SEED_RELATIVE_PATH, read_seed

__all__ = ["SEED_RELATIVE_PATH", "read_seed", "render_section"]
```

- [ ] **Step 6: Add the import-linter contract entry**

In `pyproject.toml`, add `"sync.context"` to `forbidden_modules` under the contract named `sync.core depends on nothing`, keeping the existing entries:

```toml
forbidden_modules = [
    "sync.graph",
    "sync.signals",
    "sync.index",
    "sync.detect",
    "sync.telemetry",
    "sync.remediate",
    "sync.forge",
    "sync.route",
    "sync.cli",
    "sync.context",
]
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
uv run pytest tests/test_context_package.py tests/test_import_boundary.py -v
```

Expected: 12 passed.

- [ ] **Step 8: Commit**

```bash
git add src/sync/context tests/test_context_package.py pyproject.toml
git commit -m "feat: the context file a customer commits, and the section it becomes"
```

---

### Task 3: The prompt carries it

**Files:**
- Modify: `src/sync/remediate/agent_patch.py`
- Test: `tests/test_agent_patch_context.py` (create)

**Interfaces:**
- Consumes: `sync.context.render_section` from Task 2.
- Produces: `build_patch_prompt(finding, change, site, diagnostics="", repo_context="") -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_patch_context.py`. Read `tests/test_agent_patch.py` first and reuse whatever `Finding`, `VendorChange` and `CallSite` builders it already has rather than inventing new ones; the fixtures below name them `finding()`, `change()` and `site()`.

```python
from sync.remediate.agent_patch import build_patch_prompt

# Import the existing builders rather than writing new ones. If `tests/test_agent_patch.py`
# defines them as module-level helpers, import them here; if it defines them as fixtures,
# move them to `tests/conftest.py` in this task and import from there.
from tests.test_agent_patch import change, finding, site


def test_no_context_is_byte_identical_to_the_prompt_without_the_parameter():
    """The landing property. Every existing assertion on this function must hold unchanged.

    Compared against the call that omits the parameter entirely rather than against a stored
    fixture, so this stays true as the rest of the prompt changes.
    """
    without = build_patch_prompt(finding(), change(), site())
    with_empty = build_patch_prompt(finding(), change(), site(), repo_context="")
    assert with_empty == without


def test_context_appears_in_the_prompt():
    prompt = build_patch_prompt(
        finding(), change(), site(), repo_context="Package manager is pnpm."
    )
    assert "Package manager is pnpm." in prompt


def test_context_sits_between_the_rationale_and_the_rules():
    """Section order is load-bearing, and this one has a place rather than an end.

    The repository is described before the edit is constrained, so `Rules:` keeps the last and
    strongest position.
    """
    prompt = build_patch_prompt(
        finding(), change(), site(), repo_context="Package manager is pnpm."
    )
    assert prompt.index("Why this matters") < prompt.index("Package manager is pnpm.")
    assert prompt.index("Package manager is pnpm.") < prompt.index("Rules:")


def test_context_sits_ahead_of_the_diagnostics_block():
    """Everything stable stays ahead of the only part that changes between retries.

    `2026-07-25-sync-latency-architecture.md` binds this: anything appended after diagnostics
    invalidates the cached prefix every round.
    """
    prompt = build_patch_prompt(
        finding(),
        change(),
        site(),
        diagnostics="TS2554: Expected 1 arguments, but got 2.",
        repo_context="Package manager is pnpm.",
    )
    assert prompt.index("Package manager is pnpm.") < prompt.index("A previous attempt failed")


def test_whitespace_only_context_renders_no_section():
    without = build_patch_prompt(finding(), change(), site())
    assert build_patch_prompt(finding(), change(), site(), repo_context="  \n ") == without
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_agent_patch_context.py -v
```

Expected: FAIL — `TypeError: build_patch_prompt() got an unexpected keyword argument 'repo_context'`.

- [ ] **Step 3: Add the parameter**

In `src/sync/remediate/agent_patch.py`, import the renderer at the top:

```python
from sync.context import render_section
```

Change the signature and insert the section. The parameter is trailing and defaulted, so every existing caller is unaffected:

```python
def build_patch_prompt(
    finding: Finding,
    change: VendorChange,
    site: CallSite,
    diagnostics: str = "",
    repo_context: str = "",
) -> str:
    """Everything the agent needs, and nothing it does not."""
```

Inside, after the `f"Why this matters: {finding.rationale}"` entry and before `_SCOPE_RULES`, replace the bare `_SCOPE_RULES` element with a conditional insertion. The `sections` list ends:

```python
        f"Why this matters: {finding.rationale}",
        "",
    ]

    # Ahead of `_SCOPE_RULES` so the rules keep the last and strongest position, and ahead of
    # the diagnostics block so the cacheable prefix grows rather than moves. An empty context
    # appends nothing at all -- not an empty heading -- which is what keeps a prompt built for a
    # repository with no context byte-identical to the prompt built before this existed.
    context_section = render_section(repo_context)
    if context_section:
        sections += [context_section, ""]

    sections.append(_SCOPE_RULES)
```

Update the module docstring's paragraph on section order to name context as the new stable section.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_agent_patch_context.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Run every existing agent-patch and remediation test**

```bash
uv run pytest tests/test_agent_patch.py tests/test_remediation_graph.py -v
```

Expected: all pass, unmodified. If any fails, the change is not additive and the cause is the section insertion — fix it rather than editing the test.

- [ ] **Step 6: Commit**

```bash
git add src/sync/remediate/agent_patch.py tests/test_agent_patch_context.py
git commit -m "feat: the patch prompt carries what is true of the repository"
```

---

### Task 4: `sync run` seeds from the checkout

**Files:**
- Modify: `src/sync/cli.py`
- Test: `tests/test_cli_context_seed.py` (create)

**Interfaces:**
- Consumes: `sync.context.read_seed` (Task 2), `GraphStore.upsert_repo_context` (Task 1).
- Produces: `sync.cli.seed_repo_context(store, repo) -> bool` — True when a row was written.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_context_seed.py`:

```python
import os

import pytest

from sync.cli import seed_repo_context
from sync.context import SEED_RELATIVE_PATH
from sync.core import RepoRef
from sync.core.models import RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _repo(tmp_path) -> RepoRef:
    return RepoRef(
        repo_id="github.com/acme/storefront",
        url="https://github.com/acme/storefront",
        local_path=str(tmp_path),
        head_sha="0" * 40,
    )


def _seed_file(tmp_path, text: str) -> None:
    target = tmp_path / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_no_file_writes_no_row(store, tmp_path):
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront") is None


def test_a_file_writes_a_seeded_row(store, tmp_path):
    _seed_file(tmp_path, "Generated code lives under src/generated.")
    assert seed_repo_context(store, _repo(tmp_path)) is True
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "Generated code lives under src/generated."
    assert found.source == "seeded-file"


def test_seeding_overwrites_an_operator_edit(store, tmp_path):
    """The customer's committed file wins when the two disagree.

    An operator edit to a seeded row is overwritten on the next index, and that is the point:
    the file is the original and the row is a copy of it.
    """
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="an operator wrote this",
            source="operator",
        )
    )
    _seed_file(tmp_path, "the committed file says this")
    seed_repo_context(store, _repo(tmp_path))
    found = store.repo_context("github.com/acme/storefront")
    assert found.body == "the committed file says this"
    assert found.source == "seeded-file"


def test_no_file_leaves_an_operator_row_alone(store, tmp_path):
    """Absence of a file is not an instruction to erase what an operator wrote."""
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="an operator wrote this",
            source="operator",
        )
    )
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront").body == "an operator wrote this"


def test_an_unreadable_file_writes_no_row_and_does_not_raise(store, tmp_path):
    target = tmp_path / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"broken \xff bytes")
    assert seed_repo_context(store, _repo(tmp_path)) is False
    assert store.repo_context("github.com/acme/storefront") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_cli_context_seed.py -v
```

Expected: FAIL — `ImportError: cannot import name 'seed_repo_context' from 'sync.cli'`.

- [ ] **Step 3: Write the function**

In `src/sync/cli.py`, import the reader and the model near the existing imports:

```python
from sync.context import read_seed
from sync.core.models import RepoContext
```

Add the function beside `_clone` and `_reset_clone`:

```python
def seed_repo_context(store: GraphStore, repo: RepoRef) -> bool:
    """Copy the checkout's `.sync/context.md` into the graph, if it has one.

    Returns whether a row was written, which is what the caller logs. Absent, empty, unreadable
    and oversize all return False: the caller cannot act differently on any of them, and a run
    must not be abandoned because a customer's optional file is malformed.

    A missing file leaves an existing row alone. Absence of a file is not an instruction to
    erase what an operator wrote -- only a present, readable file overwrites, and then the
    customer's own text is what wins.
    """
    body = read_seed(repo.local_path)
    if body is None:
        return False
    store.upsert_repo_context(
        RepoContext(repo_id=repo.repo_id, body=body, source="seeded-file")
    )
    return True
```

- [ ] **Step 4: Call it from `run`**

In `src/sync/cli.py`'s `run`, immediately after the clone or local-checkout resolution produces `repo` and the store is available, add:

```python
    if seed_repo_context(store, repo):
        print(f"context: seeded from {SEED_RELATIVE_PATH} for {repo.repo_id}")
```

Import `SEED_RELATIVE_PATH` from `sync.context` alongside `read_seed`. Match the surrounding progress output's form — if `run` uses a logger rather than `print`, use that instead.

- [ ] **Step 5: Read the context back when building a patch prompt**

Find where `run` builds the remediation state and passes `finding`, `change` and `site` toward `build_patch_prompt`. Read the row once per run, not once per finding:

```python
    context_row = store.repo_context(repo.repo_id)
    repo_context = context_row.body if context_row is not None else ""
```

Thread `repo_context` through to `build_patch_prompt`'s call site in `sync/remediate`. If the remediation state is a typed object, add `repo_context: str = ""` to it and set it here; the default keeps every existing construction valid.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
uv run pytest tests/test_cli_context_seed.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Run the remediation suite**

```bash
uv run pytest tests/test_remediation_graph.py tests/test_agent_patch.py tests/test_agent_patch_context.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/sync/cli.py src/sync/remediate tests/test_cli_context_seed.py
git commit -m "feat: a run seeds context from the checkout and hands it to the patch agent"
```

---

### Task 5: The console reads and writes it

**Files:**
- Modify: `src/sync/dashboard/graph_views.py`
- Modify: `src/sync/api/app.py`
- Test: `tests/test_graph_views_context.py` (create)
- Test: `tests/test_api_context.py` (create)

**Interfaces:**
- Consumes: `GraphStore.repo_context`, `GraphStore.upsert_repo_context` (Task 1); `CONTEXT_BODY_MAX` (Task 1).
- Produces:
  - `graph_views.repo_context(store, repo_id) -> dict` with keys `repo_id`, `body`, `source`, `updated_at`
  - `ContextReader = Callable[[str], dict]` and `ContextWriter = Callable[[str, str], None]` in `sync.api.app`
  - Routes `GET` and `POST /api/repos/{repo_id}/context`

- [ ] **Step 1: Write the failing view test**

Create `tests/test_graph_views_context.py`:

```python
import os

import pytest

from sync.core.models import RepoContext
from sync.dashboard import graph_views
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_repository_with_no_context_echoes_its_scope_and_an_empty_body(store):
    """A payload that names the scope it was computed in cannot be rendered under the wrong
    heading in silence -- the convention every repository-scoped view in this module keeps."""
    view = graph_views.repo_context(store, "github.com/acme/storefront")
    assert view["repo_id"] == "github.com/acme/storefront"
    assert view["body"] == ""
    assert view["source"] is None
    assert view["updated_at"] is None


def test_a_stored_context_renders_with_its_source(store):
    """`source` is rendered because the precedence rule surprises anyone who meets the body
    without it: a seeded row is overwritten on the next index and an operator row is not."""
    store.upsert_repo_context(
        RepoContext(
            repo_id="github.com/acme/storefront",
            body="Package manager is pnpm.",
            source="seeded-file",
        )
    )
    view = graph_views.repo_context(store, "github.com/acme/storefront")
    assert view["body"] == "Package manager is pnpm."
    assert view["source"] == "seeded-file"
    assert isinstance(view["updated_at"], str)


def test_the_view_returns_primitives_rather_than_a_live_model(store):
    store.upsert_repo_context(
        RepoContext(repo_id="r", body="b", source="operator")
    )
    view = graph_views.repo_context(store, "r")
    assert isinstance(view, dict)
    assert not isinstance(view["updated_at"], object.__class__) or isinstance(view["updated_at"], str)
    assert all(isinstance(v, (str, type(None))) for v in view.values())
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_graph_views_context.py -v
```

Expected: FAIL — `AttributeError: module 'sync.dashboard.graph_views' has no attribute 'repo_context'`.

- [ ] **Step 3: Write the view**

Append to `src/sync/dashboard/graph_views.py`, and add `repo_context` to the docstring's list of functions:

```python
def repo_context(store: GraphStore, repo_id: str) -> dict:
    """One repository's context, as the row the console renders.

    Echoes `repo_id` back for the reason every repository-scoped view here does: a payload that
    names the scope it was computed in cannot be rendered under the wrong heading in silence.

    `source` is part of the payload rather than an internal detail. The precedence rule --
    a `seeded-file` row is overwritten by the next index and an `operator` row is not -- is
    invisible in the body and surprising when met, so a screen that rendered bare prose would
    be hiding the one fact a reader needs before editing it.

    An absent row is an empty body with a null source rather than a 404. A repository that has
    no context is a normal repository, and the screen that offers to write some is the same
    screen that shows what is there.
    """
    found = store.repo_context(repo_id)
    return {
        "repo_id": repo_id,
        "body": found.body if found is not None else "",
        "source": found.source if found is not None else None,
        "updated_at": found.updated_at.isoformat() if found is not None and found.updated_at else None,
    }
```

- [ ] **Step 4: Write the failing route test**

Create `tests/test_api_context.py`. Read `tests/test_api_app.py` first and build the app the way it already does — `create_app` requires every reader, so reuse its existing fake-reader helper rather than writing a new set:

```python
import pytest
from starlette.testclient import TestClient

from sync.core.models import CONTEXT_BODY_MAX
# Reuse whatever helper `tests/test_api_app.py` uses to satisfy `create_app`'s required
# readers. If it is a fixture, move it to `tests/conftest.py` in this task.
from tests.test_api_app import app_with


@pytest.fixture()
def written():
    return []


@pytest.fixture()
def client(written):
    stored = {"repo_id": "r", "body": "", "source": None, "updated_at": None}

    def context_reader(repo_id: str) -> dict:
        return {**stored, "repo_id": repo_id}

    def context_writer(repo_id: str, body: str) -> None:
        written.append((repo_id, body))

    return TestClient(app_with(context_reader=context_reader, context_writer=context_writer))


def test_get_returns_the_view(client):
    response = client.get("/api/repos/github.com%2Facme%2Fstorefront/context")
    assert response.status_code == 200
    assert response.json()["body"] == ""


def test_post_writes_and_returns_the_view(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "Package manager is pnpm."}
    )
    assert response.status_code == 200
    assert written == [("r", "Package manager is pnpm.")]


def test_post_with_an_empty_body_is_400_and_writes_nothing(client, written):
    response = client.post("/api/repos/r/context", json={"body": "   "})
    assert response.status_code == 400
    assert written == []


def test_post_with_a_missing_body_key_is_400(client, written):
    assert client.post("/api/repos/r/context", json={}).status_code == 400
    assert written == []


def test_post_with_a_non_string_body_is_400(client, written):
    assert client.post("/api/repos/r/context", json={"body": 7}).status_code == 400
    assert written == []


def test_post_over_the_cap_is_400_naming_the_limit(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "x" * (CONTEXT_BODY_MAX + 1)}
    )
    assert response.status_code == 400
    assert str(CONTEXT_BODY_MAX) in response.json()["error"]
    assert written == []


def test_post_exactly_at_the_cap_is_accepted(client, written):
    response = client.post(
        "/api/repos/r/context", json={"body": "x" * CONTEXT_BODY_MAX}
    )
    assert response.status_code == 200
    assert written == [("r", "x" * CONTEXT_BODY_MAX)]
```

- [ ] **Step 5: Run it to verify it fails**

```bash
uv run pytest tests/test_api_context.py -v
```

Expected: FAIL — `TypeError: create_app() got an unexpected keyword argument 'context_reader'`.

- [ ] **Step 6: Add the routes**

In `src/sync/api/app.py`, declare the two callables beside the existing reader aliases:

```python
# Context is a reader and a writer rather than a reader alone, because this is the first route
# on this app that writes. Both are injected for the reason every reader above is: a test
# substitutes fakes without reaching into module state.
ContextReader = Callable[[str], dict[str, Any]]
ContextWriter = Callable[[str, str], None]
```

Add both to `create_app`'s keyword-only parameters — required, not defaulted, matching the docstring's rule that a deployment forgetting one fails at start-up rather than 500ing a customer's first visit.

Add the handlers inside `create_app`:

```python
    async def repo_context(request: Request) -> JSONResponse:
        return JSONResponse(context_reader(request.path_params["repo_id"]))

    async def set_repo_context(request: Request) -> JSONResponse:
        """Write one repository's context.

        The first write route on this app. The transport still holds no logic: it checks the
        body is a non-empty string within the cap, calls one writer, and returns the reader's
        view of what it wrote.

        Over the cap is refused rather than truncated, and the message names the limit -- a 400
        that does not say how long is too long leaves the caller guessing at a number this
        module knows.
        """
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        body = payload.get("body") if isinstance(payload, dict) else None
        if not isinstance(body, str) or not body.strip():
            return JSONResponse({"error": "body must be a non-empty string"}, status_code=400)
        if len(body) > CONTEXT_BODY_MAX:
            return JSONResponse(
                {"error": f"body must be at most {CONTEXT_BODY_MAX} characters"},
                status_code=400,
            )
        repo_id = request.path_params["repo_id"]
        context_writer(repo_id, body.strip())
        return JSONResponse(context_reader(repo_id))
```

Register both routes in the `Route(...)` list:

```python
        Route("/api/repos/{repo_id:path}/context", repo_context, methods=["GET"]),
        Route("/api/repos/{repo_id:path}/context", set_repo_context, methods=["POST"]),
```

`{repo_id:path}` rather than `{repo_id}`: a `repo_id` is `host/owner/name` and contains slashes, so the default converter would never match one.

Import `CONTEXT_BODY_MAX` from `sync.core.models` at the top.

- [ ] **Step 7: Wire the real readers at start-up**

In `src/sync/api/__main__.py`, pass the two new arguments where the other readers are built:

```python
        context_reader=lambda repo_id: graph_views.repo_context(store, repo_id),
        context_writer=lambda repo_id, body: store.upsert_repo_context(
            RepoContext(repo_id=repo_id, body=body, source="operator")
        ),
```

Import `RepoContext` from `sync.core.models`.

- [ ] **Step 8: Run the tests to verify they pass**

```bash
uv run pytest tests/test_graph_views_context.py tests/test_api_context.py tests/test_api_app.py -v
```

Expected: all pass. Existing `test_api_app.py` tests must pass without modification beyond supplying the two new required readers.

- [ ] **Step 9: Commit**

```bash
git add src/sync/dashboard/graph_views.py src/sync/api tests/test_graph_views_context.py tests/test_api_context.py
git commit -m "feat: the console reads a repository's context and an operator may write it"
```

---

### Task 6: `sync context` on the command line

**Files:**
- Modify: `src/sync/cli.py`
- Test: `tests/test_cli_context_command.py` (create)

**Interfaces:**
- Consumes: `GraphStore.repo_context`, `GraphStore.upsert_repo_context` (Task 1).
- Produces: `sync context show --repo-id X`, `sync context set --repo-id X --body <path|->`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_context_command.py`:

```python
import io
import os

import pytest

from sync.cli import main
from sync.core.models import RepoContext
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_show_prints_nothing_and_exits_zero_when_there_is_no_context(store, capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["sync", "context", "show", "--repo-id", "r", "--dsn", DSN])
    assert main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_show_prints_the_body(store, capsys, monkeypatch):
    store.upsert_repo_context(RepoContext(repo_id="r", body="pnpm", source="operator"))
    monkeypatch.setattr("sys.argv", ["sync", "context", "show", "--repo-id", "r", "--dsn", DSN])
    assert main() == 0
    assert "pnpm" in capsys.readouterr().out


def test_set_from_a_file_writes_an_operator_row(store, tmp_path, monkeypatch):
    source_file = tmp_path / "ctx.md"
    source_file.write_text("Generated code lives under src/generated.", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["sync", "context", "set", "--repo-id", "r", "--body", str(source_file), "--dsn", DSN],
    )
    assert main() == 0
    found = store.repo_context("r")
    assert found.body == "Generated code lives under src/generated."
    assert found.source == "operator"


def test_set_from_stdin_writes_an_operator_row(store, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("read from stdin"))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() == 0
    assert store.repo_context("r").body == "read from stdin"


def test_set_over_the_cap_writes_nothing_and_exits_non_zero(store, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("x" * 8001))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() != 0
    assert "8000" in capsys.readouterr().err
    assert store.repo_context("r") is None


def test_set_with_an_empty_body_writes_nothing_and_exits_non_zero(store, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("   \n "))
    monkeypatch.setattr(
        "sys.argv", ["sync", "context", "set", "--repo-id", "r", "--body", "-", "--dsn", DSN]
    )
    assert main() != 0
    assert store.repo_context("r") is None
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_cli_context_command.py -v
```

Expected: FAIL — argparse exits with `invalid choice: 'context'`.

- [ ] **Step 3: Write the command functions**

In `src/sync/cli.py`, beside the other command functions:

```python
def context_show(args: argparse.Namespace) -> int:
    """Print one repository's context body, or nothing when it has none.

    Nothing rather than a message, and zero rather than an error. A repository with no context
    is a normal repository, and a caller piping this into a file wants an empty file rather
    than the word "none" in it.
    """
    store = GraphStore(args.dsn)
    found = store.repo_context(args.repo_id)
    if found is not None:
        print(found.body)
    return 0


def context_set(args: argparse.Namespace) -> int:
    """Write one repository's context from a file or from stdin.

    `source` is `operator` and not a choice. The CLI is a human at a keyboard, and a flag that
    let a caller write `seeded-file` would let Sync's own precedence rule be spoofed by the
    party it protects the customer from.

    Over the cap and empty both refuse, and neither writes. Truncating would hand an agent prose
    cut mid-sentence, and writing an empty body would make absence and emptiness two states.
    """
    if args.body == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.body).read_text(encoding="utf-8")
    body = raw.strip()
    if not body:
        print("context: refusing to write an empty body", file=sys.stderr)
        return 1
    if len(body) > CONTEXT_BODY_MAX:
        print(
            f"context: body is {len(body)} characters; the limit is {CONTEXT_BODY_MAX}",
            file=sys.stderr,
        )
        return 1
    GraphStore(args.dsn).upsert_repo_context(
        RepoContext(repo_id=args.repo_id, body=body, source="operator")
    )
    return 0
```

Import `CONTEXT_BODY_MAX` alongside the existing `RepoContext` import added in Task 4.

- [ ] **Step 4: Register the subcommand**

In `main()`, beside the other `sub.add_parser` calls:

```python
    context_parser = sub.add_parser(
        "context", help="read or write what stays true of one repository"
    )
    context_sub = context_parser.add_subparsers(dest="context_command", required=True)

    context_show_parser = context_sub.add_parser("show", help="print a repository's context")
    context_show_parser.add_argument("--repo-id", dest="repo_id", required=True)
    context_show_parser.add_argument("--dsn", default=DEFAULT_DSN)
    context_show_parser.set_defaults(func=context_show)

    context_set_parser = context_sub.add_parser("set", help="write a repository's context")
    context_set_parser.add_argument("--repo-id", dest="repo_id", required=True)
    context_set_parser.add_argument(
        "--body", required=True, help="path to a file holding the context, or - for stdin"
    )
    context_set_parser.add_argument("--dsn", default=DEFAULT_DSN)
    context_set_parser.set_defaults(func=context_set)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_cli_context_command.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/sync/cli.py tests/test_cli_context_command.py
git commit -m "feat: sync context show and set, from a file or from stdin"
```

---

### Task 7: The MCP server says it has context, and serves it

**Files:**
- Modify: `src/sync/mcp/resources.py`
- Modify: `src/sync/mcp/server.py`
- Test: `tests/test_mcp_context.py` (create)

**Interfaces:**
- Consumes: `GraphStore.repo_context` (Task 1).
- Produces:
  - `resources.CONTEXT_URI_PREFIX = "sync://context/"`, `CONTEXT_URI_TEMPLATE`, `CONTEXT_MIME_TYPE = "text/markdown"`
  - `resources.read(uri, feed, known_vendors, context_reader=None)` — new trailing keyword, defaulted
  - `server.SERVER_INSTRUCTIONS: str`

**Neither change is a tool.** `tests/golden/tool_schemas.json` must not be regenerated, and `sync.mcp.registry` is untouched.

Context appears as a **template only**, never in `resources/list`. That listing is concrete URIs a client can read right now, and enumerating every repository would be a query this module has no business making — the same reason the feed lists only vendors a verified snapshot is held for.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_context.py`:

```python
import json

import pytest

from sync.mcp.resources import (
    CONTEXT_MIME_TYPE,
    CONTEXT_URI_TEMPLATE,
    ResourceError,
    read,
    resource_templates_as_data,
)
from sync.mcp.server import SERVER_INSTRUCTIONS


def test_the_context_template_is_advertised():
    templates = {t["uriTemplate"] for t in resource_templates_as_data()}
    assert CONTEXT_URI_TEMPLATE in templates
    assert "sync://feed/{vendor}" in templates


def test_the_context_template_declares_markdown():
    template = next(
        t for t in resource_templates_as_data() if t["uriTemplate"] == CONTEXT_URI_TEMPLATE
    )
    assert template["mimeType"] == CONTEXT_MIME_TYPE


def test_reading_a_repository_with_context_returns_its_body():
    result = read(
        "sync://context/github.com/acme/storefront",
        feed=None,
        known_vendors=(),
        context_reader=lambda repo_id: "Package manager is pnpm.",
    )
    assert result["contents"][0]["text"] == "Package manager is pnpm."
    assert result["contents"][0]["mimeType"] == CONTEXT_MIME_TYPE


def test_reading_a_repository_with_no_context_is_an_error_rather_than_an_empty_string():
    """An empty resource and a repository nobody has described are different facts.

    A client that received "" has no way to tell them apart, and would report the repository as
    described-with-nothing.
    """
    with pytest.raises(ResourceError):
        read(
            "sync://context/github.com/acme/storefront",
            feed=None,
            known_vendors=(),
            context_reader=lambda repo_id: None,
        )


def test_a_server_with_no_context_reader_refuses_rather_than_returning_nothing():
    with pytest.raises(ResourceError):
        read("sync://context/anything", feed=None, known_vendors=())


def test_the_repo_id_keeps_its_slashes():
    """`repo_id` is host/owner/name. A parser that split on the first slash would look up
    'github.com' and find nothing, for every repository."""
    seen = []
    read(
        "sync://context/github.com/acme/storefront",
        feed=None,
        known_vendors=(),
        context_reader=lambda repo_id: seen.append(repo_id) or "body",
    )
    assert seen == ["github.com/acme/storefront"]


def test_the_instructions_name_no_tool_that_does_not_exist():
    from sync.mcp.registry import schemas_as_data

    published = {schema["name"] for schema in schemas_as_data()}
    for word in SERVER_INSTRUCTIONS.split():
        candidate = word.strip("`.,()")
        if candidate.startswith("sync_"):
            assert candidate in published, f"instructions name an absent tool: {candidate}"


def test_the_tool_schemas_golden_file_is_untouched():
    """The tripwire on the frozen four. If this design ever needs the golden file regenerated,
    the design is wrong."""
    from pathlib import Path

    from sync.mcp.registry import schemas_as_data

    golden = json.loads(
        (Path(__file__).parent / "golden" / "tool_schemas.json").read_text(encoding="utf-8")
    )
    assert schemas_as_data() == golden
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_mcp_context.py -v
```

Expected: FAIL — `ImportError: cannot import name 'CONTEXT_MIME_TYPE' from 'sync.mcp.resources'`.

- [ ] **Step 3: Add the resource**

In `src/sync/mcp/resources.py`, beside the feed constants:

```python
CONTEXT_URI_PREFIX = "sync://context/"
CONTEXT_URI_TEMPLATE = f"{CONTEXT_URI_PREFIX}{{repo_id}}"
CONTEXT_MIME_TYPE = "text/markdown"
```

Add a second entry to `RESOURCE_TEMPLATES`:

```python
    ResourceTemplateSpec(
        uri_template=CONTEXT_URI_TEMPLATE,
        name="repository-context",
        description=(
            "What stays true of one repository while its code changes underneath: "
            "conventions, generated directories, the package manager its lockfile names. "
            "Written by an operator or copied from a `.sync/context.md` the repository "
            "itself carries. Never a call site, a finding or telemetry."
        ),
        mime_type=CONTEXT_MIME_TYPE,
    ),
```

Extend `read` with a trailing defaulted keyword and a branch, leaving the feed path exactly as it is:

```python
def read(
    uri: str,
    feed: FeedCache | None,
    known_vendors: tuple[str, ...],
    context_reader: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    if uri.startswith(CONTEXT_URI_PREFIX):
        return _read_context(uri, context_reader)
    if not uri.startswith(FEED_URI_PREFIX):
        raise ResourceError(f"unknown resource: {uri}", UNKNOWN_RESOURCE, uri=uri)
    # ... the existing feed body, unchanged ...
```

And the helper beside it:

```python
def _read_context(uri: str, context_reader: Callable[[str], str | None] | None) -> dict[str, Any]:
    """One repository's context, or a `ResourceError` naming why there is none.

    The repository id keeps every slash after the prefix. A `repo_id` is `host/owner/name`, so
    a parser that split on the first one would look up "github.com" and find nothing, for every
    repository that exists.

    A repository with no context is an error rather than an empty string. A client that received
    "" could not tell "nobody has described this repository" from "somebody described it as
    nothing", and would report the second.
    """
    repo_id = uri[len(CONTEXT_URI_PREFIX):]
    if context_reader is None:
        raise ResourceError(
            "this server serves no repository context", UNKNOWN_RESOURCE, uri=uri
        )
    body = context_reader(repo_id)
    if body is None:
        raise ResourceError(
            f"no context is held for '{repo_id}'", UNKNOWN_RESOURCE, uri=uri
        )
    return {"contents": [{"uri": uri, "mimeType": CONTEXT_MIME_TYPE, "text": body}]}
```

Import `Callable` from `collections.abc` if the module does not already.

- [ ] **Step 4: Add the instructions and wire the reader**

In `src/sync/mcp/server.py`, above `main`:

```python
# Advisory guidance a compatible client receives in the initialize response. `instructions` is a
# field the MCP specification defines on `InitializeResult` in revision 2025-06-18, which is what
# `PROTOCOL_VERSION` pins -- it is not a tool, it does not pass through `sync.mcp.registry`, and
# the golden tool-schema file never sees it.
#
# It names no tool that does not exist. A client that acted on an invented name would get a
# method error from a server that had just advertised it, which is worse than saying nothing.
SERVER_INSTRUCTIONS = "\n".join(
    [
        "Sync holds the API Dependency Graph for this machine's repositories: which call sites "
        "depend on which third-party operations, what those vendors changed, and what the "
        "repository's own traffic showed.",
        "",
        "Read `sync://context/<repo_id>` before proposing an edit to a repository. It carries "
        "what stays true of that checkout -- conventions, generated directories, the package "
        "manager its lockfile names -- and it is cheaper than rediscovering any of it. A "
        "repo_id is host/owner/name, for example github.com/acme/storefront.",
        "",
        "This server never writes to a repository. `sync_propose_patch` returns a verified "
        "patch as data and stops before anything is pushed; deciding what to do with it is "
        "yours.",
    ]
)
```

Add the field to the `initialize` result, beside `capabilities` and `serverInfo`:

```python
                "instructions": SERVER_INSTRUCTIONS,
```

Pass the reader through `_read`. Where `main` builds the `GraphStore` and the surface, build the reader and hand it to the read path:

```python
    def context_reader(repo_id: str) -> str | None:
        found = store.repo_context(repo_id)
        return found.body if found is not None else None
```

Thread it into the `resources/read` branch:

```python
    if method == "resources/read":
        return _read(request_id, params, feed, context_reader)
```

and add the trailing parameter to `_read`, defaulted to `None` so every existing test that calls it with three arguments keeps passing.

- [ ] **Step 5: Run the tests to verify they pass**

```bash
uv run pytest tests/test_mcp_context.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Run every MCP test, unmodified**

```bash
uv run pytest tests/test_mcp_main.py tests/test_mcp_entry_point.py tests/test_mcp_propose_patch.py tests/test_mcp_resources.py -v
```

Expected: all pass without edits. `tests/golden/tool_schemas.json` must be unchanged — confirm with `git status` that it is not modified.

- [ ] **Step 7: Run the whole suite**

```bash
uv run pytest
```

Expected: green. Roughly two to four minutes.

- [ ] **Step 8: Commit**

```bash
git add src/sync/mcp tests/test_mcp_context.py
git commit -m "feat: the MCP server advertises repository context and serves it as a resource"
```

---

## Self-Review

**Spec coverage.** Every section of `2026-08-06-sync-repo-context-design.md` maps to a task: the table and model to Task 1; `sync.context` and the import-linter contract to Task 2; prompt injection to Task 3; seeding and precedence to Task 4; the write path and the console view to Task 5; the CLI to Task 6; both MCP primitives to Task 7. The design's two checkable claims — the untouched golden file and the byte-identical prompt — are asserted in Task 7 Step 1 and Task 3 Step 1 respectively.

**Not covered, and deliberately.** The design's "What this does not do" section names three: no agent-written context (`CONTEXT_SOURCES` ships with two members and Task 1 Step 1 asserts it), no console screen (M7's line, not this plan), and the incomplete import-linter list (Task 2 adds only `sync.context`).

**Type consistency.** `RepoContext(repo_id, body, source, updated_at)` is used identically in Tasks 1, 4, 5 and 6. `CONTEXT_BODY_MAX` is defined in Task 1 and consumed in Tasks 2, 5 and 6. `read_seed` returns `str | None` in Task 2 and is consumed as such in Task 4. `graph_views.repo_context` returns a dict in Task 5 and is the `context_reader` the API consumes; the MCP `context_reader` in Task 7 is a different callable returning `str | None`, which is intentional — one serves a JSON view and the other a resource body.

**One thing an implementer must check rather than assume.** Tasks 3, 5 and 6 import helpers from existing test modules (`tests/test_agent_patch.py`, `tests/test_api_app.py`). If those helpers are pytest fixtures rather than plain functions, move them to `tests/conftest.py` as part of the task that first needs them, and say so in that task's commit body.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-08-06-sync-repo-context.md`.

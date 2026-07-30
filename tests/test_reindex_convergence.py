"""What a second index of a changed repository leaves behind.

`upsert_call_site` keys identity on `(repo_id, path, symbol, line, col)` and its own comment says
what that costs: "a call site that merely shifts down the file (no other content change) becomes a
new row rather than an update to the old one. That is safe at M0 only because cli.py truncates the
whole graph at the start of every run." Three facts, measured against Postgres before any of this
was written:

1. One blank line inserted above a call site turns one row into two, and the stale row keeps the
   finding that was raised against it -- `finding.call_site_id` cascades on delete, and nothing was
   deleting.
2. The cure was `truncate_all()`, which empties every table in the database. A second repository's
   call sites go with it. `cli.py` states that a hosted control plane must never do this "since it
   would erase other customers' state rather than just this one's".
3. So the wipe is load-bearing rather than convenient, and it is load-bearing because a query was
   missing a clause: `call_sites_for_operation(vendor_id, operation_id)` had no repository filter,
   so with two repositories in one graph `VendorChangeDetector` emitted a finding for each. Two of
   the four detectors already held the `repo_id` they needed and did not pass it.

`.claude/rules/graph-grain.md`: "Re-running a stage must converge, not accumulate." The idempotence
already tested is over *identical* input, which converges through the natural key. Convergence over
a repository that changed is what nothing tested and nothing implemented.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

_DETECTORS = Path(__file__).resolve().parents[1] / "src" / "sync" / "detect"


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(**over) -> CallSite:
    fields = dict(
        repo_id="repo-a", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create", args_keys=["amount"],
        response_fields_read=["status"], sdk_version="18.0.0", content_hash="h1",
    )
    fields.update(over)
    return CallSite(**fields)


def _positions(store: GraphStore) -> list[tuple[str, str, int]]:
    with store._connect().cursor() as cur:
        cur.execute("SELECT repo_id, path, line FROM call_site ORDER BY repo_id, path, line")
        return [(r["repo_id"], r["path"], r["line"]) for r in cur.fetchall()]


_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-optional-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "response-optional-property-removed",
         "text": "removed the optional property `status` from the response"},
)


# --- convergence over a repository that changed -----------------------------------------


def test_a_call_site_that_moved_leaves_no_row_where_it_used_to_be(store) -> None:
    """The reproduction, and the whole of the defect: one blank line added above the call."""
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [_site(line=13)])

    assert _positions(store) == [("repo-a", "src/billing.ts", 13)]


def test_a_call_site_that_was_deleted_leaves_no_row(store) -> None:
    """A call the customer removed is not a call site, and a detector cannot tell a row for one
    from a row for a call that is still there."""
    store.replace_call_sites(
        "repo-a", [_site(line=12), _site(line=40, content_hash="h2")]
    )
    store.replace_call_sites("repo-a", [_site(line=12)])

    assert _positions(store) == [("repo-a", "src/billing.ts", 12)]


def test_a_repository_that_now_calls_nothing_keeps_no_rows(store) -> None:
    """The empty set is a real answer, not a no-op guard. A customer who removed their last call
    to a vendor has zero call sites, and a convergence that declined to write that would leave the
    graph claiming an integration that is gone."""
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [])

    assert _positions(store) == []


def test_the_row_that_goes_takes_its_findings_with_it(store) -> None:
    """`finding.call_site_id` is `ON DELETE CASCADE`, which is what makes this safe to do at all.

    A finding pointing at a position the code no longer has is worse than a missing one: it reads
    as a live defect, and `make_locate` would send an agent to a line that moved.
    """
    stale = store.replace_call_sites("repo-a", [_site(line=12)])[0]
    store.insert_finding(Finding(
        id="", detector="vendor_change", claim="response-field", call_site_id=stale,
        vendor_change_id=None, severity="breaking", rationale="PostCharges dropped status",
    ))

    store.replace_call_sites("repo-a", [_site(line=13)])

    assert store.open_findings() == []


def test_replacing_with_the_same_sites_changes_no_identity(store) -> None:
    """Idempotence, which the natural key already gave and the delete must not take away.

    `graph-grain.md` asks for exactly this assertion: run the stage twice against one fixture and
    check the row count and every row identity are unchanged.
    """
    sites = [_site(line=12), _site(line=40, content_hash="h2")]

    first = store.replace_call_sites("repo-a", sites)
    second = store.replace_call_sites("repo-a", sites)

    assert first == second
    assert len(_positions(store)) == 2


def test_re_indexing_one_repository_leaves_another_alone(store) -> None:
    """The reason this is a per-repository operation and not a smarter truncate."""
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites(
        "repo-b", [_site(repo_id="repo-b", path="src/pay.ts", line=40, content_hash="h2")]
    )

    store.replace_call_sites("repo-a", [_site(line=13)])

    assert _positions(store) == [
        ("repo-a", "src/billing.ts", 13),
        ("repo-b", "src/pay.ts", 40),
    ]


# --- the clause the wipe was standing in for --------------------------------------------


def test_the_store_answers_for_one_repository_when_asked(store) -> None:
    """Unscoped stays available and means every repository, which is a real query for an aggregate
    over customers. What it cannot go on being is the only form, because a detector scans one."""
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites(
        "repo-b", [_site(repo_id="repo-b", path="src/pay.ts", line=40, content_hash="h2")]
    )

    everywhere = store.call_sites_for_operation("stripe", "PostCharges")
    scoped = store.call_sites_for_operation("stripe", "PostCharges", repo_id="repo-a")

    assert {s.repo_id for s in everywhere} == {"repo-a", "repo-b"}
    assert {s.repo_id for s in scoped} == {"repo-a"}


def test_a_detector_scanning_one_repository_ignores_another(store) -> None:
    """Measured before the fix: two findings, one per repository, from a scan of one.

    A finding names a call site, and a pull request is opened against the repository that call site
    belongs to. Crossing repositories here is not noise -- it is a patch proposed to a customer for
    a line in somebody else's codebase.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites(
        "repo-b", [_site(repo_id="repo-b", path="src/pay.ts", line=40, content_hash="h2")]
    )
    store.upsert_vendor_change(_CHANGE)

    findings = list(VendorChangeDetector(store, vendor_id="stripe", repo_id="repo-a").scan())

    assert [store.get_call_site(f.call_site_id).repo_id for f in findings] == ["repo-a"]


@pytest.mark.parametrize(
    "module", sorted(p.name for p in _DETECTORS.glob("*.py") if p.name != "__init__.py")
)
def test_no_detector_asks_for_call_sites_without_naming_the_repository(module: str) -> None:
    """A guard rather than four fixtures, and a guard is what this needs.

    All four detectors called `call_sites_for_operation(vendor_id, operation_id)` and two of them
    already held a `repo_id`; the parameter is keyword-only and optional so the unscoped query stays
    expressible, which means a fifth detector can silently reacquire the defect. This is what makes
    that loud. Read from the source rather than from behaviour because a detector needing observed
    shapes or spans to emit anything cannot be checked cheaply any other way.
    """
    tree = ast.parse((_DETECTORS / module).read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "call_sites_for_operation":
            continue
        assert any(keyword.arg == "repo_id" for keyword in node.keywords), (
            f"{module} line {node.lineno} asks the store for call sites on an operation without "
            f"naming a repository, so it will find every customer's"
        )

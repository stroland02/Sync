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

A fourth fact, measured after the first three had been acted on and the reason this file was
rewritten: making the stale row go away by deleting it takes the finding with it. One row, one
finding, a comment added above the call -- the ghost went and the finding count went to zero, with
no error. So the convergence asserted here is over what the graph *asserts*, not over what it
stores: a retracted row stays, keeps whatever was concluded about it, and is excluded from every
query that speaks for the revision last indexed. Which is why the helpers below read
`retracted_at IS NULL` rather than the whole table -- a test that asserted an empty table would
have been asserting the defect.
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


def _positions(store: GraphStore, *, retracted: bool = False) -> list[tuple[str, str, int]]:
    """The positions the graph asserts, or the ones it has retracted. Never both.

    Two calls rather than one query returning a flag, because every assertion in this file is
    about one of the two sets and a test that mixed them would pass on either.
    """
    predicate = "IS NOT NULL" if retracted else "IS NULL"
    with store._connect().cursor() as cur:
        cur.execute(
            f"SELECT repo_id, path, line FROM call_site WHERE retracted_at {predicate} "
            f"ORDER BY repo_id, path, line"
        )
        return [(r["repo_id"], r["path"], r["line"]) for r in cur.fetchall()]


def _retracted_at(store: GraphStore, path: str, line: int):
    with store._connect().cursor() as cur:
        cur.execute(
            "SELECT retracted_at FROM call_site WHERE path = %s AND line = %s", (path, line)
        )
        return cur.fetchone()["retracted_at"]


def _findings_in_table(store: GraphStore) -> list[str]:
    """Every finding row, whatever its status and whatever became of its call site.

    Deliberately not `open_findings`: this asks whether the record is still there, and the
    record being there while nothing acts on it is the property this file exists to hold apart.
    """
    with store._connect().cursor() as cur:
        cur.execute("SELECT id FROM finding ORDER BY id")
        return [r["id"] for r in cur.fetchall()]


_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v1", to_version="v2",
    kind="response-optional-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    raw={"id": "response-optional-property-removed",
         "text": "removed the optional property `status` from the response"},
)


# --- convergence over a repository that changed -----------------------------------------


def test_a_call_site_that_moved_is_no_longer_asserted_where_it_used_to_be(store) -> None:
    """The reproduction, and the whole of the defect: one blank line added above the call.

    Both sets are asserted because only the pair says what happened. The graph stops claiming line
    12 -- which is what a detector, a rank and `make_locate` all read -- and the row is still there
    to hold the findings raised while it was current.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [_site(line=13)])

    assert _positions(store) == [("repo-a", "src/billing.ts", 13)]
    assert _positions(store, retracted=True) == [("repo-a", "src/billing.ts", 12)]


def test_a_call_site_that_was_deleted_is_no_longer_asserted(store) -> None:
    """A call the customer removed is not a call site, and a detector cannot tell a row for one
    from a row for a call that is still there."""
    store.replace_call_sites(
        "repo-a", [_site(line=12), _site(line=40, content_hash="h2")]
    )
    store.replace_call_sites("repo-a", [_site(line=12)])

    assert _positions(store) == [("repo-a", "src/billing.ts", 12)]
    assert _positions(store, retracted=True) == [("repo-a", "src/billing.ts", 40)]


def test_a_repository_that_now_calls_nothing_asserts_no_call_sites(store) -> None:
    """The empty set is a real answer, not a no-op guard. A customer who removed their last call
    to a vendor has zero call sites, and a convergence that declined to write that would leave the
    graph claiming an integration that is gone."""
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [])

    assert _positions(store) == []
    assert _positions(store, retracted=True) == [("repo-a", "src/billing.ts", 12)]


def test_a_call_that_comes_back_to_its_old_position_is_current_again(store) -> None:
    """The comment above the call gets deleted too, and then the call is back at line 12.

    Identity is positional, so this is the row that was retracted rather than a new one. A
    retraction that could not be undone would leave the graph denying a call the code makes, which
    is the original defect with the sign flipped -- and it would be the same row denying it.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [_site(line=13)])
    store.replace_call_sites("repo-a", [_site(line=12)])

    assert _positions(store) == [("repo-a", "src/billing.ts", 12)]
    assert _positions(store, retracted=True) == [("repo-a", "src/billing.ts", 13)]


def test_retraction_records_the_pass_that_lost_the_call_not_the_latest_one(store) -> None:
    """`retracted_at` answers when the graph stopped seeing a call, so re-stamping would break it.

    A row already retracted is left alone by later passes. Asserting the value is unchanged rather
    than asserting what it is: the fact under test is stability, and the timestamp itself is
    whatever the clock said.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [_site(line=13)])
    first = _retracted_at(store, "src/billing.ts", 12)
    # Two nulls compare equal, so without this the assertion below holds over a store that never
    # retracted anything at all -- stability asserted where there is nothing to be stable.
    assert first is not None

    store.replace_call_sites("repo-a", [_site(line=13)])

    assert _retracted_at(store, "src/billing.ts", 12) == first


def test_a_finding_outlives_the_call_site_it_names_moving(store) -> None:
    """Retraction keeps the record and stops acting on it. Both halves, in one test.

    `finding.call_site_id` is `ON DELETE CASCADE`, so deleting a stale call site deletes what was
    concluded about it -- silently, and `CLAUDE.md` puts what a run concluded among the data this
    system learns routing from. A ghost row is something a reader can notice; a finding that
    vanished is not, which is why the first attempt at this brief traded down rather than up.

    The other half is why deleting was tempting: a finding pointing at a position the code no
    longer has reads as live, and `make_locate` would send an agent to a line that moved. So the
    row stays and stops being open. Nothing acts on it, and it is still there to be asked about.
    """
    stale = store.replace_call_sites("repo-a", [_site(line=12)])[0]
    finding_id = store.insert_finding(Finding(
        id="", detector="vendor_change", claim="response-field", call_site_id=stale,
        vendor_change_id=None, severity="breaking", rationale="PostCharges dropped status",
    ))

    store.replace_call_sites("repo-a", [_site(line=13)])

    assert _findings_in_table(store) == [finding_id]
    assert store.open_findings() == []


def test_replacing_with_the_same_sites_changes_no_identity(store) -> None:
    """Idempotence, which the natural key already gave and the retraction must not take away.

    `graph-grain.md` asks for exactly this assertion: run the stage twice against one fixture and
    check the row count and every row identity are unchanged. The retracted set being empty is the
    other half -- a second pass over an unchanged repository must retract nothing, and one that
    stamped and un-stamped the same rows would pass a row count while making the timestamp mean
    nothing.
    """
    sites = [_site(line=12), _site(line=40, content_hash="h2")]

    first = store.replace_call_sites("repo-a", sites)
    second = store.replace_call_sites("repo-a", sites)

    assert first == second
    assert len(_positions(store)) == 2
    assert _positions(store, retracted=True) == []


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


# --- what reads "current", and what does not --------------------------------------------


def test_a_detector_raises_nothing_against_a_call_site_that_moved(store) -> None:
    """Retraction downstream. Without this the writer is the only thing that changed.

    The same vendor change, the same operation, and the only call site the graph has for it is one
    the last pass stopped finding. A finding here would name a line the code does not have, and
    `make_locate` would work on it.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [])
    store.upsert_vendor_change(_CHANGE)

    findings = list(VendorChangeDetector(store, vendor_id="stripe", repo_id="repo-a").scan())

    assert findings == []


def test_a_retracted_call_site_is_still_readable_by_the_id_a_finding_holds(store) -> None:
    """The other side of that: excluded from what a detector asks, present for a reader.

    A finding raised while the call site was current outlives it, and explaining that finding means
    answering where the call was and when the graph stopped seeing it. `get_call_site` is unfiltered
    for exactly this, and `retracted_at` on the model is how a caller can tell.
    """
    stale = store.replace_call_sites("repo-a", [_site(line=12)])[0]
    store.replace_call_sites("repo-a", [_site(line=13)])

    site = store.get_call_site(stale)

    assert site.line == 12
    assert site.retracted_at is not None


def test_ranking_counts_the_calls_the_code_has_and_not_the_ones_it_had(store) -> None:
    """`call_site_counts` feeds a rank, and a rank over the whole table measures editing.

    One call, moved twice, is one call. Counting rows instead would say three, and would say more
    every time a line is added above it -- ranking the repository that changed most rather than the
    one that calls the vendor most.
    """
    store.replace_call_sites("repo-a", [_site(line=12)])
    store.replace_call_sites("repo-a", [_site(line=13)])
    store.replace_call_sites("repo-a", [_site(line=14)])

    assert store.call_site_counts("repo-a") == {"stripe": 1}


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

"""What a scan may empty, and what it may not.

`GraphStore.truncate_all` empties every table `schema.sql` declares, and a scan called it as
`truncate_all(keep=("call_site",))` -- an allow-list holding one name out of eight, which a
caller had to remember and which no table added afterwards ever joined.

Two of the seven it did not name cannot be rebuilt by anything. `migration_outcome` is the
migration corpus: one row per repair attempt, the only durable record that a pull request was
ever opened, and the table `abandon_reason` lives in, which is what makes "abandoned runs are
data" a rule rather than a wish. `repo_context` is what stays true of a repository while the
code changes underneath it -- and the same scan seeds it eight lines before the truncate and
reads it back a hundred lines after, so the patch agent's prompt carried an empty string with no
error raised anywhere.

Three more are telemetry a scan did not produce and cannot re-produce: `observed_shape`,
`observed_call` and `observed_error_window` each say in their own grain comment that they cannot
be backfilled, because an error tracker's retention is finite and a response nobody kept is
gone.

These drive `sync.cli.run` against a real store rather than a recorder. The truncate is inside
`run()`, and a fake that records the call can only say the call happened -- the question here is
what it did to Postgres.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pytest

from sync.cli import run
from sync.context import SEED_RELATIVE_PATH
from sync.core import (
    CallSite,
    Finding,
    MigrationOutcome,
    ObservedCall,
    ObservedErrorWindow,
    ObservedShape,
    Patch,
    RepoContext,
    RepoRef,
    VendorChange,
)
from sync.graph.store import GraphStore
from sync.signals.registry import PreparedVendor

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SCANNED = "acme/storefront"
"""The repository the run under test scans."""

OTHER = "acme/warehouse"
"""A second repository, so the rows a scan must not reach include rows it has no business
knowing about at all. The database holds every customer at once and a scan is about one."""

CONTEXT_BODY = "Generated clients live under src/generated and are never edited by hand."


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(**over) -> CallSite:
    fields = dict(
        repo_id=SCANNED, path="src/billing.ts", line=1, col=0, vendor_id="stripe",
        # Deliberately not the operation `_change()` names. A scan that raised a finding would
        # enter the remediation graph, which wants a checkpointer, an agent and a forge, and this
        # file is about the truncate rather than about remediation.
        operation_id="PostCharges", symbol="stripe.charges.create",
        sdk_version="18.0.0", content_hash="h1",
    )
    fields.update(over)
    return CallSite(**fields)


def _change(**over) -> VendorChange:
    fields = dict(
        vendor_id="stripe", from_version="v1", to_version="v2",
        kind="response-optional-property-removed", operation_id="PostRefunds",
        path_ptr="/v1/refunds", severity="breaking", source="oasdiff",
        raw={"id": "response-optional-property-removed", "text": "removed `status`"},
    )
    fields.update(over)
    return VendorChange(**fields)


def _outcome(**over) -> MigrationOutcome:
    fields = dict(
        finding_id="f-1", attempt_index=0, site=_site(id="cs-1"), change=_change(id="vc-1"),
        patch=Patch(diff="d", strategy="codemod", rationale="r"),
        tier=0, routing_row="unrouted", wall_ms=12, salt="s1",
    )
    fields.update(over)
    return MigrationOutcome.from_attempt(**fields)


class _StubVendor:
    vendor_id = "stripe"

    def fetch_changes(self, from_version, to_version):
        return [_change()]


class _StubAdapter:
    """The language adapter, reduced to the one call `run()` makes of it before the scan."""

    def matches(self, repo):
        return True

    def index(self, repo):
        return [_site(repo_id=repo.repo_id)]

    def discard_contaminated_dependencies(self, repo):
        return False


@pytest.fixture()
def scan(store, monkeypatch, tmp_path):
    """Run the real `sync.cli.run` against `store`, and return its exit code.

    Everything `run()` reaches outside Postgres is replaced, `http_fetch` included: the
    deprecation halves of a scan download two vendor pages, and a test that reached the network
    would assert on whatever those vendors published today. An empty body parses to no
    deprecations, which is the answer this file wants from them.

    The store is handed in rather than constructed by `run()`, so the assertions read the same
    connection the scan wrote through and the scan uses whatever DSN `conftest` gave this worker.
    """
    import sync.cli as cli

    def fake_clone(url, dest):
        seed = dest / SEED_RELATIVE_PATH
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_text(CONTEXT_BODY, encoding="utf-8")
        return RepoRef(repo_id=SCANNED, url=url, local_path=str(dest), head_sha="0" * 40)

    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(adapter=_StubVendor(), documents=()),
    )
    monkeypatch.setattr(cli, "select_language_adapter", lambda repo, vendor: _StubAdapter())
    monkeypatch.setattr(cli, "_clone", fake_clone)
    monkeypatch.setattr(cli, "http_fetch", lambda url: "")
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)

    args = argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn=DSN,
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )
    return lambda: run(args)


def test_a_scan_does_not_empty_the_migration_corpus(store, scan):
    """The corpus cannot be backfilled: every attempt processed before it existed is lost, and
    every attempt a scan deleted is lost the same way. `BACKLOG.md` notes three or four rows
    after more than a thousand commits, which is what a scan emptying this table looks like."""
    store.record_migration_outcome(_outcome())
    store.record_migration_outcome(_outcome(finding_id="f-2", attempt_index=1))

    assert scan() == 0

    assert {row.finding_id for row in store.migration_outcomes()} == {"f-1", "f-2"}


def test_a_scan_reads_back_the_context_it_seeded(store, scan):
    """The failure `run()`'s own comment claimed was impossible: the row is seeded from the
    checkout before the transaction opens, the truncate empties the table inside it, and the read
    a hundred lines later found nothing. The patch agent's prompt then carried an empty string
    and no stage reported a problem."""
    assert scan() == 0

    found = store.repo_context(SCANNED)
    assert found is not None, "the scan deleted the context it had just seeded"
    assert found.body == CONTEXT_BODY
    assert found.source == "seeded-file"


def test_a_scan_leaves_another_repositorys_context_alone(store, scan):
    """Context is per repository and a scan is about one of them. Wiping the table makes every
    other customer's patch agent run contextless until that repository is scanned again."""
    store.upsert_repo_context(RepoContext(
        repo_id=OTHER, body="Payments are proxied through src/gateway.", source="operator",
    ))

    assert scan() == 0

    found = store.repo_context(OTHER)
    assert found is not None, "a scan of one repository deleted another's context"
    assert found.source == "operator"


def test_a_scan_does_not_empty_observed_telemetry(store, scan):
    """A scan produces none of these three tables and cannot re-produce them. A shape is a
    baseline sample of what a vendor sent, a call is one unit of work that already happened, and
    an error window comes out of a tracker whose retention has already started running."""
    store.record_observed_shape(ObservedShape(
        vendor_id="stripe", operation_id="PostCharges", field_path="/status",
        json_type="string", source="interceptor",
    ))
    store.record_observed_call(ObservedCall(
        repo_id=OTHER, vendor_id="stripe", operation_id="PostCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="POST", trace_id="t1",
        spans={"s1": {"target": "digest", "status": 200, "resend": 0}},
    ))
    now = datetime.now(timezone.utc)
    store.record_observed_error_window(ObservedErrorWindow(
        repo_id=OTHER, vendor_id="stripe", operation_id="PostCharges", binding_rung="observed",
        source="sentry", status_class="4xx", window_start=now - timedelta(days=1),
        window_end=now, error_count=3, issue_count=1,
    ))

    assert scan() == 0

    assert len(store.observed_shapes("stripe", "PostCharges")) == 1
    assert store.observed_calls_count(OTHER) == 1
    assert store.observed_error_windows_count(OTHER) == 1


def test_a_scan_still_clears_what_it_re_derives(store, scan):
    """The other direction, and without it every assertion above passes against a scan that
    simply stopped clearing anything.

    A stale finding is indistinguishable from a live one to everything downstream -- it names a
    detector, a call site and a claim, and nothing on the row says which run put it there. A
    stale vendor change is worse: it does not converge, because `oasdiff breaking` returns a
    different answer on successive runs over identical bytes, so leaving it would accumulate
    rather than reconverge. Both tables go, and both are named by the method that empties them.
    """
    stale_site = store.replace_call_sites(OTHER, [_site(repo_id=OTHER, path="src/pay.ts")])[0]
    store.upsert_vendor_change(_change(operation_id="PostPayouts"))
    store.insert_finding(Finding(
        id="", detector="vendor_change", claim="response-field", call_site_id=stale_site,
        vendor_change_id=None, severity="breaking", rationale="stale",
        binding_rung="static",
    ))
    assert store.open_findings() != []

    assert scan() == 0

    assert store.open_findings() == []
    # Only what this scan upserted. `_StubVendor` yields the one change `_change()` builds.
    assert [c.operation_id for c in store.all_vendor_changes("stripe")] == ["PostRefunds"]


def test_a_scan_records_the_pass_it_just_ran(store, scan):
    """Decision 41's durable half, written by the thing that actually indexes.

    A toast announcing "Index finished, 1,204 call sites" must not be the only place that fact
    exists. Without this the Overview can say rows exist and cannot say a pass completed, which
    is the difference between a count worth trusting and one left by a run that died.
    """
    assert scan() == 0

    run = store.latest_index_run(SCANNED)

    assert run is not None, "a completed scan left no index_run row"
    assert run["finished_at"] is not None, "the pass finished but the row does not say so"
    assert run["call_sites"] == len(store.call_sites_for_repository(SCANNED))

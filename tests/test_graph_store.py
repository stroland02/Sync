import os
import threading
from datetime import datetime, timezone

import psycopg
import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, ObservedShape, VendorChange
from sync.core.models import SEVERITY_ORDER
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SEEN = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def fetch_counts(monkeypatch):
    """How many rows crossed the wire on each `fetchall()`, independent of what a caller's
    Python goes on to do with them afterwards -- slicing a result after it already arrived
    does not change how many rows arrived. This is what makes "rows read" a different
    measurement from "rows returned": a page carved out of an unbounded fetch in Python
    returns a short list while this still records the long one, which is the divergence a
    real SQL `LIMIT` is supposed to close.
    """
    counts: list[int] = []
    real_fetchall = psycopg.Cursor.fetchall

    def counting_fetchall(self):
        result = real_fetchall(self)
        counts.append(len(result))
        return result

    monkeypatch.setattr(psycopg.Cursor, "fetchall", counting_fetchall)
    return counts


def _execute_count(monkeypatch):
    """How many round trips a read made -- the metric that proves an N+1 join collapsed to
    one query rather than merely getting fast enough not to notice.
    """
    import sync.graph.store as store_module

    calls: list[str] = []
    real_execute = store_module.psycopg.Connection.execute

    def counting_execute(self, query, *args, **kwargs):
        calls.append(query)
        return real_execute(self, query, *args, **kwargs)

    monkeypatch.setattr(store_module.psycopg.Connection, "execute", counting_execute)
    return calls


def test_many_calls_open_one_connection(monkeypatch):
    """Every public method used to call `_connect()`, so the acceptance run's
    2,896 vendor changes cost 2,896 connect/authenticate/close cycles. The
    count is the assertion because it is the thing that regresses: a new
    method that opens its own connection reads correctly and is silently
    2,896 handshakes slower again.
    """
    import sync.graph.store as store_module

    real_connect = store_module.psycopg.connect
    connects = 0

    def counting_connect(*args, **kwargs):
        nonlocal connects
        connects += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(store_module.psycopg, "connect", counting_connect)

    s = GraphStore(DSN)
    s.apply_schema()
    s.upsert_call_site(_site())
    s.upsert_call_site(_site(line=99, col=2, content_hash="hash-99"))
    s.call_sites_for_operation("stripe", "PostCharges")
    s.all_vendor_changes("stripe")

    assert connects == 1


def test_a_closed_connection_is_replaced_and_the_query_answers_with_real_rows(store):
    """B117: the API holds one store for the process lifetime, so a connection that died
    must be replaced on the next call -- and replaced rather than swallowed: the row written
    before the drop comes back, not an empty result wearing the outage's name.
    """
    store.upsert_call_site(_site())
    store._connect().close()

    sites = store.call_sites_for_operation("stripe", "PostCharges")

    assert len(sites) == 1
    assert sites[0].symbol == "stripe.charges.create"
    # The store stays usable, not merely un-broken for one call.
    assert store.call_sites_for_operation_count("stripe", "PostCharges") == 1


def test_a_connection_lost_under_an_open_transaction_raises_rather_than_reconnecting(store):
    """A reconnect inside `transaction()` would hand later writes to a fresh autocommit
    connection while the block's own transaction dies with the old one -- a failed write
    turned into a silently partial one. The honest behaviour is to raise, and to leave
    nothing from the failed block committed.
    """
    store.upsert_call_site(_site())

    with pytest.raises(psycopg.OperationalError):
        with store.transaction():
            store._connect().close()
            store.upsert_call_site(_site(line=99, col=2, content_hash="hash-99"))

    # Nothing from the failed block reached the database; the store recovered afterwards.
    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert [s.line for s in sites] == [42]


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
    store.upsert_call_site(_site(content_hash="hash-2", response_fields_read=["status", "id"]))
    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert len(sites) == 1
    assert sites[0].response_fields_read == ["status", "id"]


def test_two_call_sites_differing_only_in_line_upsert_to_two_rows(store):
    store.upsert_call_site(
        _site(line=10, col=4, response_fields_read=["charges_enabled"], content_hash="hash-a")
    )
    store.upsert_call_site(
        _site(line=40, col=4, response_fields_read=["requirements"], content_hash="hash-b")
    )
    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert len(sites) == 2
    by_line = {s.line: s for s in sites}
    assert by_line[10].response_fields_read == ["charges_enabled"]
    assert by_line[40].response_fields_read == ["requirements"]


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
            claim="response-field",
            call_site_id=site_id,
            vendor_change_id=change_id,
            severity="breaking",
            rationale="status removed",
            # What `VendorChangeDetector` itself attributes, rather than a value chosen to satisfy
            # the write: a wrong static binding is what would make this claim wrong.
            binding_rung="static",
        )
    )
    assert len(store.open_findings()) == 1
    store.set_finding_status(finding_id, "abandoned")
    assert store.open_findings() == []
    assert store.get_call_site(site_id).symbol == "stripe.charges.create"
    assert store.get_vendor_change(change_id).kind == "response-property-removed"


def _change(**kw) -> VendorChange:
    base = dict(
        vendor_id="stripe",
        from_version="v2300",
        to_version="v2345",
        kind="response-property-removed",
        operation_id="GetCharges",
        path_ptr="/paths/~1v1~1charges",
        severity="breaking",
        source="oasdiff",
        raw={"text": "removed the optional property `error/payment_intent/customer` from the response"},
    )
    base.update(kw)
    return VendorChange(**base)


def test_upsert_vendor_change_distinguishes_by_operation_id(store):
    first = store.upsert_vendor_change(_change(operation_id="GetCharges"))
    second = store.upsert_vendor_change(_change(operation_id="PostCharges"))
    assert first != second
    assert len(store.all_vendor_changes("stripe")) == 2


def test_upsert_vendor_change_distinguishes_by_raw_text(store):
    first = store.upsert_vendor_change(
        _change(raw={"text": "removed the optional property `customer` from the response"})
    )
    second = store.upsert_vendor_change(
        _change(raw={"text": "removed the optional property `payment_method` from the response"})
    )
    assert first != second
    assert len(store.all_vendor_changes("stripe")) == 2


def test_upsert_vendor_change_is_idempotent_on_identical_content(store):
    first = store.upsert_vendor_change(_change())
    second = store.upsert_vendor_change(_change())
    assert first == second
    assert len(store.all_vendor_changes("stripe")) == 1


def test_upsert_vendor_change_does_not_corrupt_raw_across_operations(store):
    a_id = store.upsert_vendor_change(
        _change(
            operation_id="GetCharges",
            raw={"text": "removed the optional property `customer` from the response"},
        )
    )
    b_id = store.upsert_vendor_change(
        _change(
            operation_id="PostCharges",
            raw={"text": "removed the optional property `payment_method` from the response"},
        )
    )
    a = store.get_vendor_change(a_id)
    b = store.get_vendor_change(b_id)
    assert a.operation_id == "GetCharges"
    assert a.raw["text"] == "removed the optional property `customer` from the response"
    assert b.operation_id == "PostCharges"
    assert b.raw["text"] == "removed the optional property `payment_method` from the response"


def test_a_transaction_that_returns_commits_its_rows(store):
    with store.transaction():
        store.upsert_call_site(_site())
    assert len(store.call_sites_for_operation("stripe", "PostCharges")) == 1


def test_a_failure_inside_a_transaction_writes_no_rows(store):
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.upsert_call_site(_site())
            store.upsert_vendor_change(_change())
            raise RuntimeError("ingest died halfway")

    assert store.call_sites_for_operation("stripe", "PostCharges") == []
    assert store.all_vendor_changes("stripe") == []


def test_a_failure_after_a_truncate_restores_the_previous_graph(store):
    """`cli.run` truncates and re-ingests inside one transaction, so the graph
    a crash leaves behind is the *previous* run's, complete, rather than an
    empty or half-filled one. TRUNCATE rolling back is what makes that hold,
    and it is a Postgres-specific property worth pinning rather than assuming.
    """
    store.upsert_call_site(_site())

    with pytest.raises(RuntimeError):
        with store.transaction():
            store.truncate_all()
            store.upsert_call_site(_site(path="src/new.ts", content_hash="hash-new"))
            raise RuntimeError("ingest died halfway")

    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert [s.path for s in sites] == ["src/billing.ts"]


def test_a_second_thread_sharing_the_store_is_swept_into_the_open_transaction(store):
    """The transaction belongs to the store's connection, not to the caller
    that opened it. A write issued through the same store from another thread
    is inside the block whether or not it means to be, and disappears when the
    block rolls back -- silently, since nothing raises. This is the boundary
    `cli.run` stays inside by being single-threaded, and the one M1's fan-out
    across findings has to respect by giving each branch its own store.
    """
    opened, wrote = threading.Event(), threading.Event()

    def other_thread():
        assert opened.wait(10)
        store.upsert_call_site(_site(path="src/other-thread.ts", content_hash="hash-other"))
        wrote.set()

    worker = threading.Thread(target=other_thread)
    worker.start()
    try:
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.upsert_call_site(_site())
                opened.set()
                assert wrote.wait(10)
                raise RuntimeError("ingest died halfway")
    finally:
        worker.join(10)

    assert store.call_sites_for_operation("stripe", "PostCharges") == []


def test_a_reader_on_another_connection_waits_out_the_ingest(store):
    """It does not read the previous graph while the ingest runs: TRUNCATE
    holds ACCESS EXCLUSIVE until the block returns, so a concurrent reader
    blocks for the whole ingest and then reads whatever committed. `lock_timeout`
    turns that wait into an error the test can assert on; without it the read
    would simply hang until the ingest finished.
    """
    store.upsert_call_site(_site())

    reader = psycopg.connect(DSN, autocommit=True)
    reader.execute("SET lock_timeout = '250ms'")
    try:
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with store.transaction():
                store.truncate_all()
                store.upsert_call_site(_site(path="src/new.ts", content_hash="hash-new"))
                reader.execute("SELECT count(*) FROM call_site").fetchone()
    finally:
        reader.close()

    assert [s.path for s in store.call_sites_for_operation("stripe", "PostCharges")] == ["src/billing.ts"]


def test_get_call_site_round_trips_the_id_the_upsert_returned(store):
    """`VendorChangeDetector` builds a `Finding` from `call_site.id` and
    `cli.run` hands that id to the remediation graph, which reads the site back
    by it. Nothing else in the suite asserts the id survives the round trip.
    """
    site_id = store.upsert_call_site(_site())
    assert store.get_call_site(site_id).id == site_id


def test_get_vendor_change_round_trips_the_id_the_upsert_returned(store):
    change_id = store.upsert_vendor_change(_change())
    assert store.get_vendor_change(change_id).id == change_id


def test_get_call_site_raises_key_error_for_an_unknown_id(store):
    with pytest.raises(KeyError):
        store.get_call_site("no-such-call-site")


def test_get_vendor_change_raises_key_error_for_an_unknown_id(store):
    with pytest.raises(KeyError):
        store.get_vendor_change("no-such-vendor-change")


def test_loop_depth_survives_the_round_trip(store):
    """The column exists so a detector can ask for shape without re-indexing. A value that
    reaches the row and not the query is the same as no column at all.
    """
    site = _site()
    site = site.model_copy(update={"loop_depth": 2})
    site_id = store.upsert_call_site(site)

    with store._connect().cursor() as cur:
        cur.execute("SELECT loop_depth FROM call_site WHERE id = %s", (site_id,))
        assert cur.fetchone()["loop_depth"] == 2


def test_reindexing_a_call_that_moved_into_a_loop_updates_its_depth(store):
    """Wrapping an existing call in a `for` changes its shape without changing its identity,
    and a stale zero would tell a detector the opposite of what the code now does.
    """
    site = _site()
    store.upsert_call_site(site)
    store.upsert_call_site(site.model_copy(update={"loop_depth": 1}))

    with store._connect().cursor() as cur:
        cur.execute("SELECT loop_depth FROM call_site WHERE repo_id = %s", (site.repo_id,))
        assert [row["loop_depth"] for row in cur.fetchall()] == [1]


def test_two_claims_about_one_call_site_are_two_rows(store):
    """The natural key, and the column that was missing from it.

    A finding's id is derived from `(detector, call_site_id, vendor_change_id, claim)` and the
    insert is ON CONFLICT DO NOTHING, so anything the key cannot tell apart is one row and the
    loser is discarded without an error. Before `claim` joined the key, one detector saying two
    things about one call site stored whichever it emitted first.
    """
    site_id = store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="GetCharges", symbol="stripe.charges.list", args_keys=["limit"],
            response_fields_read=["data"], sdk_version="18.0.0", content_hash="h",
        )
    )

    # `EfficiencyDetector` carries the correlator's own rung, which is `observed` when the spans
    # correlated and `unresolved` when they did not. These two fixtures are about the identity of a
    # row rather than about attribution, so they take the correlated case -- the one a finding with
    # a call count behind it actually has. The rung is not in the finding's key, and
    # `test_finding_rung.py` is where that is asserted.
    loop = store.insert_finding(
        Finding(
            detector="efficiency", call_site_id=site_id, claim="loop",
            severity="info", rationale="called 40 times in one unit of work",
            binding_rung="observed",
        )
    )
    cached = store.insert_finding(
        Finding(
            detector="efficiency", call_site_id=site_id, claim="uncached-repeat",
            severity="info", rationale="the same request was made 40 times",
            binding_rung="observed",
        )
    )

    assert loop != cached
    assert len(store.open_findings()) == 2


def test_the_same_claim_inserted_twice_converges_on_one_row(store):
    """DETECT is a pipeline stage, so re-running it must converge rather than accumulate.

    The mirror of the test above, and the reason `claim` may not carry a live count: a
    discriminator derived from the rationale would make two runs over an unchanged graph
    produce two ids and a fresh row every time. That trades a silent loss for a silent
    duplication, which is the same bug wearing the opposite sign.
    """
    site_id = store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="GetCharges", symbol="stripe.charges.list", args_keys=["limit"],
            response_fields_read=["data"], sdk_version="18.0.0", content_hash="h",
        )
    )

    def emit() -> str:
        return store.insert_finding(
            Finding(
                detector="efficiency", call_site_id=site_id, claim="loop",
                severity="info", rationale="called 40 times in one unit of work",
                binding_rung="observed",
            )
        )

    assert emit() == emit()
    assert len(store.open_findings()) == 1


_HOUR_14 = datetime(2026, 7, 20, 14, tzinfo=timezone.utc)
_HOUR_15 = datetime(2026, 7, 20, 15, tzinfo=timezone.utc)
_HOUR_16 = datetime(2026, 7, 20, 16, tzinfo=timezone.utc)


def _error_window(**over) -> ObservedErrorWindow:
    base = dict(
        repo_id="r1", vendor_id="stripe", operation_id="PostCharges",
        binding_rung="observed", source="error-tracker-group", status_class="5xx",
        window_start=_HOUR_14, window_end=_HOUR_15,
        error_count=8, issue_count=1,
    )
    base.update(over)
    return ObservedErrorWindow(**base)


def test_a_window_rewritten_under_a_better_rung_carries_the_new_one(store):
    """`binding_rung` is outside the natural key so that a correlator which improves converges on
    the row it already wrote instead of adding a second one that double-counts the window. The
    conflict clause therefore has to carry the rung forward, and until now nothing proved it did.

    No ingest-level test can: the writer's rung is a module constant, so every row an export
    produces carries the same one and the assignment could have been deleted with the suite still
    green. The rung has to change here, at the store, or it never changes at all.
    """
    store.record_observed_error_window(_error_window(binding_rung="unresolved"))
    store.record_observed_error_window(_error_window(binding_rung="observed"))

    rows = store.observed_error_windows("r1")
    assert [row.binding_rung for row in rows] == ["observed"], "one row, under the newer rung"


def test_a_removal_does_not_reach_another_source_in_the_same_window(store):
    """`source` is in the natural key because two sources are two samples of the same failures,
    and a removal that ignored it would destroy the second sample the moment either one re-ran.

    An error tracker's grouping and a span-derived count disagreeing about one operation is
    information about the correlator; with one of them deleted there is nothing to disagree
    with, and nothing in the graph records that there ever was.
    """
    store.record_observed_error_window(_error_window())
    store.record_observed_error_window(_error_window(source="span-derived"))

    store.remove_observed_error_windows_outside(
        "r1", "stripe", "error-tracker-group", _HOUR_14, _HOUR_15, ()
    )

    assert [row.source for row in store.observed_error_windows("r1")] == ["span-derived"]


def test_a_removal_does_not_reach_the_window_beside_the_one_it_was_given(store):
    """The bounds are the ones the caller wrote, never every window for the repository. An
    earlier or later period is a separate observation that this ingest does not contradict, and
    comparing one window against another is the only thing these rows support unaided -- so a
    removal reaching past its own bounds deletes the series it exists to build.

    The two rows carry the same `(operation_id, status_class)` deliberately. Anything narrower
    would survive on its key alone and prove nothing about the bounds.
    """
    store.record_observed_error_window(_error_window())
    store.record_observed_error_window(
        _error_window(window_start=_HOUR_15, window_end=_HOUR_16)
    )

    store.remove_observed_error_windows_outside(
        "r1", "stripe", "error-tracker-group", _HOUR_14, _HOUR_15, ()
    )

    rows = store.observed_error_windows("r1")
    assert [(row.window_start, row.window_end) for row in rows] == [(_HOUR_15, _HOUR_16)]


def test_repo_ids_lists_every_repository_the_index_has_seen(store):
    """`repo_ids` is `DISTINCT repo_id` over `call_site`, which is what makes it see a
    repository even when every one of its findings has closed -- `open_findings` cannot,
    because it filters on finding status and joins away nothing about the repository itself.
    """
    store.upsert_call_site(_site(repo_id="r-a"))
    store.upsert_call_site(_site(repo_id="r-b", path="src/sms.ts", content_hash="hash-b"))
    store.upsert_call_site(_site(repo_id="r-a", path="src/other.ts", content_hash="hash-c"))

    assert store.repo_ids() == ["r-a", "r-b"]


def test_repo_ids_of_an_empty_graph_is_empty_not_an_error(store):
    assert store.repo_ids() == []


def test_call_site_coverage_pairs_each_vendors_count_with_its_own_timestamp(store):
    """A positional zip of two independently-ordered result sets would silently swap a count
    and a timestamp between vendors. Seeded so count-rank and timestamp-rank are inverted --
    stripe has the most call sites and the oldest timestamp, twilio has the fewest and the
    newest -- so a positional-zip bug fails instead of coincidentally lining up.
    """
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts", line=1, content_hash="hash-a"))
    store.upsert_call_site(_site(vendor_id="stripe", path="src/b.ts", line=2, content_hash="hash-b"))
    newer_id = store.upsert_call_site(
        _site(vendor_id="twilio", operation_id="SendSms", path="src/c.ts", line=3, content_hash="hash-c")
    )
    with store._connect().cursor() as cur:
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE vendor_id = 'stripe'",
            (datetime(2020, 1, 1, tzinfo=timezone.utc),),
        )
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2030, 1, 1, tzinfo=timezone.utc), newer_id),
        )

    coverage = store.call_site_coverage("r1")

    assert coverage["stripe"] == (2, datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert coverage["twilio"] == (1, datetime(2030, 1, 1, tzinfo=timezone.utc))


def test_service_coverage_groups_one_vendors_operations_into_its_products(store):
    """A vendor is the provider; a service is one of the APIs it sells. Seeded so one provider
    carries two products, which is the case a per-vendor query cannot answer and the case that
    makes the console's Services screen a different list from its Vendors screen.
    """
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="PostCharges", service_id="Payments",
              path="src/a.ts", line=1, content_hash="hash-a")
    )
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="GetCharge", service_id="Payments",
              path="src/b.ts", line=2, content_hash="hash-b")
    )
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="PostSubscriptions", service_id="Billing",
              path="src/c.ts", line=3, content_hash="hash-c")
    )

    rows = {(row["vendor_id"], row["service_id"]): row for row in store.service_coverage("r1")}

    assert rows[("stripe", "Payments")]["sites"] == 2
    assert rows[("stripe", "Payments")]["operations"] == 2
    assert rows[("stripe", "Billing")]["sites"] == 1


def test_service_coverage_keeps_an_ungrouped_operation_as_a_null_group(store):
    """No adapter maps an operation onto a product yet, so most real rows are ungrouped. Dropping
    them would report a vendor as selling no APIs when what it has is no adapter -- the absence of
    a mapping is the fact, and a query that filters it out cannot report it.
    """
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="PostCharges", service_id="Payments",
              path="src/a.ts", line=1, content_hash="hash-a")
    )
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="PostRefunds", path="src/b.ts", line=2,
              content_hash="hash-b")
    )

    grouped = {row["service_id"]: row["sites"] for row in store.service_coverage("r1")}

    assert grouped == {"Payments": 1, None: 1}


def test_service_coverage_excludes_a_retracted_call_site(store):
    """The same rule `call_site_coverage` keeps: a call the last pass stopped finding is not part
    of what the repository currently has, so it contributes to no product's count.
    """
    store.upsert_call_site(
        _site(vendor_id="stripe", operation_id="PostCharges", service_id="Payments",
              path="src/a.ts", line=1, content_hash="hash-a")
    )
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE repo_id = 'r1'")

    assert store.service_coverage("r1") == []


def test_call_site_coverage_a_vendor_with_no_call_sites_is_absent(store):
    store.upsert_call_site(_site(vendor_id="stripe"))

    coverage = store.call_site_coverage("r1")

    assert "twilio" not in coverage


def test_call_site_coverage_of_an_unindexed_repository_is_empty(store):
    assert store.call_site_coverage("never-indexed") == {}


def test_call_site_coverage_excludes_a_retracted_rows_count_and_timestamp(store):
    """A retracted row must contribute neither a count nor a timestamp. The retracted row's
    timestamp is set far in the future and the survivor's far in the past, so a leak into
    either the count or the timestamp is unmistakable.
    """
    surviving_id = store.upsert_call_site(
        _site(path="src/a.ts", line=1, content_hash="hash-a")
    )
    retracted_id = store.upsert_call_site(
        _site(path="src/b.ts", line=2, content_hash="hash-b")
    )
    with store._connect().cursor() as cur:
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2020, 1, 1, tzinfo=timezone.utc), surviving_id),
        )
        cur.execute(
            "UPDATE call_site SET indexed_at = %s, retracted_at = now() WHERE id = %s",
            (datetime(2099, 1, 1, tzinfo=timezone.utc), retracted_id),
        )

    coverage = store.call_site_coverage("r1")

    assert coverage["stripe"] == (1, datetime(2020, 1, 1, tzinfo=timezone.utc))


# -- pagination reaches the store: a real SQL LIMIT, not a Python slice -----------------------
#
# Every test below asserts on *rows returned* (the list length, which a Python slice would
# also satisfy) and on *rows read* (`fetch_counts`, which only a real `LIMIT` keeps small).
# A test that checked returned length alone would pass unchanged against the Python-slice
# implementation these methods replace -- CLAUDE.md's own words for that: "a test that has
# never failed has never been shown to test anything."


def test_call_sites_for_operation_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))

    sites = store.call_sites_for_operation("stripe", "PostCharges", limit=2, offset=0)

    assert len(sites) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_call_sites_for_operation_paginates_past_the_first_page(store):
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))

    first = store.call_sites_for_operation("stripe", "PostCharges", limit=2, offset=0)
    second = store.call_sites_for_operation("stripe", "PostCharges", limit=2, offset=2)

    assert [s.path for s in first] == ["src/0.ts", "src/1.ts"]
    assert [s.path for s in second] == ["src/2.ts", "src/3.ts"]


def test_call_sites_for_operation_with_no_limit_returns_every_row(store):
    """Every existing caller -- three detectors and `binding_surface` -- calls this with no
    `limit` at all and must keep getting everything, unbounded, exactly as before.
    """
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))

    assert len(store.call_sites_for_operation("stripe", "PostCharges")) == 5


def test_call_sites_for_operation_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))

    assert store.call_sites_for_operation_count("stripe", "PostCharges") == 5
    assert len(store.call_sites_for_operation("stripe", "PostCharges", limit=2)) == 2


def _sites_at(store, paths: list[str]) -> None:
    for i, path in enumerate(paths):
        store.upsert_call_site(_site(path=path, line=i + 1, content_hash=f"hash-{i}"))


def test_the_common_directory_is_the_deepest_one_every_call_site_shares(store):
    """The prefix the binding surface factors out of its path column.

    It is a property of the filtered set rather than of a page, computed in SQL, because a prefix
    computed over fifty rows would make the same call site render differently on page one and page
    two -- the column's meaning would depend on the window, which is the class of claim this console
    exists to remove.
    """
    _sites_at(store, [
        "packages/billing/src/adapters/stripe/charges/create.ts",
        "packages/billing/src/adapters/stripe/charges/refund.ts",
    ])

    assert store.call_sites_common_directory("stripe", "PostCharges") == (
        "packages/billing/src/adapters/stripe/charges/"
    )


def test_the_common_directory_never_cuts_a_path_segment_in_half(store):
    """`create-a.ts` and `create-b.ts` share the characters `create-`, and a prefix that stopped
    there would name a directory that does not exist and leave a remainder no reader could rejoin.
    The answer is the last `/`, not the last matching character.
    """
    _sites_at(store, [
        "packages/billing/charges/create-a.ts",
        "packages/billing/charges/create-b.ts",
    ])

    assert store.call_sites_common_directory("stripe", "PostCharges") == (
        "packages/billing/charges/"
    )


def test_the_common_directory_is_empty_when_two_call_sites_share_no_directory(store):
    """A customer calling one operation from two trees has no shared prefix, and the honest answer
    is nothing to factor out -- not the first directory of whichever row sorted first.
    """
    _sites_at(store, ["packages/billing/charge.ts", "services/orders/send.ts"])

    assert store.call_sites_common_directory("stripe", "PostCharges") == ""


def test_a_single_call_site_reports_its_own_directory(store):
    """One row shares its whole directory with itself. Reporting the filename too would factor out
    the only part of the path that distinguishes anything, which is the failure the segment rule
    above prevents in general.
    """
    _sites_at(store, ["packages/billing/src/charge.ts"])

    assert store.call_sites_common_directory("stripe", "PostCharges") == "packages/billing/src/"


def test_the_common_directory_is_empty_when_there_are_no_call_sites(store):
    assert store.call_sites_common_directory("stripe", "PostCharges") == ""


def test_the_common_directory_moves_with_the_path_filter(store):
    """It narrows with the same predicate the page does. A prefix drawn from the unfiltered set
    would be shorter than the one the visible rows actually share, so the column would keep
    repeating characters the filter had already established.
    """
    _sites_at(store, [
        "packages/billing/charges/create.ts",
        "packages/billing/refunds/create.ts",
    ])

    assert store.call_sites_common_directory("stripe", "PostCharges") == "packages/billing/"
    assert store.call_sites_common_directory(
        "stripe", "PostCharges", path_prefix="packages/billing/charges"
    ) == "packages/billing/charges/"


def test_the_common_directory_ignores_a_retracted_call_site(store):
    """The same exclusion every other read of this relation makes. A retracted row shortening the
    prefix would make the visible rows repeat a directory none of them needed to.
    """
    keeper = _site(path="packages/billing/charges/create.ts", line=1, content_hash="hash-keep")
    store.upsert_call_site(keeper)
    store.upsert_call_site(_site(path="services/orders/send.ts", line=9, content_hash="hash-gone"))
    # `replace_call_sites` stamps `retracted_at` on every current row it is not handed, which is
    # how a pass that no longer finds a call site records the loss. Both rows are live before this
    # and share no directory at all, so a prefix that counted the retracted one would be empty.
    store.replace_call_sites("r1", [keeper])

    assert store.call_sites_common_directory("stripe", "PostCharges") == (
        "packages/billing/charges/"
    )


def test_vendor_changes_for_operation_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(4):
        store.upsert_vendor_change(_change(operation_id="PostCharges", raw={"text": f"t{i}"}))

    changes = store.vendor_changes_for_operation("stripe", "PostCharges", limit=1, offset=0)

    assert len(changes) == 1, "rows returned"
    assert fetch_counts[-1] == 1, "rows read off the wire"


def test_vendor_changes_for_operation_count_matches_the_filter_not_the_page(store):
    for i in range(4):
        store.upsert_vendor_change(_change(operation_id="PostCharges", raw={"text": f"t{i}"}))

    assert store.vendor_changes_for_operation_count("stripe", "PostCharges") == 4
    assert len(store.vendor_changes_for_operation("stripe", "PostCharges", limit=1)) == 1


def test_vendor_changes_for_operation_excludes_a_different_operation(store):
    """A sibling of `all_vendor_changes`, not a parameter on it: that method's exact
    `(self, vendor_id)` signature is pinned by `sync.mcp.tools.GraphReader`'s structural
    protocol, so `binding_surface`'s operation scoping has to be its own query.
    """
    store.upsert_vendor_change(_change(operation_id="PostCharges"))
    store.upsert_vendor_change(_change(operation_id="PostRefunds"))

    scoped = store.vendor_changes_for_operation("stripe", "PostCharges")

    assert [c.operation_id for c in scoped] == ["PostCharges"]
    assert store.vendor_changes_for_operation_count("stripe", "PostCharges") == 1
    assert store.all_vendor_changes("stripe")  # the wide method is unaffected and still works
    assert len(store.all_vendor_changes("stripe")) == 2


def test_observed_calls_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        store.record_observed_call(_observed_call(trace_id=f"t{i}"))

    calls = store.observed_calls("r1", limit=2, offset=0)

    assert len(calls) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_observed_calls_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        store.record_observed_call(_observed_call(trace_id=f"t{i}"))

    assert store.observed_calls_count("r1") == 5
    assert len(store.observed_calls("r1", limit=2)) == 2


def test_observed_error_windows_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        store.record_observed_error_window(_error_window(status_class=f"{i}xx"))

    windows = store.observed_error_windows("r1", limit=2, offset=0)

    assert len(windows) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_observed_error_windows_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        store.record_observed_error_window(_error_window(status_class=f"{i}xx"))

    assert store.observed_error_windows_count("r1") == 5
    assert len(store.observed_error_windows("r1", limit=2)) == 2


def _finding_for_open(site_id: str, **kw) -> Finding:
    base = dict(
        detector="vendor-change", claim="response-field", call_site_id=site_id,
        severity="breaking", rationale="status removed", binding_rung="static",
    )
    base.update(kw)
    return Finding(**base)


def test_open_findings_page_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    findings = store.open_findings_page(limit=2, offset=0)

    assert len(findings) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_open_findings_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    assert store.open_findings_count() == 5
    assert len(store.open_findings_page(limit=2)) == 2
    assert len(store.open_findings()) == 5  # the unpaginated method is unaffected


def test_open_findings_count_excludes_a_retracted_call_sites_finding(store):
    """The count must agree with the join `open_findings` itself reads through, not just
    with `finding.status` -- a retracted call site's finding is invisible to both or neither.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (site_id,))

    assert store.open_findings_count() == 0
    assert store.open_findings() == []


# -- the overview's total is a bounded SQL count, not a Python min() over an exact one ---------


def test_open_findings_count_bounded_reports_the_bound_once_the_true_count_exceeds_it(store):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    assert store.open_findings_count_bounded(3) == (3, True)


def test_open_findings_count_bounded_reports_the_true_count_when_under_the_bound(store):
    for i in range(3):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    assert store.open_findings_count_bounded(10) == (3, False)


def test_open_findings_count_bounded_the_bound_reaches_postgres_as_a_real_limit(store, monkeypatch):
    """A `count(*)` over an *unbounded* subquery followed by `min(n, bound)` in Python returns
    the same two numbers this method does for every case above -- the only way to tell that
    implementation apart from Sentry's `count_hits` pattern is to prove the query sent to
    Postgres actually carries the `LIMIT` that stops the scan at `bound`, which is what keeps
    this cheap at ten thousand matching rows rather than merely returning the right answer once
    it has already paid to look at all ten thousand.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id))
    calls = _execute_count(monkeypatch)

    store.open_findings_count_bounded(1)

    assert any("LIMIT" in query for query in calls), "the bound must reach Postgres as a real LIMIT"


def test_open_findings_count_bounded_excludes_a_retracted_call_sites_finding(store):
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (site_id,))

    assert store.open_findings_count_bounded(10) == (0, False)


# -- the vendor and severity distributions are real GROUP BYs, never a page tallied in Python --


def test_open_findings_vendor_counts_tallies_by_vendor(store):
    stripe_a = store.upsert_call_site(_site(path="src/a.ts", line=1, vendor_id="stripe"))
    stripe_b = store.upsert_call_site(_site(path="src/b.ts", line=2, vendor_id="stripe"))
    shopify = store.upsert_call_site(
        _site(path="src/c.ts", line=3, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding_for_open(stripe_a, claim="c1"))
    store.insert_finding(_finding_for_open(stripe_b, claim="c2"))
    store.insert_finding(_finding_for_open(shopify, claim="c3"))

    assert store.open_findings_vendor_counts() == {"shopify": 1, "stripe": 2}


def test_open_findings_vendor_counts_is_one_query_regardless_of_finding_count(store, monkeypatch):
    """The defect this replaces read every open finding into Python and tallied vendors in a
    loop, which materialised a row per finding to answer a question whose cardinality is the
    number of vendors, not the number of findings. Ten findings against one vendor must cost the
    same one query as one finding does.
    """
    for i in range(10):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    calls = _execute_count(monkeypatch)
    counts = store.open_findings_vendor_counts()

    assert counts == {"stripe": 10}
    assert len(calls) == 1, f"expected one query for ten findings, made {len(calls)}"


def test_open_findings_vendor_counts_excludes_a_retracted_call_sites_finding(store):
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (site_id,))

    assert store.open_findings_vendor_counts() == {}


def test_open_findings_severity_counts_tallies_by_severity(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    site_c = store.upsert_call_site(_site(path="src/c.ts", line=3))
    store.insert_finding(_finding_for_open(site_a, claim="c1", severity="breaking"))
    store.insert_finding(_finding_for_open(site_b, claim="c2", severity="breaking"))
    store.insert_finding(_finding_for_open(site_c, claim="c3", severity="warning"))

    assert store.open_findings_severity_counts() == {"breaking": 2, "warning": 1}


def test_open_findings_severity_counts_of_an_empty_graph_is_empty(store):
    assert store.open_findings_severity_counts() == {}


# -- one snapshot of the fleet-wide indexed_at and shared binding rung -------------------------


def test_open_findings_summary_reports_the_newest_indexed_at_among_open_findings(store):
    older = store.upsert_call_site(_site(path="src/a.ts", line=1))
    newer = store.upsert_call_site(_site(path="src/b.ts", line=2))
    with store._connect().cursor() as cur:
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2020, 1, 1, tzinfo=timezone.utc), older),
        )
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2030, 1, 1, tzinfo=timezone.utc), newer),
        )
    store.insert_finding(_finding_for_open(older, claim="c1"))
    store.insert_finding(_finding_for_open(newer, claim="c2"))

    summary = store.open_findings_summary()

    assert summary["indexed_at"] == datetime(2030, 1, 1, tzinfo=timezone.utc)


def test_open_findings_summary_binding_rung_is_none_when_findings_disagree(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(site_a, claim="c1", binding_rung="static"))
    store.insert_finding(_finding_for_open(site_b, claim="c2", binding_rung="observed"))

    assert store.open_findings_summary()["binding_rung"] is None


def test_open_findings_summary_binding_rung_is_the_shared_rung_when_every_finding_agrees(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(site_a, claim="c1", binding_rung="observed"))
    store.insert_finding(_finding_for_open(site_b, claim="c2", binding_rung="observed"))

    assert store.open_findings_summary()["binding_rung"] == "observed"


def test_open_findings_summary_of_an_empty_graph_is_all_none(store):
    assert store.open_findings_summary() == {"indexed_at": None, "binding_rung": None}


# -- the same reads, narrowed to one repository ------------------------------------------------
#
# Repository scope is what every console level below Codebase inherits (B92). Each read below
# already joins `call_site`, which is where `repo_id` lives, so the filter is a predicate on a
# join these queries already make rather than a second query or a Python pass over the result.


def _two_repositories(store) -> None:
    """One open finding in `r1` and one in `r2`, differing only by repository."""
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(mine, claim="c1"))
    store.insert_finding(_finding_for_open(theirs, claim="c2"))


def test_open_findings_page_scoped_to_a_repository_omits_another_repositorys_finding(store):
    _two_repositories(store)

    findings = store.open_findings_page(repo_id="r1")

    assert len(findings) == 1
    assert len(store.open_findings_page()) == 2, "unscoped still answers for the fleet"


def test_open_findings_count_scoped_to_a_repository(store):
    _two_repositories(store)

    assert store.open_findings_count(repo_id="r1") == 1
    assert store.open_findings_count() == 2


def test_open_findings_count_bounded_scoped_to_a_repository(store):
    _two_repositories(store)

    assert store.open_findings_count_bounded(10, repo_id="r1") == (1, False)
    assert store.open_findings_count_bounded(10) == (2, False)


def test_open_findings_vendor_counts_scoped_to_a_repository(store):
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(
        _site(repo_id="r2", path="src/b.ts", line=2, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding_for_open(mine, claim="c1"))
    store.insert_finding(_finding_for_open(theirs, claim="c2"))

    assert store.open_findings_vendor_counts(repo_id="r1") == {"stripe": 1}
    assert store.open_findings_vendor_counts() == {"shopify": 1, "stripe": 1}


def test_open_findings_vendor_counts_scoped_to_a_repository_is_still_one_query(store, monkeypatch):
    _two_repositories(store)

    calls = _execute_count(monkeypatch)
    store.open_findings_vendor_counts(repo_id="r1")

    assert len(calls) == 1, f"expected one query, made {len(calls)}"


def test_open_findings_severity_counts_scoped_to_a_repository(store):
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(mine, claim="c1", severity="breaking"))
    store.insert_finding(_finding_for_open(theirs, claim="c2", severity="warning"))

    assert store.open_findings_severity_counts(repo_id="r1") == {"breaking": 1}
    assert store.open_findings_severity_counts() == {"breaking": 1, "warning": 1}


def test_open_findings_summary_scoped_to_a_repository_reads_only_that_repositorys_rungs(store):
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(mine, claim="c1", binding_rung="static"))
    store.insert_finding(_finding_for_open(theirs, claim="c2", binding_rung="observed"))

    assert store.open_findings_summary(repo_id="r1")["binding_rung"] == "static"
    assert store.open_findings_summary()["binding_rung"] is None, "the fleet mixes two rungs"


# -- the at-risk page: what the vendor screen renders, filtered in SQL --------------------------
#
# `GraphSurface.whats_at_risk` answers the same question and cannot be narrowed to a repository:
# `sync/mcp/tools.py` is frozen, its rows carry no `repo_id`, and it walks every open finding
# doing one `get_call_site` round trip per row. This is the same replacement `overview_summary`
# already made for `/api/overview`.


def test_open_findings_at_risk_returns_one_row_per_open_finding(store):
    change_id = store.upsert_vendor_change(_change(operation_id="PostCharges"))
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id, vendor_change_id=change_id))

    rows = store.open_findings_at_risk()

    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == "src/billing.ts"
    assert row["line"] == 42
    assert row["symbol"] == "stripe.charges.create"
    assert row["operation_id"] == "PostCharges"
    assert row["vendor_id"] == "stripe"
    assert row["change_kind"] == "response-property-removed"
    assert row["severity"] == "breaking"
    assert row["binding_rung"] == "static"


def test_open_findings_at_risk_change_kind_is_null_when_the_finding_names_no_change(store):
    """A finding raised by a detector that read traffic rather than a changelog names no
    `vendor_change`, and the row must say so rather than dropping out of the page entirely --
    which is what an inner join would have done.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id, detector="status-rate", binding_rung="observed"))

    rows = store.open_findings_at_risk()

    assert len(rows) == 1
    assert rows[0]["change_kind"] is None


def test_open_findings_at_risk_scoped_to_a_repository(store):
    _two_repositories(store)

    assert len(store.open_findings_at_risk(repo_id="r1")) == 1
    assert len(store.open_findings_at_risk()) == 2


def test_open_findings_at_risk_scoped_to_a_vendor(store):
    stripe = store.upsert_call_site(_site(path="src/a.ts", line=1))
    shopify = store.upsert_call_site(
        _site(path="src/b.ts", line=2, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding_for_open(stripe, claim="c1"))
    store.insert_finding(_finding_for_open(shopify, claim="c2"))

    rows = store.open_findings_at_risk(vendor_id="stripe")

    assert [row["vendor_id"] for row in rows] == ["stripe"]


def test_open_findings_at_risk_scoped_to_a_severity(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding_for_open(site_a, claim="c1", severity="breaking"))
    store.insert_finding(_finding_for_open(site_b, claim="c2", severity="warning"))

    rows = store.open_findings_at_risk(severity="warning")

    assert [row["severity"] for row in rows] == ["warning"]


def test_open_findings_at_risk_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    rows = store.open_findings_at_risk(limit=2, offset=0)

    assert len(rows) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def _sites_by_severity(store, severities: list[str]) -> None:
    """One open finding per severity, inserted in an order that is not the ranked one.

    Insertion order matters to these tests: the default ordering is `created_at`, so a fixture
    inserted most-severe-first would pass a severity-ordered assertion while doing nothing at all.
    """
    for i, severity in enumerate(severities):
        site_id = store.upsert_call_site(
            _site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}")
        )
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}", severity=severity))


def test_open_findings_at_risk_defaults_to_the_order_findings_were_raised_in(store):
    """The default is unchanged and is asserted rather than assumed. A table that silently
    reorders is a table whose page boundaries move under a reader, so the ordering this shipped
    with stays the ordering nobody chose -- what changes is that the screen now names it.
    """
    _sites_by_severity(store, ["info", "breaking", "warning"])

    rows = store.open_findings_at_risk()

    assert [row["path"] for row in rows] == ["src/0.ts", "src/1.ts", "src/2.ts"]


def test_open_findings_at_risk_can_order_by_declared_severity(store):
    _sites_by_severity(store, ["info", "deprecation", "breaking", "addition", "warning"])

    rows = store.open_findings_at_risk(order="severity")

    assert [row["severity"] for row in rows] == list(SEVERITY_ORDER)


def test_the_severity_ordering_is_a_sql_order_by_not_a_python_sort(store, fetch_counts):
    """A page ordered in Python is fifty rows of two and a half thousand put in order and
    presented as the worst fifty. The ordering has to reach the database, so the page this reads
    is the first page of the ordered set rather than an ordering of the first page.
    """
    _sites_by_severity(store, ["info", "deprecation", "breaking", "addition", "warning"])

    rows = store.open_findings_at_risk(order="severity", limit=2)

    assert [row["severity"] for row in rows] == ["breaking", "warning"]
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_the_severity_ordering_breaks_ties_the_same_way_every_time(store):
    """Two findings of one severity need a total order or the pages overlap and skip. The
    tiebreak is the default ordering, so a severity-ordered page is the default ordering inside
    each severity rather than whatever the planner returned.
    """
    _sites_by_severity(store, ["breaking", "breaking", "breaking"])

    first = store.open_findings_at_risk(order="severity", limit=2, offset=0)
    second = store.open_findings_at_risk(order="severity", limit=2, offset=2)

    assert [row["path"] for row in first] == ["src/0.ts", "src/1.ts"]
    assert [row["path"] for row in second] == ["src/2.ts"]


def test_a_severity_the_rank_does_not_name_sorts_last_rather_than_first(store):
    """`schema.sql` stores severity as TEXT, so a value outside the vocabulary can exist -- an
    older row, or a vendor adapter ahead of `sync.core`. It must not be promoted: an unrankable
    finding at the top of a page an operator opened to see the worst first is a false claim about
    which finding matters most, and silence at the end is merely a gap.
    """
    _sites_by_severity(store, ["breaking", "info"])
    site_id = store.upsert_call_site(_site(path="src/x.ts", line=9, content_hash="hash-x"))
    store.insert_finding(_finding_for_open(site_id, claim="claim-x", severity="breaking"))
    store._connect().execute(
        "UPDATE finding SET severity = %s WHERE claim = %s", ("catastrophic", "claim-x")
    )

    rows = store.open_findings_at_risk(order="severity")

    assert [row["severity"] for row in rows] == ["breaking", "info", "catastrophic"]


def test_an_ordering_the_store_does_not_know_raises_rather_than_falling_back(store):
    """Internal contract, so it raises. A typo in our own call site that fell back to the default
    would reorder a page while the screen went on naming the ordering it was asked for, which is
    the one failure an echoed ordering cannot catch.
    """
    with pytest.raises(ValueError, match="unknown ordering"):
        store.open_findings_at_risk(order="severty")


def test_the_count_is_the_same_whichever_ordering_the_page_took(store):
    """An ordering narrows nothing. If a total ever moved with a sort, the sort would be filtering
    and saying it was arranging.
    """
    _sites_by_severity(store, ["info", "breaking", "warning"])

    assert store.open_findings_at_risk_count() == 3
    assert len(store.open_findings_at_risk(order="severity")) == 3


def test_open_findings_at_risk_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}"))
        store.insert_finding(_finding_for_open(site_id, claim=f"claim-{i}"))

    assert store.open_findings_at_risk_count() == 5
    assert len(store.open_findings_at_risk(limit=2)) == 2


def test_open_findings_at_risk_count_honours_the_same_filters_as_the_page(store):
    _two_repositories(store)

    assert store.open_findings_at_risk_count(repo_id="r1") == 1
    assert store.open_findings_at_risk_count() == 2


def test_open_findings_at_risk_excludes_a_retracted_call_sites_finding(store):
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding_for_open(site_id))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (site_id,))

    assert store.open_findings_at_risk() == []
    assert store.open_findings_at_risk_count() == 0


# -- the observed-shape join collapses from N+1 to one query -----------------------------------


def _observed_call(**over) -> ObservedCall:
    base = dict(
        repo_id="r1", vendor_id="stripe", operation_id="PostCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="post", trace_id="t1",
        url_template="/v1/charges", spans={"s1": {"target": "d1", "status": 200, "resend": 0}},
        first_seen=_HOUR_14, last_seen=_HOUR_14,
    )
    base.update(over)
    return ObservedCall(**base)


def _shape(**over) -> ObservedShape:
    base = dict(
        vendor_id="stripe", operation_id="PostCharges", field_path="/amount",
        json_type="number", source="interceptor", sample_count=1,
        first_seen=_HOUR_14, last_seen=_HOUR_14,
    )
    base.update(over)
    return ObservedShape(**base)


def test_observed_operation_pairs_excludes_the_uncorrelated_empty_operation(store):
    store.record_observed_call(_observed_call(operation_id="PostCharges", trace_id="t1"))
    store.record_observed_call(_observed_call(operation_id="", binding_rung="unresolved", trace_id="t2"))

    assert store.observed_operation_pairs("r1") == [("stripe", "PostCharges")]


def test_observed_shapes_for_operations_reads_every_pair_in_one_query(store, monkeypatch):
    """The N+1 this replaces issued one query per distinct `(vendor_id, operation_id)` pair.
    Ten pairs must not cost ten round trips -- the property is asserted by counting queries,
    which is the only way to distinguish "collapsed" from "merely fast enough not to notice".
    """
    pairs = [("stripe", f"Op{i}") for i in range(10)]
    for vendor_id, operation_id in pairs:
        store.record_observed_shape(_shape(vendor_id=vendor_id, operation_id=operation_id))

    calls = _execute_count(monkeypatch)
    shapes = store.observed_shapes_for_operations(pairs)

    assert len(shapes) == 10
    assert len(calls) == 1, f"expected one query for ten pairs, made {len(calls)}"


def test_observed_shapes_for_operations_with_no_pairs_makes_no_query(store, monkeypatch):
    """An uncorrelated call names no pair, and `observed_telemetry` must not turn that
    absence into a query that joins against nothing.
    """
    calls = _execute_count(monkeypatch)

    assert store.observed_shapes_for_operations([]) == []
    assert calls == []


def test_observed_shapes_for_operations_limit_is_sql_not_a_python_slice(store, fetch_counts):
    for i in range(5):
        store.record_observed_shape(_shape(field_path=f"/f{i}"))
    pairs = [("stripe", "PostCharges")]

    shapes = store.observed_shapes_for_operations(pairs, limit=2, offset=0)

    assert len(shapes) == 2, "rows returned"
    assert fetch_counts[-1] == 2, "rows read off the wire"


def test_observed_shapes_for_operations_count_matches_the_filter_not_the_page(store):
    for i in range(5):
        store.record_observed_shape(_shape(field_path=f"/f{i}"))
    pairs = [("stripe", "PostCharges")]

    assert store.observed_shapes_for_operations_count(pairs) == 5
    assert len(store.observed_shapes_for_operations(pairs, limit=2)) == 2


def test_a_removal_reports_how_many_rows_it_took_out(store):
    """The count has a caller: an ingest that wrote nothing and deleted three rows reads exactly
    like one that held nothing for this vendor, and the operator sees only the writes. Scoped the
    same way the delete is, so the row belonging to another source is not in the number either.
    """
    store.record_observed_error_window(_error_window())
    store.record_observed_error_window(_error_window(status_class="4xx"))
    store.record_observed_error_window(_error_window(source="span-derived"))

    removed = store.remove_observed_error_windows_outside(
        "r1", "stripe", "error-tracker-group", _HOUR_14, _HOUR_15, ()
    )

    assert removed == 2


# -- filtering and faceting a long table ----------------------------------------
#
# A console table over a real customer repository holds thousands of call sites, and the
# affordance that makes it usable -- narrow to a directory, or to one repository -- has to be
# a real SQL predicate rather than a filter applied to whichever page arrived. A filter over
# one page reports a total drawn from the whole set, which is the "a reader cannot tell what
# this view can see" defect this milestone has closed six times, wearing a new hat.


def test_call_sites_for_operation_narrows_to_a_path_prefix(store):
    store.upsert_call_site(_site(path="src/billing/charge.ts", content_hash="hash-a"))
    store.upsert_call_site(_site(path="src/reporting/export.ts", content_hash="hash-b"))

    sites = store.call_sites_for_operation("stripe", "PostCharges", path_prefix="src/billing/")

    assert [s.path for s in sites] == ["src/billing/charge.ts"]


def test_call_sites_for_operation_path_prefix_is_sql_not_a_python_filter(store, fetch_counts):
    """A prefix applied after the fetch reads every row off the wire and then throws most of
    them away, which is exactly the cost the filter exists to avoid at ten thousand call sites.
    """
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/keep/{i}.ts", line=i, content_hash=f"keep-{i}"))
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/drop/{i}.ts", line=i, content_hash=f"drop-{i}"))

    sites = store.call_sites_for_operation("stripe", "PostCharges", path_prefix="src/keep/")

    assert len(sites) == 5, "rows returned"
    assert fetch_counts[-1] == 5, "rows read off the wire"


def test_call_sites_for_operation_path_prefix_treats_underscore_as_a_literal(store):
    """`_` is a single-character wildcard in SQL `LIKE` and is ordinary in a source path --
    `src/my_module/` is the normal spelling of a Python or TypeScript directory. A prefix
    built as a `LIKE` pattern without escaping matches `src/myXmodule/` too, silently, and no
    fixture in this repository would have caught it.
    """
    store.upsert_call_site(_site(path="src/my_module/charge.ts", content_hash="hash-a"))
    store.upsert_call_site(_site(path="src/myXmodule/charge.ts", content_hash="hash-b"))

    sites = store.call_sites_for_operation("stripe", "PostCharges", path_prefix="src/my_module/")

    assert [s.path for s in sites] == ["src/my_module/charge.ts"]


def test_call_sites_for_operation_path_prefix_treats_percent_as_a_literal(store):
    store.upsert_call_site(_site(path="src/100%/charge.ts", content_hash="hash-a"))
    store.upsert_call_site(_site(path="src/other/charge.ts", content_hash="hash-b"))

    sites = store.call_sites_for_operation("stripe", "PostCharges", path_prefix="src/100%/")

    assert [s.path for s in sites] == ["src/100%/charge.ts"]


def test_call_sites_for_operation_count_honours_the_path_prefix(store):
    """The denominator has to move with the filter. A total drawn from the unfiltered set
    beside a filtered page tells a reader the page is a window on something it is not.
    """
    for i in range(3):
        store.upsert_call_site(_site(path=f"src/keep/{i}.ts", line=i, content_hash=f"keep-{i}"))
    store.upsert_call_site(_site(path="src/drop/0.ts", content_hash="drop-0"))

    assert store.call_sites_for_operation_count("stripe", "PostCharges") == 4
    assert (
        store.call_sites_for_operation_count(
            "stripe", "PostCharges", path_prefix="src/keep/"
        )
        == 3
    )


def test_call_sites_for_operation_combines_the_path_prefix_with_repo_id(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/keep/a.ts", content_hash="hash-a"))
    store.upsert_call_site(_site(repo_id="r2", path="src/keep/b.ts", content_hash="hash-b"))
    store.upsert_call_site(_site(repo_id="r1", path="src/drop/c.ts", content_hash="hash-c"))

    sites = store.call_sites_for_operation(
        "stripe", "PostCharges", repo_id="r1", path_prefix="src/keep/"
    )

    assert [s.path for s in sites] == ["src/keep/a.ts"]


def test_call_site_repositories_for_operation_counts_sites_per_repository(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", content_hash="hash-a"))
    store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", content_hash="hash-b"))
    store.upsert_call_site(_site(repo_id="r2", path="src/c.ts", content_hash="hash-c"))

    assert store.call_site_repositories_for_operation("stripe", "PostCharges") == {
        "r1": 2,
        "r2": 1,
    }


def test_call_site_repositories_for_operation_is_one_query_not_one_per_repository(
    store, monkeypatch
):
    for i in range(5):
        store.upsert_call_site(_site(repo_id=f"r{i}", path=f"src/{i}.ts", content_hash=f"h-{i}"))
    queries = _execute_count(monkeypatch)

    store.call_site_repositories_for_operation("stripe", "PostCharges")

    assert len(queries) == 1


def test_call_site_repositories_for_operation_excludes_retracted_sites(store):
    """A repository whose every call site has been retracted is absent, not present with a
    zero. The facet is the option list for a filter, and offering a repository that can only
    ever return an empty page invents a choice the graph does not hold.
    """
    site_id = store.upsert_call_site(_site(repo_id="r2", path="src/c.ts", content_hash="hash-c"))
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", content_hash="hash-a"))
    store.replace_call_sites("r2", [])

    assert store.call_site_repositories_for_operation("stripe", "PostCharges") == {"r1": 1}
    assert store.get_call_site(site_id).retracted_at is not None


def test_call_site_repositories_for_operation_is_scoped_to_the_operation(store):
    store.upsert_call_site(_site(repo_id="r1", operation_id="PostCharges", content_hash="hash-a"))
    store.upsert_call_site(
        _site(repo_id="r2", operation_id="GetCharges", path="src/b.ts", content_hash="hash-b")
    )

    assert store.call_site_repositories_for_operation("stripe", "PostCharges") == {"r1": 1}


def test_open_findings_severity_counts_narrows_to_one_vendor(store):
    """The fleet screen asks this across every vendor; a vendor screen asks it for one. The
    same aggregate answers both -- a second method would be a second place for the join to
    disagree about which findings are open.
    """
    stripe_site = store.upsert_call_site(_site(vendor_id="stripe", content_hash="hash-a"))
    twilio_site = store.upsert_call_site(
        _site(vendor_id="twilio", path="src/sms.ts", content_hash="hash-b")
    )
    store.insert_finding(_finding_for_open(stripe_site, severity="breaking"))
    store.insert_finding(_finding_for_open(twilio_site, severity="warning", claim="other"))

    assert store.open_findings_severity_counts() == {"breaking": 1, "warning": 1}
    assert store.open_findings_severity_counts(vendor_id="stripe") == {"breaking": 1}


def test_open_findings_severity_counts_for_a_vendor_with_nothing_open_is_empty(store):
    assert store.open_findings_severity_counts(vendor_id="stripe") == {}


def _dismissable_finding(store) -> str:
    site_id = store.upsert_call_site(_site())
    return store.insert_finding(
        Finding(
            detector="vendor-change",
            claim="response-field-type-changed",
            call_site_id=site_id,
            severity="warning",
            rationale="the call reads a field whose type the vendor changed",
            binding_rung="static",
        )
    )


def test_replaying_one_dismissal_converges_on_one_row(store):
    """`CLAUDE.md`: every table gets a natural key and an explicit conflict clause, and `efcc19d`
    was this bug. One person dismissing one finding at one instant is one event however many
    times the write is replayed -- a retry after a dropped connection must not leave two rows
    that make `dismissal_history_count` report a decision taken twice."""
    finding_id = _dismissable_finding(store)
    at = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)

    store.record_dismissal(finding_id, reason="false_positive", actor="sebastian", at=at)
    store.record_dismissal(finding_id, reason="false_positive", actor="sebastian", at=at)

    assert store.dismissal_history_count(finding_id) == 1


def test_two_genuine_decisions_at_different_times_are_two_rows(store):
    """The key must not collapse a real change of mind. Dismissing, restoring and dismissing
    again is three events, and the history is what shows somebody argued with themselves."""
    finding_id = _dismissable_finding(store)
    store.record_dismissal(
        finding_id, reason="wont_fix", actor="a", at=datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
    )
    store.record_dismissal(
        finding_id, reason=None, actor="a", at=datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    )

    assert store.dismissal_history_count(finding_id) == 2
    assert store.dismissal_state(finding_id)["dismissed"] is False


# -- index_run: decision 41's durable half -----------------------------------------------------
#
# A toast may announce "Index finished, 1,204 call sites" but must never be the only place that
# fact exists. `call_site.indexed_at` says rows exist, which cannot tell a pass that finished from
# one that died halfway -- and that difference is exactly what a reader needs before trusting a
# count. One row per pass, per repository.


def test_a_repository_never_indexed_has_no_pass(store):
    # Absence rather than a zeroed row. Never-indexed and indexed-and-found-nothing are different
    # facts, and this is the one the console keeps apart everywhere else.
    assert store.latest_index_run("r1") is None


def test_a_finished_pass_reports_what_it_wrote(store):
    store.start_index_run("r1", started_at=SEEN)
    store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=1204)

    run = store.latest_index_run("r1")

    assert run is not None
    assert run["finished_at"] is not None
    assert run["call_sites"] == 1204


def test_a_pass_that_never_finished_is_distinguishable_from_one_that_did(store):
    """The whole reason this is a table and not a timestamp on `call_site`. A pass that died
    halfway leaves rows behind, so a count taken from those rows would read as a completed index
    of a smaller codebase."""
    store.start_index_run("r1", started_at=SEEN)

    run = store.latest_index_run("r1")

    assert run is not None
    assert run["finished_at"] is None
    assert run["call_sites"] is None


def test_the_latest_pass_wins_and_the_earlier_ones_are_kept(store):
    later = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    store.start_index_run("r1", started_at=SEEN)
    store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=10)
    store.start_index_run("r1", started_at=later)
    store.finish_index_run("r1", started_at=later, finished_at=later, call_sites=12)

    assert store.latest_index_run("r1")["call_sites"] == 12
    assert store.index_run_count("r1") == 2


def test_one_pass_is_scoped_to_its_own_repository(store):
    store.start_index_run("r1", started_at=SEEN)
    store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=7)

    assert store.latest_index_run("r2") is None


def test_replaying_the_same_pass_converges(store):
    """`CLAUDE.md`: every stage is idempotent, every table gets a natural key and an explicit
    conflict clause. Re-running INDEX over the same input converges on the same rows, so one pass
    started at one instant is one row however many times it is recorded."""
    store.start_index_run("r1", started_at=SEEN)
    store.start_index_run("r1", started_at=SEEN)
    store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=3)

    assert store.index_run_count("r1") == 1


def test_a_pass_that_died_is_distinguishable_from_one_still_running(store):
    """The coordinator's ruling on `index_run`, and it is a real gap in the first cut.

    `finished_at IS NULL` alone cannot tell a pass that died from one still going, so a reader
    looking at a stale unfinished row has no way to know whether to wait. An explicit terminal
    state from a closed set says which -- the same discipline as `migration_outcome`'s outcome
    and `abandon_reason`, and the fourth state again: not finished, not failed, not absent.
    """
    store.start_index_run("r1", started_at=SEEN)
    assert store.latest_index_run("r1")["outcome"] is None

    store.fail_index_run("r1", started_at=SEEN, at=SEEN, outcome="failed")

    run = store.latest_index_run("r1")
    assert run["outcome"] == "failed"
    assert run["finished_at"] is not None
    # A pass that died wrote no trustworthy count, and a partial one is not a smaller count.
    assert run["call_sites"] is None


def test_a_completed_pass_says_completed(store):
    store.start_index_run("r1", started_at=SEEN)
    store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=12)

    assert store.latest_index_run("r1")["outcome"] == "completed"


def test_an_outcome_outside_the_closed_set_is_refused(store):
    store.start_index_run("r1", started_at=SEEN)

    # Closed for the reason `abandon_reason_code` is: a promise to learn which repositories fail
    # to index needs a schema that can answer it, and free text cannot be aggregated.
    with pytest.raises(ValueError):
        store.fail_index_run("r1", started_at=SEEN, at=SEEN, outcome="it broke")


def test_severity_by_vendor_crosses_both_columns_without_either_filter(store):
    """G3's source: severity counted per vendor, as one grouping rather than two.

    `by_vendor` and `by_severity` are each a single-column facet, and neither can answer "which
    integration is publishing the breaking changes" -- a reader could only get there by filtering
    to one vendor and reading the severity facet, once per vendor.

    Counted with the page's own filters ignored, the same rule the single-column facets follow:
    a facet that narrowed itself would show the reader only the slice they already chose.
    """
    store.upsert_vendor_change(_change(vendor_id="stripe", severity="breaking"))
    store.upsert_vendor_change(
        _change(vendor_id="stripe", severity="warning", operation_id="PostCharges")
    )
    store.upsert_vendor_change(
        _change(vendor_id="twilio", severity="breaking", operation_id="GetCalls")
    )

    crossed = store.vendor_changes_page(vendor_ids=["stripe"])["by_vendor_severity"]

    assert crossed == {
        "stripe": {"breaking": 1, "warning": 1},
        "twilio": {"breaking": 1},
    }


def test_severity_by_vendor_omits_a_severity_a_vendor_never_published(store):
    """A vendor with no breaking change is absent from that key, never present at nought.

    The grouping returns groups that exist. Rendering a missing key as a zero would claim the
    pairing was measured and found empty, which is the absence-versus-zero distinction the
    console is built to keep.
    """
    store.upsert_vendor_change(_change(vendor_id="stripe", severity="warning"))

    crossed = store.vendor_changes_page()["by_vendor_severity"]

    assert crossed == {"stripe": {"warning": 1}}
    assert "breaking" not in crossed["stripe"]


def _detected_on(store, change, day: datetime) -> None:
    """Stamp a change's detection date.

    `upsert_vendor_change` takes no `detected_at` -- the column is the database's `now()`, which
    is correct for production and useless for a series test. Adding a parameter to the writer
    that only a test would ever pass is an abstraction with no caller behind it, so the date is
    set here instead.
    """
    change_id = store.upsert_vendor_change(change)
    store._connect().execute(
        "UPDATE vendor_change SET detected_at = %s WHERE id = %s", (day, change_id)
    )


def test_changes_by_day_and_vendor_buckets_on_the_detection_date(store):
    """T3's source: integration changes tallied by the day Sync detected them, per vendor.

    Bucketed in SQL rather than folded from a page, because a series derived from one page of
    rows is the series of whichever rows the ordering reached -- and this feed's ordering is
    newest-first, so a client-side fold would draw the most recent page and label it the history.
    """
    early = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    late = datetime(2026, 8, 3, 22, 0, tzinfo=timezone.utc)
    _detected_on(store, _change(vendor_id="stripe"), early)
    _detected_on(store, _change(vendor_id="stripe", operation_id="PostCharges"), early)
    _detected_on(store, _change(vendor_id="twilio", operation_id="GetCalls"), late)

    series = store.changes_by_day_and_vendor()

    assert series == [
        {"day": "2026-08-01", "vendor_id": "stripe", "n": 2},
        {"day": "2026-08-03", "vendor_id": "twilio", "n": 1},
    ]


def test_changes_by_day_emits_no_row_for_a_day_nothing_was_detected(store):
    """A day with no change is absent, never a zero.

    Nothing in the graph records that an adapter ran, so a gap is a day nothing was recorded --
    which may be a day no vendor published or a day nothing fetched, and those are different
    facts. Emitting a zero would assert the first.
    """
    _detected_on(store, _change(vendor_id="stripe"), datetime(2026, 8, 1, tzinfo=timezone.utc))
    _detected_on(
        store,
        _change(vendor_id="stripe", operation_id="PostCharges"),
        datetime(2026, 8, 5, tzinfo=timezone.utc),
    )

    days = [row["day"] for row in store.changes_by_day_and_vendor()]

    assert days == ["2026-08-01", "2026-08-05"]


def test_selecting_two_integrations_returns_their_union(store):
    """M15 Task 4. A codebase with forty integrations is not filterable one at a time.

    The union is the whole claim: a rail that let a reader press two options and returned the
    intersection, or only the last one pressed, would look identical on screen -- pressed
    options and a shorter table -- and be wrong.
    """
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts"))
    store.upsert_call_site(_site(vendor_id="twilio", path="src/b.ts"))
    store.upsert_call_site(_site(vendor_id="openai", path="src/c.ts"))

    page = store.call_sites_page("r1", vendor_ids=["stripe", "twilio"])

    assert page["total"] == 2
    assert {row["vendor_id"] for row in page["items"]} == {"stripe", "twilio"}


def test_an_empty_selection_is_the_whole_set_rather_than_none_of_it(store):
    """Deselecting every option means "stop narrowing", not "match nothing".

    The distinction has no `null` to carry it once a filter is a list, so it is stated here: an
    empty list reads as absent. A rail whose last deselection emptied the table would strand a
    reader with no visible way back.
    """
    store.upsert_call_site(_site(vendor_id="stripe"))
    store.upsert_call_site(_site(vendor_id="twilio", path="src/b.ts"))

    assert store.call_sites_page("r1", vendor_ids=[])["total"] == 2


def test_a_facet_under_multi_select_still_ignores_its_own_filter(store):
    """The rail's existing rule, which multi-select is the case that could quietly break it.

    A facet narrowed by its own selection collapses to the options already pressed, and a reader
    who has pressed two of forty integrations would lose the other thirty-eight -- with no way
    back, because the options that would clear the filter are the ones that vanished.
    """
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts"))
    store.upsert_call_site(_site(vendor_id="twilio", path="src/b.ts"))
    store.upsert_call_site(_site(vendor_id="openai", path="src/c.ts"))

    page = store.call_sites_page("r1", vendor_ids=["stripe", "twilio"])

    assert page["by_vendor"] == {"stripe": 1, "twilio": 1, "openai": 1}


def test_two_facets_narrow_each_other_while_each_ignores_itself(store):
    """The other half of the rule: a facet ignores *its own* filter, not every filter.

    A facet ignoring all of them would report counts describing a set the reader is not looking
    at, which is the same lie in the other direction.
    """
    store.upsert_call_site(_site(vendor_id="stripe", operation_id="PostCharges", path="src/a.ts"))
    store.upsert_call_site(_site(vendor_id="stripe", operation_id="GetBalance", path="src/b.ts"))
    store.upsert_call_site(_site(vendor_id="twilio", operation_id="GetCalls", path="src/c.ts"))

    page = store.call_sites_page("r1", operation_ids=["PostCharges"])

    # The vendor facet honours the operation filter and ignores nothing of its own.
    assert page["by_vendor"] == {"stripe": 1}
    # The operation facet ignores the operation filter, so every operation is still offered.
    assert page["by_operation"] == {"PostCharges": 1, "GetBalance": 1, "GetCalls": 1}


def test_loop_depth_is_offered_as_a_facet_of_its_own(store):
    """Static evidence, and the one facet a reader uses to find quadratic call shapes.

    `schema.sql` is explicit that a depth is proof of shape rather than of volume, so this is a
    facet over what the code says -- which is exactly what makes it worth filtering by.
    """
    store.upsert_call_site(_site(path="src/a.ts", loop_depth=0))
    store.upsert_call_site(_site(path="src/b.ts", loop_depth=2))
    store.upsert_call_site(_site(path="src/c.ts", loop_depth=2))

    page = store.call_sites_page("r1", loop_depths=[2])

    assert page["total"] == 2
    assert page["by_loop_depth"] == {0: 1, 2: 2}


def test_a_bare_string_where_a_list_belongs_is_refused(store):
    """A string is a sequence of characters, and `= ANY('stripe')` matches nothing.

    That failure is silent -- an empty page, which reads as "no call site matches" rather than
    as a caller error -- so it is refused at the call rather than diagnosed later. This is the
    one guard here, and it exists because the wrong answer is indistinguishable from a real one.
    """
    with pytest.raises(TypeError):
        store.call_sites_page("r1", vendor_ids="stripe")


def test_changes_take_a_union_of_severities(store):
    """The same widening on the changes feed, where the pair a reviewer wants is
    breaking-and-deprecation -- two of five, and not expressible one at a time."""
    store.upsert_vendor_change(_change(severity="breaking"))
    store.upsert_vendor_change(_change(severity="deprecation", operation_id="GetBalance"))
    store.upsert_vendor_change(_change(severity="info", operation_id="GetCalls"))

    page = store.vendor_changes_page(severities=["breaking", "deprecation"])

    assert page["total"] == 2
    assert {row["severity"] for row in page["items"]} == {"breaking", "deprecation"}
    # The severity facet still offers the member the reader did not press.
    assert page["by_severity"] == {"breaking": 1, "deprecation": 1, "info": 1}

import os
import threading

import psycopg
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

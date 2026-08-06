import os
import threading
from datetime import datetime, timezone

import psycopg
import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, ObservedShape, VendorChange
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


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

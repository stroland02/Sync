"""View models for the three graph screens: the binding surface, the observed rung, detector
accountability.

`SYNC_DSN`, read the same way every other test module reads it, not a database this file names
for itself. `conftest.pytest_configure` hands every run -- and, under `-n auto`, every worker --
its own throwaway database before this module's tests execute; a hardcoded `sync_graph_views_check`
name would opt back out of that isolation and be the one database every worker shares, racing
every other worker's `truncate_all()` and insert against the same rows.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, ObservedShape, RepoSettings, VendorChange
from sync.core.models import SEVERITY_ORDER
from sync.dashboard.graph_views import (
    binding_surface,
    detector_accountability,
    findings_page,
    index_coverage,
    observed_telemetry,
    overview_summary,
    repo_settings,
    severity_rollup,
    vendor_change_volume,
    vendor_operation_exposure,
    vendor_findings,
)
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SEEN = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _query_count(monkeypatch) -> list[str]:
    """How many round trips a read made -- proves an N+1 join collapsed to one query rather
    than merely running fast enough that nobody counted.
    """
    import sync.graph.store as store_module

    calls: list[str] = []
    real_execute = store_module.psycopg.Connection.execute

    def counting_execute(self, query, *args, **kwargs):
        calls.append(query)
        return real_execute(self, query, *args, **kwargs)

    monkeypatch.setattr(store_module.psycopg.Connection, "execute", counting_execute)
    return calls


def _site(**over) -> CallSite:
    base = dict(
        repo_id="r1", path="src/billing.ts", line=42, col=8, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        sdk_version="14.0.0", content_hash="h",
    )
    base.update(over)
    return CallSite(**base)


def _change(**over) -> VendorChange:
    base = dict(
        vendor_id="stripe", from_version="2026-01-01", to_version="2026-02-01",
        kind="response-field-type-changed", operation_id="PostCharges",
        path_ptr="/v1/charges", severity="warning", source="oasdiff",
        raw={"text": "amount changed type"},
    )
    base.update(over)
    return VendorChange(**base)


def _finding(call_site_id: str, **over) -> Finding:
    base = dict(
        detector="vendor-change", claim="response-field-type-changed",
        call_site_id=call_site_id, severity="warning",
        rationale="the call reads a field whose type the vendor changed",
        binding_rung="static",
    )
    base.update(over)
    return Finding(**base)


def _observed_call(**over) -> ObservedCall:
    base = dict(
        repo_id="r1", vendor_id="stripe", operation_id="PostCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="post", trace_id="t1",
        url_template="/v1/charges", spans={"s1": {"target": "d1", "status": 200, "resend": 0}},
        first_seen=SEEN, last_seen=SEEN,
    )
    base.update(over)
    return ObservedCall(**base)


def _shape(**over) -> ObservedShape:
    base = dict(
        vendor_id="stripe", operation_id="PostCharges", field_path="/amount",
        json_type="number", source="interceptor", sample_count=1,
        first_seen=SEEN, last_seen=SEEN,
    )
    base.update(over)
    return ObservedShape(**base)


def _error_window(**over) -> ObservedErrorWindow:
    base = dict(
        repo_id="r1", vendor_id="stripe", operation_id="PostCharges", binding_rung="observed",
        source="error-tracker-group", status_class="5xx",
        window_start=SEEN, window_end=SEEN, error_count=3, issue_count=1,
    )
    base.update(over)
    return ObservedErrorWindow(**base)


# -- binding_surface -------------------------------------------------------------


def test_binding_surface_lists_call_sites_bound_to_one_vendor_operation(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2, repo_id="r2"))
    # A call site on a different operation must not appear.
    store.upsert_call_site(_site(path="src/c.ts", line=3, operation_id="PostRefunds"))

    result = binding_surface(store, "stripe", "PostCharges")

    paths = {row["path"] for row in result["call_sites"]["items"]}
    assert paths == {"src/a.ts", "src/b.ts"}
    assert {site_a, site_b}  # both ids were used; guards against a copy-paste that reused one


def test_binding_surface_every_call_site_row_reports_the_static_rung(store):
    # A call site is what the static index found, so every row here rests on the same rung --
    # the surface must not invent 'resolved' or 'observed' for a binding no correlator touched.
    store.upsert_call_site(_site())

    result = binding_surface(store, "stripe", "PostCharges")

    assert result["call_sites"]["items"], "the fixture wrote no call site"
    assert all(row["binding_rung"] == "static" for row in result["call_sites"]["items"])


def test_binding_surface_reports_the_directory_its_call_sites_share(store):
    """The prefix the screen factors out of the path column, echoed like every other fact about the
    scope a page was computed in. Under the same predicate as the rows, so a filtered page's prefix
    is the one its visible rows actually share.
    """
    for i, path in enumerate([
        "packages/billing/src/adapters/stripe/charges/create.ts",
        "packages/billing/src/adapters/stripe/charges/refund.ts",
    ]):
        store.upsert_call_site(_site(path=path, line=i + 1, content_hash=f"h{i}"))

    page = binding_surface(store, "stripe", "PostCharges")

    assert page["call_sites_common_directory"] == "packages/billing/src/adapters/stripe/charges/"


def test_binding_surface_reports_no_common_directory_when_there_is_none(store):
    """Two trees calling one operation share nothing, and the payload says so with an empty string
    rather than with the first directory of whichever row sorted first. The screen renders the whole
    path when this is empty, which is the only correct fallback.
    """
    for i, path in enumerate(["packages/billing/charge.ts", "services/orders/send.ts"]):
        store.upsert_call_site(_site(path=path, line=i + 1, content_hash=f"h{i}"))

    assert binding_surface(store, "stripe", "PostCharges")["call_sites_common_directory"] == ""


def test_binding_surface_reports_no_common_directory_for_a_rung_that_holds_no_rows(store):
    """`binding_rung` other than `static` empties the call-site page by design. The prefix has to
    empty with it: a directory named above a table with no rows in it is a claim about rows the
    reader cannot see.
    """
    store.upsert_call_site(_site(path="packages/billing/charges/create.ts"))

    page = binding_surface(store, "stripe", "PostCharges", binding_rung="observed")

    assert page["call_sites"]["items"] == []
    assert page["call_sites_common_directory"] == ""


def test_binding_surface_filters_call_sites_by_repo_id_when_asked(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))

    result = binding_surface(store, "stripe", "PostCharges", repo_id="r1")

    assert [row["path"] for row in result["call_sites"]["items"]] == ["src/a.ts"]
    assert result["call_sites"]["total"] == 1


def test_binding_surface_a_binding_rung_other_than_static_is_an_empty_page_not_an_error(store):
    # Every call site row this view builds reports 'static' unconditionally -- a call site is
    # what the static index found, and nothing about it rests on a resolution step or on
    # watched traffic. Asking for a different rung is a real question with a real answer: none
    # of these rows carry it, so it is an empty page, matching every other "nothing recorded"
    # answer in this module -- never an error and never silently the unfiltered set.
    store.upsert_call_site(_site())

    result = binding_surface(store, "stripe", "PostCharges", binding_rung="observed")

    assert result["call_sites"] == {"items": [], "total": 0, "next_offset": None}


def test_binding_surface_a_binding_rung_of_static_returns_the_normal_page(store):
    store.upsert_call_site(_site())

    result = binding_surface(store, "stripe", "PostCharges", binding_rung="static")

    assert result["call_sites"]["total"] == 1


def test_binding_surface_paginates_call_sites_independently_of_changes(store):
    for i in range(5):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
    store.upsert_vendor_change(_change(operation_id="PostCharges"))

    result = binding_surface(
        store, "stripe", "PostCharges", call_sites_limit=2, call_sites_offset=0
    )

    assert len(result["call_sites"]["items"]) == 2
    assert result["call_sites"]["total"] == 5
    assert result["call_sites"]["next_offset"] == 2
    # The changes page is untouched by the call-sites page size -- they are two questions.
    assert result["changes"]["total"] == 1
    assert result["changes"]["next_offset"] is None


def test_binding_surface_call_sites_next_offset_is_null_on_the_last_page(store):
    for i in range(3):
        store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))

    result = binding_surface(
        store, "stripe", "PostCharges", call_sites_limit=2, call_sites_offset=2
    )

    assert len(result["call_sites"]["items"]) == 1
    assert result["call_sites"]["next_offset"] is None


def test_binding_surface_reports_only_changes_matching_the_operation(store):
    store.upsert_call_site(_site())
    store.upsert_vendor_change(_change(operation_id="PostCharges", kind="response-field-type-changed"))
    store.upsert_vendor_change(_change(operation_id="PostRefunds", kind="field-removed"))

    result = binding_surface(store, "stripe", "PostCharges")

    kinds = {row["kind"] for row in result["changes"]["items"]}
    assert kinds == {"response-field-type-changed"}
    assert result["changes"]["total"] == 1


def test_binding_surface_paginates_changes_independently_of_call_sites(store):
    store.upsert_call_site(_site())
    for i in range(4):
        store.upsert_vendor_change(
            _change(operation_id="PostCharges", raw={"text": f"change {i}"})
        )

    result = binding_surface(store, "stripe", "PostCharges", changes_limit=2, changes_offset=0)

    assert len(result["changes"]["items"]) == 2
    assert result["changes"]["total"] == 4
    assert result["changes"]["next_offset"] == 2
    # The call-sites page is untouched by the changes page size.
    assert result["call_sites"]["total"] == 1
    assert result["call_sites"]["next_offset"] is None


def test_binding_surface_on_an_operation_nobody_calls_is_empty_not_an_error(store):
    result = binding_surface(store, "stripe", "GetNothing")

    assert result["call_sites"] == {"items": [], "total": 0, "next_offset": None}
    assert result["changes"] == {"items": [], "total": 0, "next_offset": None}


def test_binding_surface_excludes_retracted_call_sites(store):
    # A retracted call site is a position the code no longer occupies -- `binding_surface`
    # reads `call_sites_for_operation`, whose own contract excludes it, and this pins that the
    # exclusion actually reaches this view rather than being assumed from the store's docstring.
    live_id = store.upsert_call_site(_site(path="src/a.ts", line=1))
    retracted_id = store.upsert_call_site(_site(path="src/b.ts", line=2))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (retracted_id,))

    result = binding_surface(store, "stripe", "PostCharges")

    paths = {row["path"] for row in result["call_sites"]["items"]}
    assert paths == {"src/a.ts"}
    assert live_id != retracted_id  # guards against a copy-paste that reused one id for both


# -- index_coverage ---------------------------------------------------------------


def test_index_coverage_counts_call_sites_per_vendor(store):
    store.upsert_call_site(_site(path="src/a.ts", line=1, vendor_id="stripe"))
    store.upsert_call_site(_site(path="src/b.ts", line=2, vendor_id="stripe"))
    store.upsert_call_site(_site(path="src/c.ts", line=3, vendor_id="twilio", operation_id="SendSms"))

    result = index_coverage(store, "r1")

    assert result["by_vendor"] == {"stripe": 2, "twilio": 1}
    assert result["total_call_sites"] == 3


def test_index_coverage_a_vendor_with_no_call_sites_is_absent_not_zero(store):
    store.upsert_call_site(_site(vendor_id="stripe"))

    result = index_coverage(store, "r1")

    assert "twilio" not in result["by_vendor"]
    assert "twilio" not in result["last_indexed"]


def test_index_coverage_is_scoped_to_one_repository(store):
    store.upsert_call_site(_site(repo_id="r1"))
    store.upsert_call_site(_site(repo_id="r2", path="src/other.ts"))

    result = index_coverage(store, "r1")

    assert result["total_call_sites"] == 1


def test_index_coverage_of_an_unindexed_repository_is_all_zero(store):
    result = index_coverage(store, "never-indexed")

    assert result["by_vendor"] == {}
    assert result["last_indexed"] == {}
    assert result["total_call_sites"] == 0


def test_index_coverage_reports_last_indexed_as_an_iso_string(store):
    store.upsert_call_site(_site(vendor_id="stripe"))

    result = index_coverage(store, "r1")

    indexed_at = result["last_indexed"]["stripe"]
    assert isinstance(indexed_at, str)
    datetime.fromisoformat(indexed_at)  # does not raise


def test_index_coverage_by_vendor_and_last_indexed_always_share_the_same_keys(store):
    """`by_vendor` and `last_indexed` are built from one `GraphStore.call_site_coverage` read
    now, so they cannot disagree about which vendors are present -- there is no second round
    trip whose result could name a different key set. This is the property that makes the
    original defect structurally impossible rather than merely unlikely: with one query there
    is only one snapshot, and nothing else to race against it. That is argued here, not
    triggered -- reproducing the actual race would mean patching internals to simulate a write
    landing between two reads, which proves nothing about the real code.
    """
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts", line=1))
    store.upsert_call_site(_site(vendor_id="twilio", operation_id="SendSms", path="src/b.ts", line=2))
    store.upsert_call_site(_site(vendor_id="sendgrid", operation_id="SendEmail", path="src/c.ts", line=3))

    result = index_coverage(store, "r1")

    assert set(result["by_vendor"]) == set(result["last_indexed"]) == {"stripe", "twilio", "sendgrid"}


def test_index_coverage_pairs_the_newest_timestamp_with_its_own_vendor(store):
    """A test that checked `by_vendor` and `last_indexed` independently would pass on an
    implementation that paired one vendor's count with another vendor's timestamp -- so the two
    vendors are seeded with their counts and their timestamps in opposite rank order, and the
    assertion checks both fields for one vendor together.
    """
    store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts", line=1))
    store.upsert_call_site(_site(vendor_id="stripe", path="src/b.ts", line=2))
    twilio_id = store.upsert_call_site(
        _site(vendor_id="twilio", operation_id="SendSms", path="src/c.ts", line=3)
    )

    with store._connect().cursor() as cur:
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE repo_id = 'r1' AND vendor_id = 'stripe'",
            (datetime(2020, 1, 1, tzinfo=timezone.utc),),
        )
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2030, 1, 1, tzinfo=timezone.utc), twilio_id),
        )

    result = index_coverage(store, "r1")

    assert result["by_vendor"]["stripe"] == 2
    assert result["last_indexed"]["stripe"] == "2020-01-01T00:00:00+00:00"
    assert result["by_vendor"]["twilio"] == 1
    assert result["last_indexed"]["twilio"] == "2030-01-01T00:00:00+00:00"


# -- observed_telemetry ------------------------------------------------------------


_EMPTY_PAGE = {"items": [], "total": 0, "next_offset": None}


def test_observed_telemetry_reports_calls_for_one_repository(store):
    store.record_observed_call(_observed_call(repo_id="r1", trace_id="t1"))
    store.record_observed_call(_observed_call(repo_id="r2", trace_id="t2"))

    result = observed_telemetry(store, "r1")

    assert [row["trace_id"] for row in result["calls"]["items"]] == ["t1"]
    assert result["calls"]["total"] == 1


def test_observed_telemetry_call_rows_carry_the_derived_evidence_counts(store):
    # `call_count`, `error_count` and friends are properties on `ObservedCall`, derived from
    # `spans` rather than stored -- the view model must read them, not restate `len(spans)`.
    spans = {
        "s1": {"target": "d1", "status": 200, "resend": 0},
        "s2": {"target": "d1", "status": 500, "resend": 1},
    }
    store.record_observed_call(_observed_call(trace_id="t1", spans=spans))

    result = observed_telemetry(store, "r1")

    row = result["calls"]["items"][0]
    assert row["call_count"] == 2
    assert row["distinct_targets"] == 1
    assert row["repeated_calls"] == 1
    assert row["error_count"] == 1
    assert row["max_resend_count"] == 1


def test_observed_telemetry_calls_paginate_independently_of_shapes_and_windows(store):
    for i in range(5):
        store.record_observed_call(_observed_call(trace_id=f"t{i}"))
    store.record_observed_shape(_shape())
    store.record_observed_error_window(_error_window())

    result = observed_telemetry(store, "r1", calls_limit=2, calls_offset=0)

    assert len(result["calls"]["items"]) == 2
    assert result["calls"]["total"] == 5
    assert result["calls"]["next_offset"] == 2
    # Shapes and error windows are untouched by the calls page size.
    assert result["shapes"]["total"] == 1
    assert result["error_windows"]["total"] == 1


def test_observed_telemetry_shapes_are_scoped_to_operations_this_repo_was_seen_calling(store):
    # `observed_shape` carries no `repo_id` -- it is a vendor-wide baseline. The view joins it
    # in through the (vendor_id, operation_id) pairs this repository's own observed calls name,
    # so a shape recorded for an operation this repo never called must not leak in.
    store.record_observed_call(_observed_call(repo_id="r1", operation_id="PostCharges"))
    store.record_observed_shape(_shape(operation_id="PostCharges", field_path="/amount"))
    store.record_observed_shape(_shape(operation_id="PostRefunds", field_path="/status"))

    result = observed_telemetry(store, "r1")

    fields = {row["field_path"] for row in result["shapes"]["items"]}
    assert fields == {"/amount"}


def test_observed_telemetry_shapes_are_not_scoped_to_the_calls_page(store):
    """Shapes are joined through every operation this repository's calls have ever named, not
    just the ones on the current page of calls -- the two are independent questions, and a
    shape must not disappear because its call happened to sort onto page two.
    """
    store.record_observed_call(_observed_call(trace_id="t-a", operation_id="OpA"))
    store.record_observed_call(_observed_call(trace_id="t-b", operation_id="OpB"))
    store.record_observed_shape(_shape(operation_id="OpA", field_path="/a"))
    store.record_observed_shape(_shape(operation_id="OpB", field_path="/b"))

    result = observed_telemetry(store, "r1", calls_limit=1, calls_offset=0)

    fields = {row["field_path"] for row in result["shapes"]["items"]}
    assert fields == {"/a", "/b"}


def test_observed_telemetry_shapes_paginate_independently(store):
    for i in range(5):
        store.record_observed_shape(_shape(field_path=f"/f{i}"))
    store.record_observed_call(_observed_call())

    result = observed_telemetry(store, "r1", shapes_limit=2, shapes_offset=0)

    assert len(result["shapes"]["items"]) == 2
    assert result["shapes"]["total"] == 5
    assert result["shapes"]["next_offset"] == 2


def test_observed_telemetry_shape_join_makes_a_flat_number_of_queries_not_one_per_pair(
    store, monkeypatch
):
    """The N+1 this replaces issued one query per distinct `(vendor_id, operation_id)` pair a
    repository's calls named -- ten operations used to cost ten round trips for one page. The
    replacement makes exactly two: one `SELECT` for the page and one `count(*)` for the total,
    which is the "a separate count" the store's own contract promises -- flat at ten pairs and
    flat at a thousand, never one query per pair either way.
    """
    for i in range(10):
        store.record_observed_call(_observed_call(trace_id=f"t{i}", operation_id=f"Op{i}"))
        store.record_observed_shape(_shape(operation_id=f"Op{i}", field_path="/amount"))

    calls = _query_count(monkeypatch)
    result = observed_telemetry(store, "r1")

    shape_queries = [q for q in calls if "observed_shape" in q]
    assert len(shape_queries) == 2, f"expected exactly two shape queries, made {len(shape_queries)}"
    assert result["shapes"]["total"] == 10


def test_observed_telemetry_an_uncorrelated_call_does_not_crash_the_shape_join(store):
    # `operation_id` is '' for a span nothing could correlate, paired with `binding_rung`
    # 'unresolved'. An empty operation must not be asked of `observed_shapes`, which requires
    # a non-empty one.
    store.record_observed_call(
        _observed_call(operation_id="", binding_rung="unresolved", trace_id="t-uncorrelated")
    )

    result = observed_telemetry(store, "r1")

    assert result["calls"]["items"][0]["operation_id"] == ""
    assert result["calls"]["items"][0]["binding_rung"] == "unresolved"
    assert result["shapes"] == _EMPTY_PAGE


def test_observed_telemetry_reports_error_windows_for_one_repository(store):
    store.record_observed_error_window(_error_window(repo_id="r1"))
    store.record_observed_error_window(_error_window(repo_id="r2"))

    result = observed_telemetry(store, "r1")

    assert len(result["error_windows"]["items"]) == 1
    assert result["error_windows"]["items"][0]["repo_id"] == "r1"


def test_observed_telemetry_error_windows_paginate_independently(store):
    for i in range(5):
        store.record_observed_error_window(_error_window(status_class=f"{i}xx"))
    store.record_observed_call(_observed_call())

    result = observed_telemetry(store, "r1", error_windows_limit=2, error_windows_offset=0)

    assert len(result["error_windows"]["items"]) == 2
    assert result["error_windows"]["total"] == 5
    assert result["error_windows"]["next_offset"] == 2


def test_observed_telemetry_of_a_repository_with_no_traffic_is_all_empty(store):
    result = observed_telemetry(store, "never-observed")

    assert result == {
        "repo_id": "never-observed",
        "telemetry_attached_at": None,
        "calls": _EMPTY_PAGE,
        "shapes": _EMPTY_PAGE,
        "error_windows": _EMPTY_PAGE,
    }


# -- detector_accountability --------------------------------------------------------


def test_detector_accountability_groups_findings_by_detector(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding(site_a, detector="vendor-change", claim="c1"))
    store.insert_finding(_finding(site_b, detector="efficiency", claim="loop"))

    result = detector_accountability(store)

    names = {row["detector"] for row in result["detectors"]}
    assert names == {"vendor-change", "efficiency"}
    assert result["total_open_findings"] == 2


def test_detector_accountability_breaks_each_detector_down_by_rung(store):
    # The rung breakdown per detector is the point: a detector whose findings all rest on
    # 'static' is a different kind of claim from one reading telemetry.
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    site_c = store.upsert_call_site(_site(path="src/c.ts", line=3))
    store.insert_finding(_finding(site_a, detector="observed-drift", claim="c1", binding_rung="observed"))
    store.insert_finding(_finding(site_b, detector="observed-drift", claim="c2", binding_rung="observed"))
    store.insert_finding(_finding(site_c, detector="observed-drift", claim="c3", binding_rung="static"))

    result = detector_accountability(store)

    row = next(r for r in result["detectors"] if r["detector"] == "observed-drift")
    assert row["by_rung"] == {"observed": 2, "static": 1}
    assert row["total"] == 3


def test_detector_accountability_breaks_each_detector_down_by_claim_and_severity(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(
        _finding(site_a, detector="vendor-change", claim="removed", severity="breaking")
    )
    store.insert_finding(
        _finding(site_b, detector="vendor-change", claim="deprecated", severity="deprecation")
    )

    result = detector_accountability(store)

    row = next(r for r in result["detectors"] if r["detector"] == "vendor-change")
    assert row["by_claim"] == {"removed": 1, "deprecated": 1}
    assert row["by_severity"] == {"breaking": 1, "deprecation": 1}


def test_detector_accountability_excludes_findings_that_are_no_longer_open(store):
    # `open_findings` is the only findings read `GraphStore` offers, so this view -- like the
    # rest of the console -- cannot see a closed finding. Proven here so the limit is a tested
    # fact rather than an assumption the docstring merely asserts.
    site = store.upsert_call_site(_site())
    finding_id = store.insert_finding(_finding(site))
    store.set_finding_status(finding_id, "patched")

    result = detector_accountability(store)

    assert result["detectors"] == []
    assert result["total_open_findings"] == 0


def test_detector_accountability_cross_detector_rung_tally(store):
    # Cross-detector tally counts each open finding once across all detectors,
    # with explicit presence of every known rung (even zero counts).
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    site_c = store.upsert_call_site(_site(path="src/c.ts", line=3))
    store.insert_finding(_finding(site_a, detector="vendor-change", claim="c1", binding_rung="static"))
    store.insert_finding(_finding(site_b, detector="observed-drift", claim="c2", binding_rung="observed"))
    store.insert_finding(_finding(site_c, detector="efficiency", claim="c3", binding_rung="static"))

    result = detector_accountability(store)

    assert result["by_rung"]["static"] == 2
    assert result["by_rung"]["observed"] == 1
    assert result["by_rung"]["resolved"] == 0
    assert result["by_rung"]["unresolved"] == 0
    assert result["by_rung"]["unattributed"] == 0
    assert result["total_open_findings"] == 3


def test_detector_accountability_with_no_findings_is_empty_not_an_error(store):
    result = detector_accountability(store)

    assert result == {
        "repo_id": None,
        "detectors": [],
        "by_rung": {
            "static": 0,
            "resolved": 0,
            "observed": 0,
            "unresolved": 0,
            "unattributed": 0,
        },
        "total_open_findings": 0,
    }


# -- severity_rollup ----------------------------------------------------------------


def test_severity_rollup_counts_open_findings_per_severity(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    site_c = store.upsert_call_site(_site(path="src/c.ts", line=3))
    store.insert_finding(_finding(site_a, claim="c1", severity="breaking"))
    store.insert_finding(_finding(site_b, claim="c2", severity="breaking"))
    store.insert_finding(_finding(site_c, claim="c3", severity="warning"))

    result = severity_rollup(store)

    assert result["by_severity"] == {"breaking": 2, "warning": 1}
    assert result["total"] == 3


def test_severity_rollup_excludes_findings_that_are_no_longer_open(store):
    site = store.upsert_call_site(_site())
    finding_id = store.insert_finding(_finding(site))
    store.set_finding_status(finding_id, "patched")

    result = severity_rollup(store)

    assert result == {"by_severity": {}, "total": 0}


def test_severity_rollup_with_no_findings_is_empty_not_an_error(store):
    result = severity_rollup(store)

    assert result == {"by_severity": {}, "total": 0}


def test_severity_rollup_reaches_the_store_in_a_flat_number_of_queries(store, monkeypatch):
    """The defect this replaces read every open `Finding` into Python and tallied severities in
    a `Counter` -- one row materialised per finding for a question whose cardinality is the
    number of severities. Ten findings must not cost more round trips than one does.
    """
    for i in range(10):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site_id, claim=f"c{i}"))

    calls = _query_count(monkeypatch)
    result = severity_rollup(store)

    assert result["total"] == 10
    assert len(calls) <= 2, f"expected at most two queries for ten findings, made {len(calls)}"


# -- overview_summary ----------------------------------------------------------------


def test_overview_summary_tallies_vendors_as_a_real_group_by(store):
    stripe_a = store.upsert_call_site(_site(path="src/a.ts", line=1, vendor_id="stripe"))
    stripe_b = store.upsert_call_site(_site(path="src/b.ts", line=2, vendor_id="stripe"))
    shopify = store.upsert_call_site(
        _site(path="src/c.ts", line=3, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding(stripe_a, claim="c1"))
    store.insert_finding(_finding(stripe_b, claim="c2"))
    store.insert_finding(_finding(shopify, claim="c3"))

    result = overview_summary(store)

    vendors = {row["vendor_id"]: row["open_finding_count"] for row in result["vendors"]}
    assert vendors == {"stripe": 2, "shopify": 1}
    assert result["total_findings"] == 3


def test_overview_summary_total_is_bounded_but_the_vendor_distribution_is_not(store):
    """The caveat section 24.2 states in hard: a distribution must never be derived from a
    bounded page. Three findings against one vendor and two against another, with `bound=3`,
    must report a bounded `total_findings` of 3 while `vendors` still sums to the true
    population of 5 -- proving the breakdown was computed by its own unbounded `GROUP BY`
    rather than tallied from whichever rows the bounded count happened to touch.
    """
    for i in range(3):
        site_id = store.upsert_call_site(_site(path=f"src/a{i}.ts", line=i, vendor_id="stripe"))
        store.insert_finding(_finding(site_id, claim=f"stripe-{i}"))
    for i in range(2):
        site_id = store.upsert_call_site(
            _site(path=f"src/b{i}.ts", line=i, vendor_id="shopify", operation_id="GetOrders")
        )
        store.insert_finding(_finding(site_id, claim=f"shopify-{i}"))

    result = overview_summary(store, bound=3)

    assert result["total_findings"] == 3
    assert result["total_findings_bound"] == 3
    assert result["total_findings_bound_reached"] is True
    vendors = {row["vendor_id"]: row["open_finding_count"] for row in result["vendors"]}
    assert vendors == {"stripe": 3, "shopify": 2}
    assert sum(vendors.values()) == 5


def test_overview_summary_bound_not_reached_when_the_true_count_is_under_it(store):
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id))

    result = overview_summary(store, bound=1000)

    assert result["total_findings"] == 1
    assert result["total_findings_bound"] == 1000
    assert result["total_findings_bound_reached"] is False
    # `context_savings` rests on the same scan as `total_findings`: under the bound, it is the
    # true figure, and the flag that says so must agree with `total_findings_bound_reached`
    # rather than a reader having to infer one from the other.
    assert result["context_savings_bound_reached"] is False


def test_overview_summary_context_savings_is_derived_from_the_bounded_total(store):
    from sync.mcp.tools import _TOKENS_PER_AVOIDED_READ

    for i in range(4):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site_id, claim=f"c{i}"))

    result = overview_summary(store, bound=2)

    assert result["total_findings"] == 2
    assert result["context_savings"] == 2 * _TOKENS_PER_AVOIDED_READ
    # The defect this guards: `context_savings` understating past the bound is correct, but
    # rendering it bare, with nothing marking it as a floor, claims an exactness the truncated
    # scan behind it never produced -- the same failure `total_findings_bound_reached` exists to
    # name for the sibling figure in the same card.
    assert result["context_savings_bound_reached"] is True


def test_overview_summary_indexed_at_and_binding_source_reflect_every_open_finding(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    with store._connect().cursor() as cur:
        cur.execute(
            "UPDATE call_site SET indexed_at = %s WHERE id = %s",
            (datetime(2030, 1, 1, tzinfo=timezone.utc), site_b),
        )
    store.insert_finding(_finding(site_a, claim="c1", binding_rung="observed"))
    store.insert_finding(_finding(site_b, claim="c2", binding_rung="observed"))

    result = overview_summary(store)

    assert result["indexed_at"] == "2030-01-01T00:00:00+00:00"
    assert result["binding_source"] == "observed"


def test_overview_summary_binding_source_is_none_when_findings_disagree(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding(site_a, claim="c1", binding_rung="static"))
    store.insert_finding(_finding(site_b, claim="c2", binding_rung="observed"))

    result = overview_summary(store)

    assert result["binding_source"] is None


def test_overview_summary_feed_fetched_at_is_always_null(store):
    """The frozen `GraphSurface` this replaces is constructed with no `feed_fetched_at` anywhere
    in this deployment (`sync/api/__main__.py`), so the field this route has always reported was
    already always null; this view keeps reporting the same true absence rather than inventing a
    value the frozen surface never had either.
    """
    result = overview_summary(store)

    assert result["feed_fetched_at"] is None


def test_overview_summary_with_no_findings_is_empty_not_an_error(store):
    result = overview_summary(store)

    assert result == {
        "repo_id": None,
        "vendors": [],
        "total_findings": 0,
        "total_findings_bound": 1000,
        "total_findings_bound_reached": False,
        "indexed_at": None,
        "feed_fetched_at": None,
        "binding_source": None,
        "context_savings": 0,
        "context_savings_bound_reached": False,
        "repositories": [],
    }


def test_overview_summary_reaches_the_store_in_a_flat_number_of_queries(store, monkeypatch):
    """The defect this replaces read every open finding, looked up its call site one row at a
    time and counted vendors in a Python loop -- a route whose query count grew with the number
    of open findings. Ten open findings must cost the same handful of queries as one does.
    """
    for i in range(10):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site_id, claim=f"c{i}"))

    calls = _query_count(monkeypatch)
    result = overview_summary(store)

    assert result["total_findings"] == 10
    assert len(calls) <= 4, f"expected at most four queries for ten findings, made {len(calls)}"


# -- repository scope, across every view a console level below Codebase reads -----------------
#
# B92: repository scope is what every level under Codebase inherits, and an unscoped answer
# rendered under a repository heading is a false claim about that repository. Each view below
# takes an optional `repo_id` and echoes it back, so a payload says which scope it was computed
# in rather than leaving a render site to remember.


def _one_finding_per_repository(store) -> None:
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(
        _site(repo_id="r2", path="src/b.ts", line=2, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding(mine, claim="c1", severity="breaking"))
    store.insert_finding(_finding(theirs, claim="c2", severity="warning"))


def test_overview_summary_scoped_to_a_repository_counts_only_that_repository(store):
    _one_finding_per_repository(store)

    scoped = overview_summary(store, repo_id="r1")

    assert scoped["total_findings"] == 1
    assert scoped["vendors"] == [{"vendor_id": "stripe", "open_finding_count": 1}]
    assert scoped["repo_id"] == "r1"


def test_overview_summary_unscoped_still_answers_for_the_fleet_and_says_so(store):
    _one_finding_per_repository(store)

    fleet = overview_summary(store)

    assert fleet["total_findings"] == 2
    assert fleet["repo_id"] is None, "null is the fleet scope, and the payload has to carry it"


def test_overview_summary_unscoped_carries_per_repository_breakdown(store):
    _one_finding_per_repository(store)
    # Add a 3rd repository with an indexed call site but no findings
    store.upsert_call_site(_site(repo_id="r3", path="src/c.ts", line=1, vendor_id="twilio"))

    fleet = overview_summary(store)

    assert "repositories" in fleet
    repos = {r["repo_id"]: r for r in fleet["repositories"]}
    assert repos["r1"] == {"repo_id": "r1", "open_finding_count": 1, "vendors": ["stripe"]}
    assert repos["r2"] == {"repo_id": "r2", "open_finding_count": 1, "vendors": ["shopify"]}
    assert repos["r3"] == {"repo_id": "r3", "open_finding_count": 0, "vendors": []}

    scoped = overview_summary(store, repo_id="r1")
    assert "repositories" not in scoped


def test_severity_rollup_scoped_to_a_repository(store):
    _one_finding_per_repository(store)

    assert severity_rollup(store, repo_id="r1") == {"by_severity": {"breaking": 1}, "total": 1}
    assert severity_rollup(store)["total"] == 2


def test_detector_accountability_scoped_to_a_repository(store):
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding(mine, claim="c1", detector="vendor-change"))
    store.insert_finding(_finding(theirs, claim="c2", detector="status-rate", binding_rung="observed"))

    scoped = detector_accountability(store, repo_id="r1")

    assert [entry["detector"] for entry in scoped["detectors"]] == ["vendor-change"]
    assert scoped["total_open_findings"] == 1
    assert scoped["repo_id"] == "r1"
    assert detector_accountability(store)["total_open_findings"] == 2


# -- vendor_findings -----------------------------------------------------------------------
#
# The API Services level's own page. `GraphSurface.whats_at_risk` answers the same question for
# an agent and cannot answer it for a repository -- `sync/mcp/tools.py` is frozen and its rows
# carry no `repo_id` -- which is the same reason `overview_summary` replaced it on `/api/overview`.


def test_vendor_findings_returns_the_console_rows_for_one_vendor(store):
    change_id = store.upsert_vendor_change(_change(kind="response-property-removed"))
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id, vendor_change_id=change_id, severity="breaking"))

    page = vendor_findings(store, "stripe")

    assert page["total"] == 1
    row = page["items"][0]
    assert row["file"] == "src/billing.ts"
    assert row["line"] == 42
    assert row["symbol"] == "stripe.charges.create"
    assert row["operation"] == "PostCharges"
    assert row["vendor"] == "stripe"
    assert row["change_kind"] == "response-property-removed"
    assert row["severity"] == "breaking"
    assert row["binding_source"] == "static"
    assert isinstance(row["finding_id"], str)


def test_vendor_findings_omits_another_vendors_finding(store):
    stripe = store.upsert_call_site(_site(path="src/a.ts", line=1))
    shopify = store.upsert_call_site(
        _site(path="src/b.ts", line=2, vendor_id="shopify", operation_id="GetOrders")
    )
    store.insert_finding(_finding(stripe, claim="c1"))
    store.insert_finding(_finding(shopify, claim="c2"))

    assert vendor_findings(store, "stripe")["total"] == 1


def test_vendor_findings_scoped_to_a_repository(store):
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding(mine, claim="c1"))
    store.insert_finding(_finding(theirs, claim="c2"))

    scoped = vendor_findings(store, "stripe", repo_id="r1")

    assert scoped["total"] == 1
    assert scoped["repo_id"] == "r1"
    assert vendor_findings(store, "stripe")["total"] == 2


def test_findings_page_scoped_to_repository_across_vendors(store):
    """The Codebase Overview findings view: all open findings for ONE selected codebase across all vendors."""
    stripe_r1 = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1, vendor_id="stripe"))
    twilio_r1 = store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", line=2, vendor_id="twilio", operation_id="SendSms"))
    stripe_r2 = store.upsert_call_site(_site(repo_id="r2", path="src/c.ts", line=3, vendor_id="stripe"))

    store.insert_finding(_finding(stripe_r1, claim="c1"))
    store.insert_finding(_finding(twilio_r1, claim="c2"))
    store.insert_finding(_finding(stripe_r2, claim="c3"))

    page = findings_page(store, repo_id="r1")

    assert page["total"] == 2
    assert page["repo_id"] == "r1"
    assert {row["vendor"] for row in page["items"]} == {"stripe", "twilio"}

    fleet_page = findings_page(store)
    assert fleet_page["total"] == 3
    assert fleet_page["repo_id"] is None


def test_vendor_findings_scoped_by_severity_and_by_path_prefix(store):
    billing = store.upsert_call_site(_site(path="src/billing/pay.ts", line=1))
    other = store.upsert_call_site(_site(path="src/other/pay.ts", line=2))
    store.insert_finding(_finding(billing, claim="c1", severity="breaking"))
    store.insert_finding(_finding(other, claim="c2", severity="warning"))

    assert vendor_findings(store, "stripe", severity="breaking")["total"] == 1
    assert vendor_findings(store, "stripe", path="src/billing")["total"] == 1


def test_vendor_findings_names_the_ordering_it_applied_even_when_nobody_chose_one(store):
    """The envelope carries the ordering because the screen has to state it.

    An unordered table is not unordered -- it is in the order Sync raised the findings, and it said
    so nowhere. A reader who cannot see the ordering cannot tell a page boundary that moved from a
    finding that changed, which is the same class of unsayable claim as a total counted off a page.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id))

    assert vendor_findings(store, "stripe")["order"] == "first-seen"
    assert vendor_findings(store, "stripe", order="severity")["order"] == "severity"


def test_vendor_findings_carries_the_severity_rank_it_would_order_by(store):
    """The rank travels in the payload rather than being restated in TypeScript.

    It is a declared judgement, not a fact the graph stores, so B100 requires it be put somewhere a
    reader can see -- and the console cannot import Python. The two ways to get it on screen are a
    second copy in `types.ts` held to this one by a guard, or the query sending the rank it used.
    The second is strictly more honest: the sentence a reader gets is derived from the ordering that
    actually ran, so there is no version of this where the screen names an order the rows are not
    in. It rides every page, chosen or not, because the control has to describe the choice before it
    is made.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id))

    assert vendor_findings(store, "stripe")["severity_order"] == list(SEVERITY_ORDER)
    assert vendor_findings(store, "stripe", order="severity")["severity_order"] == list(SEVERITY_ORDER)


def test_vendor_findings_orders_by_severity_in_sql_ahead_of_its_own_limit(store):
    """The page has to be the first page of the ordered set, not an ordering of the first page.
    Inserted least-severe-first so a Python sort over the page window could not produce this.
    """
    for i, severity in enumerate(["info", "deprecation", "breaking"]):
        site_id = store.upsert_call_site(
            _site(path=f"src/{i}.ts", line=i, content_hash=f"hash-{i}")
        )
        store.insert_finding(_finding(site_id, claim=f"c{i}", severity=severity))

    page = vendor_findings(store, "stripe", order="severity", limit=1)

    assert [row["severity"] for row in page["items"]] == ["breaking"]
    assert page["total"] == 3, "the total is the ordered set's, not the page's"


def test_vendor_findings_falls_back_to_the_default_ordering_and_says_which_it_used(store):
    """`order` reaches this from a query string, so an unrecognised value is a boundary condition
    rather than a bug. It resolves to the default rather than raising, and the envelope reports the
    ordering that was *applied* -- so a hand-edited URL cannot leave the screen naming an ordering
    the rows are not in. The store raises on the same value, because a typo in our own call site
    has no echo to catch it.
    """
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id))

    page = vendor_findings(store, "stripe", order="severty")

    assert page["order"] == "first-seen"


def test_vendor_findings_pages_with_a_real_sql_limit(store):
    for i in range(5):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site_id, claim=f"c{i}"))

    page = vendor_findings(store, "stripe", limit=2, offset=1)

    assert page["total"] == 5, "the total is the filtered set, never the page"
    assert len(page["items"]) == 2
    assert page["next_offset"] == 3


def test_vendor_findings_last_page_has_no_next_offset(store):
    site_id = store.upsert_call_site(_site())
    store.insert_finding(_finding(site_id))

    assert vendor_findings(store, "stripe", limit=50)["next_offset"] is None


def test_vendor_findings_envelope_carries_the_pages_own_rung(store):
    site_a = store.upsert_call_site(_site(path="src/a.ts", line=1))
    site_b = store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.insert_finding(_finding(site_a, claim="c1", binding_rung="static"))
    store.insert_finding(_finding(site_b, claim="c2", binding_rung="observed"))

    assert vendor_findings(store, "stripe")["binding_source"] is None, "two rungs disagree"


def test_vendor_findings_envelope_rung_is_scoped_with_the_rows_it_describes(store):
    """The envelope's rung describes the page. A rung computed across the fleet while the rows
    were narrowed to one repository would be provenance for a set the reader cannot see.
    """
    mine = store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    theirs = store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    store.insert_finding(_finding(mine, claim="c1", binding_rung="static"))
    store.insert_finding(_finding(theirs, claim="c2", binding_rung="observed"))

    assert vendor_findings(store, "stripe", repo_id="r1")["binding_source"] == "static"


def test_vendor_findings_of_a_vendor_with_nothing_open_is_an_empty_page(store):
    page = vendor_findings(store, "nobody")

    assert page["total"] == 0
    assert page["items"] == []
    assert page["binding_source"] is None
    assert page["indexed_at"] is None


def test_vendor_findings_reaches_the_store_in_a_flat_number_of_queries(store, monkeypatch):
    for i in range(10):
        site_id = store.upsert_call_site(_site(path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site_id, claim=f"c{i}"))

    calls = _query_count(monkeypatch)
    page = vendor_findings(store, "stripe", limit=2)

    assert page["total"] == 10
    assert len(calls) <= 3, f"expected at most three queries for ten findings, made {len(calls)}"

# -- narrowing a long surface ---------------------------------------------------
#
# A call-site table over a real customer repository is thousands of rows long, and the two
# questions an operator actually arrives with -- "which repository" and "which part of the
# tree" -- are both facts the graph already stores. Both narrowings are real SQL predicates
# with matching denominators, for the reason `binding_surface` already pages in SQL: a filter
# applied to whichever page arrived reports a total drawn from a set it did not filter.


def test_binding_surface_narrows_call_sites_to_a_path_prefix(store):
    store.upsert_call_site(_site(path="src/billing/charge.ts", line=1))
    store.upsert_call_site(_site(path="src/reporting/export.ts", line=2))

    result = binding_surface(store, "stripe", "PostCharges", path_prefix="src/billing/")

    assert [row["path"] for row in result["call_sites"]["items"]] == ["src/billing/charge.ts"]


def test_binding_surface_call_sites_total_follows_the_path_prefix(store):
    """The denominator is what tells a reader whether the page in front of them is the whole
    filtered answer or the first window on it. Left unfiltered beside a filtered page it
    reports a set the page is not drawn from.
    """
    store.upsert_call_site(_site(path="src/billing/charge.ts", line=1))
    store.upsert_call_site(_site(path="src/reporting/export.ts", line=2))

    result = binding_surface(store, "stripe", "PostCharges", path_prefix="src/billing/")

    assert result["call_sites"]["total"] == 1


def test_binding_surface_path_prefix_leaves_vendor_changes_untouched(store):
    """A vendor change has no position in the customer's codebase -- `path_ptr` is a pointer
    into the vendor's own specification. Narrowing the call sites to a directory must not be
    read as narrowing what the vendor changed.
    """
    store.upsert_call_site(_site(path="src/reporting/export.ts"))
    store.upsert_vendor_change(_change())

    result = binding_surface(store, "stripe", "PostCharges", path_prefix="src/billing/")

    assert result["call_sites"]["total"] == 0
    assert result["changes"]["total"] == 1


def test_binding_surface_path_prefix_combines_with_repo_id(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/billing/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/billing/b.ts", line=2))

    result = binding_surface(
        store, "stripe", "PostCharges", repo_id="r1", path_prefix="src/billing/"
    )

    assert [row["path"] for row in result["call_sites"]["items"]] == ["src/billing/a.ts"]
    assert result["call_sites"]["total"] == 1


def test_binding_surface_reports_which_repositories_hold_a_call_site(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r1", path="src/b.ts", line=2))
    store.upsert_call_site(_site(repo_id="r2", path="src/c.ts", line=3))

    result = binding_surface(store, "stripe", "PostCharges")

    assert result["repositories"] == [
        {"repo_id": "r1", "call_site_count": 2},
        {"repo_id": "r2", "call_site_count": 1},
    ]


def test_binding_surface_repositories_ignore_the_filters_they_are_the_options_for(store):
    """The facet is the option list a repository filter is set from. Narrowed by the filter it
    sets, it collapses to whatever is already selected and there is no way back to the others.
    Its counts are therefore counts over the whole operation, not over the filtered page.
    """
    store.upsert_call_site(_site(repo_id="r1", path="src/billing/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/reporting/b.ts", line=2))

    result = binding_surface(
        store, "stripe", "PostCharges", repo_id="r1", path_prefix="src/billing/"
    )

    assert result["repositories"] == [
        {"repo_id": "r1", "call_site_count": 1},
        {"repo_id": "r2", "call_site_count": 1},
    ]


def test_binding_surface_on_an_operation_nobody_calls_reports_no_repositories(store):
    result = binding_surface(store, "stripe", "PostCharges")

    assert result["repositories"] == []


def test_binding_surface_a_rung_other_than_static_still_reports_the_repositories(store):
    """The empty call-site page that answers a non-static rung is the filtered answer, not the
    absence of any call site. The facet says so: a reader looking at nothing can still see the
    operation is called from two repositories, which is what tells the two apart.
    """
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))

    result = binding_surface(store, "stripe", "PostCharges", binding_rung="observed")

    assert result["call_sites"]["items"] == []
    assert [row["repo_id"] for row in result["repositories"]] == ["r1", "r2"]


def test_severity_rollup_narrows_to_one_vendor(store):
    stripe_site = store.upsert_call_site(_site(vendor_id="stripe", path="src/a.ts", line=1))
    twilio_site = store.upsert_call_site(_site(vendor_id="twilio", path="src/b.ts", line=2))
    store.insert_finding(_finding(stripe_site, claim="c1", severity="breaking"))
    store.insert_finding(_finding(twilio_site, claim="c2", severity="warning"))

    assert severity_rollup(store, vendor_id="stripe") == {
        "by_severity": {"breaking": 1},
        "total": 1,
    }


def test_severity_rollup_for_a_vendor_with_nothing_open_is_zero_not_the_fleet_total(store):
    """A vendor screen asking for a breakdown it has no findings for must not fall back to the
    fleet's -- an unscoped answer served for a scoped question is the failure mode a filter
    that silently does nothing always has.
    """
    site = store.upsert_call_site(_site(vendor_id="stripe"))
    store.insert_finding(_finding(site, severity="breaking"))

    assert severity_rollup(store, vendor_id="twilio") == {"by_severity": {}, "total": 0}


def test_severity_rollup_composes_the_repository_scope_with_the_vendor(store):
    """The two narrow together. A vendor screen opened inside a selected repository asks for
    that vendor *in* that repository -- either scope alone answers a question nobody asked and
    renders it under a heading that claims the other.
    """
    here = store.upsert_call_site(_site(repo_id="r1", vendor_id="stripe", path="src/a.ts", line=1))
    elsewhere = store.upsert_call_site(
        _site(repo_id="r2", vendor_id="stripe", path="src/b.ts", line=2)
    )
    other_vendor = store.upsert_call_site(
        _site(repo_id="r1", vendor_id="twilio", path="src/c.ts", line=3)
    )
    store.insert_finding(_finding(here, claim="c1", severity="breaking"))
    store.insert_finding(_finding(elsewhere, claim="c2", severity="warning"))
    store.insert_finding(_finding(other_vendor, claim="c3", severity="warning"))

    both = severity_rollup(store, repo_id="r1", vendor_id="stripe")

    assert both == {"by_severity": {"breaking": 1}, "total": 1}
    assert severity_rollup(store, vendor_id="stripe")["total"] == 2, "vendor alone spans repos"
    assert severity_rollup(store, repo_id="r1")["total"] == 2, "repository alone spans vendors"


def test_severity_rollup_total_and_breakdown_are_two_aggregates_under_one_scope(store):
    """The total is its own SQL read rather than the sum of the breakdown beside it. Two numbers
    that cannot contradict each other are two numbers that can never reveal one of them is wrong.
    """
    for i, severity in enumerate(("breaking", "warning", "warning")):
        site = store.upsert_call_site(_site(repo_id="r1", path=f"src/{i}.ts", line=i))
        store.insert_finding(_finding(site, claim=f"c{i}", severity=severity))

    result = severity_rollup(store, repo_id="r1", vendor_id="stripe")

    assert result["by_severity"] == {"breaking": 1, "warning": 2}
    assert result["total"] == 3


# -- repo_settings ------------------------------------------------------------------


def test_repo_settings_returns_defaults_for_unconfigured_repo(store):
    result = repo_settings(store, "github.com/acme/new-repo")

    assert result["repo_id"] == "github.com/acme/new-repo"
    assert result["merge_policy"] == "when_checks_pass"
    assert result["merge_method"] == "squash"
    assert result["base_branch"] == "main"
    assert result["allowed_merge_policies"] == ["never", "when_checks_pass"]
    assert result["allowed_merge_methods"] == ["squash", "merge", "rebase"]
    assert "immediate" in result["merge_policy_refusals"]
    assert result["updated_at"] is None


def test_repo_settings_persists_and_retrieves_settings(store):
    store.upsert_repo_settings(
        RepoSettings(
            repo_id="github.com/acme/configured-repo",
            merge_policy="never",
            merge_method="rebase",
            base_branch="develop",
        )
    )

    result = repo_settings(store, "github.com/acme/configured-repo")

    assert result["repo_id"] == "github.com/acme/configured-repo"
    assert result["merge_policy"] == "never"
    assert result["merge_method"] == "rebase"
    assert result["base_branch"] == "develop"
    assert result["updated_at"] is not None


def test_upsert_repo_settings_refuses_immediate_merge_policy(store):
    # System invariant: "nothing reaches a pull request unverified".
    # An immediate merge policy without verification is explicitly refused and raises ValueError.
    with pytest.raises(ValueError, match="violates invariant 'nothing reaches a pull request unverified'"):
        store.upsert_repo_settings(
            RepoSettings.model_construct(
                repo_id="github.com/acme/bad-repo",
                merge_policy="immediate",
                merge_method="squash",
                base_branch="main",
                merge_policy_refusals={"immediate": "Refused: violates invariant 'nothing reaches a pull request unverified'"},
            )
        )


def test_upsert_repo_settings_refuses_invalid_merge_method(store):
    with pytest.raises(ValueError, match="Invalid merge_method"):
        store.upsert_repo_settings(
            RepoSettings.model_construct(
                repo_id="github.com/acme/bad-repo",
                merge_policy="when_checks_pass",
                merge_method="fast-forward-only",
                base_branch="main",
                merge_policy_refusals={},
            )
        )


def test_vendor_change_volume_aggregates_timeline_and_kinds(store):
    c1 = VendorChange(
        id="c1",
        vendor_id="stripe",
        kind="breaking",
        severity="breaking",
        operation_id="PostCharges",
        path_ptr="/v1/charges",
        from_version="v1",
        to_version="v2",
        source="oasdiff",
        detected_at=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
    )
    c2 = VendorChange(
        id="c2",
        vendor_id="stripe",
        kind="parameter_removed",
        severity="warning",
        operation_id="PostCharges",
        path_ptr="/v1/charges",
        from_version="v2",
        to_version="v3",
        source="oasdiff",
        detected_at=datetime(2026, 6, 20, 14, 0, tzinfo=timezone.utc),
    )
    c3 = VendorChange(
        id="c3",
        vendor_id="stripe",
        kind="breaking",
        severity="breaking",
        operation_id="GetCharges",
        path_ptr="/v1/charges",
        from_version="v3",
        to_version="v4",
        source="oasdiff",
        detected_at=datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
    )
    c4 = VendorChange(
        id="c4",
        vendor_id="openai",
        kind="endpoint_superseded",
        severity="deprecation",
        operation_id="CreateCompletion",
        path_ptr="/v1/completions",
        from_version="v1",
        to_version="v2",
        source="oasdiff",
        detected_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
    )

    store.upsert_vendor_change(c1)
    store.upsert_vendor_change(c2)
    store.upsert_vendor_change(c3)
    store.upsert_vendor_change(c4)

    stripe_vol = vendor_change_volume(store, "stripe")
    assert stripe_vol["vendor_id"] == "stripe"
    assert stripe_vol["total_changes"] == 3
    assert stripe_vol["by_kind"] == {"breaking": 2, "parameter_removed": 1}
    assert stripe_vol["by_severity"] == {"breaking": 2, "warning": 1}
    assert len(stripe_vol["timeline"]) == 1
    assert stripe_vol["timeline"][0]["count"] == 3
    assert stripe_vol["timeline"][0]["by_kind"] == {"breaking": 2, "parameter_removed": 1}

    openai_vol = vendor_change_volume(store, "openai")
    assert openai_vol["vendor_id"] == "openai"
    assert openai_vol["total_changes"] == 1
    assert openai_vol["by_kind"] == {"endpoint_superseded": 1}

    empty_vol = vendor_change_volume(store, "nonexistent")
    assert empty_vol["vendor_id"] == "nonexistent"
    assert empty_vol["total_changes"] == 0
    assert empty_vol["timeline"] == []


# --- Decision 29: operations you call, with site counts and rungs ---------------------------
#
# The vendor page leads with exposure. What it leads with is this: which of a vendor's
# operations this codebase actually calls, how many places call each, and on what evidence.


def test_vendor_operation_exposure_counts_call_sites_per_operation(store):
    store.upsert_call_site(_site(path="src/a.ts", line=1))
    store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.upsert_call_site(_site(operation_id="GetCharges", path="src/c.ts", line=3))

    result = vendor_operation_exposure(store, "stripe")

    assert [(row["operation_id"], row["call_site_count"]) for row in result["operations"]] == [
        ("PostCharges", 2),
        ("GetCharges", 1),
    ]


def test_vendor_operation_exposure_orders_by_exposure_then_name(store):
    """Most-called first, because the screen's question is where the exposure is. Ties break on
    the operation id so the order is total rather than whatever the planner returned."""
    store.upsert_call_site(_site(operation_id="B", path="src/a.ts", line=1))
    store.upsert_call_site(_site(operation_id="A", path="src/b.ts", line=2))
    store.upsert_call_site(_site(operation_id="C", path="src/c.ts", line=3))
    store.upsert_call_site(_site(operation_id="C", path="src/d.ts", line=4))

    result = vendor_operation_exposure(store, "stripe")

    assert [row["operation_id"] for row in result["operations"]] == ["C", "A", "B"]


def test_vendor_operation_exposure_narrows_to_one_repository(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))

    result = vendor_operation_exposure(store, "stripe", repo_id="r1")

    assert result["operations"] == [
        {
            "operation_id": "PostCharges",
            "call_site_count": 1,
            "repository_count": 1,
            "binding_rung": "static",
            "observed": None,
        }
    ]


def test_vendor_operation_exposure_reports_how_many_repositories_call_an_operation(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))

    result = vendor_operation_exposure(store, "stripe")

    assert result["operations"][0]["repository_count"] == 2


def test_vendor_operation_exposure_carries_the_static_rung_on_every_row(store):
    """A call site is what the static index found. The rung is a column rather than a join, and
    an exposure row that could not name one would be unattributable."""
    store.upsert_call_site(_site())

    result = vendor_operation_exposure(store, "stripe")

    assert result["operations"][0]["binding_rung"] == "static"


def test_vendor_operation_exposure_excludes_a_retracted_call_site(store):
    """A call the last index pass stopped finding is not current exposure."""
    store.upsert_call_site(_site(path="src/a.ts", line=1))
    store.upsert_call_site(_site(path="src/b.ts", line=2))
    store.replace_call_sites("r1", [_site(path="src/a.ts", line=1)])

    result = vendor_operation_exposure(store, "stripe")

    assert result["operations"][0]["call_site_count"] == 1


def test_vendor_operation_exposure_on_a_vendor_nobody_calls_is_empty(store):
    result = vendor_operation_exposure(store, "stripe")

    assert result["operations"] == []


def test_vendor_operation_exposure_reports_observed_as_never_measured_without_a_repository(store):
    """Telemetry attaches per repository. Asked across every repository, whether an operation was
    observed has no single answer, and `None` says so rather than defaulting to `False`."""
    store.upsert_call_site(_site())

    result = vendor_operation_exposure(store, "stripe")

    assert result["operations"][0]["observed"] is None
    assert result["telemetry_attached_at"] is None


def test_vendor_operation_exposure_separates_never_measured_from_not_observed(store):
    """B157's distinction, on this screen. With telemetry attached, an operation no span named is
    a measured `False`. Without it, every operation is `None` -- nothing looked."""
    store.upsert_call_site(_site(operation_id="PostCharges", path="src/a.ts", line=1))
    store.upsert_call_site(_site(operation_id="GetCharges", path="src/b.ts", line=2))
    store.mark_telemetry_attached("r1", SEEN)
    store.record_observed_call(_observed_call(operation_id="PostCharges"))

    result = vendor_operation_exposure(store, "stripe", repo_id="r1")

    observed = {row["operation_id"]: row["observed"] for row in result["operations"]}
    assert observed == {"PostCharges": True, "GetCharges": False}
    assert result["telemetry_attached_at"] == SEEN.isoformat()

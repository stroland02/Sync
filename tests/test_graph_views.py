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
import time
from datetime import datetime, timezone

import psycopg
import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, ObservedShape, RepoSettings, VendorChange
from sync.core.models import FINDING_RUNGS, SEVERITY_ORDER
from sync.dashboard.graph_views import (
    binding_surface,
    detector_accountability,
    findings_by_kind_over_time,
    findings_page,
    index_coverage,
    observed_telemetry,
    overview_summary,
    repo_settings,
    repository_graph,
    repository_graph,
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
        "bindings_by_rung": {
            "static": 0,
            "resolved": 0,
            "observed": 0,
            "unresolved": 0,
            "unattributed": 0,
        },
        "last_index_run": None,
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
    # Five since `bindings_by_rung` landed, and the bound is what this guard is about rather than
    # the number: each of the five is a single aggregate or `GROUP BY` whose cost does not move
    # with how many findings are open, so ten and ten thousand cost the same five.
    assert len(calls) <= 5, f"expected at most five queries for ten findings, made {len(calls)}"


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


class TestRepositoryGraph:
    """The dependency graph the Overview draws: this repository's call sites, out to its vendors.

    Owner decision 2 puts this panel beside the fact tiles on the first screen, so it is not
    optional. `DependencyCanvas` already draws it; what did not exist was one scoped read that
    answers the whole graph, and fanning the console out per vendor and per operation would issue
    a query per node to draw one picture.
    """

    def test_a_repository_with_no_call_sites_draws_no_edges_and_says_so(self, store):
        # Whole-dict rather than field-by-field on purpose: this pins the contract, so a field
        # added to the payload has to be added here deliberately instead of arriving unnoticed.
        # `indexed_at` is `None` and `off_path` is nought, and those say different things -- the
        # first is "no call site row has ever existed here", which cannot tell a never-run index
        # from one that found nothing; the second is a read that happened and returned none.
        assert repository_graph(store, "r1") == {
            "repo_id": "r1",
            "vendors": [],
            "bindings": [],
            "observed_bindings": [],
            "off_path": {"unresolved": 0, "unattributed": 0},
            "rungs": list(FINDING_RUNGS),
            "indexed_at": None,
            "total_bindings": 0,
            "truncated": False,
        }

    def test_every_binding_carries_the_rung_it_came_from(self, store):
        store.replace_call_sites("r1", [_site()])

        graph = repository_graph(store, "r1")

        # `CLAUDE.md`: every binding carries its rung, and so does every artifact derived from it.
        # A call site is what the static index found -- nothing here rests on a resolution or a
        # correlation -- so the rung is `static` and is never blended upward by this view.
        assert [b["binding_rung"] for b in graph["bindings"]] == ["static"]

    def test_a_binding_names_the_position_a_reader_would_open(self, store):
        store.replace_call_sites("r1", [_site()])

        binding = repository_graph(store, "r1")["bindings"][0]

        assert binding["vendor_id"] == "stripe"
        assert binding["operation_id"] == "PostCharges"
        assert binding["path"] == "src/billing.ts"
        assert binding["line"] == 42
        assert binding["symbol"] == "stripe.charges.create"

    def test_a_retracted_call_site_is_not_a_place_this_code_calls_the_vendor(self, store):
        store.replace_call_sites("r1", [_site()])
        store.replace_call_sites("r1", [])

        # Retraction is the difference between exposure and history. A position the last index
        # pass stopped finding is not somewhere this codebase calls the vendor now, and drawing
        # it would show a reader an edge they cannot act on.
        assert repository_graph(store, "r1")["bindings"] == []

    def test_another_repository_s_call_sites_are_not_drawn_here(self, store):
        store.replace_call_sites("r1", [_site()])
        store.replace_call_sites("r2", [_site(repo_id="r2", path="other/pay.ts")])

        paths = [b["path"] for b in repository_graph(store, "r1")["bindings"]]

        assert paths == ["src/billing.ts"]

    def test_a_vendor_reports_its_call_site_count_and_when_it_was_last_indexed(self, store):
        store.replace_call_sites("r1", [_site(), _site(line=90, operation_id="GetCharges")])

        vendors = repository_graph(store, "r1")["vendors"]

        assert len(vendors) == 1
        assert vendors[0]["vendor_id"] == "stripe"
        assert vendors[0]["indexed_call_sites"] == 2
        # Staleness, never a promise of currency -- `index_coverage` carries that argument and
        # this view repeats its fact rather than deriving an age the response would date.
        assert vendors[0]["last_indexed"] is not None

    def test_the_row_bound_is_declared_rather_than_silently_cutting_the_picture(self, store):
        store.replace_call_sites("r1", [_site(line=n) for n in range(1, 6)])

        graph = repository_graph(store, "r1", limit=2)

        # A graph quietly missing edges is a graph that lies about a codebase's exposure. The
        # bound is reported with the total it was applied to, so the console can say the picture
        # is partial instead of drawing a smaller codebase than the one that exists.
        assert len(graph["bindings"]) == 2
        assert graph["total_bindings"] == 5
        assert graph["truncated"] is True


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


class TestOverviewBindingsByRung:
    """Dashboard 2's source: open findings tallied by the rung their binding was established at.

    `docs/superpowers/plans/2026-08-18-dashboards.md` names `/api/overview` as where this comes
    from, and its standing rule is that a count of bindings is not a count of bindings -- it is a
    count *at a rung*, and the rung goes on the chart.
    """

    def test_every_rung_in_the_vocabulary_is_present_even_at_nought(self, store):
        """A rung absent from the payload and a rung at nought are different claims, and a chart
        that stacks five segments cannot tell them apart from a dict missing three keys. The
        vocabulary is closed, so the whole of it is reported."""
        by_rung = overview_summary(store)["bindings_by_rung"]

        assert by_rung == {
            "static": 0,
            "resolved": 0,
            "observed": 0,
            "unresolved": 0,
            "unattributed": 0,
        }

    def test_it_tallies_each_finding_at_the_rung_it_was_bound_at(self, store):
        site = store.upsert_call_site(_site())
        store.insert_finding(_finding(site, binding_rung="static"))
        store.insert_finding(_finding(site, claim="deprecation", binding_rung="observed"))

        by_rung = overview_summary(store)["bindings_by_rung"]

        assert by_rung["static"] == 1
        assert by_rung["observed"] == 1
        assert by_rung["resolved"] == 0

    def test_the_distribution_narrows_with_the_scope_it_is_rendered_under(self, store):
        one = store.upsert_call_site(_site(repo_id="r1"))
        two = store.upsert_call_site(_site(repo_id="r2", path="other/pay.ts"))
        store.insert_finding(_finding(one, binding_rung="static"))
        store.insert_finding(_finding(two, binding_rung="observed"))

        # A fleet-wide distribution rendered under one repository's name is a false claim about
        # that repository -- the same reason `repo_id` is echoed back on this payload.
        scoped = overview_summary(store, repo_id="r1")["bindings_by_rung"]

        assert scoped["static"] == 1
        assert scoped["observed"] == 0

    def test_the_distribution_is_not_bounded_by_the_total_beside_it(self, store):
        """`total_findings` stops counting at its bound; this must not. A distribution derived
        from a bounded page is the distribution of whichever rows the ordering reached, which
        `overview_summary`'s own docstring refuses for the vendor breakdown for the same reason."""
        site = store.upsert_call_site(_site())
        for i in range(5):
            store.insert_finding(_finding(site, claim=f"k{i}", binding_rung="static"))

        payload = overview_summary(store, bound=2)

        assert payload["total_findings_bound_reached"] is True
        assert payload["bindings_by_rung"]["static"] == 5


# --- Dashboard 1: findings by kind over time -------------------------------------------------
#
# The product's own output, dated. The trap this set exists to hold is that `created_at` is when
# Sync first RECORDED a finding, not when the vendor published the change behind it, and a reader
# looking at a bar chart of dates will assume the second.


def _record_finding_on(store, finding_id: str, day: str) -> None:
    """Backdate a finding. `created_at` defaults to `now()` and the writer takes no override, so
    dated history cannot be built any other way."""
    store._connect().execute(
        "UPDATE finding SET created_at = %s::timestamptz WHERE id = %s", (day, finding_id)
    )


def test_findings_by_kind_over_time_buckets_by_the_day_a_finding_was_recorded(store):
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    a = store.insert_finding(_finding(sites[0], claim="c1", severity="breaking"))
    b = store.insert_finding(_finding(sites[0], claim="c2", severity="warning"))
    _record_finding_on(store, a, "2026-08-16T04:00:00+00:00")
    _record_finding_on(store, b, "2026-08-17T04:00:00+00:00")

    result = findings_by_kind_over_time(store)

    assert result["days"] == [
        {"day": "2026-08-16", "counts": {"breaking": 1}},
        {"day": "2026-08-17", "counts": {"warning": 1}},
    ]


def test_findings_by_kind_over_time_echoes_the_closed_vocabulary(store):
    """The severities are a closed set, so a reader can tell a kind at nought from a kind that
    does not exist. The view names all five rather than only those that occurred."""
    result = findings_by_kind_over_time(store)

    assert result["severities"] == list(SEVERITY_ORDER)


def test_findings_by_kind_over_time_omits_a_severity_no_finding_carried_that_day(store):
    """A day's dict holds only what happened. Filling every day with five zeroes would make the
    payload assert four measurements nobody took."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    a = store.insert_finding(_finding(sites[0], claim="c1", severity="breaking"))
    _record_finding_on(store, a, "2026-08-16T04:00:00+00:00")

    result = findings_by_kind_over_time(store)

    assert result["days"][0]["counts"] == {"breaking": 1}


def test_findings_by_kind_over_time_counts_a_finding_that_has_since_closed(store):
    """A time series of only still-open findings would rewrite its own history as work gets done:
    yesterday's bar would shrink every time somebody merged a patch. This counts what Sync
    produced, and reports separately how much of it is still open."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    a = store.insert_finding(_finding(sites[0], claim="c1", severity="breaking", status="patched"))
    _record_finding_on(store, a, "2026-08-16T04:00:00+00:00")

    result = findings_by_kind_over_time(store)

    assert result["total"] == 1
    assert result["still_open"] == 0


def test_findings_by_kind_over_time_carries_the_rungs_its_findings_rest_on(store):
    """Every derived figure carries its rung. A bar chart cannot show one per bar without becoming
    unreadable, so the window's rung composition travels beside it."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    a = store.insert_finding(_finding(sites[0], claim="c1", binding_rung="static"))
    b = store.insert_finding(_finding(sites[0], claim="c2", binding_rung="observed"))
    _record_finding_on(store, a, "2026-08-16T04:00:00+00:00")
    _record_finding_on(store, b, "2026-08-16T05:00:00+00:00")

    result = findings_by_kind_over_time(store)

    assert result["by_rung"] == {"static": 1, "observed": 1}


def test_findings_by_kind_over_time_narrows_to_one_repository(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))
    r1 = store.replace_call_sites("r1", [_site(repo_id="r1", path="src/a.ts", line=1)])
    r2 = store.replace_call_sites("r2", [_site(repo_id="r2", path="src/b.ts", line=2)])
    a = store.insert_finding(_finding(r1[0], claim="c1", severity="breaking"))
    b = store.insert_finding(_finding(r2[0], claim="c2", severity="warning"))
    _record_finding_on(store, a, "2026-08-16T04:00:00+00:00")
    _record_finding_on(store, b, "2026-08-16T04:00:00+00:00")

    result = findings_by_kind_over_time(store, repo_id="r1")

    assert result["days"] == [{"day": "2026-08-16", "counts": {"breaking": 1}}]
    assert result["repo_id"] == "r1"


def test_findings_by_kind_over_time_on_an_empty_graph_reports_no_days(store):
    """No day is an empty list rather than a run of zeroes. Nothing records a DETECT run, so a
    day with no row is a day nothing was recorded -- which may be no changes or may be no run,
    and inventing a zero would claim the first."""
    result = findings_by_kind_over_time(store)

    assert result["days"] == []
    assert result["total"] == 0
    assert result["by_rung"] == {}


# --- The indexing canvas: every rung on the picture, and off-path kept visible ----------------
#
# `repository_graph` drew static edges only, which is correct about call sites and incomplete as
# a picture of what Sync knows. These cover the rest of the closed rung vocabulary and the two
# states an empty canvas must not conflate.


def test_repository_graph_carries_observed_edges_at_their_own_rung(store):
    """A stronger rung is a separate edge, never blended into the static one. Two facts about the
    same operation stay two facts."""
    store.upsert_call_site(_site())
    store.record_observed_call(_observed_call(operation_id="PostCharges"))

    result = repository_graph(store, "r1")

    assert {"vendor_id": "stripe", "operation_id": "PostCharges", "binding_rung": "observed", "calls": 1} in (
        result["observed_bindings"]
    )
    assert all(binding["binding_rung"] == "static" for binding in result["bindings"])


def test_repository_graph_keeps_an_uncorrelated_span_off_path_rather_than_dropping_it(store):
    """`unresolved` is traffic that named no operation. Dropping it would understate what reached
    the vendor; folding it into `observed` would claim a correlation nothing made."""
    store.upsert_call_site(_site())
    store.record_observed_call(
        _observed_call(operation_id="", binding_rung="unresolved", trace_id="t9")
    )

    result = repository_graph(store, "r1")

    assert result["off_path"]["unresolved"] == 1
    assert all(edge["binding_rung"] != "unresolved" for edge in result["observed_bindings"])


def test_repository_graph_counts_unattributed_findings_off_path(store):
    """`unattributed` is a finding whose rung predates the column. It is not a rung a binder
    emits, so it cannot be drawn as one, and it is not nothing either.

    Written by SQL because `insert_finding` refuses the value outright, and that refusal is
    correct: nothing may write `unattributed` today, so the only rows carrying it are history.
    Constructing one any other way would be testing a state the writer guarantees cannot arise.
    """
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1", binding_rung="static"))
    store._connect().execute(
        "UPDATE finding SET binding_rung = 'unattributed' WHERE id = %s", (finding_id,)
    )

    result = repository_graph(store, "r1")

    assert result["off_path"]["unattributed"] == 1


def test_repository_graph_reports_off_path_as_nought_when_the_graph_holds_none(store):
    """Nought here is a measurement: the tables were read and held none. That is different from
    the never-indexed case below, which is why only one of them is a number."""
    store.upsert_call_site(_site())

    result = repository_graph(store, "r1")

    assert result["off_path"] == {"unresolved": 0, "unattributed": 0}


def test_repository_graph_echoes_the_closed_rung_vocabulary(store):
    """So a rung with no edge reads as a rung with no edge, rather than as a rung that cannot be."""
    result = repository_graph(store, "r1")

    assert result["rungs"] == list(FINDING_RUNGS)


def test_repository_graph_says_nothing_has_ever_been_indexed_rather_than_nought(store):
    """The distinction this canvas turns on. No call site row has ever existed for this
    repository, which is either an index that never ran or one that ran and found no vendor call
    -- and nothing records which, so it must not claim either."""
    result = repository_graph(store, "r1")

    assert result["indexed_at"] is None
    assert result["bindings"] == []


def test_repository_graph_reports_when_the_index_last_wrote_a_row_here(store):
    store.upsert_call_site(_site())

    result = repository_graph(store, "r1")

    assert result["indexed_at"] is not None


def test_repository_graph_still_reports_indexed_after_every_call_site_is_retracted(store):
    """A repository whose calls have all gone was still indexed. Reporting `None` would say the
    index never ran, which is a different and false claim."""
    store.upsert_call_site(_site(path="src/a.ts", line=1))
    store.replace_call_sites("r1", [])

    result = repository_graph(store, "r1")

    assert result["indexed_at"] is not None
    assert result["bindings"] == []


def test_repository_graph_binding_keys_are_exactly_what_the_console_reads(store):
    """The key set, pinned.

    `bindings` emitted `rung` while `RepositoryGraphBinding` declared `binding_rung` and
    `file-tree-canvas.tsx` read `binding_rung`, so the console saw `undefined` for the rung on
    every edge of the screen whose whole premise is that every edge carries one. TypeScript could
    not catch it -- the type was right and the payload was wrong -- and no test compared them.
    This is that comparison.
    """
    store.upsert_call_site(_site())
    store.record_observed_call(_observed_call(operation_id="PostCharges"))

    result = repository_graph(store, "r1")

    assert set(result["bindings"][0]) == {
        "vendor_id",
        "operation_id",
        "path",
        "line",
        "symbol",
        "binding_rung",
    }
    assert set(result["observed_bindings"][0]) == {
        "vendor_id",
        "operation_id",
        "binding_rung",
        "calls",
    }


# --- Decision 45: dismissal, and the grain it insists on --------------------------------------
#
# "One row is one dismissal of one finding by one person at one time, not a property of the
# finding -- a finding dismissed and later un-dismissed has two rows and the current state is the
# latest, because otherwise the console cannot show that somebody changed their mind."


def test_a_dismissal_is_a_row_rather_than_a_column_on_the_finding(store):
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    store.record_dismissal(finding_id, reason="false_positive", actor="ada")

    assert store.dismissal_state(finding_id) == {
        "dismissed": True,
        "reason": "false_positive",
        "actor": "ada",
    }


def test_un_dismissing_writes_a_second_row_and_the_latest_wins(store):
    """The whole reason the grain is a row: a column would overwrite, and the console could not
    show that somebody changed their mind."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    store.record_dismissal(finding_id, reason="wont_fix", actor="ada")
    store.record_dismissal(finding_id, reason=None, actor="bo")

    assert store.dismissal_state(finding_id)["dismissed"] is False
    assert store.dismissal_history_count(finding_id) == 2


def test_a_finding_nobody_touched_is_not_dismissed_and_names_no_reason(store):
    """Not dismissed is the absence of a dismissal, never a reason of its own."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    assert store.dismissal_state(finding_id) == {
        "dismissed": False,
        "reason": None,
        "actor": None,
    }


def test_a_dismissal_reason_outside_the_closed_vocabulary_is_refused(store):
    """The same discipline as `abandon_reason`: a promise to learn from dismissals needs a schema
    that can answer the question, and free text cannot be aggregated."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    with pytest.raises(ValueError):
        store.record_dismissal(finding_id, reason="seemed wrong to me", actor="ada")


def test_dismissal_does_not_remove_the_finding(store):
    """Dismissal is not deletion. The finding stays listed and is filtered out by default, which
    the read surface can only do if the row is still there."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    store.record_dismissal(finding_id, reason="intentional", actor="ada")

    assert any(f.id == finding_id for f in store.open_findings())


def test_false_positive_dismissals_are_countable_on_their_own(store):
    """`false positive` feeds detector accuracy and nothing else does, so it has to be separable
    from the other three reasons rather than pooled with them."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    a = store.insert_finding(_finding(sites[0], claim="c1"))
    b = store.insert_finding(_finding(sites[0], claim="c2"))
    store.record_dismissal(a, reason="false_positive", actor="ada")
    store.record_dismissal(b, reason="wont_fix", actor="ada")

    assert store.dismissal_reason_counts() == {"false_positive": 1, "wont_fix": 1}


# --- Decision 76: the event bus, as a real bus rather than polling behind a facade ------------
#
# Owner-selected on 2026-08-18: real LISTEN/NOTIFY, one event per call site, and the event
# CARRIES the node rather than signalling a re-read. The cost of both was stated when the choice
# was offered and taken deliberately.


def test_writing_a_call_site_publishes_an_event_carrying_the_node(store):
    """Fat payload, owner-selected: the canvas draws from the stream without a refetch."""
    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site())

        received = events.next(timeout=5.0)

    assert received == {
        "kind": "call_site.indexed",
        "repo_id": "r1",
        "path": "src/billing.ts",
        "vendor_id": "stripe",
        "operation_id": "PostCharges",
        "binding_rung": "static",
    }


def test_an_event_names_the_static_rung_because_that_is_what_a_call_site_is(store):
    """Every edge carries the rung it was established at, on the wire as well as on the screen."""
    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site())
        assert events.next(timeout=5.0)["binding_rung"] == "static"


def test_a_subscriber_hears_nothing_from_another_repository(store):
    """Scope is the route's, and the bus honours it rather than shipping one repository's
    activity to a client watching another."""
    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site(repo_id="r2", path="src/other.ts"))
        store.upsert_call_site(_site(repo_id="r1", path="src/mine.ts"))

        received = events.next(timeout=5.0)

    assert received["repo_id"] == "r1"
    assert received["path"] == "src/mine.ts"


def test_an_event_is_published_per_call_site_rather_than_per_file(store):
    """Owner-selected granularity. Two call sites in one file are two events, because the choice
    was the finest grain and not a per-file coalesce."""
    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site(path="src/a.ts", line=1))
        store.upsert_call_site(_site(path="src/a.ts", line=9))

        first = events.next(timeout=5.0)
        second = events.next(timeout=5.0)

    assert first["path"] == "src/a.ts"
    assert second["path"] == "src/a.ts"


def test_a_payload_too_large_to_notify_degrades_to_a_signal_rather_than_failing(store):
    """`NOTIFY` refuses a payload over 8000 bytes. A fat event that cannot fit falls back to a
    thin one naming the file, so the console re-reads instead of the index run dying on a long
    path -- the write must never fail because the notification did."""
    # Deliberately past the 7900-byte guard: 2000 segments was not, which is worth knowing
    # -- most real paths will never trip this, and the fallback exists for the ones that do.
    long_path = "src/" + ("d/" * 4500) + "billing.ts"

    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site(path=long_path))

        received = events.next(timeout=5.0)

    assert received["kind"] == "call_site.indexed.unsent"
    assert received["repo_id"] == "r1"
    assert "path" not in received


def test_a_new_finding_publishes_an_event_carrying_its_severity_and_rung(store):
    """Decision 76's second publisher, and what decision 87's new-findings banner needs.

    The severity rides along because 87's banner is a triage prompt -- a reader deciding whether
    to interrupt what they are doing needs to know whether the arrival was breaking or an
    addition, and a banner that made them open the table to find out would be a worse interruption
    than no banner.
    """
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])

    with store.subscribe_events("r1") as events:
        finding_id = store.insert_finding(_finding(sites[0], claim="c1", severity="breaking"))

        received = events.next(timeout=5.0)

    assert received == {
        "kind": "finding.opened",
        "repo_id": "r1",
        "finding_id": finding_id,
        "vendor_id": "stripe",
        "severity": "breaking",
        "binding_rung": "static",
    }


def test_a_finding_event_carries_the_rung_its_claim_rests_on(store):
    """Every artifact derived from a binding carries the rung, on the wire as on the screen. A
    banner that could not say what a finding rests on would be asking a reader to act on a claim
    whose evidence class it had dropped in transit."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])

    with store.subscribe_events("r1") as events:
        store.insert_finding(_finding(sites[0], claim="c1", binding_rung="observed"))

        assert events.next(timeout=5.0)["binding_rung"] == "observed"


def test_re_running_detect_over_the_same_finding_publishes_nothing_the_second_time(store):
    """DETECT converges: `insert_finding` is `ON CONFLICT DO NOTHING`, so a re-run writes no row.
    The event has to follow the write rather than the call, or a second pass would announce
    findings nobody opened and the banner would cry wolf on every scheduled run."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    store.insert_finding(_finding(sites[0], claim="c1"))

    with store.subscribe_events("r1") as events:
        store.insert_finding(_finding(sites[0], claim="c1"))

        assert events.next(timeout=2.0) is None


# --- The bus where it lies, rather than where it works ----------------------------------------
#
# Every defect this transport has had was in the quiet path: a stream that blocked forever on an
# idle channel looked identical to one that worked, because the tests only ever asserted on
# events that arrived. These assert the states where a transport reports success and is wrong.


def test_a_quiet_channel_returns_none_within_the_timeout_rather_than_blocking(store):
    """The defect that shipped in CI-W419, as a test that fails by hanging if it returns.

    A stream that cannot say "nothing yet" cannot drive a heartbeat, and without a heartbeat the
    console cannot tell an idle index from a dead connection -- which decision 76 requires it to
    render as different things.
    """
    with store.subscribe_events("r1") as events:
        started = time.monotonic()
        assert events.next(timeout=1.0) is None
        assert time.monotonic() - started < 5.0


def test_a_subscriber_that_arrives_late_misses_what_was_sent_before_it(store):
    """`NOTIFY` is not queued: a notification sent with nobody listening is gone.

    Asserted rather than worked around, because the console's honest answer is to say what its
    count is over -- events since it connected -- rather than to imply it watched the whole run.
    A test that pretended otherwise would be describing a transport we do not have.
    """
    store.upsert_call_site(_site(path="src/before.ts"))

    with store.subscribe_events("r1") as events:
        assert events.next(timeout=1.0) is None


def test_a_subscriber_behind_by_several_events_drains_them_in_order(store):
    """A burst is the normal case for an index run, not the exceptional one. The second shape of
    this stream dropped everything after the first and the per-call-site test caught it; this
    holds the property directly rather than as a side effect of counting."""
    with store.subscribe_events("r1") as events:
        for index in range(5):
            store.upsert_call_site(_site(path=f"src/a{index}.ts", line=index + 1))

        drained = [events.next(timeout=5.0) for _ in range(5)]

    assert [event["path"] for event in drained] == [f"src/a{i}.ts" for i in range(5)]


def test_two_repositories_indexing_at_once_do_not_cross_streams(store):
    """One channel carries every repository, so the filter is the only thing keeping a client from
    seeing another codebase's activity. Interleaved rather than sequential, because a filter that
    works on a quiet channel can still fail on a busy one."""
    with store.subscribe_events("r1") as events:
        store.upsert_call_site(_site(repo_id="r2", path="src/theirs-1.ts"))
        store.upsert_call_site(_site(repo_id="r1", path="src/mine-1.ts"))
        store.upsert_call_site(_site(repo_id="r2", path="src/theirs-2.ts"))
        store.upsert_call_site(_site(repo_id="r1", path="src/mine-2.ts"))

        drained = [events.next(timeout=5.0) for _ in range(2)]

    assert [event["path"] for event in drained] == ["src/mine-1.ts", "src/mine-2.ts"]
    assert all(event["repo_id"] == "r1" for event in drained)


def test_a_closed_connection_ends_the_stream_rather_than_hanging(store):
    """A dropped connection must surface, because decision 76 makes the console render a drop and
    it can only do that if the server side stops rather than waiting forever."""
    with store.subscribe_events("r1") as events:
        events._connection.close()

        with pytest.raises(psycopg.OperationalError):
            events.next(timeout=2.0)


def test_the_burst_cost_of_per_call_site_events_is_measured_rather_than_assumed(store):
    """Per-call-site fat events were chosen with their cost stated. This is the cost, measured.

    Recorded so the granularity can be argued with a number rather than a worry. If a real
    repository ever makes this unacceptable, the fix is a coalescing publisher and this test is
    what will show it changed.
    """
    count = 200

    with store.subscribe_events("r1") as events:
        started = time.monotonic()
        for index in range(count):
            store.upsert_call_site(_site(path=f"src/f{index}.ts", line=index + 1))
        written = time.monotonic() - started

        drain_started = time.monotonic()
        drained = [events.next(timeout=10.0) for _ in range(count)]
        drained_in = time.monotonic() - drain_started

    assert all(event is not None for event in drained)
    # Generous, and deliberately so: this asserts the shape is linear and unblocked, not a
    # benchmark that fails on a slow machine. `written`/`drained_in` go in the register.
    assert drained_in < 30.0
    print(f"\nburst: {count} events written in {written:.2f}s, drained in {drained_in:.2f}s")


def test_dismissing_a_finding_publishes_an_event(store):
    """Revised: emit now, because the write path is in flight rather than anticipated.

    The reason travels because a dismissal is the one signal that feeds detector accuracy, and a
    banner or toast that could not say *why* something left the list would be reporting a
    disappearance rather than a decision.
    """
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))

    with store.subscribe_events("r1") as events:
        store.record_dismissal(finding_id, reason="false_positive", actor="ada")

        received = events.next(timeout=5.0)

    assert received == {
        "kind": "finding.dismissed",
        "repo_id": "r1",
        "finding_id": finding_id,
        "reason": "false_positive",
        "actor": "ada",
    }


def test_restoring_a_finding_publishes_its_own_event_rather_than_a_dismissal_with_no_reason(store):
    """A restore is not a dismissal carrying `None`. They are opposite decisions, and a console
    told only that *something changed* would have to re-read to find out which."""
    store.upsert_call_site(_site())
    sites = store.replace_call_sites("r1", [_site()])
    finding_id = store.insert_finding(_finding(sites[0], claim="c1"))
    store.record_dismissal(finding_id, reason="wont_fix", actor="ada")

    with store.subscribe_events("r1") as events:
        store.record_dismissal(finding_id, reason=None, actor="bo")

        received = events.next(timeout=5.0)

    assert received["kind"] == "finding.restored"
    assert received["actor"] == "bo"
    assert "reason" not in received


class TestOverviewLastIndexRun:
    """Decision 41's fact, on the screen it has to be readable from.

    A toast may announce "Index finished, 1,204 call sites" but must never be the only place it
    exists. `index_run` records it; this is what puts it on `/api/overview`, where somebody who
    missed the toast can still read it a minute later.
    """

    def test_a_repository_never_indexed_reports_no_pass(self, store):
        # Absence, not a zeroed row. Never-indexed and indexed-and-found-nothing are the
        # distinction this console keeps apart everywhere else.
        assert overview_summary(store, repo_id="r1")["last_index_run"] is None

    def test_a_completed_pass_carries_its_count_and_its_outcome(self, store):
        store.start_index_run("r1", started_at=SEEN)
        store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=1204)

        run = overview_summary(store, repo_id="r1")["last_index_run"]

        assert run["outcome"] == "completed"
        assert run["call_sites"] == 1204
        assert run["finished_at"] == SEEN.isoformat()

    def test_a_pass_still_running_reports_no_count_rather_than_nought(self, store):
        store.start_index_run("r1", started_at=SEEN)

        run = overview_summary(store, repo_id="r1")["last_index_run"]

        # In flight is the fourth state: not finished, not failed, not absent. A count here would
        # be a partial one rendered as the size of the codebase.
        assert run["outcome"] is None
        assert run["finished_at"] is None
        assert run["call_sites"] is None

    def test_a_pass_that_died_says_so_rather_than_looking_unfinished(self, store):
        store.start_index_run("r1", started_at=SEEN)
        store.fail_index_run("r1", started_at=SEEN, at=SEEN, outcome="failed")

        run = overview_summary(store, repo_id="r1")["last_index_run"]

        assert run["outcome"] == "failed"

    def test_the_fleet_scope_reports_no_pass_because_a_pass_is_one_repositorys(self, store):
        store.start_index_run("r1", started_at=SEEN)
        store.finish_index_run("r1", started_at=SEEN, finished_at=SEEN, call_sites=9)

        # `repo_id=None` is the fleet, and an index pass belongs to one repository. Reporting
        # some repository's pass under a fleet heading would be the same false attribution
        # `codebases-panel` printed one total under every card.
        assert overview_summary(store)["last_index_run"] is None


def test_a_finding_row_carries_the_name_two_people_can_say(store):
    """M15 Task 6, at the payload rather than in the console.

    `web/CLAUDE.md`: a rule the payload can answer belongs in the payload, so two screens cannot
    disagree about one fact. A name derived in the console would be derived again in the CLI and
    in a pull-request body, and the third copy is where they would start to differ.
    """
    site = store.upsert_call_site(_site(vendor_id="stripe", operation_id="PostCharges"))
    store.insert_finding(_finding(site, claim="response-field-type-changed"))

    row = findings_page(store, repo_id="r1")["items"][0]

    assert row["name"].startswith("stripe-postcharges-")


def test_the_name_survives_re_deriving_the_finding(store):
    """The property the feature rests on, proven through the store rather than in isolation.

    `insert_finding` converges on the row it already wrote, so a second scan must not rename a
    finding somebody has already written into a ticket.
    """
    site = store.upsert_call_site(_site(vendor_id="stripe", operation_id="PostCharges"))
    store.insert_finding(_finding(site, claim="response-field-type-changed"))
    first = findings_page(store, repo_id="r1")["items"][0]["name"]

    store.insert_finding(_finding(site, claim="response-field-type-changed"))
    second = findings_page(store, repo_id="r1")["items"][0]["name"]

    assert first == second

"""View models for the three graph screens: the binding surface, the observed rung, detector
accountability.

Runs against a dedicated database, never the shared `sync` one a developer's console may be
watching live:

    docker exec sync-postgres-1 psql -U sync -d postgres -c "CREATE DATABASE sync_graph_views_check"

`tests/test_dashboard_fleet.py` truncates the shared `sync` database directly, which is fine in
CI but not here -- this module follows `tests/test_seed_console.py`'s pattern of a throwaway
database instead, because a `truncate_all()` against `sync` would erase a running console's seed
data out from under an operator watching it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, ObservedShape, VendorChange
from sync.dashboard.graph_views import (
    binding_surface,
    detector_accountability,
    index_coverage,
    observed_telemetry,
)
from sync.graph.store import GraphStore

DSN = os.environ.get(
    "SYNC_GRAPH_VIEWS_TEST_DSN", "postgresql://sync:sync@localhost:5433/sync_graph_views_check"
)

SEEN = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


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

    paths = {row["path"] for row in result["call_sites"]}
    assert paths == {"src/a.ts", "src/b.ts"}
    assert {site_a, site_b}  # both ids were used; guards against a copy-paste that reused one


def test_binding_surface_every_call_site_row_reports_the_static_rung(store):
    # A call site is what the static index found, so every row here rests on the same rung --
    # the surface must not invent 'resolved' or 'observed' for a binding no correlator touched.
    store.upsert_call_site(_site())

    result = binding_surface(store, "stripe", "PostCharges")

    assert result["call_sites"], "the fixture wrote no call site"
    assert all(row["binding_rung"] == "static" for row in result["call_sites"])


def test_binding_surface_filters_call_sites_by_repo_id_when_asked(store):
    store.upsert_call_site(_site(repo_id="r1", path="src/a.ts", line=1))
    store.upsert_call_site(_site(repo_id="r2", path="src/b.ts", line=2))

    result = binding_surface(store, "stripe", "PostCharges", repo_id="r1")

    assert [row["path"] for row in result["call_sites"]] == ["src/a.ts"]


def test_binding_surface_reports_only_changes_matching_the_operation(store):
    store.upsert_call_site(_site())
    store.upsert_vendor_change(_change(operation_id="PostCharges", kind="response-field-type-changed"))
    store.upsert_vendor_change(_change(operation_id="PostRefunds", kind="field-removed"))

    result = binding_surface(store, "stripe", "PostCharges")

    kinds = {row["kind"] for row in result["changes"]}
    assert kinds == {"response-field-type-changed"}


def test_binding_surface_on_an_operation_nobody_calls_is_empty_not_an_error(store):
    result = binding_surface(store, "stripe", "GetNothing")

    assert result["call_sites"] == []
    assert result["changes"] == []


def test_binding_surface_excludes_retracted_call_sites(store):
    # A retracted call site is a position the code no longer occupies -- `binding_surface`
    # reads `call_sites_for_operation`, whose own contract excludes it, and this pins that the
    # exclusion actually reaches this view rather than being assumed from the store's docstring.
    live_id = store.upsert_call_site(_site(path="src/a.ts", line=1))
    retracted_id = store.upsert_call_site(_site(path="src/b.ts", line=2))
    with store._connect().cursor() as cur:
        cur.execute("UPDATE call_site SET retracted_at = now() WHERE id = %s", (retracted_id,))

    result = binding_surface(store, "stripe", "PostCharges")

    paths = {row["path"] for row in result["call_sites"]}
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


def test_observed_telemetry_reports_calls_for_one_repository(store):
    store.record_observed_call(_observed_call(repo_id="r1", trace_id="t1"))
    store.record_observed_call(_observed_call(repo_id="r2", trace_id="t2"))

    result = observed_telemetry(store, "r1")

    assert [row["trace_id"] for row in result["calls"]] == ["t1"]


def test_observed_telemetry_call_rows_carry_the_derived_evidence_counts(store):
    # `call_count`, `error_count` and friends are properties on `ObservedCall`, derived from
    # `spans` rather than stored -- the view model must read them, not restate `len(spans)`.
    spans = {
        "s1": {"target": "d1", "status": 200, "resend": 0},
        "s2": {"target": "d1", "status": 500, "resend": 1},
    }
    store.record_observed_call(_observed_call(trace_id="t1", spans=spans))

    result = observed_telemetry(store, "r1")

    row = result["calls"][0]
    assert row["call_count"] == 2
    assert row["distinct_targets"] == 1
    assert row["repeated_calls"] == 1
    assert row["error_count"] == 1
    assert row["max_resend_count"] == 1


def test_observed_telemetry_shapes_are_scoped_to_operations_this_repo_was_seen_calling(store):
    # `observed_shape` carries no `repo_id` -- it is a vendor-wide baseline. The view joins it
    # in through the (vendor_id, operation_id) pairs this repository's own observed calls name,
    # so a shape recorded for an operation this repo never called must not leak in.
    store.record_observed_call(_observed_call(repo_id="r1", operation_id="PostCharges"))
    store.record_observed_shape(_shape(operation_id="PostCharges", field_path="/amount"))
    store.record_observed_shape(_shape(operation_id="PostRefunds", field_path="/status"))

    result = observed_telemetry(store, "r1")

    fields = {row["field_path"] for row in result["shapes"]}
    assert fields == {"/amount"}


def test_observed_telemetry_an_uncorrelated_call_does_not_crash_the_shape_join(store):
    # `operation_id` is '' for a span nothing could correlate, paired with `binding_rung`
    # 'unresolved'. An empty operation must not be asked of `observed_shapes`, which requires
    # a non-empty one.
    store.record_observed_call(
        _observed_call(operation_id="", binding_rung="unresolved", trace_id="t-uncorrelated")
    )

    result = observed_telemetry(store, "r1")

    assert result["calls"][0]["operation_id"] == ""
    assert result["calls"][0]["binding_rung"] == "unresolved"
    assert result["shapes"] == []


def test_observed_telemetry_reports_error_windows_for_one_repository(store):
    store.record_observed_error_window(_error_window(repo_id="r1"))
    store.record_observed_error_window(_error_window(repo_id="r2"))

    result = observed_telemetry(store, "r1")

    assert len(result["error_windows"]) == 1
    assert result["error_windows"][0]["repo_id"] == "r1"


def test_observed_telemetry_of_a_repository_with_no_traffic_is_all_empty(store):
    result = observed_telemetry(store, "never-observed")

    assert result == {
        "repo_id": "never-observed", "calls": [], "shapes": [], "error_windows": [],
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


def test_detector_accountability_with_no_findings_is_empty_not_an_error(store):
    result = detector_accountability(store)

    assert result == {"detectors": [], "total_open_findings": 0}

import os

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
            call_site_id=site_id,
            vendor_change_id=change_id,
            severity="breaking",
            rationale="status removed",
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

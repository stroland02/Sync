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
    store.upsert_call_site(_site(content_hash="hash-2", line=44))
    sites = store.call_sites_for_operation("stripe", "PostCharges")
    assert len(sites) == 1
    assert sites[0].line == 44


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

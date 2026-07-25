import os

import pytest

from sync.core import CallSite, VendorChange
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(store, *, operation_id="PostCharges", reads=("id", "status"), args=("amount",), path="src/a.ts"):
    return store.upsert_call_site(
        CallSite(
            repo_id="r1", path=path, line=1, col=0, vendor_id="stripe",
            operation_id=operation_id, symbol="stripe.charges.create",
            args_keys=list(args), response_fields_read=list(reads),
            sdk_version="18.0.0", content_hash=path,
        )
    )


def _change(store, *, operation_id="PostCharges", kind="response-property-removed", field="status"):
    return store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2", kind=kind,
            operation_id=operation_id, path_ptr=f"/paths/x/{field}",
            severity="breaking", source="oasdiff", raw={"id": kind, "field": field},
        )
    )


def test_a_change_on_an_operation_the_code_calls_produces_a_finding(store):
    _site(store)
    _change(store)
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1
    assert findings[0].severity == "breaking"
    assert findings[0].detector == "vendor_change"


def test_a_change_on_an_operation_the_code_never_calls_is_ignored(store):
    _site(store, operation_id="PostCharges")
    _change(store, operation_id="PostRefunds")
    assert VendorChangeDetector(store).scan() == []


def test_a_removed_field_the_code_never_reads_is_ignored(store):
    _site(store, reads=("id",))
    _change(store, field="status")
    assert VendorChangeDetector(store).scan() == []


def test_a_removed_request_parameter_the_code_passes_produces_a_finding(store):
    _site(store, args=("amount", "source"))
    _change(store, kind="request-parameter-removed", field="source")
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1


def test_every_affected_call_site_produces_its_own_finding(store):
    _site(store, path="src/a.ts")
    _site(store, path="src/b.ts")
    _change(store)
    assert len(VendorChangeDetector(store).scan()) == 2


def test_the_rationale_names_the_operation_and_the_field(store):
    _site(store)
    _change(store)
    rationale = VendorChangeDetector(store).scan()[0].rationale
    assert "PostCharges" in rationale
    assert "status" in rationale

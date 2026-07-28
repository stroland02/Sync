import json
import os
from pathlib import Path

import pytest

from sync.core import CallSite, VendorChange
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "specs"
REAL_RECORD = Path(__file__).parent / "fixtures" / "oasdiff" / "stripe_v2320_v2330_postcharges.json"


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


def test_the_real_oasdiff_pipeline_only_finds_call_sites_that_touch_the_changed_field(store):
    """Ground the filter in real oasdiff output, not hand-built `raw` dicts.

    charges_base.json -> charges_revision.json produces two real breaking
    changes on PostCharges: a removed request property `source`, and a
    removed (optional) response property `status`. Neither record carries a
    structured `field` key -- the field name lives only in oasdiff's `text`
    message. A call site is a genuine hit only if it actually passes `source`
    or reads `status`; a call site that does neither must not match.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")
    for change in changes:
        store.upsert_vendor_change(change)

    hit_id = _site(store, path="src/hit.ts", args=("amount", "source"), reads=("id", "status"))
    miss_id = _site(store, path="src/miss.ts", args=("amount",), reads=("id",))

    findings = VendorChangeDetector(store).scan()

    def matched(site_id, kind):
        return any(f.call_site_id == site_id and kind in f.rationale for f in findings)

    assert matched(hit_id, "request-property-removed")
    assert not matched(miss_id, "request-property-removed")
    assert matched(hit_id, "response-optional-property-removed")
    assert not matched(miss_id, "response-optional-property-removed")


def test_a_change_whose_field_cannot_be_determined_still_produces_a_finding(store):
    """Failing to resolve the field is recoverable; emit rather than drop.

    No structured key and no backticked token in `text` -- there is nothing
    to extract. The operation still matches, so the finding must still fire,
    and its rationale must read differently from a field-matched one.
    """
    _site(store)
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/v1/charges", severity="breaking", source="oasdiff",
            raw={"id": "response-property-removed", "text": "removed a response property"},
        )
    )
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1
    rationale = findings[0].rationale
    assert "PostCharges" in rationale
    assert "operation match only" in rationale
    assert "call site reads" not in rationale
    assert "call site passes" not in rationale


def test_a_change_whose_kind_is_neither_request_nor_response_still_produces_a_finding(store):
    """A future oasdiff category we have never seen must not vanish silently.

    The field is determinable here (`Charge` is backticked in `text`), but
    the kind itself doesn't say which side of the API it touches, so there is
    no list to check the field against. Emit on the operation match alone.
    """
    _site(store)
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="components-schema-removed", operation_id="PostCharges",
            path_ptr="/components/schemas/Charge", severity="breaking", source="oasdiff",
            raw={"id": "components-schema-removed", "text": "removed the schema `Charge`"},
        )
    )
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1
    rationale = findings[0].rationale
    assert "PostCharges" in rationale
    assert "operation match only" in rationale
    assert "call site reads" not in rationale
    assert "call site passes" not in rationale


def _real_change(store):
    """One verbatim record from Stripe's real v2320 -> v2330 window.

    Twelve real segments deep, leaf `iin`. No call site in any repository reads
    `iin`, which is why leaf-only matching found nothing against this window.
    """
    record = json.loads(REAL_RECORD.read_text(encoding="utf-8"))
    return store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v2320", to_version="v2330",
            kind=record["id"], operation_id=record["operationId"],
            path_ptr=record["path"], severity="breaking", source="oasdiff", raw=record,
        )
    )


def test_a_real_nested_change_matches_a_call_site_that_reads_the_path_leading_to_it(store):
    """The measured defect, stated as a test.

    The change's path starts at `customer`; a call site that reads
    `result.customer` is reading into the subtree the vendor changed. Leaf-only
    matching asked whether the call site read `iin`, twelve levels down, and no
    call site ever does.
    """
    _site(store, reads=("customer",))
    _real_change(store)
    assert len(VendorChangeDetector(store).scan()) == 1


def test_a_real_nested_change_ignores_a_call_site_touching_none_of_its_path(store):
    """The filter still filters, which is what stops this being operation-match-only.

    `id`, `status` and `amount` appear nowhere in the change's path. Measured
    across the whole v2320 -> v2330 window, none of them is a first segment of
    any of the 327,124 records, so this is the common case and not a contrived one.
    """
    _site(store, reads=("id", "status"), args=("amount",))
    _real_change(store)
    assert VendorChangeDetector(store).scan() == []


def test_a_partial_path_match_does_not_claim_the_call_site_read_the_changed_field(store):
    """Reading toward a change is not reading the changed field, and must not read as if it is.

    This is the low-confidence match: it degrades to an operation-match-only
    finding rather than being dropped, and its rationale says which field
    actually changed and which path the call site actually reads.
    """
    _site(store, reads=("customer",))
    _real_change(store)
    rationale = VendorChangeDetector(store).scan()[0].rationale
    assert "operation match only" in rationale
    assert "customer" in rationale
    assert "iin" in rationale
    assert "call site reads `iin`" not in rationale


def test_a_call_site_that_reads_the_changed_field_itself_is_reported_as_a_field_match(store):
    """A full-depth read keeps the confident rationale, so the two are distinguishable."""
    _site(store, reads=("status",))
    _change(store, field="status")
    rationale = VendorChangeDetector(store).scan()[0].rationale
    assert "call site reads `status`" in rationale
    assert "operation match only" not in rationale


def test_a_nested_request_path_matches_the_argument_path_the_call_site_passes(store):
    """Request-side paths get the same treatment; nothing about this is response-only."""
    _site(store, args=("metadata", "metadata.order_id"))
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="request-property-removed", operation_id="PostCharges",
            path_ptr="/v1/charges", severity="breaking", source="oasdiff",
            raw={"id": "request-property-removed", "text": "removed the property `metadata/order_id`"},
        )
    )
    assert len(VendorChangeDetector(store).scan()) == 1


def test_a_call_site_path_deeper_than_the_change_still_matches(store):
    """The indexer records every prefix, so the comparison only runs one way.

    A change naming `metadata` must reach a call site recorded as
    `metadata.order_id`, which it does because that call site also recorded
    `metadata`.
    """
    _site(store, args=("metadata", "metadata.order_id"))
    _change(store, kind="request-property-removed", field="metadata")
    assert len(VendorChangeDetector(store).scan()) == 1


def test_a_structural_segment_in_the_change_path_does_not_break_the_match(store):
    """oasdiff writes `items` where an array is walked; a call site writes nothing there.

    A call site that reaches past an array -- `result.data[0].customer` written
    so the chain survives -- records `data.customer`, which must still meet
    `data/items/customer`. `items` occurs in 327,084 of the window's 327,124
    records, so a rule that could not step over it would match almost nothing.
    """
    _site(store, reads=("data", "data.customer"))
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/v1/charges", severity="breaking", source="oasdiff",
            raw={"id": "response-property-removed", "text": "removed the property `data/items/customer/email`"},
        )
    )
    findings = VendorChangeDetector(store).scan()
    assert len(findings) == 1
    # `data` matches this change without stepping over anything, so only the
    # deeper path being quoted proves the step happened.
    assert "`data.customer`" in findings[0].rationale


def test_a_change_path_is_anchored_so_a_shared_name_deeper_down_is_not_a_match(store):
    """A top-level `card` is not the `card` hanging off an error, and must not match it.

    Without anchoring, `card` appears somewhere in all 327,124 records of the
    window, so every call site reading a top-level `card` would match every one
    of them -- operation-match-only wearing a field match's rationale.
    """
    _site(store, reads=("card",))
    _real_change(store)
    assert VendorChangeDetector(store).scan() == []

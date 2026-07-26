import os
from pathlib import Path

import pytest

from sync.core import CallSite, VendorChange
from sync.detect.vendor_change import VendorChangeDetector, _changed_field
from sync.graph.store import GraphStore
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "specs"


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


def _leaf_change(text: str, kind: str = "response-optional-property-removed") -> VendorChange:
    return VendorChange(
        vendor_id="stripe", from_version="v2320", to_version="v2330",
        kind=kind, operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"text": text},
    )


def test_a_bare_field_name_is_returned_unchanged():
    assert _changed_field(_leaf_change("removed the optional property `source`")) == "source"


def test_a_nested_property_path_resolves_to_its_leaf():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/setup_attempt/payment_method_details`"
    )
    assert _changed_field(change) == "payment_method_details"


def test_schema_composition_segments_are_not_mistaken_for_fields():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/"
        "anyOf[subschema #1: payment_method_card_generated_card]/setup_attempt`"
    )
    assert _changed_field(change) == "setup_attempt"


def test_a_path_whose_leaf_is_a_composition_segment_falls_back_to_the_last_real_name():
    change = _leaf_change(
        "removed the optional property `error/payment_method/anyOf[subschema #2: Foo]`"
    )
    assert _changed_field(change) == "payment_method"


def test_a_token_with_no_resolvable_field_returns_none():
    assert _changed_field(_leaf_change("removed the optional property `anyOf[subschema #1: Foo]`")) is None


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

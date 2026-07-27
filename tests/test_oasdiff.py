import subprocess
from pathlib import Path

import pytest

from sync.core import VendorChange
from sync.signals import oasdiff
from sync.signals.oasdiff import changed_field, run_oasdiff_breaking, to_vendor_changes

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_breaking_changes_are_detected_regardless_of_exit_code():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    assert records, "oasdiff reported no breaking changes for a fixture pair with two hand-labelled ones"


def test_identical_specs_produce_no_changes():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_base.json")
    assert records == []


def test_nonzero_exit_raises_instead_of_returning_empty_list(monkeypatch):
    """A crashed or killed oasdiff must not be mistaken for "no breaking changes".

    A process that dies before writing any JSON returns exit code 1 and empty
    stdout -- the same stdout a clean "no findings" run would never produce,
    since oasdiff always writes the literal `[]` for that case. Any non-zero
    exit has to raise so a killed process can't be read as a clean report.
    """

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="killed")

    monkeypatch.setattr(oasdiff.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")


def test_records_convert_to_vendor_changes_with_operation_and_severity():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")
    assert all(c.vendor_id == "stripe" for c in changes)
    assert all(c.severity == "breaking" for c in changes)
    assert all(c.source == "oasdiff" for c in changes)
    assert any(c.operation_id == "PostCharges" for c in changes)


def test_path_ptr_holds_the_url_path_not_a_json_pointer():
    """Pins what `path_ptr` actually contains, because two specs once said otherwise.

    `2026-07-26-sync-public-change-feed.md` illustrated `path_ptr` as `/data/status`, and
    `2026-07-26-sync-observed-contract-drift.md` built a one-join claim on that reading. Both
    were wrong: oasdiff reports `path` as the operation's URL, and that is what is stored. A
    join written against the pointer reading matches nothing, so the contradiction is worth a
    test rather than a comment -- prose drifts from code silently, an assertion does not.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")

    assert changes, "fixture pair produced no changes; this test cannot check anything"
    for change in changes:
        assert change.path_ptr.startswith("/v1/"), (
            f"path_ptr held {change.path_ptr!r}; it is oasdiff's URL path, not a JSON Pointer"
        )


def test_kind_is_the_oasdiff_rule_id():
    """`VendorChange.kind` is `record["id"]`, one of the rules `oasdiff checks` enumerates.

    Anything switching on `kind` is switching on that enum, so it needs a default branch and
    a completeness check against the pinned binary -- never a hand-maintained copy of the list.
    """
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")

    assert changes
    for change, record in zip(changes, records, strict=True):
        assert change.kind == record["id"]


def _leaf_change(text: str, kind: str = "response-optional-property-removed") -> VendorChange:
    return VendorChange(
        vendor_id="stripe", from_version="v2320", to_version="v2330",
        kind=kind, operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"text": text},
    )


def test_a_bare_field_name_is_returned_unchanged():
    assert changed_field(_leaf_change("removed the optional property `source`")) == "source"


def test_a_nested_property_path_resolves_to_its_leaf():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/setup_attempt/payment_method_details`"
    )
    assert changed_field(change) == "payment_method_details"


def test_schema_composition_segments_are_not_mistaken_for_fields():
    change = _leaf_change(
        "removed the optional property "
        "`error/payment_method/card/generated_from/"
        "anyOf[subschema #1: payment_method_card_generated_card]/setup_attempt`"
    )
    assert changed_field(change) == "setup_attempt"


def test_a_path_whose_leaf_is_a_composition_segment_falls_back_to_the_last_real_name():
    change = _leaf_change(
        "removed the optional property `error/payment_method/anyOf[subschema #2: Foo]`"
    )
    assert changed_field(change) == "payment_method"


def test_a_token_with_no_resolvable_field_returns_none():
    assert changed_field(_leaf_change("removed the optional property `anyOf[subschema #1: Foo]`")) is None

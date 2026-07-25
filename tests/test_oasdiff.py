from pathlib import Path

from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

FIXTURES = Path(__file__).parent / "fixtures" / "specs"


def test_breaking_changes_are_detected_despite_exit_code_one():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    assert records, "oasdiff reported no breaking changes; exit code 1 was probably treated as failure"


def test_identical_specs_produce_no_changes():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_base.json")
    assert records == []


def test_records_convert_to_vendor_changes_with_operation_and_severity():
    records = run_oasdiff_breaking(FIXTURES / "charges_base.json", FIXTURES / "charges_revision.json")
    changes = to_vendor_changes(records, vendor_id="stripe", from_version="base", to_version="revision")
    assert all(c.vendor_id == "stripe" for c in changes)
    assert all(c.severity == "breaking" for c in changes)
    assert all(c.source == "oasdiff" for c in changes)
    assert any(c.operation_id == "PostCharges" for c in changes)

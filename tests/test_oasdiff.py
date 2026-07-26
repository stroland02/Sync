import subprocess
from pathlib import Path

import pytest

from sync.signals import oasdiff
from sync.signals.oasdiff import run_oasdiff_breaking, to_vendor_changes

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

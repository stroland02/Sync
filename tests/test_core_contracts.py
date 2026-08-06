from datetime import datetime

import pytest
from pydantic import ValidationError

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VerifyResult, VendorChange


def test_call_site_records_what_the_code_actually_touches():
    site = CallSite(
        repo_id="r1",
        path="src/billing.ts",
        line=42,
        col=8,
        vendor_id="stripe",
        operation_id="PostCharges",
        symbol="stripe.charges.create",
        args_keys=["amount", "currency"],
        response_fields_read=["id", "status"],
        sdk_version="18.0.0",
        content_hash="abc123",
    )
    assert site.operation_id == "PostCharges"
    assert "amount" in site.args_keys
    assert "status" in site.response_fields_read


def test_vendor_change_carries_severity_and_source():
    change = VendorChange(
        vendor_id="stripe",
        from_version="v2300",
        to_version="v2345",
        kind="response-property-removed",
        operation_id="PostCharges",
        path_ptr="/paths/~1v1~1charges/post/responses/200",
        severity="breaking",
        source="oasdiff",
        raw={"id": "response-property-removed"},
    )
    assert change.severity == "breaking"
    assert change.source == "oasdiff"


def test_finding_links_a_call_site_to_a_change():
    finding = Finding(
        detector="vendor_change",
        claim="response-field",
        call_site_id="cs1",
        vendor_change_id="vc1",
        severity="breaking",
        rationale="charges.create no longer returns `status`",
    )
    assert finding.status == "open"


def test_verify_result_carries_diagnostics_on_failure():
    result = VerifyResult(ok=False, diagnostics="src/billing.ts(42,8): error TS2339")
    assert result.ok is False
    assert "TS2339" in result.diagnostics


def test_patch_and_evidence_round_trip():
    patch = Patch(diff="--- a\n+++ b\n", strategy="codemod", rationale="renamed field")
    evidence = Evidence(
        spec_diff={"kind": "response-property-removed"},
        changelog_entry="`status` removed from charge responses",
        call_sites=["src/billing.ts:42"],
        ci_run_url="https://github.com/o/r/actions/runs/1",
    )
    assert patch.strategy == "codemod"
    assert evidence.ci_run_url.endswith("/1")


def test_repo_ref_identifies_a_checkout():
    ref = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path="/tmp/r", head_sha="deadbeef")
    assert ref.repo_id == "r1"


def test_a_finding_cannot_be_built_without_saying_what_it_claims():
    """`claim` is required rather than defaulted, and that is the whole fix.

    The graph identifies a finding by `(detector, call_site_id, vendor_change_id, claim)`. A
    field that defaulted to an empty string would be correct for every caller that set it and
    silently collision-prone for every caller that did not -- which is the defect this field
    exists to close, rebuilt one layer down. Three detectors shipped omitting a value nobody
    forced them to supply; pydantic is what makes forgetting impossible rather than merely
    fixed.
    """
    with pytest.raises(ValidationError):
        Finding(
            detector="vendor_change",
            call_site_id="cs1",
            vendor_change_id="vc1",
            severity="breaking",
            rationale="charges.create no longer returns `status`",
        )


def test_a_finding_cannot_name_its_claim_with_an_empty_string():
    """Required is not enough on its own, and this is the gap it leaves.

    Omitting the field and writing `claim=""` to satisfy a type checker produce the identical
    collision in the graph, and only the first is caught by making the field required. The
    length constraint closes the second at the same place rather than leaving it to a reviewer
    who would be reading a line that looks deliberate.
    """
    with pytest.raises(ValidationError):
        Finding(
            detector="efficiency",
            claim="",
            call_site_id="cs1",
            severity="info",
            rationale="called 40 times in one unit of work",
        )


def test_severity_order_ranks_every_severity_the_vocabulary_declares():
    """The rank and the vocabulary have to cover each other exactly.

    A rank that lives away from the `Severity` literal drifts the moment the literal widens, and
    this one has widened once already -- `warning` was added when oasdiff's own grading stopped
    being discarded. An unranked severity sorts to the end of a severity-ordered page, so the
    failure is a finding an operator asked to see first arriving last, which nothing else would
    catch.
    """
    from typing import get_args

    from sync.core.models import SEVERITY_ORDER, Severity

    assert set(SEVERITY_ORDER) == set(get_args(Severity))
    assert len(SEVERITY_ORDER) == len(set(SEVERITY_ORDER)), "a severity is ranked twice"


def test_severity_order_puts_breaking_first_and_info_last():
    """The order is a declared judgement, not a discovered fact, so it is asserted rather than
    described: `breaking` is a call site that will fail, `info` is a note. Everything between
    them is graded by what it costs the operator whose code calls the operation.
    """
    from sync.core.models import SEVERITY_ORDER

    assert SEVERITY_ORDER[0] == "breaking"
    assert SEVERITY_ORDER[-1] == "info"
    assert SEVERITY_ORDER.index("deprecation") > SEVERITY_ORDER.index("warning")

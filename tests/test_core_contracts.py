from datetime import datetime

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

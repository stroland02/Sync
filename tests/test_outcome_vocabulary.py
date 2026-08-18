"""Tests for M9: The outcome vocabulary.

Covers:
1. Flat schemas for all outcome tools (no top-level oneOf/allOf/anyOf).
2. Server-side validation with model-directed error messages.
3. Calibration rubric (confidence integers 1..10) and citation parsing (path:line with fenced quote).
4. Retired outcome tool name redirection.
5. Outcome data models in sync.core.outcomes.
"""

from __future__ import annotations

import pytest

from sync.core.outcomes import (
    CONFIDENCE_RUBRIC,
    Abandonment,
    Citation,
    ExternalCauseReport,
    FindingsReport,
    HumanQuestion,
    PatchProposal,
    parse_citation,
    validate_confidence,
)
from sync.runner.outcome_tools import (
    OUTCOME_TOOL_SCHEMAS,
    RETIRED_OUTCOME_TOOL_NAMES,
    OutcomeToolValidator,
    validate_outcome_call,
)


# --- 1. Flat schema invariant -----------------------------------------------------


def test_every_outcome_tool_has_a_flat_top_level_schema():
    """Reference-run learning (`superlog-02`): runner APIs reject composition keywords
    (oneOf/allOf/anyOf) at the top level of a tool's input_schema. A rejected schema
    blocks every run at agent-create time."""
    assert len(OUTCOME_TOOL_SCHEMAS) >= 5
    for schema in OUTCOME_TOOL_SCHEMAS:
        name = schema["name"]
        input_schema = schema["input_schema"]
        assert input_schema.get("type") == "object", f"{name} schema type must be 'object'"
        assert "oneOf" not in input_schema, f"{name} schema has top-level 'oneOf'"
        assert "allOf" not in input_schema, f"{name} schema has top-level 'allOf'"
        assert "anyOf" not in input_schema, f"{name} schema has top-level 'anyOf'"
        assert "properties" in input_schema, f"{name} schema missing 'properties'"


# --- 2. Calibration rubric and citation parsing -----------------------------------


def test_confidence_rubric_spans_one_to_ten():
    assert 1 in CONFIDENCE_RUBRIC
    assert 10 in CONFIDENCE_RUBRIC
    for score in range(1, 11):
        assert score in CONFIDENCE_RUBRIC
        assert len(CONFIDENCE_RUBRIC[score]) > 10


@pytest.mark.parametrize("valid_score", [1, 5, 10])
def test_validate_confidence_accepts_valid_integers(valid_score: int):
    ok, err = validate_confidence(valid_score)
    assert ok is True
    assert err is None


@pytest.mark.parametrize("invalid_score", [0, 11, -1, 5.5, "high", None])
def test_validate_confidence_rejects_out_of_range_or_non_integer(invalid_score):
    ok, err = validate_confidence(invalid_score)
    assert ok is False
    assert err is not None
    assert "1 to 10" in err


def test_parse_citation_valid_single_line():
    text = "src/billing.ts:14\n```typescript\nstripe.charges.create(params)\n```"
    citation = parse_citation(text)
    assert citation.path == "src/billing.ts"
    assert citation.line == 14
    assert citation.end_line is None
    assert "stripe.charges.create" in citation.quote


def test_parse_citation_valid_line_range():
    text = "src/billing.ts:14-16\n```typescript\nstripe.charges.create({\n  amount: 100\n})\n```"
    citation = parse_citation(text)
    assert citation.path == "src/billing.ts"
    assert citation.line == 14
    assert citation.end_line == 16
    assert "amount: 100" in citation.quote


def test_parse_citation_missing_line_number_raises_or_fails():
    with pytest.raises(ValueError, match="path:line"):
        parse_citation("src/billing.ts\n```typescript\nfoo\n```")


def test_parse_citation_missing_fenced_quote_raises_or_fails():
    with pytest.raises(ValueError, match="fenced code quote"):
        parse_citation("src/billing.ts:14\nno backticks here")


# --- 3. Outcome tool validation (server-side for the model) -----------------------


def test_validate_report_findings_valid():
    args = {
        "summary": "Stripe API v2026-11-01 removed charge status field",
        "root_cause": "Call site reads response.status which was deprecated in 2026-05-01",
        "confidence": 9,
        "estimated_impact": "Billing reconciliation webhook handler will raise AttributeError",
    }
    res = validate_outcome_call("report_findings", args)
    assert res.ok is True
    assert isinstance(res.payload, FindingsReport)
    assert res.payload.confidence == 9


def test_validate_report_findings_invalid_confidence():
    args = {
        "summary": "Stripe API v2026-11-01 removed charge status field",
        "root_cause": "Call site reads response.status",
        "confidence": 15,
    }
    res = validate_outcome_call("report_findings", args)
    assert res.ok is False
    assert "confidence" in res.error.lower()
    assert "1 to 10" in res.error


def test_validate_propose_patch_valid():
    args = {
        "diff": "--- a/src/billing.ts\n+++ b/src/billing.ts\n@@ -1,1 +1,1 @@\n-status\n+payment_status\n",
        "strategy": "agent",
        "rationale": "Updated field name to payment_status per vendor changelog",
        "confidence": 10,
        "citations": [
            "src/billing.ts:14\n```typescript\nconst status = charge.status;\n```"
        ],
    }
    res = validate_outcome_call("propose_patch", args)
    assert res.ok is True
    assert isinstance(res.payload, PatchProposal)
    assert res.payload.confidence == 10
    assert len(res.payload.citations) == 1
    assert res.payload.citations[0].path == "src/billing.ts"


def test_validate_propose_patch_missing_citations_fails():
    args = {
        "diff": "--- a/src/billing.ts\n+++ b/src/billing.ts\n",
        "strategy": "agent",
        "rationale": "Updated field name",
        "confidence": 10,
        "citations": [],
    }
    res = validate_outcome_call("propose_patch", args)
    assert res.ok is False
    assert "citation" in res.error.lower()


def test_validate_report_external_cause_valid():
    args = {
        "summary": "Stripe sandbox is returning 503 Service Unavailable",
        "cause": "Vendor outage on mock endpoints",
        "vendor": "stripe",
        "external_url": "https://status.stripe.com/incidents/123",
        "confidence": 8,
        "citations": [
            "src/billing.ts:25\n```typescript\nawait stripe.charges.create(params)\n```"
        ],
    }
    res = validate_outcome_call("report_external_cause", args)
    assert res.ok is True
    assert isinstance(res.payload, ExternalCauseReport)
    assert res.payload.vendor == "stripe"


def test_validate_ask_human_valid():
    args = {
        "question": "Should currency conversion use fixed EUR rate or dynamic FX quote?",
        "context": "Stripe multi-currency checkout requires explicit exchange source",
        "blocking": True,
        "confidence": 7,
        "citations": [
            "src/billing.ts:40\n```typescript\ncurrency: 'eur'\n```"
        ],
    }
    res = validate_outcome_call("ask_human", args)
    assert res.ok is True
    assert isinstance(res.payload, HumanQuestion)
    assert res.payload.blocking is True


def test_validate_abandon_valid():
    args = {
        "reason_code": "unsupported_sdk_version",
        "explanation": "Repository pins stripe-node v7 which cannot be migrated automatically to v18",
        "confidence": 9,
        "citations": [
            "package.json:15\n```json\n\"stripe\": \"^7.0.0\"\n```"
        ],
    }
    res = validate_outcome_call("abandon", args)
    assert res.ok is True
    assert isinstance(res.payload, Abandonment)
    assert res.payload.reason_code == "unsupported_sdk_version"


# --- 4. Retired tool names redirect -----------------------------------------------


@pytest.mark.parametrize(
    "retired_name,expected_redirect",
    [
        ("submit_patch", "propose_patch"),
        ("report_outage", "report_external_cause"),
        ("ask_user", "ask_human"),
        ("give_up", "abandon"),
    ],
)
def test_retired_outcome_tool_names_return_helpful_redirect_error(
    retired_name: str, expected_redirect: str
):
    assert retired_name in RETIRED_OUTCOME_TOOL_NAMES
    res = validate_outcome_call(retired_name, {})
    assert res.ok is False
    assert expected_redirect in res.error
    assert "renamed" in res.error.lower() or "retired" in res.error.lower()


# --- 5. Node and Graph integration ------------------------------------------------


class _FakeStore:
    def __init__(self):
        self.finding_status = None
        self.recorded_outcomes = []

    def set_finding_status(self, finding_id: str, status: str):
        self.finding_status = status

    def record_migration_outcome(self, outcome):
        self.recorded_outcomes.append(outcome)


class _FakeForge:
    def __init__(self):
        self.deleted_branches = []

    def delete_branch(self, repo, branch: str):
        self.deleted_branches.append(branch)


def test_make_external_cause_records_without_marking_finding_abandoned():
    from sync.core import CallSite, Finding, RepoRef, VendorChange
    from sync.remediate.nodes import make_external_cause

    store = _FakeStore()
    forge = _FakeForge()
    recorded = []

    def fake_record(state, terminal_status=None, abandon_reason=None):
        recorded.append((terminal_status, abandon_reason))

    external_cause_node = make_external_cause(store, forge, record=fake_record)

    state = {
        "finding": Finding(
            id="f1",
            detector="vendor_change",
            claim="response-field",
            call_site_id="cs1",
            vendor_change_id="vc1",
            severity="breaking",
            rationale="status field removed",
        ),
        "repo": RepoRef(repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40),
        "site": CallSite(
            repo_id="r1",
            path="src/billing.ts",
            line=6,
            col=8,
            vendor_id="stripe",
            operation_id="PostCharges",
            symbol="stripe.charges.create",
            args_keys=["amount"],
            response_fields_read=["status"],
            sdk_version="18.0.0",
            content_hash="h1",
        ),
        "change": VendorChange(
            vendor_id="stripe",
            from_version="v1",
            to_version="v2",
            kind="response-property-removed",
            operation_id="PostCharges",
            path_ptr="/x/status",
            severity="breaking",
            source="oasdiff",
            raw={"field": "status"},
        ),
        "branch": "sync/patch-f1-attempt-1",
        "external_cause_report": {
            "summary": "Stripe sandbox is down (HTTP 503)",
            "cause": "Vendor infrastructure issue",
        },
    }

    result = external_cause_node(state)
    assert result["outcome"] == "external_cause"
    assert "503" in result["report_reason"]
    assert store.finding_status is None  # NOT marked abandoned
    assert len(forge.deleted_branches) == 1
    assert forge.deleted_branches[0] == "sync/patch-f1-attempt-1"
    assert len(recorded) == 1
    assert recorded[0][0] == "external_cause"


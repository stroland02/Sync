"""Wiring GitHubForge.pull_request_outcome into the corpus so merge rate gets a numerator.

`open_pull_request` records the pull request number and the run ends. A pull request merges
days later, or never, and until something asks GitHub what became of it, `pr_merged` stays null
on every corpus row and the merge rate -- the direct test of the product claim -- has no numerator.

`reconcile_pull_request_outcomes` resolves the repository for each open attempt's finding,
queries `GitHubForge.pull_request_outcome(repo, pr_number)`, and updates `migration_outcome`
with the exact instant GitHub holds in `mergedAt` (rather than stamping `now()`).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from sync.benchmark.axes import compute_axes
from sync.benchmark.reconcile import reconcile_pull_request_outcomes
from sync.core import CallSite, Finding, MigrationOutcome, RepoRef, VendorChange
from sync.forge.github import COMMIT_AUTHOR_EMAIL, GitHubForge, PullRequestOutcome
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

REPO = RepoRef(
    repo_id="acme/payments",
    url="https://github.com/acme/payments",
    local_path="/tmp/acme-payments",
    head_sha="0" * 40,
)

SITE = CallSite(
    id="cs-1",
    repo_id="acme/payments",
    path="src/billing.ts",
    line=10,
    col=4,
    vendor_id="stripe",
    operation_id="PostCharges",
    symbol="stripe.charges.create",
    args_keys=["amount", "currency"],
    response_fields_read=["status"],
    sdk_version="18.0.0",
    content_hash="h1",
)

CHANGE = VendorChange(
    id="vc-1",
    vendor_id="stripe",
    from_version="2024-04-10",
    to_version="2024-06-20",
    kind="request-property-removed",
    operation_id="PostCharges",
    path_ptr="/v1/charges",
    severity="breaking",
    source="oasdiff",
    raw={"field": "amount"},
)

FINDING = Finding(
    id="f-1",
    detector="vendor_change",
    claim="request-field",
    call_site_id="cs-1",
    vendor_change_id="vc-1",
    severity="breaking",
    rationale="amount removed",
    binding_rung="static",
)


@pytest.fixture()
def store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _outcome(**overrides: Any) -> MigrationOutcome:
    fields: dict[str, Any] = dict(
        finding_id="f-1",
        attempt_index=0,
        vendor_id="stripe",
        from_version="2024-04-10",
        to_version="2024-06-20",
        change_kind="request-property-removed",
        change_severity="breaking",
        language="typescript",
        symbol_shape="stripe.charges.create",
        arg_arity=2,
        response_fields_touched_count=1,
        strategy="codemod",
        tier=0,
        routing_row="unrouted",
        wall_ms=1000,
        input_tokens=0,
        output_tokens=0,
        static_verify_passed=True,
        terminal_status="pr_opened",
        pr_number=41,
    )
    fields.update(overrides)
    return MigrationOutcome(**fields)


def _fake_forge(payloads: dict[int, dict]) -> GitHubForge:
    forge = GitHubForge()

    def _run(args: list[str], cwd: Path) -> str:
        # args: [_gh(), "pr", "view", str(number), ...]
        number = int(args[3])
        if number in payloads:
            return json.dumps(payloads[number])
        raise RuntimeError(f"no payload for PR #{number}")

    forge._run = _run  # type: ignore[method-assign]
    return forge


# --- Repository resolution per finding --------------------------------------


def test_repo_id_for_finding_resolves_through_call_site(store: GraphStore):
    cs_id = store.upsert_call_site(SITE)
    vc_id = store.upsert_vendor_change(CHANGE)
    f = Finding(
        detector="vendor_change",
        claim="request-field",
        call_site_id=cs_id,
        vendor_change_id=vc_id,
        severity="breaking",
        rationale="amount removed",
        binding_rung="static",
    )
    f_id = store.insert_finding(f)

    assert store.repo_id_for_finding(f_id) == "acme/payments"
    assert store.repo_id_for_finding("nonexistent") is None


def test_repo_ids_for_findings_batch_resolution(store: GraphStore):
    site2 = CallSite(
        id="cs-2",
        repo_id="acme/auth",
        path="src/auth.ts",
        line=20,
        col=8,
        vendor_id="auth0",
        operation_id="PostTokens",
        symbol="auth0.tokens.create",
        sdk_version="1.0.0",
        content_hash="h2",
    )
    cs1_id = store.upsert_call_site(SITE)
    cs2_id = store.upsert_call_site(site2)
    vc_id = store.upsert_vendor_change(CHANGE)
    f1 = Finding(
        detector="vendor_change",
        claim="request-field",
        call_site_id=cs1_id,
        vendor_change_id=vc_id,
        severity="breaking",
        rationale="amount removed",
        binding_rung="static",
    )
    f2 = Finding(
        detector="vendor_change",
        claim="token-field",
        call_site_id=cs2_id,
        severity="breaking",
        rationale="tokens changed",
        binding_rung="static",
    )
    f1_id = store.insert_finding(f1)
    f2_id = store.insert_finding(f2)

    resolved = store.repo_ids_for_findings([f1_id, f2_id, "f-unknown"])
    assert resolved == {f1_id: "acme/payments", f2_id: "acme/auth"}


# --- Stamping exact mergedAt timestamp vs fallback --------------------------


def test_set_merge_outcome_records_exact_timestamp_from_github(store: GraphStore):
    store.record_migration_outcome(_outcome())

    github_instant = "2026-08-16T10:04:00+00:00"
    store.set_merge_outcome(
        "f-1",
        0,
        pr_number=41,
        pr_merged=True,
        human_edits_before_merge=2,
        pr_merged_at=github_instant,
    )

    rows = store.migration_outcomes()
    assert len(rows) == 1
    assert rows[0].pr_merged is True
    assert rows[0].human_edits_before_merge == 2
    assert rows[0].pr_merged_at is not None
    assert rows[0].pr_merged_at.isoformat() == "2026-08-16T10:04:00+00:00"


def test_set_merge_outcome_unmerged_rejection_leaves_merged_at_null(store: GraphStore):
    store.record_migration_outcome(_outcome())

    store.set_merge_outcome(
        "f-1",
        0,
        pr_number=41,
        pr_merged=False,
        human_edits_before_merge=0,
    )

    rows = store.migration_outcomes()
    assert len(rows) == 1
    assert rows[0].pr_merged is False
    assert rows[0].pr_merged_at is None


# --- Reconciling PR outcomes into the corpus -------------------------------


def test_reconcile_pull_request_outcomes_updates_merged_and_closed_rows(store: GraphStore):
    # Set up graph with call sites and findings
    cs1_id = store.upsert_call_site(SITE)
    vc_id = store.upsert_vendor_change(CHANGE)
    f1 = Finding(
        detector="vendor_change",
        claim="request-field",
        call_site_id=cs1_id,
        vendor_change_id=vc_id,
        severity="breaking",
        rationale="amount removed",
        binding_rung="static",
    )
    f1_id = store.insert_finding(f1)

    # 1. Row with PR #41 that merged on GitHub
    store.record_migration_outcome(_outcome(finding_id=f1_id, attempt_index=0, pr_number=41))

    # 2. Row with PR #42 that was closed without merging
    site2 = CallSite(
        id="cs-2",
        repo_id="acme/payments",
        path="src/refunds.ts",
        line=15,
        col=4,
        vendor_id="stripe",
        operation_id="PostRefunds",
        symbol="stripe.refunds.create",
        sdk_version="18.0.0",
        content_hash="h2",
    )
    cs2_id = store.upsert_call_site(site2)
    finding2 = Finding(
        detector="vendor_change",
        claim="refund-field",
        call_site_id=cs2_id,
        severity="breaking",
        rationale="refund param",
        binding_rung="static",
    )
    f2_id = store.insert_finding(finding2)
    store.record_migration_outcome(_outcome(finding_id=f2_id, attempt_index=0, pr_number=42))

    # 3. Row with PR #43 that is still OPEN on GitHub
    site3 = CallSite(
        id="cs-3",
        repo_id="acme/payments",
        path="src/disputes.ts",
        line=25,
        col=4,
        vendor_id="stripe",
        operation_id="PostDisputes",
        symbol="stripe.disputes.create",
        sdk_version="18.0.0",
        content_hash="h3",
    )
    cs3_id = store.upsert_call_site(site3)
    finding3 = Finding(
        detector="vendor_change",
        claim="dispute-field",
        call_site_id=cs3_id,
        severity="breaking",
        rationale="dispute param",
        binding_rung="static",
    )
    f3_id = store.insert_finding(finding3)
    store.record_migration_outcome(_outcome(finding_id=f3_id, attempt_index=0, pr_number=43))

    forge = _fake_forge({
        41: {
            "number": 41,
            "state": "MERGED",
            "mergedAt": "2026-08-16T10:04:00Z",
            "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}],
        },
        42: {
            "number": 42,
            "state": "CLOSED",
            "mergedAt": None,
            "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}],
        },
        43: {
            "number": 43,
            "state": "OPEN",
            "mergedAt": None,
            "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}],
        },
    })

    repos = {"acme/payments": REPO}

    updated = reconcile_pull_request_outcomes(store, forge, repos)
    assert len(updated) == 2  # PR 41 (merged) and PR 42 (closed unmerged) resolved

    outcomes = store.migration_outcomes()
    by_f = {o.finding_id: o for o in outcomes}

    assert by_f[f1_id].pr_merged is True
    assert by_f[f1_id].pr_merged_at is not None
    assert by_f[f1_id].human_edits_before_merge == 0

    assert by_f[f2_id].pr_merged is False
    assert by_f[f2_id].pr_merged_at is None

    assert by_f[f3_id].pr_merged is None  # still waiting for review

    # The benchmark axes now compute real merge rate!
    axes = compute_axes(outcomes)
    assert axes.counts.pull_requests_opened == 3
    assert axes.counts.pull_requests_merged == 1
    # Merge rate over decided PRs (1 merged / 2 decided)
    assert axes.merge_rate_by_change_kind["request-property-removed"].value == 0.5
    assert axes.merge_rate_by_change_kind["request-property-removed"].n == 2


def test_cli_reconcile_pull_requests_command(store: GraphStore, monkeypatch):
    from sync.cli import build_parser, reconcile_pull_requests

    cs_id = store.upsert_call_site(SITE)
    finding = Finding(
        detector="vendor_change",
        claim="request-field",
        call_site_id=cs_id,
        severity="breaking",
        rationale="amount removed",
        binding_rung="static",
    )
    f_id = store.insert_finding(finding)
    store.record_migration_outcome(_outcome(finding_id=f_id, attempt_index=0, pr_number=41))

    forge = _fake_forge({
        41: {
            "number": 41,
            "state": "MERGED",
            "mergedAt": "2026-08-16T10:04:00Z",
            "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}],
        }
    })
    monkeypatch.setattr("sync.cli.GitHubForge", lambda: forge)

    args = build_parser().parse_args(["reconcile-pull-requests", "--dsn", DSN])
    exit_code = reconcile_pull_requests(args)
    assert exit_code == 0

    outcome = store.migration_outcomes()[0]
    assert outcome.pr_merged is True
    assert outcome.pr_merged_at is not None


def test_cli_benchmark_reconcile_flag(store: GraphStore, monkeypatch, capsys):
    from sync.cli import benchmark, build_parser

    cs_id = store.upsert_call_site(SITE)
    finding = Finding(
        detector="vendor_change",
        claim="request-field",
        call_site_id=cs_id,
        severity="breaking",
        rationale="amount removed",
        binding_rung="static",
    )
    f_id = store.insert_finding(finding)
    store.record_migration_outcome(_outcome(finding_id=f_id, attempt_index=0, pr_number=41))

    forge = _fake_forge({
        41: {
            "number": 41,
            "state": "MERGED",
            "mergedAt": "2026-08-16T10:04:00Z",
            "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}],
        }
    })
    monkeypatch.setattr("sync.cli.GitHubForge", lambda: forge)

    args = build_parser().parse_args(["benchmark", "--dsn", DSN, "--reconcile"])
    exit_code = benchmark(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "Merge rate" in captured.out or "merge_rate" in captured.out or "Merge decisions" in captured.out
    outcome = store.migration_outcomes()[0]
    assert outcome.pr_merged is True


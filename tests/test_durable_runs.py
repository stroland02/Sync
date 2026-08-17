"""Tests for M10: Durable runs, parked states, and the human turn.

M10 closes the loop between Sync and the human/CI review cycle:
1. A run parks in `awaiting_review` / `awaiting_ci` / `awaiting_human` instead of ending.
2. GitHub webhooks (review comments, changes_requested, check_runs) are parsed and verified.
3. A parked run resumes from its Postgres/memory checkpoint, formats model feedback,
   generates a follow-up fix commit, and pushes to the existing PR branch.
4. Distinguishes `parked`, `abandoned`, `opened`, `external_cause`, and `merged` outcomes in the corpus.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange, VerifyResult
from sync.forge.github import PullRequest
from sync.forge.webhook import (
    CheckRunEvent,
    PullRequestEvent,
    PullRequestReviewCommentEvent,
    PullRequestReviewEvent,
    WebhookFormatError,
    WebhookSignatureError,
    dispatch_webhook_event,
    format_review_feedback,
    parse_check_run_event,
    parse_pull_request_event,
    parse_review_comment_event,
    parse_review_event,
    verify_signature,
)
from sync.remediate import nodes
from sync.remediate.durable import resume_durable_run
from sync.remediate.graph import build_graph
from sync.remediate.state import Outcome, RunState

SECRET = b"test-webhook-secret"

SITE = CallSite(
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
    indexed_at=datetime(2026, 7, 25, 9, 30, tzinfo=timezone.utc),
)
CHANGE = VendorChange(
    vendor_id="stripe",
    from_version="v1",
    to_version="v2",
    kind="response-property-removed",
    operation_id="PostCharges",
    path_ptr="/x/status",
    severity="breaking",
    source="oasdiff",
    raw={"field": "status"},
    detected_at=datetime(2026, 7, 28, 11, 0, tzinfo=timezone.utc),
)
FINDING = Finding(
    id="f1",
    detector="vendor_change",
    claim="response-field",
    call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking",
    rationale="status removed",
    created_at=datetime(2026, 7, 28, 11, 5, tzinfo=timezone.utc),
)
REPO = RepoRef(
    repo_id="r1",
    url="https://example.invalid/r",
    local_path="/tmp/r",
    head_sha="0" * 40,
)


def _sign(body: bytes, secret: bytes = SECRET) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


class StubStore:
    def __init__(self):
        self.status = None
        self.status_calls = []
        self.outcomes = []
        self.merge_outcomes = []

    def get_call_site(self, _id):
        return SITE

    def get_vendor_change(self, _id):
        return CHANGE

    def set_finding_status(self, _id, _status):
        self.status = _status
        self.status_calls.append((_id, _status))

    def record_migration_outcome(self, outcome):
        self.outcomes.append(outcome)

    def migration_outcomes(self):
        return self.outcomes

    def set_merge_outcome(self, finding_id, attempt_index, pr_number, pr_merged, human_edits_before_merge):
        self.merge_outcomes.append((finding_id, attempt_index, pr_number, pr_merged, human_edits_before_merge))


class StubAdapter:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.prepare_calls = 0
        self.verify_calls = 0

    def prepare(self, _repo):
        self.prepare_calls += 1
        return True

    def static_verify(self, _repo, _patch):
        self.verify_calls += 1
        return VerifyResult(ok=self.ok, diagnostics="" if self.ok else "error TS2339")


class StubRemediator:
    def __init__(self, patches: list[Patch] | None = None):
        self.patches = list(patches or [Patch(diff="--- a\n+++ b\n", strategy="agent", rationale="fix")])
        self.calls = 0

    def propose(self, finding, change, site, repo, diagnostics=""):
        self.calls += 1
        if self.patches:
            return self.patches.pop(0)
        return Patch(diff=f"--- a\n+++ b\n+edit {self.calls}\n", strategy="agent", rationale="followup")


class StubForge:
    def __init__(self, pr_number: int = 42):
        self.pr_number = pr_number
        self.pushed_branches = []
        self.opened_prs = []
        self.deleted_branches = []

    def push_branch(self, _repo, _patch):
        branch = "sync/f1"
        self.pushed_branches.append(branch)
        return branch


    def await_ci(self, _repo, _branch):
        return True, "https://ci/1"

    def open_pull_request(self, repo, branch, evidence):
        self.opened_prs.append((branch, evidence))
        return PullRequest(number=self.pr_number, url=f"https://github.com/org/repo/pull/{self.pr_number}")

    def delete_branch(self, _repo, branch):
        self.deleted_branches.append(branch)



# ============================================================================
# 1. Parked State & Graph Routing Tests
# ============================================================================


def test_outcome_vocabulary_includes_parked():
    """`Outcome` literal carries 'parked' for suspended durable runs."""
    import typing
    from sync.remediate.state import Outcome

    assert "parked" in typing.get_args(Outcome)


def test_make_park_node_sets_parked_outcome_and_reason():
    """`make_park` sets outcome to 'parked' and preserves or defaults parked_reason."""
    store = StubStore()
    park_node = nodes.make_park(store)

    state: RunState = {
        "finding": FINDING,
        "repo": REPO,
        "branch": "sync/f1",
        "outcome": "running",
        "parked_reason": "awaiting_review",
    }
    result = park_node(state)

    assert result["outcome"] == "parked"
    assert result["parked_reason"] == "awaiting_review"


def test_durable_graph_routes_open_pr_to_park_node():
    """When built with durable=True, open_pr routes to park and marks outcome as parked."""
    store = StubStore()
    adapter = StubAdapter(ok=True)
    remediator = StubRemediator()
    forge = StubForge(pr_number=99)
    checkpointer = InMemorySaver()

    graph = build_graph(
        store=store,
        adapter=adapter,
        remediator=remediator,
        forge=forge,
        checkpointer=checkpointer,
        durable=True,
    )

    initial_state: RunState = {
        "finding": FINDING,
        "repo": REPO,
        "outcome": "running",
        "static_attempts": 0,
        "ci_attempts": 0,
        "durable": True,
    }

    config = {"configurable": {"thread_id": "thread-f1"}}
    final_state = graph.invoke(initial_state, config=config)

    assert final_state["outcome"] == "parked"
    assert final_state["parked_reason"] == "awaiting_review"
    assert final_state["pr_number"] == 99
    assert len(forge.opened_prs) == 1
    assert len(forge.deleted_branches) == 0


def test_a_parked_finding_is_not_counted_among_the_abandoned():
    """B134's corpus-level half of "abandoned distinguishable from parked": a finding whose
    run opened a pull request and parked for review must never be counted as one that gave
    up, and its own status must not read the same as a finding nothing has ever attempted.

    `park` itself writes no `migration_outcome` row -- parking is not a new attempt, it is a
    pause after the attempt that already succeeded and recorded `terminal_status="opened"`.
    So the corpus row this asserts on is the one `open_pr` wrote a beat earlier, and the
    property under test is that nothing downstream mistakes it for an abandonment.
    """
    store = StubStore()
    adapter = StubAdapter(ok=True)
    remediator = StubRemediator()
    forge = StubForge(pr_number=99)
    checkpointer = InMemorySaver()

    graph = build_graph(
        store=store, adapter=adapter, remediator=remediator, forge=forge,
        checkpointer=checkpointer, durable=True,
    )
    initial_state: RunState = {
        "finding": FINDING, "repo": REPO, "outcome": "running",
        "static_attempts": 0, "ci_attempts": 0, "durable": True,
    }
    config = {"configurable": {"thread_id": "thread-f1"}}
    final_state = graph.invoke(initial_state, config=config)

    assert final_state["outcome"] == "parked"
    assert [o.terminal_status for o in store.outcomes] == ["opened"]
    assert not any(o.terminal_status == "abandoned" for o in store.outcomes)


# ============================================================================
# 2. Webhook Event Parsing & Verification Tests
# ============================================================================


def test_parse_review_event_submitted_changes_requested():
    """Parses a pull_request_review event with changes_requested."""
    payload = {
        "action": "submitted",
        "review": {
            "state": "changes_requested",
            "body": "Please handle the status undefined fallback case.",
            "user": {"login": "alice"},
        },
        "pull_request": {
            "number": 42,
            "head": {"ref": "sync/fix-1"},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    event = parse_review_event(body)

    assert isinstance(event, PullRequestReviewEvent)
    assert event.action == "submitted"
    assert event.state == "changes_requested"
    assert event.body == "Please handle the status undefined fallback case."
    assert event.reviewer == "alice"
    assert event.pr_number == 42


def test_parse_review_comment_event_created():
    """Parses a pull_request_review_comment event on a specific line of code."""
    payload = {
        "action": "created",
        "comment": {
            "path": "src/billing.ts",
            "line": 12,
            "body": "This property was removed in Stripe v2, check status_code instead.",
            "diff_hunk": "@@ -10,4 +10,4 @@\n-const s = charge.status;\n+const s = charge.code;",
            "user": {"login": "bob"},
        },
        "pull_request": {
            "number": 42,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    event = parse_review_comment_event(body)

    assert isinstance(event, PullRequestReviewCommentEvent)
    assert event.action == "created"
    assert event.pr_number == 42
    assert event.path == "src/billing.ts"
    assert event.line == 12
    assert "Stripe v2" in event.body
    assert event.reviewer == "bob"
    assert "charge.status" in event.diff_hunk


def test_parse_check_run_event_completed_failure():
    """Parses a check_run event when CI finishes with failure."""
    payload = {
        "action": "completed",
        "check_run": {
            "conclusion": "failure",
            "head_sha": "abc12345",
            "output": {
                "title": "TypeScript Typecheck Failed",
                "summary": "src/billing.ts:12: Property status does not exist",
            },
        },
        "check_suite": {
            "pull_requests": [{"number": 42}],
        },
    }
    body = json.dumps(payload).encode("utf-8")
    event = parse_check_run_event(body)

    assert isinstance(event, CheckRunEvent)
    assert event.action == "completed"
    assert event.conclusion == "failure"
    assert event.pr_number == 42
    assert event.output_title == "TypeScript Typecheck Failed"
    assert "Property status does not exist" in event.output_summary


def test_format_review_feedback_structures_diff_and_comment():
    """`format_review_feedback` produces actionable prompt instruction from review comments."""
    comment_event = PullRequestReviewCommentEvent(
        action="created",
        pr_number=42,
        path="src/billing.ts",
        line=14,
        body="Use payment_intent.status instead of charge.status",
        diff_hunk="@@ -12,3 +12,3 @@",
        reviewer="reviewer1",
    )
    feedback = format_review_feedback(comment_event)

    assert "Review comment from reviewer1 on src/billing.ts:14" in feedback
    assert "Use payment_intent.status instead of charge.status" in feedback
    assert "@@ -12,3 +12,3 @@" in feedback


# ============================================================================
# 3. Durable Resumption & Follow-up Commit Loop Tests
# ============================================================================


def test_resume_durable_run_on_review_comment_pushes_followup_commit():
    """When a review comment arrives for a parked run, `resume_durable_run` wakes the run,
    applies feedback, runs patch, passes verification, and pushes a second commit to the same PR branch."""
    store = StubStore()
    adapter = StubAdapter(ok=True)
    # Remediator with initial patch and follow-up patch
    patch1 = Patch(diff="--- a\n+++ b\n-old\n+first_patch\n", strategy="agent", rationale="first attempt")
    patch2 = Patch(diff="--- a\n+++ b\n-first_patch\n+second_patch\n", strategy="agent", rationale="address review")
    remediator = StubRemediator(patches=[patch1, patch2])
    forge = StubForge(pr_number=42)
    checkpointer = InMemorySaver()

    graph = build_graph(
        store=store,
        adapter=adapter,
        remediator=remediator,
        forge=forge,
        checkpointer=checkpointer,
        durable=True,
    )

    thread_id = "f1"
    config = {"configurable": {"thread_id": thread_id}}

    # 1. Initial run -> parks at awaiting_review
    initial_state: RunState = {
        "finding": FINDING,
        "repo": REPO,
        "outcome": "running",
        "static_attempts": 0,
        "ci_attempts": 0,
        "durable": True,
    }
    parked_state = graph.invoke(initial_state, config=config)
    assert parked_state["outcome"] == "parked"
    assert parked_state["pr_number"] == 42
    assert len(forge.pushed_branches) == 1

    # 2. Review comment arrives
    review_comment = PullRequestReviewCommentEvent(
        action="created",
        pr_number=42,
        path="src/billing.ts",
        line=6,
        body="Please import IntentStatus enum instead of raw string.",
        diff_hunk="@@ -5,3 +5,3 @@",
        reviewer="senior-eng",
    )

    # 3. Resume run
    resumed_state = resume_durable_run(
        graph=graph,
        checkpointer=checkpointer,
        thread_id=thread_id,
        event=review_comment,
        store=store,
    )

    # 4. Verified follow-up execution
    assert resumed_state["outcome"] == "parked"
    assert resumed_state["parked_reason"] == "awaiting_review"
    assert resumed_state["turn"] == 2
    # Two commits pushed to the same branch
    assert len(forge.pushed_branches) == 2
    assert forge.pushed_branches[0] == forge.pushed_branches[1]
    # Feedback was recorded on the resumed state
    assert "senior-eng" in resumed_state.get("review_feedback", "") or "IntentStatus" in resumed_state.get("review_feedback", "")


def test_dispatch_webhook_event_routes_and_resumes():
    """`dispatch_webhook_event` verifies HMAC signature, decodes payload, locates thread, and resumes run."""
    store = StubStore()
    adapter = StubAdapter(ok=True)
    remediator = StubRemediator()
    forge = StubForge(pr_number=77)
    checkpointer = InMemorySaver()

    graph = build_graph(
        store=store,
        adapter=adapter,
        remediator=remediator,
        forge=forge,
        checkpointer=checkpointer,
        durable=True,
    )

    thread_id = "thread-77"
    config = {"configurable": {"thread_id": thread_id}}

    # Prime initial parked run
    state: RunState = {
        "finding": FINDING,
        "repo": REPO,
        "outcome": "running",
        "static_attempts": 0,
        "ci_attempts": 0,
        "durable": True,
    }
    graph.invoke(state, config=config)

    # Simulate webhook delivery for PR 77 review comment
    payload = {
        "action": "created",
        "comment": {
            "path": "src/billing.ts",
            "line": 6,
            "body": "Fix typings",
            "diff_hunk": "@@ -1 +1 @@",
            "user": {"login": "charlie"},
        },
        "pull_request": {"number": 77},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign(body, SECRET)

    resumed = dispatch_webhook_event(
        event_name="pull_request_review_comment",
        body=body,
        signature=sig,
        secret=SECRET,
        graph=graph,
        checkpointer=checkpointer,
        thread_id=thread_id,
        store=store,
    )

    assert resumed is True
    assert len(forge.pushed_branches) == 2

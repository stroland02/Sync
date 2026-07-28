import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange
from sync.forge.github import (
    COMMIT_AUTHOR_EMAIL,
    COMMIT_AUTHOR_NAME,
    GitHubForge,
    _gh,
    _owner_repo,
    branch_name_for,
    render_pr_body,
)
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.nodes import Forge

EVIDENCE = Evidence(
    spec_diff={"id": "response-property-removed", "field": "status"},
    changelog_entry="`status` was removed from charge responses",
    call_sites=["src/billing.ts:6"],
    ci_run_url="https://github.com/o/r/actions/runs/123",
)
PATCH = Patch(diff="--- a\n+++ b\n", strategy="agent", rationale="status removed")
REPO = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path="/tmp/r", head_sha="0" * 40)


def test_forge_satisfies_the_protocol_shape():
    assert isinstance(GitHubForge(), Forge)


def test_branch_name_is_deterministic_and_git_safe():
    name = branch_name_for(PATCH, REPO)
    assert name.startswith("sync/")
    assert " " not in name
    assert branch_name_for(PATCH, REPO) == name


def test_branch_name_differs_for_a_different_patch():
    """Two findings against the same repo must not collide on one branch name:
    the second push's `checkout -B` plus `--force-with-lease` would silently
    rewrite the first finding's already-opened pull request."""
    other = Patch(diff="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n", strategy="agent", rationale="a different fix")
    assert branch_name_for(other, REPO) != branch_name_for(PATCH, REPO)


def test_two_successive_patches_for_one_finding_resolve_to_the_same_branch():
    """A CI retry re-runs the patch node against the same finding, and the diff
    it produces is only the increment on top of the attempt already committed
    on the branch. If branch identity followed the diff, every retry would push
    a second `sync/api-drift-*` branch to the customer's repository and abandon
    the first — having already spent their Actions minutes on it."""
    first = Patch(diff="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n", strategy="agent", rationale="status removed")
    retry = Patch(diff="--- a\n+++ b\n@@ -9 +9 @@\n-still_broken\n+fixed\n", strategy="agent", rationale="status removed")
    assert branch_name_for(retry, REPO) == branch_name_for(first, REPO)


def test_a_patch_carries_its_findings_rationale_verbatim(tmp_path, monkeypatch):
    """`branch_name_for` treats `patch.rationale` as the finding's identity, which
    holds only while a remediator copies the finding's rationale into every patch
    it proposes for it. Were that to stop — a remediator writing its own text, a
    detector changing the format per attempt — branch identity would start
    varying between one finding's CI attempts again, stranding a pushed branch
    per retry, and every test in this file would still pass. This is where that
    assumption is supposed to break.

    The agent itself is stubbed out: what is under test is the contract between
    `Finding` and `Patch`, not the model call that fills the working tree.
    """
    repo_path = tmp_path / "clone"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, text=True,
                   encoding="utf-8", check=True)
    monkeypatch.setattr(AgentRemediator, "_run_agent", lambda self, prompt, path, identity: None)

    finding = Finding(
        detector="vendor_change",
        call_site_id="cs1",
        vendor_change_id="vc1",
        severity="breaking",
        rationale="response-property-removed on GetCharges: call site reads `status` (src/billing.ts:6)",
    )
    change = VendorChange(
        vendor_id="stripe", from_version="2024-01-01", to_version="2024-06-01",
        kind="response-property-removed", operation_id="GetCharges",
        path_ptr="/v1/charges", severity="breaking", source="oasdiff",
    )
    site = CallSite(
        repo_id="r1", path="src/billing.ts", line=6, col=2, vendor_id="stripe",
        operation_id="GetCharges", symbol="stripe.charges.retrieve",
        response_fields_read=["status"], sdk_version="14.0.0", content_hash="h",
    )
    repo = RepoRef(repo_id="r1", url=REPO.url, local_path=str(repo_path), head_sha="0" * 40)

    remediator = AgentRemediator()
    first = remediator.propose(finding, change, site, repo)
    retry = remediator.propose(finding, change, site, repo, diagnostics="tsc: error TS2339")

    assert first.rationale == finding.rationale
    assert branch_name_for(retry, repo) == branch_name_for(first, repo)


def test_two_findings_that_happen_to_produce_the_same_diff_do_not_share_a_branch():
    """The counterweight to the test above: stability across attempts must not
    be bought by making the name a function of the repository alone."""
    one = Patch(diff=PATCH.diff, strategy="agent", rationale="response-property-removed on GetCharges")
    two = Patch(diff=PATCH.diff, strategy="agent", rationale="request-parameter-removed on PostRefunds")
    assert branch_name_for(one, REPO) != branch_name_for(two, REPO)


def test_branch_name_is_git_safe_even_when_rationale_contains_illegal_characters():
    """`rationale` is free text an agent generated; it is the nearest thing a
    regression that starts splicing unsanitized input into the branch name
    would reach for. `branch_name_for` must stay safe regardless of what it
    contains, not just regardless of whether it contains a space."""
    hostile = Patch(
        diff=PATCH.diff,
        strategy="agent",
        rationale="fix: `status`? colon:tilde~caret^glob*range[a-z]..dotdot\\backslash",
    )
    name = branch_name_for(hostile, REPO)
    for illegal in (" ", ":", "~", "^", "?", "*", "[", "]", "..", "\\"):
        assert illegal not in name
    assert not name.endswith(".lock")


@pytest.mark.parametrize("url", [
    "https://github.com/o/r",
    "https://github.com/o/r.git",
    "https://github.com/o/r/",
    "git@github.com:o/r.git",
])
def test_gh_api_addresses_the_repository_as_owner_name(url):
    """`RepoRef.url` is whatever `--repo` was handed on the command line, and
    `gh api` needs `owner/name` out of it. A wrong parse sends the required
    status checks query to a path that 404s, which reads as an unprotected
    repository and silently drops `await_ci` to its weaker fallback gate."""
    assert _owner_repo(url) == "o/r"


def test_pr_body_contains_every_evidence_element():
    body = render_pr_body(EVIDENCE)
    assert "response-property-removed" in body
    assert "status" in body
    assert "src/billing.ts:6" in body
    assert "https://github.com/o/r/actions/runs/123" in body


def test_pr_body_states_that_ci_verified_the_change():
    body = render_pr_body(EVIDENCE).lower()
    assert "ci" in body
    assert "passed" in body or "green" in body


def test_pr_body_discloses_that_it_was_generated():
    assert "Sync" in render_pr_body(EVIDENCE)


def test_pr_body_discloses_the_limit_of_the_verification_gate():
    """`await_ci` gates on the base branch's required status checks where it can
    read them and on "any successful run for the commit" where it cannot — which
    is every repository where Sync's token is not an admin, the ordinary case
    rather than the edge one. A reviewer deciding whether to trust the linked run
    has no other surface to learn that from, and a gate that degrades quietly is
    the overclaim, not the degradation."""
    body = render_pr_body(EVIDENCE).lower()
    assert "required status checks" in body
    assert "admin" in body


def test_pr_body_preserves_non_ascii_characters_in_the_spec_diff():
    evidence = Evidence(
        spec_diff={"id": "response-property-removed", "note": "clé API supprimée — ne plus utiliser"},
        changelog_entry=EVIDENCE.changelog_entry,
        call_sites=EVIDENCE.call_sites,
        ci_run_url=EVIDENCE.ci_run_url,
    )
    assert "clé API supprimée — ne plus utiliser" in render_pr_body(evidence)


HEAD = "a" * 40


UNPROTECTED = "gh: Branch not protected (HTTP 404)"


def _forge_returning(payload: str, timeout_seconds: float = 1) -> GitHubForge:
    """A forge whose subprocess layer is replaced, so `await_ci`'s decision logic
    can be tested without git, without `gh`, and without the network.

    The repository it stands for has no branch protection Sync can read, so
    these cases exercise the fallback gate: any successful run counts.
    """
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=timeout_seconds)

    def fake_run(args, cwd):
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        if "protection/required_status_checks" in " ".join(args):
            raise RuntimeError(UNPROTECTED)
        return payload

    forge._run = fake_run
    return forge


def _run(status: str, conclusion: str | None, sha: str = HEAD, url: str = "https://ci/1",
         workflow: str = "CI") -> dict:
    return {"status": status, "conclusion": conclusion, "url": url, "headSha": sha,
            "workflowName": workflow}


def _check(name: str, status: str, conclusion: str | None, url: str) -> dict:
    """One entry of `gh api repos/{o}/{r}/commits/{sha}/check-runs`, whose shape
    differs from `gh run list`'s: check runs are named per job and carry
    `html_url`, and it is the job name that a required status check names."""
    return {"name": name, "status": status, "conclusion": conclusion, "html_url": url}


def _forge_against(
    contexts: list[str] | None,
    check_runs: list[dict] | None = None,
    runs: list[dict] | None = None,
    timeout_seconds: float = 0.3,
) -> GitHubForge:
    """A forge answering every argv `await_ci` issues against a repository whose
    base branch requires `contexts`.

    `contexts=None` stands for a repository Sync cannot read protection for:
    `gh api` exits non-zero, which is what both a base branch with no
    protection rule (404) and a token without the admin rights that endpoint
    requires (403) look like from here.
    """
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=timeout_seconds)

    def fake_run(args, cwd):
        if args[:2] == ["git", "rev-parse"]:
            return "origin/main" if args[-1] == "origin/HEAD" else HEAD
        joined = " ".join(args)
        if "protection/required_status_checks" in joined:
            if contexts is None:
                raise RuntimeError(UNPROTECTED)
            return json.dumps({"contexts": contexts})
        if "check-runs" in joined:
            assert "o/r" in joined, f"check runs must be read from the repository Sync pushed to: {joined}"
            return json.dumps({"total_count": len(check_runs), "check_runs": check_runs})
        return json.dumps(runs)

    forge._run = fake_run
    return forge


def test_an_always_green_unrelated_workflow_does_not_satisfy_a_protected_branch():
    """The observed shape: a `label.yml` running actions/labeler on every push,
    green in seconds, beside a `test.yml` whose job is gated
    `if: github.actor != 'sync-bot'` and therefore skips. Every run for the
    commit is either green or skipped, so a gate that only asks whether some
    run succeeded reports green and renders the labeler's URL as the
    verification link. Nothing typechecked or tested the patch."""
    forge = _forge_against(
        contexts=["test"],
        check_runs=[
            _check("label", "completed", "success", "https://ci/label"),
            _check("test", "completed", "skipped", "https://ci/test"),
        ],
        runs=[
            _run("completed", "success", url="https://ci/label", workflow="label"),
            _run("completed", "skipped", url="https://ci/test", workflow="test"),
        ],
    )
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "test" in detail


def test_the_required_check_supplies_the_url_a_reviewer_clicks():
    """Both runs are green here, so the gate opens either way; what the required
    contexts settle is which URL becomes `Evidence.ci_run_url`. The labeler
    sorts first and would win any tie-break among successful runs, so a URL
    pointing at it means the required-check filter did not happen."""
    forge = _forge_against(
        contexts=["test"],
        check_runs=[
            _check("label", "completed", "success", "https://ci/label"),
            _check("test", "completed", "success", "https://ci/test"),
        ],
        runs=[
            _run("completed", "success", url="https://ci/label", workflow="label"),
            _run("completed", "success", url="https://ci/test", workflow="test"),
        ],
    )
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/test"


def test_a_required_check_that_never_reports_is_not_a_verdict():
    """A required context with no check run for this commit is the case a
    workflow that does not trigger on `push` produces. Something else being
    green says nothing about it, and the message has to name what is missing:
    "CI is slow" and "the required workflow never ran" need different fixes."""
    forge = _forge_against(
        contexts=["test", "typecheck"],
        check_runs=[_check("label", "completed", "success", "https://ci/label")],
        runs=[_run("completed", "success", url="https://ci/label", workflow="label")],
    )
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "test" in detail
    assert "typecheck" in detail


def test_a_repository_with_no_readable_protection_falls_back_to_any_success():
    """Pins the documented limitation rather than endorsing it. With no required
    contexts to name, Sync cannot tell the workflow that verifies the patch from
    one that always passes, and accepts any success. Erring red instead would
    mean Sync opens no pull request against any repository whose protection it
    cannot read — which is every repository where its token is not an admin."""
    forge = _forge_against(
        contexts=None,
        runs=[
            _run("completed", "success", url="https://ci/label", workflow="label"),
            _run("completed", "skipped", url="https://ci/test", workflow="test"),
        ],
        timeout_seconds=1,
    )
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/label"


def test_ci_is_green_when_every_run_for_the_commit_succeeded():
    forge = _forge_returning(json.dumps([
        _run("completed", "success", url="https://ci/1"),
        _run("completed", "success", url="https://ci/2"),
    ]))
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/1"


def test_one_failing_workflow_makes_the_whole_commit_red():
    """The passing run (lint) comes first in `gh`'s newest-first ordering; the
    failing run (test) is second. A human reading the PR needs the failing
    one's URL, not whichever run happened to be newest."""
    forge = _forge_returning(json.dumps([
        _run("completed", "success", url="https://ci/lint"),
        _run("completed", "failure", url="https://ci/test"),
    ]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert detail == "https://ci/test"


def test_runs_still_in_progress_are_not_treated_as_a_verdict():
    forge = _forge_returning(json.dumps([_run("completed", "success"), _run("in_progress", None)]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "still running" in detail


def test_green_requires_the_run_set_to_be_stable_across_two_polls():
    """A `workflow_run: types: [completed]` chain (a workflow that only starts
    once another one finishes) creates its run record after the first
    workflow's record already reads completed/success. A poll landing in that
    gap sees one green run and must not treat it as the whole verdict — the
    second workflow hasn't started yet and might still fail.

    Poll 1: only `ci` is visible, and it already looks green.
    Poll 2: `integration` has appeared, but is still running.
    Poll 3: both are complete and green, for the first time.
    Poll 4: still both complete and green — now it is safe to call it green.
    """
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=2)
    responses = [
        json.dumps([_run("completed", "success", url="https://ci/ci")]),
        json.dumps([
            _run("completed", "success", url="https://ci/ci"),
            _run("in_progress", None, url="https://ci/integration"),
        ]),
        json.dumps([
            _run("completed", "success", url="https://ci/ci"),
            _run("completed", "success", url="https://ci/integration"),
        ]),
        json.dumps([
            _run("completed", "success", url="https://ci/ci"),
            _run("completed", "success", url="https://ci/integration"),
        ]),
    ]
    poll_count = 0

    def fake_run(args, cwd):
        nonlocal poll_count
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        if "protection/required_status_checks" in " ".join(args):
            raise RuntimeError(UNPROTECTED)
        raw = responses[poll_count]
        poll_count += 1
        return raw

    forge._run = fake_run
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/ci"
    # The load-bearing assertion: if `await_ci` returned as soon as it first
    # saw an all-green run set (poll 1, `ci` alone), it would stop here having
    # consumed only one response — exactly the bug this test exists to catch.
    assert poll_count == len(responses)


def test_a_run_from_an_earlier_push_to_the_same_branch_does_not_count():
    forge = _forge_returning(json.dumps([_run("completed", "success", sha="b" * 40)]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "no completed CI run" in detail


def test_a_branch_with_no_runs_at_all_is_red():
    forge = _forge_returning("[]")
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "no completed CI run" in detail


# Every conclusion `gh run list --json conclusion` can emit that indicates
# something genuinely went wrong. `not any(conclusion == "failure")` is the
# natural way to loosen the gate and would pass every test above it while
# still reading a cancelled, timed-out, or action-required run as green.
# `skipped` and `neutral` are deliberately excluded from this list — see the
# pair of tests below it, not this one.
BLOCKING_CONCLUSIONS = [
    "failure",
    "cancelled",
    "stale",
    "startup_failure",
    "timed_out",
    "action_required",
    None,
]


@pytest.mark.parametrize("conclusion", BLOCKING_CONCLUSIONS)
def test_every_blocking_conclusion_makes_the_commit_red(conclusion):
    """Each case pairs the blocking run with a success, so `failing` is the
    only route to red. A blocking run on its own reaches red either way — via
    `failing`, or, if it were wrongly classified as non-blocking, via the
    empty-`succeeded` path polling to the timeout — which leaves the assertion
    unable to say which set the conclusion belongs to. Paired, an
    over-inclusive `NON_BLOCKING_CONCLUSIONS` flips this green."""
    forge = _forge_returning(json.dumps([
        _run("completed", "success", url="https://ci/ok"),
        _run("completed", conclusion, url="https://ci/bad"),
    ]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert detail == "https://ci/bad"


# `skipped` (a job gated by `if:`) and `neutral` neither block a green verdict
# nor count toward one. A commit whose only runs skip is not verified by
# anything and must stay red; a commit where a gated workflow skips alongside
# one that actually ran and succeeded must not be held hostage by the gate.
NON_BLOCKING_CONCLUSIONS = ["skipped", "neutral"]


@pytest.mark.parametrize("conclusion", NON_BLOCKING_CONCLUSIONS)
def test_a_non_blocking_conclusion_alongside_a_success_is_green(conclusion):
    """The gated run comes first in the list, `gh`'s ordinary newest-first
    ordering whenever the gated workflow's run record is created after the
    one that actually verified the patch. A mutant that returns `runs[0]`
    instead of `succeeded[0]` would return the gated run's URL here — which
    would then become `ci_run_url` and render as the verification link a
    reviewer clicks, pointing at a run that did nothing."""
    forge = _forge_returning(json.dumps([
        _run("completed", conclusion, url="https://ci/gated"),
        _run("completed", "success", url="https://ci/ci"),
    ]))
    green, url = forge.await_ci(REPO, "sync/x")
    assert green is True
    assert url == "https://ci/ci"


@pytest.mark.parametrize("conclusion", NON_BLOCKING_CONCLUSIONS)
def test_a_non_blocking_conclusion_alone_is_red(conclusion):
    """Red, and red as soon as the run set stops changing rather than at the
    deadline — see `test_a_commit_that_can_never_go_green_is_abandoned_before_the_deadline`."""
    forge = _forge_returning(json.dumps([_run("completed", conclusion, workflow="test")]))
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert detail == f"nothing verified {HEAD[:12]}: test concluded {conclusion}"


def test_the_green_url_does_not_depend_on_the_order_gh_listed_the_runs():
    """`gh run list` orders by run id, so which successful run comes first is an
    accident of which workflow GitHub registered last. That URL is
    `Evidence.ci_run_url` and the link a reviewer clicks, and two attempts on
    the same commit must not cite different runs."""
    runs = [
        _run("completed", "success", url="https://ci/2", workflow="integration"),
        _run("completed", "success", url="https://ci/1", workflow="ci"),
    ]
    forward = _forge_returning(json.dumps(runs)).await_ci(REPO, "sync/x")
    backward = _forge_returning(json.dumps(list(reversed(runs)))).await_ci(REPO, "sync/x")
    assert forward == backward


def test_the_timeout_message_does_not_claim_a_still_running_workflow_completed():
    """Poll 1 sees one completed green run; poll 2 sees a second workflow that
    has since appeared and is still running, and the deadline passes there. The
    message becomes the next patch attempt's diagnostics and, on abandonment,
    the operator-facing reason, so it has to describe what the last poll saw —
    a flag latched by an earlier poll reports a state that a later one
    contradicted."""
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=0.5)
    responses = [
        json.dumps([_run("completed", "success", url="https://ci/ci")]),
        json.dumps([
            _run("completed", "success", url="https://ci/ci"),
            _run("in_progress", None, url="https://ci/integration"),
        ]),
    ]
    polls = 0

    def fake_run(args, cwd):
        nonlocal polls
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        if "protection/required_status_checks" in " ".join(args):
            raise RuntimeError(UNPROTECTED)
        # Each poll spends a large share of the budget deliberately: with a zero
        # poll interval and no cost per poll, the loop spins often enough that
        # the run set never appears to change while the deadline approaches.
        time.sleep(0.2)
        response = responses[min(polls, len(responses) - 1)]
        polls += 1
        return response

    forge._run = fake_run
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "still running" in detail
    # Below two polls the latched-flag path is never entered and the assertion
    # above would pass for the wrong reason.
    assert polls >= 2


def test_a_commit_that_can_never_go_green_is_abandoned_before_the_deadline():
    """Every run complete, none failing, none successful is terminal: the run set
    is stable, so no further poll can turn it green or red. Waiting out the full
    timeout costs the run half an hour it cannot use, and the graph then spends
    another model patch attempt and another pushed branch before abandoning."""
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=1800)
    payload = json.dumps([_run("completed", "skipped", url="https://ci/gated", workflow="test")])
    polls = 0

    def fake_run(args, cwd):
        nonlocal polls
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        if "protection/required_status_checks" in " ".join(args):
            raise RuntimeError(UNPROTECTED)
        polls += 1
        # Confirming stability takes two identical observations. A third means
        # `await_ci` is waiting on a set that has nothing left to change.
        assert polls <= 2, "await_ci kept polling a run set that could not change"
        return payload

    forge._run = fake_run
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "skipped" in detail


def test_timeout_message_does_not_claim_completed_runs_never_completed():
    """A commit whose only run goes green on its last poll before the deadline
    — one confirming poll short of being accepted as stable — is not the same
    failure mode as a commit whose CI never finished running. The message is
    fed straight into the next patch attempt's diagnostics and, on
    abandonment, the operator-facing reason; it must not tell either of them
    that nothing completed when something did."""
    forge = GitHubForge(poll_interval_seconds=1, timeout_seconds=1)
    payload = json.dumps([_run("completed", "success")])

    def fake_run(args, cwd):
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        if "protection/required_status_checks" in " ".join(args):
            raise RuntimeError(UNPROTECTED)
        return payload

    forge._run = fake_run
    green, detail = forge.await_ci(REPO, "sync/x")
    assert green is False
    assert "completed without a confirmed green verdict" in detail


def _forge_recording() -> tuple[GitHubForge, list[list[str]], list[Path]]:
    """A forge whose subprocess layer records every argv and cwd it was called
    with, so `push_branch` and `open_pull_request` — pure argv composition over
    `self._run` — can be tested without git, `gh`, or the network."""
    forge = GitHubForge()
    calls: list[list[str]] = []
    cwds: list[Path] = []

    def fake_run(args, cwd):
        calls.append(args)
        cwds.append(cwd)
        return ""

    forge._run = fake_run
    return forge, calls, cwds


def test_push_branch_issues_the_expected_git_sequence():
    forge, calls, cwds = _forge_recording()
    branch = forge.push_branch(REPO, PATCH)

    assert branch == branch_name_for(PATCH, REPO)
    assert calls == [
        ["git", "checkout", "-B", branch],
        ["git", "add", "-u"],
        ["git", "-c", f"user.name={COMMIT_AUTHOR_NAME}", "-c", f"user.email={COMMIT_AUTHOR_EMAIL}",
         "commit", "-m", f"fix: {PATCH.rationale}"],
        ["git", "push", "-u", "origin", branch, "--force-with-lease"],
    ]
    assert cwds == [Path(REPO.local_path)] * 4


def test_push_branch_commits_under_syncs_identity_with_real_git(tmp_path, monkeypatch):
    """`test_push_branch_issues_the_expected_git_sequence` stubs `_run` and never
    executes git, so it cannot catch a commit that fails, or one that silently
    inherits an identity from the host, under real git. This one runs the real
    `checkout`/`add`/`commit` sequence against a throwaway repository with the
    host's global and system git config suppressed, then reads the resulting
    commit's author back to prove Sync supplied its own identity rather than
    inheriting one.

    `push` is neutralised by monkeypatching `GitHubForge._run` at the class
    level to intercept any argv starting with `["git", "push"]` before it
    reaches `subprocess`, recording it instead; every other argv still goes
    through the real implementation, so `checkout`/`add`/`commit` run for
    real. There is no remote on this repository, so an unneutralised push
    would fail loudly rather than silently reach the network.
    """
    # Suppresses any global or system git identity the host machine happens to
    # have configured, so a pass here proves Sync's own `-c` overrides did the
    # work rather than the developer machine's config doing it for us.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    repo_path = tmp_path / "clone"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True)
    (repo_path / "file.txt").write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True)
    subprocess.run(
        ["git", "-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-m", "seed"],
        cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    (repo_path / "file.txt").write_text("patched\n", encoding="utf-8")

    real_run = GitHubForge._run
    pushes: list[list[str]] = []

    def run_with_push_neutralised(self, args, cwd):
        if args[:2] == ["git", "push"]:
            pushes.append(args)
            return ""
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_with_push_neutralised)

    repo = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path=str(repo_path), head_sha="0" * 40)
    forge = GitHubForge()
    forge.push_branch(repo, PATCH)

    assert len(pushes) == 1

    author = subprocess.run(
        ["git", "log", "-1", "--format=%an <%ae>"],
        cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    # Literal, not derived from the imported constants: this must catch a
    # wrong constant value, not just a wrong wiring of a correct one.
    assert author == "Sync <sync@users.noreply.github.com>"


def test_open_pull_request_issues_the_expected_gh_invocation():
    """Exact-argv equality, same standard as `push_branch`: a dropped `--body`
    would open a pull request carrying none of the evidence `Evidence` exists
    to deliver — no spec diff, no call sites, no CI run URL, no disclosure —
    and nothing about the return value would catch it. `--repo` matters
    because a forked clone's `gh pr create` infers the base repository from
    the remote unless told otherwise, which for a fork resolves to the fork's
    parent, not the repository Sync pushed to."""
    forge, calls, cwds = _forge_recording()
    forge.open_pull_request(REPO, "sync/x", EVIDENCE)

    assert calls == [
        [_gh(), "pr", "create",
         "--repo", REPO.url,
         "--title", f"fix: {EVIDENCE.changelog_entry[:60]}",
         "--body", render_pr_body(EVIDENCE),
         "--head", "sync/x"],
    ]
    assert cwds == [Path(REPO.local_path)]

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
    # A commit, because the patch is read as `git diff HEAD` and an unborn HEAD
    # names nothing. Every clone Sync works in has one; a repository with no
    # commit is a shape of this fixture, not of anything the pipeline sees.
    (repo_path / "file.txt").write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=repo_path, capture_output=True, text=True,
                   encoding="utf-8", check=True)
    subprocess.run(
        ["git", "-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-m", "seed"],
        cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    from sync.runner import ClaudeSdkRunner

    monkeypatch.setattr(ClaudeSdkRunner, "run", lambda self, prompt, path, identity: None)

    finding = Finding(
        detector="vendor_change",
        claim="response-field",
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


REMOTE_TIP = "b" * 40


def _forge_recording(remote_tip: str | None = None) -> tuple[GitHubForge, list[list[str]], list[Path]]:
    """A forge whose subprocess layer records every argv and cwd it was called
    with, so `push_branch` and `open_pull_request` — pure argv composition over
    `self._run` — can be tested without git, `gh`, or the network.

    `remote_tip` is what the remote holds for the branch. None makes the fetch
    fail the way git does when the ref is not there; a stub that answered every
    argv with the empty string would instead have `push_branch` lease against a
    commit named by nothing.
    """
    forge = GitHubForge()
    calls: list[list[str]] = []
    cwds: list[Path] = []

    def fake_run(args, cwd):
        calls.append(args)
        cwds.append(cwd)
        if args[:2] == ["git", "fetch"] and remote_tip is None:
            raise RuntimeError("fatal: couldn't find remote ref")
        if args[:2] == ["git", "rev-parse"]:
            return "origin/main" if args[-1] == "origin/HEAD" else remote_tip
        # The commits a stub places on the remote are ones an earlier run of the
        # same finding pushed; a stub answering the authorship walk with anything
        # else would have `push_branch` refuse its own branch here.
        if args[:2] == ["git", "log"]:
            return COMMIT_AUTHOR_EMAIL
        # `open_pull_request` asks GitHub for the number of the pull request it just
        # created, rather than parsing it back out of the URL. A stub answering the empty
        # string would make that call fail as a JSON decode error rather than exercising it.
        if args[1:3] == ["pr", "view"]:
            return '{"number": 41}'
        return ""

    forge._run = fake_run
    return forge, calls, cwds


def test_push_branch_issues_the_expected_git_sequence_for_a_new_branch():
    forge, calls, cwds = _forge_recording()
    branch = forge.push_branch(REPO, PATCH)

    assert branch == branch_name_for(PATCH, REPO)
    assert calls == [
        ["git", "checkout", "-B", branch],
        ["git", "add", "-u"],
        ["git", "-c", f"user.name={COMMIT_AUTHOR_NAME}", "-c", f"user.email={COMMIT_AUTHOR_EMAIL}",
         "commit", "-m", f"fix: {PATCH.rationale}"],
        ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
        ["git", "fetch", "--shallow-exclude=main", "origin",
         f"+refs/heads/{branch}:refs/remotes/origin/{branch}"],
        ["git", "push", "-u", "origin", branch],
    ]
    assert cwds == [Path(REPO.local_path)] * 6


def test_push_branch_leases_against_the_commit_it_fetched():
    """Exact argv, because the difference between leasing against the fetched
    commit and leasing against whatever `refs/remotes/origin/<branch>` currently
    says is invisible in behaviour until something else in the clone fetches —
    and the patch agent holds `Bash` in this clone. The authorship walk names the
    same fetched commit for the same reason, and ends at `HEAD`: what the push
    destroys is what the commit it is about to push does not carry forward."""
    forge, calls, cwds = _forge_recording(remote_tip=REMOTE_TIP)
    branch = forge.push_branch(REPO, PATCH)

    assert calls[-3:] == [
        ["git", "rev-parse", f"refs/remotes/origin/{branch}"],
        ["git", "log", "--format=%ae", REMOTE_TIP, "^HEAD"],
        ["git", "push", "-u", "origin", branch, f"--force-with-lease={branch}:{REMOTE_TIP}"],
    ]
    assert cwds == [Path(REPO.local_path)] * 8


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


def _git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    """Real git, failing loudly. The push tests below are worth nothing unless
    every step of their setup actually happened.

    `env` overlays the inherited environment rather than replacing it, so a test
    that sets a committer identity still gets the fixture's suppression of the
    host's global and system git config.
    """
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True,
        env=None if env is None else {**os.environ, **env},
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path, monkeypatch):
    """A bare repository standing in for the customer's GitHub repository.

    The host's global and system git config is suppressed for the whole test, so
    nothing here can pass on the developer machine's identity or push settings.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "--initial-branch=main", cwd=seed)
    (seed / "file.txt").write_text("original\n", encoding="utf-8")
    _git("add", "file.txt", cwd=seed)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-m", "seed", cwd=seed)

    bare = tmp_path / "remote.git"
    _git("clone", "--bare", str(seed), str(bare), cwd=tmp_path)
    return bare


def _sync_clone(remote: Path, dest: Path) -> RepoRef:
    """A clone shaped like the one `cli.py` makes, with the patch already applied.

    `--depth` implies `--single-branch`, so the clone carries no
    `refs/remotes/origin/*` for any branch but the default one. That absence is
    the whole mechanism these tests exist for, and a full clone would hide it: it
    would fetch a branch an earlier run had left behind and hand the lease the
    state this clone is supposed not to have. `as_uri` because git ignores
    `--depth` for a plain local path.
    """
    _git("clone", "--depth", "1", remote.as_uri(), str(dest), cwd=dest.parent)
    (dest / "file.txt").write_text("patched\n", encoding="utf-8")
    return RepoRef(
        repo_id="r1", url=remote.as_uri(), local_path=str(dest),
        head_sha=_git("rev-parse", "HEAD", cwd=dest),
    )


# Who put a commit on the branch. An earlier run of the same finding wrote as
# Sync; anyone else — a reviewer pushing a fixup — writes as themselves, and
# that difference is the whole of what `push_branch` may act on.
SYNC_WRITER = (COMMIT_AUTHOR_NAME, COMMIT_AUTHOR_EMAIL)
HUMAN_WRITER = ("Reviewer", "reviewer@example.com")


def _push_to_branch(
    remote: Path, workdir: Path, branch: str, content: str,
    writer: tuple[str, str], committer: tuple[str, str] | None = None,
) -> str:
    """Put a commit on `branch` from a clone of the writer's own, and return the
    sha the remote ends up at.

    `committer` overrides only the committer identity, leaving the author alone,
    which is what GitHub does to a commit it squashes or re-commits from the web
    editor.
    """
    _git("clone", remote.as_uri(), str(workdir), cwd=workdir.parent)
    if _git("ls-remote", "--heads", "origin", branch, cwd=workdir):
        _git("checkout", branch, cwd=workdir)
    else:
        _git("checkout", "-b", branch, cwd=workdir)
    (workdir / "file.txt").write_text(content, encoding="utf-8")
    _git("add", "-u", cwd=workdir)

    name, email = writer
    env = None
    if committer is not None:
        env = {"GIT_COMMITTER_NAME": committer[0], "GIT_COMMITTER_EMAIL": committer[1]}
    _git("-c", f"user.name={name}", "-c", f"user.email={email}",
         "commit", "-m", f"commit by {name}", cwd=workdir, env=env)
    _git("push", "origin", branch, cwd=workdir)
    return _git("rev-parse", "HEAD", cwd=workdir)


def _advance_default_branch(remote: Path, workdir: Path) -> None:
    """Move the customer's default branch on, which is what a repository anyone
    else commits to does between a finding's first attempt and its retry."""
    _git("clone", remote.as_uri(), str(workdir), cwd=workdir.parent)
    (workdir / "unrelated.txt").write_text("somebody else's work\n", encoding="utf-8")
    _git("add", "-A", cwd=workdir)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.com",
         "commit", "-m", "unrelated work", cwd=workdir)
    _git("push", "origin", "main", cwd=workdir)


def _resume_on_branch(clone: Path, branch: str) -> None:
    """Put the clone on a branch an earlier process pushed, the way `cli.py`'s
    `_checkout_branch` does when a checkpointed run resumes into a fresh clone.

    The fetch carries no `--depth`, which matters here: it leaves the branch's
    history deep in a clone that is otherwise shallow, and anything downstream
    that expects to walk only the commits the branch adds has to cope with that.
    """
    _git("fetch", "origin", f"+{branch}:refs/remotes/origin/{branch}", cwd=clone)
    _git("checkout", "-f", "-B", branch, f"origin/{branch}", cwd=clone)
    (clone / "file.txt").write_text("patched\n", encoding="utf-8")


def test_push_branch_creates_a_branch_the_remote_does_not_have(tmp_path, remote):
    """The ordinary case, and the one that must not regress while the re-run case
    is being fixed: nothing exists to lease against, and the push has to create
    the branch."""
    repo = _sync_clone(remote, tmp_path / "clone")

    branch = GitHubForge().push_branch(repo, PATCH)

    assert _git("rev-parse", branch, cwd=remote) == _git("rev-parse", "HEAD", cwd=Path(repo.local_path))


def _shipped(remote: Path, branch: str) -> list[str]:
    """Every path the branch actually carries on the remote. Read from the bare
    repository rather than from the clone, because what the clone holds and what
    the push delivered are the two things these tests exist to tell apart."""
    return _git("ls-tree", "-r", "--name-only", branch, cwd=remote).splitlines()


def test_push_branch_carries_a_new_file_the_patch_needed(tmp_path, remote):
    """Some correct fixes need a module that is not there yet -- an extracted
    helper, a type declaration, a shim -- and `git add -u` never stages an
    untracked path. Before staging became the agent's assertion, such a patch
    could not ship: the file was held out of the typecheck as untracked, the gate
    failed on the unresolved import, and the finding abandoned naming a compile
    error rather than the reason, which was that Sync structurally could not
    carry a new file.

    A file the agent staged itself is not untracked. It is in the index, `git add
    -u` refreshes rather than drops it, and the commit carries it.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    clone = Path(repo.local_path)
    (clone / "money.ts").write_text("export const toCents = (n: number) => n * 100;\n", encoding="utf-8")
    _git("add", "money.ts", cwd=clone)

    branch = GitHubForge().push_branch(repo, PATCH)

    assert "money.ts" in _shipped(remote, branch)
    assert "toCents" in _git("show", f"{branch}:money.ts", cwd=remote)
    # The tracked modification still ships alongside it: a commit carrying only
    # the new file would satisfy both assertions above and be half a patch.
    assert "patched" in _git("show", f"{branch}:file.txt", cwd=remote)


def test_push_branch_leaves_behind_a_file_the_agent_never_staged(tmp_path, remote):
    """The guard, and the test that would silently pass if it were dropped -- the
    case above says nothing about debris. The patch agent holds `Bash` inside this
    clone and its tool calls leave things behind that no part of the patch or the
    review evidence describes: a build directory, a log, a stray dependency
    install. A branch carrying that is worse than one that never opened, and
    `git add -A` here would commit all of it.

    Neither of these is gitignored, deliberately. Ignored paths are excluded by
    git itself, so an assertion resting on them would hold with the staging
    widened to `-A` and prove nothing.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    clone = Path(repo.local_path)
    (clone / "build").mkdir()
    (clone / "build" / "bundle.js").write_text("// generated\n", encoding="utf-8")
    (clone / "npm-debug.log").write_text("noise\n", encoding="utf-8")

    branch = GitHubForge().push_branch(repo, PATCH)

    shipped = _shipped(remote, branch)
    assert "build/bundle.js" not in shipped
    assert "npm-debug.log" not in shipped
    # An empty commit would satisfy both assertions above for the wrong reason.
    assert "patched" in _git("show", f"{branch}:file.txt", cwd=remote)


def test_push_branch_updates_a_branch_an_earlier_run_left_on_the_remote(tmp_path, remote):
    """Re-running a finding is ordinary — after fixing an environment fault or an
    earlier bug — and branch identity is derived from the finding, so the branch
    this run targets is the one the earlier run already pushed. The clone has
    never seen that ref, and a lease with nothing recorded means "this ref must
    not exist", so Sync refuses its own branch and the run abandons. That is what
    the M0 acceptance run died of."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)

    assert GitHubForge().push_branch(repo, PATCH) == branch
    assert _git("rev-parse", branch, cwd=remote) == _git("rev-parse", "HEAD", cwd=Path(repo.local_path))


def test_push_branch_updates_a_branch_of_its_own_that_github_re_committed(tmp_path, remote):
    """A commit Sync authored can reach the branch with a committer that is not
    Sync: GitHub rewrites the committer on a squash and on any edit made through
    the web UI, and a rebase rewrites it too while leaving the author alone.
    Reading the committer instead of the author would call that commit a
    stranger's and abandon a finding whose branch Sync wrote every line of."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(
        remote, tmp_path / "earlier", branch, "an earlier attempt\n",
        SYNC_WRITER, committer=("GitHub", "noreply@github.com"),
    )

    assert GitHubForge().push_branch(repo, PATCH) == branch
    assert _git("rev-parse", branch, cwd=remote) == _git("rev-parse", "HEAD", cwd=Path(repo.local_path))


def test_push_branch_refuses_a_branch_whose_tip_somebody_else_wrote(tmp_path, remote):
    """A reviewer pushing a fixup onto Sync's branch between runs is the case that
    matters: the lease only knows the tip was observed, not whose it was, so it
    would fetch their commit and then replace it. Discarding a human's work on a
    repository Sync does not own is the worst thing this product can do, and it
    would be silent — the run would go on to open a pull request."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)

    with pytest.raises(RuntimeError, match="reviewer@example.com"):
        GitHubForge().push_branch(repo, PATCH)

    assert _git("rev-parse", branch, cwd=remote) == theirs


def test_push_branch_refuses_a_branch_hiding_a_stranger_commit_under_a_sync_tip(tmp_path, remote):
    """The tip is not the question; what the push would destroy is.

    A reviewer pushes a fixup onto Sync's branch and a Sync-authored commit then
    lands above it — a rebase, a cherry-pick, an amend that reorders. The branch
    now points at a commit Sync wrote, sitting on one it did not, and a check
    that reads only the tip sees nothing wrong. The force-push then discards the
    reviewer's commit, silently, on a repository Sync does not own.

    Every other push test in this file passes with the check reading only the
    tip. This is the one that does not.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)
    tip = _push_to_branch(remote, tmp_path / "later", branch, "a later Sync attempt\n", SYNC_WRITER)

    with pytest.raises(RuntimeError, match="reviewer@example.com"):
        GitHubForge().push_branch(repo, PATCH)

    assert _git("rev-parse", branch, cwd=remote) == tip
    # The tip surviving is not the property that matters — the commit underneath
    # it is what a tip-only check would have thrown away.
    assert theirs in _git("rev-list", branch, cwd=remote).splitlines()


def test_push_branch_updates_a_branch_of_its_own_that_has_several_commits(tmp_path, remote):
    """Widening the check from one commit to a range must not turn the ordinary
    retry into a refusal. A finding that has already retried once leaves two
    commits behind, both Sync's, and the next attempt has to replace them."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "first", branch, "the first attempt\n", SYNC_WRITER)
    _push_to_branch(remote, tmp_path / "second", branch, "the second attempt\n", SYNC_WRITER)

    assert GitHubForge().push_branch(repo, PATCH) == branch
    assert _git("rev-parse", branch, cwd=remote) == _git("rev-parse", "HEAD", cwd=Path(repo.local_path))


def test_push_branch_updates_a_branch_created_before_the_default_branch_moved(tmp_path, remote):
    """The retry that arrives days later, against a repository that did not stand
    still: the branch forks from a default branch commit the new clone cannot
    see, because `--depth` cut the history above it. There is no merge base to
    compute, so a range anchored on the clone's own HEAD sweeps in the customer's
    default branch commits along with Sync's — and refuses a push that would
    discard nothing but Sync's own work.

    Nothing about this is exotic. Every retry against a repository anyone else
    commits to lands here, which makes it the failure mode that would take the
    whole retry path down rather than one branch.
    """
    # The branch name is a function of the repository id and the patch's
    # rationale alone, so it is known before the clone that will push to it
    # exists — which it has to be, because the default branch has to move
    # between the branch being created and the clone being made.
    branch = branch_name_for(PATCH, RepoRef(
        repo_id="r1", url=remote.as_uri(), local_path=str(tmp_path), head_sha="0" * 40))
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)
    _advance_default_branch(remote, tmp_path / "moved")

    repo = _sync_clone(remote, tmp_path / "clone")
    assert branch == branch_name_for(PATCH, repo)

    assert GitHubForge().push_branch(repo, PATCH) == branch
    assert _git("rev-parse", branch, cwd=remote) == _git("rev-parse", "HEAD", cwd=Path(repo.local_path))


def test_push_branch_carries_a_stranger_commit_forward_rather_than_refusing(tmp_path, remote):
    """A resumed run checks the clone out onto the branch it pushed and commits on
    top of it, so a reviewer's fixup already on that branch is a parent of what
    Sync is about to push — carried forward, not discarded. The check is about
    what the push destroys, and this push destroys nothing.

    Refusing here instead would make any branch unusable to Sync the moment
    anyone touched it, which is a different bug from the one the check exists
    for.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)
    _resume_on_branch(Path(repo.local_path), branch)

    assert GitHubForge().push_branch(repo, PATCH) == branch
    assert theirs in _git("rev-list", branch, cwd=remote).splitlines()


def test_push_branch_refuses_a_branch_that_moved_after_it_was_fetched(tmp_path, remote, monkeypatch):
    """The race the lease exists for, and the only test here that separates a
    lease against observed state from a plain `--force`: every other test in this
    file passes either way.

    A second writer moves the branch between Sync's fetch and Sync's push, so the
    state Sync observed is no longer the state it would overwrite. The push must
    be refused and their commit must survive.

    Both commits are written as Sync, so the authorship check cannot be what
    refuses this push. Were the interloper a human, this test would pass with the
    lease deleted entirely.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)

    real_run = GitHubForge._run
    interloper: list[str] = []

    def run_with_a_writer_between_fetch_and_push(self, args, cwd):
        if args[:2] == ["git", "push"] and not interloper:
            interloper.append(
                _push_to_branch(remote, tmp_path / "interloper", branch,
                                "work Sync never saw\n", SYNC_WRITER)
            )
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_with_a_writer_between_fetch_and_push)

    with pytest.raises(RuntimeError):
        GitHubForge().push_branch(repo, PATCH)

    # The property, not the wording git happens to reject with: what the other
    # writer pushed is still what the branch points at.
    assert _git("rev-parse", branch, cwd=remote) == interloper[0]


def _forge_with_pull_requests(monkeypatch, listing: str) -> GitHubForge:
    """A forge whose git runs for real and whose `gh pr list` answers `listing`.

    The pull request state these tests turn on lives on GitHub, not in the bare
    repository standing in for it, so it is the one thing here that has to be
    stubbed. Everything else — the branch, its tip, its author, whether the
    deletion actually took — is real git against a real remote.
    """
    real_run = GitHubForge._run

    def run_with_gh_stubbed(self, args, cwd):
        if args[1:3] == ["pr", "list"]:
            return listing
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_with_gh_stubbed)
    return GitHubForge()


def _remote_has(remote: Path, branch: str) -> bool:
    return bool(_git("ls-remote", "--heads", str(remote), branch, cwd=remote))


def test_delete_branch_removes_a_branch_an_abandoned_finding_left_behind(tmp_path, remote, monkeypatch):
    """A finding that abandons after pushing leaves a branch with no pull request
    on a repository Sync does not own. One is untidy; a fleet of them is a mess
    Sync made and never cleaned up."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "run", branch, "the abandoned attempt\n", SYNC_WRITER)
    forge = _forge_with_pull_requests(monkeypatch, "[]")

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is True
    assert not _remote_has(remote, branch)
    assert branch in detail


def test_delete_branch_keeps_a_branch_that_has_an_open_pull_request(tmp_path, remote, monkeypatch):
    """A pull request open on the branch means a human may be reading it right
    now. Abandonment is Sync's verdict on its own patch, not permission to close
    a review out from under whoever is in it."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "run", branch, "the abandoned attempt\n", SYNC_WRITER)
    forge = _forge_with_pull_requests(monkeypatch, json.dumps([{"number": 7}]))

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is False
    assert _remote_has(remote, branch)
    assert "pull request" in detail


def test_delete_branch_keeps_a_branch_whose_tip_somebody_else_wrote(tmp_path, remote, monkeypatch):
    """Same rule as the push, for the same reason: a tip Sync did not author is
    somebody's work, and cleanup is not a licence to delete it."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)
    forge = _forge_with_pull_requests(monkeypatch, "[]")

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is False
    assert _git("rev-parse", branch, cwd=remote) == theirs
    assert "reviewer@example.com" in detail


def test_delete_branch_keeps_a_branch_hiding_a_stranger_commit_under_a_sync_tip(tmp_path, remote, monkeypatch):
    """Deleting a branch destroys every commit it adds, not only the one it points
    at, so a tip Sync authored says nothing about what the deletion costs. Same
    rule as the push and the same reason, over a range the deletion makes wider:
    the push at least leaves behind whatever it carries forward."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)
    _push_to_branch(remote, tmp_path / "later", branch, "a later Sync attempt\n", SYNC_WRITER)
    forge = _forge_with_pull_requests(monkeypatch, "[]")

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is False
    assert theirs in _git("rev-list", branch, cwd=remote).splitlines()
    assert "reviewer@example.com" in detail


def test_delete_branch_keeps_a_stranger_commit_the_clone_is_itself_sitting_on(tmp_path, remote, monkeypatch):
    """The push and the deletion ask different questions, and this is where the
    difference shows. A resumed run leaves the clone checked out on the branch, so
    a reviewer's fixup on it is part of the clone's own history — which makes it
    something the push carries forward and nothing at all to the deletion, since
    no ref on the remote would keep it reachable afterwards.

    A deletion that reused the push's range, excluding what the clone already
    has, would find nothing to object to here and remove their commit.
    """
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "earlier", branch, "an earlier attempt\n", SYNC_WRITER)
    theirs = _push_to_branch(remote, tmp_path / "reviewer", branch, "a reviewer's fixup\n", HUMAN_WRITER)
    _push_to_branch(remote, tmp_path / "later", branch, "a later Sync attempt\n", SYNC_WRITER)
    _resume_on_branch(Path(repo.local_path), branch)
    forge = _forge_with_pull_requests(monkeypatch, "[]")

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is False
    assert _remote_has(remote, branch)
    assert theirs in _git("rev-list", branch, cwd=remote).splitlines()
    assert "reviewer@example.com" in detail


def test_delete_branch_removes_a_branch_of_its_own_that_has_several_commits(tmp_path, remote, monkeypatch):
    """The counterweight: widening what the deletion inspects must not leave
    every retried finding's branch behind. Two attempts, both Sync's, is what a
    finding that retried once and then abandoned leaves on the remote."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "first", branch, "the first attempt\n", SYNC_WRITER)
    _push_to_branch(remote, tmp_path / "second", branch, "the second attempt\n", SYNC_WRITER)
    forge = _forge_with_pull_requests(monkeypatch, "[]")

    deleted, detail = forge.delete_branch(repo, branch)

    assert deleted is True
    assert not _remote_has(remote, branch)
    assert branch in detail


def test_delete_branch_does_nothing_when_the_remote_has_no_such_branch(tmp_path, remote, monkeypatch):
    """Abandonment before the push is the ordinary case — a patch that never
    typechecked never reached a branch — and cleanup runs for those too. Asking
    the remote to delete a branch that was never there earns an error worth
    reporting to nobody, so the deletion must not be attempted at all."""
    repo = _sync_clone(remote, tmp_path / "clone")
    real_run = GitHubForge._run
    pushes: list[list[str]] = []

    def run_recording_pushes(self, args, cwd):
        if args[1:3] == ["pr", "list"]:
            return "[]"
        if args[:2] == ["git", "push"]:
            pushes.append(args)
            return ""
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_recording_pushes)

    deleted, detail = GitHubForge().delete_branch(repo, "sync/api-drift-never-pushed")

    assert deleted is False
    assert pushes == []
    # Nothing to delete is a normal outcome, not a failed deletion. Reported as a
    # failure it would put a git error into an abandon record whose actual reason
    # is the finding's, and send an operator looking for a fault that is not there.
    assert "could not" not in detail


def test_delete_branch_keeps_a_branch_that_moved_after_it_was_checked(tmp_path, remote, monkeypatch):
    """The same race as the push, on the way out. Between reading the tip and
    deleting the branch, somebody pushes to it; the branch Sync checked is not
    the branch it would remove. Both commits here are written as Sync, so
    authorship cannot be what refuses this — only the lease can."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "run", branch, "the abandoned attempt\n", SYNC_WRITER)

    real_run = GitHubForge._run
    interloper: list[str] = []

    def run_with_a_writer_before_the_deletion(self, args, cwd):
        if args[1:3] == ["pr", "list"]:
            return "[]"
        if args[:2] == ["git", "push"] and not interloper:
            interloper.append(
                _push_to_branch(remote, tmp_path / "interloper", branch,
                                "work Sync never saw\n", SYNC_WRITER)
            )
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_with_a_writer_before_the_deletion)

    deleted, detail = GitHubForge().delete_branch(repo, branch)

    assert deleted is False
    assert detail
    assert _git("rev-parse", branch, cwd=remote) == interloper[0]


def test_delete_branch_reports_a_failed_deletion_rather_than_raising(tmp_path, remote, monkeypatch):
    """Cleanup runs after a finding has already failed, and the operator's useful
    signal is why the finding abandoned. A cleanup that raises replaces that
    reason with its own and loses the one that matters."""
    repo = _sync_clone(remote, tmp_path / "clone")
    branch = branch_name_for(PATCH, repo)
    _push_to_branch(remote, tmp_path / "run", branch, "the abandoned attempt\n", SYNC_WRITER)

    real_run = GitHubForge._run

    def run_with_the_deletion_failing(self, args, cwd):
        if args[1:3] == ["pr", "list"]:
            return "[]"
        if args[:2] == ["git", "push"]:
            raise RuntimeError("remote: refusing to delete a protected branch")
        return real_run(self, args, cwd)

    monkeypatch.setattr(GitHubForge, "_run", run_with_the_deletion_failing)

    deleted, detail = GitHubForge().delete_branch(repo, branch)

    assert deleted is False
    assert "protected" in detail
    assert _remote_has(remote, branch)


def test_open_pull_request_issues_the_expected_gh_invocation():
    """Exact-argv equality, same standard as `push_branch`: a dropped `--body`
    would open a pull request carrying none of the evidence `Evidence` exists
    to deliver — no spec diff, no call sites, no CI run URL, no disclosure —
    and nothing about the return value would catch it. `--repo` matters
    because a forked clone's `gh pr create` infers the base repository from
    the remote unless told otherwise, which for a fork resolves to the fork's
    parent, not the repository Sync pushed to."""
    forge, calls, cwds = _forge_recording()
    pull_request = forge.open_pull_request(REPO, "sync/x", EVIDENCE)

    # Two invocations now, and the second is part of the contract rather than an
    # implementation detail: the number is asked of GitHub because parsing it out of the URL
    # would be a second implementation of what `gh` already knows, failing by producing a
    # plausible wrong number rather than an error.
    assert calls == [
        [_gh(), "pr", "create",
         "--repo", REPO.url,
         "--title", f"fix: {EVIDENCE.changelog_entry[:60]}",
         "--body", render_pr_body(EVIDENCE),
         "--head", "sync/x"],
        [_gh(), "pr", "view", "", "--repo", REPO.url, "--json", "number"],
    ]
    assert cwds == [Path(REPO.local_path), Path(REPO.local_path)]
    assert pull_request.number == 41

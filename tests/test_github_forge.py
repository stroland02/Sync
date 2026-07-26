import json

import pytest

from sync.core import Evidence, Patch, RepoRef
from sync.forge.github import GitHubForge, branch_name_for, render_pr_body
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


def test_pr_body_preserves_non_ascii_characters_in_the_spec_diff():
    evidence = Evidence(
        spec_diff={"id": "response-property-removed", "note": "clé API supprimée — ne plus utiliser"},
        changelog_entry=EVIDENCE.changelog_entry,
        call_sites=EVIDENCE.call_sites,
        ci_run_url=EVIDENCE.ci_run_url,
    )
    assert "clé API supprimée — ne plus utiliser" in render_pr_body(evidence)


HEAD = "a" * 40


def _forge_returning(payload: str, timeout_seconds: int = 1) -> GitHubForge:
    """A forge whose subprocess layer is replaced, so `await_ci`'s decision logic
    can be tested without git, without `gh`, and without the network."""
    forge = GitHubForge(poll_interval_seconds=0, timeout_seconds=timeout_seconds)

    def fake_run(args, cwd):
        if args[:2] == ["git", "rev-parse"]:
            return HEAD
        return payload

    forge._run = fake_run
    return forge


def _run(status: str, conclusion: str | None, sha: str = HEAD, url: str = "https://ci/1") -> dict:
    return {"status": status, "conclusion": conclusion, "url": url, "headSha": sha}


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
    assert "never" in detail and "completed" in detail


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


# Every conclusion `gh run list --json conclusion` can emit besides "success".
# `not any(conclusion == "failure")` is the natural way to loosen the gate and
# would pass every test above it while still reading a cancelled, timed-out,
# or action-required run as green.
NON_SUCCESS_CONCLUSIONS = [
    "failure",
    "cancelled",
    "neutral",
    "skipped",
    "stale",
    "startup_failure",
    "timed_out",
    "action_required",
    None,
]


@pytest.mark.parametrize("conclusion", NON_SUCCESS_CONCLUSIONS)
def test_every_non_success_conclusion_makes_the_commit_red(conclusion):
    forge = _forge_returning(json.dumps([_run("completed", conclusion)]))
    green, _ = forge.await_ci(REPO, "sync/x")
    assert green is False


def _forge_recording() -> tuple[GitHubForge, list[list[str]]]:
    """A forge whose subprocess layer records every argv it was called with,
    so `push_branch` and `open_pull_request` — pure argv composition over
    `self._run` — can be tested without git, `gh`, or the network."""
    forge = GitHubForge()
    calls: list[list[str]] = []

    def fake_run(args, cwd):
        calls.append(args)
        return ""

    forge._run = fake_run
    return forge, calls


def test_push_branch_issues_the_expected_git_sequence():
    forge, calls = _forge_recording()
    branch = forge.push_branch(REPO, PATCH)

    assert branch == branch_name_for(PATCH, REPO)
    assert calls == [
        ["git", "checkout", "-B", branch],
        ["git", "add", "-u"],
        ["git", "commit", "-m", f"fix: {PATCH.rationale}"],
        ["git", "push", "-u", "origin", branch, "--force-with-lease"],
    ]


def test_open_pull_request_targets_the_repo_url_not_the_clones_inferred_remote():
    """A forked clone's `gh pr create` infers the base repository from the
    remote unless told otherwise, which for a fork resolves to the fork's
    parent — not the repository Sync pushed to. `--repo` must be explicit."""
    forge, calls = _forge_recording()
    forge.open_pull_request(REPO, "sync/x", EVIDENCE)

    assert len(calls) == 1
    args = calls[0]
    assert "--repo" in args
    assert args[args.index("--repo") + 1] == REPO.url
    assert "--head" in args
    assert args[args.index("--head") + 1] == "sync/x"

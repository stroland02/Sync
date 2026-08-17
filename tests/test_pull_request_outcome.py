"""Asking GitHub what became of a pull request Sync opened.

`open_pull_request` returns a number and the run ends. Until this existed nothing asked what the
number became, so `pr_merged` was null on every corpus row and merge rate -- the direct test of
the product claim -- had no numerator.

`sync merge-outcome` is the push-side answer and it stays: it verifies a signed webhook delivery
somebody collected. This is the pull-side one, for the case nobody collected anything, which has
been every case so far.

No network. `_run` is the single point where this class reaches `gh`, so a fake there exercises
the whole method against payloads shaped like `gh`'s own.
"""

from __future__ import annotations

import json

import pytest

from sync.core import RepoRef
from sync.forge.github import COMMIT_AUTHOR_EMAIL, GitHubForge, PullRequestOutcome

REPO = RepoRef(
    repo_id="acme-billing", url="https://github.com/acme/billing",
    local_path="/tmp/acme", head_sha="0" * 40,
)


def _forge(payload: dict) -> GitHubForge:
    """A forge whose one `gh` call answers `payload`."""
    forge = GitHubForge()
    forge._run = lambda args, cwd: json.dumps(payload)  # type: ignore[method-assign]
    return forge


def _sync_commit() -> dict:
    return {"authors": [{"email": COMMIT_AUTHOR_EMAIL}]}


def test_a_merged_pull_request_reports_merged_with_the_instant_github_holds():
    outcome = _forge({
        "number": 41, "state": "MERGED", "mergedAt": "2026-08-16T10:04:00Z",
        "commits": [_sync_commit()],
    }).pull_request_outcome(REPO, 41)

    assert outcome == PullRequestOutcome(
        number=41, merged=True, merged_at="2026-08-16T10:04:00Z", commits_by_others=0,
    )


def test_an_open_pull_request_is_undecided_rather_than_rejected():
    """The distinction the corpus turns on.

    `sync.benchmark.axes` excludes a null `pr_merged` from merge rate because a reviewer who has
    not decided is not a reviewer who said no. Reporting `False` here would understate the rate by
    exactly the number of pull requests still waiting -- largest at the moment the figure is first
    looked at, which is the moment it is most likely to be believed.
    """
    outcome = _forge({
        "number": 42, "state": "OPEN", "mergedAt": None, "commits": [_sync_commit()],
    }).pull_request_outcome(REPO, 42)

    assert outcome.merged is None
    assert outcome.merged_at is None


def test_a_closed_pull_request_that_never_merged_is_a_rejection():
    outcome = _forge({
        "number": 43, "state": "CLOSED", "mergedAt": None, "commits": [_sync_commit()],
    }).pull_request_outcome(REPO, 43)

    assert outcome.merged is False


def test_a_merged_pull_request_is_not_read_as_closed():
    """`gh` reports a merged pull request's state as `MERGED`, but a merge is also a close, and a
    check written against "not OPEN" records the product's best outcome as its worst. Read from
    `mergedAt`, which is present exactly when a merge happened.
    """
    outcome = _forge({
        "number": 44, "state": "MERGED", "mergedAt": "2026-08-16T11:00:00Z", "commits": [],
    }).pull_request_outcome(REPO, 44)

    assert outcome.merged is True


def test_commits_a_reviewer_authored_are_counted_and_syncs_own_are_not():
    outcome = _forge({
        "number": 45, "state": "MERGED", "mergedAt": "2026-08-16T12:00:00Z",
        "commits": [
            _sync_commit(),
            {"authors": [{"email": "reviewer@example.com"}]},
            _sync_commit(),
        ],
    }).pull_request_outcome(REPO, 45)

    assert outcome.commits_by_others == 1


def test_a_co_authored_commit_counts_as_somebody_elses():
    """A reviewer who co-authored a commit worked on it, whatever else is true of that commit.
    Counting it as Sync's would report a patch as untouched when a human had to intervene, which
    is the one direction this figure must not be wrong in -- it is the evidence for the claim that
    the patches land unedited.
    """
    outcome = _forge({
        "number": 46, "state": "MERGED", "mergedAt": "2026-08-16T12:00:00Z",
        "commits": [{"authors": [{"email": COMMIT_AUTHOR_EMAIL}, {"email": "dev@example.com"}]}],
    }).pull_request_outcome(REPO, 46)

    assert outcome.commits_by_others == 1


def test_a_commit_whose_author_github_cannot_resolve_counts_as_somebody_elses():
    """`gh` omits the address for a commit it cannot attach to an account. Treating unresolvable
    as ours would make this figure smallest exactly where the provenance is least clear.
    """
    outcome = _forge({
        "number": 47, "state": "MERGED", "mergedAt": "2026-08-16T12:00:00Z",
        "commits": [{"authors": [{"name": "someone"}]}, {"authors": []}],
    }).pull_request_outcome(REPO, 47)

    assert outcome.commits_by_others == 2


def test_a_response_with_no_state_refuses_rather_than_guessing():
    """Every branch turns on `state`. A missing one guessed as open writes a null that the next
    run reads as "still waiting" -- a row that never resolves and never complains.
    """
    with pytest.raises(RuntimeError, match="no state"):
        _forge({"number": 48, "mergedAt": None, "commits": []}).pull_request_outcome(REPO, 48)

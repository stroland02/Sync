"""Turning GitHub's pull request webhook into a recorded merge outcome.

Merge outcome is the one measurement that tests the product claim, and it cannot be
inferred from anything the run itself observes: a pull request merges days later, or never,
and only GitHub knows which. `GraphStore.set_merge_outcome` has existed as the update path
with nothing calling it, so `pr_merged` and `human_edits_before_merge` stay null and the
merge rate has no numerator. This is the caller.

There is no server here, and deliberately none. What arrives is bytes, a signature and a
store; what happens is a row update. Which HTTP framework carries those bytes is the
mounting code's business, and a framework dependency added here would be a dependency
every consumer of `sync.forge` inherits to run a function that never touches a socket.

Two gates, in one order, for the reason `sync.signals.feed.consumer` gives at greater
length: the signature proves the bytes came from GitHub, and parsing proves they say
something this receiver can act on. Neither substitutes for the other, and verification
runs first because parsing first would let unauthenticated bytes decide which corpus row
gets looked up. The corpus is the table every future routing decision is measured against;
an unverified receiver lets anyone on the internet write the number the product is judged
by.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from sync.forge.github import COMMIT_AUTHOR_EMAIL

# GitHub sends the HMAC in this header, hex-encoded and prefixed with the algorithm. The
# constant is here so mounting code does not have to spell it, and misspells it into a
# receiver that never verifies anything.
SIGNATURE_HEADER = "X-Hub-Signature-256"

# The only action that decides anything. GitHub fires `pull_request` on a dozen others --
# `opened`, `synchronize`, `labeled`, `edited` -- and a merge recorded on any of them is a
# merge that has not happened. `closed` covers both halves of the measurement: merged, and
# closed without merging, which the merge rate needs as its negative rather than as a row
# indistinguishable from one still under review.
DECIDING_ACTION = "closed"


class WebhookSignatureError(ValueError):
    """The bytes are not vouched for by the webhook secret."""


class WebhookFormatError(ValueError):
    """The bytes are vouched for and still are not a pull request event."""


def verify_signature(body: bytes, signature: str, secret: bytes) -> None:
    """Raise unless `signature` is GitHub's HMAC-SHA256 over exactly these bytes.

    Raises rather than returning a boolean, for the reason `verify_feed` does: a returned
    `False` is a value a caller can forget to check, and this one decides whether a
    stranger can write the corpus.

    Every failure is one exception. A missing header, a truncated digest and a genuine
    forgery are the same event to a caller -- these bytes are not trusted -- and an absent
    signature must never read as permission.

    `hmac.compare_digest` rather than `==`: an equality comparison on a secret-derived
    value returns as soon as two bytes differ, which leaks how much of a guess was correct
    and makes forging a digest a matter of measuring rather than of breaking SHA-256. No
    test in this repository can tell the two apart -- the difference is in timing, not in
    behaviour -- which is exactly why it is stated here rather than left to be noticed.
    """
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise WebhookSignatureError("webhook signature does not verify")


class PullRequestEvent(NamedTuple):
    action: str
    number: int
    merged: bool


def parse_pull_request_event(body: bytes) -> PullRequestEvent:
    """What the delivery says, or `WebhookFormatError`.

    Only the fields this receiver acts on are read, and each is required rather than
    defaulted. A payload missing `merged` is not a payload saying the pull request did not
    merge; defaulting it would write a false negative into the column the merge rate is
    computed from, and a false negative there is indistinguishable from a real one forever.

    A delivery of some other event type -- the `ping` GitHub sends when a hook is created,
    a `push`, an `issue_comment` -- is not a malformed pull request event. Callers route on
    the `X-GitHub-Event` header and hand only `pull_request` deliveries here; anything else
    arriving is a mounting mistake, and it raises rather than being quietly skipped.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookFormatError("webhook payload is not JSON") from exc

    if not isinstance(payload, Mapping):
        raise WebhookFormatError(f"webhook payload is a {type(payload).__name__}, not an object")

    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, Mapping):
        raise WebhookFormatError("webhook payload carries no pull_request")

    action = payload.get("action")
    number = pull_request.get("number", payload.get("number"))
    merged = pull_request.get("merged")
    if not isinstance(action, str) or not isinstance(number, int) or not isinstance(merged, bool):
        raise WebhookFormatError("pull_request carries no action, number, or merged flag")

    return PullRequestEvent(action, number, merged)


class PullRequestReviewEvent(NamedTuple):
    action: str
    pr_number: int
    state: str
    body: str
    reviewer: str


def parse_review_event(body: bytes) -> PullRequestReviewEvent:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookFormatError("webhook payload is not JSON") from exc

    if not isinstance(payload, Mapping):
        raise WebhookFormatError(f"webhook payload is a {type(payload).__name__}, not an object")

    action = payload.get("action")
    review = payload.get("review") or {}
    pr = payload.get("pull_request") or {}

    state = review.get("state", "")
    review_body = review.get("body") or ""
    reviewer = review.get("user", {}).get("login", "")
    pr_number = pr.get("number", payload.get("number", 0))

    if not isinstance(action, str) or not isinstance(pr_number, int):
        raise WebhookFormatError("review payload missing action or pull_request number")

    return PullRequestReviewEvent(
        action=action,
        pr_number=pr_number,
        state=state,
        body=review_body,
        reviewer=reviewer,
    )


class PullRequestReviewCommentEvent(NamedTuple):
    action: str
    pr_number: int
    path: str
    line: int | None
    body: str
    diff_hunk: str
    reviewer: str


def parse_review_comment_event(body: bytes) -> PullRequestReviewCommentEvent:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookFormatError("webhook payload is not JSON") from exc

    if not isinstance(payload, Mapping):
        raise WebhookFormatError(f"webhook payload is a {type(payload).__name__}, not an object")

    action = payload.get("action")
    comment = payload.get("comment") or {}
    pr = payload.get("pull_request") or {}

    path = comment.get("path", "")
    line = comment.get("line") or comment.get("original_line")
    comment_body = comment.get("body", "")
    diff_hunk = comment.get("diff_hunk", "")
    reviewer = comment.get("user", {}).get("login", "")
    pr_number = pr.get("number", payload.get("number", 0))

    if not isinstance(action, str) or not isinstance(pr_number, int):
        raise WebhookFormatError("review comment payload missing action or pull_request number")

    return PullRequestReviewCommentEvent(
        action=action,
        pr_number=pr_number,
        path=path,
        line=line,
        body=comment_body,
        diff_hunk=diff_hunk,
        reviewer=reviewer,
    )


class CheckRunEvent(NamedTuple):
    action: str
    conclusion: str
    head_sha: str
    pr_number: int | None
    output_title: str | None
    output_summary: str | None


def parse_check_run_event(body: bytes) -> CheckRunEvent:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookFormatError("webhook payload is not JSON") from exc

    if not isinstance(payload, Mapping):
        raise WebhookFormatError(f"webhook payload is a {type(payload).__name__}, not an object")

    action = payload.get("action", "")
    check_run = payload.get("check_run") or {}
    conclusion = check_run.get("conclusion") or ""
    head_sha = check_run.get("head_sha", "")

    output = check_run.get("output") or {}
    output_title = output.get("title")
    output_summary = output.get("summary")

    check_suite = payload.get("check_suite") or check_run.get("check_suite") or {}
    prs = check_suite.get("pull_requests") or check_run.get("pull_requests") or []
    pr_number = prs[0].get("number") if prs else None

    return CheckRunEvent(
        action=action,
        conclusion=conclusion,
        head_sha=head_sha,
        pr_number=pr_number,
        output_title=output_title,
        output_summary=output_summary,
    )


def format_review_feedback(
    event: PullRequestReviewEvent | PullRequestReviewCommentEvent | CheckRunEvent | Any,
) -> str:
    if isinstance(event, PullRequestReviewCommentEvent):
        location = f"{event.path}:{event.line}" if event.line else event.path
        reviewer_part = f" from {event.reviewer}" if event.reviewer else ""
        diff_part = f"\nDiff context:\n```diff\n{event.diff_hunk}\n```" if event.diff_hunk else ""
        return (
            f"Review comment{reviewer_part} on {location}:\n"
            f"{event.body}{diff_part}"
        )
    if isinstance(event, PullRequestReviewEvent):
        reviewer_part = f" ({event.reviewer})" if event.reviewer else ""
        return (
            f"Reviewer{reviewer_part} {event.state.replace('_', ' ')} on the pull request:\n"
            f"{event.body}"
        )
    if isinstance(event, CheckRunEvent):
        title = event.output_title or "CI check"
        summary = event.output_summary or f"Conclusion: {event.conclusion}"
        return f"CI check failure ({title}):\n{summary}"
    return str(event)


def dispatch_webhook_event(
    event_name: str,
    body: bytes,
    signature: str,
    secret: bytes,
    graph,
    checkpointer,
    thread_id: str | None = None,
    store=None,
) -> bool:
    """Verify and route incoming GitHub webhook to durable run resumption."""
    verify_signature(body, signature, secret)

    from sync.remediate.durable import resume_durable_run

    if event_name == "pull_request_review_comment":
        comment_event = parse_review_comment_event(body)
        target_thread = thread_id or f"thread-{comment_event.pr_number}"
        resume_durable_run(
            graph=graph,
            checkpointer=checkpointer,
            thread_id=target_thread,
            event=comment_event,
            store=store,
        )
        return True

    if event_name == "pull_request_review":
        review_event = parse_review_event(body)
        target_thread = thread_id or f"thread-{review_event.pr_number}"
        resume_durable_run(
            graph=graph,
            checkpointer=checkpointer,
            thread_id=target_thread,
            event=review_event,
            store=store,
        )
        return True

    if event_name == "check_run":
        check_event = parse_check_run_event(body)
        if check_event.conclusion in ("failure", "timed_out", "action_required"):
            target_thread = thread_id or (f"thread-{check_event.pr_number}" if check_event.pr_number else None)
            if target_thread:
                resume_durable_run(
                    graph=graph,
                    checkpointer=checkpointer,
                    thread_id=target_thread,
                    event=check_event,
                    store=store,
                )
                return True

    return False



def count_human_edits(commits: Sequence[Mapping[str, Any]]) -> int:
    """How many commits on the branch somebody other than Sync wrote.

    Sync is identified by the author address `push_branch` commits under, imported rather
    than repeated so the two cannot drift apart. The author, not the committer: GitHub
    rewrites the committer on a squash and on any edit made through the web UI, and a
    rebase rewrites it while leaving the author alone, so reading the committer would count
    Sync's own commits as human edits after any of those. This is the same decision
    `push_branch` makes when it refuses to replace a tip it did not author, and it is not a
    security control for the same reason: `git commit --author` sets the field to anything.

    A commit carrying no author address counts as somebody else's. Sync's always carry one,
    so the ambiguous case is not Sync's, and guessing the other way would hide precisely
    the edits this exists to count.

    `commits` is passed in rather than read from the payload because GitHub's pull request
    event does not contain them -- it carries a count and a link. Fetching them is a
    network call, which belongs to the caller that already holds a GitHub client, not to a
    pure function.
    """
    return sum(
        1 for entry in commits
        if entry.get("commit", {}).get("author", {}).get("email") != COMMIT_AUTHOR_EMAIL
    )


def record_merge_outcome(
    body: bytes,
    signature: str,
    secret: bytes,
    store,
    commits: Sequence[Mapping[str, Any]] | None = None,
) -> bool:
    """Record what one webhook delivery says about a pull request Sync opened.

    Returns whether a row was written. `False` covers the two ordinary cases -- an action
    that decides nothing, and a pull request Sync did not open -- and neither is an error:
    humans and other automation open pull requests in the same repository, and every one of
    them delivers here. Raising on those would turn somebody else's merge into an entry in
    an operator's log.

    `commits` left unset means the caller has not fetched them, and the column stays null
    rather than being recorded as zero. Zero is a measurement, and it reads as "no human
    touched this patch" -- the exact claim the benchmark rests on, which makes it the worst
    available default.

    The pull request is matched to its attempt by `pr_number`, which is the only durable
    link between GitHub and a corpus row: the row carries no branch and the payload carries
    no finding. That link has to be written when the pull request is opened. Nothing does
    that yet -- `sync.remediate.corpus` records every other column and leaves this one null
    -- so until it does, every delivery lands on the quiet no-match path.
    """
    verify_signature(body, signature, secret)
    event = parse_pull_request_event(body)
    if event.action != DECIDING_ACTION:
        return False

    attempt = _attempt_for(store, event.number)
    if attempt is None:
        return False

    finding_id, attempt_index = attempt
    store.set_merge_outcome(
        finding_id,
        attempt_index,
        pr_number=event.number,
        pr_merged=event.merged,
        human_edits_before_merge=None if commits is None else count_human_edits(commits),
    )
    return True


def _attempt_for(store, pr_number: int) -> tuple[str, int] | None:
    """The attempt a merge describes: the last one, when a finding took several.

    A retried finding pushes to one branch repeatedly, so several rows share a pull
    request, and the code that merged is the final attempt's. Recording against an earlier
    one would credit a merge to a patch that was superseded before a reviewer saw it, and
    the routing matrix would learn that whatever the first attempt tried works.
    """
    candidates = [row for row in store.migration_outcomes() if row.pr_number == pr_number]
    if not candidates:
        return None
    latest = max(candidates, key=lambda row: row.attempt_index)
    return latest.finding_id, latest.attempt_index

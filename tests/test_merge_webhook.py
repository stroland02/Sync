"""The receiver that gives the merge rate a numerator.

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` audits its own preconditions
and finds this one missing: `set_merge_outcome` exists and nothing calls it, so `pr_merged`
and `human_edits_before_merge` stay null and the one measurement that tests the product
claim -- that binding-driven patches land more often -- cannot be computed at all.

Merge outcome arrives days after the run, from GitHub, over a channel anyone on the
internet can post to. That is why half of these tests are about the signature: the corpus
is the table every future routing decision is measured against, and an unverified receiver
lets a stranger write the number the product is judged by.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest

from sync.core import CallSite, MigrationOutcome, Patch, VendorChange
from sync.forge.github import COMMIT_AUTHOR_EMAIL
from sync.forge.webhook import (
    WebhookFormatError,
    WebhookSignatureError,
    count_human_edits,
    record_merge_outcome,
    verify_signature,
)
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
SECRET = b"a shared secret"

SITE = CallSite(
    id="cs-1", repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount"], response_fields_read=["status"], sdk_version="18.0.0", content_hash="h",
)
CHANGE = VendorChange(
    id="vc-1", vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
    kind="request-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
    severity="breaking", source="oasdiff", raw={},
)


def _outcome(finding_id: str = "f-1", attempt_index: int = 0, pr_number: int | None = None):
    row = MigrationOutcome.from_attempt(
        finding_id=finding_id, attempt_index=attempt_index, site=SITE, change=CHANGE,
        patch=Patch(diff="d", strategy="codemod", rationale="r"),
        tier=0, routing_row="unrouted", wall_ms=12, salt="s1",
    )
    return row.model_copy(update={"pr_number": pr_number})


def _body(action: str = "closed", number: int = 42, merged: bool = True) -> bytes:
    """The subset of GitHub's `pull_request` event this receiver reads.

    Serialised here rather than templated as text because the signature is over the exact
    bytes: a test that signed one rendering and delivered another would be testing its own
    formatter.
    """
    return json.dumps({
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "merged": merged,
            "head": {"ref": "sync/api-drift-a8c8787b7ad9"},
        },
        "repository": {"full_name": "o/r"},
    }).encode("utf-8")


def _signature(body: bytes, secret: bytes = SECRET) -> str:
    """GitHub's `X-Hub-Signature-256`, computed independently of the module under test.

    Calling the receiver's own helper to build the expected value would make every
    signature test pass against any implementation that agreed with itself.
    """
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


class _RecordingStore:
    """A store that answers `migration_outcomes` and records `set_merge_outcome`.

    The rows are the corpus this receiver has to find its way around in; what reaches
    Postgres is proven once, at the bottom of this file, against the real store.
    """

    def __init__(self, *rows: MigrationOutcome) -> None:
        self.rows = list(rows)
        self.calls: list[tuple[str, int, dict]] = []

    def migration_outcomes(self) -> list[MigrationOutcome]:
        return list(self.rows)

    def set_merge_outcome(self, finding_id, attempt_index, **fields):
        self.calls.append((finding_id, attempt_index, fields))


# --- the signature, which is not optional theatre ----------------------------------


def test_a_signature_over_these_bytes_verifies():
    body = _body()

    verify_signature(body, _signature(body), SECRET)


def test_a_signature_over_different_bytes_is_refused():
    """The attack this stops is replay with substitution: a signature GitHub really did
    produce, delivered over a body someone else wrote."""
    with pytest.raises(WebhookSignatureError):
        verify_signature(_body(number=1), _signature(_body(number=2)), SECRET)


def test_a_signature_under_a_different_secret_is_refused():
    with pytest.raises(WebhookSignatureError):
        verify_signature(_body(), _signature(_body(), b"not the secret"), SECRET)


@pytest.mark.parametrize("signature", ["", "sha256=", "garbage", "sha1=abc"])
def test_a_missing_or_malformed_signature_is_refused_like_a_forged_one(signature):
    """"Verify if you can" is the same as not verifying. An absent header is the shape a
    caller mounting this behind a proxy that strips headers would produce, and it must not
    read as permission."""
    with pytest.raises(WebhookSignatureError):
        verify_signature(_body(), signature, SECRET)


def test_the_signature_is_checked_before_the_payload_is_parsed():
    """Ordering, not decoration. Parsing first would mean unauthenticated bytes decide
    which corpus row gets looked up before anything has vouched for them, and the error a
    caller sees would name the wrong problem."""
    body = b"{not json at all"

    with pytest.raises(WebhookSignatureError):
        record_merge_outcome(body, "sha256=deadbeef", SECRET, _RecordingStore())


def test_a_validly_signed_payload_that_is_malformed_is_still_refused():
    """A signature proves origin, not correctness. Whoever holds the secret can sign
    nonsense, and a buggy sender is likelier than a hostile one."""
    body = b'{"action": "closed"}'

    with pytest.raises(WebhookFormatError):
        record_merge_outcome(body, _signature(body), SECRET, _RecordingStore())


def test_a_closure_that_does_not_say_whether_it_merged_is_refused():
    """The field is required rather than defaulted, and the difference is a lie that cannot
    be undone: a missing `merged` read as `False` writes a negative into the column the
    merge rate is computed from, and afterwards nothing distinguishes it from a pull
    request that was really closed unmerged."""
    body = json.dumps({
        "action": "closed",
        "pull_request": {"number": 42, "head": {"ref": "sync/api-drift-a8c8787b7ad9"}},
    }).encode("utf-8")
    store = _RecordingStore(_outcome(pr_number=42))

    with pytest.raises(WebhookFormatError):
        record_merge_outcome(body, _signature(body), SECRET, store)
    assert store.calls == []


# --- which events count ------------------------------------------------------------


@pytest.mark.parametrize("action", ["opened", "synchronize", "labeled", "edited", "reopened"])
def test_an_action_that_is_not_a_closure_records_nothing(action):
    """A pull request event fires on a dozen actions. Recording an outcome on `opened`
    writes a merge that has not happened, and on `synchronize` overwrites one that has."""
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body(action=action)

    assert record_merge_outcome(body, _signature(body), SECRET, store) is False
    assert store.calls == []


def test_a_merged_pull_request_records_the_merge():
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body(action="closed", number=42, merged=True)

    assert record_merge_outcome(body, _signature(body), SECRET, store) is True

    finding_id, attempt_index, fields = store.calls[0]
    assert (finding_id, attempt_index) == ("f-1", 0)
    assert fields["pr_merged"] is True


def test_a_closed_pull_request_that_never_merged_records_the_negative():
    """The merge rate needs both halves. A closed-unmerged pull request that recorded
    nothing would leave the row indistinguishable from one still under review, and the rate
    would be computed over a denominator that quietly shrinks to whatever merged."""
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body(action="closed", number=42, merged=False)

    assert record_merge_outcome(body, _signature(body), SECRET, store) is True
    assert store.calls[0][2]["pr_merged"] is False


def test_a_pull_request_sync_never_opened_is_ignored_quietly():
    """Humans and other automation open pull requests in the same repository, and the
    webhook fires for all of them. An unknown number is the ordinary case, not a fault:
    raising would turn every unrelated merge into an error in somebody's log."""
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body(number=99)

    assert record_merge_outcome(body, _signature(body), SECRET, store) is False
    assert store.calls == []


def test_the_merge_lands_on_the_attempt_that_produced_the_merged_code():
    """One pull request, several attempt rows: a finding that took three tries pushed three
    times to the same branch, and the code that merged is the last one's. Recording against
    the first would attribute a merge to a patch that was superseded before anyone saw it."""
    store = _RecordingStore(
        _outcome(attempt_index=0, pr_number=42),
        _outcome(attempt_index=2, pr_number=42),
        _outcome(attempt_index=1, pr_number=42),
    )
    body = _body(number=42)

    record_merge_outcome(body, _signature(body), SECRET, store)

    assert store.calls[0][1] == 2


# --- human edits before merge ------------------------------------------------------


def _commit(email: str) -> dict:
    """One entry of `GET /repos/{owner}/{repo}/pulls/{n}/commits`."""
    return {"sha": "0" * 40, "commit": {"author": {"name": "Someone", "email": email}}}


def test_a_branch_only_sync_wrote_has_no_human_edits():
    assert count_human_edits([_commit(COMMIT_AUTHOR_EMAIL), _commit(COMMIT_AUTHOR_EMAIL)]) == 0


def test_every_commit_sync_did_not_author_is_a_human_edit():
    """The column exists to tell a patch that merged untouched from one a reviewer had to
    finish. Counting every commit would make the first look edited; counting none would
    make the second look clean, and the routing decisions read off this column would be
    measuring the wrong thing in both directions."""
    commits = [
        _commit(COMMIT_AUTHOR_EMAIL),
        _commit("reviewer@example.com"),
        _commit(COMMIT_AUTHOR_EMAIL),
        _commit("someone.else@example.com"),
    ]

    assert count_human_edits(commits) == 2


def test_a_commit_with_no_author_email_counts_as_somebody_else():
    """Sync's own commits always carry its address, because `push_branch` supplies it. A
    commit that carries none did not come from Sync, and guessing in the other direction
    would hide exactly the human edits this counts."""
    assert count_human_edits([{"sha": "0" * 40, "commit": {"author": {}}}]) == 1


def test_a_commit_github_re_committed_still_counts_as_syncs():
    """GitHub rewrites the committer on a squash and on a web-UI edit while leaving the
    author alone, which is why this reads the author -- the same decision `push_branch`
    makes when it refuses to replace somebody else's tip."""
    entry = _commit(COMMIT_AUTHOR_EMAIL)
    entry["commit"]["committer"] = {"name": "GitHub", "email": "noreply@github.com"}

    assert count_human_edits([entry]) == 0


def test_commits_that_were_not_supplied_leave_the_column_null():
    """The pull request event does not carry commits, so a caller that has not fetched them
    knows nothing about human edits. Recording zero would be a measurement nobody made, and
    it would read as "no human touched this" -- the exact claim the benchmark rests on."""
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body()

    record_merge_outcome(body, _signature(body), SECRET, store)

    assert store.calls[0][2]["human_edits_before_merge"] is None


def test_supplied_commits_are_counted_into_the_record():
    store = _RecordingStore(_outcome(pr_number=42))
    body = _body()

    record_merge_outcome(
        body, _signature(body), SECRET, store,
        commits=[_commit(COMMIT_AUTHOR_EMAIL), _commit("reviewer@example.com")],
    )

    assert store.calls[0][2]["human_edits_before_merge"] == 1


# --- against the real table --------------------------------------------------------


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_the_merge_reaches_the_row_it_describes(store: GraphStore):
    """Everything above stubs the store, so none of it proves the column moves. This one
    records an attempt, links it to a pull request the way opening one does, delivers a
    signed merge, and reads the row back."""
    store.record_migration_outcome(_outcome())
    store.set_merge_outcome("f-1", 0, pr_number=42)
    body = _body(number=42, merged=True)

    assert record_merge_outcome(
        body, _signature(body), SECRET, store,
        commits=[_commit(COMMIT_AUTHOR_EMAIL), _commit("reviewer@example.com")],
    ) is True

    row = store.migration_outcomes()[0]
    assert row.pr_merged is True
    assert row.human_edits_before_merge == 1
    assert row.pr_merged_at is not None

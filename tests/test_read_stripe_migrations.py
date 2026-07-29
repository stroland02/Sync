"""Reading a mined migration commit, and refusing to call an unreadable one a finding.

`2026-07-28-sync-ground-truth-count.md` settled sample size and left label quality open: it
inferred agent authorship from message uniformity, which is suggestive and not proof. This is
the instrument that looks for what would settle it, and
`2026-07-29-sync-ground-truth-quality.md` is what it was pointed at.

Every test drives the pure half from a committed payload. Fetching shells out to `gh`, which is
a vendor API, and no test may touch it -- the same split `mine_stripe_migrations.py` keeps, for
the same reason.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.read_stripe_migrations import (
    MEASURED,
    UNMEASURABLE,
    classify_authorship,
    classify_diff,
    read_commit_response,
)

FIXTURES = Path(__file__).parent / "fixtures" / "github_commits"


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# --- measured, or unmeasurable -----------------------------------------------------


def test_a_rate_limited_response_is_not_a_commit_that_changed_nothing():
    """The distinction the counting instrument was built around, inherited here. A reader that
    answers "no files changed" to an exhausted token has turned a measurement failure into a
    finding, and a zero that means two things is a zero nobody can act on.
    """
    reading = read_commit_response(_payload("rate_limited"), repo="acme/app", sha="deadbee")

    assert reading.outcome == UNMEASURABLE
    assert reading.authorship is None
    assert reading.diff is None
    assert "rate limit" in reading.detail.lower()


def test_a_real_commit_reads_as_measured():
    reading = read_commit_response(_payload("no_trailer_pin_only"), repo="acme/app", sha="x")

    assert reading.outcome == MEASURED
    assert reading.authorship is not None
    assert reading.diff is not None


# --- authorship --------------------------------------------------------------------


def test_a_co_author_trailer_naming_an_agent_is_recorded_as_one():
    """The count could only say the messages looked uniform. A trailer is not an inference: the
    committer wrote down who wrote the patch, and this reads what they wrote.
    """
    authorship = classify_authorship(_payload("agent_trailer_pin_only"))

    assert authorship.agent_trailer is True
    assert any("claude" in trailer.lower() for trailer in authorship.trailers)


def test_a_commit_with_no_trailer_and_no_bot_identity_carries_no_agent_signal():
    """The counterweight, and the one that keeps the signal from being decoration. A classifier
    that answered "agent" for everything would agree with the verdict and prove nothing.
    """
    authorship = classify_authorship(_payload("no_trailer_pin_only"))

    assert authorship.agent_trailer is False
    assert authorship.bot_identity is False
    assert authorship.trailers == ()


def test_a_non_ascii_commit_message_is_read_rather_than_mangled():
    """This cohort is multilingual -- the count quotes Spanish and French subjects, and this
    fixture is Slovak. A trailer search over a message that lost its bytes to a locale codec
    finds nothing and reports a human, which is the failure that flatters the answer.
    """
    payload = _payload("agent_trailer_non_ascii_message")

    authorship = classify_authorship(payload)

    assert "pripnúť" in payload["commit"]["message"]
    assert authorship.agent_trailer is True


# --- what the diff touched ----------------------------------------------------------


def test_a_commit_that_moves_only_the_pin_is_classified_as_pin_only():
    """A version bump that changes nothing else is not a migration. It either compiled by luck
    or broke silently, and as a labelled patch it says the correct answer to a breaking release
    is to touch no call site -- which is the opposite of what the benchmark needs to score.
    """
    diff = classify_diff(_payload("no_trailer_pin_only"))

    assert diff.touches_pin is True
    assert diff.pin_only is True
    assert diff.call_site_files == ()


def test_a_commit_that_moves_the_pin_and_the_call_sites_is_classified_apart_from_it():
    """The shape the benchmark actually needs: the human moved the version and then changed the
    code the move broke. Telling the two apart is the whole point of reading the diffs.
    """
    diff = classify_diff(_payload("no_trailer_pin_and_call_sites"))

    assert diff.touches_pin is True
    assert diff.pin_only is False
    assert diff.call_site_files


def test_dependency_bookkeeping_is_not_a_call_site():
    """A lockfile moving beside a pin is a dependency bump wearing a migration's shape. Counting
    `package-lock.json` as a call site would report the largest and least informative group in
    the cohort as labelled patches.
    """
    payload = _payload("no_trailer_pin_and_call_sites")
    payload["files"] = [
        {"filename": "package-lock.json", "additions": 4, "deletions": 4,
         "patch": "@@ -1 +1 @@\n-  \"version\": \"1.0.0\"\n+  \"version\": \"1.0.1\""},
        {"filename": "src/pay.ts", "additions": 1, "deletions": 1,
         "patch": "@@ -1 +1 @@\n-  apiVersion: '2026-05-27.dahlia',\n+  apiVersion: '2026-06-24.dahlia',"},
    ]

    diff = classify_diff(payload)

    assert diff.touches_pin is True
    assert "package-lock.json" not in diff.call_site_files
    # The lockfile's own changed lines are not the pin either, so a classifier counting any
    # non-pin line as a call-site edit would call this a migration.
    assert diff.pin_only is True

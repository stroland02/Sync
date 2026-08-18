"""The patch route's view model: the diff, where it went, and which kind of nothing.

A diff shown without its destination is the shape a reader mistakes for a change that has already
landed. Every assertion about absence here exists because three different runs produce no diff and
only one of them is a fault.
"""

from __future__ import annotations

from starlette.testclient import TestClient

from sync.dashboard.patch import diff_stat, patch_payload
from sync.mcp.tools import GraphSurface
from tests.test_api_routes import FETCHED, FakeGraph, _build_app

DIFF = (
    "--- a/src/billing.ts\n"
    "+++ b/src/billing.ts\n"
    "@@ -1,3 +1,3 @@\n"
    "-const charge = stripe.charges.create(amount)\n"
    "+const charge = stripe.charges.create({ amount })\n"
    " export { charge }\n"
)


def test_a_file_header_is_not_counted_as_a_changed_line():
    """`+++` and `---` are headers, and counting them tells a reader a one-line change is three."""
    assert diff_stat(DIFF) == {"files_changed": 1, "lines_added": 1, "lines_removed": 1}


def test_the_stat_follows_the_diff_rather_than_anything_stored_beside_it():
    two_files = DIFF + "--- a/src/refunds.ts\n+++ b/src/refunds.ts\n+const x = 1\n"

    assert diff_stat(two_files)["files_changed"] == 2


def test_the_diff_is_served_with_the_branch_it_was_pushed_to():
    """Owner ruling: seeing the change and seeing where it went must not come apart."""
    payload = patch_payload(
        {
            "patch": {"diff": DIFF, "strategy": "rename", "rationale": "the field moved"},
            "repo_id": "acme/app",
            "branch": "sync/fix-charges",
            "pr_url": "https://github.com/acme/app/pull/7",
            "pr_number": 7,
        }
    )

    assert payload["diff"] == DIFF
    assert payload["target"] == {
        "repo_id": "acme/app",
        "branch": "sync/fix-charges",
        "pr_url": "https://github.com/acme/app/pull/7",
        "pr_number": 7,
    }


def test_a_patch_that_was_never_pushed_says_so_rather_than_showing_a_blank_branch():
    """A patch exists and a branch does not, and both are true at once."""
    payload = patch_payload(
        {"patch": {"diff": DIFF, "strategy": "rename", "rationale": "r"}, "repo_id": "acme/app"}
    )

    assert payload["diff"] == DIFF
    assert payload["target"]["branch"] is None
    assert payload["absent_because"] is None


def test_a_run_that_decided_against_a_patch_is_not_a_run_that_gave_up():
    """The distinction this view exists to keep: a judgement is not a failure."""
    reported = patch_payload({"patch": None, "outcome": "reported", "repo_id": "r"})
    abandoned = patch_payload({"patch": None, "outcome": "abandoned", "repo_id": "r"})

    assert reported["absent_because"] != abandoned["absent_because"]
    assert "no patch was warranted" in reported["absent_because"]
    assert "abandoned" in abandoned["absent_because"]


def test_a_run_still_working_is_not_a_run_with_no_patch():
    """Not-yet is its own state, and it must not read as a decision already taken."""
    payload = patch_payload({"patch": None, "outcome": None, "repo_id": "r"})

    assert "has not produced a patch yet" in payload["absent_because"]
    assert payload["stat"] is None


def _client(patch_reader):
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    return TestClient(_build_app(surface=surface, patch_reader=patch_reader))


def test_a_finding_with_no_run_at_all_is_a_404():
    """No run is a missing page. A run that chose not to patch is not, and that is the next test."""
    response = _client(lambda finding_id: None).get("/api/findings/f1/patch")

    assert response.status_code == 404


def test_a_run_that_produced_no_patch_answers_200_with_the_reason():
    """The reason is what a reviewer opened this to read, so it is an answer rather than an absence.

    Returning 404 here would collapse *we decided against a patch* onto *there is no such
    finding*, which is the same defect as letting absence look like zero.
    """
    payload = patch_payload({"patch": None, "outcome": "reported", "repo_id": "r"})

    response = _client(lambda finding_id: payload).get("/api/findings/f1/patch")

    assert response.status_code == 200
    assert "no patch was warranted" in response.json()["absent_because"]
    assert response.json()["diff"] is None

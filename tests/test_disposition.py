"""What Sync will do about a finding, decided before anything runs.

`sync.route.disposition` is the one derivation three callers share: the run decides a tier at
`locate` with a clone in hand, the watch tick decides one with no clone, and the console
previews one for a reader. The value of the decision table is that the row which decided is
recorded, so the property that matters most here is not any single verdict -- it is that a
caller without a clone can never be told something a caller with one would contradict.

The three nothings are the other half. `no_catalogue`, `no_jurisdiction` and `no_vendor_change`
are three different facts and none of them is tier -1; folding any pair together would put a
sentence on screen claiming Sync had ruled on a finding it never routed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef, VendorChange
from sync.route.disposition import (
    AUTOMATIC_CODES,
    Disposition,
    decide_tier,
    disposition,
)
from sync.route.matrix import AGENT, CODEMOD, NO_PATCH, TEMPLATED

FIXTURE = Path(__file__).parent / "fixtures" / "ts" / "two_payment_intents"
TARGET = "app/api/setup_accounts/route.ts"

# The same call the tier-0 tests pin: 1-based line, 0-based column, `receipt_email` passed as a
# string literal and `customer` as an identifier. Row 4 turns on exactly that difference, and it
# is the only row that reads the clone -- which makes this fixture the one place the "a preview
# is a bound" property can actually be measured rather than asserted.
FIRST_CALL = (11, 23)

REQUEST_REMOVED_RULE = {
    "id": "request-property-removed", "level": "warning",
    "kind": "existence", "action": "remove", "direction": "request",
}
RESPONSE_REMOVED_RULE = {
    "id": "response-optional-property-removed", "level": "warning",
    "kind": "existence", "action": "remove", "direction": "response",
}
REQUIRED_ADDED_RULE = {
    "id": "new-required-request-property", "level": "error",
    "kind": "existence", "action": "add", "direction": "request",
}
LIFECYCLE_RULE = {
    "id": "sunset-deleted", "level": "error",
    "kind": "lifecycle", "action": "remove", "direction": "none",
}
TYPE_RULE = {
    "id": "request-property-type-changed", "level": "error",
    "kind": "type", "action": "change", "direction": "request",
}
CATALOGUE = {
    rule["id"]: rule
    for rule in (
        REQUEST_REMOVED_RULE, RESPONSE_REMOVED_RULE,
        REQUIRED_ADDED_RULE, LIFECYCLE_RULE, TYPE_RULE,
    )
}


def _change(field: str, kind: str = "request-property-removed") -> VendorChange:
    return VendorChange(
        vendor_id="stripe", from_version="v2300", to_version="v2345", kind=kind,
        operation_id="PostPaymentIntents", path_ptr="/v1/payment_intents",
        severity="breaking", source="oasdiff",
        raw={"id": kind, "text": f"removed the request property `{field}`"},
    )


def _site(path: str = TARGET, position: tuple[int, int] = FIRST_CALL) -> CallSite:
    line, col = position
    return CallSite(
        repo_id="repo-1", path=path, line=line, col=col, vendor_id="stripe",
        operation_id="PostPaymentIntents", symbol="stripe.paymentIntents.create",
        args_keys=["amount", "currency", "customer", "receipt_email"],
        response_fields_read=["id"], sdk_version="22.4.0", content_hash="h",
    )


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    return RepoRef(
        repo_id="repo-1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="abc123",
    )


# --- the bound ----------------------------------------------------------------------


def test_a_preview_without_a_clone_is_never_cheaper_than_the_decision_with_one(
    repo: RepoRef,
) -> None:
    """The property every clone-less caller rests on, measured on the one row that can move.

    Row 4 (`request-field-removed-literal`) is the only row that reads the checkout, and
    `receipt_email` is written as a string literal in the fixture -- so with the clone the
    table routes it to CODEMOD, and without one the literal fact is unknown and it must fall
    to the agent tier. Cheaper-without-a-clone is the direction that would be a lie: it would
    let the tick mark a finding mechanically safe and the run then discover it is not.
    """
    change, site = _change("receipt_email"), _site()

    with_clone, _ = decide_tier(change, site, CATALOGUE, repo)
    without_clone, _ = decide_tier(change, site, CATALOGUE, None)

    assert with_clone == CODEMOD
    assert without_clone == AGENT
    assert without_clone >= with_clone, (
        "a preview taken without the clone must name a tier at least as expensive as the "
        "decision taken with one -- never a cheaper one"
    )


def test_the_clone_only_refines_the_row_it_can_establish(repo: RepoRef) -> None:
    """A row that does not read the checkout decides identically either way.

    Without this, the test above is equally satisfied by a preview that simply routes
    everything to the agent tier, which would be useless rather than merely conservative.
    """
    change, site = _change("receipt_email", kind="sunset-deleted"), _site()

    assert decide_tier(change, site, CATALOGUE, repo) == decide_tier(
        change, site, CATALOGUE, None
    )


# --- the three nothings, which are three different facts -----------------------------


def test_no_catalogue_and_no_jurisdiction_are_not_the_same_answer() -> None:
    """One says the table was never loaded, the other that it does not cover this change.

    A reader deciding whether Sync has ruled on a finding needs them apart: the first is a
    deployment that has not staged the routing table, the second is a deprecation signal
    working exactly as designed.
    """
    site = _site()

    unloaded = disposition(_change("receipt_email"), site, catalogue=None)
    uncovered = disposition(
        _change("gpt-4", kind="deprecation/model-retired"), site, CATALOGUE
    )

    assert unloaded.code == "no_catalogue"
    assert uncovered.code == "no_jurisdiction"
    assert unloaded.code != uncovered.code


def test_a_change_outside_the_table_is_not_reported_as_no_patch() -> None:
    """`(None, None)` is not tier -1, and this is the collapse that would hurt most.

    `no_patch` says Sync ruled that nothing in this repository needs editing. A deprecation
    the catalogue does not carry has had no ruling at all, and rendering it as one would
    switch off the one signal that costs no tokens.
    """
    outside = disposition(
        _change("gpt-4", kind="deprecation/model-retired"), _site(), CATALOGUE
    )

    assert outside.code == "no_jurisdiction"
    assert outside.tier is None
    assert outside.tier != NO_PATCH


def test_a_finding_naming_no_vendor_change_says_so() -> None:
    """The observed-drift and status-rate detectors raise findings with no change to route."""
    verdict = disposition(None, None, CATALOGUE)

    assert verdict.code == "no_vendor_change"
    assert verdict.tier is None
    assert not verdict.automatic


# --- what is automatic, and what waits for a person ----------------------------------


def test_a_mechanical_tier_is_automatic_and_carries_the_row_that_said_so(
    repo: RepoRef,
) -> None:
    """Automatic work records which row made it automatic, so a wrong policy is a query."""
    verdict = disposition(_change("receipt_email"), _site(), CATALOGUE, repo)

    assert verdict.code == "mechanical"
    assert verdict.tier == CODEMOD
    assert verdict.routing_row == "request-field-removed-literal"
    assert verdict.automatic


def test_a_templated_tier_is_automatic_too() -> None:
    """Both tiers below the agent are mechanical: the shape is known, only the value is not."""
    verdict = disposition(
        _change("statement_descriptor", kind="new-required-request-property"),
        _site(),
        CATALOGUE,
    )

    assert verdict.tier == TEMPLATED
    assert verdict.automatic


@pytest.mark.parametrize(
    "verdict_of",
    [
        pytest.param(
            lambda: disposition(_change("x", kind="sunset-deleted"), _site(), CATALOGUE),
            id="no_patch",
        ),
        pytest.param(
            lambda: disposition(
                _change("x", kind="request-property-type-changed"), _site(), CATALOGUE
            ),
            id="needs_agent",
        ),
        pytest.param(
            lambda: disposition(_change("x"), _site(), catalogue=None), id="no_catalogue"
        ),
        pytest.param(
            lambda: disposition(
                _change("x", kind="deprecation/model-retired"), _site(), CATALOGUE
            ),
            id="no_jurisdiction",
        ),
        pytest.param(lambda: disposition(None, None, CATALOGUE), id="no_vendor_change"),
    ],
)
def test_everything_that_is_not_mechanical_waits_for_a_person(verdict_of) -> None:
    """The fall-through direction of the table is preserved one level up.

    An unrecognised change costs a person's attention rather than a model run nobody asked
    for -- the same safety property `matrix.route` states for its own fall-through.
    """
    verdict: Disposition = verdict_of()

    assert not verdict.automatic, f"{verdict.code} must not open work by itself"


def test_every_disposition_carries_a_reason_a_screen_can_render() -> None:
    """A code with no sentence beside it puts a reader back where they started."""
    verdicts = [
        disposition(_change("receipt_email"), _site(), CATALOGUE),
        disposition(_change("x", kind="sunset-deleted"), _site(), CATALOGUE),
        disposition(_change("x"), _site(), catalogue=None),
        disposition(None, None, CATALOGUE),
    ]

    for verdict in verdicts:
        assert verdict.reason.strip(), f"{verdict.code} carries no reason"


def test_the_automatic_set_is_a_subset_of_the_codes_that_exist() -> None:
    """`AUTOMATIC_CODES` is what the tick and the ticket writer both branch on.

    A typo in it would not raise -- it would silently stop every finding being automatic, and
    the tick would keep printing that it notified everything.
    """
    assert AUTOMATIC_CODES == {"mechanical"}
    # The membership test both callers make, exercised in both directions against verdicts
    # this module actually produced -- an `automatic` property that agreed with the set only
    # for the true case would let every declined finding through.
    mechanical = disposition(
        _change("statement_descriptor", kind="new-required-request-property"), _site(), CATALOGUE
    )
    declined = disposition(_change("x", kind="sunset-deleted"), _site(), CATALOGUE)

    assert mechanical.code in AUTOMATIC_CODES and mechanical.automatic
    assert declined.code not in AUTOMATIC_CODES and not declined.automatic

"""Whether a finding that ought to cost nothing actually reaches the tier that costs nothing.

Tier 0 is the whole economic claim -- `CLAUDE.md`: "knowing which change kinds are safely
mechanical is what lets Sync skip a model call and beat competitors on both cost and merge
rate." Rows 3 and 4 of the decision table are the entire tier-0 surface, and both were
declining, so every finding that a codemod could have repaired bought an agent run instead.

Worse than declining: a route to the agent tier *excludes* the deterministic remediators from
the cascade, because `_serves` narrows the candidate list by strategy. So wiring the table made
tier 0 less reachable than it had been before the table existed, on exactly the change class
`property_omit` was written for.

These tests fix the reachable half and pin the unreachable half open. Row 4 needs to know
whether the argument is a literal, and the answer is in the clone the cascade is already
holding. Row 3 needs a count across the whole graph, which is not, and it must keep declining
rather than being satisfied by a loosened predicate -- which is what the second half of this
file exists to prevent.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import (
    RoutingDecision,
    TerminalTier,
    TieredRemediator,
    routing_facts,
)
from sync.route.matrix import CODEMOD

FIXTURE = Path(__file__).parent / "fixtures" / "ts" / "two_payment_intents"
TARGET = "app/api/setup_accounts/route.ts"

# The first `stripe.paymentIntents.create` call, as the indexer reports it: 1-based line,
# 0-based column, on the call_expression node. It passes `receipt_email` as a string literal
# and `customer` as an identifier, which is the whole of what row 4 turns on.
FIRST_CALL = (11, 23)

REQUEST_REMOVED_RULE = {
    "id": "request-property-removed", "level": "warning",
    "kind": "existence", "action": "remove", "direction": "request",
}
RESPONSE_REMOVED_RULE = {
    "id": "response-optional-property-removed", "level": "warning",
    "kind": "existence", "action": "remove", "direction": "response",
}
CATALOGUE = {rule["id"]: rule for rule in (REQUEST_REMOVED_RULE, RESPONSE_REMOVED_RULE)}


class SpyAgent:
    """Records whether the expensive tier was reached at all."""

    strategy = "agent"

    def __init__(self) -> None:
        self.proposed = 0

    def can_handle(self, finding, change) -> bool:
        return True

    def propose(self, finding, change, site, repo, diagnostics: str = "") -> Patch:
        self.proposed += 1
        return Patch(diff="agent diff", strategy="agent", rationale="the agent ran")


def _finding() -> Finding:
    return Finding(
        detector="vendor_change", call_site_id="cs-1", vendor_change_id="vc-1",
        severity="breaking", rationale="PostPaymentIntents changed",
    )


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


def _write(repo: RepoRef, body: str, name: str = "src/inline.ts") -> str:
    target = Path(repo.local_path) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return name


def _cascade(agent: SpyAgent, *, catalogue=CATALOGUE) -> TieredRemediator:
    return TieredRemediator(
        [PropertyOmitRemediator(), TerminalTier(agent)], catalogue=catalogue,
    )


# --- the reachable half -----------------------------------------------------------


def test_a_literal_argument_reaches_the_codemod_and_never_the_agent(repo: RepoRef) -> None:
    """The M0 acceptance-run shape, routed by the table rather than by list order.

    `receipt_email: 'onboarding@example.com'` is a string literal at the named call site, so
    row 4's condition is established from the clone the cascade already holds.
    """
    agent = SpyAgent()
    patch = _cascade(agent).propose(_finding(), _change("receipt_email"), _site(), repo)

    assert patch.strategy == "codemod"
    assert agent.proposed == 0, "the agent ran on a change a codemod repaired"
    assert "receipt_email" in patch.diff


def test_the_established_fact_is_read_off_the_source_not_the_index(repo: RepoRef) -> None:
    """`args_keys` names `customer` too, and the two differ only in the source.

    If the fact came from the index both would look alike, so this is the assertion that the
    literal test is a real one rather than a restatement of what the indexer already said.
    """
    site = _site()
    assert "customer" in site.args_keys and "receipt_email" in site.args_keys

    literal = routing_facts(_change("receipt_email"), site, repo)
    variable = routing_facts(_change("customer"), site, repo)

    assert literal.field_passed_as_literal is True
    assert variable.field_passed_as_literal is False


# --- the half that must keep declining --------------------------------------------


def test_a_variable_argument_still_declines_to_the_agent(repo: RepoRef) -> None:
    """`customer: customerId` is an identifier. Deleting the pair drops the only use of a
    variable, which is reasoning about the surrounding code rather than an edit, so the row
    declines and the agent gets it. This is the test that stops the one above from being
    satisfied by a loosened predicate."""
    agent = SpyAgent()
    patch = _cascade(agent).propose(_finding(), _change("customer"), _site(), repo)

    assert patch.strategy == "agent"
    assert agent.proposed == 1


def test_a_spread_cannot_establish_the_fact_and_declines(repo: RepoRef) -> None:
    """`...defaults` may itself supply the property, so nothing about the explicit pair
    settles what the request sends. Not established is not permission."""
    path = _write(repo, (
        "import Stripe from 'stripe';\n"
        "const stripe = new Stripe('k');\n"
        "export async function pay(defaults: object) {\n"
        "  return await stripe.paymentIntents.create({\n"
        "    ...defaults,\n"
        "    receipt_email: 'a@example.com',\n"
        "  });\n"
        "}\n"
    ))
    site = _site(path=path, position=(4, 15))
    assert routing_facts(_change("receipt_email"), site, repo).field_passed_as_literal is None

    agent = SpyAgent()
    patch = _cascade(agent).propose(_finding(), _change("receipt_email"), site, repo)

    assert patch.strategy == "agent"


def test_the_response_side_row_still_declines(repo: RepoRef) -> None:
    """Row 3 needs `call_sites_reading_field`, a count across the whole graph that `propose`
    is not handed and cannot derive from one call site. It stays unestablished, the row
    declines, and the response-side removal costs an agent run until a caller holding the
    graph supplies the count."""
    change = _change("status", kind="response-optional-property-removed")
    facts = routing_facts(change, _site(), repo)
    assert facts.call_sites_reading_field is None

    agent = SpyAgent()
    patch = _cascade(agent).propose(_finding(), change, _site(), repo)

    assert patch.strategy == "agent"
    assert agent.proposed == 1


def test_a_missing_repo_leaves_the_fact_unestablished() -> None:
    """`nodes.py` previews the route at `locate` without a clone in hand. Absent the source
    the fact is unknown rather than false, so that preview is an upper bound on the tier and
    never a contradiction of what `propose` decides."""
    facts = routing_facts(_change("receipt_email"), _site())
    assert facts.field_passed_as_literal is None
    assert facts.field_resolved is True


def test_an_unreadable_file_leaves_the_fact_unestablished(repo: RepoRef) -> None:
    """A stale binding -- the index outliving the file -- must not read as permission."""
    facts = routing_facts(_change("receipt_email"), _site(path="src/gone.ts"), repo)
    assert facts.field_passed_as_literal is None


# --- a routed tier must not abandon work the cascade could still do ----------------


def test_a_codemod_route_with_no_willing_codemod_reaches_the_agent(repo: RepoRef) -> None:
    """Routing narrows the cascade by strategy, so a tier-0 route offers only the codemods.

    When none of them can take the change, the old narrowing left an empty field and the
    finding was abandoned without the agent ever being asked -- a routing decision turning
    into a lost repair. `LiteralSwapRemediator` handles deprecations only, so it declines a
    `request-property-removed` that the table nonetheless routes to tier 0.
    """
    decisions: list[RoutingDecision] = []
    agent = SpyAgent()
    remediator = TieredRemediator(
        [LiteralSwapRemediator(), TerminalTier(agent)],
        catalogue=CATALOGUE,
        on_route=decisions.append,
    )

    patch = remediator.propose(_finding(), _change("receipt_email"), _site(), repo)

    # Asserted rather than assumed: without it this test passes for the wrong reason,
    # because a route to the agent tier reaches the agent by the ordinary path.
    assert [d.tier for d in decisions] == [CODEMOD]
    assert patch.strategy == "agent"
    assert agent.proposed == 1

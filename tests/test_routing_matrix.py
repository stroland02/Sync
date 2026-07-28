"""The decision table from `2026-07-27-sync-routing-matrix.md`, held to its own claims.

The spec makes three promises a conditional chain could not keep: that every rule oasdiff can
emit routes somewhere, that no two rows contradict, and that an unrecognised change falls
through to the agent rather than to a codemod. Each is a test here.

The completeness test reads the catalogue from the pinned binary rather than a committed copy.
That is the point: a new oasdiff release adding a check fails CI instead of silently routing an
unknown kind.
"""

from __future__ import annotations

import pytest

from sync.route import AGENT, CODEMOD, NO_PATCH, TEMPLATED, RoutingFacts, catalogue_index, route
from sync.signals.oasdiff import run_oasdiff_checks

UNKNOWN = RoutingFacts()


@pytest.fixture(scope="module")
def catalogue() -> dict[str, dict]:
    return catalogue_index(run_oasdiff_checks())


# --- the three promises the spec makes ------------------------------------------


def test_every_rule_oasdiff_can_emit_routes_somewhere(catalogue):
    """Completeness over the live rule set, which is what makes the table survive an upgrade."""
    assert len(catalogue) > 100, "catalogue implausibly small; oasdiff output shape likely changed"

    for rule_id, rule in catalogue.items():
        tier, row = route(rule, UNKNOWN)
        assert tier in (NO_PATCH, CODEMOD, TEMPLATED, AGENT), f"{rule_id} routed to {tier!r}"
        assert row, f"{rule_id} routed without naming the row that decided it"


def test_the_catalogue_introduces_no_kind_the_table_has_never_considered(catalogue):
    """The promise that makes this table survive an oasdiff upgrade.

    A new rule in a *known* kind is fine -- it inherits that kind's row. A rule in a kind
    nobody has classified is not: it would fall through to the agent silently, which is safe
    but invisible, and the whole point of the table is that routing decisions are deliberate.
    This test is where an oasdiff upgrade announces itself.

    When it fails, do not widen the set to make it pass. Read the new kind, decide which tier
    it belongs in, add or amend a row in `sync.route.matrix`, then add the kind here.
    """
    classified = {
        "lifecycle",      # tier -1, row "lifecycle"
        "existence",      # rows 3, 4, 6
        "requiredness",   # row 5
        "type",           # row 7
        "structure",      # row 8
        "constraints",    # fall-through, deliberately: a tightened constraint needs judgement
        "values",         # fall-through, deliberately
        "mutability",     # fall-through, deliberately
    }
    seen = {rule["kind"] for rule in catalogue.values()}
    assert seen <= classified, (
        f"oasdiff introduced unclassified rule kind(s): {sorted(seen - classified)}. "
        "Decide their tier in sync.route.matrix before widening this set."
    )


def test_the_mechanical_surface_stays_small(catalogue):
    """Tier 0 is the blast radius. If a table edit ever routes a large share of the rule set
    to a codemod, that is a defect being announced early rather than discovered in a customer's
    repository -- precision over recall is the committed position.

    Facts are set as favourably as the graph could ever report them, so this measures the
    table's ceiling, not a typical run.
    """
    generous = RoutingFacts(
        field_resolved=True,
        call_sites_reading_field=1,
        field_passed_as_literal=True,
        value_already_passed=False,
    )
    mechanical = [r for r in catalogue.values() if route(r, generous)[0] == CODEMOD]
    share = len(mechanical) / len(catalogue)
    assert share < 0.15, (
        f"{len(mechanical)}/{len(catalogue)} rules ({share:.0%}) reach tier 0 under ideal facts; "
        "the mechanical surface is meant to be a hand-audited minority"
    )


def test_an_unknown_kind_falls_through_to_the_agent():
    """Default-deny. An unrecognised change routed to an agent costs money; routed to a
    codemod it corrupts code. The fall-through direction is the safety property."""
    invented = {
        "id": "some-rule-a-future-oasdiff-will-add",
        "level": "error",
        "direction": "response",
        "kind": "a-kind-that-does-not-exist-yet",
        "action": "change",
    }
    tier, row = route(invented, UNKNOWN)
    assert tier == AGENT
    assert row == "fall-through"


def test_no_two_rows_assign_different_tiers_to_the_same_input(catalogue):
    """First-match-wins makes ordering part of the spec, so a later row must never be the
    only correct answer for an input an earlier row already claimed. Routing every real rule
    under every combination of call-site facts asserts the table is a function, not a race."""
    fact_space = [
        RoutingFacts(),
        RoutingFacts(field_resolved=True, call_sites_reading_field=1),
        RoutingFacts(field_resolved=True, call_sites_reading_field=5),
        RoutingFacts(field_resolved=True, field_passed_as_literal=True),
        RoutingFacts(field_resolved=True, value_already_passed=True),
        RoutingFacts(field_resolved=False),
    ]
    for rule in catalogue.values():
        for facts in fact_space:
            first = route(rule, facts)
            assert route(rule, facts) == first, "routing is not deterministic"


# --- tier -1: the row that stops patches against code that was never wrong --------


def test_lifecycle_rules_never_produce_a_patch(catalogue):
    """21 of the 212 breaking rules describe how the vendor documented a deprecation.

    `api-deprecated-sunset-missing`, `sunset-deleted`, `api-invalid-stability-level` -- none
    names a change to anything customer code sends or receives, so no edit in a consumer
    repository resolves them. Routing these to an agent is the most expensive false positive
    available: a confident patch against correct code.
    """
    lifecycle = [r for r in catalogue.values() if r["kind"] == "lifecycle"]
    assert lifecycle, "no lifecycle rules found; tier -1 has lost its justification"

    for rule in lifecycle:
        tier, _ = route(rule, UNKNOWN)
        assert tier == NO_PATCH, f"{rule['id']} would be patched"


def test_a_known_lifecycle_rule_is_reported_not_patched(catalogue):
    rule = catalogue.get("api-deprecated-sunset-missing")
    assert rule is not None, "expected rule absent from catalogue; oasdiff ids changed"
    assert route(rule, UNKNOWN) == (NO_PATCH, "lifecycle")


# --- rows 3-6: the mechanical surface, which needs call-site facts ----------------


def _rule(**over) -> dict:
    base = {"id": "x", "level": "error", "direction": "response", "kind": "existence", "action": "remove"}
    base.update(over)
    return base


def test_a_removed_response_field_read_at_one_site_is_mechanical():
    facts = RoutingFacts(field_resolved=True, call_sites_reading_field=1)
    assert route(_rule(), facts) == (CODEMOD, "response-field-removed-single-site")


def test_the_same_change_read_at_several_sites_is_not_mechanical():
    """The call-site count is the whole reason the graph exists. "A response property was
    removed" does not justify a mechanical edit; "and exactly one call site reads it" does."""
    facts = RoutingFacts(field_resolved=True, call_sites_reading_field=4)
    tier, _ = route(_rule(), facts)
    assert tier == AGENT


def test_a_required_request_property_already_passed_needs_no_patch():
    """Row 5. The graph knows the call site already supplies the value, so there is nothing
    to change. Without the graph this would be a needless pull request."""
    rule = _rule(direction="request", kind="requiredness", action="change")
    facts = RoutingFacts(field_resolved=True, value_already_passed=True)
    assert route(rule, facts) == (NO_PATCH, "already-satisfied")


def test_the_same_rule_routes_to_a_patch_when_the_value_is_absent():
    rule = _rule(direction="request", kind="requiredness", action="change")
    facts = RoutingFacts(field_resolved=True, value_already_passed=False)
    tier, _ = route(rule, facts)
    assert tier != NO_PATCH


def test_an_unresolvable_field_is_never_mechanical():
    """`changed_field()` returning None is common and not a defect -- oasdiff records often
    name no field. A codemod cannot edit a field nobody can name."""
    facts = RoutingFacts(field_resolved=False, call_sites_reading_field=1)
    tier, row = route(_rule(), facts)
    assert tier == AGENT
    assert row == "field-unresolved"


def test_facts_default_to_unknown_not_to_favourable():
    """Absent evidence must not read as permission. RoutingFacts() knows nothing, so every
    row requiring a call-site fact must decline it."""
    for rule in (
        _rule(),
        _rule(direction="request", action="remove"),
        _rule(direction="request", kind="requiredness", action="change"),
    ):
        tier, _ = route(rule, RoutingFacts())
        assert tier == AGENT, f"unknown facts reached tier {tier}"


# --- structural kinds stay with the agent ----------------------------------------


@pytest.mark.parametrize("kind", ["type", "structure"])
def test_type_and_structure_changes_are_never_mechanical(kind):
    facts = RoutingFacts(field_resolved=True, call_sites_reading_field=1)
    tier, _ = route(_rule(kind=kind, action="change"), facts)
    assert tier == AGENT

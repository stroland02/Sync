"""The tier decision table, as data.

`docs/superpowers/specs/2026-07-27-sync-routing-matrix.md` is the argument. The short version:
oasdiff publishes 506 checker rules and `VendorChange.kind` is one of those identifiers, so a
table with a row per identifier would rot on every oasdiff release. Each rule carries
`level`, `direction`, `kind`, and `action`, and seven kinds by eight actions is a grid a person
can hold in their head. The table keys on the metadata.

Two properties are worth more than the routing itself, and both come from the table being data
rather than a conditional chain. Completeness is checkable -- every rule the pinned binary can
emit either matches a row or provably reaches the fall-through. And the row that decided is
returned alongside the tier, so `migration_outcome` can record *why* a finding was routed the
way it was. "Tier 0 was wrong for this change kind" is then a query rather than an excavation.

This module deliberately does not import from `sync.core` or touch the remediation graph. It is
a pure function over metadata and call-site facts; wiring it into `prepare` is a separate
change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

# Tiers. The zeroth is not the cheapest -- NO_PATCH is, because the cheapest patch is the one
# that was never justified.
NO_PATCH: Literal[-1] = -1
CODEMOD: Literal[0] = 0
TEMPLATED: Literal[1] = 1
AGENT: Literal[2] = 2

Tier = Literal[-1, 0, 1, 2]


@dataclass(frozen=True)
class RoutingFacts:
    """What the API Dependency Graph knows about the call sites a change touches.

    Every field defaults to `None`, meaning *not established*. Absent evidence must never read
    as permission: a row that needs a fact declines when the fact is unknown, which is what
    keeps an unpopulated graph from routing work to a codemod.
    """

    field_resolved: bool | None = None
    """Whether `changed_field()` could name the field. Often it cannot, and that is not a
    defect -- oasdiff records frequently name no field at all."""

    call_sites_reading_field: int | None = None
    """How many indexed call sites read the changed field."""

    field_passed_as_literal: bool | None = None
    """Whether the request field is supplied as a literal rather than a variable. A codemod can
    remove a literal; it cannot reason about where a variable came from."""

    value_already_passed: bool | None = None
    """Whether the call site already supplies a property that became required."""


@dataclass(frozen=True)
class _Row:
    name: str
    tier: Tier
    matches: Callable[[dict[str, Any], RoutingFacts], bool]


def _is(rule: dict[str, Any], **axes: str) -> bool:
    return all(rule.get(axis) == value for axis, value in axes.items())


# Evaluated top to bottom, first match wins -- DMN's FIRST hit policy, which makes the ordering
# part of the specification rather than an accident of how the code was written.
_ROWS: tuple[_Row, ...] = (
    # 1. Vendor documentation hygiene, not a change to the consumer's contract. 21 of the 212
    #    breaking rules. No edit in a consumer repository resolves `sunset-deleted`.
    _Row("lifecycle", NO_PATCH, lambda r, f: r.get("kind") == "lifecycle"),

    # 2. A codemod cannot edit a field nobody can name. Placed above the mechanical rows so
    #    they never have to restate it.
    _Row("field-unresolved", AGENT, lambda r, f: f.field_resolved is False),

    # 3. The call-site count is the entire reason the graph exists: "a response property was
    #    removed" does not justify a mechanical edit, "and exactly one site reads it" does.
    _Row(
        "response-field-removed-single-site",
        CODEMOD,
        lambda r, f: (
            _is(r, kind="existence", action="remove", direction="response")
            and f.field_resolved is True
            and f.call_sites_reading_field == 1
        ),
    ),

    # 4. Same shape on the request side, gated on the argument being a literal.
    _Row(
        "request-field-removed-literal",
        CODEMOD,
        lambda r, f: (
            _is(r, kind="existence", action="remove", direction="request")
            and f.field_resolved is True
            and f.field_passed_as_literal is True
        ),
    ),

    # 5. Nothing to change: the call site already supplies the value. Without the graph this
    #    would be a needless pull request against correct code.
    _Row(
        "already-satisfied",
        NO_PATCH,
        lambda r, f: (
            _is(r, kind="requiredness", action="change", direction="request")
            and f.value_already_passed is True
        ),
    ),

    # 6. A required request property was added. One constrained edit against a template, not a
    #    full agent loop -- the shape of the change is known, only the value is not.
    _Row(
        "required-request-property-added",
        TEMPLATED,
        lambda r, f: (
            _is(r, kind="existence", action="add", direction="request")
            and f.field_resolved is True
        ),
    ),

    # 7-8. Type and structure changes are never mechanical. Stated as rows rather than left to
    #      the fall-through so the intent is legible and testable.
    _Row("type-change", AGENT, lambda r, f: r.get("kind") == "type"),
    _Row("structure-change", AGENT, lambda r, f: r.get("kind") == "structure"),
)

_FALL_THROUGH = "fall-through"


def route(rule: dict[str, Any], facts: RoutingFacts) -> tuple[Tier, str]:
    """The tier for one change, and the name of the row that decided it.

    `rule` is a catalogue record from `run_oasdiff_checks()`, carrying at least `kind`,
    `action`, and `direction`. Unmatched input falls through to `AGENT`: an unrecognised change
    routed to an agent costs money, while one routed to a codemod corrupts code. The
    fall-through direction is the safety property, not an oversight.
    """
    for row in _ROWS:
        if row.matches(rule, facts):
            return row.tier, row.name
    return AGENT, _FALL_THROUGH


def catalogue_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """`run_oasdiff_checks()` output keyed by rule id, which is what `VendorChange.kind` holds."""
    return {record["id"]: record for record in records if "id" in record}

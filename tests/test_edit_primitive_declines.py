"""The edit primitives' unexecuted statements, and what each decline costs a caller.

M3-W110. `sync.route.templates` is the module where a wrong answer cannot be caught by
re-parsing: tree-sitter reports `{ model: "x", , max_tokens: 16 }` with zero ERROR nodes and
`has_error` false, the same verdict it gives correct source. So every assertion below is on the
emitted source, byte for byte, and every decline is pinned against a spelled-out literal rather
than against `== source` -- the function returns the input object on a decline, which makes
`== source` true whatever the code did.

Three of these paths reach a caller that cannot tell "I declined" from "there was nothing to
change", and the tests say which: `omit_property_at` answers two ways where three are needed,
`argument_is_literal_at` answers `None` where nothing was established, and `apply_rules` with no
rules is indistinguishable from a file the rules did not match.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.core.conformance import ConformanceFailure, check_remediator
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.route.matrix import AGENT, CODEMOD, RoutingFacts, route
from sync.route.templates import apply_rules, argument_is_literal_at, omit_property_at

# --- the byte-column clamp, and the two ways a position falls outside a call ----------
#
# `_to_character_column`, `_contains` and `_call_at` are reached from `omit_property_at` and
# from nowhere else in the module, and `scripts/dead_links_baseline.txt` records that nothing
# in `src/` calls `omit_property_at`. So these three paths are exercised here and by no
# production caller; the primitive is held to its documented answer anyway, because the
# baseline entry is a statement about wiring rather than about correctness.

MULTILINE_CALL = (
    "const a = stripe.paymentIntents.create({ amount: 1,\n"
    "  receipt_email: 'x@example.com',\n"
    "});\n"
)


def test_a_byte_column_past_the_end_of_its_line_still_resolves_the_call():
    """The column arrives from `CallSite`, which tree-sitter measured in bytes against whatever
    the file said then. A file that has since lost characters from that line hands this a byte
    column the line no longer has, and the conversion clamps to the line's own length rather
    than indexing past it.

    Clamping to the end of the line keeps the position inside a call that continues onto
    later lines, which is what makes the edit land. Clamping to zero, or to the start, would
    put it before the call and decline.
    """
    result = omit_property_at(
        MULTILINE_CALL, "receipt_email", language="typescript", line=1, col=999
    )

    assert result == "const a = stripe.paymentIntents.create({ amount: 1,\n});\n"


INDENTED_CALL = "  const a = create({ receipt_email: 'x' });\n"


def test_a_column_before_the_call_on_its_own_start_line_declines():
    """Column zero of an indented line is on the call's start line and before the call.

    A range is not a line. Accepting the position because the line matched would edit
    whichever call the formatter happened to put there.
    """
    result = omit_property_at(
        INDENTED_CALL, "receipt_email", language="typescript", line=1, col=0
    )

    assert result == "  const a = create({ receipt_email: 'x' });\n"


TWO_STATEMENTS = "const a = create({ receipt_email: 'x' }); const b = 2;\n"


def test_a_column_past_the_call_on_its_end_line_declines():
    """The mirror: a column after the call closes, on the same line.

    Ranges are half-open at the end, so the column the second statement starts at is one past
    the call and not inside it. Treating it as inside would let a stale column edit the
    neighbour of the call the finding named.
    """
    result = omit_property_at(
        TWO_STATEMENTS, "receipt_email", language="typescript",
        line=1, col=TWO_STATEMENTS.index("const b"),
    )

    assert result == "const a = create({ receipt_email: 'x' }); const b = 2;\n"


# --- the literal fact, and the three answers row 4 needs kept apart -------------------

LITERAL_CALL = (
    "const a = stripe.paymentIntents.create({\n"
    "  receipt_email: 'x@example.com',\n"
    "});\n"
)


def test_a_position_naming_no_call_cannot_establish_the_literal_fact():
    """`None`, not `False`. Line 2 of that source is inside the argument object and starts no
    call, so nothing was located and nothing is known about how the argument was written.

    `False` would mean "located, and not a literal", which row 4 reads as a decline it can
    explain. `None` means the router never saw the call at all.
    """
    assert argument_is_literal_at(
        LITERAL_CALL, "receipt_email", language="typescript", line=1, col=0
    ) is None


def test_an_unestablished_literal_fact_keeps_row_four_from_firing():
    """What the `None` above costs: the request-side mechanical row declines and the change
    routes to the agent. Row 4 tests `is True`, so absent evidence is not permission."""
    rule = {"id": "request-property-removed", "kind": "existence",
            "action": "remove", "direction": "request", "level": "error"}
    unestablished = argument_is_literal_at(
        LITERAL_CALL, "receipt_email", language="typescript", line=1, col=0
    )
    established = argument_is_literal_at(
        LITERAL_CALL, "receipt_email", language="typescript", line=0, col=10
    )

    assert route(rule, RoutingFacts(
        field_resolved=True, field_passed_as_literal=unestablished
    )) == (AGENT, "fall-through")
    assert route(rule, RoutingFacts(
        field_resolved=True, field_passed_as_literal=established
    )) == (CODEMOD, "request-field-removed-literal")


def _is_literal(source: str) -> bool | None:
    return argument_is_literal_at(
        source, "receipt_email", language="typescript",
        line=0, col=source.index("create"),
    )


def test_a_template_with_no_substitution_is_a_literal():
    """A backtick string with nothing interpolated is a literal spelled differently. The whole
    of what the call sends is written at the call site, so removing the pair removes the whole
    of it -- which is what row 4 gates on."""
    assert _is_literal("const a = create({ receipt_email: `x@example.com` });\n") is True


def test_a_template_carrying_a_substitution_is_not_a_literal():
    """One substitution reaches a variable, which is the case this predicate exists to keep
    away from a codemod: deleting the pair drops the only use of `user` and leaves the question
    of what it was for."""
    assert _is_literal("const a = create({ receipt_email: `${user}@example.com` });\n") is False


def test_a_tagged_template_is_not_a_literal():
    """`tag`x`` parses as a call, not as a template string, so the substitution scan is never
    reached and the answer comes from the literal-kind set. Right for the right reason: the tag
    function is code, and what it returns is not written at the call site."""
    assert _is_literal("const a = create({ receipt_email: tag`x@example.com` });\n") is False


# --- no rules to apply, which the caller cannot tell from rules that matched nothing ---

RETIRED_MODEL_SOURCE = 'const m = "claude-3-7-sonnet-20250219";\n'


def test_no_rules_leaves_the_source_byte_identical():
    assert apply_rules([], RETIRED_MODEL_SOURCE, "typescript") == (
        'const m = "claude-3-7-sonnet-20250219";\n'
    )


def _no_model_id_change() -> VendorChange:
    """A deprecation naming a replacement and no `model_id`.

    `can_handle` tests the replacement and never the id, so this passes the gate; then
    `model_literal_swap` needs both and emits no rule. The in-repo catalogue always writes
    `model_id`, so this arrives from the two sources that do not go through it -- a published
    feed, whose consumer builds `VendorChange(**entry)` with no check on `raw`, and a
    third-party adapter.
    """
    return VendorChange(
        vendor_id="anthropic", from_version="2026-07-01", to_version="2026-07-28",
        kind="deprecation/model-retired", operation_id="claude-3-7-sonnet-20250219",
        path_ptr="", severity="breaking", source="vendor-deprecation-table",
        raw={"replacement": "claude-opus-4-8", "state": "retired"},
    )


def _clone(root: Path, source: str = RETIRED_MODEL_SOURCE) -> RepoRef:
    # Bytes, because the assertion below is byte-for-byte. `write_text` expands `\n` to
    # `os.linesep`, so on Windows it would put CRLF in a file the remediator reads with
    # `read_bytes` -- the round trip `literal_swap` avoids for exactly this reason.
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "m.ts").write_bytes(source.encode("utf-8"))
    return RepoRef(
        repo_id="r", url="https://example.invalid/r", local_path=str(root), head_sha="s"
    )


def _site() -> CallSite:
    return CallSite(
        id="cs-1", repo_id="r", path="src/m.ts", line=1, col=10, vendor_id="anthropic",
        operation_id="claude-3-7-sonnet-20250219", symbol="model", args_keys=["model"],
        sdk_version="0.70.0", content_hash="h",
    )


def _finding() -> Finding:
    return Finding(
        detector="deprecation", claim="parameter:model", call_site_id="cs-1",
        vendor_change_id="vc-1", severity="breaking", rationale="the case under test",
    )


def test_a_deprecation_with_no_model_id_is_accepted_and_then_produces_nothing(tmp_path: Path):
    """The gap between `can_handle` and `model_literal_swap`, measured rather than argued.

    The retired id is still in the clone afterwards, so the empty diff is not "already
    migrated" -- it is a decline wearing the same clothes.
    """
    repo = _clone(tmp_path)
    change = _no_model_id_change()
    remediator = LiteralSwapRemediator()

    assert remediator.can_handle(_finding(), change) is True

    patch = remediator.propose(_finding(), change, _site(), repo)

    assert patch.diff == ""
    assert (tmp_path / "src" / "m.ts").read_bytes().decode("utf-8") == RETIRED_MODEL_SOURCE


def test_the_conformance_kit_refuses_that_case_rather_than_passing_it(tmp_path: Path):
    """The kit does not read this empty diff as conformance.

    A remediator that declines writes nothing and satisfies every rule about what `propose`
    puts on disk, vacuously. `check_remediator` reports that against the case: nothing was
    measured. So no path through `apply_rules` can make a remediator claim success having
    written nothing -- the kit fails, and downstream `make_patch` reads an empty diff as
    `patch=None` and never reaches `push_branch`.
    """
    with pytest.raises(ConformanceFailure) as raised:
        check_remediator(
            LiteralSwapRemediator(), _finding(), _no_model_id_change(), _site(),
            _clone(tmp_path),
        )

    assert "must be one this remediator patches" in str(raised.value)


MIGRATED_SOURCE = 'const m = "claude-opus-4-8";\n'


def _complete_change() -> VendorChange:
    change = _no_model_id_change()
    return VendorChange(
        vendor_id=change.vendor_id, from_version=change.from_version,
        to_version=change.to_version, kind=change.kind, operation_id=change.operation_id,
        path_ptr=change.path_ptr, severity=change.severity, source=change.source,
        raw={**change.raw, "model_id": "claude-3-7-sonnet-20250219"},
    )


def test_the_no_rules_decline_looks_exactly_like_an_already_migrated_file(tmp_path: Path):
    """Two different facts, one answer, and the answer is the one that means "already correct".

    `apply_rules` returns the input both when there was no rule to apply and when the rules
    matched nothing, and `propose` reduces both to `updated == original`. So the remediator
    reports "nothing to do" for a change it could not build a migration for, and reports it as
    a `Patch` rather than as an exception -- which is what costs the attempt. The tier that
    does distinguish them, `PropertyOmitRemediator`, raises `CannotPatch` instead and the
    cascade falls through to the agent inside the same attempt.
    """
    no_rule = LiteralSwapRemediator().propose(
        _finding(), _no_model_id_change(), _site(), _clone(tmp_path / "a")
    )
    already_done = LiteralSwapRemediator().propose(
        _finding(), _complete_change(), _site(), _clone(tmp_path / "b", MIGRATED_SOURCE)
    )

    assert isinstance(no_rule, Patch) and isinstance(already_done, Patch)
    assert no_rule.diff == already_done.diff == ""
    assert no_rule.strategy == already_done.strategy == "codemod"
    assert (tmp_path / "a" / "src" / "m.ts").read_bytes() == RETIRED_MODEL_SOURCE.encode("utf-8")
    assert (tmp_path / "b" / "src" / "m.ts").read_bytes() == MIGRATED_SOURCE.encode("utf-8")

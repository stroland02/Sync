"""Removing a property from the one call a finding names, not every call that matches.

`omit_parameter` scopes by a value in the same object -- "remove temperature from the object
naming this model". That is the wrong scope for a finding that names a location: a file can
contain two identical calls, and removing the property from both is wrong even when both pass
it, because the finding named one and the reviewer was told it named one.

This scopes by position. `CallSite` records the start of the call expression
(`typescript.py` stores `start_point[0] + 1` and `start_point[1]`), so the position identifies
a call and the object is that call's argument.
"""

from __future__ import annotations

import pytest

from sync.route.templates import omit_property_at

TWO_CALLS = """\
export async function a() {
  return stripe.paymentIntents.create({
    amount: 1000,
    receipt_email: 'a@example.com',
  });
}

export async function b() {
  return stripe.paymentIntents.create({
    amount: 2000,
    receipt_email: 'b@example.com',
  });
}
"""


def _omit(source: str, line: int, col: int, prop: str = "receipt_email") -> str:
    return omit_property_at(source, prop, language="typescript", line=line, col=col)


# --- the case that makes position scoping necessary -------------------------------


def test_only_the_named_call_is_edited():
    """The acceptance case. Two identical calls in one file, both passing the property.

    A naive implementation removes both, and the diff then claims something the finding never
    said.
    """
    result = _omit(TWO_CALLS, line=2, col=9)

    assert "receipt_email: 'a@example.com'" not in result
    assert "receipt_email: 'b@example.com'" in result


def test_the_second_call_can_be_targeted_independently():
    result = _omit(TWO_CALLS, line=9, col=9)

    assert "receipt_email: 'a@example.com'" in result
    assert "receipt_email: 'b@example.com'" not in result


def test_editing_one_call_leaves_the_other_byte_identical():
    result = _omit(TWO_CALLS, line=2, col=9)
    assert "    amount: 2000,\n    receipt_email: 'b@example.com',\n" in result


# --- locating the call ------------------------------------------------------------


def test_a_position_inside_the_call_also_resolves_it():
    """The exact start is preferred, but a position anywhere inside the call resolves to it.

    An off-by-one between a 0-based and a 1-based column would otherwise turn a correct patch
    into a silent no-op, which reads as "nothing to fix".
    """
    result = _omit(TWO_CALLS, line=3, col=4)
    assert "receipt_email: 'a@example.com'" not in result


def test_a_position_matching_no_call_declines():
    assert _omit(TWO_CALLS, line=1, col=0) == TWO_CALLS


def test_a_line_beyond_the_file_declines():
    assert _omit(TWO_CALLS, line=999, col=0) == TWO_CALLS


# --- declining rather than guessing ------------------------------------------------


def test_a_call_without_an_object_argument_declines():
    source = "const r = doThing(receipt_email);\n"
    assert _omit(source, line=1, col=10) == source


def test_a_property_absent_from_the_named_call_declines():
    source = "const r = create({ amount: 1 });\n"
    assert _omit(source, line=1, col=10) == source


def test_a_spread_is_not_mistaken_for_the_property():
    """A spread carries no key, so nothing here names the property. Editing anyway would
    remove a different entry than the finding described."""
    source = "const r = create({ ...defaults });\n"
    assert _omit(source, line=1, col=10) == source


def test_a_nested_object_of_the_named_call_is_not_searched():
    """The property must be an argument of this call, not of something inside it. Removing a
    nested one would produce a diff the finding does not justify."""
    source = (
        "const r = create({\n"
        "  amount: 1,\n"
        "  metadata: { receipt_email: 'x' },\n"
        "});\n"
    )
    assert "metadata: { receipt_email: 'x' }" in _omit(source, line=1, col=10)


# --- the same span discipline as the other edits -----------------------------------


def test_no_dangling_comma_is_left_behind():
    source = "const r = create({ amount: 1, receipt_email: 'x', currency: 'usd' });\n"
    result = _omit(source, line=1, col=10)

    assert ", ," not in result and ",," not in result
    assert result == "const r = create({ amount: 1, currency: 'usd' });\n"


def test_a_trailing_property_is_removed_without_orphaning_its_comma():
    source = "const r = create({ amount: 1, receipt_email: 'x' });\n"
    assert _omit(source, line=1, col=10) == "const r = create({ amount: 1 });\n"


def test_it_is_idempotent():
    once = _omit(TWO_CALLS, line=2, col=9)
    assert omit_property_at(once, "receipt_email", language="typescript", line=2, col=9) == once


@pytest.mark.parametrize("language", ["typescript", "javascript"])
def test_it_works_across_languages(language: str):
    source = "const r = create({ amount: 1, receipt_email: 'x' });\n"
    result = omit_property_at(source, "receipt_email", language=language, line=1, col=10)
    assert result == "const r = create({ amount: 1 });\n"

"""Removing a deprecated argument, which is harder than swapping a string.

A naive removal leaves `{ model: "x", , max_tokens: 16 }`. That is the failure to design
against, and re-parsing does not catch it: tree-sitter recovers silently and reports zero ERROR
nodes for a dangling comma, so a validate-after-editing safety net would have passed the broken
result. The pair and its separator are therefore deleted as one span, which makes the breakage
impossible rather than detectable.

Removal is scoped to the object that also names the model. A `temperature` nested somewhere
else in the same file is not this call's argument, and removing it would edit code the finding
never described.
"""

from __future__ import annotations

import pytest

from sync.route.templates import omit_argument_at, omit_parameter

MODEL = "claude-opus-5"


def _omit(source: str, parameter: str = "temperature", model: str = MODEL) -> str:
    return omit_parameter(source, parameter, language="typescript", within_object_naming=model)


# --- the shapes real code takes ---------------------------------------------------


def test_a_parameter_on_its_own_line_takes_the_line_with_it():
    source = (
        "client.messages.create({\n"
        '  model: "claude-opus-5",\n'
        "  temperature: 0.7,\n"
        "  max_tokens: 16,\n"
        "});\n"
    )
    assert _omit(source) == (
        "client.messages.create({\n"
        '  model: "claude-opus-5",\n'
        "  max_tokens: 16,\n"
        "});\n"
    )


def test_the_last_entry_is_removed_without_orphaning_a_comma():
    source = (
        "client.messages.create({\n"
        '  model: "claude-opus-5",\n'
        "  temperature: 0.7\n"
        "});\n"
    )
    result = _omit(source)

    assert "temperature" not in result
    assert ", }" not in result.replace("\n", " ")
    assert '  model: "claude-opus-5"' in result


def test_an_inline_object_keeps_its_shape():
    source = 'const r = create({ model: "claude-opus-5", temperature: 0.7, max_tokens: 16 });\n'
    assert _omit(source) == 'const r = create({ model: "claude-opus-5", max_tokens: 16 });\n'


def test_an_inline_parameter_at_the_end_is_removed_cleanly():
    source = 'const r = create({ model: "claude-opus-5", temperature: 0.7 });\n'
    assert _omit(source) == 'const r = create({ model: "claude-opus-5" });\n'


def test_every_occurrence_in_scope_is_removed():
    source = (
        'const a = create({ model: "claude-opus-5", temperature: 1 });\n'
        'const b = create({ model: "claude-opus-5", temperature: 2 });\n'
    )
    assert "temperature" not in _omit(source)


# --- the breakage this design exists to prevent -----------------------------------


def test_the_result_never_contains_a_dangling_comma():
    """The failure a naive removal produces, and the one re-parsing does not catch.

    tree-sitter reports zero ERROR nodes for `{ x: 1, , y: 2 }`, so this is asserted on the
    text rather than trusted to a parser that tolerates it.
    """
    for source in (
        'create({ model: "claude-opus-5", temperature: 1, max_tokens: 2 });',
        'create({ temperature: 1, model: "claude-opus-5" });',
        'create({ model: "claude-opus-5", temperature: 1 });',
    ):
        result = _omit(source)
        assert ", ," not in result
        assert ",," not in result
        assert "{ ," not in result and "{," not in result


def test_the_edited_object_still_parses_as_an_object():
    from ast_grep_py import SgRoot

    source = (
        "client.messages.create({\n"
        '  model: "claude-opus-5",\n'
        "  temperature: 0.7,\n"
        "});\n"
    )
    root = SgRoot(_omit(source), "typescript").root()
    obj = root.find(kind="object")

    assert obj is not None
    assert "model" in obj.text()


# --- scope: only the object that names the model ----------------------------------


def test_a_nested_object_with_the_same_key_is_untouched():
    """`metadata.temperature` is not this call's argument. Removing it would edit code the
    finding never described, which is worse than leaving a real one in place."""
    source = (
        "create({\n"
        '  model: "claude-opus-5",\n'
        "  metadata: { temperature: 'hot' },\n"
        "});\n"
    )
    assert "temperature: 'hot'" in _omit(source)


def test_an_unrelated_call_is_untouched():
    source = (
        'other({ model: "gpt-4o", temperature: 0.7 });\n'
        'create({ model: "claude-opus-5", temperature: 0.7 });\n'
    )
    result = _omit(source)

    assert 'other({ model: "gpt-4o", temperature: 0.7 });' in result
    assert result.count("temperature") == 1


# --- declining -------------------------------------------------------------------


def test_a_source_without_the_parameter_is_returned_unchanged():
    source = 'create({ model: "claude-opus-5", max_tokens: 16 });\n'
    assert _omit(source) == source


def test_a_source_without_the_model_is_returned_unchanged():
    source = 'create({ model: "gpt-4o", temperature: 0.7 });\n'
    assert _omit(source) == source


def test_removing_the_only_argument_leaves_a_valid_empty_object():
    source = 'create({ temperature: 0.7, model: "claude-opus-5" });\n'
    result = _omit(source, parameter="temperature")
    assert result == 'create({ model: "claude-opus-5" });\n'


def test_it_is_idempotent():
    source = (
        "create({\n"
        '  model: "claude-opus-5",\n'
        "  temperature: 0.7,\n"
        "});\n"
    )
    once = _omit(source)
    assert _omit(once) == once


@pytest.mark.parametrize("language", ["typescript", "javascript"])
def test_it_works_across_languages(language: str):
    source = 'create({ model: "claude-opus-5", temperature: 1 });\n'
    result = omit_parameter(source, "temperature", language=language, within_object_naming=MODEL)
    assert result == 'create({ model: "claude-opus-5" });\n'


# --- the same deletion, scoped by position instead of by a sibling value -----------
#
# `omit_parameter` scopes to an object that names the model, which is right for a
# deprecation whose finding carries no location. A spec-change finding carries a call
# site, and two calls in one file can both pass the property -- so that scoping would
# edit a call the finding never named. Both entry points share `_deletion_span`; only
# the scoping differs.


def _omit_at(source: str, argument: str, line: int, col: int) -> str:
    return omit_argument_at(source, argument, language="typescript", line=line, col=col)


TWO_CALLS = (
    "const a = await stripe.paymentIntents.create({\n"
    "  amount: 1000,\n"
    "  receipt_email: 'first@example.com',\n"
    "});\n"
    "\n"
    "const b = await stripe.paymentIntents.create({\n"
    "  amount: 2000,\n"
    "  receipt_email: 'second@example.com',\n"
    "});\n"
)


def test_it_removes_the_argument_only_from_the_call_the_finding_located():
    """Two calls in one file, both passing the property. The finding names one; a patch
    touching the other is wrong even though the other is also affected, because the
    reviewer is told the diff covers one call site.
    """
    result = _omit_at(TWO_CALLS, "receipt_email", line=0, col=16)

    assert "first@example.com" not in result
    assert "second@example.com" in result


def test_the_second_call_is_reachable_by_its_own_position():
    result = _omit_at(TWO_CALLS, "receipt_email", line=5, col=16)

    assert "first@example.com" in result
    assert "second@example.com" not in result


def test_a_position_matching_no_call_cannot_be_established():
    """Nothing was located, so nothing is known -- which is not the same as knowing the
    property is absent."""
    assert _omit_at(TWO_CALLS, "receipt_email", line=3, col=0) is None


def test_a_column_that_does_not_match_cannot_be_established():
    """Line alone is not identity: two calls can share a line. A near miss must decline
    rather than fall back to the first call on that line."""
    assert _omit_at(TWO_CALLS, "receipt_email", line=0, col=99) is None


def test_an_argument_the_call_does_not_pass_reads_as_already_correct():
    """The call and its object were located and the key is simply not among them. That
    is an answer, and a different one from "cannot tell": the code already agrees with
    the vendor, so there is nothing for a later tier to do either."""
    assert _omit_at(TWO_CALLS, "customer", line=0, col=16) == TWO_CALLS


def test_an_argument_that_is_not_an_object_literal_cannot_be_established():
    source = "const a = await stripe.paymentIntents.create(params);\n"
    assert _omit_at(source, "receipt_email", line=0, col=16) is None


def test_a_call_with_no_arguments_cannot_be_established():
    source = "const a = await stripe.paymentIntents.create();\n"
    assert _omit_at(source, "receipt_email", line=0, col=16) is None


def test_an_object_carrying_a_spread_declines_rather_than_guessing():
    """`...defaults` may itself supply the property, so deleting the explicit pair does
    not establish that the request stops sending it. The agent can read `defaults`;
    this cannot, and a patch that claims a removal it did not achieve is worse than none.
    """
    source = (
        "const a = await stripe.paymentIntents.create({\n"
        "  ...defaults,\n"
        "  receipt_email: 'x@example.com',\n"
        "});\n"
    )
    assert _omit_at(source, "receipt_email", line=0, col=16) is None


def test_a_matching_name_inside_a_string_or_comment_is_not_touched():
    """The reason this is a parser and not a regular expression."""
    source = (
        "const note = 'receipt_email: keep me';\n"
        "// receipt_email: keep me too\n"
        "const a = await stripe.paymentIntents.create({\n"
        "  amount: 1000,\n"
        "  receipt_email: 'go@example.com',\n"
        "});\n"
    )
    result = _omit_at(source, "receipt_email", line=2, col=16)

    assert "keep me" in result
    assert "keep me too" in result
    assert "go@example.com" not in result


def test_it_is_idempotent_at_a_position():
    once = _omit_at(TWO_CALLS, "receipt_email", line=0, col=16)
    assert _omit_at(once, "receipt_email", line=0, col=16) == once


def test_an_inline_object_keeps_its_spacing():
    source = "const a = stripe.paymentIntents.create({ amount: 1, receipt_email: 'x' });\n"
    assert _omit_at(source, "receipt_email", line=0, col=10) == (
        "const a = stripe.paymentIntents.create({ amount: 1 });\n"
    )

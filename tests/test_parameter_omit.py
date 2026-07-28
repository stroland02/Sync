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

from sync.route.templates import omit_parameter

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

"""Renaming a deprecated argument to the successor a vendor named.

The hazard here is not syntax, it is silence. Renaming `budget_tokens` to `max_tokens` in an
object that already carries `max_tokens` produces a duplicate key, which JavaScript resolves to
the last one without complaint: the code parses, type-checks, and quietly uses a different
value than either the author or the patch intended. That case is declined rather than edited.

Quoting is preserved because a key written `"temperature"` and one written `temperature` are the
same key, and rewriting one form as the other puts a style change in a diff whose only claimed
purpose is a rename.
"""

from __future__ import annotations

import pytest

from sync.route.templates import rename_parameter

MODEL = "claude-opus-5"


def _rename(source: str, old: str = "budget_tokens", new: str = "max_tokens") -> str:
    return rename_parameter(source, old, new, language="typescript", within_object_naming=MODEL)


# --- the rename ------------------------------------------------------------------


def test_a_bare_key_is_renamed():
    source = 'create({ model: "claude-opus-5", budget_tokens: 8 });\n'
    assert _rename(source) == 'create({ model: "claude-opus-5", max_tokens: 8 });\n'


def test_the_value_is_untouched():
    source = "create({\n  model: \"claude-opus-5\",\n  budget_tokens: computeBudget(x),\n});\n"
    assert "computeBudget(x)" in _rename(source)


def test_only_the_key_changes_on_the_line():
    source = 'create({ model: "claude-opus-5", budget_tokens: 8, other: 1 });\n'
    result = _rename(source)

    assert "other: 1" in result
    assert 'model: "claude-opus-5"' in result


# --- quoting is preserved ---------------------------------------------------------


def test_a_double_quoted_key_keeps_its_quotes():
    source = 'create({ model: "claude-opus-5", "budget_tokens": 8 });\n'
    assert _rename(source) == 'create({ model: "claude-opus-5", "max_tokens": 8 });\n'


def test_a_single_quoted_key_keeps_its_quotes():
    source = "create({ model: \"claude-opus-5\", 'budget_tokens': 8 });\n"
    assert _rename(source) == "create({ model: \"claude-opus-5\", 'max_tokens': 8 });\n"


# --- the silent hazard ------------------------------------------------------------


def test_it_declines_when_the_target_key_is_already_present():
    """A duplicate key does not fail. JavaScript takes the last one, so the object would
    silently carry a different value than either the author or this patch intended -- and it
    would type-check on the way through.
    """
    source = 'create({ model: "claude-opus-5", max_tokens: 16, budget_tokens: 8 });\n'
    assert _rename(source) == source


def test_it_declines_per_object_not_globally():
    """One object having a conflict must not stop a clean one being fixed, or a single
    awkward call site would silently freeze the whole file."""
    source = (
        'const a = create({ model: "claude-opus-5", max_tokens: 16, budget_tokens: 8 });\n'
        'const b = create({ model: "claude-opus-5", budget_tokens: 8 });\n'
    )
    result = _rename(source)

    assert 'max_tokens: 16, budget_tokens: 8' in result
    assert 'const b = create({ model: "claude-opus-5", max_tokens: 8 });' in result


def test_a_quoted_duplicate_is_still_a_duplicate():
    """`"max_tokens"` and `max_tokens` are the same key. Comparing the raw text would miss
    the collision and produce exactly the silent overwrite this guards."""
    source = 'create({ model: "claude-opus-5", "max_tokens": 16, budget_tokens: 8 });\n'
    assert _rename(source) == source


# --- scope ------------------------------------------------------------------------


def test_a_nested_object_is_untouched():
    source = (
        "create({\n"
        '  model: "claude-opus-5",\n'
        "  metadata: { budget_tokens: 1 },\n"
        "});\n"
    )
    assert "metadata: { budget_tokens: 1 }" in _rename(source)


def test_an_object_naming_another_model_is_untouched():
    source = 'other({ model: "gpt-4o", budget_tokens: 8 });\n'
    assert _rename(source) == source


# --- edges ------------------------------------------------------------------------


def test_a_source_without_the_parameter_is_unchanged():
    source = 'create({ model: "claude-opus-5", max_tokens: 16 });\n'
    assert _rename(source) == source


def test_it_is_idempotent():
    source = 'create({ model: "claude-opus-5", budget_tokens: 8 });\n'
    once = _rename(source)
    assert _rename(once) == once


def test_every_occurrence_in_scope_is_renamed():
    source = (
        'const a = create({ model: "claude-opus-5", budget_tokens: 1 });\n'
        'const b = create({ model: "claude-opus-5", budget_tokens: 2 });\n'
    )
    assert "budget_tokens" not in _rename(source)


@pytest.mark.parametrize("language", ["typescript", "javascript"])
def test_it_works_across_languages(language: str):
    source = 'create({ model: "claude-opus-5", budget_tokens: 8 });\n'
    result = rename_parameter(
        source, "budget_tokens", "max_tokens", language=language, within_object_naming=MODEL
    )
    assert "max_tokens: 8" in result

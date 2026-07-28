"""Defects an audit reproduced against this module, pinned so they stay fixed.

Each of these produced wrong output rather than an error, which is the class this project
treats as most expensive: a patch that compiles, type-checks, and does the wrong thing.

Every fixture here is deliberately non-ASCII or duplicate-keyed. `CLAUDE.md` records that all
other fixtures in this repository are ASCII, which is exactly why these bugs survived a green
suite.
"""

from __future__ import annotations

from ast_grep_py import SgRoot

from sync.route.templates import omit_parameter, omit_property_at, rename_parameter

MODEL = "claude-opus-5"


# --- byte columns versus character columns ----------------------------------------

# `sync/index/typescript.py` parses `read_bytes()`, so `start_point[1]` is a BYTE column.
# ast-grep reports a CHARACTER column. On any line containing a multi-byte character the two
# diverge, and a large enough divergence lands on a different call entirely.
ACCENTED = (
    "const note = '" + "é" * 57 + "';\n"
    "const a = stripe.p.create({ receipt_email: 'a@example.com' });\n"
    "const b = stripe.q.create({ receipt_email: 'b@example.com' });\n"
)


def _byte_col(source: str, line: int, char_col: int) -> int:
    """The byte column tree-sitter would report for a character column."""
    text = source.splitlines()[line - 1]
    return len(text[:char_col].encode("utf-8"))


def test_a_byte_column_from_the_indexer_resolves_the_right_call():
    """The audit reproduced the opposite: the byte column of call one equalled the character
    column of call two, `_call_at` took it as an exact match, and the wrong call was edited.
    """
    char_col = ACCENTED.splitlines()[1].index("stripe")
    result = omit_property_at(
        ACCENTED, "receipt_email", language="typescript",
        line=2, col=_byte_col(ACCENTED, 2, char_col),
    )

    assert "receipt_email: 'a@example.com'" not in result
    assert "receipt_email: 'b@example.com'" in result


def test_the_accented_line_itself_is_untouched():
    char_col = ACCENTED.splitlines()[1].index("stripe")
    result = omit_property_at(
        ACCENTED, "receipt_email", language="typescript",
        line=2, col=_byte_col(ACCENTED, 2, char_col),
    )
    assert "é" * 57 in result


def test_a_multibyte_value_does_not_shift_the_edit():
    """The span arithmetic mixes tree-sitter offsets with Python string slices. A multi-byte
    character before the target moves one and not the other."""
    source = 'create({ model: "claude-opus-5", note: "café", temperature: 1 });\n'
    result = omit_parameter(source, "temperature", language="typescript", within_object_naming=MODEL)

    assert result == 'create({ model: "claude-opus-5", note: "café" });\n'


# --- overlapping deletion spans ---------------------------------------------------


def test_two_pairs_with_the_same_key_do_not_corrupt_the_object():
    """Reproduced by the audit as `create({ model: "claude-opus-5", );` -- output that does not
    parse. Two spans overlapped and both were applied."""
    source = 'create({ model: "claude-opus-5", temperature: 1, temperature: 2 });\n'
    result = omit_parameter(source, "temperature", language="typescript", within_object_naming=MODEL)

    assert result == 'create({ model: "claude-opus-5" });\n'
    assert SgRoot(result, "typescript").root().find(kind="object") is not None


def test_the_result_of_a_duplicated_key_removal_still_parses():
    source = "create({\n  model: \"claude-opus-5\",\n  temperature: 1,\n  temperature: 2,\n});\n"
    result = omit_parameter(source, "temperature", language="typescript", within_object_naming=MODEL)

    assert "temperature" not in result
    assert SgRoot(result, "typescript").root().find(kind="object") is not None


# --- the duplicate-key guard, defeated by keys that are not pairs -------------------


def test_a_shorthand_property_counts_as_the_key_it_names():
    """`{ max_tokens }` is `max_tokens: max_tokens`. Renaming onto it produces a duplicate key,
    which JavaScript resolves to the last one silently -- the exact failure the guard exists to
    prevent, reached by a node kind the guard did not look at."""
    source = 'create({ model: "claude-opus-5", max_tokens, budget_tokens: 8 });\n'
    assert rename_parameter(
        source, "budget_tokens", "max_tokens", language="typescript", within_object_naming=MODEL
    ) == source


def test_a_computed_key_that_is_a_literal_counts_too():
    source = 'create({ model: "claude-opus-5", ["max_tokens"]: 16, budget_tokens: 8 });\n'
    assert rename_parameter(
        source, "budget_tokens", "max_tokens", language="typescript", within_object_naming=MODEL
    ) == source


def test_a_clean_object_still_renames():
    """The guard must not become so broad it declines everything."""
    source = 'create({ model: "claude-opus-5", budget_tokens: 8 });\n'
    assert "max_tokens: 8" in rename_parameter(
        source, "budget_tokens", "max_tokens", language="typescript", within_object_naming=MODEL
    )

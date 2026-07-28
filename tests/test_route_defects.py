"""Defects an audit reproduced against this module, pinned so they stay fixed.

Each of these produced wrong output rather than an error, which is the class this project
treats as most expensive: a patch that compiles, type-checks, and does the wrong thing.

Every fixture here is deliberately non-ASCII or duplicate-keyed. `CLAUDE.md` records that all
other fixtures in this repository are ASCII, which is exactly why these bugs survived a green
suite.
"""

from __future__ import annotations

from ast_grep_py import SgRoot

from sync.route.templates import (
    _MAX_REMOVALS,
    omit_argument_at,
    omit_parameter,
    omit_property_at,
    rename_parameter,
)

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


# --- removing the sole entry of an inline object ------------------------------------


def test_removing_the_sole_entry_of_an_inline_object_closes_the_braces():
    """The audit reproduced `create({  })` -- two spaces where the pair had been.

    It parses, so nothing downstream fails, which is why it survived. The cost is that a
    diff claiming only to remove an argument also carries a whitespace change, and this
    module already declines that trade twice: `_widen_to_whole_line` exists for it, and
    `rename_parameter` preserves quoting for it.
    """
    source = 'create({ model: "claude-opus-5" });\n'
    result = omit_parameter(source, "model", language="typescript", within_object_naming=MODEL)

    assert result == "create({});\n"


def test_a_sole_entry_with_a_trailing_comma_closes_the_braces_too():
    """The same object written with a trailing comma left one space rather than two.

    Same defect, different branch of `_deletion_span`: the comma is consumed by the
    following-separator rule and the space after the brace is not.
    """
    source = 'create({ model: "claude-opus-5", });\n'
    result = omit_parameter(source, "model", language="typescript", within_object_naming=MODEL)

    assert result == "create({});\n"


def test_the_sole_entry_of_a_multiline_object_keeps_the_whole_line_rule():
    """Pinned as unchanged. The inline fix must not reach the multi-line shape, where
    `_widen_to_whole_line` already takes the entry's line and leaves the braces where the
    author put them."""
    source = 'create({\n  model: "claude-opus-5"\n});\n'
    result = omit_parameter(source, "model", language="typescript", within_object_naming=MODEL)

    assert result == "create({\n});\n"


def test_removing_one_of_several_entries_still_leaves_the_object_spaced():
    """The other direction of the same fix. Closing up the braces must happen only when
    nothing is left between them, or every removal would reformat its neighbours."""
    source = "const a = stripe.p.create({ receipt_email: 'x', amount: 1 });\n"
    result = omit_property_at(
        source, "receipt_email", language="typescript", line=1, col=source.index("stripe")
    )

    assert result == "const a = stripe.p.create({ amount: 1 });\n"


# --- two calls that start at the same position --------------------------------------
#
# The rule: among the calls starting at the recorded position, one whose own argument list
# holds an object literal is preferred, and the widest span breaks a tie. Nesting depth
# alone cannot decide it -- the two shapes below want opposite ends of the nest.


def test_a_call_applied_to_a_calls_result_resolves_to_the_one_holding_the_object():
    """`wrap(cfg)({ ... })`: `wrap(cfg)` and the whole expression both start at the same
    column, and the audit reproduced the inner one being chosen. It has no object argument,
    so the edit found nothing and returned the source -- a silent no-op, which reads as
    "nothing to fix" rather than as a miss."""
    source = "const a = wrap(cfg)({ receipt_email: 'x' });\n"
    result = omit_property_at(
        source, "receipt_email", language="typescript", line=1, col=source.index("wrap")
    )

    assert result == "const a = wrap(cfg)({});\n"


def test_a_chained_call_still_resolves_to_the_inner_one():
    """`stripe.p.create({ ... }).then(h)` was already right, by traversal order rather than
    by rule. Pinned because the rule that fixes the shape above must not break this one:
    here the object is on the inner call and the outer takes `(h)`."""
    source = "const a = stripe.p.create({ receipt_email: 'x' }).then(h);\n"
    result = omit_property_at(
        source, "receipt_email", language="typescript", line=1, col=source.index("stripe")
    )

    assert result == "const a = stripe.p.create({}).then(h);\n"


def test_the_widest_call_wins_when_both_candidates_carry_an_object():
    """`f({ a: 1 })({ receipt_email: 'x' })` leaves the object filter undecided, so the tie
    goes to the widest span -- the complete expression at that position rather than a
    fragment of it. Choosing the narrower one would edit `{ a: 1 }`, which does not hold the
    property, and return the source unchanged."""
    source = "const a = f({ a: 1 })({ receipt_email: 'x' });\n"
    result = omit_property_at(
        source, "receipt_email", language="typescript", line=1, col=source.index("f(")
    )

    assert result == "const a = f({ a: 1 })({});\n"


def test_the_same_rule_decides_which_object_omit_argument_at_edits():
    """`_object_argument_at` picks by traversal order too, and gets the mirror image wrong:
    it took the outer call of a chain, found `(h)` rather than an object, and answered None
    -- "cannot establish" for a shape that is entirely establishable, which abandons a
    finding another tier would have to pay for."""
    source = "const a = stripe.p.create({ receipt_email: 'x' }).then(h);\n"
    result = omit_argument_at(
        source, "receipt_email", language="typescript", line=0, col=source.index("stripe")
    )

    assert result == "const a = stripe.p.create({}).then(h);\n"


def test_omit_argument_at_still_resolves_the_wrapped_call():
    source = "const a = wrap(cfg)({ receipt_email: 'x' });\n"
    result = omit_argument_at(
        source, "receipt_email", language="typescript", line=0, col=source.index("wrap")
    )

    assert result == "const a = wrap(cfg)({});\n"


# --- the removal bound, which the audit did not check -------------------------------


def test_the_removal_bound_is_reachable_by_a_file_rather_than_by_an_object():
    """Pinned as a known limitation, not as intended behaviour.

    `_MAX_REMOVALS` bounds passes over the whole source, not over one object, and
    `omit_parameter` makes one removal per pass. No realistic object carries two hundred
    copies of one key, but a file carrying two hundred calls that each pass it is ordinary,
    and the loop then returns a partially edited source that parses and type-checks. Raising
    the constant moves the cliff rather than removing it; the fix is a caller-visible signal
    that the pass ran out, which is a change to this function's contract and not this task's.
    """
    source = 'stripe.messages.create({ model: "claude-opus-5", temperature: 1 });\n' * (_MAX_REMOVALS + 1)
    result = omit_parameter(source, "temperature", language="typescript", within_object_naming=MODEL)

    assert result.count("temperature") == 1

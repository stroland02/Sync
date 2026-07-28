"""Indexing string literals that name a vendor operation.

The existing indexer finds call sites -- `stripe.charges.create` -- by walking member chains.
A model id is not a call: it is a string sitting in an options object, and no member chain
leads to it. Without this, a deprecation finding knows a model is dying and cannot say where
in the repository it is named, which is the half the vendor's own CSV export already does.

The output is `CallSite` with `operation_id` set to the literal's value, so
`call_sites_for_operation(vendor_id, change.operation_id)` joins these against deprecation
changes with no change to the DETECT stage at all.
"""

from __future__ import annotations

import pytest

from sync.index.literals import index_operation_literals

CLAUDE = ("claude-",)


def _index(source: str, prefixes=CLAUDE, language="typescript"):
    return index_operation_literals(
        source,
        path="src/client.ts",
        repo_id="repo-1",
        vendor_id="anthropic",
        sdk_version="0.70.0",
        prefixes=prefixes,
        language=language,
    )


# --- what it finds ---------------------------------------------------------------


def test_it_finds_a_double_quoted_model_id():
    sites = _index('const m = { model: "claude-3-7-sonnet-20250219" };')

    assert len(sites) == 1
    assert sites[0].operation_id == "claude-3-7-sonnet-20250219"
    assert sites[0].vendor_id == "anthropic"
    assert sites[0].path == "src/client.ts"


def test_it_finds_a_single_quoted_model_id():
    sites = _index("const m = { model: 'claude-opus-4-8' };")
    assert [s.operation_id for s in sites] == ["claude-opus-4-8"]


def test_the_quotes_are_not_part_of_the_operation_id():
    """`operation_id` is joined against the vendor's table, which names the model without
    quotes. Leaving them on would make every join miss and every finding silently vanish."""
    sites = _index('const m = "claude-opus-4-8";')
    assert sites[0].operation_id == "claude-opus-4-8"


def test_line_is_one_based_and_col_is_zero_based():
    """Matches `typescript.py`, which records `start_point[0] + 1` and `start_point[1]`.

    Two indexers disagreeing about line numbering would put the patch on the wrong line, and
    only for the newer kind of finding.
    """
    source = "const a = 1;\nconst m = \"claude-opus-4-8\";\n"
    site = _index(source)[0]

    assert site.line == 2
    assert site.col == source.splitlines()[1].index('"')


def test_every_occurrence_is_its_own_site():
    """`efcc19d` made line and col part of call-site identity to stop same-file collisions.
    Two mentions of one model in one file are two places to patch, not one."""
    source = 'const a = "claude-opus-4-8";\nconst b = "claude-opus-4-8";\n'
    sites = _index(source)

    assert len(sites) == 2
    assert {s.line for s in sites} == {1, 2}


def test_the_enclosing_key_is_recorded_as_the_symbol():
    """A reviewer reading the pull request wants "the `model` field", not "a string".

    `symbol` carries how the value is used, matching the existing indexer where it carries the
    member chain.
    """
    sites = _index('const m = { model: "claude-opus-4-8" };')
    assert sites[0].symbol == "model"


# --- what it must not find -------------------------------------------------------


def test_a_literal_without_a_known_prefix_is_ignored():
    """Precision over recall. Indexing every string in a repository would make the graph
    mostly noise and every join slower for nothing."""
    assert _index('const m = "gpt-4o-2024-11-20";') == []


def test_an_identifier_is_not_a_literal():
    source = "const claude_opus_4_8 = 1;"
    assert _index(source) == []


def test_a_comment_mentioning_a_model_is_not_a_call_site():
    """A patch applied to a comment is noise in a diff a human has to approve."""
    source = '// we used to use "claude-3-7-sonnet-20250219" here\nconst x = 1;\n'
    assert _index(source) == []


def test_an_import_path_that_happens_to_match_is_still_a_literal_but_not_a_model():
    """Guarded by the prefix, not by position. Recorded so the limit is explicit: this
    indexes strings that look like operation ids, and the DETECT join decides which matter."""
    sites = _index('import x from "claude-helper";', prefixes=("claude-",))
    assert [s.operation_id for s in sites] == ["claude-helper"]


def test_empty_source_yields_nothing():
    assert _index("") == []


def test_malformed_source_does_not_raise():
    """Customer repositories contain files that do not parse -- generated code, partial
    checkouts, syntax a newer compiler accepts. One bad file must not abort the index."""
    assert _index("const = = = {{{") == []


# --- identity and provenance -----------------------------------------------------


def test_content_hash_is_stable_for_the_same_line():
    a = _index('const m = "claude-opus-4-8";')[0]
    b = _index('const m = "claude-opus-4-8";')[0]
    assert a.content_hash == b.content_hash


def test_content_hash_differs_when_the_surrounding_line_changes():
    """The hash detects that a site moved or its context changed, which is what lets a
    re-index converge instead of duplicating."""
    a = _index('const m = { model: "claude-opus-4-8" };')[0]
    b = _index('const other = { model: "claude-opus-4-8" };')[0]
    assert a.content_hash != b.content_hash


@pytest.mark.parametrize("language", ["typescript", "javascript"])
def test_it_works_across_languages(language: str):
    sites = _index('const m = "claude-opus-4-8";', language=language)
    assert [s.operation_id for s in sites] == ["claude-opus-4-8"]

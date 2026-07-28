"""Turning a finding into an executable rule instead of a diff.

`2026-07-28-sync-domain-specific-thesis.md` argues the missing piece is a notation: the model
should emit a migration, not edit files. `ast-grep` supplies it, and a deprecated model id is
the first migration mechanical enough to need no model at all -- one string literal becomes
another, with the replacement named by the vendor.

These tests hold the rule to the standard a patch has to meet before it is worth more than a
diff: it applies deterministically, it does not touch what it was not aimed at, and running it
twice changes nothing the second time.
"""

from __future__ import annotations

from datetime import date

import pytest

from sync.route.templates import apply_rules, model_literal_swap
from sync.signals.deprecations import ModelDeprecation, to_vendor_changes

RETIRED = ModelDeprecation(
    vendor_id="anthropic",
    model_id="claude-3-7-sonnet-20250219",
    state="retired",
    replacement="claude-sonnet-4-6",
    retirement_date=date(2026, 2, 19),
    deprecated_date=date(2025, 10, 28),
    not_before=None,
)

NO_REPLACEMENT = ModelDeprecation(
    vendor_id="anthropic",
    model_id="claude-opus-4-20250514",
    state="retired",
    replacement=None,
    retirement_date=date(2026, 6, 15),
    deprecated_date=None,
    not_before=None,
)


def _change(row: ModelDeprecation):
    return to_vendor_changes([row], "a", "b")[0]


def _rules(row: ModelDeprecation = RETIRED):
    return model_literal_swap(_change(row), language="typescript")


# --- what the rule is ------------------------------------------------------------


def test_a_rule_is_emitted_for_a_deprecation_with_a_replacement():
    rules = _rules()
    assert rules
    for rule in rules:
        assert rule["language"] == "typescript"
        assert rule["id"].startswith("sync-")
        assert "fix" in rule


def test_no_rule_without_a_replacement():
    """A migration with no target is not a migration. Emitting a rule that deletes the model
    id, or guesses one, is worse than reporting the finding and stopping."""
    assert model_literal_swap(_change(NO_REPLACEMENT), language="typescript") == []


def test_no_rule_for_a_change_that_is_not_a_deprecation():
    from sync.core import VendorChange

    unrelated = VendorChange(
        vendor_id="stripe", from_version="a", to_version="b",
        kind="response-property-removed", operation_id="PostCharges",
        path_ptr="/v1/charges", severity="breaking", source="oasdiff", raw={},
    )
    assert model_literal_swap(unrelated, language="typescript") == []


# --- what the rule does ----------------------------------------------------------


def test_it_rewrites_a_double_quoted_literal():
    source = 'const m = { model: "claude-3-7-sonnet-20250219" };'
    assert apply_rules(_rules(), source, "typescript") == 'const m = { model: "claude-sonnet-4-6" };'


def test_it_rewrites_a_single_quoted_literal_and_keeps_the_quotes():
    """Style is not the point, minimal diffs are. Converting quotes would add noise to every
    review and could trip a formatter the customer runs in the CI this patch has to pass."""
    source = "const m = { model: 'claude-3-7-sonnet-20250219' };"
    assert apply_rules(_rules(), source, "typescript") == "const m = { model: 'claude-sonnet-4-6' };"


def test_it_rewrites_every_occurrence():
    source = (
        'const a = "claude-3-7-sonnet-20250219";\n'
        'const b = "claude-3-7-sonnet-20250219";\n'
    )
    result = apply_rules(_rules(), source, "typescript")
    assert "claude-3-7-sonnet-20250219" not in result
    assert result.count("claude-sonnet-4-6") == 2


# --- what the rule must not do ---------------------------------------------------


def test_it_leaves_a_different_model_alone():
    source = 'const m = "claude-opus-4-8";'
    assert apply_rules(_rules(), source, "typescript") == source


def test_it_does_not_match_a_longer_id_that_starts_the_same():
    """`claude-3-7-sonnet-20250219` must not rewrite `claude-3-7-sonnet-20250219-preview`.

    A prefix match here would silently retarget a model the vendor never deprecated, and the
    result still compiles -- the failure would only surface at the API.
    """
    source = 'const m = "claude-3-7-sonnet-20250219-preview";'
    assert apply_rules(_rules(), source, "typescript") == source


def test_it_does_not_touch_the_id_inside_a_comment_free_identifier():
    """The id appears as part of a variable name, not as a string. A textual find-and-replace
    would corrupt this; matching the AST does not."""
    source = "const claude_3_7_sonnet_20250219 = 1;"
    assert apply_rules(_rules(), source, "typescript") == source


def test_applying_twice_changes_nothing_the_second_time():
    """Idempotence, the same property every pipeline stage is held to. A patch that is not
    idempotent cannot be safely retried, and the remediation graph retries."""
    source = 'const m = "claude-3-7-sonnet-20250219";'
    once = apply_rules(_rules(), source, "typescript")
    assert apply_rules(_rules(), once, "typescript") == once


def test_source_with_no_match_is_returned_unchanged():
    source = "const x = 1;\n"
    assert apply_rules(_rules(), source, "typescript") == source


# --- the failure the whole feature exists for ------------------------------------


def test_the_migration_survives_a_realistic_call_site():
    """Shaped like real code: the id sits in an options object inside an awaited call.

    This is the case a type checker passes and the vendor rejects -- the SDK accepts any
    string, so `tsc` is silent and the request fails at runtime on a known date.
    """
    source = (
        "const response = await client.messages.create({\n"
        '  model: "claude-3-7-sonnet-20250219",\n'
        "  max_tokens: 1024,\n"
        "  messages: [{ role: 'user', content: 'hi' }],\n"
        "});\n"
    )
    result = apply_rules(_rules(), source, "typescript")

    assert '"claude-sonnet-4-6"' in result
    assert "claude-3-7-sonnet-20250219" not in result
    assert "max_tokens: 1024" in result
    assert "role: 'user'" in result


@pytest.mark.parametrize("language", ["typescript", "javascript"])
def test_the_same_rule_shape_works_across_languages(language: str):
    rules = model_literal_swap(_change(RETIRED), language=language)
    source = 'const m = "claude-3-7-sonnet-20250219";'
    assert apply_rules(rules, source, language) == 'const m = "claude-sonnet-4-6";'

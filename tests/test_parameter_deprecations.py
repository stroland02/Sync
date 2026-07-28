"""Parameters a vendor deprecated, which the SDK still accepts.

This is the sharpest case Sync has for existing. Anthropic's own words: deprecated parameters
"remain in the SDK request types so existing code continues to type-check, but their behavior
changes per model." `tsc` is green and the vendor returns 400. This repository hit exactly that
-- `CLAUDE.md` records `temperature`, `top_p` and `budget_tokens` returning HTTP 400 -- so the
argument is in the project's own history rather than in a pitch.

It is also the first finding that needs *two* facts about one call site: that it passes the
parameter, and that it targets a model the deprecation applies to. Passing `temperature` is
fine on an older model and a 400 on Claude 4.7 or later. A tool without a graph cannot say
which call sites are affected; it can only say the parameter exists.

Fixture is the published table, verbatim.
"""

from __future__ import annotations

import pytest

from sync.signals.deprecations import parse_parameter_deprecations

ANTHROPIC_PARAMETERS = """\
## API parameter deprecations

Anthropic occasionally deprecates request parameters that no longer apply to current models.

| Parameter                       | Status                                 | Behavior                                                                | Recommended replacement                                     |
| ------------------------------- | -------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------ |
| `temperature`, `top_p`, `top_k` | Deprecated (Claude Opus 4.7 and later) | Returns a 400 error when set to a non-default value on Claude 4.7 and later models. | Omit and use [prompting](/docs/en/prompt) to guide behavior. |
| `budget_tokens`                 | Deprecated (Claude Opus 4.5 and later) | Returns a 400 error.                                                    | `max_tokens`                                                 |
"""


def _by_name(rows):
    return {row.parameter: row for row in rows}


# --- one row, several parameters --------------------------------------------------


def test_a_row_naming_three_parameters_yields_three_rows():
    """The published table groups parameters that share a fate.

    Keeping them grouped would mean a finding that names three parameters when a call site
    passes one, and a reviewer cannot act on that without re-reading the vendor page.
    """
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))

    assert {"temperature", "top_p", "top_k", "budget_tokens"} == set(rows)


def test_the_backticks_are_stripped():
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    assert all("`" not in name for name in rows)


# --- the model scope, which is the whole point ------------------------------------


def test_the_model_scope_is_captured():
    """`temperature` is valid on an older model and a 400 on Claude 4.7 or later.

    Without the scope every call site passing the parameter looks affected, which is a false
    positive on every repository that has not upgraded yet.
    """
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))

    assert rows["temperature"].applies_from == "Claude Opus 4.7 and later"
    assert rows["budget_tokens"].applies_from == "Claude Opus 4.5 and later"


def test_the_behaviour_is_kept_for_the_pull_request_body():
    """"Returns a 400 error when set to a non-default value" is what convinces a reviewer.
    Paraphrasing it loses the vendor's authority, which is the only authority here."""
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    assert "400" in rows["temperature"].behavior


# --- replacements: an identifier, or prose that is not one -------------------------


def test_a_named_replacement_is_captured():
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    assert rows["budget_tokens"].replacement == "max_tokens"


def test_prose_guidance_is_not_a_replacement():
    """"Omit and use prompting to guide behavior" is advice, not an identifier.

    Read as one it becomes the target of a rename, writing a sentence into an argument
    position -- the same class as the `---` and markdown-link bugs, and the reason the fix
    here is removal rather than substitution.
    """
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))

    assert rows["temperature"].replacement is None
    assert rows["temperature"].remedy == "omit"


def test_a_named_replacement_is_a_rename_not_an_omission():
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    assert rows["budget_tokens"].remedy == "rename"


# --- robustness -------------------------------------------------------------------


def test_a_page_with_no_parameter_table_yields_nothing():
    """Most vendors publish no such table. Finding none is normal, not a failure."""
    assert parse_parameter_deprecations("openai", "# Deprecations\n\nModels only.\n") == []


def test_the_model_lifecycle_table_is_not_read_as_parameters():
    """Both tables live on one page. A lifecycle row has a state cell and no behaviour, and
    reading one as a parameter would emit findings for every model name."""
    lifecycle = (
        "| API model name | Current state | Deprecated | Tentative retirement date |\n"
        "| -------------- | ------------- | ---------- | ------------------------- |\n"
        "| claude-old-1   | Retired       | June 5, 2026 | August 5, 2026          |\n"
    )
    assert parse_parameter_deprecations("anthropic", lifecycle) == []


def test_malformed_input_does_not_raise():
    assert parse_parameter_deprecations("anthropic", "| broken |\n|---|\n") == []


@pytest.mark.parametrize("name", ["temperature", "top_p", "top_k", "budget_tokens"])
def test_every_parameter_carries_its_vendor(name: str):
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    assert rows[name].vendor_id == "anthropic"


# --- the real page ----------------------------------------------------------------


def test_it_parses_the_shape_the_vendor_actually_publishes():
    """The published row wraps its replacement in a markdown link and its status in
    parentheses. Both were taken verbatim rather than tidied, because tidied fixtures are how
    the `---` placeholder survived until a live page was tried.
    """
    rows = _by_name(parse_parameter_deprecations("anthropic", ANTHROPIC_PARAMETERS))
    row = rows["temperature"]

    assert row.parameter == "temperature"
    assert row.applies_from and row.applies_from.startswith("Claude")
    assert row.replacement is None

"""Model and parameter deprecations: the findings that carry a deadline.

Every other signal Sync produces answers "is this broken?" A deprecation answers "when does
this break?", which is a different and more useful question -- it can be scheduled.

The gap is documented by the vendors themselves. Anthropic's recommended audit is to export a
CSV of usage by API key and model; OpenAI publishes tables of shutdown dates. Both tell you
*that* you use a dying model. Neither can tell you *which line of code holds the string*, and
neither can a type checker: Anthropic's own note says deprecated parameters "remain in the SDK
request types so existing code continues to type-check, but their behavior changes per model."

Fixtures are trimmed from the real published tables on 2026-07-28.
"""

from __future__ import annotations

from datetime import date

import pytest

from sync.signals.deprecations import (
    ModelDeprecation,
    parse_deprecation_table,
    to_vendor_changes,
    urgency,
)

# Real rows, real dates, verbatim shapes.
ANTHROPIC_TABLE = """\
| API model name             | Current state | Deprecated        | Tentative retirement date          |
| -------------------------- | ------------- | ----------------- | ---------------------------------- |
| claude-opus-5              | Active        | N/A               | Not sooner than July 24, 2027       |
| claude-opus-4-1-20250805   | Deprecated    | June 5, 2026      | August 5, 2026                      |
| claude-opus-4-20250514     | Retired       | April 14, 2026    | June 15, 2026                       |
| claude-3-7-sonnet-20250219 | Retired       | October 28, 2025  | February 19, 2026                   |
"""


def _by_id(rows: list[ModelDeprecation]) -> dict[str, ModelDeprecation]:
    return {row.model_id: row for row in rows}


# --- parsing ---------------------------------------------------------------------


def test_the_published_table_parses_into_rows():
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))

    assert set(rows) == {
        "claude-opus-5",
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-3-7-sonnet-20250219",
    }
    assert rows["claude-opus-4-1-20250805"].state == "deprecated"
    assert rows["claude-opus-4-1-20250805"].retirement_date == date(2026, 8, 5)


def test_an_active_model_carries_no_deprecation_date():
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    active = rows["claude-opus-5"]

    assert active.state == "active"
    assert active.deprecated_date is None


def test_not_sooner_than_is_not_a_retirement_date():
    """An active model's cell reads "Not sooner than July 24, 2027" -- a floor, not a date.

    Reading it as a retirement date would manufacture a deadline for a model nobody has
    deprecated, and a false deadline is worse than none: it spends the urgency the real ones
    need.
    """
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    assert rows["claude-opus-5"].retirement_date is None
    assert rows["claude-opus-5"].not_before == date(2027, 7, 24)


def test_a_malformed_table_yields_nothing_rather_than_raising():
    """These tables are scraped from vendor documentation, which is written for humans and
    reformatted without notice. One vendor restyling a page must not abort a scan."""
    assert parse_deprecation_table("anthropic", "not a table at all") == []
    assert parse_deprecation_table("anthropic", "| a | b |\n| - | - |\n") == []


# --- replacements, which live in a different table on the same page ----------------

# The state table names no replacement. Each deprecation announcement carries its own table,
# with the model ids in backticks. Verbatim shape from the published page.
ANTHROPIC_HISTORY = """\
### 2026-06-05: Claude Opus 4.1 model

| Retirement date | Deprecated model           | Recommended replacement |
| --------------- | -------------------------- | ----------------------- |
| August 5, 2026  | `claude-opus-4-1-20250805` | `claude-opus-4-8`       |

### 2025-10-28: Claude Sonnet 3.7 model

| Retirement date   | Deprecated model             | Recommended replacement |
| ----------------- | ---------------------------- | ----------------------- |
| February 19, 2026 | `claude-3-7-sonnet-20250219` | `claude-sonnet-4-6`     |
"""


def test_replacements_are_read_from_the_announcement_tables():
    """A migration needs a target. Without this the finding says "this dies" and cannot say
    what to use instead, which makes it an alert rather than a repair."""
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE + ANTHROPIC_HISTORY))

    assert rows["claude-opus-4-1-20250805"].replacement == "claude-opus-4-8"
    assert rows["claude-3-7-sonnet-20250219"].replacement == "claude-sonnet-4-6"


def test_backticks_are_stripped_from_model_ids():
    """The announcement tables wrap ids in backticks and the state table does not. A
    replacement carrying them would be written into source as `\"`claude-opus-4-8`\"`."""
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE + ANTHROPIC_HISTORY))
    assert "`" not in (rows["claude-opus-4-1-20250805"].replacement or "")


def test_a_model_with_no_announcement_table_has_no_replacement():
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    assert rows["claude-opus-4-20250514"].replacement is None


def test_the_state_table_still_parses_when_history_follows_it():
    """Both tables live in one document, so parsing must not let one corrupt the other --
    the announcement rows have no state column and must not become models."""
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE + ANTHROPIC_HISTORY))
    assert rows["claude-opus-4-1-20250805"].retirement_date == date(2026, 8, 5)
    assert len(rows) == 4


# --- urgency, which is what makes these different ---------------------------------


def test_urgency_counts_down_to_the_retirement_date():
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    row = rows["claude-opus-4-1-20250805"]  # retires 2026-08-05

    assert urgency(row, today=date(2026, 7, 28)) == 8
    assert urgency(row, today=date(2026, 8, 5)) == 0


def test_a_model_past_its_retirement_date_is_already_failing():
    """Negative days are not a smaller number than zero here -- they are a different state.

    Past retirement the vendor says requests "will fail", so this is an outage in the code
    rather than a deadline approaching.
    """
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    row = rows["claude-3-7-sonnet-20250219"]  # retired 2026-02-19

    assert urgency(row, today=date(2026, 7, 28)) < 0


def test_an_active_model_has_no_urgency():
    rows = _by_id(parse_deprecation_table("anthropic", ANTHROPIC_TABLE))
    assert urgency(rows["claude-opus-5"], today=date(2026, 7, 28)) is None


# --- the pipeline handoff ---------------------------------------------------------


def test_only_dying_models_become_vendor_changes():
    """An active model is not a change. Emitting one would put a finding on every model a
    codebase names, which is how a tool teaches people to ignore it."""
    rows = parse_deprecation_table("anthropic", ANTHROPIC_TABLE)
    changes = to_vendor_changes(rows, from_version="2026-07-01", to_version="2026-07-28")

    named = {change.operation_id for change in changes}
    assert "claude-opus-5" not in named
    assert "claude-opus-4-1-20250805" in named


def test_a_change_carries_the_retirement_date_and_replacement_in_raw():
    """`sync.core` is not modified to carry a deadline. VendorChange.raw already exists for
    vendor-specific detail, and adding a field would be a contract change for one adapter."""
    rows = parse_deprecation_table("anthropic", ANTHROPIC_TABLE)
    change = next(c for c in to_vendor_changes(rows, "a", "b") if c.operation_id == "claude-opus-4-1-20250805")

    assert change.raw["retirement_date"] == "2026-08-05"
    assert change.raw["state"] == "deprecated"
    assert change.vendor_id == "anthropic"


def test_a_retired_model_is_breaking_and_a_deprecated_one_is_not_yet():
    rows = parse_deprecation_table("anthropic", ANTHROPIC_TABLE)
    changes = {c.operation_id: c for c in to_vendor_changes(rows, "a", "b")}

    assert changes["claude-3-7-sonnet-20250219"].severity == "breaking"
    assert changes["claude-opus-4-1-20250805"].severity == "deprecation"


def test_the_kind_is_stable_and_namespaced():
    """`kind` is oasdiff's rule-id domain elsewhere. These do not come from oasdiff, so they
    are namespaced to keep the two from ever colliding in a routing table."""
    rows = parse_deprecation_table("anthropic", ANTHROPIC_TABLE)
    for change in to_vendor_changes(rows, "a", "b"):
        assert change.kind.startswith("deprecation/")
        assert change.source == "vendor-deprecation-table"


@pytest.mark.parametrize("state,expected", [("retired", "breaking"), ("deprecated", "deprecation")])
def test_severity_follows_state(state: str, expected: str):
    row = ModelDeprecation(
        vendor_id="anthropic", model_id="m", state=state, replacement="n",
        retirement_date=date(2026, 8, 5), deprecated_date=None, not_before=None,
    )
    assert to_vendor_changes([row], "a", "b")[0].severity == expected

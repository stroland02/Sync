"""How urgent a dying model is, and the parameter changes the signal promised to emit.

Two capabilities the deprecation signal already claimed and did not deliver, both because the
function computing them had no caller.

`urgency` returns days until a model stops working, signed, and its docstring says why the
sign is the point: negative means the retirement date has passed, so the vendor states the
requests already fail and this is an outage in the code rather than a deadline. Nothing
consulted it, so a model that died last month and one dying next year reached a reviewer
looking identical.

`parameters_to_vendor_changes` emitted nothing because nobody called it, even though the
objection its own docstring records -- a parameter change no detector could join -- was
retired when `ParameterDeprecationDetector` was wired.

Every test here drives `sync.cli`, the production path. One that called `urgency` or
`parameters_to_vendor_changes` directly would pass against exactly the state this task exists
to end: the function works, and nothing gets to it.

Dates are injected everywhere. `urgency` takes `today` for this reason, and a test that read
the system clock would pass today and fail in a year, which is a test that gets deleted rather
than fixed.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pytest

import sync.cli as cli
from sync.cli import _model_deprecations, run
from sync.core import RepoRef
from sync.signals.deprecations import ANTHROPIC, OPENAI
from sync.signals.registry import PreparedVendor

# Fixed, so every number below is arithmetic rather than a fact about when the suite ran.
TODAY = date(2027, 1, 1)

# One page carrying every case the sign is supposed to separate: a model whose retirement date
# has passed, one a year out, one dying with no date at all, and one nobody has deprecated.
# The parameter table sits below them, which is how both vendors actually publish -- and is
# what the parser has to keep apart from the lifecycle rows.
ANTHROPIC_PAGE = """\
| API model name  | Current state | Deprecated   | Tentative retirement date   |
| --------------- | ------------- | ------------ | --------------------------- |
| claude-opus-9   | Active        | N/A          | Not sooner than May 1, 2028 |
| claude-past-1   | Retired       | June 5, 2026 | August 5, 2026              |
| claude-later-1  | Deprecated    | June 5, 2026 | January 1, 2028             |
| claude-undated-1| Deprecated    | June 5, 2026 |                             |

### 2026-06-05: an announcement

| Retirement date | Deprecated model  | Recommended replacement |
| --------------- | ----------------- | ----------------------- |
| August 5, 2026  | `claude-past-1`   | `claude-opus-9`         |
| January 1, 2028 | `claude-later-1`  | `claude-opus-9`         |

### Deprecated parameters

| Parameter   | Status                            | Behavior                          | Recommendation |
| ----------- | --------------------------------- | --------------------------------- | -------------- |
| temperature | Deprecated (Claude Opus 4.7 and later) | Returns a 400 error when set. | Omit it        |
"""

# A second vendor, so a wiring that reached one and stopped shows up as a missing change rather
# than passing on the first page it managed to fetch.
OPENAI_PAGE = """\
| API model name | Current state | Deprecated   | Tentative retirement date |
| -------------- | ------------- | ------------ | ------------------------- |
| gpt-past-1     | Retired       | June 5, 2026 | August 5, 2026            |
"""

PAGES = {ANTHROPIC.url: ANTHROPIC_PAGE, OPENAI.url: OPENAI_PAGE}


def _fetch_pages(url: str) -> str:
    if url not in PAGES:
        raise AssertionError(f"nothing fetched {url}")
    return PAGES[url]


def _changes(tmp_path: Path, today: date = TODAY) -> dict:
    """Model deprecations as `VendorChange` rows, through the CLI's own caller."""
    rows = _model_deprecations(
        tmp_path / "cache", "v2320", "v2330", fetch=_fetch_pages, today=today,
    )
    return {change.operation_id: change for change in rows}


# --- the distinction the signed return exists for ---------------------------------


def test_a_dead_model_and_one_dying_next_year_are_distinguishable(tmp_path: Path) -> None:
    """The whole point. Before this, both arrived carrying a retirement date and nothing that
    said one of them had already passed, so a reviewer had to do the subtraction the vendor's
    own data supports."""
    changes = _changes(tmp_path)

    past = changes["claude-past-1"].raw["urgency_days"]
    later = changes["claude-later-1"].raw["urgency_days"]

    assert past != later
    assert past < 0 < later


def test_a_passed_retirement_date_stays_negative(tmp_path: Path) -> None:
    """Not clamped to zero and not dropped. `2026-08-05` is 149 days before `2027-01-01`, and
    the sign is what says these requests fail now rather than later."""
    urgency = _changes(tmp_path)["claude-past-1"].raw["urgency_days"]

    assert urgency == -149


def test_a_model_dying_a_year_out_carries_the_days_remaining(tmp_path: Path) -> None:
    """The other half, so the test above cannot be satisfied by a field that is always
    negative."""
    assert _changes(tmp_path)["claude-later-1"].raw["urgency_days"] == 365


def test_a_dying_model_with_no_retirement_date_has_no_urgency(tmp_path: Path) -> None:
    """None, and specifically not zero. Zero is a deadline that falls today, which is a
    measurement; no date at all is the absence of one, and a reader that could not tell them
    apart would schedule work against a date the vendor never published."""
    urgency = _changes(tmp_path)["claude-undated-1"].raw["urgency_days"]

    assert urgency is None
    assert urgency != 0


def test_a_model_nobody_deprecated_produces_no_change_to_be_urgent_about(
    tmp_path: Path,
) -> None:
    """An active model is not a change, so there is nothing for urgency to land on. Emitting
    one would put a finding against every model a codebase names."""
    assert "claude-opus-9" not in _changes(tmp_path)


# --- determinism ------------------------------------------------------------------


def test_urgency_is_computed_against_the_injected_date(tmp_path: Path) -> None:
    """Same input, same answer, on any day the suite runs.

    Two runs thirty days apart differ by exactly thirty, which is only true if the date came
    from the argument rather than from the clock. A test that asserted one number against
    `date.today()` would pass this week and fail next.
    """
    early = _changes(tmp_path, today=TODAY)["claude-later-1"].raw["urgency_days"]
    late = _changes(tmp_path, today=date(2027, 1, 31))["claude-later-1"].raw["urgency_days"]

    assert early - late == 30


def test_the_state_and_the_urgency_are_decided_against_one_date(tmp_path: Path) -> None:
    """The parse derives lifecycle state from a date and urgency measures against one, and a
    row that read `retired` from one clock and a positive countdown from another would be
    self-contradicting. One resolved date serves both."""
    changes = _changes(tmp_path, today=date(2026, 8, 6))

    assert changes["claude-past-1"].raw["state"] == "retired"
    assert changes["claude-past-1"].raw["urgency_days"] == -1


# --- the parameter half -----------------------------------------------------------


class _CollectingStore:
    def __init__(self) -> None:
        self.changes: list = []

    def apply_schema(self) -> None: ...

    def transaction(self):
        class _Nothing:
            def __enter__(self): return None
            def __exit__(self, *exc): return False

        return _Nothing()

    def truncate_signal_and_detect(self) -> None: ...

    def replace_call_sites(self, repo_id, sites) -> list[str]:
        return [f"cs-{index}" for index, _ in enumerate(sites)]

    def upsert_call_site(self, site) -> str:
        return "cs-1"

    def upsert_vendor_change(self, change) -> None:
        self.changes.append(change)

    def insert_finding(self, finding) -> str:
        return "f-1"


class _NoFindings:
    detector_id = "stub"

    def __init__(self, *args, **kwargs) -> None: ...

    def scan(self):
        return []


class _StubVendor:
    vendor_id = "stripe"

    def __init__(self, *args, **kwargs) -> None: ...

    def fetch_changes(self, from_version, to_version):
        return []


class _StubAdapter:
    def __init__(self, *args, **kwargs) -> None: ...

    def matches(self, repo) -> bool:
        return True

    def index(self, repo):
        return []


@pytest.fixture()
def stubbed(monkeypatch: pytest.MonkeyPatch) -> _CollectingStore:
    """Everything a run needs except the deprecation signal, which is what is under test.

    `_parameter_deprecations` is deliberately left live: the wiring being asserted is that the
    rows it parses become `VendorChange` rows, so stubbing it would remove the only input.
    """
    store = _CollectingStore()
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _NoFindings)
    monkeypatch.setattr(cli, "ParameterDeprecationDetector", _NoFindings)
    monkeypatch.setattr(cli, "ObservedDriftDetector", _NoFindings)
    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(adapter=_StubVendor(), documents=()),
    )
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "http_fetch", _fetch_pages)
    monkeypatch.setattr(cli, "_literal_call_sites", lambda repo: ([], []))
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(
            repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40
        ),
    )
    return store


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )


def test_a_parameter_deprecation_becomes_a_vendor_change_through_the_cli(
    tmp_path: Path, stubbed: _CollectingStore
) -> None:
    """`parameters_to_vendor_changes` was complete, tested, and called by nothing, so the
    remedy and the vendor's own wording reached no remediator. This is the call site.

    Driven through `run()` rather than by calling the function, because calling it is what a
    test could always do and is exactly why the gap survived four sweeps.
    """
    run(_args(tmp_path), today=TODAY)

    parameters = [c for c in stubbed.changes if c.kind == "deprecation/parameter"]
    assert [c.operation_id for c in parameters] == ["temperature"]
    assert parameters[0].raw["remedy"] == "omit"
    assert parameters[0].raw["applies_from"] == "Claude Opus 4.7 and later"


def test_a_parameter_change_carries_no_version_range_it_did_not_come_from(
    tmp_path: Path, stubbed: _CollectingStore
) -> None:
    """A deprecation happens on a date, not across a release. Borrowing the run's Stripe
    window would file an Anthropic parameter under `v2320..v2330`, which is a provenance the
    row does not have -- so both ends carry the date the vendor's page was read instead."""
    run(_args(tmp_path), today=TODAY)

    change = next(c for c in stubbed.changes if c.kind == "deprecation/parameter")

    assert change.from_version == change.to_version == TODAY.isoformat()
    assert "v2320" not in (change.from_version, change.to_version)


def test_the_model_half_still_reaches_the_store_beside_it(
    tmp_path: Path, stubbed: _CollectingStore
) -> None:
    """The parameter wiring must not displace the retirement wiring: both halves read one page
    per vendor and both end up in the store."""
    run(_args(tmp_path), today=TODAY)

    kinds = {c.kind for c in stubbed.changes}
    assert "deprecation/parameter" in kinds
    assert "deprecation/model-retired" in kinds

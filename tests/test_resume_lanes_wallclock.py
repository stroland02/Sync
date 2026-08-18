"""A reset time given as a wall clock with its zone is parseable, and a hold without a deadline never ends.

Claude Code prints `You've hit your session limit ... resets 8:20pm (America/New_York)`. The zone is
stated in the notice, so nothing has to be guessed about the machine. Before this, `reset_seconds`
returned `None` for that shape, `hold_expired` could never fire, and the lane was held forever --
which on 2026-08-18 was the lane running `B7`, the single highest-value item on the board.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "resume_lanes",
    Path(__file__).resolve().parents[1] / "scripts" / "orchestration" / "resume_lanes.py",
)
resume_lanes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(resume_lanes)

NY = ZoneInfo("America/New_York")


def _at(hour: int, minute: int = 0) -> int:
    return int(datetime(2026, 8, 18, hour, minute, tzinfo=NY).timestamp())


def test_a_duration_still_wins_and_is_unchanged():
    assert resume_lanes.reset_seconds("Resets in 1h53m10s.") == 1 * 3600 + 53 * 60 + 10


def test_a_wall_clock_later_today_is_the_gap_until_then():
    notice = "You've hit your session limit  resets 8:20pm (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(19, 20)) == 3600


def test_a_wall_clock_already_past_is_expired_rather_than_tomorrow():
    """**This test asserted the defect and had to be rewritten.**

    It originally required 20:49 against a 20:20 reset to return 23h31m -- tomorrow's occurrence --
    on the reasoning that a past time cannot mean a negative hold. That is true and it is not the
    only alternative: a reset twenty-nine minutes in the past means it has already lifted. The
    original expectation was written from the arithmetic rather than from what an agent CLI means
    when it prints one, and it held a free lane for a day before anybody read the number.
    """
    notice = "resets 8:20pm (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(20, 49)) == 0


def test_a_midnight_form_parses():
    notice = "You've hit your session limit  resets 12:30am (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(23, 30)) == 3600


def test_an_unknown_zone_is_not_guessed():
    assert resume_lanes.reset_seconds("resets 8:20pm (Mars/Olympus)", now=_at(19, 20)) is None


def test_a_wall_clock_with_no_zone_is_not_guessed():
    """The original refusal stands: without a zone there is nothing to compute against."""
    assert resume_lanes.reset_seconds("resets 10:20am", now=_at(9, 20)) is None


def test_a_reset_that_just_passed_is_expired_not_tomorrow():
    """The regression: a hold extended by a full day three minutes after it lifted.

    Lane A printed `resets 1:20am (America/New_York)` and the sweep read it at 01:23. Rolling a
    past time to tomorrow's occurrence gave 1436 minutes, so a lane that had been free for three
    minutes was held for a day. **Session windows are hours, not days** -- Claude's is five, Gemini's
    about two -- so a rolled-forward window longer than any real one means the notice has already
    expired rather than describing a future reset.
    """
    notice = "You've hit your session limit  resets 1:20am (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(1, 23)) == 0


def test_a_genuine_future_reset_later_today_is_unaffected():
    notice = "resets 8:20pm (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(19, 20)) == 3600


def test_a_reset_just_after_midnight_read_before_midnight_still_rolls():
    """Rolling forward is still right when the gap is plausibly one window."""
    notice = "resets 1:20am (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(23, 20)) == 2 * 3600

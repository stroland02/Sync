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


def test_a_wall_clock_already_past_rolls_to_tomorrow():
    """20:49 against a 20:20 reset is tomorrow's, not a negative hold."""
    notice = "resets 8:20pm (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(20, 49)) == pytest.approx(23 * 3600 + 31 * 60, abs=60)


def test_a_midnight_form_parses():
    notice = "You've hit your session limit  resets 12:30am (America/New_York)"
    assert resume_lanes.reset_seconds(notice, now=_at(23, 30)) == 3600


def test_an_unknown_zone_is_not_guessed():
    assert resume_lanes.reset_seconds("resets 8:20pm (Mars/Olympus)", now=_at(19, 20)) is None


def test_a_wall_clock_with_no_zone_is_not_guessed():
    """The original refusal stands: without a zone there is nothing to compute against."""
    assert resume_lanes.reset_seconds("resets 10:20am", now=_at(9, 20)) is None

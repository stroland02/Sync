"""How long a budget hold has left is measured from the notice, not from the terminal's last output.

Those are the same number only while the notice is the last thing the agent printed and Orca's
last-output timestamp is tracking. Neither held on 2026-08-17: Lane D's terminal reported 23 minutes
of silence while carrying a fresh `Resets in 17m34s` banner printed seconds earlier, so the sweep
compared a new window against an old clock, declared the hold expired, and retried into the same
quota wall. The retry produced another notice, and the pass after that reported the lane STALE --
which is the classification that invites an interrupt, and an interrupt is what ended Lane E's
session earlier the same day.

The fix is to remember when each distinct notice was first seen and measure from there.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "resume_lanes",
    Path(__file__).resolve().parents[1] / "scripts" / "orchestration" / "resume_lanes.py",
)
resume_lanes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(resume_lanes)

TASK = "task_lane_d"
FIRST = "Individual quota reached. Resets in 1h42m45s."
SECOND = "Individual quota reached. Resets in 17m34s."


@pytest.fixture
def clock(tmp_path: Path) -> Path:
    return tmp_path / "hold_clock.json"


def test_a_notice_seen_for_the_first_time_starts_its_own_clock(clock: Path):
    elapsed = resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000)
    assert elapsed == 0


def test_the_same_notice_keeps_accumulating(clock: Path):
    resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000)
    assert resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_600) == 600


def test_a_different_notice_restarts_the_clock(clock: Path):
    """The regression. A fresh banner means the last retry already failed."""
    resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000)
    assert resume_lanes.hold_elapsed(clock, TASK, SECOND, now=2_400) == 0
    assert resume_lanes.hold_elapsed(clock, TASK, SECOND, now=2_500) == 100


def test_lanes_do_not_share_a_clock(clock: Path):
    resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000)
    assert resume_lanes.hold_elapsed(clock, "task_lane_e", FIRST, now=1_900) == 0
    assert resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_900) == 900


def test_an_unreadable_clock_file_does_not_stop_the_sweep(clock: Path):
    """The safety net's one job is to run when nobody is watching, so it never dies on its own state."""
    clock.write_text("{ this is not json", encoding="utf-8")
    assert resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000) == 0


def test_the_clock_survives_a_restart_of_the_sweep(clock: Path):
    resume_lanes.hold_elapsed(clock, TASK, FIRST, now=1_000)
    reread = json.loads(clock.read_text(encoding="utf-8"))
    assert reread[TASK]["notice"] == FIRST
    assert reread[TASK]["seen_at"] == 1_000

"""A lane is stalled when its agent has stopped, not when Orca's record of it went bad.

The two come apart constantly. `worker-start` gives up after about a minute waiting for a busy TUI
and marks the dispatch failed, while the agent it was trying to attach to is working the whole time.
Measured 2026-08-17: Lane C spent six minutes inside one `npm install` while every sweep read its
dispatch as failed and created another retry dispatch, one per sweep, against a lane that needed
nothing.

The terminal is the evidence and the dispatch record is the hypothesis.
"""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "resume_lanes",
    Path(__file__).resolve().parents[1] / "scripts" / "orchestration" / "resume_lanes.py",
)
resume_lanes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(resume_lanes)

SILENCE_MS = 8 * 60 * 1000
HANDLE = "term_lane_c"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _live() -> dict[str, int]:
    return {HANDLE: _now_ms() - 3_000}


def _quiet() -> dict[str, int]:
    return {HANDLE: _now_ms() - 40 * 60 * 1000}


def test_a_failed_dispatch_over_a_producing_terminal_is_not_stalled():
    """The regression: six minutes of npm install, one garbage retry dispatch per sweep."""
    dispatch = {"status": "failed", "last_failure": "runtime closed the connection"}
    needs, why = resume_lanes.verdict(dispatch, _live(), SILENCE_MS, fallback_handle=HANDLE)
    assert needs is False
    assert "working" in why


def test_a_failed_dispatch_over_a_silent_terminal_is_stalled():
    dispatch = {"status": "failed", "last_failure": "runtime closed the connection"}
    needs, why = resume_lanes.verdict(dispatch, _quiet(), SILENCE_MS, fallback_handle=HANDLE)
    assert needs is True
    assert "failed" in why


def test_a_failed_dispatch_with_no_terminal_to_check_is_stalled():
    """No evidence is not evidence of health -- without a terminal the record is all there is."""
    dispatch = {"status": "failed", "last_failure": "runtime closed the connection"}
    needs, _ = resume_lanes.verdict(dispatch, {}, SILENCE_MS, fallback_handle=HANDLE)
    assert needs is True


def test_never_attached_over_a_producing_terminal_is_not_stalled():
    """worker-start timing out on a busy TUI is the single most common way this record goes bad."""
    dispatch = {"status": "dispatched", "assignee_handle": None}
    needs, why = resume_lanes.verdict(dispatch, _live(), SILENCE_MS, fallback_handle=HANDLE)
    assert needs is False
    assert "working" in why


def test_never_attached_with_no_recorded_terminal_is_stalled():
    dispatch = {"status": "dispatched", "assignee_handle": None}
    needs, _ = resume_lanes.verdict(dispatch, _live(), SILENCE_MS, fallback_handle=None)
    assert needs is True


def test_an_attached_and_producing_lane_is_left_alone():
    dispatch = {"status": "dispatched", "assignee_handle": HANDLE}
    needs, why = resume_lanes.verdict(dispatch, _live(), SILENCE_MS)
    assert needs is False
    assert "working" in why


def test_an_attached_and_silent_lane_is_stalled():
    dispatch = {"status": "dispatched", "assignee_handle": HANDLE}
    needs, why = resume_lanes.verdict(dispatch, _quiet(), SILENCE_MS)
    assert needs is True
    assert "silent for" in why


def test_a_vanished_terminal_is_stalled():
    dispatch = {"status": "dispatched", "assignee_handle": HANDLE}
    needs, why = resume_lanes.verdict(dispatch, {}, SILENCE_MS)
    assert needs is True
    assert "gone" in why

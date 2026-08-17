"""The safety net's one job is telling an exhausted lane from a dead one.

Every case here is a tail this workspace actually produced. The interesting one is Lane E on
2026-08-17: the quota notice arrived while a tool call was in flight, so the agent's TUI kept
rendering the in-flight line and its own chrome *below* the banner and then never moved again. The
banner was pushed out of the six-line window by static furniture rather than by new output, the
sweep read STALE for fifty-five minutes, and the interrupt sent to unwedge it killed the session.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "resume_lanes",
    Path(__file__).resolve().parents[1] / "scripts" / "orchestration" / "resume_lanes.py",
)
resume_lanes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(resume_lanes)


def _cli_returning(tail: list[str]):
    def call(_cli, *_args):
        return {"result": {"terminal": {"tail": tail}}}

    return call


GEMINI_QUOTA = [
    "Individual quota reached. Please upgrade your subscription to increase your limits. "
    "Resets in 1h53m10s.",
    "Error ID: 9a33d975-2e6e-4c3e-8dad-7bb363d2df1d-5351",
]

# What the agent leaves on screen underneath the banner when the outage lands mid-tool-call. None
# of it is new output -- it is the frame that was already drawn.
FROZEN_CHROME = [
    "  Thought for 5s, 239 tokens",
    "   Analyzing the Blocker",
    "  Bash(orca orchestration send --from term_d...) (ctrl+o to",
    "expand)",
    "",
    "  bypass permissions on (shift+tab to cycle)   5 agents",
    ">",
]


def test_a_banner_at_the_very_end_is_held(monkeypatch):
    monkeypatch.setattr(resume_lanes, "call", _cli_returning(GEMINI_QUOTA))
    assert resume_lanes.budget_held("orca", "term_x") is not None


def test_a_banner_buried_under_frozen_chrome_is_still_held_when_the_lane_is_silent(monkeypatch):
    """The regression. The tail has not moved, so the banner describes now, not history."""
    monkeypatch.setattr(resume_lanes, "call", _cli_returning(GEMINI_QUOTA + FROZEN_CHROME))
    held = resume_lanes.budget_held("orca", "term_x", silent=True)
    assert held is not None
    assert "1h53m10s" in held


def test_a_buried_banner_is_history_when_the_lane_is_producing_output(monkeypatch):
    """The bound this replaces still has to hold: output since the banner is proof of recovery."""
    monkeypatch.setattr(resume_lanes, "call", _cli_returning(GEMINI_QUOTA + FROZEN_CHROME))
    assert resume_lanes.budget_held("orca", "term_x", silent=False) is None


def test_a_healthy_tail_is_never_held(monkeypatch):
    monkeypatch.setattr(resume_lanes, "call", _cli_returning(["running the gate", "351 passed"]))
    assert resume_lanes.budget_held("orca", "term_x", silent=True) is None


@pytest.mark.parametrize(
    ("notice", "expected"),
    [
        ("Resets in 1h53m10s.", 1 * 3600 + 53 * 60 + 10),
        ("resets in 42m", 42 * 60),
        ("resets 10:20am", None),
    ],
)
def test_reset_window_is_read_only_from_a_duration(notice: str, expected: int | None):
    assert resume_lanes.reset_seconds(notice) == expected

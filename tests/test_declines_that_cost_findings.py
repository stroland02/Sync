"""The declines that do cost findings, and the channel that makes them countable.

M3-W106, following `docs/superpowers/reports/2026-07-29-detector-declines.md`. That report
examined the six *uncovered* declines in `src/sync/detect/` and found five of them cannot
happen. Its closing finding is this file's subject: the declines that actually lose a finding
are all covered, so no coverage number will ever point at them, and until now none of them left
anything a caller could count.

The channel is `ParameterDeprecationDetector`'s, extended rather than reinvented -- a counted
`list[str]` on the detector, reset by an eager `scan`, printed as a count by `cli._scan`. Three
conventions for "what could not be read" already exist in this tree and a fourth would be worse
than any of them.

What is deliberately *not* counted is as load-bearing as what is. A row belonging to another
vendor is declined correctly and loses nothing, so counting it would report every other API the
repository calls on every run. `test_a_foreign_vendor_s_traffic_is_declined_without_being_counted`
is the control for that, and it is why the channel is a claim rather than a tally of everything
the loop skipped.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import pytest

from sync.cli import _scan
from sync.core import CallSite, Finding, ObservedCall, ObservedShape
from sync.detect.efficiency import LOOP_THRESHOLD, EfficiencyDetector
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.detect.status_rate import (
    ERROR_RATE_THRESHOLD,
    MIN_STATUSED_CALLS,
    StatusRateDetector,
)
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SEEN = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
OLD = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)

FLOOR = MIN_STATUSED_CALLS
AT_THRESHOLD = math.ceil(FLOOR * ERROR_RATE_THRESHOLD)
BELOW_THRESHOLD = AT_THRESHOLD - 1


# --- the output site: what a caller sees of a decline -------------------------------


class _Store:
    """The insert path `_scan` writes through, with no database behind it."""

    def __init__(self) -> None:
        self.inserted: list[Finding] = []

    def insert_finding(self, finding: Finding) -> str:
        self.inserted.append(finding)
        return f"id-{len(self.inserted)}"


class _Channelled:
    """A detector carrying the channel, with the declines it wants to report."""

    detector_id = "channelled"

    def __init__(self, declines: list[str]) -> None:
        self.declined = declines

    def scan(self) -> list[Finding]:
        return []


class _Channelless:
    """A detector with no channel at all. `VendorChangeDetector` is one and stays one."""

    detector_id = "channelless"

    def scan(self) -> list[Finding]:
        return []


def test_the_scan_output_names_the_detector_and_its_decline_count(capsys):
    """The count reaches an operator, not only a test holding the detector.

    A number that lives on an instance nobody prints is the same silence the channel exists to
    end -- `cli._scan` already prints a per-detector finding count for exactly that reason, and
    a detector that found nothing because it declined everything is indistinguishable there
    from one that found nothing because there was nothing to find.
    """
    _scan([("drift", _Channelled(["a: no baseline", "b: no baseline"]))], _Store())

    assert "drift: 0 finding(s), 2 declined" in capsys.readouterr().out


def test_a_clean_scan_reports_its_declines_as_zero_rather_than_omitting_them(capsys):
    """Present and empty, never absent -- the position `ReachabilityRanking.unreadable` argues.

    An omitted count does not distinguish a detector that declined nothing from one whose
    channel was never wired, and the second is the failure this repository keeps shipping.
    """
    _scan([("drift", _Channelled([]))], _Store())

    assert "drift: 0 finding(s), 0 declined" in capsys.readouterr().out


def test_a_detector_with_no_channel_claims_nothing_about_its_declines(capsys):
    """Absent is not zero, and printing zero for a detector that counts nothing would be a
    claim it never made. `VendorChangeDetector` is read-only to this task and has no channel."""
    printed = _scan([("vendor_change", _Channelless())], _Store())
    del printed

    out = capsys.readouterr().out
    assert "vendor_change: 0 finding(s)" in out
    assert "declined" not in out

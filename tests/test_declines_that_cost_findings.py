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


# --- the graph the detectors read ---------------------------------------------------


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(
    store: GraphStore,
    operation_id: str = "GetAccount",
    reads: tuple[str, ...] = ("data.status",),
    vendor_id: str = "stripe",
) -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id=vendor_id,
            operation_id=operation_id, symbol=f"{vendor_id}.accounts.retrieve",
            args_keys=["limit"], response_fields_read=list(reads),
            sdk_version="18.0.0", content_hash=f"h-{vendor_id}",
        )
    )


def _spans(count: int, prefix: str = "t", status: int | None = 200) -> dict:
    return {
        f"{prefix}span{index}": {"target": f"{prefix}target{index}", "status": status, "resend": 0}
        for index in range(count)
    }


def _statuses(spans: list[int | None], prefix: str = "t") -> dict:
    return {
        f"{prefix}span{index}": {"target": f"{prefix}target{index}", "status": status, "resend": 0}
        for index, status in enumerate(spans)
    }


def _observe_call(store: GraphStore, spans: dict, **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id="GetAccount",
        binding_rung="observed", server_address="api.stripe.com", http_method="get",
        trace_id="t1", url_template="/v1/accounts", spans=spans,
        first_seen=SEEN, last_seen=SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _efficiency(store: GraphStore, vendor_id: str = "stripe") -> EfficiencyDetector:
    return EfficiencyDetector(store=store, repo_id="r", vendor_id=vendor_id)


# --- efficiency: a cost claim with nowhere to report it -----------------------------


def test_a_cost_claim_with_no_indexed_call_site_is_counted(store):
    """The quietest decline in the package.

    There is no `continue` here for coverage to have missed -- `reachable` is empty and the
    loop below it simply does not run -- so the only way this one becomes visible is by being
    counted. The claim was computed and thrown away.
    """
    _observe_call(store, _spans(LOOP_THRESHOLD))
    detector = _efficiency(store)

    assert list(detector.scan()) == []
    assert len(detector.declined) == 1
    assert "GetAccount" in detector.declined[0]
    assert "loop" in detector.declined[0]


def test_a_cost_claim_that_reaches_a_call_site_is_not_counted_as_declined(store):
    """So the counter above cannot be satisfied by one that always reports."""
    _site(store)
    _observe_call(store, _spans(LOOP_THRESHOLD))
    detector = _efficiency(store)

    assert len(list(detector.scan())) == 1
    assert detector.declined == []


def test_a_foreign_vendor_s_traffic_is_declined_without_being_counted(store):
    """The decline that costs nothing, held out of the channel deliberately.

    A row belonging to another vendor is declined because this detector is scoped to one, and
    the finding it would have produced belongs to an instance scoped to the other. Counting it
    would put a number on every run that says "this repository calls more than one API", which
    is the noise that would make the rest of the channel unreadable.
    """
    _site(store)
    _observe_call(store, _spans(LOOP_THRESHOLD, prefix="st"))
    detector = _efficiency(store)
    list(detector.scan())
    without = list(detector.declined)

    _observe_call(store, _spans(LOOP_THRESHOLD * 5, prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com", trace_id="t2")
    louder = _efficiency(store)
    list(louder.scan())

    assert without == [] and louder.declined == []


def test_scanning_twice_reports_the_same_declines(store):
    """Idempotence, held to the standard every other stage is. A channel that accumulated
    across scans would report twice the work on the second run and the conformance kit's
    two-scan comparison would be the only thing that noticed."""
    _observe_call(store, _spans(LOOP_THRESHOLD))
    detector = _efficiency(store)

    list(detector.scan())
    first = list(detector.declined)
    list(detector.scan())

    assert detector.declined == first and first != []


# --- status_rate: three gates, and what each one costs ------------------------------


def _mix(total: int, errors: int, error_status: int = 500) -> list[int | None]:
    """`total` statuses of which `errors` are failures. Failures first; order is not read."""
    return [error_status] * errors + [200] * (total - errors)


def _rate(store: GraphStore) -> StatusRateDetector:
    return StatusRateDetector(store=store, repo_id="r", vendor_id="stripe")


def test_an_operation_failing_under_the_sample_floor_is_counted(store):
    """Half the traffic failing, and silent because there is not enough of it.

    The floor is the right call -- two calls with one failure is not a fifty per cent error
    rate -- but the operation really is failing and the detector really did decline to say so.
    """
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR // 2, FLOOR // 4)))
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert len(detector.declined) == 1
    assert "GetAccount" in detector.declined[0]
    assert str(FLOOR) in detector.declined[0]


def test_an_operation_with_no_failures_under_the_floor_declines_nothing(store):
    """The discrimination the floor decline rests on. A thin population that returned no
    failures lost no finding, and counting it would make the number a count of quiet
    operations rather than of findings the detector chose not to raise."""
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR // 2, 0)))
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert detector.declined == []


def test_an_operation_failing_under_the_rate_threshold_is_counted(store):
    """`ERROR_RATE_THRESHOLD` gets no argument beyond policy -- the module says so itself --
    so the population it silences is exactly the one somebody reviewing the number needs."""
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR, BELOW_THRESHOLD)))
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert len(detector.declined) == 1
    assert f"{BELOW_THRESHOLD} of {FLOOR}" in detector.declined[0]


def test_an_operation_clearing_the_floor_with_no_failures_declines_nothing(store):
    """The same discrimination one gate later, so the threshold decline cannot be satisfied by
    a counter that fires on every healthy operation with enough traffic to be measured."""
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR, 0)))
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert detector.declined == []


def test_a_rate_that_resolves_to_no_indexed_call_site_is_counted(store):
    """Traffic to an operation nothing in the index resolves to. The rate cleared both gates
    and the finding was lost for want of a location, which is the loudest of the three."""
    _observe_call(store, _statuses(_mix(FLOOR, AT_THRESHOLD)))
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert len(detector.declined) == 1
    assert "call site" in detector.declined[0]


def test_a_rate_that_reaches_a_call_site_is_not_counted_as_declined(store):
    """So none of the three counters can be satisfied by one that always reports."""
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR, AT_THRESHOLD)))
    detector = _rate(store)

    assert len(list(detector.scan())) == 1
    assert detector.declined == []


def test_a_foreign_vendor_s_population_is_declined_without_being_counted(store):
    """The same refusal `efficiency` makes, at the same place in the loop and for the same
    reason: a vendor this detector is not scoped to is another instance's finding, not a lost
    one."""
    _site(store)
    _observe_call(store, _statuses(_mix(FLOOR, AT_THRESHOLD), prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com", trace_id="t2")
    detector = _rate(store)

    assert list(detector.scan()) == []
    assert detector.declined == []

"""The detector that reads status codes, and the four ways a rate computed from them can lie.

Every test here that matters is a discrimination rather than a demonstration. A rate is a
fraction, and a fraction has three places to go wrong before the threshold is even reached: the
numerator can count the wrong events, the denominator can count the wrong things, and the
population can merge two things that should not have been averaged. Each has its own test, and
each is built so that the wrong implementation gives the opposite answer rather than a slightly
different one.

The denominator test is the load-bearing one. `observed_call` is keyed per trace, so the
obvious query -- rows with an error, over rows -- is available, cheap, and wrong: a row is not a
call, and one trace of a hundred clean requests would weigh the same as one trace of a single
failure. `test_the_denominator_is_requests_and_not_traces` is built so that the row-counting
implementation fires at 50% where the span-counting one is silent at 1%.

The fault test holds a refusal. Nothing in this table establishes who caused a status code, and
the two rationales it compares are checked for being the same shape rather than for wording.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

import pytest

from sync.core import CallSite, ObservedCall
from sync.core.protocols import Detector
from sync.detect.status_rate import (
    ERROR_RATE_THRESHOLD,
    MIN_STATUSED_CALLS,
    StatusRateDetector,
)
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SEEN = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)

FLOOR = MIN_STATUSED_CALLS
AT_THRESHOLD = math.ceil(FLOOR * ERROR_RATE_THRESHOLD)
"""Errors out of `FLOOR` requests that land the rate exactly on the threshold."""

BELOW_THRESHOLD = AT_THRESHOLD - 1


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(
    store: GraphStore, operation_id: str = "GetCharges", path: str = "src/billing.ts", line: int = 12
) -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path=path, line=line, col=4, vendor_id="stripe",
            operation_id=operation_id, symbol="stripe.charges.list",
            args_keys=["limit"], response_fields_read=["data"],
            sdk_version="18.0.0", content_hash="h",
        )
    )


def _spans(statuses: list[int | None], prefix: str = "s") -> dict:
    """One span per status. The target is distinct per span, so nothing here reads as a repeat."""
    return {
        f"{prefix}{index}": {"target": f"{prefix}target{index}", "status": status, "resend": 0}
        for index, status in enumerate(statuses)
    }


def _mix(total: int, errors: int, error_status: int = 500) -> list[int | None]:
    """`total` statuses of which `errors` are failures. Failures first; order is not read."""
    return [error_status] * errors + [200] * (total - errors)


def _observe(store: GraphStore, statuses: list[int | None], trace_id: str = "t1", **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id="GetCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="get", trace_id=trace_id,
        url_template="/v1/charges", spans=_spans(statuses, prefix=trace_id),
        first_seen=SEEN, last_seen=SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _detector(store: GraphStore) -> StatusRateDetector:
    return StatusRateDetector(store=store, repo_id="r", vendor_id="stripe")


def test_the_detector_satisfies_the_detector_protocol(store):
    assert isinstance(_detector(store), Detector)
    assert _detector(store).detector_id == "status-rate"


def test_an_error_rate_at_the_threshold_over_enough_requests_is_a_finding(store):
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    findings = list(_detector(store).scan())

    assert [f.detector for f in findings] == ["status-rate"]
    assert str(AT_THRESHOLD) in findings[0].rationale
    assert str(FLOOR) in findings[0].rationale


def test_a_rate_one_error_below_the_threshold_stays_silent(store):
    _site(store)
    _observe(store, _mix(FLOOR, BELOW_THRESHOLD))

    assert list(_detector(store).scan()) == []


def test_a_high_rate_below_the_sample_floor_stays_silent(store):
    """Two calls, one failing, is a 50% error rate and means nothing.

    The floor is on the denominator rather than on the finding: a rate is not a rate until
    enough requests have been seen for one error to stop moving it by tens of percent. This is
    the same discipline `observed_drift` applies to its baseline and for the same reason.
    """
    _site(store)
    _observe(store, [500, 200])

    assert list(_detector(store).scan()) == []


def test_a_rate_just_under_the_sample_floor_stays_silent(store):
    """The floor is a floor and not a rounding. One request short is short."""
    _site(store)
    _observe(store, _mix(FLOOR - 1, FLOOR - 1))

    assert list(_detector(store).scan()) == []


def test_the_denominator_is_requests_and_not_traces(store):
    """The wrong query is available, cheap, and gives the opposite answer.

    `FLOOR` traces. Twelve of them make twenty requests each and one of those twenty fails; the
    other eighty-eight make a single clean request. Counting traces that contain a failure over
    traces gives 12%, which clears the threshold and fires. Counting failed requests over
    requests gives twelve out of three hundred and twenty-eight, under four per cent, and is
    silent.

    Built at this size on purpose. The obvious two-row version of this test cannot fail: two
    rows never reach the sample floor, so a row-counting detector is silenced by the floor
    rather than by the denominator, and the test proves nothing about the thing it names. Here
    the row count clears a row-shaped floor and the span count clears a span-shaped one, so
    every arrangement of the wrong query reaches the threshold check and gives the wrong answer.
    """
    _site(store)
    for index in range(12):
        _observe(store, _mix(20, 1), trace_id=f"busy{index}",
                 first_seen=SEEN + timedelta(minutes=index))
    for index in range(FLOOR - 12):
        _observe(store, _mix(1, 0), trace_id=f"quiet{index}",
                 first_seen=SEEN + timedelta(minutes=100 + index))

    assert list(_detector(store).scan()) == []


def test_many_requests_inside_one_trace_count_individually(store):
    """The other half of the grain. One unit of work making FLOOR requests is FLOOR requests."""
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    assert len(list(_detector(store).scan())) == 1


def test_requests_with_no_status_leave_the_fraction_entirely(store):
    """A request that got no response is neither a failure nor a success.

    `ObservedCall.error_count` already refuses to count these as errors. The denominator has to
    make the matching refusal, or every operation whose collector dropped a response looks
    healthier than it is. Enough of them here that including them in the denominator would drag
    the rate under the threshold and silence a finding that should fire.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD) + [None] * FLOOR)

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert str(FLOOR) in findings[0].rationale


def test_requests_with_no_status_never_raise_a_finding_on_their_own(store):
    """The refusal in the other direction: an absent response is not an observed failure."""
    _site(store)
    _observe(store, [None] * (FLOOR * 2))

    assert list(_detector(store).scan()) == []


def test_two_hosts_are_never_averaged_together(store):
    """`server_address` is in the natural key because one operation on two hosts is two
    integrations -- a sandbox and a live key, or two regions. Averaging them produces a rate
    that describes neither.

    A sandbox failing at twice the threshold over exactly the floor, and a healthy production
    host carrying nine times the volume. Merged, the rate is a fifth of the threshold and
    nothing fires. Split, the sandbox fires alone and the finding names it.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD * 2), trace_id="sandbox",
             server_address="api.sandbox.stripe.com")
    _observe(store, _mix(FLOOR * 9, 0), trace_id="live")

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert "api.sandbox.stripe.com" in findings[0].rationale


def test_a_rate_that_rose_between_the_earliest_and_latest_samples_is_breaking(store):
    """The only case in which this detector claims something changed.

    Both samples clear the floor on their own and they do not overlap, so each is a rate rather
    than an impression. The earliest is clean and the latest is at twice the threshold.
    """
    _site(store)
    _observe(store, _mix(FLOOR, 0), trace_id="early", first_seen=SEEN)
    _observe(store, _mix(FLOOR, AT_THRESHOLD * 2), trace_id="late",
             first_seen=SEEN + timedelta(hours=1))

    findings = list(_detector(store).scan())

    assert [f.severity for f in findings] == ["breaking"]


def test_a_rate_already_at_this_level_in_the_earliest_sample_is_informational(store):
    """Nothing changed. An operation that has always failed at this rate is a standing
    condition, and reporting it as breaking would put it in triage beside a call site that
    stopped compiling."""
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD * 2), trace_id="early", first_seen=SEEN)
    _observe(store, _mix(FLOOR, AT_THRESHOLD * 2), trace_id="late",
             first_seen=SEEN + timedelta(hours=1))

    findings = list(_detector(store).scan())

    assert [f.severity for f in findings] == ["info"]


def test_a_rate_with_no_earlier_comparable_sample_is_informational(store):
    """One sample is a level, not a change.

    The stored traffic holds exactly one floor-sized block, so there is no earlier period to
    compare against and the detector says a level rather than inventing a trend.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    findings = list(_detector(store).scan())

    assert [f.severity for f in findings] == ["info"]
    assert len(findings) == 1


def test_two_samples_that_cannot_be_separated_make_no_change_claim(store):
    """Three rows of half a floor each. Any earliest block and any latest block share a row,
    so there are not two independent periods and no comparison is made."""
    _site(store)
    half = FLOOR // 2
    _observe(store, _mix(half, 0), trace_id="a", first_seen=SEEN)
    _observe(store, _mix(half, 0), trace_id="b", first_seen=SEEN + timedelta(minutes=1))
    _observe(store, _mix(half, AT_THRESHOLD * 4), trace_id="c",
             first_seen=SEEN + timedelta(minutes=2))

    findings = list(_detector(store).scan())

    assert [f.severity for f in findings] == ["info"]


def test_a_rate_that_fell_is_not_reported_as_a_change(store):
    """An operation recovering is not a break. The claim is directional and the test says so."""
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD * 4), trace_id="early", first_seen=SEEN)
    _observe(store, _mix(FLOOR, AT_THRESHOLD), trace_id="late",
             first_seen=SEEN + timedelta(hours=1))

    findings = list(_detector(store).scan())

    assert [f.severity for f in findings] == ["info"]


def test_client_and_server_errors_are_reported_the_same_way(store):
    """The refusal this brief was written around.

    A 429 is a limit the caller provoked, a 401 can be a rotated key, and a 500 can be a
    malformed request. Nothing in this table says which side caused a status code, so a 4xx
    group and a 5xx group must produce findings of the same severity and the same shape. A
    detector that graded them differently would be asserting a cause it cannot observe.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD, error_status=429), trace_id="client")
    _observe(store, _mix(FLOOR, AT_THRESHOLD, error_status=500), trace_id="server",
             server_address="api-eu.stripe.com")

    findings = list(_detector(store).scan())

    assert len(findings) == 2
    assert len({f.severity for f in findings}) == 1


def test_the_rationale_carries_the_status_codes_that_were_seen(store):
    """What a reviewer needs to judge a claim the detector cannot make for them.

    The counts are the evidence. Without them the finding says an operation is failing and
    gives a human no way to tell a rate limit from a rotated credential.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD, error_status=429))

    rationale = next(iter(_detector(store).scan())).rationale

    assert "429" in rationale
    assert "4xx" in rationale and "5xx" in rationale


def test_the_rationale_states_the_denominator_it_used(store):
    """A rate quoted without its denominator is the number that gets misquoted.

    Five requests here carried no status. The denominator has to be the statused ones, and the
    rationale has to say the number it divided by -- so `FLOOR` and not `FLOOR + 5`.
    """
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD) + [None] * 5)

    rationale = next(iter(_detector(store).scan())).rationale

    assert f"{AT_THRESHOLD} of {FLOOR}" in rationale
    assert f"{AT_THRESHOLD} of {FLOOR + 5}" not in rationale


def test_every_call_site_for_the_operation_is_told(store):
    """An operation that is failing breaks each place that calls it, and each is a separate
    place a human has to look. Unlike an efficiency finding, this one is additive across call
    sites."""
    _site(store, path="src/billing.ts", line=12)
    _site(store, path="src/reports.ts", line=88)
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    findings = list(_detector(store).scan())

    assert len(findings) == 2
    assert len({f.call_site_id for f in findings}) == 2


def test_a_call_site_that_reads_no_response_field_is_still_told(store):
    """`observed_drift` filters by the fields a site reads because a divergence in a field
    nobody consumes cannot break that site. An operation returning an error breaks the caller
    whatever it reads, so no such filter applies here."""
    store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/fire.ts", line=3, col=1, vendor_id="stripe",
            operation_id="GetCharges", symbol="stripe.charges.list",
            args_keys=[], response_fields_read=[], sdk_version="18.0.0", content_hash="h",
        )
    )
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    assert len(list(_detector(store).scan())) == 1


def test_an_uncorrelated_observation_yields_no_finding(store):
    """`operation_id` is empty when nothing correlated the request. A finding names an
    operation, and there is none to name.

    What enforces this is the no-call-site rule rather than the detector's explicit early-out.
    No `call_site` row carries an empty `operation_id`, so the lookup finds nothing either way,
    and mutation testing says so: deleting the early-out leaves this test green. The assertion
    is still worth keeping -- it pins the outcome callers depend on against whichever mechanism
    happens to deliver it -- but it does not have the coverage its name suggests.
    """
    _site(store)
    _observe(store, _mix(FLOOR, FLOOR), operation_id="", binding_rung="unresolved")

    assert list(_detector(store).scan()) == []


def test_an_operation_no_indexed_code_calls_yields_no_finding(store):
    """Same constraint as every other detector: no call site, no location to report."""
    _observe(store, _mix(FLOOR, FLOOR))

    assert list(_detector(store).scan()) == []


def test_another_repository_traffic_is_never_read(store):
    _site(store)
    _observe(store, _mix(FLOOR, FLOOR), repo_id="other")

    assert list(_detector(store).scan()) == []


def test_another_vendor_traffic_is_never_read(store):
    _site(store)
    _observe(store, _mix(FLOOR, FLOOR), vendor_id="openai")

    assert list(_detector(store).scan()) == []


def test_scanning_twice_returns_the_same_findings(store):
    """The detector reads; it must not accumulate or mutate anything."""
    _site(store)
    _observe(store, _mix(FLOOR, AT_THRESHOLD))

    first = [f.rationale for f in _detector(store).scan()]
    second = [f.rationale for f in _detector(store).scan()]

    assert first == second and first != []

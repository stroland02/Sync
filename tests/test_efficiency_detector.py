"""The first detector whose findings are about money, and therefore the one most able to lie.

Three of these tests exist to hold a refusal rather than a behaviour: no dollar figure, no
page-size finding, and no loop finding assembled out of separate traces. Each is a place where
a plausible-looking number could be produced from data that does not support it, and a
regression there would not fail loudly -- it would quietly start being wrong in a renewal
conversation.

The trace-grain test is the load-bearing one. `observed_call` puts the trace in its natural
key precisely so that one request making 200 calls is distinguishable from 200 requests making
one, and a detector that counted across traces would erase the only property that makes the
loop finding sayable at all.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, ObservedCall
from sync.core.protocols import Detector
from sync.detect.efficiency import (
    LOOP_THRESHOLD,
    REPEAT_THRESHOLD,
    RESEND_THRESHOLD,
    EfficiencyDetector,
)
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

SEEN = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(store: GraphStore, operation_id: str = "GetCharges") -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id=operation_id, symbol="stripe.charges.list",
            args_keys=["limit"], response_fields_read=["data"],
            sdk_version="18.0.0", content_hash="h",
        )
    )


def _spans(targets: list[str], status: int | None = 200, resend: int = 0) -> dict:
    """One span per target. `targets` carries the salted digests, so equal strings are the
    same request having been made twice."""
    return {
        f"span{index}": {"target": target, "status": status, "resend": resend}
        for index, target in enumerate(targets)
    }


def _observe(store: GraphStore, spans: dict, trace_id: str = "t1", **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id="GetCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="get", trace_id=trace_id,
        url_template="/v1/charges", spans=spans, first_seen=SEEN, last_seen=SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _detector(store: GraphStore) -> EfficiencyDetector:
    return EfficiencyDetector(store=store, repo_id="r", vendor_id="stripe")


def test_the_detector_satisfies_the_detector_protocol(store):
    assert isinstance(_detector(store), Detector)
    assert _detector(store).detector_id == "efficiency"


def test_many_calls_to_one_operation_in_one_trace_is_a_loop(store):
    """The strongest signal the table supports, and the one the grain was designed for."""
    _site(store)
    _observe(store, _spans([f"target{i}" for i in range(LOOP_THRESHOLD)]))

    findings = list(_detector(store).scan())

    assert [f.detector for f in findings] == ["efficiency"]
    assert "loop" in findings[0].rationale.lower()
    assert str(LOOP_THRESHOLD) in findings[0].rationale


def test_a_trace_one_call_below_the_threshold_stays_silent(store):
    _site(store)
    _observe(store, _spans([f"target{i}" for i in range(LOOP_THRESHOLD - 1)]))

    assert [f for f in _detector(store).scan() if "loop" in f.rationale.lower()] == []


def test_the_same_volume_spread_across_traces_is_not_a_loop(store):
    """The whole reason the trace is in the natural key.

    One request making LOOP_THRESHOLD calls is a loop. LOOP_THRESHOLD requests making one call
    each is a service under normal load, and a detector that could not tell them apart would
    fire on every busy endpoint. A windowed rollup cannot make this distinction; this table can,
    and this test is what proves the detector actually uses it rather than summing.
    """
    _site(store)
    for index in range(LOOP_THRESHOLD):
        _observe(store, _spans([f"target{index}"]), trace_id=f"trace{index}")

    assert list(_detector(store).scan()) == []


def test_identical_targets_within_one_trace_are_an_uncached_repeat(store):
    """Equal digests mean the same URL. That is what the salted target is for."""
    _site(store)
    _observe(store, _spans(["same"] * (REPEAT_THRESHOLD + 1)))

    findings = [f for f in _detector(store).scan() if "cache" in f.rationale.lower()]

    assert len(findings) == 1
    assert "same request" in findings[0].rationale.lower()


def test_distinct_targets_within_one_trace_are_work_and_not_a_repeat(store):
    """Fetching three different charges is three charges. Only equal digests are a repeat."""
    _site(store)
    _observe(store, _spans([f"charge{i}" for i in range(REPEAT_THRESHOLD + 1)]))

    assert [f for f in _detector(store).scan() if "cache" in f.rationale.lower()] == []


def test_a_repeated_call_that_failed_is_not_reported_as_a_missing_cache(store):
    """A 500 that the caller re-issued is a retry, not an absent cache.

    `ObservedCall.repeated_calls` counts every duplicate digest including these, which is right
    for the property and wrong for this finding: telling somebody to cache a call that failed
    would be advice to cache an error. The detector therefore counts repeats over successful
    spans only, and this test is the difference between the two.
    """
    _site(store)
    _observe(store, _spans(["same"] * (REPEAT_THRESHOLD + 1), status=500))

    assert [f for f in _detector(store).scan() if "cache" in f.rationale.lower()] == []


def test_a_resend_count_at_the_floor_is_a_retry_storm(store):
    _site(store)
    _observe(store, _spans(["target"], resend=RESEND_THRESHOLD))

    findings = [f for f in _detector(store).scan() if "retr" in f.rationale.lower()]

    assert len(findings) == 1
    assert str(RESEND_THRESHOLD) in findings[0].rationale


def test_resend_is_read_as_the_worst_single_call_not_the_total(store):
    """Each span already counts its own resends, so summing them answers no question.

    Enough spans that a sum would clear the floor while every individual call retried once.
    """
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(RESEND_THRESHOLD + 2)], resend=1))

    assert [f for f in _detector(store).scan() if "retr" in f.rationale.lower()] == []


def test_an_uncorrelated_observation_yields_no_finding(store):
    """`operation_id` is empty when nothing correlated the request, and it must stay silent.

    What actually enforces this is the no-call-site rule rather than the detector's explicit
    early-out: no `call_site` row carries an empty `operation_id`, because both indexers drop a
    site whose symbol did not resolve, so the lookup finds nothing either way. Mutation testing
    established that -- deleting the early-out leaves this test green -- and the docstring says
    so rather than claiming a coverage this assertion does not have.

    The assertion is still worth keeping. It pins the outcome, which is what callers depend on,
    against whichever mechanism happens to deliver it.
    """
    _site(store)
    _observe(
        store,
        _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]),
        operation_id="",
        binding_rung="unresolved",
    )

    assert list(_detector(store).scan()) == []


def test_an_operation_no_indexed_code_calls_yields_no_finding(store):
    """Same constraint as `observed_drift`: no call site, no finding."""
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))

    assert list(_detector(store).scan()) == []


def test_another_repository_traffic_is_never_read(store):
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]), repo_id="other")

    assert list(_detector(store).scan()) == []


def test_the_rationale_states_the_call_volume_and_never_a_dollar_figure(store):
    """The finding this task was told to be careful about.

    No table in this repository holds a price per vendor call, so a saving cannot be computed
    from anything real. A call count can. An inflated number quoted at a renewal is worse than
    no number, so the volume is stated and the money is not -- and this test is what stops a
    plausible-looking constant being introduced later.
    """
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))

    for finding in _detector(store).scan():
        assert "$" not in finding.rationale
        assert "usd" not in finding.rationale.lower()
        assert str(LOOP_THRESHOLD) in finding.rationale


def test_findings_are_informational_rather_than_breaking(store):
    """An efficiency finding has not broken anything.

    `Severity` has no cost axis, and the honest fit is `info`. Reporting one as `breaking`
    would let a cost saving compete in triage with a call site that stops compiling.
    """
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))

    assert {f.severity for f in _detector(store).scan()} == {"info"}


def test_no_page_size_finding_is_emitted_from_anything(store):
    """The refusal, pinned so that a proxy cannot be introduced quietly.

    A default page size is visible only in a request's query string. The one column that ever
    held it is the salted target digest, which is one-way by construction, and `url_template`
    carries the vendor's published path with no query string at all. So the table cannot see
    page size, and a detector that fired on a proxy -- many distinct targets looking like a
    pagination walk -- would be guessing while sounding certain.
    """
    _site(store)
    _observe(store, _spans([f"page{i}" for i in range(LOOP_THRESHOLD)]))

    for finding in _detector(store).scan():
        assert "page" not in finding.rationale.lower()


def test_scanning_twice_returns_the_same_findings(store):
    """The detector reads; it must not accumulate or mutate anything."""
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))

    first = [f.rationale for f in _detector(store).scan()]
    second = [f.rationale for f in _detector(store).scan()]

    assert first == second and first != []


def test_a_cost_shared_across_call_sites_says_so_in_every_finding(store):
    """One looping trace against an operation three call sites reach produces three findings,
    and the cost was incurred once.

    That is right for the other detectors and wrong here. A vendor-change finding is a repair
    instruction: each site is independently broken and independently fixable, so three sites
    are three pieces of work. An efficiency finding is a cost claim, and three of them assert
    three savings that do not exist. Totalling a column would report three times the truth, in
    the one setting the design document says these findings exist for.

    The row count stays one per site, so this detector stays consistent with every other one.
    What changes is that each rationale states the cost is shared, and how many sites share it.
    """
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))
    for index in range(3):
        store.upsert_call_site(
            CallSite(
                repo_id="r", path=f"src/a{index}.ts", line=index + 1, col=4,
                vendor_id="stripe", operation_id="GetCharges",
                symbol="stripe.charges.list", args_keys=["limit"],
                response_fields_read=["data"], sdk_version="18.0.0",
                content_hash=f"h{index}",
            )
        )

    findings = list(_detector(store).scan())

    assert len(findings) >= 3
    assert all("shared across 3 call sites" in f.rationale for f in findings)


def test_a_cost_reaching_one_call_site_is_not_described_as_shared(store):
    """The common case, and the one where the note would be a lie.

    One call site is where the cost is not shared with anything, so saying it is shared —
    and saying it over a count of one — would be both false and the kind of phrasing a
    reader stops trusting. The note has to earn its place by there being more than one site.
    """
    _site(store)
    _observe(store, _spans([f"t{i}" for i in range(LOOP_THRESHOLD)]))

    findings = list(_detector(store).scan())

    assert findings
    assert all("shared across" not in f.rationale for f in findings)


def test_two_claims_about_one_call_site_survive_being_stored(store):
    """Two distinct claims about one call site are two findings, and must be two rows.

    The graph derives a finding's id from its identity fields and inserts ON CONFLICT DO
    NOTHING, so two findings the key cannot tell apart are one row and nobody is told which
    one was dropped. One unit of work that calls the same target LOOP_THRESHOLD times is both
    a loop and an absent cache -- the two claims `_claims` documents as not being mutually
    exclusive -- with different fixes, so losing either loses a repair a reviewer would act on.
    """
    _site(store)
    _observe(store, _spans(["same"] * LOOP_THRESHOLD))

    findings = list(_detector(store).scan())
    assert len(findings) >= 2, "the case must produce two claims or this proves nothing"

    for finding in findings:
        store.insert_finding(finding)

    assert len(store.open_findings()) == len(findings)


def test_one_claim_evidenced_by_two_traces_is_one_finding(store):
    """The other half of the same key, and it points the opposite way.

    A trace is unbounded: a busy repository produces one `observed_call` row per request, and
    every one of them looping over the same call site supports the same claim. Emitting a
    finding each would put thousands of rows in front of a reviewer for one piece of work --
    `scan` already argues that N findings assert N savings that do not exist -- so the
    trace is evidence rather than identity, and the detector says it once and quotes the
    worst unit of work it saw.
    """
    _site(store)
    _observe(store, _spans(["a"] * LOOP_THRESHOLD), trace_id="quiet")
    _observe(store, _spans(["b"] * (LOOP_THRESHOLD * 3)), trace_id="loud")

    findings = [f for f in _detector(store).scan() if "loop" in f.rationale.lower()]

    assert len(findings) == 1
    assert str(LOOP_THRESHOLD * 3) in findings[0].rationale, "the worst trace is the one quoted"


def test_a_second_ingest_updates_the_claim_rather_than_adding_a_row(store):
    """The guard against the obvious fix, which is wrong in the opposite direction.

    Folding the rationale into the finding's id would have separated the two claims, and it
    would also have made the id a function of a live call count. The count is not stable across
    ingests -- more traffic arrives, the loop gets longer -- so every ingest would write a fresh
    row for a claim already in the graph, and a reviewer would see the same loop reported over
    and over. That is a silent duplication where the bug being fixed was a silent loss.

    Two scans separated by more traffic, and the claim converges on the row it already wrote.
    """
    _site(store)
    _observe(store, _spans([f"a{i}" for i in range(LOOP_THRESHOLD)]))
    first = [store.insert_finding(f) for f in _detector(store).scan()]

    _observe(store, _spans([f"b{i}" for i in range(LOOP_THRESHOLD * 2)]))
    second = [store.insert_finding(f) for f in _detector(store).scan()]

    assert first and first == second, "the same claim must derive the same id after more traffic"
    assert len(store.open_findings()) == len(first)

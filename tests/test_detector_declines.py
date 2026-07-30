"""The six places a detector declines to emit a finding, and what a caller sees of each.

M3-W103. Five of the six turn out to be unreachable through the only entry point a detector
has, and this file does not reach them by calling internals. What it pins instead is the clause
that makes each one dead, because that clause is the thing whose change would bring the guard
back to life -- and a guard nobody can reach is dead by an argument, not by a coincidence, only
if the argument is asserted somewhere.

Three of the five are `if site.id is None: continue`, in `observed_drift._undeclared`,
`observed_drift._diverged` and `status_rate.scan`. All three read their sites from
`GraphStore.call_sites_for_operation`, whose rows come from a `TEXT PRIMARY KEY`, so `id` is
never None. `parameter_deprecation` carries the same guard and needs it, because it takes its
call sites from the caller rather than from the store -- and `vendor_change` carries no guard at
all and is right not to. Four detectors, three answers, and the difference is provenance.

The other two are in `status_rate`: `_leading_block`'s exhausted `return None` and `_periods`'
`if leading is None or trailing is None`. `scan` will not call `_periods` until the whole
population has cleared the same floor the split is measured against, so a block always exists.
`test_the_floor_that_gates_a_finding_is_the_floor_that_splits_the_periods` is the coupling those
two rest on.

The sixth -- `efficiency`'s vendor guard -- is reachable, ordinary, and fires on every healthy
multi-vendor repository. It is covered here three ways, because the failure it prevents is not a
missing finding but a finding attributed to the wrong vendor's traffic.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

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
NEW = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)

FLOOR = MIN_STATUSED_CALLS
AT_THRESHOLD = math.ceil(FLOOR * ERROR_RATE_THRESHOLD)

SHARED_OPERATION = "GetAccount"
"""An operation id two vendors both plausibly publish.

The guard `efficiency` applies to a foreign vendor's traffic is only observable when the two
vendors' populations can collide, and they collide on `operation_id` -- which is the key
`strongest` holds its per-claim winner under, with no vendor component. A fixture using
`GetCharges` for one vendor and `ListMessages` for the other cannot fail however the guard is
broken, because the call-site lookup finds nothing for the foreign operation and the finding is
lost one line later for an unrelated reason.
"""


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(
    store: GraphStore,
    vendor_id: str = "stripe",
    operation_id: str = SHARED_OPERATION,
    path: str = "src/billing.ts",
    reads: tuple[str, ...] = ("data",),
) -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path=path, line=12, col=4, vendor_id=vendor_id,
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


def _observe_call(store: GraphStore, spans: dict, **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id=SHARED_OPERATION,
        binding_rung="observed", server_address="api.stripe.com", http_method="get",
        trace_id="t1", url_template="/v1/accounts", spans=spans,
        first_seen=SEEN, last_seen=SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _efficiency(store: GraphStore, vendor_id: str = "stripe") -> EfficiencyDetector:
    return EfficiencyDetector(store=store, repo_id="r", vendor_id=vendor_id)


# --- efficiency's vendor guard: the one decline that is reachable -------------------


def test_another_vendor_s_traffic_against_a_shared_operation_id_raises_nothing(store):
    """The reachable decline, and the finding it stops is worse than a missing one.

    The repository calls two vendors and both publish an operation this index recorded under the
    same id. `observed_calls` is scoped by repository and not by vendor, so the Twilio row
    arrives at the Stripe detector; without the guard it becomes a Stripe loop finding, quoting
    Twilio's call volume against a Stripe call site. That is not a lost finding, it is a cost
    claim about the wrong integration.
    """
    _site(store, vendor_id="stripe")
    _site(store, vendor_id="twilio", path="src/sms.ts")
    _observe_call(store, _spans(LOOP_THRESHOLD, prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com")

    assert list(_efficiency(store, vendor_id="stripe").scan()) == []


def test_the_same_traffic_is_read_by_the_detector_scoped_to_its_own_vendor(store):
    """The positive control the test above needs in order to mean anything.

    A negative assertion over a fixture nothing could ever fire on is satisfied by a detector
    that never fires at all. Same graph, same rows, detector scoped to Twilio: the finding
    appears, so the silence above is the guard rather than an inert fixture.
    """
    _site(store, vendor_id="stripe")
    _site(store, vendor_id="twilio", path="src/sms.ts")
    _observe_call(store, _spans(LOOP_THRESHOLD, prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com")

    findings = list(_efficiency(store, vendor_id="twilio").scan())

    assert [f.detector for f in findings] == ["efficiency"]
    assert "api.twilio.com" in findings[0].rationale


def test_another_vendor_s_louder_trace_never_displaces_the_quoted_one(store):
    """`strongest` is keyed `(operation_id, claim.kind)` and carries no vendor component.

    So the guard is not only about which findings exist, it is about which trace gets quoted. A
    Twilio unit of work five times as loud as the Stripe one would win the key and put Twilio's
    number in a Stripe rationale -- the same row count, the wrong magnitude, and nothing
    downstream able to tell.
    """
    _site(store, vendor_id="stripe")
    _observe_call(store, _spans(LOOP_THRESHOLD, prefix="st"))
    _observe_call(store, _spans(LOOP_THRESHOLD * 5, prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com")

    findings = [f for f in _efficiency(store).scan() if "loop" in f.rationale.lower()]

    assert len(findings) == 1
    assert f"{LOOP_THRESHOLD} calls" in findings[0].rationale
    assert "api.stripe.com" in findings[0].rationale
    assert "twilio" not in findings[0].rationale


def test_a_declined_observation_leaves_no_trace_the_caller_could_count(store):
    """The invisibility, asserted rather than described.

    A graph holding a foreign vendor's traffic produces findings equal to a graph that never
    held it, field for field. The detector has carried a `declined` channel since M3-W106 and
    this decline is deliberately kept out of it: correct vendor scoping loses no finding, and
    counting it would report every other API the repository calls on every run.
    `test_a_foreign_vendor_s_traffic_is_declined_without_being_counted` holds that half.
    """
    _site(store, vendor_id="stripe")
    _observe_call(store, _spans(LOOP_THRESHOLD, prefix="st"))
    without = [f.model_dump(exclude={"created_at"}) for f in _efficiency(store).scan()]

    _observe_call(store, _spans(LOOP_THRESHOLD * 5, prefix="tw"), vendor_id="twilio",
                  server_address="api.twilio.com")
    with_declined = [f.model_dump(exclude={"created_at"}) for f in _efficiency(store).scan()]

    assert without and without == with_declined


# --- the clause that makes three `site.id is None` guards dead ----------------------


def test_the_column_a_call_site_id_is_read_from_cannot_be_null(store):
    """Why three of the six declines cannot happen, asserted against the live schema.

    `observed_drift._undeclared`, `observed_drift._diverged` and `status_rate.scan` each guard
    `site.id is None`, and each reads its sites only from `call_sites_for_operation`, which is
    `SELECT * FROM call_site`. `id` is that table's primary key, so the attribute is never None
    and the three `continue` statements are unreachable. Change this column and they come alive.

    The second assertion is what makes the first one able to fail. A query that returned 'NO'
    for everything -- a mistyped column name reading as absent, a filter that matched nothing --
    would satisfy the first assertion for the wrong reason, so a column this schema deliberately
    leaves nullable is read through the same query and has to come back 'YES'.
    """
    rows = store._connect().execute(
        """
        SELECT table_name, column_name, is_nullable
          FROM information_schema.columns
         WHERE (table_name, column_name) IN (('call_site', 'id'), ('finding', 'vendor_change_id'))
        """
    ).fetchall()
    nullable = {(row["table_name"], row["column_name"]): row["is_nullable"] for row in rows}

    assert nullable[("call_site", "id")] == "NO"
    assert nullable[("finding", "vendor_change_id")] == "YES"


def test_every_call_site_the_store_hands_a_detector_carries_an_id(store):
    """The same fact one level up, at the call the three detectors actually make."""
    _site(store, vendor_id="stripe")
    _site(store, vendor_id="stripe", path="src/reports.ts")

    sites = store.call_sites_for_operation("stripe", SHARED_OPERATION)

    assert len(sites) == 2
    assert all(site.id is not None for site in sites)


def test_a_finding_built_without_a_call_site_id_is_refused_rather_than_stored(store):
    """Why `vendor_change` needs no guard, and why the other three are belt on braces.

    `Finding.call_site_id` is `str` with no default. So the alternative to guarding is not a
    finding that resolves to nothing -- it is a `ValidationError` at the moment of construction.
    `vendor_change.scan` passes `site.id` straight through on that basis and is correct to.

    The second half is the control. A test that only watches a constructor raise passes when the
    constructor is broken for some other reason, so the same call with an id has to succeed.
    """
    with pytest.raises(ValidationError) as raised:
        Finding(
            detector="observed-drift", claim="shape-drift:/data/status", call_site_id=None,
            severity="info", rationale="r",
        )

    assert "call_site_id" in str(raised.value)

    accepted = Finding(
        detector="observed-drift", claim="shape-drift:/data/status", call_site_id="cs1",
        severity="info", rationale="r",
    )
    assert accepted.call_site_id == "cs1"


# --- the coupling that makes status_rate's two remaining declines dead --------------


def _statuses(total: int, errors: int) -> list[int]:
    return [500] * errors + [200] * (total - errors)


def _rate_spans(statuses: list[int], prefix: str) -> dict:
    return {
        f"{prefix}{index}": {"target": f"{prefix}target{index}", "status": status, "resend": 0}
        for index, status in enumerate(statuses)
    }


def test_the_floor_that_gates_a_finding_is_the_floor_that_splits_the_periods(store):
    """`_leading_block`'s exhausted `return None` and `_periods`' None guard rest on this.

    `scan` will not call `_periods` until `_tally(rows).statused` has reached `self._floor`, and
    `_leading_block` counts statused requests by the same predicate over the same rows. So the
    cumulative count always reaches the floor before the rows run out, and neither statement can
    execute.

    What that argument needs is for the two floors to be one floor, and this is that assertion,
    made from outside: one graph, two detectors differing only in the floor. At ten, two blocks
    of ten exist and are disjoint, so a comparison is stated. At twenty, the population still
    clears the gate -- twenty statused requests in total -- and the leading block now consumes
    both rows, so the two blocks overlap and no comparison is stated. In neither case is a block
    absent. A `_periods` measured against a different floor from the gate would lose the
    comparison at ten, which is the mutation this kills.
    """
    _site(store, vendor_id="stripe")
    _observe_call(store, _rate_spans(_statuses(10, 0), "early"), trace_id="early",
                  first_seen=SEEN, last_seen=SEEN)
    _observe_call(store, _rate_spans(_statuses(10, 10), "late"), trace_id="late",
                  first_seen=SEEN + timedelta(hours=1), last_seen=SEEN + timedelta(hours=1))

    at_ten = list(
        StatusRateDetector(store, repo_id="r", vendor_id="stripe", min_statused_calls=10).scan()
    )
    at_twenty = list(
        StatusRateDetector(store, repo_id="r", vendor_id="stripe", min_statused_calls=20).scan()
    )

    assert len(at_ten) == 1
    assert "earliest 10 request(s) held show 0.0%" in at_ten[0].rationale
    assert at_ten[0].severity == "breaking"

    assert len(at_twenty) == 1
    assert "does not contain two separated samples" in at_twenty[0].rationale
    assert at_twenty[0].severity == "info"


def test_a_population_that_clears_the_gate_always_states_one_of_the_two_histories(store):
    """The observable form of the same invariant, over every population size that fires.

    There is no third sentence and no crash: whatever the shape of the traffic, a finding either
    quotes two rates or says it holds only a level. `_periods` has a third return path for
    "no block reached the floor" and it is not among the outcomes, because reaching this point
    means a block was reached.
    """
    _site(store, vendor_id="stripe")
    for index in range(4):
        _observe_call(
            store,
            _rate_spans(_statuses(FLOOR // 2, AT_THRESHOLD), f"r{index}"),
            trace_id=f"r{index}",
            first_seen=SEEN + timedelta(minutes=index),
            last_seen=SEEN + timedelta(minutes=index),
        )

    findings = list(StatusRateDetector(store, repo_id="r", vendor_id="stripe").scan())

    assert len(findings) == 1
    rationale = findings[0].rationale
    stated = "does not contain two separated samples" in rationale
    compared = "request(s) held show" in rationale
    assert stated != compared, rationale


# --- observed_drift: the floor guards the row, not the row that grades it -----------


def _observe_shape(store: GraphStore, **over) -> None:
    fields = dict(
        vendor_id="stripe", operation_id=SHARED_OPERATION, field_path="/data/status",
        json_type="string", source="replay", sample_count=MIN_SAMPLES,
        first_seen=NEW, last_seen=NEW,
    )
    fields.update(over)
    store.record_observed_shape(ObservedShape(**fields))


DECLARED_STRING = DeclaredField(
    field_path="/data/status", json_types=frozenset({"string"}), required=True, nullable=False,
)


def _drift(store: GraphStore) -> ObservedDriftDetector:
    return ObservedDriftDetector(store, spec={SHARED_OPERATION: [DECLARED_STRING]})


def test_a_single_earlier_observation_is_enough_to_grade_a_divergence_breaking(store):
    """Pinned because it reads as an asymmetry rather than as a decision.

    `MIN_SAMPLES` gates the row a finding is raised on. It does not gate the sibling row that
    decides that finding's severity: `_contradicts_earlier_window` reads every sibling whatever
    its count. So one observation -- the count the module's own docstring calls "one upstream
    incident or one misbehaving account" -- promotes a divergence from `info` to `breaking`, and
    severity is where this module says its confidence lives.

    The sibling here is not even the declared type. A single earlier `null` is a divergence in
    its own right, too thin to report on its own, and sufficient to grade a different divergence
    as the vendor's behaviour having changed.

    Both lines are covered, so this is not a defect this task fixes. The test exists so the
    asymmetry is visible in the suite rather than only in a report.
    """
    _site(store, vendor_id="stripe", reads=("data.status",))
    _observe_shape(store, json_type="null", nullable_seen=True, first_seen=OLD, sample_count=1)
    _observe_shape(store, json_type="number", first_seen=NEW, sample_count=MIN_SAMPLES)

    findings = list(_drift(store).scan())

    assert len(findings) == 1
    assert findings[0].severity == "breaking"


def test_the_same_divergence_with_no_earlier_sibling_at_all_is_informational(store):
    """The control for the test above: without the one-sample row the grade is `info`, so the
    assertion there is about the sibling and not about the divergence."""
    _site(store, vendor_id="stripe", reads=("data.status",))
    _observe_shape(store, json_type="number", first_seen=NEW, sample_count=MIN_SAMPLES)

    findings = list(_drift(store).scan())

    assert len(findings) == 1
    assert findings[0].severity == "info"

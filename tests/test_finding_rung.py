"""A persisted finding can be attributed to the rung that produced it.

`CLAUDE.md`: *Every binding carries the rung it came from -- `static`, `resolved`, or `observed`
-- and so does every artifact derived from it. A false positive that cannot be attributed to a
rung cannot be fixed.* And `.claude/rules/graph-grain.md` says where it lives: *If a row's
content depends on a binding, the row records which rung produced that binding. **Not a join
away -- a column.***

`finding` had no such column, and neither did `call_site`, so a finding could not be attributed
even by joining. The cost was already being paid: `sync.benchmark.binding` scores precision per
rung and carries its own `EmittedFinding` type whose docstring says *"Not `sync.core.Finding`,
which carries no rung"* -- so the module that exists to attribute a false positive to a binder
could not read the rung off the row, and its own docstring says an aggregate without the split
is useless.

The rule that decides which rung a finding carries
--------------------------------------------------
**The rung names the binding whose wrongness would make the finding wrong.** Run the five
detectors through it and no further judgement is needed:

- `vendor_change`, `parameter_deprecation` -- a wrong static binding makes the finding wrong and
  nothing else is load-bearing. `static`.
- `observed_drift` -- the binding is static and the evidence is observed. A wrong static binding
  makes it wrong; a correct binding with a surprising shape is the finding working. `static`.
- `efficiency`, `status_rate` -- a perfect static binding still yields a wrong finding if the
  span-to-operation correlation is wrong, and that correlation is a binding whose rung
  `observed_call` already records. Carried through, including when it is `unresolved`.

Where a finding rests on two load-bearing bindings the weaker rung wins. Inside these two
detectors that is a two-value decision -- `observed_call.binding_rung` is only ever `observed` or
`unresolved` -- so it needs no ranking of the four and invents no tiebreak.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, ObservedCall, ObservedShape, VendorChange
from sync.detect.status_rate import ERROR_RATE_THRESHOLD, MIN_STATUSED_CALLS
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


def _observe(store: GraphStore, spans: dict, trace_id: str = "t1", **over) -> None:
    fields = dict(
        repo_id="r", vendor_id="stripe", operation_id="GetCharges", binding_rung="observed",
        server_address="api.stripe.com", http_method="get", trace_id=trace_id,
        url_template="/v1/charges", spans=spans, first_seen=SEEN, last_seen=SEEN,
    )
    fields.update(over)
    store.record_observed_call(ObservedCall(**fields))


def _spans(count: int, target: str = "t", status: int | None = 200) -> dict:
    return {
        f"span{index}": {"target": target, "status": status, "resend": 0}
        for index in range(count)
    }


# The population a rate claim needs: enough statused calls to clear the floor, with the error
# count that lands the rate exactly on the threshold. Taken from the detector rather than
# written down, so a moved threshold moves these with it.
_FLOOR = MIN_STATUSED_CALLS
_AT_THRESHOLD = math.ceil(_FLOOR * ERROR_RATE_THRESHOLD)


def _statuses(total: int, errors: int) -> dict:
    """One span per status, distinct targets so nothing reads as a repeated request."""
    codes = [500] * errors + [200] * (total - errors)
    return {
        f"s{index}": {"target": f"target{index}", "status": code, "resend": 0}
        for index, code in enumerate(codes)
    }


# --- the deliverable: the query that attributes a finding to a rung -------------------


def test_a_persisted_finding_can_be_attributed_to_a_rung_by_one_column(store):
    """The query the rule exists for, written out. One column on one row -- no join, which is
    what `graph-grain.md` requires and what the shape has to make cheap."""
    site_id = _site(store)
    finding_id = store.insert_finding(
        Finding(
            detector="vendor_change", claim="c", call_site_id=site_id,
            severity="breaking", rationale="r", binding_rung="static",
        )
    )

    row = store._connect().execute(
        "SELECT binding_rung FROM finding WHERE id = %s", (finding_id,)
    ).fetchone()

    assert row["binding_rung"] == "static"


def test_findings_group_by_rung_without_touching_another_table(store):
    """The aggregate `sync.benchmark.binding` exists to produce. If this needed a join the
    shape would be wrong."""
    site_id = _site(store)
    for detector, rung in (("vendor_change", "static"), ("efficiency", "observed"),
                           ("status_rate", "unresolved")):
        store.insert_finding(
            Finding(
                detector=detector, claim="c", call_site_id=site_id,
                severity="info", rationale="r", binding_rung=rung,
            )
        )

    rows = store._connect().execute(
        "SELECT binding_rung, count(*) AS findings FROM finding GROUP BY binding_rung"
    ).fetchall()

    assert {row["binding_rung"]: row["findings"] for row in rows} == {
        "static": 1, "observed": 1, "unresolved": 1,
    }


def test_the_rung_survives_a_read_back_through_the_model(store):
    site_id = _site(store)
    store.insert_finding(
        Finding(
            detector="efficiency", claim="c", call_site_id=site_id,
            severity="info", rationale="r", binding_rung="unresolved",
        )
    )

    assert [f.binding_rung for f in store.open_findings()] == ["unresolved"]


# --- required on the model, defaulted only in the column -----------------------------


def test_a_finding_constructed_without_a_rung_says_it_was_never_attributed():
    """Defaulted rather than required, which is the weaker of the two positions and was chosen
    knowing it. Requiring the field would fail a forgetful detector at construction; `Finding` is
    exported from `sync.core`, which `CLAUDE.md` calls the published plugin SDK, so a required
    field breaks every detector a third party has written -- and inside this repository alone it
    cost 153 failures and 120 errors across 32 files.

    So the value a forgetful caller gets is at least honest -- `unattributed` says no binder
    claimed this. What closes the gap is that the value cannot be persisted: `insert_finding`
    refuses it, which is the section below. Constructing one is still allowed and still means
    nothing was attributed.
    """
    finding = Finding(
        detector="d", claim="c", call_site_id="cs", severity="info", rationale="r",
    )

    assert finding.binding_rung == "unattributed"


def test_unattributed_is_not_a_rung_a_binder_can_emit():
    """`BindingRung` describes what binders produce. `unattributed` is a fact about history --
    a row written before attribution existed -- so it stays out of that vocabulary while
    remaining readable on a `Finding`."""
    from sync.core import BindingRung

    assert "unattributed" not in getattr(BindingRung, "__args__", ())


def test_a_row_written_before_the_column_existed_reads_as_unattributed(store):
    """The default's only job. Simulated the way it actually happens: a row inserted without
    the column, which is what every row already in a deployed database is.
    """
    site_id = _site(store)
    store._connect().execute(
        """
        INSERT INTO finding (id, detector, claim, call_site_id, severity, rationale, status)
        VALUES ('legacy', 'vendor_change', 'c', %s, 'breaking', 'r', 'open')
        """,
        (site_id,),
    )

    row = store._connect().execute(
        "SELECT binding_rung FROM finding WHERE id = 'legacy'"
    ).fetchone()

    assert row["binding_rung"] == "unattributed"
    assert [f.binding_rung for f in store.open_findings()] == ["unattributed"]


# --- refused at the write, which is where the boundary is ----------------------------


def test_persisting_a_finding_that_names_no_rung_is_refused(store):
    """The enforcement the default leaves open, at the only place it can go.

    `CLAUDE.md` puts validation at boundaries -- user input, vendor responses, subprocess output
    -- and a write to Postgres is one; a Pydantic constructor inside our own detector is not.
    `sync.graph` is internal, so unlike the model no published contract is at stake here.

    Refused rather than warned. A warning in a pipeline log is the silent-wrong-answer failure
    this repository keeps finding: the row lands looking exactly like one written before the column
    existed, and nothing afterwards can tell the two apart -- so a detector added next month that
    forgets produces findings nobody can attribute, forever.
    """
    site_id = _site(store)
    forgetful = Finding(
        detector="a_detector_that_forgot", claim="c", call_site_id=site_id,
        severity="breaking", rationale="r",
    )

    with pytest.raises(ValueError, match="a_detector_that_forgot"):
        store.insert_finding(forgetful)


def test_the_refused_finding_leaves_no_row_behind(store):
    """A refusal that had already written would be worse than none: the row would be there,
    `unattributed`, and the exception would suggest it was not."""
    site_id = _site(store)

    with pytest.raises(ValueError):
        store.insert_finding(
            Finding(
                detector="another_forgetful_detector", claim="c", call_site_id=site_id,
                severity="breaking", rationale="r",
            )
        )

    row = store._connect().execute("SELECT count(*) AS findings FROM finding").fetchone()
    assert row["findings"] == 0


# --- what each detector attributes its findings to ----------------------------------


def test_vendor_change_findings_are_attributed_to_the_static_binding(store):
    """A wrong static binding makes the finding wrong, and nothing else is load-bearing."""
    from sync.detect.vendor_change import VendorChangeDetector

    site_id = _site(store, operation_id="PostCharges")
    store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/v1/charges", severity="breaking", source="oasdiff",
            raw={"id": "response-property-removed",
                 "text": "removed the optional property `data` from the response"},
        )
    )

    findings = list(VendorChangeDetector(store=store, vendor_id="stripe").scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"static"}
    assert site_id


def test_observed_drift_findings_are_attributed_to_the_static_binding(store):
    """The distinction that decides it: the binding is static, the evidence is observed. A
    correct binding meeting a surprising shape is the finding working, not a mis-binding.
    """
    from sync.detect.observed_drift import MIN_SAMPLES, ObservedDriftDetector

    store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create",
            args_keys=["amount"], response_fields_read=["data.surprise"],
            sdk_version="18.0.0", content_hash="h",
        )
    )
    store.record_observed_shape(
        ObservedShape(
            vendor_id="stripe", operation_id="PostCharges", field_path="/data/surprise",
            json_type="string", source="error-payload", sample_count=MIN_SAMPLES,
            first_seen=SEEN, last_seen=SEEN,
        )
    )

    # A spec that declares nothing for this operation, so the observed field is undescribed --
    # the claim this detector raises with no vendor change at all.
    findings = list(ObservedDriftDetector(store, spec={"PostCharges": []}).scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"static"}


def test_efficiency_findings_carry_the_correlation_s_own_rung(store):
    """A perfect static binding still yields a wrong finding if the span was correlated to the
    wrong operation, so the rung that matters is the correlator's."""
    from sync.detect.efficiency import EfficiencyDetector

    _site(store)
    _observe(store, _spans(30, target="same"), binding_rung="observed")

    findings = list(EfficiencyDetector(store=store, repo_id="r", vendor_id="stripe").scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"observed"}


def test_an_uncorrelated_efficiency_finding_says_unresolved_rather_than_observed(store):
    """`unresolved` is a real rung meaning no binding was established, and carrying it through
    is what lets the benchmark see a correlator's false positives at all."""
    from sync.detect.efficiency import EfficiencyDetector

    _site(store)
    _observe(store, _spans(30, target="same"), binding_rung="unresolved")

    findings = list(EfficiencyDetector(store=store, repo_id="r", vendor_id="stripe").scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"unresolved"}


def test_status_rate_findings_carry_the_correlation_s_own_rung(store):
    from sync.detect.status_rate import StatusRateDetector

    _site(store)
    _observe(store, _statuses(_FLOOR, _AT_THRESHOLD), binding_rung="observed")

    findings = list(StatusRateDetector(store=store, repo_id="r", vendor_id="stripe").scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"observed"}


def test_a_population_mixing_rungs_takes_the_weaker_one(store):
    """Two load-bearing bindings, so the weaker wins -- and inside this detector that is a
    two-value decision rather than a ranking of the four, because `observed_call.binding_rung`
    is only ever `observed` or `unresolved`. An `unresolved` span in the population is enough
    to make the finding's attribution honest about it.
    """
    from sync.detect.status_rate import StatusRateDetector

    _site(store)
    _observe(store, _statuses(_FLOOR, _AT_THRESHOLD), trace_id="t1", binding_rung="observed")
    _observe(store, _statuses(_FLOOR, _AT_THRESHOLD), trace_id="t2", binding_rung="unresolved")

    findings = list(StatusRateDetector(store=store, repo_id="r", vendor_id="stripe").scan())

    assert findings
    assert {f.binding_rung for f in findings} == {"unresolved"}


# --- the graph-grain Verify rule ----------------------------------------------------


def test_inserting_the_same_finding_twice_converges_on_one_row(store):
    """`graph-grain.md`: idempotence is a test, not an intention -- run the stage twice against
    one fixture and assert the row count and every row identity are unchanged. A column added
    to the identity by accident would show up here."""
    site_id = _site(store)
    finding = Finding(
        detector="vendor_change", claim="c", call_site_id=site_id,
        severity="breaking", rationale="r", binding_rung="static",
    )

    first = store.insert_finding(finding)
    second = store.insert_finding(finding)

    rows = store._connect().execute("SELECT id FROM finding").fetchall()
    assert first == second
    assert [row["id"] for row in rows] == [first]


def test_the_rung_is_not_part_of_a_finding_s_identity(store):
    """Two runs that disagree about the rung converge on one row rather than accumulating.

    The rung describes the binding a claim rested on, not which claim it is, so putting it in
    the key would make a correlator that improved from `unresolved` to `observed` write a
    second row for the same claim -- and every rate computed over the table would double-count
    exactly the findings whose attribution got better.
    """
    site_id = _site(store)
    base = dict(
        detector="efficiency", claim="c", call_site_id=site_id, severity="info", rationale="r",
    )

    first = store.insert_finding(Finding(**base, binding_rung="unresolved"))
    second = store.insert_finding(Finding(**base, binding_rung="observed"))

    assert first == second
    assert len(store._connect().execute("SELECT id FROM finding").fetchall()) == 1

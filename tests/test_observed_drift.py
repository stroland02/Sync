"""The detector that fires before anything breaks.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` places this after the shape
store for a reason: it asks what the vendor actually sent, and compares that against what the
vendor published. Specification diffing sees only what vendors announce, and error-triggered
tools see only what has already failed, so this is the one detector in the system with no
shipped competitor.

It is also the one most able to violate precision-over-recall, because traffic is noisy in ways
a specification is not. Most of what follows is therefore true negatives: the shapes that look
like drift and are not, and the divergences real enough to see but too thin to say anything
about.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, ObservedShape
from sync.core.protocols import Detector
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

OLD = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
NEW = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)

STATUS_DECLARED_STRING = DeclaredField(
    field_path="/data/status", json_types=frozenset({"string"}), required=True, nullable=False,
)


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def _site(store: GraphStore, reads=("data.status",), operation_id="PostCharges") -> str:
    return store.upsert_call_site(
        CallSite(
            repo_id="r", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id=operation_id, symbol="stripe.charges.create",
            args_keys=["amount"], response_fields_read=list(reads),
            sdk_version="18.0.0", content_hash="h",
        )
    )


def _observe(store: GraphStore, **over) -> None:
    fields = dict(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        json_type="string", source="replay", sample_count=MIN_SAMPLES,
        first_seen=NEW, last_seen=NEW,
    )
    fields.update(over)
    store.record_observed_shape(ObservedShape(**fields))


def _detector(store: GraphStore, declared=(STATUS_DECLARED_STRING,), operation_id="PostCharges"):
    return ObservedDriftDetector(store, spec={operation_id: list(declared)})


# --- observed versus specification: the case that exists nowhere else -------------


def test_a_type_the_specification_does_not_declare_is_a_finding(store: GraphStore):
    """The unpublished change. Stripe publishes `status` as a string; traffic says it is
    arriving as a number, and nobody announced it."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert "number" in findings[0].rationale
    assert "/data/status" in findings[0].rationale


def test_the_finding_addresses_the_call_site_that_reads_the_field(store: GraphStore):
    """A `Finding` is resolved back to a location by `call_site_id`. A drift finding that
    addressed an operation instead would be unroutable by everything downstream."""
    site_id = _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    findings = list(_detector(store).scan())

    assert [f.call_site_id for f in findings] == [site_id]
    assert findings[0].detector == "observed-drift"


def test_a_type_the_specification_declares_raises_nothing(store: GraphStore):
    """Agreement is the overwhelmingly common case and it has to be silent, or the detector is
    a report that the vendor exists."""
    _site(store)
    _observe(store, json_type="string")

    assert list(_detector(store).scan()) == []


def test_a_union_the_specification_declares_raises_nothing(store: GraphStore):
    """A field the specification declares as string-or-number is not drifting when traffic
    shows both. Reading only the first declared type would fire on every union in the API."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    declared = DeclaredField(
        field_path="/data/status", json_types=frozenset({"string", "number"}),
        required=True, nullable=False,
    )

    assert list(_detector(store, declared=(declared,)).scan()) == []


def test_a_null_where_the_specification_requires_a_value_is_a_finding(store: GraphStore):
    """The second half of the unpublished-change case: the type did not change, the vendor
    started omitting the value."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="null", nullable_seen=True, first_seen=NEW)

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert "null" in findings[0].rationale


def test_a_null_the_specification_allows_raises_nothing(store: GraphStore):
    """A nullable field arriving null is the specification being obeyed."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="null", nullable_seen=True, first_seen=NEW)

    declared = DeclaredField(
        field_path="/data/status", json_types=frozenset({"string"}), required=True, nullable=True,
    )

    assert list(_detector(store, declared=(declared,)).scan()) == []


def test_a_field_the_specification_does_not_describe_is_reported_as_an_addition(store: GraphStore):
    """A field in traffic that the specification never mentions. It breaks no consumer -- code
    cannot read what it does not know about -- so it is an addition, and it is exactly the
    evidence that the vendor shipped something they did not publish."""
    _site(store)
    _observe(store, json_type="string")
    _observe(store, field_path="/data/settlement_delay", json_type="number")

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert findings[0].severity == "addition"
    assert "/data/settlement_delay" in findings[0].rationale


# --- the sample floor -------------------------------------------------------------


def test_a_shape_below_the_sample_floor_is_silent(store: GraphStore):
    """A shape seen too few times is not a baseline, however large the divergence looks. One
    upstream incident, or one misbehaving account, produces a handful of responses that look
    exactly like a contract change."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW, sample_count=MIN_SAMPLES - 1)

    assert list(_detector(store).scan()) == []


def test_the_floor_admits_a_shape_that_reaches_it(store: GraphStore):
    """Pins which side of the comparison the boundary sits on. A floor asserted only from
    below is satisfied by a detector that never fires at all."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW, sample_count=MIN_SAMPLES)

    assert len(list(_detector(store).scan())) == 1


def test_the_floor_is_a_named_constant_a_caller_can_read():
    """The number is a policy, not an implementation detail: whoever tunes it needs to find it
    and whoever reads a finding needs to know what it was."""
    assert MIN_SAMPLES >= 30


# --- safe-miss over false-positive -------------------------------------------------


def test_a_drift_on_a_field_no_call_site_reads_is_silent(store: GraphStore):
    """The customer cannot be broken by a field their code never reads. Emitting anyway would
    spend a reviewer's attention on a change that cannot reach them."""
    _site(store, reads=("data.amount",))
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    assert list(_detector(store).scan()) == []


def test_an_operation_with_no_call_sites_raises_nothing(store: GraphStore):
    """Nothing in this repository calls the operation, so there is no location to address and
    nothing a patch could change."""
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    assert list(_detector(store).scan()) == []


def test_an_operation_the_specification_does_not_cover_is_skipped(store: GraphStore):
    """With nothing to compare against, every observed field would look undeclared and the
    detector would report the whole response as an unpublished change."""
    _site(store, operation_id="PostRefunds")
    _observe(store, operation_id="PostRefunds", json_type="number")

    assert list(_detector(store).scan()) == []


def test_a_field_the_code_reads_only_a_prefix_of_still_counts(store: GraphStore):
    """`result.data` leads into `/data/status`. The index records what the syntax writes, which
    is often shallower than the field that drifted, and requiring an exact match would miss
    almost every real call site."""
    _site(store, reads=("data",))
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    assert len(list(_detector(store).scan())) == 1


# --- observed now versus observed before: enrichment, never a trigger --------------


def test_a_shift_between_windows_the_specification_agrees_with_raises_nothing(store: GraphStore):
    """The constraint the spec is explicit about. Both shapes are declared, so the baseline
    moving between windows is not a finding on its own -- it is only ever enrichment of a
    divergence found against the specification."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD, last_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW, last_seen=NEW)

    declared = DeclaredField(
        field_path="/data/status", json_types=frozenset({"string", "number"}),
        required=True, nullable=False,
    )

    assert list(_detector(store, declared=(declared,)).scan()) == []


def test_a_divergence_the_earlier_window_contradicts_is_the_stronger_finding(store: GraphStore):
    """The field was a string first and is a number now, so the specification is not merely
    inaccurate -- the vendor's behaviour changed. That is what the detector exists to catch and
    the severity says so."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)

    assert list(_detector(store).scan())[0].severity == "breaking"


def test_a_long_standing_mismatch_is_reported_as_information(store: GraphStore):
    """No earlier window shows this field behaving differently, so the likeliest explanation is
    that the specification was always wrong rather than that anything changed. Same divergence,
    weaker claim, and the severity is the only place that distinction can live."""
    _site(store)
    _observe(store, json_type="number", first_seen=OLD)

    findings = list(_detector(store).scan())

    assert len(findings) == 1
    assert findings[0].severity == "info"


# --- what the finding rests on -----------------------------------------------------


def test_an_earlier_sighting_of_the_same_shape_is_not_a_contradiction(store: GraphStore):
    """One field, one divergent type, two sources. The older row does not contradict the newer
    one -- it agrees with it -- so nothing here says the vendor changed anything, and reading
    "there is an older row" as "the behaviour changed" would report every long-standing
    mismatch as breaking the moment a second source saw it.
    """
    _site(store)
    _observe(store, json_type="number", first_seen=OLD, source="replay")
    _observe(store, json_type="number", first_seen=NEW, source="error-payload")

    assert {f.severity for f in _detector(store).scan()} == {"info"}


def test_the_rationale_reports_the_evidence_and_its_limit(store: GraphStore):
    """`parameter_deprecation` says out loud that it did not resolve the model scope. This one
    says the divergence is an observation of a sample, not a statement the vendor made, because
    a reviewer deciding whether to act needs to know which of those they are holding."""
    _site(store)
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW, sample_count=61, source="error-payload")

    rationale = list(_detector(store).scan())[0].rationale

    assert "61" in rationale
    assert "error-payload" in rationale
    assert "observed" in rationale.lower()


def test_the_detector_satisfies_the_detector_protocol(store: GraphStore):
    """Everything downstream consumes detectors through the protocol, not through this class."""
    assert isinstance(_detector(store), Detector)


def test_two_claims_about_one_call_site_survive_being_stored(store: GraphStore):
    """Two fields of one response are two claims, and must be two rows.

    The graph derives a finding's id from its identity fields and inserts ON CONFLICT DO
    NOTHING, so two findings the key cannot tell apart are one row and nobody is told which
    was dropped. This detector is the case needing no assumption about reachability: it has
    two independent yield sites for one loop -- a field the specification never described, and
    a field whose shape drifted -- and a response carrying both produces two facts about one
    call site.
    """
    _site(store, reads=("data.status", "data.extra"))
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)
    _observe(store, field_path="/data/extra", json_type="string")

    findings = list(_detector(store).scan())
    assert len(findings) >= 2, "the case must produce two claims or this proves nothing"

    for finding in findings:
        store.insert_finding(finding)

    assert len(store.open_findings()) == len(findings)


def test_two_undescribed_fields_on_one_call_site_are_two_rows(store: GraphStore):
    """The field path is what carries identity here, and this is what proves it.

    `test_two_claims_about_one_call_site_survive_being_stored` uses one undescribed field and
    one drift, so it passes even if the claim names only which of the two yield sites emitted
    it -- mutation testing established that. Two undescribed fields are the case that does not:
    they come from one yield site, and only the path tells them apart.
    """
    _site(store, reads=("data.status",))
    _observe(store, field_path="/data/first", json_type="string")
    _observe(store, field_path="/data/second", json_type="string")

    findings = list(_detector(store).scan())
    assert len(findings) == 2

    for finding in findings:
        store.insert_finding(finding)

    assert len(store.open_findings()) == 2


def test_the_claim_says_which_of_the_two_things_this_detector_found(store: GraphStore):
    """A field path can produce one kind of claim or the other and never both, so the prefix
    carries no identity -- which is exactly why it needs pinning somewhere.

    `claim` is a column, and a query asking how much of this detector's output is unannounced
    additions rather than shapes contradicting the specification reads it. A prefix that named
    the wrong one would answer that question wrongly and break nothing else.
    """
    _site(store, reads=("data.status",))
    _observe(store, json_type="string", first_seen=OLD)
    _observe(store, json_type="number", first_seen=NEW)
    _observe(store, field_path="/data/extra", json_type="string")

    claims = sorted(f.claim for f in _detector(store).scan())

    assert claims == ["shape-drift:/data/status", "undescribed-field:/data/extra"]

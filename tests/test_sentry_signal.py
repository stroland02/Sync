"""The first link in the chain: an error payload becomes shape rows.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` names three sources feeding
the shape store, ascending in cost. This is the cheapest one -- error payloads are already
captured, cost the customer nothing, and need no SDK install -- and it is the most biased, since
a baseline assembled from failures is not a baseline of normal traffic.

The privacy rule is the point of the whole store, so it is tested rather than commented. The
fixture is deliberately stuffed with values that must never reach a column: an amount, a name, an
email, a card token, vendor identifiers, a free-text description.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.graph.store import GraphStore
from sync.signals.sentry import ARRAY_ELEMENT, SentryShapeReader

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "sentry"

SENSITIVE = [
    "ch_3NpqR2eZvKYlo2C41gK3TQzr",
    "cus_NffrFeUfNV2Hib",
    "tok_1NpqR2eZvKYlo2CsecretXYZ",
    "Ada Lovelace",
    "ada@example.com",
    "Analytical Engine",
    "4242",
    "4999",
]


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def event():
    return json.loads((FIXTURES / "stripe_charge_error.json").read_text(encoding="utf-8"))


def _resolve(method: str, url: str) -> str | None:
    """Stands in for the vendor adapter that maps a request to an operation."""
    if method == "POST" and url.endswith("/v1/charges"):
        return "PostCharges"
    return None


def _reader(store: GraphStore, **over) -> SentryShapeReader:
    kwargs = dict(store=store, vendor_id="stripe", resolve_operation=_resolve)
    kwargs.update(over)
    return SentryShapeReader(**kwargs)


def _paths(store: GraphStore) -> dict[str, str]:
    return {row.field_path: row.json_type for row in store.observed_shapes("stripe", "PostCharges")}


# --- the walk ---------------------------------------------------------------------


def test_a_payload_becomes_rows(store: GraphStore, event):
    assert _reader(store).ingest(event) > 0
    assert store.observed_shapes("stripe", "PostCharges") != []


def test_every_scalar_is_recorded_with_its_json_type(store: GraphStore, event):
    _reader(store).ingest(event)
    paths = _paths(store)

    assert paths["/status"] == "string"
    assert paths["/amount"] == "number"
    assert paths["/paid"] == "boolean"


def test_a_nested_object_is_addressed_by_json_pointer(store: GraphStore, event):
    """Depth is the whole reason field_path is a pointer rather than a name. `status` alone
    would collide with the status inside every refund."""
    _reader(store).ingest(event)

    assert _paths(store)["/payment_method_details/card/brand"] == "string"


def test_containers_are_recorded_as_well_as_their_leaves(store: GraphStore, event):
    """A field the specification declares an object and traffic sends as an array is drift, and
    the detector can only see it if the container itself carries a type."""
    paths = _reader(store).ingest(event) and _paths(store)

    assert paths["/customer"] == "object"
    assert paths["/refunds/data"] == "array"


def test_a_null_is_recorded_as_null_and_as_nullable(store: GraphStore, event):
    """`failure_code` is null on this payload. The detector's second comparison is a field
    arriving null where the specification requires a value, so this has to survive."""
    _reader(store).ingest(event)
    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}

    assert rows["/failure_code"].json_type == "null"
    assert rows["/failure_code"].nullable_seen is True


def test_the_source_says_the_rows_came_from_an_error(store: GraphStore, event):
    """`source` is in the table's natural key precisely so a failure-biased sample cannot be
    merged into one drawn from normal traffic."""
    _reader(store).ingest(event)

    assert {r.source for r in store.observed_shapes("stripe", "PostCharges")} == {"error-payload"}


def test_a_key_containing_a_slash_is_escaped(store: GraphStore):
    """RFC 6901: `/` becomes `~1` and `~` becomes `~0`. Unescaped, a key containing a slash
    produces a pointer indistinguishable from a nested field, and the detector would compare it
    against a declared field that does not exist."""
    _reader(store).ingest(_event({"a/b": 1, "c~d": 2}))
    paths = _paths(store)

    assert "/a~1b" in paths
    assert "/c~0d" in paths


# --- arrays, which is the part that goes wrong ------------------------------------


def test_array_elements_collapse_to_one_path(store: GraphStore, event):
    """Two refunds in this payload. Addressing them by index would make `/refunds/data/0/status`
    and `/refunds/data/1/status` two different fields, so a response carrying three refunds
    tomorrow would look like a brand new field appearing and the one carrying one would look
    like a field disappearing. Every array in the API would read as drift on every observation.
    """
    _reader(store).ingest(event)
    paths = _paths(store)

    assert f"/refunds/data/{ARRAY_ELEMENT}/status" in paths
    assert not [p for p in paths if "/0/" in p or "/1/" in p]


def test_an_array_of_ten_identical_elements_counts_once(store: GraphStore):
    """`sample_count` is evidence that a shape is established, and the detector's floor rests on
    it. One response carrying a fifty-element array would clear a floor of thirty by itself,
    which is exactly the noise the floor exists to exclude, so a payload contributes at most one
    observation per distinct shape."""
    _reader(store).ingest(_event({"data": [{"status": "ok"} for _ in range(10)]}))

    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}
    assert rows[f"/data/{ARRAY_ELEMENT}/status"].sample_count == 1


def test_elements_that_genuinely_differ_are_kept_apart(store: GraphStore):
    """Collapsing the index must not collapse the shapes. One refund whose `reason` is a string
    and another whose `reason` is null are two observations of one path, and flattening them to
    one would hide the nullability the detector is looking for."""
    _reader(store).ingest(_event({"data": [{"reason": "duplicate"}, {"reason": None}]}))

    types = {
        r.json_type
        for r in store.observed_shapes("stripe", "PostCharges")
        if r.field_path == f"/data/{ARRAY_ELEMENT}/reason"
    }
    assert types == {"string", "null"}


def test_an_empty_array_still_records_the_container(store: GraphStore):
    """An array that is empty in this sample is not an absent field. Recording nothing would let
    a field vanish from the baseline because one response happened to carry no elements."""
    _reader(store).ingest(_event({"data": []}))

    assert _paths(store)["/data"] == "array"


# --- the privacy rule -------------------------------------------------------------


def test_no_value_from_the_payload_reaches_a_row(store: GraphStore, event):
    """Asserted against the serialised rows, so a future column cannot smuggle a value in
    without failing here. The fixture carries a card token, a customer id, a name, an email, an
    amount and a free-text description; none of them is a shape."""
    _reader(store).ingest(event)
    serialised = " ".join(r.model_dump_json() for r in store.observed_shapes("stripe", "PostCharges"))

    for secret in SENSITIVE:
        assert secret not in serialised, f"{secret} crossed the extraction boundary"


def test_an_enum_the_specification_publishes_is_retained(store: GraphStore, event):
    """A vendor enum is public data, and it is what lets the baseline say which members traffic
    exercises. The decision is `ObservedShape.from_observation`'s, not this module's."""
    _reader(store, spec_enums={"PostCharges": {"/status": ["requires_action", "succeeded"]}}).ingest(event)

    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}
    assert rows["/status"].spec_enum_values == ["requires_action"]


def test_an_unpublished_value_at_a_field_with_an_enum_is_still_discarded(store: GraphStore, event):
    """The published list is the rule, not "this field is enum-shaped". `description` here is
    free text and stays out even when the caller supplies an enum for a different field."""
    _reader(store, spec_enums={"PostCharges": {"/description": ["a", "b"]}}).ingest(event)

    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}
    assert rows["/description"].spec_enum_values == []


def test_nothing_is_retained_when_the_caller_supplies_no_specification(store: GraphStore, event):
    """The safe default. A reader wired up without the published enums retains no values at
    all rather than guessing which strings look public."""
    _reader(store).ingest(event)

    assert all(r.spec_enum_values == [] for r in store.observed_shapes("stripe", "PostCharges"))


# --- payloads that are not what they claim to be ----------------------------------


def _event(body, url="https://api.stripe.com/v1/charges", method="POST", timestamp=None):
    event = {
        "event_id": "e" * 32,
        "request": {"url": url, "method": method},
        "contexts": {"response": {"type": "response", "status_code": 402, "data": body}},
    }
    if timestamp is not None:
        event["timestamp"] = timestamp
    return event


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param({}, id="empty"),
        pytest.param({"request": {"url": "u", "method": "POST"}}, id="no-response-context"),
        pytest.param({"contexts": {"response": {"data": {"a": 1}}}}, id="no-request"),
        pytest.param(_event(body=None), id="null-body"),
        pytest.param(_event(body="a string, not an object"), id="scalar-body"),
        pytest.param({"contexts": "not-a-mapping", "request": 7}, id="wrong-types"),
    ],
)
def test_a_malformed_payload_records_nothing_and_does_not_raise(store: GraphStore, malformed):
    """This reads data a third party produced. One bad event must not stop the rest of a batch
    being read, so it yields no rows instead of an exception."""
    assert _reader(store).ingest(malformed) == 0
    assert store.observed_shapes("stripe", "PostCharges") == []


def test_a_malformed_payload_is_logged_rather_than_swallowed(store: GraphStore, caplog):
    """Silence on one bad payload is correct; silence on all of them is a signal source that
    quietly stopped working, which looks identical to a vendor who changed nothing."""
    with caplog.at_level(logging.WARNING, logger="sync.signals.sentry"):
        _reader(store).ingest({"contexts": {"response": {"data": {"a": 1}}}})

    assert caplog.records != []


def test_the_log_line_carries_no_payload_content(store: GraphStore, caplog):
    """A log file is a column with worse access control. The reason a payload was rejected is
    diagnostic; its contents are the thing this module exists to discard."""
    with caplog.at_level(logging.WARNING, logger="sync.signals.sentry"):
        _reader(store).ingest(_event(body="tok_1NpqR2eZvKYlo2CsecretXYZ"))

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert logged != "", "a rejected payload has to log something for this to be worth asserting"
    assert "tok_1NpqR2eZvKYlo2CsecretXYZ" not in logged


def test_an_operation_the_resolver_cannot_name_records_nothing(store: GraphStore):
    """Guessing the operation would file every unrecognised URL's shapes under whatever
    operation happened to be nearest, and a baseline attributed to the wrong operation produces
    findings against fields that operation never returns."""
    assert _reader(store).ingest(_event({"a": 1}, url="https://api.stripe.com/v1/refunds")) == 0


# --- when it happened -------------------------------------------------------------


def test_the_event_timestamp_becomes_the_observation_window(store: GraphStore, event):
    """An error payload is forwarded long after the response arrived, and the drift detector
    decides severity by asking which shape was seen first. Stamping ingestion time would make
    every backfilled batch look like the newest behaviour the vendor has."""
    _reader(store).ingest(event)

    row = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}["/status"]
    assert row.first_seen == datetime(2026, 7, 20, 9, 15, 30, tzinfo=timezone.utc)


def test_an_unreadable_timestamp_does_not_lose_the_payload(store: GraphStore):
    """The timestamp is metadata about the observation, not the observation. A payload whose
    timestamp is missing or malformed still carries shapes worth having."""
    assert _reader(store).ingest(_event({"a": 1}, timestamp="not-a-timestamp")) > 0

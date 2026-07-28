"""A Datadog search response becomes shape rows, the same way a Sentry event does.

`docs/superpowers/specs/2026-07-25-sync-competitive-position.md` sequences Sentry and Datadog as
the M2 signal sources and is explicit that Sync must not build OTLP ingestion: competing with
Datadog on telemetry infrastructure is a losing position, joining against the graph is not. So
this reads what Datadog already holds. It receives nothing, and no test here touches a network.

The privacy rule is the point of the store, so it is tested rather than commented. The fixture is
deliberately stuffed with values that must never reach a column: an amount, a name, an email, a
card token, vendor identifiers and a free-text description.

Two sources now write `source='error-payload'`, which is one row rather than two -- see
`test_two_error_shaped_sources_land_on_one_row`, which pins that consequence rather than leaving
it to be discovered from a count that looks like corroboration and is not.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.graph.store import GraphStore
from sync.signals.datadog import ARRAY_ELEMENT, DatadogShapeReader
from sync.signals.sentry import ARRAY_ELEMENT as SENTRY_ARRAY_ELEMENT

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "datadog"

SENSITIVE = [
    "ch_3NpqR2eZvKYlo2C41gK3TQzr",
    "cus_NffrFeUfNV2Hib",
    "tok_1NpqR2eZvKYlo2CsecretXYZ",
    "Ada Lovelace",
    "ada@example.com",
    "Analytical Engine",
    "4242",
    "4999",
    "web-01.prod",
    "billing-api",
]


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def payload():
    return json.loads((FIXTURES / "stripe_charge_error.json").read_text(encoding="utf-8"))


def _resolve(method: str, url: str) -> str | None:
    """Stands in for the vendor adapter that maps a request to an operation."""
    if method == "POST" and url.endswith("/v1/charges"):
        return "PostCharges"
    return None


def _reader(store: GraphStore, **over) -> DatadogShapeReader:
    kwargs = dict(store=store, vendor_id="stripe", resolve_operation=_resolve)
    kwargs.update(over)
    return DatadogShapeReader(**kwargs)


def _paths(store: GraphStore) -> dict[str, str]:
    return {row.field_path: row.json_type for row in store.observed_shapes("stripe", "PostCharges")}


def _log(body, url="https://api.stripe.com/v1/charges", method="POST", timestamp="2026-07-20T09:15:30.000Z"):
    """One record in the shape Datadog's log search API returns."""
    return {
        "id": "AQAAAYyLmVvBqNKlEw",
        "type": "log",
        "attributes": {
            "status": "error",
            "timestamp": timestamp,
            "attributes": {
                "http": {
                    "method": method,
                    "url": url,
                    "status_code": 402,
                    "response": {"body": body},
                }
            },
        },
    }


def _response(*records):
    """A whole search response. Datadog answers a page of records, not one event."""
    return {"data": list(records), "meta": {"status": "done"}, "links": {}}


# --- the walk ---------------------------------------------------------------------


def test_a_payload_becomes_rows(store: GraphStore, payload):
    assert _reader(store).ingest(payload) > 0
    assert store.observed_shapes("stripe", "PostCharges") != []


def test_every_scalar_is_recorded_with_its_json_type(store: GraphStore, payload):
    _reader(store).ingest(payload)
    paths = _paths(store)

    assert paths["/status"] == "string"
    assert paths["/amount"] == "number"
    assert paths["/paid"] == "boolean"


def test_the_pointer_is_rooted_at_the_response_body_not_at_the_datadog_envelope(
    store: GraphStore, payload
):
    """The field paths have to name fields of the vendor's response, because that is what the
    specification the detector compares against declares. Rooting them at the search response
    would produce `/data/-/attributes/attributes/http/response/body/status`, which no
    specification declares and which would additionally file Datadog's own envelope fields --
    `service`, `host`, `tags` -- as if the vendor had sent them.
    """
    _reader(store).ingest(payload)
    paths = _paths(store)

    assert "/payment_method_details/card/brand" in paths
    assert not [p for p in paths if p.startswith("/data/") or "attributes" in p]
    assert "/service" not in paths
    assert "/tags" not in paths


def test_containers_are_recorded_as_well_as_their_leaves(store: GraphStore, payload):
    """A field the specification declares an object and traffic sends as an array is drift, and
    the detector can only see it if the container itself carries a type."""
    _reader(store).ingest(payload)
    paths = _paths(store)

    assert paths["/customer"] == "object"
    assert paths["/refunds/data"] == "array"


def test_a_null_is_recorded_as_null_and_as_nullable(store: GraphStore, payload):
    """The detector's second comparison is a field arriving null where the specification
    requires a value, so this has to survive the reduction."""
    _reader(store).ingest(payload)
    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}

    assert rows["/failure_code"].json_type == "null"
    assert rows["/failure_code"].nullable_seen is True


def test_the_source_says_the_rows_came_from_an_error(store: GraphStore, payload):
    _reader(store).ingest(payload)

    assert {r.source for r in store.observed_shapes("stripe", "PostCharges")} == {"error-payload"}


# --- a page of records, which is what Datadog returns -------------------------------


def test_every_record_in_one_response_is_read(store: GraphStore):
    """Datadog answers a search with a page of records where Sentry forwards one event. Reading
    only the first would silently discard most of a batch, and the loss would look like a vendor
    that sends fewer fields rather than like a reader that stopped early.
    """
    _reader(store).ingest(_response(_log({"first": 1}), _log({"second": 2})))
    paths = _paths(store)

    assert "/first" in paths
    assert "/second" in paths


def test_one_bad_record_does_not_cost_the_others(store: GraphStore):
    """The reason this reads a page rather than an event. A batch is third-party data and one
    record that is not what it claims to be must not take the rest of the page with it."""
    _reader(store).ingest(_response(_log({"first": 1}), {"attributes": "not-a-mapping"}, _log({"third": 3})))
    paths = _paths(store)

    assert "/first" in paths
    assert "/third" in paths


# --- arrays, where two sources have to agree ----------------------------------------


def test_array_elements_collapse_to_the_same_token_sentry_uses(store: GraphStore, payload):
    """Two modules feed one table, so the array token is not this module's decision to make.
    Indexing would make array position part of a field's identity: a response carrying three
    refunds tomorrow would read as new fields appearing and one carrying a single element as
    fields disappearing.
    """
    assert ARRAY_ELEMENT == SENTRY_ARRAY_ELEMENT

    _reader(store).ingest(payload)
    paths = _paths(store)

    assert f"/refunds/data/{ARRAY_ELEMENT}/status" in paths
    assert not [p for p in paths if "/0/" in p or "/1/" in p]


def test_the_walk_is_sentrys_rather_than_a_second_copy_of_it(store: GraphStore, monkeypatch):
    """Equal constants are not the same decision. Two modules that agree today can drift, and a
    `-` in one against a `0` in the other would make the same field look like drift depending on
    which source happened to observe it -- with nothing failing, because each module's own tests
    would still pass.

    Asserting equality cannot catch that: CPython interns `"-"`, so a copied literal compares
    identical too. Repointing Sentry's constant and watching this reader's output move is what
    actually distinguishes sharing the decision from duplicating it.
    """
    from sync.signals.sentry import shapes as sentry_shapes

    monkeypatch.setattr(sentry_shapes, "ARRAY_ELEMENT", "@@")
    _reader(store).ingest(_response(_log({"data": [{"status": "ok"}]})))

    assert "/data/@@/status" in _paths(store)


def test_an_array_of_ten_identical_elements_counts_once(store: GraphStore):
    """`sample_count` is evidence a shape is established and the detector's floor rests on it.
    One response carrying a fifty-element array would clear a floor of thirty by itself."""
    _reader(store).ingest(_response(_log({"data": [{"status": "ok"} for _ in range(10)]})))

    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}
    assert rows[f"/data/{ARRAY_ELEMENT}/status"].sample_count == 1


def test_elements_that_genuinely_differ_are_kept_apart(store: GraphStore):
    """Collapsing the index must not collapse the shapes. One refund whose `reason` is a string
    and another whose `reason` is null are two observations of one path."""
    _reader(store).ingest(_response(_log({"data": [{"reason": "duplicate"}, {"reason": None}]})))

    types = {
        r.json_type
        for r in store.observed_shapes("stripe", "PostCharges")
        if r.field_path == f"/data/{ARRAY_ELEMENT}/reason"
    }
    assert types == {"string", "null"}


def test_a_key_containing_a_slash_is_escaped(store: GraphStore):
    """RFC 6901: `/` becomes `~1` and `~` becomes `~0`. Unescaped, a key containing a slash
    produces a pointer indistinguishable from a nested field."""
    _reader(store).ingest(_response(_log({"a/b": 1, "c~d": 2})))
    paths = _paths(store)

    assert "/a~1b" in paths
    assert "/c~0d" in paths


# --- the privacy rule ---------------------------------------------------------------


def test_no_value_from_the_payload_reaches_a_row(store: GraphStore, payload):
    """Asserted against the serialised rows, so a future column cannot smuggle a value in
    without failing here. Datadog's envelope is checked too: `service`, `host` and the tag list
    identify the customer's own infrastructure and are not shape either.
    """
    _reader(store).ingest(payload)
    serialised = " ".join(r.model_dump_json() for r in store.observed_shapes("stripe", "PostCharges"))

    for secret in SENSITIVE:
        assert secret not in serialised, f"{secret} crossed the extraction boundary"


def test_an_enum_the_specification_publishes_is_retained(store: GraphStore, payload):
    """A vendor enum is public data. The decision belongs to `ObservedShape.from_observation`,
    which both readers call rather than each deciding retention for itself."""
    _reader(store, spec_enums={"PostCharges": {"/status": ["requires_action", "succeeded"]}}).ingest(payload)

    rows = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}
    assert rows["/status"].spec_enum_values == ["requires_action"]


def test_nothing_is_retained_when_the_caller_supplies_no_specification(store: GraphStore, payload):
    """The safe default. A reader wired up without the published enums retains no values at all
    rather than guessing which strings look public."""
    _reader(store).ingest(payload)

    assert all(r.spec_enum_values == [] for r in store.observed_shapes("stripe", "PostCharges"))


# --- payloads that are not what they claim to be ------------------------------------


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param({}, id="empty"),
        pytest.param({"data": "not-a-list"}, id="data-not-a-list"),
        pytest.param(_response({"type": "log"}), id="no-attributes"),
        pytest.param(_response(_log(body=None)), id="null-body"),
        pytest.param(_response(_log(body="a string, not an object")), id="scalar-body"),
        pytest.param(_response({"attributes": {"attributes": {"http": {}}}}), id="no-method-or-url"),
        pytest.param({"data": [7, "x", None]}, id="records-that-are-not-mappings"),
    ],
)
def test_a_malformed_payload_records_nothing_and_does_not_raise(store: GraphStore, malformed):
    """This reads data a third party produced. One bad response must not stop a batch being
    read, so it yields no rows instead of an exception."""
    assert _reader(store).ingest(malformed) == 0
    assert store.observed_shapes("stripe", "PostCharges") == []


@pytest.mark.parametrize(
    "rejected",
    [
        pytest.param(_response({"type": "log"}), id="no-attributes"),
        pytest.param(_response(_log(body="a string, not an object")), id="scalar-body"),
        pytest.param(_response({"attributes": {"attributes": {"http": {}}}}), id="no-method-or-url"),
        pytest.param({"data": "not-a-list"}, id="page-that-is-not-a-list"),
    ],
)
def test_a_malformed_payload_is_logged_rather_than_swallowed(store: GraphStore, caplog, rejected):
    """Silence on one bad payload is correct; silence on all of them is a signal source that
    quietly stopped working, which looks identical to a vendor who changed nothing.

    Parametrised over each reason a record is rejected, because the row count does not
    distinguish them: a scalar body and a record with no method both yield nothing whether the
    guard that names them is there or not -- `walk` yields nothing for a scalar and the resolver
    declines a `None` url. The log line is the only observable difference between rejecting a
    record deliberately and falling through to zero rows by accident.
    """
    with caplog.at_level(logging.WARNING, logger="sync.signals.datadog"):
        _reader(store).ingest(rejected)

    assert caplog.records != []


def test_the_log_line_carries_no_payload_content(store: GraphStore, caplog):
    """A log file is a column with worse access control. The reason a record was rejected is
    diagnostic; its contents are the thing this module exists to discard."""
    with caplog.at_level(logging.WARNING, logger="sync.signals.datadog"):
        _reader(store).ingest(_response(_log(body="tok_1NpqR2eZvKYlo2CsecretXYZ")))

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert logged != "", "a rejected record has to log something for this to be worth asserting"
    assert "tok_1NpqR2eZvKYlo2CsecretXYZ" not in logged


def test_an_operation_the_resolver_cannot_name_records_nothing(store: GraphStore):
    """Most requests in a customer's Datadog account are not this vendor's. Guessing the
    operation would file their shapes under whatever operation happened to be nearest, and a
    baseline attributed to the wrong operation produces findings against fields that operation
    never returns."""
    assert _reader(store).ingest(_response(_log({"a": 1}, url="https://api.stripe.com/v1/refunds"))) == 0


# --- when it happened ---------------------------------------------------------------


def test_the_record_timestamp_becomes_the_observation_window(store: GraphStore, payload):
    """A log is searched long after the response arrived, and the drift detector decides
    severity by asking which shape was seen first. Stamping ingestion time would make every
    backfilled page look like the newest behaviour the vendor has."""
    _reader(store).ingest(payload)

    row = {r.field_path: r for r in store.observed_shapes("stripe", "PostCharges")}["/status"]
    assert row.first_seen == datetime(2026, 7, 20, 9, 15, 30, tzinfo=timezone.utc)


def test_an_unreadable_timestamp_does_not_lose_the_record(store: GraphStore):
    """The timestamp is metadata about the observation, not the observation."""
    assert _reader(store).ingest(_response(_log({"a": 1}, timestamp="not-a-timestamp"))) > 0


# --- what two error-shaped sources do to one baseline --------------------------------


def test_two_error_shaped_sources_land_on_one_row(store: GraphStore):
    """`source` is in the natural key so a biased sample cannot merge into an unbiased one. Both
    readers write `error-payload`, so this reader merges with Sentry's rather than sitting
    beside it: the counts add and the row cannot say which source contributed.

    That is the right key -- both samples are drawn from failures and neither corrects the
    other's bias -- but it means `sample_count` reaching the detector's floor is not evidence of
    corroboration across independent sources. Two views of the same failure population clear the
    floor faster without making the baseline any more representative of normal traffic. Pinned
    here so a reading of the counts as agreement has to argue with a test.
    """
    from sync.signals.sentry import SentryShapeReader

    sentry = SentryShapeReader(store=store, vendor_id="stripe", resolve_operation=_resolve)
    sentry.ingest(
        {
            "event_id": "e" * 32,
            "request": {"url": "https://api.stripe.com/v1/charges", "method": "POST"},
            "contexts": {"response": {"data": {"status": "requires_action"}}},
        }
    )
    _reader(store).ingest(_response(_log({"status": "requires_action"})))

    rows = [r for r in store.observed_shapes("stripe", "PostCharges") if r.field_path == "/status"]
    assert len(rows) == 1
    assert rows[0].sample_count == 2

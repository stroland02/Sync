"""The baseline that cannot be backfilled.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` declares this table and
calls its schema binding now, before the detector that reads it exists, for one reason: every
response seen before the store exists is a baseline sample permanently lost. Same argument, same
urgency, as the migration corpus.

The privacy rule is the point of the table, so it is tested rather than commented. Shapes are
recorded -- paths, JSON types, nullability, counts. A value is retained only when the vendor's
published specification names it, because a vendor enum is public data and a customer's string
is not.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from sync.core.models import ObservedShape
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

STATUS_ENUM = ["succeeded", "requires_action", "canceled"]


def _shape(**over) -> ObservedShape:
    fields = dict(
        vendor_id="stripe",
        operation_id="PostCharges",
        field_path="/data/status",
        json_type="string",
        source="error-payload",
    )
    fields.update(over)
    return ObservedShape(**fields)


# --- the reduction, which is what replaces the value ------------------------------


def test_a_value_becomes_its_json_type():
    """The type is the observation. `cus_NffrFeUfNV2Hib` is a customer identifier and never
    reaches a column; `string` is what the baseline actually needs."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/customer",
        value="cus_NffrFeUfNV2Hib", source="replay",
    )

    assert shape.json_type == "string"
    assert shape.spec_enum_values == []


@pytest.mark.parametrize(
    "value, expected",
    [
        ("succeeded", "string"),
        (4999, "number"),
        (12.5, "number"),
        (True, "boolean"),
        ({"id": 1}, "object"),
        ([1, 2], "array"),
        (None, "null"),
    ],
)
def test_every_json_type_is_recognised(value, expected):
    """`True` is the one that bites: `bool` is a subclass of `int` in Python, so a type check
    ordered wrongly records every boolean as a number and the baseline quietly disagrees with
    the specification about a type it never saw change."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/x",
        value=value, source="replay",
    )

    assert shape.json_type == expected


def test_a_null_observation_records_nullability_rather_than_a_value():
    """A field arriving null where the specification marks it required is one of the two
    findings the detector is specified to emit, so nullability has to survive the reduction."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        value=None, source="replay",
    )

    assert shape.nullable_seen is True
    assert shape.json_type == "null"


def test_a_present_value_is_not_marked_nullable():
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        value="succeeded", source="replay",
    )

    assert shape.nullable_seen is False


# --- the enum rule: public data only ----------------------------------------------


def test_an_enum_value_the_specification_publishes_is_retained():
    """`succeeded` is in Stripe's published specification. It is public data, it is what makes
    the baseline able to say which enum members traffic actually exercises, and retaining it
    costs nothing under the threat model."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        value="succeeded", source="replay", spec_enum_values=STATUS_ENUM,
    )

    assert shape.spec_enum_values == ["succeeded"]


def test_a_value_the_specification_does_not_publish_is_discarded():
    """The rule is not "retain short strings" or "retain strings that look like enums". It is
    membership in the published specification, decided by the specification, because that is
    the only test that cannot be talked into keeping a customer's data."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        value="cus_NffrFeUfNV2Hib", source="replay", spec_enum_values=STATUS_ENUM,
    )

    assert shape.spec_enum_values == []


def test_the_published_members_that_were_not_observed_are_not_invented():
    """The column records what was seen and published, not the whole published enum. A baseline
    claiming to have observed `canceled` when nothing ever sent it would be a fabricated
    observation, and the detector's comparisons rest on this column meaning what it says."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/status",
        value="succeeded", source="replay", spec_enum_values=STATUS_ENUM,
    )

    assert "canceled" not in shape.spec_enum_values


def test_a_number_is_not_retained_even_when_the_published_enum_names_it():
    """OpenAPI enums can be numeric, so this is a real case rather than a hypothetical, and
    `1 in [1]` is true in Python -- a membership test alone would retain it. The column is
    `text[]`, and how a numeric member should be spelled in it is a decision the specification
    does not make, so retention is a string rule until something makes it.
    """
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges", field_path="/data/attempt",
        value=1, source="replay", spec_enum_values=[1],
    )

    assert shape.spec_enum_values == []


def test_no_free_form_value_reaches_the_row():
    """Asserted against the rows' own serialised form, so a future column cannot smuggle a
    value in without failing here.

    The payload is what an error-tracker forwards on a failed charge: an amount, a customer
    name, an email, an API token, a vendor identifier. None of it is a shape, and none of it may
    cross the observation boundary. `succeeded` is in the payload too, and is the one thing that
    survives -- the test is worthless if everything is dropped for lack of a rule.
    """
    payload = {
        "/data/status": "succeeded",
        "/data/amount": 4999,
        "/data/customer": "cus_NffrFeUfNV2Hib",
        "/data/billing_details/name": "Ada Lovelace",
        "/data/billing_details/email": "ada@example.com",
        "/data/source/token": "tok_1NpqR2eZvKYlo2C",
        "/data/description": "Invoice 2026-07 for Analytical Engine parts",
    }

    serialised = " ".join(
        ObservedShape.from_observation(
            vendor_id="stripe", operation_id="PostCharges", field_path=path,
            value=value, source="error-payload", spec_enum_values=STATUS_ENUM,
        ).model_dump_json()
        for path, value in payload.items()
    )

    for secret in (
        "4999", "cus_NffrFeUfNV2Hib", "Ada Lovelace", "ada@example.com",
        "tok_1NpqR2eZvKYlo2C", "Analytical Engine",
    ):
        assert secret not in serialised, f"{secret} crossed the observation boundary"
    assert "succeeded" in serialised, "a published enum member is public data and is kept"


def test_the_field_path_is_kept_because_it_is_structure_not_content():
    """Unlike the corpus, which drops file paths as customer structure, a JSON Pointer into a
    vendor's response body is the vendor's structure. `/data/billing_details/email` says Stripe
    has that field, which Stripe publishes; it says nothing about who was billed."""
    shape = ObservedShape.from_observation(
        vendor_id="stripe", operation_id="PostCharges",
        field_path="/data/billing_details/email", value="ada@example.com", source="error-payload",
    )

    assert shape.field_path == "/data/billing_details/email"


# --- persistence: the grain is a counter, not a row multiplier ---------------------


@pytest.fixture()
def store():
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


def test_a_shape_round_trips(store: GraphStore):
    store.record_observed_shape(_shape(spec_enum_values=["succeeded"], sample_count=3))
    rows = store.observed_shapes("stripe", "PostCharges")

    assert len(rows) == 1
    assert rows[0].field_path == "/data/status"
    assert rows[0].json_type == "string"
    assert rows[0].spec_enum_values == ["succeeded"]
    assert rows[0].sample_count == 3


def test_recording_the_same_shape_twice_counts_it_twice_in_one_row(store: GraphStore):
    """The whole reason `sample_count` is a column. The grain is one row per
    (vendor, operation, field_path, json_type, source) tuple, so a second observation of a
    shape already seen is a count, not a row. A table that appended instead would make every
    presence rate a function of how often the ingest ran.
    """
    store.record_observed_shape(_shape())
    store.record_observed_shape(_shape())

    rows = store.observed_shapes("stripe", "PostCharges")
    assert len(rows) == 1
    assert rows[0].sample_count == 2


def test_a_batch_adds_its_whole_count(store: GraphStore):
    """A caller that observed the same shape forty times in one window records it once with
    `sample_count=40`, and the counter has to add the batch rather than tick by one."""
    store.record_observed_shape(_shape(sample_count=40))
    store.record_observed_shape(_shape(sample_count=2))

    assert store.observed_shapes("stripe", "PostCharges")[0].sample_count == 42


def test_the_first_sighting_is_held_and_the_last_advances(store: GraphStore):
    """`first_seen` is what makes a baseline a baseline: it says how long this shape has been
    true. Overwriting it on every observation would leave a table that can only answer "recently"
    and never "since when", and the detector's observed-versus-observed comparison is a
    question about windows.
    """
    early = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    later = datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc)

    store.record_observed_shape(_shape(first_seen=early, last_seen=early))
    store.record_observed_shape(_shape(first_seen=later, last_seen=later))

    row = store.observed_shapes("stripe", "PostCharges")[0]
    assert row.first_seen == early
    assert row.last_seen == later


def test_an_observation_arriving_out_of_order_does_not_rewind_the_window(store: GraphStore):
    """Sources do not arrive in order -- an error-payload batch can be forwarded hours after a
    replay run. Taking the newer of the two ends rather than the last one written keeps the
    window honest regardless of arrival order."""
    early = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    later = datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc)

    store.record_observed_shape(_shape(first_seen=later, last_seen=later))
    store.record_observed_shape(_shape(first_seen=early, last_seen=early))

    row = store.observed_shapes("stripe", "PostCharges")[0]
    assert row.first_seen == early
    assert row.last_seen == later


def test_nullability_once_seen_is_never_forgotten(store: GraphStore):
    """`nullable_seen` is evidence, not a current reading. One null response proves the field
    can be null; a thousand non-null ones afterwards do not unprove it, and a column that
    flipped back would erase exactly the observation the detector is looking for.
    """
    store.record_observed_shape(_shape(nullable_seen=True))
    store.record_observed_shape(_shape(nullable_seen=False))

    assert store.observed_shapes("stripe", "PostCharges")[0].nullable_seen is True


def test_published_members_accumulate_across_observations(store: GraphStore):
    """Traffic exercises one enum member at a time. The column is the set of members this
    operation has been seen to send, so a second observation adds to it rather than replacing
    it -- and the table has no spec-version column, so a last-write-wins column would silently
    erase what an earlier specification named.
    """
    store.record_observed_shape(_shape(spec_enum_values=["succeeded"]))
    store.record_observed_shape(_shape(spec_enum_values=["requires_action"]))

    assert store.observed_shapes("stripe", "PostCharges")[0].spec_enum_values == [
        "requires_action", "succeeded",
    ]


def test_the_same_member_twice_does_not_duplicate_in_the_column(store: GraphStore):
    store.record_observed_shape(_shape(spec_enum_values=["succeeded"]))
    store.record_observed_shape(_shape(spec_enum_values=["succeeded"]))

    assert store.observed_shapes("stripe", "PostCharges")[0].spec_enum_values == ["succeeded"]


# --- what the natural key separates -----------------------------------------------


def test_a_type_change_on_one_path_is_a_second_row(store: GraphStore):
    """`json_type` is in the key precisely so this cannot merge. A field that used to arrive as
    a string and now arrives as a number is the unpublished change the whole document is about,
    and it has to be visible as two rows with their own windows and counts.
    """
    store.record_observed_shape(_shape(json_type="string"))
    store.record_observed_shape(_shape(json_type="number"))

    rows = store.observed_shapes("stripe", "PostCharges")
    assert sorted(row.json_type for row in rows) == ["number", "string"]


def test_the_same_shape_from_two_sources_stays_two_rows(store: GraphStore):
    """`source` is in the key because the sources have different fidelity: error-payload shapes
    are biased toward failures, replay shapes are Sync's own. Merging them would let a biased
    sample masquerade as a baseline.

    Read with `traffic_only=False` because the subject is the key rather than the reader: the
    default answer holds traffic alone and would show one row here whether or not the second
    write had merged into the first, which is the distinction this asserts.
    """
    store.record_observed_shape(_shape(source="replay"))
    store.record_observed_shape(_shape(source="error-payload"))

    assert len(store.observed_shapes("stripe", "PostCharges", traffic_only=False)) == 2


def test_two_paths_are_two_rows(store: GraphStore):
    store.record_observed_shape(_shape(field_path="/data/status"))
    store.record_observed_shape(_shape(field_path="/data/refund/status"))

    assert len(store.observed_shapes("stripe", "PostCharges")) == 2


def test_shapes_are_read_back_for_one_operation_only(store: GraphStore):
    """The detector asks about one operation at a time, and a baseline that leaked another
    operation's fields into the answer would produce findings against paths that operation
    never returns."""
    store.record_observed_shape(_shape(operation_id="PostCharges"))
    store.record_observed_shape(_shape(operation_id="PostRefunds"))

    rows = store.observed_shapes("stripe", "PostCharges")
    assert [row.operation_id for row in rows] == ["PostCharges"]


def test_shapes_are_read_back_for_one_vendor_only(store: GraphStore):
    store.record_observed_shape(_shape(vendor_id="stripe"))
    store.record_observed_shape(_shape(vendor_id="twilio"))

    rows = store.observed_shapes("stripe", "PostCharges")
    assert [row.vendor_id for row in rows] == ["stripe"]


def test_an_operation_never_observed_reads_back_empty(store: GraphStore):
    """No baseline is a distinct answer from an empty baseline, and the sample floor the spec
    mandates depends on the caller being able to tell them apart.

    Another operation is observed first, so the emptiness asserted here is the filter's doing
    rather than the table's. Against an empty table this passes no matter how the query is
    written, which would make it a test that cannot fail.
    """
    store.record_observed_shape(_shape(operation_id="PostCharges"))

    assert store.observed_shapes("stripe", "PostNeverCalled") == []

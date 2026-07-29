"""Synthesizing a mock response where observed reality outranks the published spec.

Step 1 of the replay verification tier in
`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md`. The tier exists because
a green CI run proves little when no test exercises the patched call: most customers have no
test covering their Stripe integration, and a passing suite that never runs the patched path
is weak evidence presented as strong.

The precedence rule is the whole point, and it is what these tests are mostly about:

    A specification says what the vendor promised. Observed traffic says what the vendor did.
    When those diverge, something changed that nobody announced.

A mock built only from the specification tests the patch against the vendor's promise. A mock
that prefers observation tests it against reality, and reality is what breaks customers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from sync.core import ObservedShape
from sync.detect.observed_drift import MIN_SAMPLES
from sync.verify.mock_response import (
    PLACEHOLDER_PREFIX,
    decide_field,
    synthesize_mock_response,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mock_response"
SCHEMA = json.loads((FIXTURES / "payment_intent.json").read_text(encoding="utf-8"))


def _observed(
    field_path: str,
    json_type: str,
    *,
    nullable_seen: bool = False,
    sample_count: int = MIN_SAMPLES,
    spec_enum_values: list[str] | None = None,
) -> ObservedShape:
    return ObservedShape(
        vendor_id="stripe", operation_id="PostPaymentIntents", field_path=field_path,
        json_type=json_type, nullable_seen=nullable_seen,
        spec_enum_values=spec_enum_values or [], source="error-payload",
        sample_count=sample_count,
    )


# --- the test this task exists for -------------------------------------------------


def test_an_established_observation_beats_the_specification():
    """The spec declares `id` a required, non-nullable string. Production has been seen
    sending null. The mock has to show what the vendor did, not what it promised -- the
    patched code meets reality, and a mock that hid the null would pass a patch that
    crashes on the first response.
    """
    body = synthesize_mock_response(
        SCHEMA, [_observed("/id", "null", nullable_seen=True)]
    )

    assert body["id"] is None


def test_the_decision_says_which_source_won():
    """A reader should not have to infer which source won, and neither should a caller
    assembling the evidence line for the pull request body."""
    observed = [_observed("/id", "null", nullable_seen=True)]

    assert decide_field("/id", {"type": "string"}, observed).source == "observed"
    assert decide_field("/amount", {"type": "integer"}, observed).source == "specification"


def test_an_observed_type_change_reshapes_the_value_not_only_its_nullability():
    """`amount` is declared an integer and has been seen as a string. Reality wins on the
    type itself, or the mock would test the patch against a number the vendor stopped
    sending."""
    body = synthesize_mock_response(SCHEMA, [_observed("/amount", "string")])

    assert isinstance(body["amount"], str)


# --- the test that makes the first one mean something ------------------------------


def test_the_specification_fills_every_field_observation_does_not_cover():
    """Without this, a synthesizer that ignored the spec entirely would pass the first
    test. Only `/id` is observed here; everything else must still be present and shaped."""
    body = synthesize_mock_response(SCHEMA, [_observed("/id", "null", nullable_seen=True)])

    assert set(body) == set(SCHEMA["properties"])
    assert isinstance(body["amount"], int)
    assert isinstance(body["livemode"], bool)
    assert isinstance(body["charges"], dict)


def test_no_observations_at_all_produces_a_specification_shaped_mock():
    body = synthesize_mock_response(SCHEMA, [])

    assert isinstance(body["id"], str)
    assert body["status"] in SCHEMA["properties"]["status"]["enum"]


# --- the sample floor, asserted on the boundary ------------------------------------


def test_one_sample_below_the_floor_does_not_override_the_specification():
    """Asserted at the boundary, not far from it: a floor that is off by one is a real bug
    and a test at ten times the floor cannot see it. A shape seen too few times is not a
    baseline -- one upstream incident supplies the whole sample."""
    body = synthesize_mock_response(
        SCHEMA, [_observed("/id", "null", nullable_seen=True, sample_count=MIN_SAMPLES - 1)]
    )

    assert isinstance(body["id"], str)


def test_exactly_the_floor_is_enough_to_override_the_specification():
    body = synthesize_mock_response(
        SCHEMA, [_observed("/id", "null", nullable_seen=True, sample_count=MIN_SAMPLES)]
    )

    assert body["id"] is None


def test_the_floor_is_the_detector_s_floor_rather_than_a_second_number(monkeypatch):
    """Two floors that can drift is the defect the Datadog signal module avoided by
    importing Sentry's array rule rather than copying it.

    Asserted by moving the detector's floor and reloading, not by comparing the two values:
    a copied literal compares equal to the original, and `is` does not separate them either
    because CPython caches small integers. Only rebinding shows where the name came from.
    """
    import importlib

    from sync.detect import observed_drift
    from sync.verify import mock_response

    monkeypatch.setattr(observed_drift, "MIN_SAMPLES", 7)
    try:
        assert importlib.reload(mock_response).MIN_SAMPLES == 7
    finally:
        monkeypatch.undo()
        importlib.reload(mock_response)

    assert mock_response.MIN_SAMPLES == MIN_SAMPLES


# --- nothing that could pass for real data ----------------------------------------


def test_every_string_is_either_a_published_enum_member_or_an_obvious_placeholder():
    """The rule being asserted, because this one protects a threat-model commitment rather
    than a behaviour.

    The shape store retains no free-form value: paths, types, nullability and counts only,
    plus enum members the vendor's published specification names, which are public data.
    So every string the synthesizer emits must be one of exactly two things -- a spec-named
    enum member, or a placeholder no reader could mistake for real data. A mock carrying
    something that reads like a customer identifier is a bug even when the value was
    fabricated, because it will be pasted into an issue by someone who thinks it is real.
    """
    body = synthesize_mock_response(SCHEMA, [])
    published = {
        value
        for schema in _walk_schemas(SCHEMA)
        for value in schema.get("enum", [])
    }

    for pointer, value in _walk_strings(body):
        assert value in published or value.startswith(PLACEHOLDER_PREFIX), (
            f"{pointer} carries {value!r}, which is neither a published enum member nor a "
            f"placeholder"
        )


def test_no_emitted_string_looks_like_an_identifier_a_token_or_an_amount():
    """The shapes a real Stripe payload carries: `pi_`/`ch_`-prefixed ids, long opaque
    hex, and money written as digits. None may appear."""
    body = synthesize_mock_response(SCHEMA, [])
    looks_real = re.compile(r"(^(pi|ch|cus|sk|pk|tok|seti)_)|([0-9a-f]{16,})|(^\d+([.,]\d+)?$)")

    for pointer, value in _walk_strings(body):
        assert not looks_real.search(value), f"{pointer} carries {value!r}"


def test_an_observed_enum_member_may_be_emitted_because_the_spec_named_it():
    """`spec_enum_values` holds only members the published specification names *and* that
    were actually observed, so it is public data twice over -- and it is the one case where
    an observation contributes a value rather than only a shape."""
    body = synthesize_mock_response(
        SCHEMA,
        [_observed("/status", "string", spec_enum_values=["canceled"])],
    )

    assert body["status"] == "canceled"


def test_an_observed_enum_member_the_specification_does_not_name_is_refused():
    """A store row is trusted for shape, never for provenance. If a value reached
    `spec_enum_values` that the schema in hand does not carry, emitting it would launder an
    unpublished string through the mock -- so the schema is checked again here."""
    body = synthesize_mock_response(
        SCHEMA,
        [_observed("/status", "string", spec_enum_values=["cus_QhX7fLeaked"])],
    )

    assert body["status"] in SCHEMA["properties"]["status"]["enum"]


# --- the two spellings of a nullable declaration -----------------------------------


def test_the_type_list_spelling_of_nullable_is_read_as_nullable():
    """OpenAPI 3.0 writes `nullable: true` beside a scalar type; JSON Schema and OpenAPI 3.1
    write the null into the type itself. Both are in the wild, and a synthesizer that read only
    the first would emit a happy string for a field the vendor documents as nullable -- hiding
    the null this whole tier exists to make the patched code meet.
    """
    decision = decide_field("/id", {"type": ["string", "null"]}, [])

    assert decision.json_type == "string"
    assert decision.nullable is True
    assert synthesize_mock_response({"type": ["string", "null"]}, []) is None


def test_a_union_of_two_real_types_takes_the_first_and_stays_non_nullable():
    """`null` is the member that carries meaning here. Without it the list is a union this
    module has no rule for, so it builds the first member rather than nothing."""
    decision = decide_field("/id", {"type": ["string", "number"]}, [])

    assert decision.json_type == "string"
    assert decision.nullable is False


def test_a_declaration_that_is_only_null_describes_a_field_that_is_always_null():
    """`{"type": "null"}` and `{"type": ["null"]}` are one declaration written two ways. Both
    describe a field the vendor always sends as null, which is a shape the patched code has to
    survive rather than a field with no declaration at all."""
    for schema in ({"type": "null"}, {"type": ["null"]}):
        decision = decide_field("/x", schema, [])

        assert (decision.json_type, decision.nullable) == ("null", True), schema
        assert synthesize_mock_response(schema, []) is None


# --- a declaration this module cannot build a value from ---------------------------


def test_a_schema_that_names_no_type_yields_no_value():
    """A schema that names no type has promised nothing. `None` rather than a placeholder,
    because a placeholder would put a value in the mock that no specification supports and the
    patched code would be tested against this module's guess."""
    assert synthesize_mock_response({}, []) is None
    assert synthesize_mock_response({"description": "an amount, one day"}, []) is None


def test_a_type_this_module_has_no_rule_for_yields_no_value():
    assert synthesize_mock_response({"type": "any"}, []) is None


def test_an_untyped_property_is_still_a_key_in_the_object():
    """The field is declared even where its shape is not, and step 3 checks
    `response_fields_read` against the mock by presence. Dropping the key would report a field
    the code legitimately reads as one the response no longer carries -- a replay failure
    manufactured by the synthesizer rather than found in the patch.
    """
    body = synthesize_mock_response(
        {"type": "object", "properties": {"id": {"type": "string"}, "extra": {}}}, []
    )

    assert set(body) == {"id", "extra"}
    assert body["extra"] is None


# --- nesting and arrays ------------------------------------------------------------


def test_an_array_with_no_declared_element_is_empty_rather_than_guessed():
    """One element of an undeclared shape would be one invented value. Empty is what this
    module can honestly claim to know."""
    body = synthesize_mock_response(
        {"type": "object", "properties": {"lines": {"type": "array"}}}, []
    )

    assert body["lines"] == []


def test_an_array_whose_items_are_a_boolean_schema_is_empty_too():
    """`items: true` is a legal JSON Schema and names no shape at all."""
    assert synthesize_mock_response({"type": "array", "items": True}, []) == []


def test_a_pointer_three_levels_deep_round_trips():
    body = synthesize_mock_response(SCHEMA, [])

    assert isinstance(body["charges"]["data"], list)
    assert isinstance(body["charges"]["data"][0]["outcome"]["risk_score"], int)


def test_an_array_element_is_addressed_with_the_store_s_array_token():
    """Observed paths collapse every element to `-`, the one array token RFC 6901 defines.
    A synthesizer expecting indexed pointers would match nothing, so this is the assertion
    that the two addressing schemes agree.
    """
    body = synthesize_mock_response(
        SCHEMA, [_observed("/charges/data/-/paid", "string")]
    )

    assert isinstance(body["charges"]["data"][0]["paid"], str)


def test_an_indexed_pointer_matches_nothing_because_the_store_never_writes_one():
    body = synthesize_mock_response(
        SCHEMA, [_observed("/charges/data/0/paid", "string")]
    )

    assert body["charges"]["data"][0]["paid"] is False


def test_a_nested_observation_three_levels_down_still_wins():
    body = synthesize_mock_response(
        SCHEMA,
        [_observed("/charges/data/-/outcome/risk_score", "null", nullable_seen=True)],
    )

    assert body["charges"]["data"][0]["outcome"]["risk_score"] is None


# --- several observations of one path ----------------------------------------------


def test_the_dominant_established_shape_is_the_one_synthesized():
    """One path carries one row per json_type, so a field seen as both string and null is
    two rows. The larger sample describes the field; the smaller still establishes that
    null happens, which the next test covers."""
    body = synthesize_mock_response(
        SCHEMA,
        [
            _observed("/id", "string", sample_count=900),
            _observed("/id", "null", nullable_seen=True, sample_count=MIN_SAMPLES),
        ],
    )

    assert body["id"] is None, "an established null is what the patched code must survive"


def test_a_null_below_the_floor_does_not_make_a_busy_field_nullable():
    body = synthesize_mock_response(
        SCHEMA,
        [
            _observed("/id", "string", sample_count=900),
            _observed("/id", "null", nullable_seen=True, sample_count=1),
        ],
    )

    assert isinstance(body["id"], str)


# --- purity ------------------------------------------------------------------------


def test_the_synthesizer_touches_no_database_and_no_network(monkeypatch):
    """A pure function: a schema and a set of shapes in, a body out. It is worth pinning,
    because the module imports two collaborators that do open connections and the next
    reader should not have to trust a docstring about it."""
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("the synthesizer opened a socket")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)

    assert synthesize_mock_response(SCHEMA, [_observed("/id", "null", nullable_seen=True)])


def test_calling_it_twice_gives_the_same_answer():
    """Deterministic, so a replay that fails is reproducible and a diff between two runs
    means the inputs changed."""
    first = synthesize_mock_response(SCHEMA, [_observed("/amount", "string")])
    second = synthesize_mock_response(SCHEMA, [_observed("/amount", "string")])

    assert first == second


def test_the_inputs_are_not_mutated():
    before = json.dumps(SCHEMA, sort_keys=True)
    shapes = [_observed("/id", "null", nullable_seen=True)]

    synthesize_mock_response(SCHEMA, shapes)

    assert json.dumps(SCHEMA, sort_keys=True) == before
    assert shapes[0].json_type == "null"


# --- helpers -----------------------------------------------------------------------


def _walk_schemas(schema):
    yield schema
    for child in (schema.get("properties") or {}).values():
        yield from _walk_schemas(child)
    items = schema.get("items")
    if isinstance(items, dict):
        yield from _walk_schemas(items)


def _walk_strings(value, pointer=""):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{pointer}/{index}")

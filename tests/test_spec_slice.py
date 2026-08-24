"""One operation's slice of a specification, small enough to hand an agent.

`build_patch_prompt` names the operation a finding is about and says nothing about its shape, so
the agent is told `PostCharges` changed and left to infer what `PostCharges` looks like. The whole
document is not the alternative: Anthropic's is 2,015,896 bytes over 144 operations, and the one
that matters is a few hundred.

The hard part is `$ref`. An OpenAPI operation is mostly pointers -- a naive slice hands the agent
`$ref: '#/components/schemas/Charge'` and tells it nothing it did not already know.
"""

from __future__ import annotations

import pytest

from sync.remediate.spec_slice import SliceTooDeep, operation_slice

DOCUMENT = {
    "openapi": "3.1.0",
    "paths": {
        "/v1/charges": {
            "post": {
                "operationId": "PostCharges",
                "parameters": [{"name": "expand", "in": "query", "schema": {"type": "string"}}],
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/ChargeCreate"}}
                    }
                },
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Charge"}}
                        }
                    }
                },
            },
            "get": {"operationId": "GetCharges", "responses": {}},
        },
        "/v1/refunds": {"post": {"operationId": "PostRefunds", "responses": {}}},
    },
    "components": {
        "schemas": {
            "Charge": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"$ref": "#/components/schemas/ChargeStatus"},
                },
            },
            "ChargeStatus": {"type": "string", "enum": ["pending", "succeeded"]},
            "ChargeCreate": {"type": "object", "properties": {"amount": {"type": "integer"}}},
            "Unrelated": {"type": "object"},
        }
    },
}


def test_the_slice_is_the_operation_the_finding_names():
    sliced = operation_slice(DOCUMENT, "PostCharges")

    assert sliced is not None
    assert sliced.path == "/v1/charges"
    assert sliced.http_method == "post"
    assert sliced.operation["operationId"] == "PostCharges"


def test_no_other_operation_comes_with_it():
    """The point of a slice. The document declares three operations and the agent is asked
    about one."""
    rendered = operation_slice(DOCUMENT, "PostCharges").render()

    assert "PostCharges" in rendered
    assert "GetCharges" not in rendered
    assert "PostRefunds" not in rendered


def test_the_default_slice_expands_the_request_and_response_shapes():
    """Depth 1, and the number is measured rather than chosen. Against Stripe's `PostCharges` in
    a 7,866,866-byte document the slice is 15,938 bytes at depth 0, 33,857 at depth 1 and 137,117
    at depth 2 -- roughly 4k, 8k and 34k tokens. Depth 2 displaces the call site and the
    diagnostics, which are the two things the agent cannot work without.
    """
    sliced = operation_slice(DOCUMENT, "PostCharges")

    assert set(sliced.schemas) == {"Charge", "ChargeCreate"}
    assert sliced.not_expanded == ("ChargeStatus",)


def test_a_reference_reached_through_another_is_followed_when_the_depth_allows():
    """The resolution is transitive, not one level hard-coded: `Charge` names `ChargeStatus`,
    and an enum is exactly where a breaking change usually is."""
    sliced = operation_slice(DOCUMENT, "PostCharges", depth=2)

    assert "ChargeStatus" in sliced.schemas, "a reference reached through another was not followed"
    assert sliced.schemas["ChargeStatus"]["enum"] == ["pending", "succeeded"]
    assert sliced.not_expanded == ()


def test_a_schema_the_operation_never_reaches_is_left_behind():
    """The other half of slicing. Carrying every schema would be the whole document wearing a
    smaller name."""
    assert "Unrelated" not in operation_slice(DOCUMENT, "PostCharges").schemas


def test_an_operation_the_document_does_not_declare_is_absent_rather_than_empty():
    """`None` and an empty slice are different claims: one says the specification does not
    describe this operation, the other says it describes it as nothing."""
    assert operation_slice(DOCUMENT, "NoSuchOperation") is None


def test_a_reference_cycle_terminates_rather_than_recurring():
    """Self-referential schemas are ordinary -- a tree node holding children of its own type."""
    document = {
        "paths": {"/v1/t": {"get": {"operationId": "GetTree",
                                    "responses": {"200": {"content": {"application/json": {
                                        "schema": {"$ref": "#/components/schemas/Node"}}}}}}}},
        "components": {"schemas": {"Node": {
            "type": "object",
            "properties": {"child": {"$ref": "#/components/schemas/Node"}},
        }}},
    }

    sliced = operation_slice(document, "GetTree")

    assert sliced is not None and "Node" in sliced.schemas


def test_a_reference_that_leaves_the_document_is_refused_rather_than_fetched():
    """A `$ref` naming another file or a URL is a fetch, and a slicer that fetches is a slicer
    that reaches the network from inside a prompt build."""
    document = {
        "paths": {"/v1/x": {"get": {"operationId": "GetX", "responses": {"200": {
            "content": {"application/json": {"schema": {"$ref": "https://example.invalid/s.json"}}}
        }}}}},
        "components": {"schemas": {}},
    }

    sliced = operation_slice(document, "GetX")

    assert sliced is not None
    assert sliced.unresolved == ("https://example.invalid/s.json",)


def test_the_slice_carries_the_hash_it_was_cut_from():
    """A citation nobody can check is the thing the owner's constraint rules out. The hash says
    which document said this, so a claim made from the slice is refutable later."""
    sliced = operation_slice(DOCUMENT, "PostCharges", spec_hash="ab3b8dbb")

    assert sliced.spec_hash == "ab3b8dbb"
    assert "ab3b8dbb" in sliced.render()


def test_a_schema_past_the_depth_bound_is_named_rather_than_dropped():
    """Measured against Stripe's `PostCharges`: depth 1 reaches 2 schemas, depth 2 reaches 21,
    depth 3 reaches 134 and the closure is 790 -- the whole document wearing a smaller name. So
    the slice is bounded, and the bound has to be visible: the agent must be able to tell "there
    is more here, called `Deep`" from "the vendor declares nothing here".
    """
    document = {
        "paths": {"/v1/x": {"get": {"operationId": "GetX", "responses": {"200": {
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Outer"}}}}}}}},
        "components": {"schemas": {
            "Outer": {"properties": {"mid": {"$ref": "#/components/schemas/Mid"}}},
            "Mid": {"properties": {"deep": {"$ref": "#/components/schemas/Deep"}}},
            "Deep": {"type": "string"},
        }},
    }

    sliced = operation_slice(document, "GetX", depth=2)

    assert set(sliced.schemas) == {"Outer", "Mid"}
    assert sliced.not_expanded == ("Deep",)
    assert "Deep" in sliced.render()


def test_a_wide_fan_out_inside_the_bound_is_refused_rather_than_truncated():
    """The depth bound is not a size bound. One schema can name a hundred others at one level,
    and a slice that quietly kept the first sixty-four would be a specification with holes the
    agent cannot see."""
    fan = {f"S{i}": {"type": "string"} for i in range(100)}
    fan["Root"] = {"properties": {f"p{i}": {"$ref": f"#/components/schemas/S{i}"}
                                  for i in range(100)}}
    document = {
        "paths": {"/v1/f": {"get": {"operationId": "GetF", "responses": {"200": {
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Root"}}}}}}}},
        "components": {"schemas": fan},
    }

    with pytest.raises(SliceTooDeep):
        operation_slice(document, "GetF", depth=2, max_schemas=32)

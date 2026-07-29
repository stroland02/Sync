"""An MCP server watched as a vendor: two captured `tools/list` responses, diffed.

Named for the signal rather than for the protocol, because `tests/test_mcp_server.py` already
exists and tests the opposite direction -- Sync exposing its own graph over MCP. Nothing here
touches that. The subject is somebody else's server, and the only thing this adapter ever sees
of it is a committed capture of what it advertised.

The fixtures are one fictional documentation server captured twice. Every tool in them exists
to exercise one thing:

- `list_spaces` is gone in the second capture -- a tool removed.
- `search_docs` gains a required `space_id`, loses `limit` and `highlight`, and narrows
  `format` from `["string", "null"]` to `"string"` -- four breakages in one tool. Two of them
  are removals of the same kind, which is what makes a row's identity testable.
- `delete_page` loses `confirm` and declares `additionalProperties: false`, so a caller still
  sending it is rejected rather than ignored.
- `compose_query` hides its properties behind `allOf` and `$ref`, which the flat reader cannot
  judge, and its contents change between the captures.
- `get_page` is identical in both, and `create_page` is new.

`get_page` has no test of its own, deliberately. "An unchanged tool produces no row" cannot be
made to fail by any single edit to the differ -- the whole-schema equality check returns early,
and deleting that check changes nothing either, because every emission path fires on a concrete
difference and an unchanged tool has none. It is entailed rather than tested, and `CLAUDE.md` is
explicit that a test which cannot fail is worse than no test. `get_page` earns its place as the
control that would break several assertions below if the differ ever emitted indiscriminately.

`create_page` does get a test, and the distinction is not arbitrary: reporting an *added* tool
is a live design temptation with precedent right here -- oasdiff reports additions and
`to_vendor_changes` maps every record it emits to a row, which is why `TwilioAdapter` carries a
`NOISE_KINDS` filter. Emitting on an addition is one edit away. Emitting on no difference at all
is not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.core import VendorAdapter
from sync.signals.mcp_server.adapter import McpServerAdapter
from sync.signals.oasdiff import changed_field

FIXTURES = Path(__file__).parent / "fixtures" / "mcp_server"

BEFORE = "2026-06-01"
AFTER = "2026-07-15"


def _adapter(server_id: str = "example-docs") -> McpServerAdapter:
    return McpServerAdapter(snapshot_dir=FIXTURES, server_id=server_id)


def _changes(from_version: str = BEFORE, to_version: str = AFTER) -> list:
    return list(_adapter().fetch_changes(from_version, to_version))


def _of_kind(kind: str, operation_id: str | None = None) -> list:
    rows = [c for c in _changes() if c.kind == kind]
    if operation_id is None:
        return rows
    return [c for c in rows if c.operation_id == operation_id]


def test_the_adapter_satisfies_the_vendor_adapter_protocol():
    """The protocol is what the registry and the pipeline type against.

    A `runtime_checkable` Protocol only checks that the members exist, so this fails when a
    method is renamed or dropped and not when a signature drifts. That is worth having anyway:
    the failure it catches is the one where an adapter is written against a stale protocol and
    is discovered at the first pipeline run rather than here.
    """
    assert isinstance(_adapter(), VendorAdapter)


def test_the_vendor_id_namespaces_the_server_behind_the_protocol():
    """`mcp:` in front, because a server and a REST API can share a name.

    Stripe ships an MCP server and Stripe has a REST adapter here. Both would claim
    `vendor_id='stripe'`, the graph keys call sites and changes on `(vendor_id, operation_id)`,
    and the two address entirely different things -- so an unprefixed id would silently mix
    tool changes into the REST vendor's rows.
    """
    assert _adapter("stripe").vendor_id == "mcp:stripe"


def test_a_tool_that_disappeared_is_a_breaking_change():
    removed = _of_kind("mcp-tool-removed")

    assert [c.operation_id for c in removed] == ["list_spaces"]
    assert removed[0].severity == "breaking"


def test_a_tool_that_appeared_produces_no_change():
    """`create_page` is new in the second capture, and new is not breaking."""
    assert not [c for c in _changes() if c.operation_id == "create_page"]


def test_an_argument_that_became_required_breaks_every_existing_caller():
    added = _of_kind("mcp-tool-required-argument-added", "search_docs")

    assert [c.raw["property"] for c in added] == ["space_id"]
    assert added[0].severity == "breaking"


def test_an_argument_that_disappeared_is_a_breaking_change():
    """`search_docs` loses two of them, which is the case that decides a row's identity.

    `GraphStore.upsert_vendor_change` hashes the row id out of vendor, versions, kind,
    `path_ptr` and `operation_id` -- all five of which two arguments removed from one tool
    share -- plus `raw['text']`. So the text is the only thing keeping them apart, and one
    tool losing two arguments is the fixture that proves it does.
    """
    removed = _of_kind("mcp-tool-argument-removed")

    assert {(c.operation_id, c.raw["property"]) for c in removed} == {
        ("search_docs", "limit"),
        ("search_docs", "highlight"),
        ("delete_page", "confirm"),
    }


def test_a_removed_argument_records_whether_the_server_now_rejects_it():
    """Same kind, opposite failure, and only the schema says which.

    `delete_page` declares `additionalProperties: false`, so a caller still passing `confirm`
    gets a validation error it can see. `search_docs` declares nothing, which JSON Schema reads
    as "additional properties permitted", so `limit` is accepted and ignored -- the call
    succeeds and does something other than what the caller asked for. The repair is the same
    edit either way, which is why this is one kind and not two; the urgency is not, which is
    why the distinction has to survive into the row.
    """
    rejected = {c.operation_id: c.raw["rejects_unknown_arguments"] for c in _of_kind("mcp-tool-argument-removed")}

    assert rejected == {"delete_page": True, "search_docs": False}


def test_an_argument_type_the_server_stopped_accepting_is_a_breaking_change():
    """Detected as a set difference, which catches replacement as well as narrowing.

    `format` goes from `["string", "null"]` to `"string"`, so `null` is no longer accepted. The
    same rule reports `"string"` becoming `"number"`, because that also drops a type the caller
    was sending. It reports nothing when the revision only adds types, which is widening and
    breaks nobody.
    """
    narrowed = _of_kind("mcp-tool-argument-type-narrowed", "search_docs")

    assert [c.raw["property"] for c in narrowed] == ["format"]
    assert narrowed[0].raw["no_longer_accepted"] == ["null"]


def test_a_schema_the_flat_reader_cannot_judge_is_named_rather_than_skipped():
    """`compose_query` composes with `allOf` and `$ref`, and it changed.

    MCP constrains `inputSchema` to "a JSON Schema object" and no further, so a server is free
    to put its properties behind composition. Reading `properties` and `required` off the top
    level then finds nothing and reports nothing -- which is indistinguishable from a tool that
    did not change. Emitting a row at `info` is what makes the blind spot countable.
    """
    unreadable = _of_kind("mcp-tool-schema-not-comparable")

    assert [c.operation_id for c in unreadable] == ["compose_query"]
    assert unreadable[0].severity == "info"


def test_an_unreadable_schema_that_did_not_change_produces_nothing():
    """The comparison that survives composition: the whole schema, for equality.

    Without it this adapter would report `compose_query` on every scan forever, and a check
    that fires every time is one nobody reads.
    """
    assert not list(_adapter().fetch_changes(BEFORE, BEFORE))


def test_rows_carry_the_argument_name_where_the_remediators_look_for_it():
    """`changed_field` is the supported way to ask which field a change is about.

    Three remediators call it, and it reads `raw['property']` before it falls back to parsing
    the free-text message. Populating the structured key is what lets a row produced here reach
    them without any of them learning what MCP is.
    """
    for change in _of_kind("mcp-tool-argument-removed") + _of_kind("mcp-tool-required-argument-added"):
        assert changed_field(change) == change.raw["property"]


def test_every_row_keeps_both_advertised_definitions():
    """`CLAUDE.md`: store the interpretation and the source.

    An MCP server has no published history, so a capture is the only record that a tool ever
    looked the way it did. A better differ has to be able to re-derive against stored rows,
    because re-fetching gives you today's server and nothing else.
    """
    for change in _changes():
        assert change.raw["before"] is not None
        assert "after" in change.raw

    removed = _of_kind("mcp-tool-removed")[0]
    assert removed.raw["after"] is None


def test_the_same_two_captures_produce_the_same_rows_twice():
    """Idempotence, asserted on the columns `_stable_id` hashes.

    `GraphStore.upsert_vendor_change` derives a row's identity from vendor, versions, kind,
    path_ptr, operation_id and `raw['text']`. A run that produced different text for the same
    change would write a second row for it on every scan.
    """
    def identity(change):
        return (
            change.vendor_id, change.from_version, change.to_version,
            change.kind, change.path_ptr, change.operation_id, change.raw["text"],
        )

    first = [identity(c) for c in _changes()]
    second = [identity(c) for c in _changes()]

    assert first == second
    assert len(set(first)) == len(first)


def test_a_truncated_capture_raises_rather_than_reading_as_a_mass_removal():
    """`tools/list` is paginated, and a capture that stopped at page one is a trap.

    Every tool past the first page is absent from it, and absent is exactly how this adapter
    reads a removal. One incomplete capture would report the server's entire catalogue as
    withdrawn -- the largest possible false positive, produced by our own capture step, and
    indistinguishable from the real thing without the cursor.
    """
    adapter = McpServerAdapter(snapshot_dir=FIXTURES, server_id="example-docs")

    with pytest.raises(ValueError, match="nextCursor"):
        list(adapter.fetch_changes("first_page_only", AFTER))


def test_a_tool_advertised_without_an_input_schema_is_rejected():
    """A capture is untrusted input and is parsed strictly, at the boundary.

    `inputSchema` is required by the protocol. A capture missing it is a malformed record, and
    building rows from it would mean inventing an empty argument list -- which reads downstream
    as "this tool takes nothing" rather than as "we could not read this".
    """
    adapter = McpServerAdapter(snapshot_dir=FIXTURES, server_id="example-docs")

    with pytest.raises(ValueError):
        list(adapter.fetch_changes("missing_input_schema", AFTER))


def test_a_missing_capture_raises_rather_than_reporting_a_quiet_server():
    adapter = McpServerAdapter(snapshot_dir=FIXTURES, server_id="example-docs")

    with pytest.raises(FileNotFoundError):
        list(adapter.fetch_changes(BEFORE, "2027-01-01"))


def test_operation_for_symbol_never_resolves():
    """There is no SDK symbol for an MCP tool call, so there is nothing to resolve.

    A client calls every tool through one method -- `session.call_tool(name, arguments)` -- and
    the name arrives as a runtime string, usually one a model chose. The indexer's `symbol` for
    every such site is the same `call_tool` chain, which addresses no single tool. Returning
    `None` keeps the miss countable; returning a guess would bind a finding to a call the
    customer's code does not make.
    """
    adapter = _adapter()

    assert adapter.operation_for_symbol("client.call_tool") is None
    assert adapter.operation_for_symbol("search_docs") is None
    assert adapter.operation_for_symbol("search_docs", language="typescript") is None

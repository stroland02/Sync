"""Every place the MCP-server signal source refuses to read, and what the caller sees of it.

The subject is somebody else's server, as in `tests/test_mcp_vendor_signal.py`, and not
`sync.mcp`, which is Sync exposing its own graph. That file tests the changes this adapter
reports. This one tests the refusals -- the inputs it declines to read -- because a refusal that
becomes nothing downstream is indistinguishable from a tool that did not change, which is the
failure `arguments.py` opens by naming.

The answer is not uniform, and the split is the point. `read_arguments` refuses a whole tool and
the caller turns that into an `mcp-tool-schema-not-comparable` row, exactly as the module
docstring promises. `_accepted_types` refuses one argument's types and the caller turns that into
*nothing*: `_types_narrowed` skips an argument whose types are unreadable, so a tool whose schema
changed only there is reported as unchanged. Both are asserted below against the rows
`fetch_changes` actually produces, because the promise is about what the caller observes and
nothing else can check it.

The fixture pair is one fictional server captured twice, four tools, one refusal each:

- `list_pages` sends `properties` as an array, which no flat read can walk.
- `rename_page` sends `title: true`, a boolean subschema -- valid JSON Schema since draft 6 and
  still not a table of arguments.
- `export_page` keeps `format`'s `type` and adds an `anyOf` beside it, so the type on show is no
  longer the whole of what the server accepts.
- `archive_page` drops `scope`'s `type` entirely, leaving a subschema that names no type at all.

`rename_page`'s description carries an em dash and three accented characters, and it is the only
non-ASCII fixture in this repository. `CLAUDE.md` records that every fixture here is ASCII and
that therefore no test catches a missing `encoding="utf-8"`. On this machine the locale codepage
is cp1252, which decodes those bytes without raising and yields mojibake, so the assertion has to
be on the recovered string rather than on the read succeeding -- and it has to be on a tool that
emits a row, which is why the accents are on `rename_page` rather than on one of the silent two.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.signals.mcp_server.adapter import SCHEMA_NOT_COMPARABLE, McpServerAdapter
from sync.signals.mcp_server.arguments import read_arguments
from sync.signals.mcp_server.snapshot import load_snapshot, parse_snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "mcp_server"

BEFORE = "refusal_before"
AFTER = "refusal_after"

RENAME_DESCRIPTION = "Renomme la page — accents délibérés."


def _adapter(server_id: str = "example-docs") -> McpServerAdapter:
    return McpServerAdapter(snapshot_dir=FIXTURES, server_id=server_id)


def _rows(tool: str) -> list:
    return [c for c in _adapter().fetch_changes(BEFORE, AFTER) if c.operation_id == tool]


# --------------------------------------------------------------------------------------------
# read_arguments refuses the whole table, and the caller makes a row of it.
# --------------------------------------------------------------------------------------------


def test_properties_that_is_not_an_object_is_refused():
    """`arguments.py:69`. A flat read of an array finds no arguments and would report none.

    JSON Schema requires `properties` to be an object. A server sending an array has sent
    something this reader cannot walk, and reading it anyway yields an empty argument table --
    which downstream is the same shape as a tool that takes nothing.
    """
    assert read_arguments({"type": "object", "properties": ["space"]}) is None


def test_a_boolean_subschema_is_refused():
    """`arguments.py:77`. `true` is a legal subschema and is not a description of an argument.

    Draft 6 onwards allows a boolean in place of a subschema object: `true` accepts any value,
    `false` accepts none. Neither states a type or anything else this reader takes, so the table
    is refused rather than filled with an entry whose absence of information is indistinguishable
    from an argument that was read.
    """
    assert read_arguments({"type": "object", "properties": {"title": True}}) is None


def test_one_unreadable_subschema_refuses_the_whole_table():
    """The refusal is not per-argument, and that is what makes the caller's row honest.

    A table holding the arguments that happened to be readable would be reported as the tool's
    arguments, and the ones dropped from it would read downstream as removed.
    """
    schema = {
        "type": "object",
        "properties": {"page_id": {"type": "string"}, "title": True},
        "required": ["page_id"],
    }

    assert read_arguments(schema) is None


def test_a_refused_table_becomes_a_row_the_caller_can_count():
    """The claim `arguments.py` opens with, asserted on what `fetch_changes` returns.

    Two tools are refused for two different reasons -- `properties` as an array and a boolean
    subschema -- and each produces exactly one row naming the tool, at `info`, because a blind
    spot that is countable is the whole point of refusing rather than reading.
    """
    for tool in ("list_pages", "rename_page"):
        rows = _rows(tool)

        assert [c.kind for c in rows] == [SCHEMA_NOT_COMPARABLE]
        assert rows[0].severity == "info"
        assert tool in rows[0].raw["text"]


# --------------------------------------------------------------------------------------------
# _accepted_types refuses one argument's types, and the caller makes nothing of it.
# --------------------------------------------------------------------------------------------


def test_a_composed_subschema_yields_no_types_even_when_it_names_one():
    """`arguments.py:89`. The argument is still read; only its types are not.

    Presence and required-ness live at the top level and survive a subschema that composes, so
    refusing the whole table here would lose two readable facts to buy nothing. `types` is
    `None` rather than empty because empty would read as "accepts nothing".

    The subschema names a `type` *and* composes, which is the only shape that makes this
    statement matter. A subschema that composes and names no type falls through to the same
    `None` one line further down, so a fixture without the `type` would pass whether or not this
    branch existed. Here the composition can only narrow what `type` allows -- `anyOf` is an
    intersection with it -- so reading `"string"` off the top would be a confident wrong answer
    rather than an incomplete one.
    """
    subschema = {"type": "string", "anyOf": [{"const": "json"}]}
    table = read_arguments({"type": "object", "properties": {"format": subschema}})

    assert table is not None
    assert table.arguments["format"].types is None


def test_a_subschema_naming_no_type_yields_no_types():
    """`arguments.py:95`, reached three ways: no `type`, a `type` that is not a string, and a
    list with a non-string member. All three are unreadable in the same way and all three have
    to answer `None` rather than a guess."""
    for subschema in ({"description": "no type here"}, {"type": 7}, {"type": ["string", 3]}):
        table = read_arguments({"type": "object", "properties": {"scope": subschema}})

        assert table is not None
        assert table.arguments["scope"].types is None


def test_an_argument_whose_types_became_unreadable_produces_no_row_at_all():
    """The refusal the caller does *not* turn into a row, and the honest limit of the adapter.

    `export_page` narrows `format` from `["string", "null"]` to `anyOf: [{"type": "string"}]`,
    and `archive_page` drops `scope`'s type altogether. Both tools changed, both changes are
    unreadable, and `fetch_changes` reports neither -- so a scan of this pair is
    indistinguishable from a scan of two tools that did not move.

    This is not a bug to fix here. `_types_narrowed` cannot emit on an unreadable type without
    emitting on every description edit to an untyped property, and telling those apart is schema
    subsumption -- which `arguments.py` correctly declines. It is pinned because the module's
    opening paragraph promises a refusal becomes a row, and for these two statements it does not.
    """
    assert _rows("export_page") == []
    assert _rows("archive_page") == []


def test_only_the_refused_tables_produce_rows():
    """Asserted over the whole pair, so an emission from either silent refusal fails here.

    Written as an exhaustive comparison rather than several separate absence checks: an absence
    check passes when the differ stops emitting entirely, and this does not.
    """
    changes = list(_adapter().fetch_changes(BEFORE, AFTER))

    assert sorted((c.operation_id, c.kind) for c in changes) == [
        ("find_pages", SCHEMA_NOT_COMPARABLE),
        ("list_pages", SCHEMA_NOT_COMPARABLE),
        ("rename_page", SCHEMA_NOT_COMPARABLE),
    ]


# --------------------------------------------------------------------------------------------
# A `required` that is not a list, which was read rather than refused.
# --------------------------------------------------------------------------------------------


def test_a_required_that_is_not_a_list_is_refused():
    """The third malformed shape in `read_arguments`, which used to be coerced instead.

    `properties` that is not an object and a subschema that is not an object are both refused.
    A `required` that is not an array was read as an empty set, which is not "we could not read
    this" but "this server requires nothing" -- a confident claim about the one fact besides
    presence that this module says it reads.
    """
    schema = {"type": "object", "properties": {"query": {"type": "string"}}, "required": "query"}

    assert read_arguments(schema) is None


def test_a_server_that_only_corrected_its_required_spelling_breaks_nobody():
    """The defect the refusal above closes, stated as the row a caller used to get.

    `find_pages` requires `query` in both captures. The first spells `required` as a string,
    which is malformed JSON Schema, and the second spells it as an array. Nothing about what the
    server accepts changed. Read rather than refused, the first capture says nothing is required
    and the second says `query` is, so the differ emitted
    `mcp-tool-required-argument-added` at `breaking` -- a fabricated breaking change telling a
    customer to start passing an argument they were already passing, and one that would drive a
    remediation pull request against working code.

    An `info` row naming the tool as unreadable is the answer that is true: the schema did change
    and this differ cannot say what it means.
    """
    rows = _rows("find_pages")

    assert [(c.kind, c.severity) for c in rows] == [(SCHEMA_NOT_COMPARABLE, "info")]


# --------------------------------------------------------------------------------------------
# snapshot.py refuses loudly, and nothing between here and `main` catches it.
# --------------------------------------------------------------------------------------------


def test_a_response_with_no_result_object_raises_rather_than_reading_as_an_empty_catalogue():
    """`snapshot.py:53`. A JSON-RPC error response has no `result`, and no tools is not zero tools.

    The capture is the whole envelope, so a server that answered `tools/list` with an error is on
    disk looking exactly like a server that answered with an empty list. Read as the latter it
    withdraws the entire catalogue -- the largest false positive this adapter can produce.
    """
    with pytest.raises(ValueError, match="carries no tools/list result object"):
        parse_snapshot({"jsonrpc": "2.0", "id": 1, "error": {"code": -32603}}, "capture.json")


def test_a_payload_that_is_not_an_object_at_all_raises_at_the_same_boundary():
    """The same statement, reached by the other route: `payload.get` is never called on a
    non-mapping, so a capture holding a bare array or a string refuses here rather than raising
    `AttributeError` somewhere less legible."""
    for payload in ([], "null", 7, None):
        with pytest.raises(ValueError, match="carries no tools/list result object"):
            parse_snapshot(payload, "capture.json")


def test_the_refusal_names_the_capture_it_came_from():
    """The message is the whole of what an operator gets, because nothing catches it.

    `fetch_changes` is permitted to raise -- `sync.core.conformance._check_fetch_changes` says so
    explicitly -- and no handler exists between `McpServerAdapter` and `main`, so this text is
    what lands on a terminal. A refusal that did not name the file would leave an operator with a
    directory of captures and no way to tell which one is bad.
    """
    adapter = _adapter()

    with pytest.raises(ValueError) as raised:
        list(adapter.fetch_changes("error_response", AFTER))

    assert "tools_list_error_response.json" in str(raised.value)


def test_a_duplicated_tool_name_refuses_the_whole_capture():
    """`snapshot.py:73`. Two definitions, one name, and no defensible way to pick.

    The specification says tool names **SHOULD** be unique within a server and calls `name` the
    tool's unique identifier, but the JSON schema puts no `uniqueItems` on the array, so a
    duplicate is non-conformant rather than unparseable. It has to be answered somewhere, and
    keeping either definition would be a tie-break: the reference implementation does not agree
    with itself on which wins -- `ToolManager.add_tool` keeps the first, its constructor keeps the
    last -- and servers are only told they **SHOULD** return tools in a deterministic order. A
    row derived from an arbitrary tie-break over an order the server need not hold stable is a
    row that does not converge, which is the one thing `CLAUDE.md` does not permit a stage to do.
    """
    with pytest.raises(ValueError, match="advertises 'search_docs' twice"):
        list(_adapter().fetch_changes("duplicate_tool", AFTER))


def test_neither_duplicate_definition_is_quietly_chosen():
    """The assertion that would fail if the refusal became a skip or a last-one-wins.

    The fixture's two `search_docs` definitions differ -- the second requires `space_id` -- so
    keeping the first, keeping the last, and dropping the tool each produce a different and
    visible answer. Nothing is returned, which is the only answer that does not invent one.
    """
    with pytest.raises(ValueError):
        list(_adapter().fetch_changes("duplicate_tool", AFTER))

    # get_page is well-formed and in the same capture: the refusal is the whole snapshot, so a
    # readable tool beside a duplicated one is not reported either.
    with pytest.raises(ValueError):
        load_snapshot(FIXTURES, "duplicate_tool")


def test_a_row_keeps_the_advertised_description_byte_for_byte():
    """`CLAUDE.md`: keep the raw vendor record, and read it with an explicit encoding.

    `rename_page`'s description is the one non-ASCII fixture in this repository, and it is on a
    tool that emits, so the string travels the whole path a real capture does: `read_text` in
    `load_snapshot`, pydantic, `model_dump`, and into `raw`. cp1252 -- this machine's locale
    codepage -- decodes those bytes without raising and yields mojibake, so a `read_text` that
    forgot its encoding would store a corrupted record and no exception. Asserting on the
    recovered string is the only thing that sees it; asserting the read succeeded would not.
    """
    row = _rows("rename_page")[0]

    assert row.raw["before"]["description"] == RENAME_DESCRIPTION
    assert row.raw["after"]["description"] == RENAME_DESCRIPTION

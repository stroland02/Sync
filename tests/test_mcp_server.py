"""The stdio transport, driven the way a client drives it: bytes in, bytes out.

There is no live agent here and there does not need to be one. MCP over stdio is JSON-RPC 2.0
in newline-delimited frames, so a client is exactly a writer of request lines and a reader of
response lines -- which a test can be. What cannot be tested this way is whether a *particular*
agent likes the schemas, and no unit test could establish that anyway.

The transport is asserted to hold no logic of its own: every tool response must be what
`dispatch` already returns, and the server's job is framing, routing and error translation.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.mcp.registry import TOOL_NAMES
from sync.mcp.server import PROTOCOL_VERSION, serve
from sync.mcp.tools import GraphSurface

INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)


class FakeGraph:
    def open_findings(self) -> list[Finding]:
        return [
            Finding(
                id="f-1", detector="vendor_change", claim="response-field",
                call_site_id="site-1",
                vendor_change_id="chg-1", severity="breaking", rationale="why",
            )
        ]

    def get_call_site(self, call_site_id: str) -> CallSite:
        return CallSite(
            id="site-1", repo_id="r", path="src/pay.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create",
            args_keys=["amount"], response_fields_read=["status"],
            sdk_version="18.0.0", content_hash="h", indexed_at=INDEXED,
        )

    def get_vendor_change(self, change_id: str) -> VendorChange:
        return self.all_vendor_changes("stripe")[0]

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        if vendor_id != "stripe":
            return []
        return [
            VendorChange(
                id="chg-1", vendor_id="stripe", from_version="v1", to_version="v2",
                kind="response-property-removed", operation_id="PostCharges",
                path_ptr="/v1/charges", severity="breaking", source="oasdiff", raw={},
            )
        ]


def _talk(*requests: dict) -> list[dict]:
    """Drive one server run over a scripted stdin, and parse what it wrote."""
    stdin = io.StringIO("".join(json.dumps(r) + "\n" for r in requests))
    stdout = io.StringIO()
    serve(GraphSurface(FakeGraph()), stdin=stdin, stdout=stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def _req(id_, method, params=None):
    body = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    return body


def test_initialize_answers_with_the_protocol_version_and_a_tools_capability():
    (response,) = _talk(_req(1, "initialize", {"protocolVersion": PROTOCOL_VERSION}))
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert "tools" in response["result"]["capabilities"]
    assert response["result"]["serverInfo"]["name"] == "sync"


def test_tools_list_publishes_all_four_with_their_argument_schemas():
    """An agent composes against this payload, so the arguments have to be in it."""
    (response,) = _talk(_req(1, "tools/list"))
    tools = response["result"]["tools"]
    assert [t["name"] for t in tools] == list(TOOL_NAMES)
    by_name = {t["name"]: t for t in tools}
    assert by_name["sync_explain_call_site"]["inputSchema"]["required"] == ["file", "line"]
    assert "limit" in by_name["sync_whats_at_risk"]["inputSchema"]["properties"]


def test_a_tool_call_returns_what_the_surface_returned_and_nothing_added():
    """The transport frames a result; it does not reshape one.

    Anything the transport computed would be logic living where the tests for that logic
    are not, so the structured payload must be `dispatch`'s return value verbatim.
    """
    from sync.mcp.registry import dispatch

    (response,) = _talk(_req(7, "tools/call", {"name": "sync_whats_at_risk", "arguments": {}}))
    expected = dispatch(GraphSurface(FakeGraph()), "sync_whats_at_risk", {})
    assert response["id"] == 7
    assert response["result"]["structuredContent"] == expected
    assert response["result"]["isError"] is False


def test_a_tool_call_also_carries_text_content_for_clients_that_only_read_text():
    (response,) = _talk(_req(1, "tools/call", {"name": "sync_whats_changed",
                                               "arguments": {"vendor": "stripe"}}))
    content = response["result"]["content"]
    assert content[0]["type"] == "text"
    assert json.loads(content[0]["text"])["items"][0]["operation"] == "PostCharges"


def test_arguments_reach_the_tool():
    (response,) = _talk(_req(1, "tools/call", {"name": "sync_explain_call_site",
                                               "arguments": {"file": "src/pay.ts", "line": 12}}))
    assert response["result"]["structuredContent"]["symbol"] == "stripe.charges.create"


def test_a_tool_that_answers_none_is_a_result_rather_than_an_error():
    """"Nothing here" is an answer. Reporting it as a protocol error teaches an agent to retry."""
    (response,) = _talk(_req(1, "tools/call", {"name": "sync_explain_call_site",
                                               "arguments": {"file": "nope.ts", "line": 1}}))
    assert "error" not in response
    assert response["result"]["structuredContent"] is None
    assert response["result"]["isError"] is False


def test_an_unknown_tool_comes_back_as_a_tool_error_not_a_crash():
    (response,) = _talk(_req(4, "tools/call", {"name": "sync_nope", "arguments": {}}))
    assert response["id"] == 4
    assert response["result"]["isError"] is True
    assert "sync_nope" in response["result"]["content"][0]["text"]


def test_a_bad_argument_comes_back_as_a_tool_error_naming_the_problem():
    """The agent can fix this one, so it must be told rather than handed a dead connection.

    A generic "the tool failed" would also be an error result and would be useless: the whole
    value here is that the agent learns its call was malformed rather than that the server is
    broken, so the message has to say which. That distinction is the assertion.
    """
    (response,) = _talk(_req(1, "tools/call", {"name": "sync_whats_changed",
                                               "arguments": {"sinse": "2026-01-01"}}))
    assert response["result"]["isError"] is True
    message = response["result"]["content"][0]["text"]
    assert "bad arguments" in message
    assert "sinse" in message
    assert "sync_whats_changed" in message


def test_an_unknown_method_is_a_json_rpc_error_with_the_documented_code():
    """The example changed and the property did not. This asked for `resources/read`, which was
    an unknown method only because `sync://feed/{vendor}` did not exist yet; the server now
    serves it, so an unimplemented method is what the assertion needs. `prompts/list` is the
    next thing an MCP client tries and the next thing this server does not do.
    """
    (response,) = _talk(_req(9, "prompts/list"))
    assert response["id"] == 9
    assert response["error"]["code"] == -32601


def test_a_malformed_line_is_a_parse_error_that_does_not_end_the_session():
    """One bad frame must not take the connection down; the next request still answers."""
    stdin = io.StringIO("{not json\n" + json.dumps(_req(2, "tools/list")) + "\n")
    stdout = io.StringIO()
    serve(GraphSurface(FakeGraph()), stdin=stdin, stdout=stdout)
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    assert responses[0]["error"]["code"] == -32700
    assert responses[0]["id"] is None
    assert responses[1]["id"] == 2


def test_a_notification_is_not_answered():
    """A JSON-RPC request without an id takes no response, and answering one is a protocol bug."""
    responses = _talk({"jsonrpc": "2.0", "method": "notifications/initialized"},
                      _req(3, "tools/list"))
    assert [r["id"] for r in responses] == [3]


def test_every_response_is_exactly_one_line_so_a_client_can_frame_on_newlines():
    """Framing is the whole contract of a newline-delimited transport.

    A pretty-printed frame is valid JSON and an unreadable stream, and the failure shows up
    at the client as a parse error on a payload that looks fine in a log.
    """
    stdin = io.StringIO(
        json.dumps(_req(1, "tools/list")) + "\n"
        + json.dumps(_req(2, "tools/call", {"name": "sync_whats_at_risk", "arguments": {}})) + "\n"
    )
    stdout = io.StringIO()
    serve(GraphSurface(FakeGraph()), stdin=stdin, stdout=stdout)

    raw = stdout.getvalue()
    assert raw.endswith("\n")
    lines = raw.splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == [1, 2]


def test_the_server_never_offers_a_tool_that_writes():
    """The published surface is three reads and one patch proposal. Nothing else exists."""
    (response,) = _talk(_req(1, "tools/list"))
    names = [t["name"] for t in response["result"]["tools"]]
    assert not any(word in name for name in names for word in ("push", "commit", "write", "open_pr"))

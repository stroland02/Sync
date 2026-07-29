"""MCP over stdio: newline-delimited JSON-RPC 2.0, and nothing else.

The transport translates a tool call into a `GraphSurface` method and its return value into a
response. It holds no logic of its own, deliberately: anything computed here would be behaviour
living where the tests for that behaviour are not, and `tools/call` therefore returns exactly
what `sync.mcp.registry.dispatch` returned.

**Why the protocol is written out rather than taken from the MCP SDK.** The `mcp` package is
present in this environment only as a transitive dependency of `claude-agent-sdk`, and
`pyproject.toml` already carries a comment about that exact hazard for `pyyaml`: a transitive
dependency can vanish in a bump. Declaring it is another worker's file to edit. The framing is
newline-delimited JSON-RPC, which is a few dozen lines, and writing it keeps this package free
of a dependency it does not declare -- and keeps the transport testable by handing it two
string buffers.

**Why stdio.** `2026-07-25-sync-graph-surface-design.md` settles this as an identity decision
rather than a plumbing one: stdio inherits the machine's identity, so a laptop-local server
needs no per-user principal, and no credential is held. Sync does not need one until it has
organizations, which is M4.

**The server never writes to the customer's repository.** Three of the four tools only read the
graph, and the fourth stops before `push_branch`. There is no tool that pushes, commits, or
opens a pull request, and a test asserts the published names cannot be one.

Error handling splits along the line an agent cares about. A malformed frame or an unknown
method is a JSON-RPC-level error, because the agent's request never reached a tool. A tool that
refused its arguments is a *result* carrying `isError`, because the agent can fix that and
retry -- which is what the MCP specification asks for, and what stops a fixable mistake from
looking like a dead server.
"""

from __future__ import annotations

import json
import sys
from typing import Any, IO

from sync.mcp.registry import dispatch, schemas_as_data
from sync.mcp.resources import (
    FEED_MIME_TYPE,
    ResourceError,
    read as read_resource,
    resource_templates_as_data,
    resources_as_data,
)
from sync.signals.feed.cache import FeedCache
from sync.mcp.tools import GraphSurface

# The revision of the MCP protocol these frames conform to. Reported back at initialize so a
# client can refuse a server it cannot speak to, rather than discovering the mismatch per call.
PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "sync"
SERVER_VERSION = "0.1.0"

_PARSE_ERROR = -32700
_METHOD_NOT_FOUND = -32601
_INTERNAL_ERROR = -32603
# What the MCP specification uses for a resource that is not there. A resource read that cannot
# be answered is not a tool failure and has no `isError` to carry: `tools/call` returns a result
# because the agent can fix its arguments and retry, and a feed nobody has fetched is not
# something the agent's next frame can repair.
_RESOURCE_NOT_FOUND = -32002


def serve(
    surface: GraphSurface,
    stdin: IO[str] | None = None,
    stdout: IO[str] | None = None,
    feed: FeedCache | None = None,
) -> None:
    """Read requests until the stream ends, answering each on one line.

    Reads from and writes to the streams handed in, which is what lets a test be the client:
    a client is a writer of request lines and a reader of response lines, and nothing about
    that requires a process boundary.

    `feed` is separate from `surface` and deliberately so. The graph is the customer's private
    data and the feed is vendor-side public information, and
    `2026-07-25-sync-graph-surface-design.md` draws that line as a data boundary rather than a
    packaging one -- so the resource is handed a cache and no store, and there is nothing here
    for it to reach the graph with.
    """
    source = stdin if stdin is not None else sys.stdin
    sink = stdout if stdout is not None else sys.stdout

    for line in source:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            # `id` is unknowable for a frame that did not parse, and JSON-RPC says to answer
            # null rather than to guess or to stay silent.
            _write(sink, _error(None, _PARSE_ERROR, f"invalid JSON: {exc}"))
            continue

        response = _handle(surface, request, feed)
        if response is not None:
            _write(sink, response)


def _handle(
    surface: GraphSurface, request: dict[str, Any], feed: FeedCache | None = None
) -> dict[str, Any] | None:
    """One request to one response, or `None` for a notification.

    A JSON-RPC request with no `id` is a notification and takes no reply. `initialized` is one,
    and answering it is a protocol violation rather than a harmless extra.
    """
    request_id = request.get("id")
    method = request.get("method")

    if request_id is None:
        return None

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    # `subscribe` is false rather than absent: a feed changes when something
                    # fetches one, this server fetches nothing, and advertising a subscription
                    # it can never notify on would have a client wait for an event.
                    "resources": {"listChanged": False, "subscribe": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "tools/list":
        return _result(request_id, {"tools": schemas_as_data()})

    if method == "tools/call":
        return _call(surface, request_id, request.get("params") or {})

    if method == "resources/list":
        return _result(request_id, {"resources": resources_as_data(feed, _known_vendors())})

    if method == "resources/templates/list":
        return _result(request_id, {"resourceTemplates": resource_templates_as_data()})

    if method == "resources/read":
        return _read(request_id, request.get("params") or {}, feed)

    return _error(request_id, _METHOD_NOT_FOUND, f"unknown method: {method}")


def _known_vendors() -> tuple[str, ...]:
    """Which vendor ids exist, from the one place that answers it.

    Read through the registry rather than kept here, so a vendor added by configuration is
    offered by this server without a second edit -- and so "unknown vendor" cannot come to mean
    two different things in two files.
    """
    from sync.signals.registry import available_vendors

    return available_vendors()


def _read(request_id: Any, params: dict[str, Any], feed: FeedCache | None) -> dict[str, Any]:
    """One resource read, or a JSON-RPC error carrying which of the outcomes it was.

    The reason travels in `error.data` rather than only in the message. A client branching on
    wording breaks when the wording improves, and the difference between a vendor nobody
    registers and a vendor nobody has fetched is the difference between fixing a typo and
    running a fetch.
    """
    try:
        contents = read_resource(params.get("uri") or "", feed, _known_vendors())
    except ResourceError as exc:
        return _error(request_id, _RESOURCE_NOT_FOUND, str(exc), data=exc.data)

    return _result(
        request_id,
        {
            "contents": [
                {
                    "uri": params.get("uri"),
                    "mimeType": FEED_MIME_TYPE,
                    "text": json.dumps(contents),
                }
            ]
        },
    )


def _call(surface: GraphSurface, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    try:
        payload = dispatch(surface, name, arguments)
    except KeyError:
        return _tool_error(request_id, f"unknown tool: {name}")
    except TypeError as exc:
        # An argument the tool does not declare. The agent can correct this, so it is a tool
        # result rather than a protocol error -- a protocol error reads as a broken server.
        return _tool_error(request_id, f"bad arguments for {name}: {exc}")
    except Exception as exc:  # noqa: BLE001 - a tool fault must not take the session down
        return _tool_error(request_id, f"{name} failed: {type(exc).__name__}: {exc}")

    return _result(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "structuredContent": payload,
            "isError": False,
        },
    )


def _tool_error(request_id: Any, message: str) -> dict[str, Any]:
    return _result(
        request_id,
        {"content": [{"type": "text", "text": message}], "structuredContent": None, "isError": True},
    )


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _write(sink: IO[str], payload: dict[str, Any]) -> None:
    """One frame, one line.

    `json.dumps` never emits a bare newline, so the separator cannot appear inside a frame and
    a client can split the stream on it. Flushing per frame is what makes the server usable
    over a pipe: a buffered response is a hang the client cannot distinguish from slow work.
    """
    sink.write(json.dumps(payload) + "\n")
    sink.flush()


def main() -> int:
    """Entry point for a stdio server over the local graph.

    Deliberately read-only: no repository, no adapter and no remediator are configured here, so
    `sync_propose_patch` reports itself unavailable rather than running a pipeline against a
    checkout this entry point never established. Wiring those is the caller's decision, because
    which checkout is served is a deployment fact and not a default.

    The feed cache starts empty and this entry point never fills it. Fetching a published feed
    is the operational half the feed specification puts outside the architecture, alongside the
    keypair and the publish job -- so `sync://feed/{vendor}` answers "no verified feed has been
    fetched" until something fetches one, which is the honest answer and not the same as an
    empty feed.

    It is built with the committed development key, because that is the only key in this
    repository. When a production key replaces the literal in `sync.core.keys`, this picks it up
    by upgrading, which is what "rotatable only through a release" means.

    Two things about the streams, both of which decide whether a client sees a working server or
    a protocol bug.

    **Stdout is the protocol and nothing else.** The real stream is taken here and handed to
    `serve`, and `sys.stdout` is pointed at stderr for the rest of the process. Anything that
    writes to stdout without being the transport -- a `print` left in a code path, a library
    banner, a logging handler somebody configures later -- then lands where it is readable
    instead of in the middle of a frame. A corrupted frame is reported by the client as a
    protocol error, which sends the search to the framing code, which is not where the bug is.

    **Both streams are read and written as UTF-8.** Python decodes stdin with the machine's
    locale codepage, which on Windows is cp1252, so a request carrying a non-ASCII path or
    symbol arrives mangled and is answered about a string the client never sent. `json.dumps`
    escapes non-ASCII on the way out, so the corruption is silent in both directions.
    """
    from sync.core import DEVELOPMENT_FEED_PUBLIC_KEY
    from sync.graph.store import GraphStore

    import os

    dsn = os.environ.get("SYNC_DSN")
    if not dsn:
        print("SYNC_DSN is not set", file=sys.stderr)
        return 2

    protocol = sys.stdout
    sys.stdin.reconfigure(encoding="utf-8")
    protocol.reconfigure(encoding="utf-8")
    sys.stdout = sys.stderr

    serve(
        GraphSurface(GraphStore(dsn)),
        stdout=protocol,
        feed=FeedCache(public_key=DEVELOPMENT_FEED_PUBLIC_KEY),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

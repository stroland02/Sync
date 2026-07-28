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
from sync.mcp.tools import GraphSurface

# The revision of the MCP protocol these frames conform to. Reported back at initialize so a
# client can refuse a server it cannot speak to, rather than discovering the mismatch per call.
PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "sync"
SERVER_VERSION = "0.1.0"

_PARSE_ERROR = -32700
_METHOD_NOT_FOUND = -32601
_INTERNAL_ERROR = -32603


def serve(surface: GraphSurface, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> None:
    """Read requests until the stream ends, answering each on one line.

    Reads from and writes to the streams handed in, which is what lets a test be the client:
    a client is a writer of request lines and a reader of response lines, and nothing about
    that requires a process boundary.
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

        response = _handle(surface, request)
        if response is not None:
            _write(sink, response)


def _handle(surface: GraphSurface, request: dict[str, Any]) -> dict[str, Any] | None:
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
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "tools/list":
        return _result(request_id, {"tools": schemas_as_data()})

    if method == "tools/call":
        return _call(surface, request_id, request.get("params") or {})

    return _error(request_id, _METHOD_NOT_FOUND, f"unknown method: {method}")


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


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


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
    """
    from sync.graph.store import GraphStore

    import os

    dsn = os.environ.get("SYNC_DSN")
    if not dsn:
        print("SYNC_DSN is not set", file=sys.stderr)
        return 2
    serve(GraphSurface(GraphStore(dsn)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

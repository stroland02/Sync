"""One capture of a server's `tools/list` response, read and checked before anything uses it.

Parsing is delegated to `mcp.types.ListToolsResult` rather than hand-rolled. The `mcp` package
is already resolved in the lockfile at 1.28.1, its models are the reference implementation of
the same schema the servers are written against, and hand-rolling would mean maintaining a
second opinion about a wire format we do not own. What it buys concretely: `inputSchema` and
`name` are required, so a malformed capture fails here instead of producing a tool with no
arguments; `extra="allow"` on `Tool` means a field added by a newer protocol revision is
carried rather than rejected; and `nextCursor` is modelled, which is the check below that
matters most.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import ListToolsResult, Tool
from pydantic import ValidationError

SNAPSHOT_FILENAME = "tools_list_{version}.json"
"""How a capture is named inside the snapshot directory.

The version segment is whatever the capturing step chose to call this capture -- see
`McpServerAdapter` on why that string is ours and not the server's.
"""


def load_snapshot(snapshot_dir: Path, version: str) -> dict[str, Tool]:
    """Every tool one capture advertised, keyed by name.

    A missing file raises. It cannot be read as "the server advertised nothing", because that
    is what a total outage looks like and it is the single most damaging thing this adapter
    could conclude quietly.
    """
    path = Path(snapshot_dir) / SNAPSHOT_FILENAME.format(version=version)
    if not path.exists():
        raise FileNotFoundError(f"no tools/list capture at {path}")
    return parse_snapshot(json.loads(path.read_text(encoding="utf-8")), str(path))


def parse_snapshot(payload: Any, source: str) -> dict[str, Tool]:
    """The tools in a captured JSON-RPC response, or a refusal naming what is wrong.

    The capture is the whole response envelope and not just its `result`, because the envelope
    is the record the server actually sent and `CLAUDE.md` requires keeping the source, not the
    interpretation of it. An error response has no `result` and is refused here rather than
    read as an empty catalogue.
    """
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise ValueError(f"{source} carries no tools/list result object")

    try:
        listing = ListToolsResult.model_validate(result)
    except ValidationError as error:
        raise ValueError(f"{source} is not a valid tools/list result: {error}") from error

    if listing.nextCursor is not None:
        # Every tool past this page is absent from the capture, and absent is how the differ
        # reads a removal. Diffing a truncated page would withdraw the server's whole
        # catalogue -- a false positive manufactured by our own capture step, and one nothing
        # downstream could tell from the real thing.
        raise ValueError(
            f"{source} is one page of a paginated tools/list (nextCursor is set); "
            "capture every page before diffing"
        )

    tools: dict[str, Tool] = {}
    for tool in listing.tools:
        if tool.name in tools:
            raise ValueError(f"{source} advertises '{tool.name}' twice")
        tools[tool.name] = tool
    return tools

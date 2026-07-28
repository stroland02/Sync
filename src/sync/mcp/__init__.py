"""The graph surface: Sync's four tools, exposed to an agent over stdio."""

from sync.mcp.registry import TOOL_NAMES, TOOLS, ToolSpec, dispatch, schemas_as_data
from sync.mcp.server import PROTOCOL_VERSION, serve
from sync.mcp.tools import DEFAULT_LIMIT, GraphReader, GraphSurface

__all__ = [
    "DEFAULT_LIMIT",
    "PROTOCOL_VERSION",
    "TOOLS",
    "TOOL_NAMES",
    "GraphReader",
    "GraphSurface",
    "ToolSpec",
    "dispatch",
    "schemas_as_data",
    "serve",
]

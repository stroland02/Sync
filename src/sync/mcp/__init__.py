"""The graph surface: Sync's four tools, exposed to an agent over stdio."""

from sync.mcp.registry import TOOL_NAMES, TOOLS, ToolSpec, dispatch, schemas_as_data
from sync.mcp.resources import (
    FEED_URI_TEMPLATE,
    RESOURCE_TEMPLATES,
    ResourceError,
    ResourceTemplateSpec,
    resource_templates_as_data,
    resources_as_data,
)
from sync.mcp.server import PROTOCOL_VERSION, serve
from sync.mcp.tools import DEFAULT_LIMIT, GraphReader, GraphSurface

__all__ = [
    "DEFAULT_LIMIT",
    "FEED_URI_TEMPLATE",
    "PROTOCOL_VERSION",
    "RESOURCE_TEMPLATES",
    "TOOLS",
    "TOOL_NAMES",
    "GraphReader",
    "GraphSurface",
    "ResourceError",
    "ResourceTemplateSpec",
    "ToolSpec",
    "dispatch",
    "resource_templates_as_data",
    "resources_as_data",
    "schemas_as_data",
    "serve",
]

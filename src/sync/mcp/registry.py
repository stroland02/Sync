"""The four tools as data: names, descriptions, argument schemas, and where each one lands.

An agent composes a call against a schema, never against a docstring, so every argument is
declared here with its type and its meaning. `tests/golden/tool_schemas.json` pins the result.

`docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` freezes the tool set on first
publish: the set may grow and arguments may be added, but nothing may be removed or renamed.
Keeping the schemas as plain data rather than deriving them from signatures is what makes that
rule checkable -- a golden file can diff data, and cannot diff a decorator's behaviour.

Dispatch is deliberately unforgiving about argument names. An agent that misspells `since` has
asked a different question from the one it believes it asked, and answering anyway returns a
plausible result for the wrong query.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sync.mcp.tools import DEFAULT_LIMIT, GraphSurface

_LIMIT = {
    "type": "integer",
    "description": f"Maximum rows to return. Defaults to {DEFAULT_LIMIT}.",
}
_OFFSET = {
    "type": "integer",
    "description": "Index of the first row to return. Use the `next_offset` of the previous page.",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="sync_whats_at_risk",
        description=(
            "Call sites in this repository that an open finding touches, with the operation "
            "each one depends on and the kind of change that hit it. Returns bindings, never "
            "file contents."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Restrict to call sites whose path starts with this prefix.",
                },
                "vendor": {
                    "type": "string",
                    "description": "Restrict to one vendor, for example `stripe`.",
                },
                "severity": {
                    "type": "string",
                    "description": "Restrict to findings of this severity, for example `breaking`.",
                },
                "limit": _LIMIT,
                "offset": _OFFSET,
            },
            "required": [],
        },
        handler=GraphSurface.whats_at_risk,
    ),
    ToolSpec(
        name="sync_explain_call_site",
        description=(
            "One call site in full: the symbol it calls, the operation it resolves to, the "
            "arguments it passes and the response fields it reads, plus shallow references to "
            "the vendor changes affecting it. Null when the graph holds no such call site."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Repository-relative path, for example `src/billing.ts`.",
                },
                "line": {
                    "type": "integer",
                    "description": "One-based line number of the call site.",
                },
            },
            "required": ["file", "line"],
        },
        handler=GraphSurface.explain_call_site,
    ),
    ToolSpec(
        name="sync_whats_changed",
        description=(
            "What a vendor changed between the versions Sync has recorded, whether or not this "
            "repository is affected. An unknown vendor is an empty page rather than an error."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor": {
                    "type": "string",
                    "description": "Vendor identifier, for example `stripe`.",
                },
                "since": {
                    "type": "string",
                    "description": "ISO-8601 timestamp; return only changes detected at or after it.",
                },
                "limit": _LIMIT,
                "offset": _OFFSET,
            },
            "required": ["vendor"],
        },
        handler=GraphSurface.whats_changed,
    ),
    ToolSpec(
        name="sync_propose_patch",
        description=(
            "Run the remediation pipeline for one finding as far as static verification and "
            "return the diff, the verification result and the evidence. Never writes to the "
            "repository: no branch is created, nothing is pushed, and no pull request is opened."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "Identifier of an open finding, as returned by sync_whats_at_risk.",
                },
            },
            "required": ["finding_id"],
        },
        handler=GraphSurface.propose_patch,
    ),
)

TOOL_NAMES: tuple[str, ...] = tuple(tool.name for tool in TOOLS)

_BY_NAME = {tool.name: tool for tool in TOOLS}


def schemas_as_data() -> list[dict[str, Any]]:
    """The published surface, in the shape the golden file stores and a client receives."""
    return [
        {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
        for tool in TOOLS
    ]


def dispatch(surface: GraphSurface, name: str, arguments: dict[str, Any]) -> Any:
    """Call the tool `name` on `surface`, or fail naming what was asked for.

    `KeyError` for an unknown tool and `TypeError` for an unknown argument, both raised by
    Python itself rather than translated: the transport turns them into protocol errors, and
    doing that here would put the transport's concerns in the registry.
    """
    tool = _BY_NAME.get(name)
    if tool is None:
        raise KeyError(name)
    return tool.handler(surface, **arguments)

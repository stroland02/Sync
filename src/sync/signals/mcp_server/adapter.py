"""An MCP server implementing the `VendorAdapter` protocol, and where the fit is imperfect.

The design document's claim is that an MCP server is structurally easier than a REST vendor,
because it publishes its contract on request: no specification to locate, no changelog to
parse, no SDK symbol scheme to derive. `tools/list` hands back the schemas. Half of that holds
and the interesting half does not, and both halves are documented here rather than in a
separate note, because the next person to write one of these will start from this file.

A server has no versions, so `from_version` and `to_version` are ours
---------------------------------------------------------------------
`fetch_changes(from_version, to_version)` assumes two comparable published states. A REST
vendor has them: a Stripe tag names a file anybody can fetch, and a row derived from it can be
re-derived by anyone who fetches the same tag. An MCP server has exactly one state -- whatever
it advertises when you ask -- and no way to ask what it advertised in June.

So the version axis here is a *capture identifier*: a name the capturing step minted for one
snapshot it took and wrote to disk. The protocol still fits, and three things follow that do
not apply to any other adapter in this repository.

- **Nothing else can reproduce a row.** For Stripe, the two versions are public, so a stored
  finding is checkable against the vendor. Here the evidence exists only in our snapshot
  directory. Losing a snapshot loses the ability to explain a row, permanently. That is why
  `raw` carries both tool definitions in full rather than a summary of the difference: the
  stored row has to be self-sufficient, because there is nothing to re-fetch.
- **Two deployments' capture ids are unrelated.** `2026-06-01` means one deployment's June
  capture and nothing more; it is not a name two customers could compare.
- **Capture cadence sets detection latency, and we set the cadence.** With a REST vendor a
  release is an event we can watch for. Here the only way to notice a change is to capture
  again and diff, so nothing between two captures is ever seen -- a tool removed and restored
  between them leaves no trace at all.

What `since` would mean, if the protocol asked for it, is therefore "since the snapshot we
took", never "since a state the vendor would recognise".

There is no call site to bind to
--------------------------------
See `operation_for_symbol`. It always returns `None`, and unlike the two other adapters that
do the same, no other indexer covers for it. This adapter produces real changes that currently
attach to nothing, and that is the honest state of it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from mcp.types import Tool

from sync.core import ChangeSource, OperationRef, VendorChange
from sync.signals.mcp_server.arguments import ArgumentTable, read_arguments
from sync.signals.mcp_server.snapshot import load_snapshot

TOOL_REMOVED = "mcp-tool-removed"
REQUIRED_ARGUMENT_ADDED = "mcp-tool-required-argument-added"
ARGUMENT_REMOVED = "mcp-tool-argument-removed"
ARGUMENT_TYPE_NARROWED = "mcp-tool-argument-type-narrowed"
SCHEMA_NOT_COMPARABLE = "mcp-tool-schema-not-comparable"

VENDOR_ID_PREFIX = "mcp:"
"""What keeps a server's tools out of a REST vendor's rows.

The graph keys call sites and changes on `(vendor_id, operation_id)`, and a vendor that
publishes both a REST API and an MCP server -- Stripe does -- would otherwise claim the same
id for two catalogues that share no operations."""

SOURCE: ChangeSource = "sdk-release"
"""Placeholder. `ChangeSource` has no member for a diff of two `tools/list` captures.

The four it has are `oasdiff`, `changelog`, `sdk-release` and `vendor-deprecation-table`, and
none of them describes this. `sdk-release` is the least wrong -- an advertised tool list is the
closest thing a server has to a released interface -- and it is still wrong, which matters
because `source` is the column that says how a row was attributed and a wrong one makes a false
positive untraceable.

The repair is one literal in `sync.core.models.ChangeSource`, at the same level of abstraction
as `oasdiff`: a tool or protocol name, not a vendor name, so it does not breach the boundary
`CLAUDE.md` protects. It is left undone here deliberately -- this worker does not own
`sync.core` -- and reported instead. `vendor_change.source` is `TEXT` with no constraint, so
adding the member needs no migration."""


class McpServerAdapter:
    """Turns two captures of one server's `tools/list` into the changes that break a caller."""

    unbindable_reason = (
        "an MCP tool name arrives as a runtime string rather than an SDK method chain, so a "
        "static call site addresses no tool and nothing binds"
    )
    uncorrelatable_reason = (
        "an MCP server communicates over JSON-RPC rather than REST HTTP, so observed HTTP spans "
        "cannot be correlated through a RequestCorrelator"
    )
    """Why no call site binds to a watched server, and why HTTP spans cannot correlate, stated
    where a run's report can read it.

    A constant rather than a derived answer, because this one is a property of the protocol and
    not of what a deployment happened to stage: see `operation_for_symbol`. Nothing an operator
    configures retires it, which is the difference from `GeneratedSpecAdapter`, where the same
    field is a property and staging a checkout answers `None`.

    Read through `getattr` at the boundary the way `sdk_bindings` is, so `VendorAdapter` does not
    widen for it.
    """

    def __init__(self, snapshot_dir: Path, server_id: str) -> None:
        self._snapshot_dir = Path(snapshot_dir)
        self.vendor_id = VENDOR_ID_PREFIX + server_id

    def fetch_changes(self, from_version: str, to_version: str) -> Iterable[VendorChange]:
        """Every advertised change between two captures that a caller could not survive.

        A tool appearing is not reported: no existing call breaks because the server learned to
        do something new. An argument becoming optional is not reported for the same reason, and
        neither is a type the server started accepting in addition to the ones it already did.
        """
        before = load_snapshot(self._snapshot_dir, from_version)
        after = load_snapshot(self._snapshot_dir, to_version)

        changes: list[VendorChange] = []
        for name in sorted(before):
            if name not in after:
                changes.append(
                    self._change(
                        kind=TOOL_REMOVED,
                        tool=name,
                        text=f"tool {name} is no longer advertised",
                        versions=(from_version, to_version),
                        before=before[name],
                        after=None,
                    )
                )
                continue
            changes.extend(
                self._tool_changes(before[name], after[name], versions=(from_version, to_version))
            )
        return changes

    def operation_for_symbol(
        self, symbol: str, *, language: str | None = None
    ) -> OperationRef | None:
        """Always `None`: an MCP tool call has no SDK symbol to resolve.

        A client reaches every tool through one method -- `session.call_tool(name, arguments)`
        in the Python SDK, `client.callTool` in the TypeScript one -- and the tool name arrives
        as a runtime string, in the general case one a model produced from the very listing this
        adapter diffs. The indexer derives `symbol` from a static method chain, and here that
        chain is identical for every tool on every server, so it addresses none of them.
        Answering with anything would bind a finding to a call the customer's code does not
        make.

        This is not the same `None` the deprecation and generated adapters return. Those decline
        a symbol map because a different indexer supplies the binding -- literal ids in one
        case, a generator's manifest in the other. Nothing supplies it here. Binding an MCP call
        site needs evidence this repository does not yet collect: the literal string argument at
        the `call_tool` site when there is one, and observed traffic when there is not.

        `language` is accepted and ignored, since there is no spelling for it to choose between.
        """
        return None

    def _tool_changes(
        self, before: Tool, after: Tool, versions: tuple[str, str]
    ) -> list[VendorChange]:
        if before.inputSchema == after.inputSchema:
            # Whole-schema equality is the only comparison that survives composition, and it is
            # what keeps an unreadable schema from being reported on every scan forever.
            return []

        before_args = read_arguments(before.inputSchema)
        after_args = read_arguments(after.inputSchema)
        if before_args is None or after_args is None:
            return [
                self._change(
                    kind=SCHEMA_NOT_COMPARABLE,
                    tool=after.name,
                    text=f"the input schema of {after.name} changed in a way this differ cannot read",
                    versions=versions,
                    before=before,
                    after=after,
                    severity="info",
                )
            ]

        return [
            *self._required_added(before_args, after_args, before, after, versions),
            *self._arguments_removed(before_args, after_args, before, after, versions),
            *self._types_narrowed(before_args, after_args, before, after, versions),
        ]

    def _required_added(
        self,
        before_args: ArgumentTable,
        after_args: ArgumentTable,
        before: Tool,
        after: Tool,
        versions: tuple[str, str],
    ) -> list[VendorChange]:
        """An argument the server now insists on, whether or not it existed before.

        Both routes break the same callers: one that was optional rejects everyone who omitted
        it, and one that is new rejects everyone, since nobody was passing a name that did not
        exist.
        """
        changes = []
        for name in sorted(after_args.arguments):
            if not after_args.arguments[name].required:
                continue
            previous = before_args.arguments.get(name)
            if previous is not None and previous.required:
                continue
            changes.append(
                self._change(
                    kind=REQUIRED_ARGUMENT_ADDED,
                    tool=after.name,
                    text=f"`{name}` is now a required argument of {after.name}",
                    versions=versions,
                    before=before,
                    after=after,
                    property=name,
                )
            )
        return changes

    def _arguments_removed(
        self,
        before_args: ArgumentTable,
        after_args: ArgumentTable,
        before: Tool,
        after: Tool,
        versions: tuple[str, str],
    ) -> list[VendorChange]:
        changes = []
        for name in sorted(before_args.arguments):
            if name in after_args.arguments:
                continue
            changes.append(
                self._change(
                    kind=ARGUMENT_REMOVED,
                    tool=after.name,
                    text=f"`{name}` is no longer an argument of {after.name}",
                    versions=versions,
                    before=before,
                    after=after,
                    property=name,
                    # One kind, two failures. The repair is the same edit -- stop passing it --
                    # but a rejected call fails where the caller can see it and an ignored one
                    # succeeds while doing something else, so triage needs to tell them apart.
                    rejects_unknown_arguments=after_args.rejects_unknown,
                )
            )
        return changes

    def _types_narrowed(
        self,
        before_args: ArgumentTable,
        after_args: ArgumentTable,
        before: Tool,
        after: Tool,
        versions: tuple[str, str],
    ) -> list[VendorChange]:
        """Types the argument used to accept and no longer does.

        A set difference rather than a subset test, so it catches a type replaced as well as a
        type dropped, and stays silent when the revision only adds -- which breaks nobody. An
        argument whose subschema names no type at all is skipped, because there is nothing to
        compare and guessing would invent a narrowing.
        """
        changes = []
        for name in sorted(before_args.arguments):
            previous = before_args.arguments[name]
            current = after_args.arguments.get(name)
            if current is None or previous.types is None or current.types is None:
                continue
            lost = previous.types - current.types
            if not lost:
                continue
            changes.append(
                self._change(
                    kind=ARGUMENT_TYPE_NARROWED,
                    tool=after.name,
                    text=f"`{name}` on {after.name} no longer accepts {', '.join(sorted(lost))}",
                    versions=versions,
                    before=before,
                    after=after,
                    property=name,
                    no_longer_accepted=sorted(lost),
                )
            )
        return changes

    def _change(
        self,
        kind: str,
        tool: str,
        text: str,
        versions: tuple[str, str],
        before: Tool,
        after: Tool | None,
        severity: str = "breaking",
        **extra: Any,
    ) -> VendorChange:
        """One row, with the two definitions it was derived from attached.

        `path_ptr` is empty on purpose. It addresses the operation for a REST vendor -- a URL
        path -- and an MCP tool has no address other than its name, which `operation_id`
        already holds. Putting the argument name there instead would be the confusion
        `.claude/rules/signal-stage.md` records as already made once: `path_ptr` is not a
        pointer to a field.

        That leaves `raw['text']` carrying the whole distinction between two rows for the same
        tool, because `GraphStore.upsert_vendor_change` hashes vendor, versions, kind,
        `path_ptr`, `operation_id` and `raw['text']` into the row id. Two arguments removed from
        one tool differ in nothing else, so the text has to name the argument -- and it does,
        backticked first, which is also where `changed_field` looks when `raw['property']` is
        absent.
        """
        from_version, to_version = versions
        return VendorChange(
            vendor_id=self.vendor_id,
            from_version=from_version,
            to_version=to_version,
            kind=kind,
            operation_id=tool,
            path_ptr="",
            severity=severity,
            source=SOURCE,
            raw={
                "text": text,
                "before": _definition(before),
                "after": _definition(after),
                **extra,
            },
        )


def _definition(tool: Tool | None) -> dict[str, Any] | None:
    """A tool as the server advertised it, reduced to what `json.dumps` accepts.

    `by_alias` matters: the protocol's field is `_meta`, and the model calls it `meta`. Dumping
    without it would store a record that does not round-trip back through the parser.
    """
    if tool is None:
        return None
    return tool.model_dump(mode="json", by_alias=True, exclude_none=True)

"""The graph surface: the questions an agent actually asks, answered from the graph.

`docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` freezes four tools and this
implements the three that read. `sync_propose_patch` needs the remediation pipeline, and the
spec says plainly that the read tools may ship first.

A generic query tool was rejected in that spec and the reason still holds: agents compose
arbitrary query languages poorly, and publishing the graph schema as the interface would make
every internal change a breaking change -- for a product whose whole claim is catching breaking
changes.

Four response rules, each of which exists because breaking it costs an agent context:

- **Never return file contents.** The binding is the answer. A tool returning source has handed
  back the tokens the graph exists to save.
- **Shallow by default.** Return the call site and its operation; return a change in full only
  when asked for it by identifier.
- **Paginate every list.** An unbounded result on a large repository consumes an agent's
  context before the model has processed anything.
- **Report provenance honestly.** `binding_source` says how the mapping was established, so an
  agent can weigh a patch by how much the binding is worth. It is per finding, because a page
  can hold findings from several binders and no one value is true of all of them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Protocol

from sync.core import CallSite, Finding, FindingRung, VendorChange
from sync.mcp import propose

DEFAULT_LIMIT = 50

# Rough cost of the file reading an agent would have done instead, per binding returned. A
# deliberate estimate rather than a measurement, and it is stated as one: published comparisons
# of graph-backed exploration against file-by-file reading report roughly an order of magnitude
# fewer tokens, and this makes that visible in the payload instead of asserting it outside.
_TOKENS_PER_AVOIDED_READ = 400


class GraphReader(Protocol):
    """The narrow read surface these tools need.

    Structural, so `GraphStore` satisfies it without importing anything from here, and a test
    can substitute a fake without a database.
    """

    def open_findings(self) -> list[Finding]: ...

    def get_call_site(self, call_site_id: str) -> CallSite: ...

    def get_vendor_change(self, change_id: str) -> VendorChange: ...

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]: ...


class GraphSurface:
    """Answers the four tools against a graph.

    The three read tools need only the graph. `sync_propose_patch` additionally needs the
    checkout and the pipeline pieces that operate on it, which are supplied at construction
    rather than as tool arguments: an agent names a finding, and which repository this server
    serves is the deployment's business rather than the agent's.

    Those pieces are optional, so a read-only deployment is a first-class configuration and
    not a broken one. `propose_patch` says so rather than raising.
    """

    def __init__(
        self,
        graph: GraphReader,
        feed_fetched_at: datetime | None = None,
        *,
        repo: Any = None,
        adapter: Any = None,
        remediator: Any = None,
        catalogue: Any = None,
    ) -> None:
        self._graph = graph
        self._feed_fetched_at = feed_fetched_at
        self._repo = repo
        self._adapter = adapter
        self._remediator = remediator
        self._catalogue = catalogue

    # -- tools ---------------------------------------------------------------------

    def whats_at_risk(
        self,
        path: str | None = None,
        vendor: str | None = None,
        severity: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Bindings an open finding touches, newest question first.

        Called with no arguments it answers rather than refusing -- an open question in the
        spec, settled here. The list is bounded by findings rather than by files, and a tool
        that refuses the question an agent starts with is not a tool. Pagination is what makes
        the unbounded case safe.
        """
        rows: list[dict[str, Any]] = []
        matched: list[Finding] = []
        newest_index: datetime | None = None

        for finding in self._graph.open_findings():
            site = self._site_for(finding)
            if site is None:
                continue
            if path is not None and not site.path.startswith(path):
                continue
            if vendor is not None and site.vendor_id != vendor:
                continue
            if severity is not None and finding.severity != severity:
                continue

            newest_index = _later(newest_index, site.indexed_at)
            matched.append(finding)
            rows.append(self._risk_row(finding, site))

        return self._page(
            rows, limit, offset, indexed_at=newest_index, binding_source=_shared_rung(matched)
        )

    def finding_by_id(self, finding_id: str) -> dict[str, Any] | None:
        """The `whats_at_risk` row for one finding, without paging to reach it.

        Not a tool. `sync.mcp.registry` declares the published set as data, so this answers the
        console's by-id question without the frozen four becoming five.

        `None` for a finding that is not open, matching `explain_call_site` and
        `propose_patch`: a finding that closed is a question with an answer, and the answer is
        "nothing here". A finding whose call site has gone is also `None`, because
        `whats_at_risk` drops that row -- a lookup that answered where the page does not would
        let the two disagree about what is open.
        """
        finding = next((f for f in self._graph.open_findings() if f.id == finding_id), None)
        if finding is None:
            return None
        site = self._site_for(finding)
        if site is None:
            return None

        return self._envelope(
            self._risk_row(finding, site),
            indexed_at=site.indexed_at,
            savings=_TOKENS_PER_AVOIDED_READ,
            # One finding, so the envelope rests on exactly the binding under it, and the row's
            # own `binding_source` carries the same value rather than a second claim.
            binding_source=finding.binding_rung,
        )

    def explain_call_site(self, file: str, line: int) -> dict[str, Any] | None:
        """One binding in full, with shallow references to what changed about it.

        `None` for a call site the graph does not hold: an agent asking about a line that was
        never indexed has asked a question with an answer, and the answer is "nothing here".

        Every finding naming the line is read rather than stopping at the first, because a call
        site carries no rung of its own -- the findings that name it do, two detectors can name
        one site, and the rung is a property of all of them and not of whichever the graph
        returned first.
        """
        matched: list[tuple[Finding, CallSite]] = []
        for finding in self._graph.open_findings():
            site = self._site_for(finding)
            if site is None or site.path != file or site.line != line:
                continue
            matched.append((finding, site))

        if not matched:
            return None

        _, site = matched[0]
        changes = [
            # Shallow. The full record is available by identifier, and returning every
            # change in full is how a tool hands back the tokens the graph saves.
            {"change_id": change.id, "kind": change.kind, "severity": change.severity}
            for change in self._changes_for_site(site)
        ]

        return self._envelope(
            {
                "symbol": site.symbol,
                "operation": site.operation_id,
                "vendor": site.vendor_id,
                "args_keys": list(site.args_keys),
                "response_fields_read": list(site.response_fields_read),
                "sdk_version": site.sdk_version,
                "known_changes": changes,
            },
            indexed_at=site.indexed_at,
            savings=_TOKENS_PER_AVOIDED_READ,
            binding_source=_shared_rung(finding for finding, _ in matched),
        )

    def whats_changed(
        self, vendor: str, since: str | None = None,
        limit: int = DEFAULT_LIMIT, offset: int = 0,
    ) -> dict[str, Any]:
        """What a vendor changed, whether or not this repository is affected.

        An unknown vendor is an empty page rather than an error: "nothing recorded for that
        vendor" is a true answer, and raising would make an agent treat a knowledge gap as a
        failure.

        `binding_source` is null here for the reason `indexed_at` is: this answer is built from
        vendor changes alone and holds no binding, so naming a rung would claim a mapping had
        been established for a payload in which no mapping appears.
        """
        rows = [
            {
                "operation": change.operation_id,
                "change_kind": change.kind,
                "path_ptr": change.path_ptr,
                "severity": change.severity,
                "from_version": change.from_version,
                "to_version": change.to_version,
                "published_at": change.detected_at.isoformat(),
            }
            for change in self._graph.all_vendor_changes(vendor)
            if since is None or change.detected_at.isoformat() >= since
        ]
        return self._page(rows, limit, offset, indexed_at=None, binding_source=None)

    def propose_patch(self, finding_id: str) -> dict[str, Any] | None:
        """A verified patch for one finding, returned as data and never written anywhere.

        The pipeline runs as far as static verification and stops: the node after it is
        `push_branch`, and this tool exists to hand an agent a diff rather than to open a
        pull request. `sync.mcp.propose` carries why stopping there is structural.

        The diff is source, and returning it is the one deliberate exception to the spec's
        "never return file contents" rule -- the diff *is* the answer here, and a tool that
        withheld it would have run the whole pipeline to say nothing. It is not a licence to
        return the file the diff applies to: the surrounding context stays out, which is why
        the response carries the diff alone and not the patched source.

        `None` for a finding the graph does not hold, matching `explain_call_site`: an agent
        asking about a finding that closed has asked a question whose answer is "nothing
        here", not one that deserves an exception.
        """
        finding = next((f for f in self._graph.open_findings() if f.id == finding_id), None)
        if finding is None:
            return None

        if self._repo is None or self._adapter is None or self._remediator is None:
            return self._envelope(
                {
                    "finding_id": finding_id,
                    "outcome": propose.UNAVAILABLE,
                    "diff": None,
                    "static_verify": None,
                    "evidence": self._evidence_for(finding),
                    "diagnostics": "this server is configured as a read-only graph surface",
                },
                indexed_at=None,
                savings=0,
                binding_source=finding.binding_rung,
            )

        state = propose.run_to_static_verify(
            finding,
            self._repo,
            store=self._graph,
            adapter=self._adapter,
            remediator=self._remediator,
            catalogue=self._catalogue,
        )
        patch = state.get("patch")
        site = state.get("site")
        return self._envelope(
            {
                "finding_id": finding_id,
                "outcome": state["outcome"],
                "diff": patch.diff if patch else None,
                "strategy": patch.strategy if patch else None,
                # `passed` rather than `ok`: the spec names this field, and an agent composes
                # against the spec. A `None` verdict is verification that never ran, which is
                # not the same claim as a typecheck that failed.
                "static_verify": (
                    {"passed": state["verify_ok"], "diagnostics": state.get("diagnostics", "")}
                    if "verify_ok" in state
                    else None
                ),
                "evidence": self._evidence_for(finding, state.get("change")),
                "diagnostics": state.get("diagnostics", ""),
            },
            indexed_at=site.indexed_at if site else None,
            savings=_TOKENS_PER_AVOIDED_READ,
            # One finding, so the envelope is where this belongs: the whole response rests on
            # exactly the binding under it.
            binding_source=finding.binding_rung,
        )

    # -- internals -----------------------------------------------------------------

    def _risk_row(self, finding: Finding, site: CallSite) -> dict[str, Any]:
        """One row of the at-risk answer, shared by the page and the by-id read.

        Shared rather than duplicated because the by-id read's whole contract is that it
        returns what the page returns; two literals would let that drift silently.
        """
        change = self._change_for(finding)
        return {
            "file": site.path,
            "line": site.line,
            "symbol": site.symbol,
            "operation": site.operation_id,
            "vendor": site.vendor_id,
            "change_kind": change.kind if change else None,
            "severity": finding.severity,
            "finding_id": finding.id,
            # Per row, because this is the only level at which it can be right: a page built
            # from a vendor-change finding and a status-rate finding rests on two binders, and
            # an agent weighs each row against the binding under it.
            "binding_source": finding.binding_rung,
        }

    def _evidence_for(
        self, finding: Finding, change: VendorChange | None = None
    ) -> dict[str, Any]:
        """What a reviewer needs to judge the patch without trusting us.

        `sync.core.Evidence` carries a fourth field, `ci_run_url`, which is deliberately not
        here: no CI ran, and an empty string in a field named for a run would report one that
        does not exist.
        """
        resolved = change if change is not None else self._change_for(finding)
        site = self._site_for(finding)
        return {
            "spec_diff": resolved.raw if resolved else {},
            "changelog": finding.rationale,
            "call_sites": [f"{site.path}:{site.line}"] if site else [],
        }

    def _site_for(self, finding: Finding) -> CallSite | None:
        """The call site a finding names, or `None` when it no longer exists.

        The index outlives the tree it was built from, so a dangling reference is expected. One
        of them must not deny an agent every other answer.
        """
        try:
            return self._graph.get_call_site(finding.call_site_id)
        except (KeyError, LookupError, ValueError):
            return None

    def _change_for(self, finding: Finding) -> VendorChange | None:
        if finding.vendor_change_id is None:
            return None
        try:
            return self._graph.get_vendor_change(finding.vendor_change_id)
        except (KeyError, LookupError, ValueError):
            return None

    def _changes_for_site(self, site: CallSite) -> list[VendorChange]:
        return [
            change
            for change in self._graph.all_vendor_changes(site.vendor_id)
            if change.operation_id == site.operation_id
        ]

    def _page(
        self,
        rows: list[dict[str, Any]],
        limit: int,
        offset: int,
        indexed_at: datetime | None,
        binding_source: FindingRung | None,
    ) -> dict[str, Any]:
        window = rows[offset : offset + limit]
        consumed = offset + len(window)
        return self._envelope(
            {
                "items": window,
                "total": len(rows),
                # `None` rather than the next index when the page is the last one. An offset
                # that always exists is an infinite loop with extra steps.
                "next_offset": consumed if consumed < len(rows) else None,
            },
            indexed_at=indexed_at,
            savings=len(window) * _TOKENS_PER_AVOIDED_READ,
            binding_source=binding_source,
        )

    def _envelope(
        self,
        payload: dict[str, Any],
        indexed_at: datetime | None,
        savings: int,
        binding_source: FindingRung | None,
    ) -> dict[str, Any]:
        """Provenance on every response, as timestamps rather than durations.

        A duration computed at response time expires silently once an answer is cached; a
        timestamp cannot claim a freshness it no longer has.

        `binding_source` is supplied rather than constant, and the argument that made it a
        constant was sound when it was written: the only binder was the static one, so `resolved`
        would have claimed a compiler pass and `observed` a telemetry correlation, neither of
        which had run. What changed is the precondition, not the reasoning. Two of the five
        detectors now raise findings from watched traffic, `finding.binding_rung` is an enforced
        column rather than a hint, and `open_findings` returns `static`, `observed`, `unresolved`
        and `unattributed` -- measured, not supposed. So the constant stopped describing the
        answer and started contradicting it.

        Null when the answer rests on no single binding: no binding at all, as in
        `whats_changed`, or several rungs at once, as in a page a static finding and a telemetry
        finding both appear on. Absent provenance is recoverable by asking again per row; wrong
        provenance is what an agent weighs the finding by.
        """
        return {
            **payload,
            "indexed_at": indexed_at.isoformat() if indexed_at else None,
            "feed_fetched_at": self._feed_fetched_at.isoformat() if self._feed_fetched_at else None,
            "binding_source": binding_source,
            "context_savings": savings,
        }


def _shared_rung(findings: Iterable[Finding]) -> FindingRung | None:
    """The rung every finding in an answer rests on, or `None` when they do not all agree.

    Not the weakest of them. Understating a rung is still a wrong answer about the rows that
    carry a stronger one, and `CLAUDE.md`'s rule is attribution rather than caution: a false
    positive an agent was told rested on a static read cannot be attributed to the correlator
    that actually produced it.
    """
    rungs = {finding.binding_rung for finding in findings}
    return rungs.pop() if len(rungs) == 1 else None


def _later(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
    if current is None:
        return candidate
    return max(current, candidate)

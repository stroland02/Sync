"""Starlette app: the transport for the operator console, over two answer sources.

The transport holds no logic. Per-finding routes are a thin call into `GraphSurface`, which
answers questions about one repository an agent is already pointed
at. Fleet-wide routes -- `/api/runs`, `/api/corpus`, `/api/corpus/abandonment`,
`/api/repositories` -- answer a
different grain, every run or every attempt across repositories, which the frozen surface
answers no question about; those go through reader callables backed by `sync.dashboard`
instead. The graph-rendering routes below -- bindings, per-repository coverage and observed
telemetry, detector accountability -- are the same amendment applied a second time: they read
`sync.dashboard.graph_views`, never the frozen surface and never SQL of their own. `app.py`
constructs neither the surface nor a dashboard view model -- all of it is built by the caller
and handed in. Errors that a reader expresses as `None` become 404 with a JSON body -- HTML
would confuse a JSON client into treating a missing finding as a broken deployment.

Four routes take an optional `repo_id` and pass it straight through: `/api/overview`,
`/api/detectors`, `/api/vendors/{vendor_id}` and the bindings route. Repository scope is what
every console level below Codebase inherits, and a fleet-wide answer rendered under a
repository's name is a false claim about that repository. The corpus is deliberately not among
them -- `migration_outcome` stores no `repo_id` at all, by a schema decision that is what makes
the table safe to aggregate across customers, so that figure states its fleet scope on screen
instead.

Every reader is a callable rather than a class for the same reason `workflow_reader` is: the
checkpointer, the corpus, the repository roll-up and the graph views each live outside
`GraphSurface`, in stores the surface does not speak, and asking one abstraction to speak all
of them would fold unrelated responsibilities into it. `WorkflowReader` is `str -> dict | None`,
matching the shape the console consumes; every other reader below takes the shape its own
route needs.
"""

from __future__ import annotations

import json

from typing import Any, Callable, Iterator, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from sync.core import ALLOWED_MERGE_METHODS, ALLOWED_MERGE_POLICIES, REFUSED_MERGE_POLICIES

from sync.core.models import CONTEXT_BODY_MAX
from sync.mcp.tools import DEFAULT_LIMIT, GraphSurface

WorkflowReader = Callable[[str], Optional[dict[str, Any]]]

# The patch a run produced, keyed the same way its workflow is. A diff is Sync's own artifact
# and is served; customer source is not, and stays blocked on the threat-model ruling.
PatchReader = Callable[[str], Optional[dict[str, Any]]]

# Whether a finding stands dismissed, and how many times somebody has changed their mind.
DismissalReader = Callable[[str], dict[str, Any]]
# Currently-dismissed findings tallied by the reason standing against each, across the graph.
# Takes no finding: this is the aggregate the per-finding reader above cannot produce, and it
# counts the latest ruling per finding rather than every row -- a finding dismissed, restored
# and dismissed again is one dismissal now, not three.
DismissalTallyReader = Callable[[], dict[str, Any]]
# Dismiss with a reason from the closed vocabulary, or restore by passing `reason=None`. The
# vocabulary is NOT restated here: `record_dismissal` owns it and raises naming it, and a
# second copy in the transport is the fact written twice that would disagree first.
DismissalWriter = Callable[..., None]

# The fleet roll-ups read the checkpointer and the graph store directly, outside `GraphSurface`
# -- same reasoning as `WorkflowReader`: a run, a repair record and a repo_id roll-up are not
# graph-surface questions, and folding them into the surface would ask one abstraction to speak
# three databases' worth of shape.
RunsReader = Callable[..., dict[str, Any]]
SetupReader = Callable[..., dict[str, Any]]
StagingReader = Callable[[str], dict[str, Any]]
StagingWriter = Callable[[str, dict[str, Any]], dict[str, Any]]
CorpusReader = Callable[..., dict[str, Any]]
CorpusHealthReader = Callable[[], dict[str, Any]]
RepositoriesReader = Callable[[], dict[str, Any]]

# `abandonment_by_change_kind`'s reader -- which change kinds are not mechanically safe, and at
# which tier. Outside `GraphSurface` for the same reason `CorpusReader` is: a per-`(change_kind,
# tier)` breakdown of `migration_outcome` is not a per-finding question the frozen surface
# answers.
AbandonmentReader = Callable[[], dict[str, Any]]

# The change-units reader backs `sync.dashboard.fleet.change_units`: open findings grouped by
# vendor change and operation across the fleet or scoped to a single repository.
ChangeUnitsReader = Callable[..., dict[str, Any]]

# The graph-rendering readers back `sync.dashboard.graph_views`, outside `GraphSurface` for the
# same reason the fleet readers above are: a binding surface, a per-repo coverage count and a
# detector roll-up are questions about the whole graph or about one repository, not the frozen
# surface's per-finding shape, and folding them in would ask one abstraction to speak a fourth
# question it was not built to answer.
BindingReader = Callable[..., dict[str, Any]]
CoverageReader = Callable[[str], dict[str, Any]]
RepositoryGraphReader = Callable[[str], dict[str, Any] | None]
ChangeVolumeReader = Callable[[str], dict[str, Any]]
ObservedReader = Callable[..., dict[str, Any]]
# Exposure for one vendor: which of its operations this codebase calls, at which rung.
# Takes the repository scope as a keyword so it composes with the vendor rather than
# replacing it -- the same rule the severity breakdown follows one route above.
VendorOperationsReader = Callable[..., dict[str, Any]]
# Dashboard 1's dated aggregate. Keyword-only scope, like every other narrowing reader.
FindingsOverTimeReader = Callable[..., dict[str, Any]]
# Decision 76's bus, as an iterator of events for one repository. An iterator rather than a
# callback so the route owns the lifetime: when the client goes, the generator is closed and
# the listening connection with it.
EventsReader = Callable[[str], Iterator[dict[str, Any]]]
DetectorReader = Callable[[], dict[str, Any]]

# The adapter inventory backs `sync.dashboard.adapters.adapter_inventory`. It takes no
# arguments and narrows by nothing: an adapter is a property of the deployment rather than
# of a repository, and a `repo_id` filter here would answer a question about which vendors a
# repository calls, which `/api/repositories/{repo_id}/observed` already answers better.
AdaptersReader = Callable[[], dict[str, Any]]

# The severity roll-up backs `sync.dashboard.graph_views.severity_rollup`, outside `GraphSurface`
# for the same reason every reader above is: it is an aggregate over open findings, not a
# per-finding question the frozen surface answers, and it is read once per call rather than
# derived from `whats_at_risk`'s own page so the two stay two questions rather than one route
# quietly answering both from data shaped for the first.
#
# Two routes read it at two scopes, and the scopes compose: `/api/overview` narrows by repository
# alone, `/api/vendors/{vendor_id}` by that repository *and* the vendor in its path. One reader
# rather than two, because the join deciding which findings count as open is the part with a wrong
# answer and a second copy of it is a second place for two totals to drift.
SeverityReader = Callable[..., dict[str, Any]]

# The vendor-findings reader backs `sync.dashboard.graph_views.vendor_findings`, and it is here
# for the reason `overview_reader` is: `sync.mcp.tools` is frozen, and `whats_at_risk` cannot
# narrow its answer to one repository because its rows carry no `repo_id`. Repository scope is
# what every console level below Codebase inherits, and API Services is the first level under
# it, so a fleet-wide page rendered under a repository's name is a false claim about that
# repository. The reader also fixes the same scan `overview_reader` did: `whats_at_risk` walks
# every open finding doing one `get_call_site` round trip per row before slicing in Python.
VendorFindingsReader = Callable[..., dict[str, Any]]
FindingsReader = Callable[..., dict[str, Any]]

# The overview reader backs `sync.dashboard.graph_views.overview_summary`: the fleet screen's
# vendor distribution and its bounded total, read straight from `GraphStore` in real SQL rather
# than from the frozen surface. `whats_at_risk` always walks every open finding doing one
# `get_call_site` round trip per row to build its shallow rows, so no `limit` passed to it bounds
# that scan -- this route used to call it twice (a probe, then a page sized to the probe's own
# total) and tally vendors in a Python loop over the result, which is the 9-19 second fleet screen
# `overview_summary`'s own docstring measures and fixes.
OverviewReader = Callable[[], dict[str, Any]]

# Context is a reader and a writer rather than a reader alone, because this is the first route
# on this app that writes. Both are injected for the reason every reader above is: a test
# substitutes fakes without reaching into module state.
ContextReader = Callable[[str], dict[str, Any]]
ContextWriter = Callable[[str, str], None]
SettingsReader = Callable[[str], dict[str, Any]]
SettingsWriter = Callable[[str, dict[str, Any]], Any]


# Ceiling on a page a caller may ask for. "Paginate every list" is a frozen rule of the graph
# surface, and a query string is the one place a caller can ask for an unbounded page: the
# surface honours whatever limit it is handed.
_MAX_LIMIT = 500


def _int_param(request: Request, name: str, default: int) -> int:
    """A query parameter parsed as int, falling back to the default rather than 400.

    A malformed pagination cursor is a client bug, not a database failure; the console
    handles the default cleanly, and 400 for a stray typed URL is more surprise than help.
    """
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _limit_param(request: Request, name: str = "limit") -> int:
    # `rows[offset : offset + limit]` in the surface treats a limit below 1 as a slice
    # bound, not a page size: negative turns the stop negative (an unbounded page from the
    # other end), zero returns nothing and never advances `next_offset`. The floor sits
    # here rather than in the surface because the frozen "paginate every list" rule belongs
    # to the transport, and `sync/mcp/tools.py` is not the surface to change.
    #
    # `name` defaults to "limit" for the one-cursor routes and is overridden by the routes that
    # paginate more than one set on the same screen (`binding`, `repository_observed`), each of
    # which needs its own query-parameter name because one cursor cannot serve two questions.
    return min(max(_int_param(request, name, DEFAULT_LIMIT), 1), _MAX_LIMIT)


def _offset_param(request: Request, name: str = "offset") -> int:
    # `_int_param` returns whatever an out-of-range value parses to and clamps nothing --
    # unlike `limit`, `offset` was never floored, so a negative value reached the surface's own
    # `rows[offset : offset + limit]` slice as a slice bound rather than a page position.
    return max(_int_param(request, name, 0), 0)


def _values_param(request: Request, name: str) -> list[str]:
    """Every value given for one repeated query parameter, empties dropped.

    A multi-select filter is spelled `?vendor_id=a&vendor_id=b` rather than as one
    comma-joined value, because the values are vendor and operation identifiers and nothing
    forbids a comma inside one -- a separator that can occur in the data is a parser that is
    wrong on somebody's repository and wrong silently.

    A single value is still `?vendor_id=a`, so a link a reader saved before this existed still
    narrows to exactly what it did then.
    """
    return [value for value in request.query_params.getlist(name) if value]


def _int_values_param(request: Request, name: str) -> list[int]:
    """The same, for a numeric facet, with an unparseable value kept as unmatchable.

    Dropping it would silently widen the set -- a hand-edited `?loop_depth=abc` would return
    *more* rows than the URL asks for, which is the one direction a filter must never fail in.
    `loop_depth` is `NOT NULL` and never negative, so -1 is a value the column cannot hold and
    the honest empty page is what comes back.
    """
    depths: list[int] = []
    for raw in _values_param(request, name):
        try:
            depths.append(int(raw))
        except ValueError:
            depths.append(-1)
    return depths


def _not_found(what: str, identifier: str) -> JSONResponse:
    return JSONResponse(
        {"error": f"{what} not found", "identifier": identifier}, status_code=404
    )


def create_app(
    *,
    surface: GraphSurface,
    workflow_reader: WorkflowReader,
    runs_reader: RunsReader,
    corpus_reader: CorpusReader,
    corpus_health_reader: CorpusHealthReader,
    repositories_reader: RepositoriesReader,
    abandonment_reader: AbandonmentReader,
    binding_reader: BindingReader,
    coverage_reader: CoverageReader,
    graph_reader: RepositoryGraphReader,
    change_volume_reader: ChangeVolumeReader,
    observed_reader: ObservedReader,
    vendor_operations_reader: VendorOperationsReader,
    findings_over_time_reader: FindingsOverTimeReader,
    events_reader: EventsReader,
    patch_reader: PatchReader,
    dismissal_reader: DismissalReader,
    dismissal_tally_reader: DismissalTallyReader,
    dismissal_writer: DismissalWriter,
    detector_reader: DetectorReader,
    adapters_reader: AdaptersReader,
    severity_reader: SeverityReader,
    overview_reader: OverviewReader,
    vendor_findings_reader: VendorFindingsReader,
    change_units_reader: ChangeUnitsReader,
    context_reader: ContextReader,
    context_writer: ContextWriter,
    findings_reader: FindingsReader | None = None,
    settings_reader: SettingsReader | None = None,
    settings_writer: SettingsWriter | None = None,
    setup_reader: SetupReader | None = None,
    staging_reader: StagingReader | None = None,
    staging_writer: StagingWriter | None = None,
    facts_reader: Callable[[str], dict[str, Any] | None] | None = None,
    call_sites_reader: Callable[..., dict[str, Any]] | None = None,
    integration_changes_reader: Callable[..., dict[str, Any]] | None = None,
    topology_reader: Callable[[str], dict[str, Any]] | None = None,
    changes_over_time_reader: Callable[..., dict[str, Any]] | None = None,
    remediation_activity_reader: Callable[[], dict[str, Any]] | None = None,
    catalogue_reader: Callable[..., dict[str, Any]] | None = None,
    # The captured snippet at one position (path, line, repo_id), or None. Separate from the
    # frozen `GraphSurface` read the finding route composes with, which explains the call from
    # its recorded shape and predates capture.
    call_site_source_reader: Callable[[str, int, str | None], dict[str, Any] | None] | None = None,
    # Owner re-ruling, 2026-08-19, scoping the threat-model rule above: bounded, index-captured
    # source windows ARE served -- on a deployment that has not switched them off. Hosted
    # deployments set SYNC_SERVE_SOURCE=false and the ruling's original argument (a partner can
    # reach a hosted console) holds there unchanged. Whole files stay unserved everywhere.
    serve_source: bool = True,
    api_password: str | None = None,
) -> Starlette:
    """Build the Starlette app bound to a particular surface and readers.

    Constructed rather than module-global so a test substitutes fakes without reaching into
    module state, and a deployment configures each reader once at start-up.

    Every reader is required rather than defaulted. A deployment that forgets one should fail
    at start-up with a `TypeError` naming the missing argument, not serve a route that 500s the
    first time a customer opens it.
    """

    def _with_source_policy(payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        """The payload, with snippets stripped where policy says so, and the policy stated.

        `source_served` is always present so the console can tell policy from absence: a row
        without a snippet on a serving deployment was indexed before capture existed, which is
        a different nothing from a deployment that withholds them.
        """
        if not serve_source:
            for row in rows:
                row.pop("snippet", None)
                row.pop("snippet_start_line", None)
        payload["source_served"] = serve_source
        return payload
    effective_findings_reader = findings_reader if findings_reader is not None else vendor_findings_reader

    async def overview(request: Request) -> JSONResponse:
        # `overview_reader` answers "what open findings do we hold, grouped by vendor, and how
        # many" straight from `GraphStore` in real SQL -- `overview_summary`'s own docstring
        # carries why this no longer reaches `whats_at_risk` at all: that method always walks
        # every open finding doing one `get_call_site` round trip per row, so no `limit` bounds
        # the scan underneath it, which is what made this route 9-19 seconds at ten thousand
        # call sites before this fix.
        #
        # `severity_reader` stays a second, independent reader rather than a field folded into
        # `overview_reader`'s own payload -- the same reasoning that already kept it separate
        # from `page["items"]`: the vendor distribution and the severity distribution are two
        # independently-computed questions, and merging them into one reader's return value
        # would let one route quietly answer both from data shaped for the first.
        #
        # `repo_id` narrows both readers together or neither. Narrowing one would put two
        # scopes on one screen with nothing on it saying which figure is in which.
        repo_id = request.query_params.get("repo_id")
        payload = overview_reader(repo_id=repo_id)
        severity = severity_reader(repo_id=repo_id)
        return JSONResponse({**payload, "severity_counts": severity["by_severity"]})

    async def findings_list(request: Request) -> JSONResponse:
        repo_id = request.path_params.get("repo_id") or request.query_params.get("repo_id")
        vendor_id = request.query_params.get("vendor_id")
        page = effective_findings_reader(
            repo_id=repo_id,
            vendor_id=vendor_id,
            severity=request.query_params.get("severity"),
            path=request.query_params.get("path"),
            order=request.query_params.get("order"),
            limit=_limit_param(request),
            offset=_offset_param(request),
        )
        breakdown = severity_reader(repo_id=repo_id, vendor_id=vendor_id)
        return JSONResponse(
            {
                **page,
                "severity_counts": breakdown["by_severity"],
                "severity_total": breakdown["total"],
            }
        )

    async def vendor_detail(request: Request) -> JSONResponse:
        # `severity_reader` is scoped to the repository and the vendor the URL names, and to
        # nothing else. It is the option list this screen's severity filter is built from, so
        # narrowing it by the severity or the path currently selected would collapse it to
        # whatever is already chosen and leave no way back to the rest.
        #
        # The two scopes it does take compose rather than replace each other: dropping the
        # repository would put a fleet-wide breakdown under a repository's heading, and dropping
        # the vendor would put every vendor's severities beside one vendor's findings. Both are
        # the same false claim the repository scoping exists to remove, one axis at a time.
        vendor_id = request.path_params["vendor_id"]
        repo_id = request.query_params.get("repo_id")
        page = vendor_findings_reader(
            vendor_id,
            repo_id=repo_id,
            severity=request.query_params.get("severity"),
            path=request.query_params.get("path"),
            # `None` means the URL named no ordering, and the transport does not know what the
            # orderings are -- it hands over what the URL said. The view resolves both an absent
            # and an unrecognised value, *and echoes the ordering it applied*, so a hand-edited URL
            # cannot leave the screen naming an ordering the rows are not in. Naming the vocabulary
            # here as well would put it in two places and let them disagree, and rejecting here
            # would turn a typo in a sort parameter into a failed page load.
            order=request.query_params.get("order"),
            limit=_limit_param(request),
            offset=_offset_param(request),
        )
        breakdown = severity_reader(repo_id=repo_id, vendor_id=vendor_id)
        return JSONResponse(
            {
                **page,
                "severity_counts": breakdown["by_severity"],
                "severity_total": breakdown["total"],
            }
        )

    async def finding_detail(request: Request) -> JSONResponse:
        finding_id = request.path_params["finding_id"]
        # `finding_by_id` is the surface's own by-id read, and it returns exactly what a
        # `whats_at_risk` row returns -- the two share `_risk_row` so they cannot drift. This
        # route used to page through the answer looking for one row, because the by-id read did
        # not exist when it was written; that reason expired and the comment saying otherwise
        # outlived it. `None` is a finding that is not open, or one whose call site has gone,
        # and both are honestly "not found" here.
        row = surface.finding_by_id(finding_id)
        if row is None:
            return _not_found("finding", finding_id)
        payload = surface.explain_call_site(row["file"], row["line"])
        if payload is None:
            # The row named the site, so the surface should hold it; a `None` here is a
            # race between pages, and the honest answer is still "not found".
            return _not_found("finding", finding_id)
        # The captured window around the call site, where policy serves it and a pass captured
        # one. Fetched here rather than through `explain_call_site` because `GraphSurface` is
        # frozen; `None` under `source_served: true` means no pass has captured this row yet.
        source = None
        if serve_source and call_site_source_reader is not None:
            source = call_site_source_reader(row["file"], row["line"], row.get("repo_id"))
        # Forward finding-level fields: the finding's own rung, its severity, call site, and repository.
        return JSONResponse(
            {
                **payload,
                "source_served": serve_source,
                "call_site_source": source,
                "finding": {
                    "finding_id": finding_id,
                    "binding_source": row["binding_source"],
                    "severity": row.get("severity"),
                    "file": row["file"],
                    "line": row["line"],
                    "repo_id": row.get("repo_id"),
                },
            }
        )

    async def vendor_changes(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        limit = _limit_param(request)
        offset = _offset_param(request)
        since = request.query_params.get("since")
        page = surface.whats_changed(vendor=vendor_id, since=since, limit=limit, offset=offset)
        return JSONResponse(page)

    async def repository_events(request: Request) -> StreamingResponse:
        """Decision 76's stream, scoped by the path decision 49 puts it in.

        **Held open with no lifetime cap, by owner selection.** The cost was stated when the
        choice was offered: a handful of forgotten tabs each hold a listening Postgres connection,
        and enough of them exhaust the pool the read API shares. What is *not* a cap and is done
        anyway is cleanup -- the generator is closed when the client disconnects, so a closed tab
        releases its connection immediately rather than at some later timeout.

        **The heartbeat is a named event rather than an SSE comment**, also owner-selected. It
        carries no domain fact and is named so nobody mistakes it for one: what it asserts is that
        the stream is alive. Without it a proxy closing an idle connection is indistinguishable
        from an index that simply had nothing to say, and decision 76 requires the console to
        render a drop -- which it can only do if a drop is distinguishable from silence.

        `X-Accel-Buffering` is set because a buffering proxy defeats the whole transport: events
        arrive in a batch when the connection closes, which is the opposite of a stream.
        """
        repo_id = request.path_params["repo_id"]

        def frames() -> Iterator[str]:
            for event in events_reader(repo_id):
                # Two newlines end an SSE frame; one separates its fields. Written as
                # escapes rather than a multi-line literal so the framing cannot be
                # reformatted away by an editor that trims trailing whitespace.
                if event["kind"] == "heartbeat":
                    # A comment line. It reaches no handler and carries no fact -- it exists
                    # so a proxy does not close an idle connection and make silence look
                    # like a drop.
                    yield ": heartbeat\n\n"
                    continue
                frame = "event: " + event["kind"] + "\n"
                frame += "data: " + json.dumps(event) + "\n\n"
                yield frame

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    async def remediation_activity(request: Request) -> JSONResponse:
        """Dashboards L2, L3 and T4. Fleet-wide: `migration_outcome` stores no repository."""
        if remediation_activity_reader is None:
            return JSONResponse(
                {"error": "Remediation activity reader not configured"}, status_code=501
            )
        return JSONResponse(remediation_activity_reader())

    async def changes_over_time(request: Request) -> JSONResponse:
        """Dashboard T3. Narrowed by vendor rather than by repository, matching the feed it
        summarises: what a vendor published is a fact about the vendor."""
        if changes_over_time_reader is None:
            return JSONResponse({"error": "Changes series reader not configured"}, status_code=501)
        return JSONResponse(
            changes_over_time_reader(vendor_id=request.query_params.get("vendor_id"))
        )

    async def findings_over_time(request: Request) -> JSONResponse:
        # `repo_id` narrows and is optional: absent means every repository the index has
        # seen, which is a wider true answer rather than a missing one.
        return JSONResponse(
            findings_over_time_reader(repo_id=request.query_params.get("repo_id"))
        )

    async def vendor_operations(request: Request) -> JSONResponse:
        # Decision 29's opening answer for the vendor page. `repo_id` narrows and is optional:
        # absent means every repository the index has seen, which is a wider true answer rather
        # than a missing one, and the payload echoes back which it gave.
        vendor_id = request.path_params["vendor_id"]
        payload = vendor_operations_reader(
            vendor_id, repo_id=request.query_params.get("repo_id")
        )
        return JSONResponse(payload)

    async def get_dismissal(request: Request) -> JSONResponse:
        """Whether this finding stands dismissed right now, and how often that has flipped."""
        return JSONResponse(dismissal_reader(request.path_params["finding_id"]))

    async def dismissal_tally(request: Request) -> JSONResponse:
        """Currently-dismissed findings, tallied by the reason standing against each.

        Unpaginated, and in `_NOT_COLLECTIONS` for the reason the severity roll-up is: this is a
        distribution over a closed reason vocabulary, so it is bounded by that vocabulary rather
        than by how many findings exist. A page of a distribution reads as the whole one.
        """
        return JSONResponse(dismissal_tally_reader())

    async def set_dismissal(request: Request) -> JSONResponse:
        """Dismiss a finding with a reason, or restore it by sending `reason: null`.

        **This writes a row, never a column.** A finding dismissed and later restored has two
        rows and the current state is the latest, which is the only arrangement in which the
        console can show that somebody changed their mind.

        `actor` is required and this route will not invent one. The column exists so a reader
        can ask *who decided*, and a console behind a single shared password cannot answer
        that from its credentials -- so the caller says who, or the write is refused. Filling
        it with a constant would satisfy the schema and destroy the column's only purpose.

        The reason is validated by `record_dismissal`, which owns the vocabulary and raises
        naming it. Re-checking it here would put the closed set in two places.
        """
        finding_id = request.path_params["finding_id"]
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)

        actor = payload.get("actor")
        if not isinstance(actor, str) or not actor.strip():
            return JSONResponse(
                {
                    "error": (
                        "actor is required: a dismissal nobody can be attributed to is not "
                        "reviewable, and this console cannot infer who you are"
                    )
                },
                status_code=400,
            )

        try:
            dismissal_writer(finding_id, reason=payload.get("reason"), actor=actor.strip())
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse(dismissal_reader(finding_id))

    async def finding_patch(request: Request) -> JSONResponse:
        """The diff a run wrote, and the branch it went to, in one answer.

        **Owner ruling: the two travel together.** A diff served alone is the shape a reader
        mistakes for a change that has already landed in their repository, and the branch is
        the only thing on the payload that says otherwise.

        A finding with no run at all is a 404. A finding whose run produced no patch is a
        200 carrying the reason -- deciding against a patch is an answer, not a missing page,
        and the reason is exactly what a reviewer opened this to read.
        """
        finding_id = request.path_params["finding_id"]
        payload = patch_reader(finding_id)
        if payload is None:
            return _not_found("patch", finding_id)
        return JSONResponse(payload)

    async def workflow(request: Request) -> JSONResponse:
        finding_id = request.path_params["finding_id"]
        payload = workflow_reader(finding_id)
        if payload is None:
            return _not_found("workflow", finding_id)
        return JSONResponse(payload)

    async def setup(request: Request) -> JSONResponse:
        """The full loop's prerequisites, probed now — each item its own state, no figure over
        them. Probing on request is the point: a cached verdict about a credential is stale the
        moment somebody logs in to fix it."""
        if setup_reader is None:
            return JSONResponse({"error": "Setup reader not configured"}, status_code=501)
        return JSONResponse(setup_reader(repo_id=request.query_params.get("repo_id")))

    async def topology_route(request: Request) -> JSONResponse:
        """One repository's API topology, measured from its own call sites."""
        if topology_reader is None:
            return JSONResponse({"error": "Topology reader not configured"}, status_code=501)
        return JSONResponse(topology_reader(request.path_params["repo_id"]))

    async def catalogue_route(request: Request) -> JSONResponse:
        """Every integration this deployment can watch, and where each one stands."""
        if catalogue_reader is None:
            return JSONResponse({"error": "Catalogue reader not configured"}, status_code=501)
        return JSONResponse(catalogue_reader(repo_id=request.query_params.get("repo_id")))

    async def integration_changes_route(request: Request) -> JSONResponse:
        """Every integration change the graph holds, newest first — the feed.

        Not repository-scoped, and the payload's own shape says so: what a vendor published is
        a fact about the vendor. Where it meets this codebase is a finding, which is a
        different screen with a different grain.
        """
        if integration_changes_reader is None:
            return JSONResponse({"error": "Changes reader not configured"}, status_code=501)
        return JSONResponse(
            integration_changes_reader(
                vendor_ids=_values_param(request, "vendor_id"),
                severities=_values_param(request, "severity"),
                limit=_limit_param(request),
                offset=_offset_param(request),
            )
        )

    async def call_sites_route(request: Request) -> JSONResponse:
        """One page of a repository's call sites, with the vendor facet counted beside it.

        The raw material of the graph, browsable: every other screen shows what Sync concluded,
        and this shows what it read. Filters are passed through unvalidated for the same reason
        the runs filter is -- a value outside the vocabulary matches nothing, and an empty page
        is the honest answer to a stale bookmark where a 400 turns yesterday's URL into an
        error screen.
        """
        if call_sites_reader is None:
            return JSONResponse({"error": "Call sites reader not configured"}, status_code=501)
        page = call_sites_reader(
            request.path_params["repo_id"],
            vendor_ids=_values_param(request, "vendor_id"),
            operation_ids=_values_param(request, "operation_id"),
            loop_depths=_int_values_param(request, "loop_depth"),
            path_prefix=request.query_params.get("path_prefix"),
            limit=_limit_param(request),
            offset=_offset_param(request),
        )
        return JSONResponse(_with_source_policy(page, page.get("items", [])))

    async def codebase_facts_route(request: Request) -> JSONResponse:
        """One repository's technical census. `facts: null` is an answer -- indexed never, or
        before the census existed -- and deliberately not a 404, which B147 measured reading
        as a repository that does not exist."""
        if facts_reader is None:
            return JSONResponse({"error": "Facts reader not configured"}, status_code=501)
        repo_id = request.path_params["repo_id"]
        return JSONResponse({"repo_id": repo_id, "facts": facts_reader(repo_id)})

    async def get_staging(request: Request) -> JSONResponse:
        """A vendor's declared staging fields and their current values (B195). An empty schema
        is an answer -- the vendor has nothing to configure -- and never a 404."""
        if staging_reader is None:
            return JSONResponse({"error": "Staging reader not configured"}, status_code=501)
        return JSONResponse(staging_reader(request.path_params["vendor_id"]))

    async def set_staging(request: Request) -> JSONResponse:
        """Write the writable staging fields. The same class of write as repository settings:
        deployment configuration, not the graph -- the read-only rule over the graph holds."""
        if staging_writer is None:
            return JSONResponse({"error": "Staging writer not configured"}, status_code=501)
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        try:
            return JSONResponse(staging_writer(request.path_params["vendor_id"], payload))
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=400)

    async def runs(request: Request) -> JSONResponse:
        repo_id = request.query_params.get("repo_id")
        limit = _limit_param(request)
        offset = _offset_param(request)
        # Passed through unvalidated on purpose: a value outside the disposition vocabulary
        # matches nothing, and an empty page is the honest answer to a stale bookmark where a
        # 400 would turn yesterday's URL into an error screen.
        outcome = request.query_params.get("outcome")
        return JSONResponse(
            runs_reader(repo_id=repo_id, limit=limit, offset=offset, outcome=outcome)
        )

    async def corpus(request: Request) -> JSONResponse:
        repo_id = request.query_params.get("repo_id")
        return JSONResponse(corpus_reader(repo_id=repo_id))

    async def corpus_health_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(corpus_health_reader())

    async def repositories(request: Request) -> JSONResponse:
        return JSONResponse(repositories_reader())

    async def abandonment(request: Request) -> JSONResponse:
        return JSONResponse(abandonment_reader())

    async def binding(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        operation_id = request.path_params["operation_id"]
        repo_id = request.query_params.get("repo_id")
        path_prefix = request.query_params.get("path_prefix")
        binding_rung = request.query_params.get("binding_rung")
        payload = binding_reader(
            vendor_id,
            operation_id,
            repo_id=repo_id,
            path_prefix=path_prefix,
            binding_rung=binding_rung,
            call_sites_limit=_limit_param(request, "call_sites_limit"),
            call_sites_offset=_offset_param(request, "call_sites_offset"),
            changes_limit=_limit_param(request, "changes_limit"),
            changes_offset=_offset_param(request, "changes_offset"),
        )
        # Only the paged shape carries rows that can hold a snippet; anything else has nothing
        # to strip and still gets the policy statement.
        sites = payload.get("call_sites")
        rows = sites.get("items", []) if isinstance(sites, dict) else []
        return JSONResponse(_with_source_policy(payload, rows))

    async def repository_coverage(request: Request) -> JSONResponse:
        repo_id = request.path_params["repo_id"]
        payload = coverage_reader(repo_id)
        if payload is None:
            return _not_found("repository", repo_id)
        return JSONResponse(payload)

    async def vendor_change_volume(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        return JSONResponse(change_volume_reader(vendor_id))

    async def repository_graph(request: Request) -> JSONResponse:
        repo_id = request.path_params["repo_id"]
        payload = graph_reader(repo_id)
        if payload is None:
            return _not_found("repository", repo_id)
        return JSONResponse(payload)

    async def repository_observed(request: Request) -> JSONResponse:
        repo_id = request.path_params["repo_id"]
        payload = observed_reader(
            repo_id,
            calls_limit=_limit_param(request, "calls_limit"),
            calls_offset=_offset_param(request, "calls_offset"),
            shapes_limit=_limit_param(request, "shapes_limit"),
            shapes_offset=_offset_param(request, "shapes_offset"),
            error_windows_limit=_limit_param(request, "error_windows_limit"),
            error_windows_offset=_offset_param(request, "error_windows_offset"),
        )
        if payload is None:
            return _not_found("repository", repo_id)
        return JSONResponse(payload)

    async def detectors(request: Request) -> JSONResponse:
        return JSONResponse(detector_reader(repo_id=request.query_params.get("repo_id")))

    async def adapters(request: Request) -> JSONResponse:
        return JSONResponse(adapters_reader())

    async def change_units(request: Request) -> JSONResponse:
        # `change_units_reader` answers `sync.dashboard.fleet.change_units`: open findings
        # grouped by vendor change and operation, fleet-wide or narrowed to one repository.
        return JSONResponse(
            change_units_reader(
                repo_id=request.query_params.get("repo_id"),
                limit=_limit_param(request),
                offset=_offset_param(request),
            )
        )

    async def repo_context(request: Request) -> JSONResponse:
        return JSONResponse(context_reader(request.path_params["repo_id"]))

    async def set_repo_context(request: Request) -> JSONResponse:
        """Write one repository's context.

        The first write route on this app. The transport still holds no logic: it checks the
        body is a non-empty string within the cap, calls one writer, and returns the reader's
        view of what it wrote.

        Over the cap is refused rather than truncated, and the message names the limit -- a 400
        that does not say how long is too long leaves the caller guessing at a number this
        module knows.
        """
        try:
            payload = await request.json()
        except ValueError:
            # `request.json()` decodes the body before parsing it, so a client that sends bytes
            # that are not valid UTF-8 raises `UnicodeDecodeError` here, not just a JSON syntax
            # error -- and `UnicodeDecodeError` is a `ValueError`, so nothing needs its own
            # clause. Both failures get the same 400: either way the caller sent a body this
            # route cannot read as the JSON it asked for.
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        body = payload.get("body") if isinstance(payload, dict) else None
        if not isinstance(body, str) or not body.strip():
            return JSONResponse({"error": "body must be a non-empty string"}, status_code=400)
        if len(body) > CONTEXT_BODY_MAX:
            return JSONResponse(
                {"error": f"body must be at most {CONTEXT_BODY_MAX} characters"},
                status_code=400,
            )
        repo_id = request.path_params["repo_id"]
        context_writer(repo_id, body.strip())
        return JSONResponse(context_reader(repo_id))

    async def get_settings(request: Request) -> JSONResponse:
        repo_id = request.path_params["repo_id"]
        if settings_reader is None:
            return JSONResponse({"error": "Settings reader not configured"}, status_code=501)
        return JSONResponse(settings_reader(repo_id))

    async def set_settings(request: Request) -> JSONResponse:
        repo_id = request.path_params["repo_id"]
        if settings_writer is None:
            return JSONResponse({"error": "Settings writer not configured"}, status_code=501)
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
        merge_policy = payload.get("merge_policy")
        if merge_policy is not None:
            if merge_policy in REFUSED_MERGE_POLICIES:
                return JSONResponse(
                    {
                        "error": f"Merge policy '{merge_policy}' is refused: violates invariant 'nothing reaches a pull request unverified'",
                        "refusal_reason": REFUSED_MERGE_POLICIES[merge_policy],
                        "allowed_merge_policies": list(ALLOWED_MERGE_POLICIES),
                    },
                    status_code=400,
                )
            if merge_policy not in ALLOWED_MERGE_POLICIES:
                return JSONResponse(
                    {
                        "error": f"Invalid merge_policy '{merge_policy}'",
                        "allowed_merge_policies": list(ALLOWED_MERGE_POLICIES),
                    },
                    status_code=400,
                )
        merge_method = payload.get("merge_method")
        if merge_method is not None and merge_method not in ALLOWED_MERGE_METHODS:
            return JSONResponse(
                {
                    "error": f"Invalid merge_method '{merge_method}'",
                    "allowed_merge_methods": list(ALLOWED_MERGE_METHODS),
                },
                status_code=400,
            )
        base_branch = payload.get("base_branch")
        if base_branch is not None and (not isinstance(base_branch, str) or not base_branch.strip()):
            return JSONResponse(
                {"error": "base_branch must be a non-empty string"},
                status_code=400,
            )
        # The same refusal `sync run` makes at the CLI, made where the screen submits: a
        # filesystem path carries no owner and name for `gh api`, so accepting one here stores
        # a remote the loop cannot address. Empty clears the setting and is not an error.
        remote_url = payload.get("remote_url")
        if remote_url is not None:
            if not isinstance(remote_url, str):
                return JSONResponse({"error": "remote_url must be a string"}, status_code=400)
            candidate = remote_url.strip()
            if candidate and "://" not in candidate and not candidate.startswith("git@"):
                return JSONResponse(
                    {
                        "error": "remote_url must be a git remote URL (https://... or git@...), "
                        "not a path — the loop addresses the repository through the forge"
                    },
                    status_code=400,
                )
        try:
            settings_writer(repo_id, payload)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if settings_reader is not None:
            return JSONResponse(settings_reader(repo_id))
        return JSONResponse({"ok": True})

    routes = [
        Route("/api/overview", overview, methods=["GET"]),
        Route("/api/findings", findings_list, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/findings", findings_list, methods=["GET"]),
        Route("/api/repos/{repo_id:path}/findings", findings_list, methods=["GET"]),
        Route("/api/vendors/{vendor_id}", vendor_detail, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/changes", vendor_changes, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/operations", vendor_operations, methods=["GET"]),
        # Before `{finding_id}`: Starlette matches in declaration order, so a literal
        # segment registered after a path parameter is swallowed by it.
        Route("/api/findings/over-time", findings_over_time, methods=["GET"]),
        Route("/api/integration-changes/over-time", changes_over_time, methods=["GET"]),
        Route("/api/corpus/activity", remediation_activity, methods=["GET"]),
        Route("/api/findings/dismissals", dismissal_tally, methods=["GET"]),
        Route("/api/findings/{finding_id}", finding_detail, methods=["GET"]),
        Route("/api/findings/{finding_id}/patch", finding_patch, methods=["GET"]),
        Route("/api/findings/{finding_id}/dismissal", get_dismissal, methods=["GET"]),
        Route("/api/findings/{finding_id}/dismissal", set_dismissal, methods=["POST"]),
        Route("/api/workflows/{finding_id}", workflow, methods=["GET"]),
        Route("/api/runs", runs, methods=["GET"]),
        Route("/api/setup", setup, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/facts", codebase_facts_route, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/call-sites", call_sites_route, methods=["GET"]),
        Route("/api/integration-changes", integration_changes_route, methods=["GET"]),
        Route("/api/integrations", catalogue_route, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/topology", topology_route, methods=["GET"]),
        Route("/api/adapters/{vendor_id}/staging", get_staging, methods=["GET"]),
        Route("/api/adapters/{vendor_id}/staging", set_staging, methods=["POST"]),
        Route("/api/corpus", corpus, methods=["GET"]),
        Route("/api/corpus/health", corpus_health_endpoint, methods=["GET"]),
        Route("/api/corpus/abandonment", abandonment, methods=["GET"]),
        Route("/api/repositories", repositories, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/events", repository_events, methods=["GET"]),
        Route("/api/repositories/{repo_id}/events", repository_events, methods=["GET"]),
        Route("/api/change-units", change_units, methods=["GET"]),
        Route(
            "/api/vendors/{vendor_id}/operations/{operation_id}/bindings",
            binding,
            methods=["GET"],
        ),
        Route("/api/repositories/{repo_id:path}/coverage", repository_coverage, methods=["GET"]),
        Route("/api/repositories/{repo_id}/coverage", repository_coverage, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/change-volume", vendor_change_volume, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/graph", repository_graph, methods=["GET"]),
        Route("/api/repositories/{repo_id}/graph", repository_graph, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/observed", repository_observed, methods=["GET"]),
        Route("/api/repositories/{repo_id}/observed", repository_observed, methods=["GET"]),
        Route("/api/detectors", detectors, methods=["GET"]),
        Route("/api/adapters", adapters, methods=["GET"]),
        # `{repo_id:path}` rather than `{repo_id}`: a `repo_id` is `host/owner/name` and
        # contains slashes, so the default converter would never match one.
        Route("/api/repos/{repo_id:path}/context", repo_context, methods=["GET"]),
        Route("/api/repos/{repo_id:path}/context", set_repo_context, methods=["POST"]),
        Route("/api/repositories/{repo_id:path}/settings", get_settings, methods=["GET"]),
        Route("/api/repos/{repo_id:path}/settings", get_settings, methods=["GET"]),
        Route("/api/repositories/{repo_id:path}/settings", set_settings, methods=["POST"]),
        Route("/api/repos/{repo_id:path}/settings", set_settings, methods=["POST"]),
    ]

    from starlette.middleware import Middleware
    from sync.api.auth import AuthenticationMiddleware

    middleware = []
    if api_password:
        middleware.append(Middleware(AuthenticationMiddleware, password=api_password))

    return Starlette(routes=routes, middleware=middleware)


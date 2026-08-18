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

# The fleet roll-ups read the checkpointer and the graph store directly, outside `GraphSurface`
# -- same reasoning as `WorkflowReader`: a run, a repair record and a repo_id roll-up are not
# graph-surface questions, and folding them into the surface would ask one abstraction to speak
# three databases' worth of shape.
RunsReader = Callable[..., dict[str, Any]]
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
    api_password: str | None = None,
) -> Starlette:
    """Build the Starlette app bound to a particular surface and readers.

    Constructed rather than module-global so a test substitutes fakes without reaching into
    module state, and a deployment configures each reader once at start-up.

    Every reader is required rather than defaulted. A deployment that forgets one should fail
    at start-up with a `TypeError` naming the missing argument, not serve a route that 500s the
    first time a customer opens it.
    """
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
        # Forward finding-level fields: the finding's own rung, its severity, call site, and repository.
        return JSONResponse(
            {
                **payload,
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
                frame = "event: " + event["kind"] + "\n"
                frame += "data: " + json.dumps(event) + "\n\n"
                yield frame

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
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

    async def workflow(request: Request) -> JSONResponse:
        finding_id = request.path_params["finding_id"]
        payload = workflow_reader(finding_id)
        if payload is None:
            return _not_found("workflow", finding_id)
        return JSONResponse(payload)

    async def runs(request: Request) -> JSONResponse:
        repo_id = request.query_params.get("repo_id")
        limit = _limit_param(request)
        offset = _offset_param(request)
        return JSONResponse(runs_reader(repo_id=repo_id, limit=limit, offset=offset))

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
        return JSONResponse(
            binding_reader(
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
        )

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
        Route("/api/findings/{finding_id}", finding_detail, methods=["GET"]),
        Route("/api/workflows/{finding_id}", workflow, methods=["GET"]),
        Route("/api/runs", runs, methods=["GET"]),
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


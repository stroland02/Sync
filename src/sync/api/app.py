"""Starlette app: the transport for the operator console, over two answer sources.

The transport holds no logic. Per-finding routes are a thin call into `GraphSurface`, which
answers questions about one repository an agent is already pointed
at. Fleet-wide routes -- `/api/runs`, `/api/corpus`, `/api/repositories` -- answer a
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

from typing import Any, Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sync.mcp.tools import DEFAULT_LIMIT, GraphSurface

WorkflowReader = Callable[[str], Optional[dict[str, Any]]]

# The fleet roll-ups read the checkpointer and the graph store directly, outside `GraphSurface`
# -- same reasoning as `WorkflowReader`: a run, a repair record and a repo_id roll-up are not
# graph-surface questions, and folding them into the surface would ask one abstraction to speak
# three databases' worth of shape.
RunsReader = Callable[..., dict[str, Any]]
CorpusReader = Callable[[], dict[str, Any]]
RepositoriesReader = Callable[[], dict[str, Any]]

# The graph-rendering readers back `sync.dashboard.graph_views`, outside `GraphSurface` for the
# same reason the fleet readers above are: a binding surface, a per-repo coverage count and a
# detector roll-up are questions about the whole graph or about one repository, not the frozen
# surface's per-finding shape, and folding them in would ask one abstraction to speak a fourth
# question it was not built to answer.
BindingReader = Callable[..., dict[str, Any]]
CoverageReader = Callable[[str], dict[str, Any]]
ObservedReader = Callable[..., dict[str, Any]]
DetectorReader = Callable[[], dict[str, Any]]

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

# The overview reader backs `sync.dashboard.graph_views.overview_summary`: the fleet screen's
# vendor distribution and its bounded total, read straight from `GraphStore` in real SQL rather
# than from the frozen surface. `whats_at_risk` always walks every open finding doing one
# `get_call_site` round trip per row to build its shallow rows, so no `limit` passed to it bounds
# that scan -- this route used to call it twice (a probe, then a page sized to the probe's own
# total) and tally vendors in a Python loop over the result, which is the 9-19 second fleet screen
# `overview_summary`'s own docstring measures and fixes.
OverviewReader = Callable[[], dict[str, Any]]


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
    repositories_reader: RepositoriesReader,
    binding_reader: BindingReader,
    coverage_reader: CoverageReader,
    observed_reader: ObservedReader,
    detector_reader: DetectorReader,
    severity_reader: SeverityReader,
    overview_reader: OverviewReader,
    vendor_findings_reader: VendorFindingsReader,
) -> Starlette:
    """Build the Starlette app bound to a particular surface and readers.

    Constructed rather than module-global so a test substitutes fakes without reaching into
    module state, and a deployment configures each reader once at start-up.

    Every reader is required rather than defaulted. A deployment that forgets one should fail
    at start-up with a `TypeError` naming the missing argument, not serve a route that 500s the
    first time a customer opens it.
    """

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
        # Two fields, two meanings, and merging them would lose one. The envelope's
        # `binding_source` is the rung of the whole answer and goes null when the detectors
        # naming this call site disagree; `finding.binding_source` is the column on the row
        # the URL names, which is what a false positive has to be attributable to.
        return JSONResponse(
            {
                **payload,
                "finding": {
                    "finding_id": finding_id,
                    "binding_source": row["binding_source"],
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

    async def workflow(request: Request) -> JSONResponse:
        finding_id = request.path_params["finding_id"]
        payload = workflow_reader(finding_id)
        if payload is None:
            return _not_found("workflow", finding_id)
        return JSONResponse(payload)

    async def runs(request: Request) -> JSONResponse:
        limit = _limit_param(request)
        offset = _offset_param(request)
        return JSONResponse(runs_reader(limit=limit, offset=offset))

    async def corpus(request: Request) -> JSONResponse:
        return JSONResponse(corpus_reader())

    async def repositories(request: Request) -> JSONResponse:
        return JSONResponse(repositories_reader())

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
        return JSONResponse(coverage_reader(request.path_params["repo_id"]))

    async def repository_observed(request: Request) -> JSONResponse:
        return JSONResponse(
            observed_reader(
                request.path_params["repo_id"],
                calls_limit=_limit_param(request, "calls_limit"),
                calls_offset=_offset_param(request, "calls_offset"),
                shapes_limit=_limit_param(request, "shapes_limit"),
                shapes_offset=_offset_param(request, "shapes_offset"),
                error_windows_limit=_limit_param(request, "error_windows_limit"),
                error_windows_offset=_offset_param(request, "error_windows_offset"),
            )
        )

    async def detectors(request: Request) -> JSONResponse:
        return JSONResponse(detector_reader(repo_id=request.query_params.get("repo_id")))

    routes = [
        Route("/api/overview", overview, methods=["GET"]),
        Route("/api/vendors/{vendor_id}", vendor_detail, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/changes", vendor_changes, methods=["GET"]),
        Route("/api/findings/{finding_id}", finding_detail, methods=["GET"]),
        Route("/api/workflows/{finding_id}", workflow, methods=["GET"]),
        Route("/api/runs", runs, methods=["GET"]),
        Route("/api/corpus", corpus, methods=["GET"]),
        Route("/api/repositories", repositories, methods=["GET"]),
        Route(
            "/api/vendors/{vendor_id}/operations/{operation_id}/bindings",
            binding,
            methods=["GET"],
        ),
        Route("/api/repositories/{repo_id}/coverage", repository_coverage, methods=["GET"]),
        Route("/api/repositories/{repo_id}/observed", repository_observed, methods=["GET"]),
        Route("/api/detectors", detectors, methods=["GET"]),
    ]
    return Starlette(routes=routes)


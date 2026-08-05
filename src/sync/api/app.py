"""Starlette app: the transport for the operator console, over two answer sources.

The transport holds no logic. Per-finding and per-vendor routes are a thin call into
`GraphSurface`, which answers questions about one repository an agent is already pointed
at. Fleet-wide routes -- `/api/runs`, `/api/corpus`, `/api/repositories` -- answer a
different grain, every run or every attempt across repositories, which the frozen surface
answers no question about; those go through reader callables backed by `sync.dashboard`
instead. `app.py` constructs neither the surface nor the dashboard view model -- both are
built by the caller and handed in. Errors that a reader expresses as `None` become 404 with
a JSON body -- HTML would confuse a JSON client into treating a missing finding as a broken
deployment.

Every reader is a callable rather than a class for the same reason `workflow_reader` is: the
checkpointer, the corpus and the repository roll-up each live outside `GraphSurface`, in
stores the surface does not speak, and asking one abstraction to speak all of them would
fold unrelated responsibilities into it. `WorkflowReader` is `str -> dict | None`, matching
the shape the console consumes; the fleet readers below take the shape their own route
needs.
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


# Upper bound on a single scan of `whats_at_risk` when the transport needs to look up a
# finding by id. The surface does not offer a by-id read; the overview and finding routes
# fan through the same page and stop when they have what they need. Chosen as an operator
# ceiling rather than a truth about the graph: past this, the console pages instead.
_SCAN_LIMIT = 10_000

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


def _limit_param(request: Request) -> int:
    # `rows[offset : offset + limit]` in the surface treats a limit below 1 as a slice
    # bound, not a page size: negative turns the stop negative (an unbounded page from the
    # other end), zero returns nothing and never advances `next_offset`. The floor sits
    # here rather than in the surface because the frozen "paginate every list" rule belongs
    # to the transport, and `sync/mcp/tools.py` is not the surface to change.
    return min(max(_int_param(request, "limit", DEFAULT_LIMIT), 1), _MAX_LIMIT)


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
) -> Starlette:
    """Build the Starlette app bound to a particular surface and readers.

    Constructed rather than module-global so a test substitutes fakes without reaching into
    module state, and a deployment configures each reader once at start-up.

    Every reader is required rather than defaulted. A deployment that forgets one should fail
    at start-up with a `TypeError` naming the missing argument, not serve a route that 500s the
    first time a customer opens it.
    """

    async def overview(request: Request) -> JSONResponse:
        # Composed from `whats_at_risk` because the surface offers no aggregate read: the
        # overview is "what open findings do we hold, grouped by vendor". A separate
        # aggregate on the surface would repeat what the page already reports.
        page = surface.whats_at_risk(limit=_SCAN_LIMIT, offset=0)
        vendor_counts: dict[str, int] = {}
        for row in page["items"]:
            vendor = row["vendor"]
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
        vendors = [
            {"vendor_id": vendor_id, "open_finding_count": count}
            for vendor_id, count in sorted(vendor_counts.items())
        ]
        return JSONResponse(
            {
                "vendors": vendors,
                "total_findings": page["total"],
                "indexed_at": page["indexed_at"],
                "feed_fetched_at": page["feed_fetched_at"],
                "binding_source": page["binding_source"],
                "context_savings": page["context_savings"],
            }
        )

    async def vendor_detail(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        limit = _limit_param(request)
        offset = _int_param(request, "offset", 0)
        page = surface.whats_at_risk(vendor=vendor_id, limit=limit, offset=offset)
        return JSONResponse(page)

    async def finding_detail(request: Request) -> JSONResponse:
        finding_id = request.path_params["finding_id"]
        # `whats_at_risk` is the surface's window on open findings; scanning it is the only
        # by-id lookup the read surface offers, and the surface's own reasoning says a
        # closed finding is `None` rather than an error. `_SCAN_LIMIT` bounds the scan; a
        # deployment past that limit adds a by-id read to the surface rather than raising
        # it here.
        page = surface.whats_at_risk(limit=_SCAN_LIMIT, offset=0)
        row = next((r for r in page["items"] if r.get("finding_id") == finding_id), None)
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
        offset = _int_param(request, "offset", 0)
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
        offset = _int_param(request, "offset", 0)
        return JSONResponse(runs_reader(limit=limit, offset=offset))

    async def corpus(request: Request) -> JSONResponse:
        return JSONResponse(corpus_reader())

    async def repositories(request: Request) -> JSONResponse:
        return JSONResponse(repositories_reader())

    routes = [
        Route("/api/overview", overview, methods=["GET"]),
        Route("/api/vendors/{vendor_id}", vendor_detail, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/changes", vendor_changes, methods=["GET"]),
        Route("/api/findings/{finding_id}", finding_detail, methods=["GET"]),
        Route("/api/workflows/{finding_id}", workflow, methods=["GET"]),
        Route("/api/runs", runs, methods=["GET"]),
        Route("/api/corpus", corpus, methods=["GET"]),
        Route("/api/repositories", repositories, methods=["GET"]),
    ]
    return Starlette(routes=routes)

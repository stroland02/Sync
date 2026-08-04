"""Starlette app: one route per graph level, each a thin call into `GraphSurface`.

The transport holds no logic. Every handler pulls its arguments off the request, calls one
method on the surface (or the workflow reader), and returns the payload. Errors that the
surface expresses as `None` become 404 with a JSON body -- HTML would confuse a JSON client
into treating a missing finding as a broken deployment.

`workflow_reader` is a callable rather than a class because the checkpointer lives outside
`GraphSurface`: the graph and the checkpoint store are two databases, and asking the surface
to speak both would fold two responsibilities into one abstraction. The reader is `str ->
dict | None`, matching the shape the console consumes.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sync.mcp.tools import DEFAULT_LIMIT, GraphSurface

WorkflowReader = Callable[[str], Optional[dict[str, Any]]]


# Upper bound on a single scan of `whats_at_risk` when the transport needs to look up a
# finding by id. The surface does not offer a by-id read; the overview and finding routes
# fan through the same page and stop when they have what they need. Chosen as an operator
# ceiling rather than a truth about the graph: past this, the console pages instead.
_SCAN_LIMIT = 10_000


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


def _not_found(what: str, identifier: str) -> JSONResponse:
    return JSONResponse(
        {"error": f"{what} not found", "identifier": identifier}, status_code=404
    )


def create_app(
    *,
    surface: GraphSurface,
    workflow_reader: WorkflowReader,
) -> Starlette:
    """Build the Starlette app bound to a particular surface and workflow reader.

    Constructed rather than module-global so a test substitutes a fake surface without
    reaching into module state, and a deployment configures the surface once at start-up.
    """

    async def overview(request: Request) -> JSONResponse:
        # Composed from `whats_at_risk` because the surface offers no aggregate read: the
        # overview is "what open findings do we hold, grouped by vendor". A separate
        # aggregate on the surface would repeat what the page already reports.
        page = surface.whats_at_risk(limit=_SCAN_LIMIT, offset=0)
        vendor_counts: dict[str, int] = {}
        for row in page["items"]:
            vendor = row.get("vendor")
            if vendor is None:
                continue
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
            }
        )

    async def vendor_detail(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        limit = _int_param(request, "limit", DEFAULT_LIMIT)
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
        return JSONResponse(payload)

    async def vendor_changes(request: Request) -> JSONResponse:
        vendor_id = request.path_params["vendor_id"]
        limit = _int_param(request, "limit", DEFAULT_LIMIT)
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

    routes = [
        Route("/api/overview", overview, methods=["GET"]),
        Route("/api/vendors/{vendor_id}", vendor_detail, methods=["GET"]),
        Route("/api/vendors/{vendor_id}/changes", vendor_changes, methods=["GET"]),
        Route("/api/findings/{finding_id}", finding_detail, methods=["GET"]),
        Route("/api/workflows/{finding_id}", workflow, methods=["GET"]),
    ]
    return Starlette(routes=routes)

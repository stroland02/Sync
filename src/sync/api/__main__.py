"""Run the operator-console HTTP transport with uvicorn.

`python -m sync.api` starts a local server bound to the graph store the environment names, so
the frontend has one process to talk to during development. The GraphStore and checkpointer
DSNs come from environment variables rather than argv because a deployment already has them,
and duplicating one for a flag would let the two drift apart silently.
"""

from __future__ import annotations

import os

import uvicorn
from starlette.applications import Starlette

from sync.api.app import create_app
from sync.dashboard import fleet, graph_views
from sync.dashboard.queries import workflow_state
from sync.graph.store import GraphStore
from sync.mcp.tools import GraphSurface
from sync.obs.log import configure as configure_logging

# The port `web/vite.config.ts` proxies `/api` to. Named rather than inlined so
# tests/test_api_routes.py can bind the two together instead of asking them to agree by hand.
DEFAULT_PORT = 8787

# INFO rather than the stdlib's WARNING default: the module loggers beneath this transport
# call `log.info`, and a quieter default would leave them exactly as unreachable as before
# this module existed.
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "text"

# Off unless a deployment opts in: reload costs a file watcher and a subprocess, and a
# production process must never acquire either by accident.
DEFAULT_RELOAD = False

_RELOAD_TRUE = frozenset({"true", "1"})
_RELOAD_FALSE = frozenset({"false", "0"})


def _reload_enabled() -> bool:
    """Read `SYNC_API_RELOAD`, unset meaning `DEFAULT_RELOAD`.

    Same boundary ruling as `sync.obs.log.configure`: an unrecognised value raises instead of
    silently falling back, because a typo that fell back to "off" would be invisible and a
    typo that fell back to "on" would hand a production process a file watcher it never asked
    for.
    """
    raw = os.environ.get("SYNC_API_RELOAD")
    if raw is None:
        return DEFAULT_RELOAD
    value = raw.strip().lower()
    if value in _RELOAD_TRUE:
        return True
    if value in _RELOAD_FALSE:
        return False
    raise ValueError(
        f"unknown SYNC_API_RELOAD value {raw!r}; must be one of "
        f"{sorted(_RELOAD_TRUE | _RELOAD_FALSE)}"
    )


def app_factory() -> Starlette:
    """Build the console API app from the environment.

    uvicorn's `reload=True` cannot take an already-constructed app object: the reloader runs
    the app in a subprocess that re-imports it, so it needs an import string it can call
    (`uvicorn.run("sync.api.__main__:app_factory", factory=True, ...)`). This function is that
    import target, and `main` calls it too rather than repeating its body, so the reload and
    non-reload paths cannot build two different apps from the same environment.
    """
    configure_logging(
        level=os.environ.get("SYNC_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        fmt=os.environ.get("SYNC_LOG_FORMAT", DEFAULT_LOG_FORMAT),
    )
    dsn = os.environ["SYNC_GRAPH_DSN"]
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", dsn)
    store = GraphStore(dsn=dsn)
    surface = GraphSurface(store)

    def workflow_reader(finding_id: str):
        return workflow_state(checkpointer_dsn, finding_id)

    def runs_reader(*, limit: int, offset: int):
        return fleet.runs(checkpointer_dsn, limit=limit, offset=offset)

    def corpus_reader():
        return fleet.corpus_summary(store)

    def repositories_reader():
        return fleet.repositories(store)

    def abandonment_reader():
        return fleet.abandonment_by_change_kind(store)

    def binding_reader(
        vendor_id: str,
        operation_id: str,
        *,
        repo_id: str | None = None,
        path_prefix: str | None = None,
        binding_rung: str | None = None,
        call_sites_limit: int,
        call_sites_offset: int,
        changes_limit: int,
        changes_offset: int,
    ):
        return graph_views.binding_surface(
            store, vendor_id, operation_id,
            repo_id=repo_id, path_prefix=path_prefix, binding_rung=binding_rung,
            call_sites_limit=call_sites_limit, call_sites_offset=call_sites_offset,
            changes_limit=changes_limit, changes_offset=changes_offset,
        )

    def coverage_reader(repo_id: str):
        return graph_views.index_coverage(store, repo_id)

    def observed_reader(
        repo_id: str,
        *,
        calls_limit: int,
        calls_offset: int,
        shapes_limit: int,
        shapes_offset: int,
        error_windows_limit: int,
        error_windows_offset: int,
    ):
        return graph_views.observed_telemetry(
            store, repo_id,
            calls_limit=calls_limit, calls_offset=calls_offset,
            shapes_limit=shapes_limit, shapes_offset=shapes_offset,
            error_windows_limit=error_windows_limit, error_windows_offset=error_windows_offset,
        )

    def detector_reader(*, repo_id: str | None = None):
        return graph_views.detector_accountability(store, repo_id=repo_id)

    def severity_reader(*, repo_id: str | None = None, vendor_id: str | None = None):
        return graph_views.severity_rollup(store, repo_id=repo_id, vendor_id=vendor_id)

    def overview_reader(*, repo_id: str | None = None):
        return graph_views.overview_summary(store, repo_id=repo_id)

    def vendor_findings_reader(
        vendor_id: str,
        *,
        repo_id: str | None = None,
        severity: str | None = None,
        path: str | None = None,
        order: str | None = None,
        limit: int,
        offset: int,
    ):
        return graph_views.vendor_findings(
            store, vendor_id,
            repo_id=repo_id, severity=severity, path=path, order=order,
            limit=limit, offset=offset,
        )

    return create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        repositories_reader=repositories_reader,
        abandonment_reader=abandonment_reader,
        binding_reader=binding_reader,
        coverage_reader=coverage_reader,
        observed_reader=observed_reader,
        detector_reader=detector_reader,
        severity_reader=severity_reader,
        overview_reader=overview_reader,
        vendor_findings_reader=vendor_findings_reader,
    )


def main() -> None:
    host = os.environ.get("SYNC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SYNC_API_PORT", DEFAULT_PORT))
    if _reload_enabled():
        uvicorn.run("sync.api.__main__:app_factory", factory=True, host=host, port=port, reload=True)
    else:
        uvicorn.run(app_factory(), host=host, port=port)


if __name__ == "__main__":
    main()

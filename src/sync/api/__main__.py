"""Run the operator-console HTTP transport with uvicorn.

`python -m sync.api` starts a local server bound to the graph store the environment names, so
the frontend has one process to talk to during development. The GraphStore and checkpointer
DSNs come from environment variables rather than argv because a deployment already has them,
and duplicating one for a flag would let the two drift apart silently. Unset, they fall back to
`sync.graph.store.DEFAULT_DSN` -- the same database every CLI subcommand defaults to, and read
from the same constant rather than restated here.

This is the one entry point that never applies the schema, and that is deliberate: every route
is a read and no route mutates the graph, so a server that created tables would be the only
writer of DDL in the product that nobody ran on purpose. `main` refuses an empty database
instead, naming the commands that fill one.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import uvicorn
from starlette.applications import Starlette

from sync.api.app import create_app
from sync.api.auth import configured_api_password, validate_bind_security
from sync.core.models import RepoContext, RepoSettings
from sync.dashboard import catalog, fleet, graph_views, setup
from sync.dashboard.adapters import adapter_inventory
from sync.dashboard.patch import patch_for_finding
from sync.dashboard.queries import workflow_state
from sync.graph.store import DEFAULT_DSN, GraphStore, describe_dsn
from sync.mcp.tools import GraphSurface
from sync.obs.log import configure as configure_logging
from sync.signals import staging

# The port `web/vite.config.ts` proxies `/api` to. Named rather than inlined so
# tests/test_api_routes.py can bind the two together instead of asking them to agree by hand.
DEFAULT_PORT = 8787
# How many edges one graph response draws. A codebase with thousands of call sites would
# otherwise send every one of them to a canvas that cannot render them legibly anyway, and the
# payload says `truncated` beside the total so a partial picture is stated rather than implied.
GRAPH_BINDING_LIMIT = 2000

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


def graph_dsn() -> str:
    return os.environ.get("SYNC_GRAPH_DSN", DEFAULT_DSN)


def require_schema(store: GraphStore, dsn: str) -> None:
    """Refuse an empty database at start, naming the commands that fill one.

    Without this the server starts, the console loads, and every route answers 500 with an
    `UndefinedTable` in the log -- nine screens' worth of a failure whose remedy is one
    command. A reader arriving at that has no way to tell it from a broken build.
    """
    missing = store.missing_tables()
    if not missing:
        return
    raise SystemExit(
        f"sync.api: {describe_dsn(dsn)} has no graph schema "
        f"({len(missing)} tables absent, including {missing[0]}).\n"
        f"The console API is read-only and never creates tables. Apply the schema with one of:\n"
        f"  uv run python scripts/seed_console.py   # the schema, plus a fixture to look at\n"
        f"  uv run sync run --vendor stripe --from-version v2320 --to-version v2330 \\\n"
        f"      --repo https://github.com/<owner>/<name>\n"
        f"Set SYNC_GRAPH_DSN if the graph lives somewhere other than the default."
    )


def _ticket_json(ticket: dict) -> dict:
    """A ticket row with its instants spelled for JSON, in one place for both routes."""
    rendered = dict(ticket)
    for key in ("requested_at", "picked_up_at", "done_at"):
        value = rendered.get(key)
        if hasattr(value, "isoformat"):
            rendered[key] = value.isoformat()
    return rendered


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
    dsn = graph_dsn()
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", dsn)
    store = GraphStore(dsn=dsn)
    surface = GraphSurface(store)

    def workflow_reader(finding_id: str):
        return workflow_state(checkpointer_dsn, finding_id)

    def patch_reader(finding_id: str):
        return patch_for_finding(checkpointer_dsn, finding_id)

    def dismissal_reader(finding_id: str):
        """The current standing plus how many times it has flipped.

        Both in one payload because a screen that shows *dismissed* without showing that it
        has been dismissed and restored twice is telling a true fact in a misleading way.
        """
        state = store.dismissal_state(finding_id)
        return {**state, "history_count": store.dismissal_history_count(finding_id)}

    def dismissal_tally_reader():
        """Dismissed findings by reason, with the total the console renders beside them.

        The total is summed here rather than counted separately so the two cannot disagree: a
        second query would count at a different instant, and a tally whose parts do not add to
        its total is the kind of wrong that reads as a rounding artefact.

        `counts` carries only reasons that occur, and the store's docstring is explicit that a
        reason absent and a reason at nought are different claims it cannot make. The console
        must not render an absent reason as a zero.
        """
        counts = store.dismissal_reason_counts()
        return {"counts": counts, "total": sum(counts.values())}

    def dismissal_writer(finding_id: str, *, reason, actor: str) -> None:
        store.record_dismissal(finding_id, reason=reason, actor=actor)

    def runs_reader(
        *,
        repo_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        outcome: str | None = None,
    ):
        return fleet.runs(
            checkpointer_dsn,
            repo_id=repo_id,
            store=store,
            limit=limit,
            offset=offset,
            outcome=outcome,
        )

    def corpus_reader(*, repo_id: str | None = None):
        return fleet.corpus_summary(store, repo_id=repo_id)

    def corpus_health_reader():
        return fleet.corpus_health(store)

    def repositories_reader():
        return fleet.repositories(store)

    def facts_reader(repo_id: str):
        return store.codebase_facts(repo_id)

    def topology_reader(repo_id: str):
        return store.api_topology(repo_id)

    def catalogue_reader(*, repo_id: str | None = None):
        return catalog.integrations_catalogue(store, repo_id=repo_id)

    def integration_changes_reader(
        *,
        vendor_ids: Sequence[str] = (),
        severities: Sequence[str] = (),
        limit: int = 50,
        offset: int = 0,
    ):
        return store.vendor_changes_page(
            vendor_ids=vendor_ids, severities=severities, limit=limit, offset=offset
        )

    def call_sites_reader(
        repo_id: str,
        *,
        vendor_ids: Sequence[str] = (),
        operation_ids: Sequence[str] = (),
        loop_depths: Sequence[int] = (),
        binding_statuses: Sequence[str] = (),
        path_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return store.call_sites_page(
            repo_id,
            vendor_ids=vendor_ids,
            operation_ids=operation_ids,
            loop_depths=loop_depths,
            binding_statuses=binding_statuses,
            path_prefix=path_prefix,
            limit=limit,
            offset=offset,
        )

    def staging_reader(vendor_id: str):
        return {
            "vendor_id": vendor_id,
            "schema": staging.staging_schema(vendor_id),
            "values": staging.read_staging(vendor_id, Path("vendor-cache")),
        }

    def staging_writer(vendor_id: str, payload: dict):
        written = staging.write_staging(vendor_id, Path("vendor-cache"), payload)
        return {
            "vendor_id": vendor_id,
            "schema": staging.staging_schema(vendor_id),
            **written,
        }

    def setup_reader(*, repo_id: str | None = None):
        # The sole repository stands in when none is named — the install story is one codebase,
        # and the checklist is most useful before anybody has learned the query parameter.
        if repo_id is None:
            repo_ids = fleet.repositories(store).get("repo_ids", [])
            repo_id = repo_ids[0] if len(repo_ids) == 1 else None
        return setup.setup_checklist(store, repo_id=repo_id)

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

    def change_volume_reader(vendor_id: str):
        return graph_views.vendor_change_volume(store, vendor_id)

    def graph_reader(repo_id: str):
        return graph_views.repository_graph(store, repo_id, limit=GRAPH_BINDING_LIMIT)

    def events_reader(repo_id: str):
        """Decision 76's bus, as an iterator the route owns the lifetime of.

        Held open with no lifetime cap by owner selection, so the generator ends when the client
        goes and the listening connection closes with it. The heartbeat is emitted here rather
        than in the store because it is a fact about this stream being alive, not about the
        graph -- nothing in `sync.graph` should be inventing events.
        """
        with store.subscribe_events(repo_id) as stream:
            while True:
                event = stream.next(timeout=15.0)
                yield event if event is not None else {"kind": "heartbeat", "repo_id": repo_id}

    def findings_over_time_reader(*, repo_id: str | None = None):
        return graph_views.findings_by_kind_over_time(store, repo_id=repo_id)

    def vendor_operations_reader(vendor_id: str, *, repo_id: str | None = None):
        return graph_views.vendor_operation_exposure(store, vendor_id, repo_id=repo_id)

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

    def findings_reader(
        *,
        repo_id: str | None = None,
        vendor_id: str | None = None,
        severity: str | None = None,
        path: str | None = None,
        order: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return graph_views.findings_page(
            store,
            repo_id=repo_id,
            vendor_id=vendor_id,
            severity=severity,
            path=path,
            order=order,
            limit=limit,
            offset=offset,
        )

    def adapters_reader():
        return adapter_inventory(store)

    def change_units_reader(
        *,
        repo_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return fleet.change_units(
            store, checkpointer_dsn, repo_id=repo_id, severity=severity, limit=limit, offset=offset
        )

    def context_reader(repo_id: str):
        return graph_views.repo_context(store, repo_id)

    def context_writer(repo_id: str, body: str) -> None:
        store.upsert_repo_context(RepoContext(repo_id=repo_id, body=body, source="operator"))

    def settings_reader(repo_id: str):
        return graph_views.repo_settings(store, repo_id)

    def settings_writer(repo_id: str, payload: dict) -> None:
        current = store.repo_settings(repo_id)
        merge_policy = payload.get("merge_policy", current.merge_policy)
        merge_method = payload.get("merge_method", current.merge_method)
        base_branch = payload.get("base_branch", current.base_branch)
        # Absent key keeps the stored value; an explicit empty string clears it, because
        # "disconnect this remote" is an act the screen offers and None is how it is stored.
        remote_url = payload.get("remote_url", current.remote_url)
        if isinstance(remote_url, str):
            remote_url = remote_url.strip() or None
        store.upsert_repo_settings(
            RepoSettings(
                repo_id=repo_id,
                merge_policy=merge_policy,
                merge_method=merge_method,
                base_branch=base_branch.strip() if isinstance(base_branch, str) and base_branch.strip() else current.base_branch,
                remote_url=remote_url,
            )
        )

    return create_app(
        surface=surface,
        workflow_reader=workflow_reader,
        patch_reader=patch_reader,
        changes_over_time_reader=lambda *, vendor_id=None: graph_views.changes_over_time(
            store, vendor_id=vendor_id
        ),
        remediation_activity_reader=lambda: fleet.remediation_activity(store),
        dismissal_reader=dismissal_reader,
        dismissal_tally_reader=dismissal_tally_reader,
        dismissal_writer=dismissal_writer,
        runs_reader=runs_reader,
        corpus_reader=corpus_reader,
        corpus_health_reader=corpus_health_reader,
        repositories_reader=repositories_reader,
        abandonment_reader=abandonment_reader,
        binding_reader=binding_reader,
        coverage_reader=coverage_reader,
        graph_reader=graph_reader,
        change_volume_reader=change_volume_reader,
        observed_reader=observed_reader,
        vendor_operations_reader=vendor_operations_reader,
        findings_over_time_reader=findings_over_time_reader,
        events_reader=events_reader,
        detector_reader=detector_reader,
        adapters_reader=adapters_reader,
        severity_reader=severity_reader,
        overview_reader=overview_reader,
        vendor_findings_reader=vendor_findings_reader,
        change_units_reader=change_units_reader,
        context_reader=context_reader,
        context_writer=context_writer,
        findings_reader=findings_reader,
        settings_reader=settings_reader,
        settings_writer=settings_writer,
        setup_reader=setup_reader,
        staging_reader=staging_reader,
        staging_writer=staging_writer,
        facts_reader=facts_reader,
        call_sites_reader=call_sites_reader,
        integration_changes_reader=integration_changes_reader,
        topology_reader=topology_reader,
        catalogue_reader=catalogue_reader,
        call_site_source_reader=store.call_site_source,
        ticket_writer=lambda finding_id, repo_id: _ticket_json(
            store.create_ticket(finding_id, repo_id, source="operator")
        ),
        tickets_reader=lambda repo_id, *, source=None: [
            _ticket_json(t) for t in store.tickets(repo_id, source=source)
        ],
        # Off is the hosted posture; a local single-operator deployment serves its own source.
        serve_source=os.environ.get("SYNC_SERVE_SOURCE", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        api_password=configured_api_password(),
    )


def main() -> None:
    # Here rather than in `app_factory`: under `reload=True` the factory runs again in a
    # reloader subprocess on every edit, and one refusal at start is the whole of what a
    # reader needs.
    dsn = graph_dsn()
    require_schema(GraphStore(dsn=dsn), dsn)

    host = os.environ.get("SYNC_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SYNC_API_PORT", DEFAULT_PORT))
    password = configured_api_password()
    validate_bind_security(host, password)

    if _reload_enabled():
        uvicorn.run("sync.api.__main__:app_factory", factory=True, host=host, port=port, reload=True)
    else:
        uvicorn.run(app_factory(), host=host, port=port)


if __name__ == "__main__":
    main()

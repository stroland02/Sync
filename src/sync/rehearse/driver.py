"""Rehearsal driver for executing the Sync pipeline against zero-remote fixtures.

Safety guarantee:
This driver never constructs or accepts a `Forge`. The pipeline is compiled with
`forge=None`, which structurally omits `push_branch`, `await_ci`, and `open_pr`
from the graph. `--depth` selects how far routing proceeds (prepare vs full),
and is not what makes the run safe -- the absence of a Forge is the safety guarantee.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver

from sync.cli import (
    _checkout_branch,
    _coverage_lines,
    _detector_suite,
    _model_deprecations,
    _parameter_deprecations,
    _reset_clone,
    _scan,
    _select,
    _thread_to_invoke,
    build_remediator,
    load_catalogue,
    model_deprecation_sources,
    prepare_vendor,
    select_language_adapter,
)
from sync.detect.parameter_deprecation import LinkedDeprecation
from sync.graph.store import GraphStore
from sync.rehearse.fixture import prepare_fixture
from sync.remediate.graph import build_graph


class _RehearsalPrepareAdapter:
    """Wraps a LanguageAdapter for --depth prepare rehearsals.

    Setting unverifiable_reason causes route_after_prepare to route directly
    to report without invoking the remediator, preserving the locate -> prepare -> report
    graph execution while guaranteeing no model call is made.
    """

    def __init__(self, adapter: Any, reason: str = "rehearsal depth 'prepare' halts before remediation"):
        self._adapter = adapter
        self.unverifiable_reason = reason

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)


def run_rehearsal(args: argparse.Namespace, *, today: date | None = None) -> int:
    """Execute a rehearsal run against a fixture repository without remote access."""
    today = today or date.today()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    fixture_name = getattr(args, "fixture", "furever")
    repo = prepare_fixture(fixture_name, root=cache)

    prepared = prepare_vendor(
        args.vendor, args.from_version, args.to_version, cache=cache,
    )
    adapter = select_language_adapter(repo, prepared.adapter)

    with GraphStore(args.dsn) as store:
        call_sites = list(adapter.index(repo))
        store.replace_call_sites(repo.repo_id, call_sites)

        unread = adapter.unread_paths(repo)

        for change in prepared.changes:
            store.upsert_vendor_change(change)

        parameter_changes = _parameter_deprecations(
            prepared.documents, prepared.adapter, repo, call_sites, today=today,
        )
        _model_deprecations(store, repo, today=today)

        linked = [
            LinkedDeprecation(
                deprecation=deprecation,
                vendor_change_id=store.upsert_vendor_change(change),
            )
            for deprecation, change in parameter_changes
        ]

        findings = _scan(
            _detector_suite(
                store,
                spec_documents=prepared.documents,
                call_sites=call_sites,
                deprecations=linked,
                vendor_id=args.vendor,
                repo_id=repo.repo_id,
                deprecation_vendors=[
                    source.vendor_id for source in model_deprecation_sources()
                ],
            ),
            store,
        )

        for line in _coverage_lines(unread):
            print(line)

        print(f"{len(findings)} finding(s)")
        if not findings:
            return 0

        selected = _select(findings, args.limit)
        print(f"rehearsing {len(selected)} of {len(findings)}")

        depth = getattr(args, "depth", "prepare")
        if depth == "prepare":
            graph_adapter: Any = _RehearsalPrepareAdapter(adapter)
            catalogue = None
            remediator = None
        else:
            graph_adapter = adapter
            catalogue = load_catalogue()
            remediator = build_remediator(catalogue)

        run_id = args.run_id or f"rehearsal-{today.isoformat()}"

        with PostgresSaver.from_conn_string(args.dsn) as checkpointer:
            checkpointer.setup()
            graph = build_graph(
                store=store,
                adapter=graph_adapter,
                remediator=remediator,
                forge=None,
                checkpointer=checkpointer,
                catalogue=catalogue,
            )

            for finding in selected:
                base = f"{finding.id}:{run_id}"
                thread_id, resuming = _thread_to_invoke(graph, base)
                config = {"configurable": {"thread_id": thread_id}}

                if resuming:
                    branch = graph.get_state(config).values.get("branch")
                    if branch:
                        _checkout_branch(repo, branch)
                    graph.update_state(config, {"repo": repo})
                else:
                    _reset_clone(repo)
                    if adapter.discard_contaminated_dependencies(repo):
                        print("discarded the previous finding's dependency tree")

                state = graph.invoke(
                    None if resuming else {"finding": finding, "repo": repo},
                    config=config,
                )

                detail = (
                    state.get("pr_url")
                    or state.get("abandon_reason")
                    or state.get("report_reason")
                )
                print(f"{state['outcome']}: {detail}")

    return 0

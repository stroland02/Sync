"""Rehearsal driver for executing the Sync pipeline against zero-remote fixtures.

Safety guarantee:
This driver never constructs or accepts a `Forge`. The pipeline is compiled with
`forge=None`, which structurally omits `push_branch`, `await_ci`, and `open_pr`
from the graph. `--depth` selects how far routing proceeds (prepare vs full),
and is not what makes the run safe -- the absence of a Forge is the safety guarantee.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import Finding, RepoRef
from sync.detect.efficiency import EfficiencyDetector
from sync.detect.observed_drift import DeclaredField, ObservedDriftDetector
from sync.detect.parameter_deprecation import LinkedDeprecation, ParameterDeprecationDetector
from sync.detect.status_rate import StatusRateDetector
from sync.detect.vendor_change import VendorChangeDetector
from sync.graph.store import GraphStore
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.rehearse.fixture import prepare_fixture
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.graph import build_graph
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.remediate.parameters import (
    ParameterOmitRemediator,
    ParameterRenameRemediator,
)
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import TerminalTier, TieredRemediator
from sync.route.matrix import catalogue_index
from sync.signals.deprecations import (
    model_deprecation_sources,
    parameter_deprecation_sources,
    parameters_to_vendor_changes,
    parse_parameter_deprecations,
)
from sync.signals.oasdiff import run_oasdiff_checks
from sync.signals.registry import VendorContext, prepare_vendor

RESUMABLE_NODES = frozenset({"await_ci", "open_pr"})


class _RehearsalPrepareAdapter:
    """Wraps a LanguageAdapter for --depth prepare rehearsals.

    Setting unverifiable_reason causes route_after_prepare to route directly
    to report without invoking the remediator, preserving the locate -> prepare -> report
    graph execution while guaranteeing no model call is made.
    """

    def __init__(
        self,
        adapter: Any,
        reason: str = "rehearsal depth 'prepare' halts before remediation",
    ):
        self._adapter = adapter
        self.unverifiable_reason = reason

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)


def select_language_adapter(repo: RepoRef, vendor_adapter: Any) -> Any:
    declined: list[str] = []
    for build in (TypeScriptAdapter, PythonAdapter):
        adapter = build(vendor_adapter=vendor_adapter)
        if adapter.matches(repo):
            return adapter
        declined.append(f"{adapter.language}: {adapter.decline_reason(repo)}")
    raise RuntimeError(f"no language adapter matched {repo.repo_id}: {'; '.join(declined)}")


def load_catalogue() -> dict[str, dict]:
    return catalogue_index(run_oasdiff_checks())


def build_remediator(catalogue: dict[str, dict] | None = None) -> TieredRemediator:
    return TieredRemediator(
        [
            LiteralSwapRemediator(),
            ParameterOmitRemediator(),
            ParameterRenameRemediator(),
            PropertyOmitRemediator(),
            TerminalTier(AgentRemediator()),
        ],
        catalogue=catalogue,
    )


def _declared_fields(spec_documents: Sequence[Any]) -> list[DeclaredField]:
    declared: list[DeclaredField] = []
    for doc in spec_documents:
        declared.extend(getattr(doc, "declared_fields", ()))
    return declared


def _detector_suite(
    store: GraphStore,
    spec_documents: Sequence[Any],
    call_sites: Sequence[Any],
    deprecations: Sequence[LinkedDeprecation],
    vendor_id: str,
    repo_id: str,
    deprecation_vendors: Sequence[str] = (),
) -> list[tuple[str, Any]]:
    return [
        ("vendor_change", VendorChangeDetector(store, repo_id=repo_id)),
        ("parameter-deprecation", ParameterDeprecationDetector(deprecations, call_sites)),
        (
            "observed-drift",
            ObservedDriftDetector(
                store, _declared_fields(spec_documents), vendor_id, repo_id=repo_id
            ),
        ),
        *[
            (
                f"model-deprecation:{vendor}",
                VendorChangeDetector(store, vendor_id=vendor, repo_id=repo_id),
            )
            for vendor in deprecation_vendors
        ],
        ("status-rate", StatusRateDetector(store, repo_id=repo_id, vendor_id=vendor_id)),
        ("efficiency", EfficiencyDetector(store, repo_id=repo_id, vendor_id=vendor_id)),
    ]


def _scan(detectors: Sequence[tuple[str, Any]], store: GraphStore) -> list[Finding]:
    findings: list[Finding] = []
    for name, detector in detectors:
        try:
            produced = list(detector.scan())
        except Exception as exc:
            print(f"{name}: unavailable ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue

        for finding in produced:
            finding.id = store.insert_finding(finding)
        findings.extend(produced)
        declined = getattr(detector, "declined", None)
        note = f", {len(declined)} declined" if declined is not None else ""
        print(f"{name}: {len(produced)} finding(s){note}")

    return findings


def _select(findings: Sequence[Finding], limit: int) -> list[Finding]:
    return list(findings[:limit]) if limit > 0 else list(findings)


def _thread_to_invoke(graph: Any, base: str) -> tuple[str, bool]:
    generation = 0
    while True:
        thread_id = f"{base}:{generation}"
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        if snapshot.created_at is None:
            return thread_id, False
        if snapshot.next and set(snapshot.next) <= RESUMABLE_NODES:
            return thread_id, True
        generation += 1


def _checkout_branch(repo: RepoRef, branch: str) -> None:
    subprocess.run(
        ["git", "checkout", "-q", branch],
        cwd=repo.local_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _reset_clone(repo: RepoRef) -> None:
    subprocess.run(
        ["git", "reset", "-q", "--hard", "HEAD"],
        cwd=repo.local_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def run_rehearsal(args: argparse.Namespace, *, today: date | None = None) -> int:
    """Execute a rehearsal run against a fixture repository without remote access."""
    today = today or date.today()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    fixture_name = getattr(args, "fixture", "furever")
    repo = prepare_fixture(fixture_name, root=cache)

    context = VendorContext(
        cache_dir=cache,
        from_version=args.from_version,
        to_version=args.to_version,
    )
    prepared = prepare_vendor(args.vendor, context)
    adapter = select_language_adapter(repo, prepared.adapter)

    with GraphStore(args.dsn) as store:
        call_sites = list(adapter.index(repo))
        store.replace_call_sites(repo.repo_id, call_sites)

        unread = adapter.unread_paths(repo)

        for change in prepared.changes:
            store.upsert_vendor_change(change)

        parameter_changes: list[tuple[Any, Any]] = []
        for source in parameter_deprecation_sources():
            spec_file = cache / f"{source.vendor_id}-deprecations.md"
            if spec_file.exists():
                deprecations = parse_parameter_deprecations(
                    source.vendor_id, spec_file.read_text(encoding="utf-8")
                )
                parameter_changes.extend(parameters_to_vendor_changes(deprecations, today=today))

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

        for unread_path in unread:
            print(f"coverage: unread {unread_path}")

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

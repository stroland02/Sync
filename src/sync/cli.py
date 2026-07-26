"""Local driver for a Sync run. The only entry point at M0."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import Finding, RepoRef
from sync.detect.vendor_change import VendorChangeDetector
from sync.forge.github import GitHubForge
from sync.graph.store import GraphStore
from sync.index.typescript import TypeScriptAdapter
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.graph import build_graph
from sync.signals.stripe.adapter import StripeAdapter, fetch_spec
from sync.signals.stripe.symbols import build_symbol_map

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"


def _select(findings: list[Finding], limit: int) -> list[Finding]:
    """`--limit 0` takes every finding; `--limit N` takes the first N.

    Pulled out of `run()` so the selection rule is reachable by a test that
    never touches Postgres, the network, or the Agent SDK.
    """
    return findings if limit == 0 else findings[:limit]


def _clone(url: str, dest: Path) -> RepoRef:
    subprocess.run(["git", "clone", "--depth", "50", url, str(dest)], check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    return RepoRef(repo_id=dest.name, url=url, local_path=str(dest), head_sha=head)


def run(args: argparse.Namespace) -> int:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    base_spec = fetch_spec(args.from_version, cache / f"{args.from_version}.json")
    head_spec = fetch_spec(args.to_version, cache / f"{args.to_version}.json")

    symbol_map_path = cache / "symbols.json"
    symbol_map_path.write_text(
        json.dumps(build_symbol_map(json.loads(head_spec.read_text(encoding="utf-8")))),
        encoding="utf-8",
    )

    vendor = StripeAdapter(spec_dir=cache, symbol_map_path=symbol_map_path)
    adapter = TypeScriptAdapter(vendor_adapter=vendor)

    store = GraphStore(args.dsn)
    store.apply_schema()

    with tempfile.TemporaryDirectory() as workdir:
        repo = _clone(args.repo, Path(workdir) / "repo")

        if not adapter.matches(repo):
            print(f"{args.repo} does not depend on the Stripe SDK", file=sys.stderr)
            return 2

        for site in adapter.index(repo):
            store.upsert_call_site(site)
        for change in vendor.fetch_changes(args.from_version, args.to_version):
            store.upsert_vendor_change(change)

        # Persist findings before running the graph: `scan()` returns unsaved
        # findings with no id, and the checkpointer needs a stable thread_id.
        findings = []
        for finding in VendorChangeDetector(store).scan():
            finding.id = store.insert_finding(finding)
            findings.append(finding)

        print(f"{len(findings)} finding(s)")
        if not findings:
            return 0

        # Each finding costs an agent run, a push, and a full CI wait, in sequence.
        # A wide version range produces enough of them to run for hours, so the
        # default processes one. `--limit 0` takes them all.
        selected = _select(findings, args.limit)
        print(f"remediating {len(selected)} of {len(findings)}")

        with PostgresSaver.from_conn_string(args.dsn) as checkpointer:
            checkpointer.setup()
            graph = build_graph(
                store=store, adapter=adapter, remediator=AgentRemediator(),
                forge=GitHubForge(), checkpointer=checkpointer,
            )
            for finding in selected:
                # Finding ids are stable across runs, so the thread id carries the
                # commit too. Without it a second run resumes the finished checkpoint
                # and reports the old outcome without doing any work.
                thread_id = f"{finding.id}:{args.run_id or repo.head_sha[:12]}"
                state = graph.invoke(
                    {"finding": finding, "repo": repo},
                    config={"configurable": {"thread_id": thread_id}},
                )
                print(f"{state['outcome']}: {state.get('pr_url') or state.get('abandon_reason')}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sync")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="detect and remediate vendor changes in a repository")
    run_parser.add_argument("--vendor", default="stripe", choices=["stripe"])
    run_parser.add_argument("--from-version", dest="from_version", required=True)
    run_parser.add_argument("--to-version", dest="to_version", required=True)
    run_parser.add_argument("--repo", required=True, help="git URL of the repository to scan")
    run_parser.add_argument("--dsn", default=DEFAULT_DSN)
    run_parser.add_argument("--cache", default=".cache/specs")
    run_parser.add_argument("--limit", type=int, default=1, help="findings to remediate; 0 for all")
    run_parser.add_argument("--run-id", dest="run_id", default=None,
                            help="checkpoint namespace; defaults to the cloned commit")
    run_parser.set_defaults(func=run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

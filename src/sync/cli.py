"""Local driver for a Sync run. The only entry point at M0."""

from __future__ import annotations

import argparse
import json
import re
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
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import TerminalTier, TieredRemediator
from sync.signals.stripe.adapter import StripeAdapter, fetch_spec
from sync.signals.stripe.symbols import build_symbol_map

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"


def _select(findings: list[Finding], limit: int) -> list[Finding]:
    """`--limit 0` takes every finding; `--limit N` takes the first N.

    Pulled out of `run()` so the selection rule is reachable by a test that
    never touches Postgres, the network, or the Agent SDK.
    """
    return findings if limit == 0 else findings[:limit]


def build_remediator() -> TieredRemediator:
    """The tier cascade, cheapest first, with the agent last and unconditional.

    Pulled out of `run()` for the same reason `_select` is: the ordering is the whole
    economic claim and it should be checkable without Postgres, the network, or the Agent
    SDK. Until this existed nothing in `src/` constructed a `TieredRemediator` at all --
    `sync.route.matrix` classified changes and `TieredRemediator` composed tiers, and
    neither ran, because `build_graph` was handed a bare `AgentRemediator`.

    The agent is wrapped rather than listed. `nodes.make_patch` calls `propose()` directly
    and has never consulted `can_handle`, so the agent handles every finding today
    whatever its severity; a cascade that gated the last tier would make that dormant
    check live and narrow what the pipeline repairs, as a side effect of a change made for
    another reason entirely.
    """
    return TieredRemediator([
        LiteralSwapRemediator(),
        PropertyOmitRemediator(),
        TerminalTier(AgentRemediator()),
    ])


_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_PORT = re.compile(r":\d+/")


def _repo_id(url: str) -> str:
    """A repository's identity, derived from its remote rather than its checkout.

    Call site ids hash `repo_id`, so this value decides whether two customers
    whose `src/billing.ts` both call `stripe.charges.create` occupy one row or
    two. Every spelling of one remote has to reduce to one string: scheme,
    trailing `.git`, scp-style `git@host:owner/name`, a port, an embedded
    credential. The credential in particular must not survive, because the
    result is written to every `call_site` row and hashed into the branch name
    the forge pushes.

    Path case is preserved. GitHub is case-insensitive there, but not every
    host is, and splitting one repository in two is a cheaper mistake than
    merging two distinct ones.
    """
    remote = _SCHEME.sub("", url.strip().rstrip("/"))
    userinfo, at, rest = remote.partition("@")
    if at and "/" not in userinfo:
        remote = rest
    remote = _PORT.sub("/", remote, count=1)
    remote = remote.replace(":", "/", 1)
    host, _, path = remote.removesuffix(".git").partition("/")
    return f"{host.lower()}/{path}"


def _clone(url: str, dest: Path) -> RepoRef:
    subprocess.run(["git", "clone", "--depth", "50", url, str(dest)], check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    return RepoRef(repo_id=_repo_id(url), url=url, local_path=str(dest), head_sha=head)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        capture_output=True, text=True, encoding="utf-8",
    )


def _reset_clone(repo: RepoRef) -> None:
    """Return the clone to the commit it was cloned at.

    One clone serves every finding, and `push_branch` leaves HEAD on the branch
    it pushed with the patch committed. Without this the next finding's agent
    starts from the previous finding's tip: its branch carries that commit as a
    parent, its pull request shows both diffs, and its CI verifies a combination
    neither finding proposed. An abandoned finding is worse -- its edits are
    still in the tree, uncommitted, and `push_branch` stages with `git add -u`,
    so they land in the next finding's commit under a message describing
    something else.

    `git clean` runs without `-x`, so ignored files survive. `node_modules` is
    what `prepare` spent tens of seconds installing, and reinstalling it per
    finding would cost more than the clone this protects.
    """
    path = Path(repo.local_path)
    _git(["checkout", "-f", repo.head_sha], path)
    _git(["clean", "-fd"], path)


def _checkout_branch(repo: RepoRef, branch: str) -> None:
    """Put the clone on a branch some earlier process pushed.

    A resumed run's checkpoint describes a working copy that died with its
    temporary directory. `await_ci` reads HEAD out of the clone to match CI runs
    against the commit it pushed, so a fresh clone left on the default branch
    polls for the wrong sha and reports no CI run until it times out.
    """
    path = Path(repo.local_path)
    # The refspec is explicit because `git fetch origin <branch>` leaves only
    # FETCH_HEAD behind, and a resumed run that pushes again needs the
    # remote-tracking ref that `--force-with-lease` compares against.
    _git(["fetch", "origin", f"+{branch}:refs/remotes/origin/{branch}"], path)
    _git(["checkout", "-f", "-B", branch, f"origin/{branch}"], path)


# Nodes whose inputs outlive the process that produced them: what they need is
# in the pushed branch. A run interrupted before `push_branch` left its patch in
# a temporary directory that is now gone, so resuming it would typecheck a tree
# holding none of the work and then commit an empty index. Those start over.
RESUMABLE_NODES = frozenset({"await_ci", "open_pr"})


def _thread_to_invoke(graph, base: str) -> tuple[str, bool]:
    """Pick the checkpoint thread for one finding, and say whether to resume it.

    Two different situations otherwise share one thread id. A run that died
    mid-flight -- the worker restarted during the CI wait -- has to resume:
    re-entering it with input instead replays every node from the start, which
    here means a second agent run and a second pushed branch. A run that
    *finished* must not be re-entered at all: `finding.id` is a stable hash and
    `head_sha` is unchanged on a re-run against the same commit, so the operator
    who fixes a broken environment and runs again presents byte-identical
    coordinates, and that finished run's state -- `patch`, `verify_ok`,
    `static_fatal`, all of them read by routing functions -- would be merged
    into the new run as though it had produced them.

    The generation suffix separates the two: finished generations are stepped
    over, and the first unused or unfinished one is invoked. `snapshot.next`
    holds the tasks LangGraph still owes on a thread, so it distinguishes an
    interrupted run from a finished one; `created_at` distinguishes a thread
    that has never run from either.
    """
    generation = 0
    while True:
        thread_id = f"{base}:{generation}"
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        if snapshot.created_at is None:
            return thread_id, False
        if snapshot.next and set(snapshot.next) <= RESUMABLE_NODES:
            return thread_id, True
        generation += 1


def run(args: argparse.Namespace) -> int:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    fetch_spec(args.from_version, cache / f"{args.from_version}.json")
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

        # One transaction for the whole ingest. It holds an ACCESS EXCLUSIVE
        # lock on the graph tables from the TRUNCATE until it commits, so any
        # concurrent reader blocks for the length of the ingest rather than
        # reading the previous graph. That is acceptable only because M0 runs
        # one scan at a time; the alternative is worse, since a run that dies
        # part-way through would otherwise leave a graph that is neither the old
        # one nor the new one, and the detector cannot tell a missing row from
        # an absent call site.
        #
        # M0 has one entry point and no incremental indexing story: a stale row
        # from a previous invocation is indistinguishable from a real finding to
        # the detector, so every run starts from an empty graph. M2's incremental
        # indexing replaces this; a hosted control plane must never do this, since
        # it would erase other customers' state rather than just this one's.
        # Finding ids are stable hashes of (detector, call_site_id, vendor_change_id),
        # so a re-inserted finding gets the same id its checkpoint thread already
        # used -- checkpoint coordinates survive the truncate.
        with store.transaction():
            store.truncate_all()

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
                store=store, adapter=adapter, remediator=build_remediator(),
                forge=GitHubForge(), checkpointer=checkpointer,
            )
            for finding in selected:
                base = f"{finding.id}:{args.run_id or repo.head_sha[:12]}"
                thread_id, resuming = _thread_to_invoke(graph, base)
                config = {"configurable": {"thread_id": thread_id}}

                if resuming:
                    # The checkpoint's RepoRef names a temporary directory that
                    # died with the process that wrote it; only the pushed
                    # branch survived, so the clone goes there and the state
                    # learns where this process put its own copy.
                    _checkout_branch(repo, graph.get_state(config).values["branch"])
                    graph.update_state(config, {"repo": repo})
                else:
                    _reset_clone(repo)

                # Resuming takes `None`: an interrupted thread handed a payload
                # re-enters at START and redoes the patch and the push it had
                # already paid for.
                state = graph.invoke(
                    None if resuming else {"finding": finding, "repo": repo},
                    config=config,
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

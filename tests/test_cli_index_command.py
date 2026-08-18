"""`sync index --repo <path>`: the smallest change that turns an empty console into the user's
own code.

The beta-readiness assessment names this the blocker above all others. A stranger container could
not index anything -- `/api/repositories` answered `{"repo_ids": []}` and the console rendered
perfectly while holding nothing. The composition already existed inside `run` and had never been
exposed on its own.

**It must work offline, on a path, with no vendor staged and no credential.** `run` takes a remote
URL and clones it, which needs `gh` and a token; a first-run user has a checkout on disk and
neither. And `M14-W433` is what makes the offline case honest rather than merely possible: a
vendor that cannot be resolved is skipped and named, instead of being served by an adapter that
invented operation ids.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.cli import build_parser


def _repo_at(path: Path) -> Path:
    """A minimal TypeScript project that calls a vendor, on disk."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "package.json").write_text(
        json.dumps({"name": "demo", "dependencies": {"stripe": "^14.0.0"}}), encoding="utf-8"
    )
    src = path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "billing.ts").write_text(
        "import Stripe from 'stripe'\n"
        "const stripe = new Stripe('sk_test')\n"
        "export const pay = () => stripe.charges.create({ amount: 1 })\n",
        encoding="utf-8",
    )
    return path


class _RecordingStore:
    def __init__(self) -> None:
        self.written: dict[str, list] = {}
        self.runs: list[tuple] = []

    def apply_schema(self):
        # The command creates what it writes to, because it is the first thing a new deployment
        # runs. A double that could not accept this would be standing in for a narrower store
        # than the one the command actually calls.
        return None

    def replace_call_sites(self, repo_id, sites):
        self.written[repo_id] = list(sites)
        return [f"id-{i}" for i, _ in enumerate(sites)]

    def start_index_run(self, repo_id, *, started_at):
        self.runs.append(("start", repo_id))

    def finish_index_run(self, repo_id, *, started_at, finished_at, call_sites):
        self.runs.append(("finish", repo_id, call_sites))

    def fail_index_run(self, repo_id, *, started_at, at, outcome):
        self.runs.append(("fail", repo_id, outcome))


def test_the_parser_offers_an_index_subcommand():
    """It did not exist. `run`, `ingest`, `shapes`, `merge`, `publish`, `intake`, `benchmark`,
    `reconcile`, `rehearse` and `context` did."""
    args = build_parser().parse_args(["index", "--repo", "."])

    assert args.repo == "."
    assert hasattr(args, "func")


def test_index_accepts_a_path_rather_than_demanding_a_remote_url(tmp_path):
    """`run --repo` refuses a checkout and takes a git remote, because `gh api` addresses the same
    repository as owner/name. A first-run user has a directory and no credential, so this one
    takes the directory."""
    repo = _repo_at(tmp_path / "demo")

    args = build_parser().parse_args(["index", "--repo", str(repo)])

    assert Path(args.repo) == repo


def test_indexing_writes_the_call_sites_it_found(tmp_path, monkeypatch):
    import sync.cli as cli

    repo = _repo_at(tmp_path / "demo")
    store = _RecordingStore()
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)

    args = build_parser().parse_args(["index", "--repo", str(repo)])
    assert args.func(args) == 0

    assert store.written, "the index wrote no call sites for a repository that calls a vendor"


def test_indexing_records_the_pass_so_the_overview_can_say_it_finished(tmp_path, monkeypatch):
    """Decision 41: "Index finished, 1,204 call sites" must be readable after the toast. The
    command records the pass the same way `run` does, or the Overview has nothing to read."""
    import sync.cli as cli

    repo = _repo_at(tmp_path / "demo")
    store = _RecordingStore()
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)

    args = build_parser().parse_args(["index", "--repo", str(repo)])
    args.func(args)

    kinds = [r[0] for r in store.runs]
    assert kinds == ["start", "finish"], kinds


def test_indexing_reaches_no_network(tmp_path, monkeypatch):
    """The whole point of the offline path. `prepare_vendor` fetches a specification over the
    network and `run` depends on it; a first run has no network guarantee, no `gh` and no token.
    A vendor that cannot be resolved offline is skipped and named -- which is only safe because
    `M14-W433` deleted the adapter that used to invent operation ids in its place.
    """
    import sync.cli as cli
    import sync.index.codebase as codebase

    repo = _repo_at(tmp_path / "demo")
    store = _RecordingStore()
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(
        codebase, "prepare_vendor",
        lambda *a, **k: pytest.fail("sync index reached the network to resolve a vendor"),
    )

    args = build_parser().parse_args(["index", "--repo", str(repo)])

    assert args.func(args) == 0


def test_indexing_a_fresh_database_creates_what_it_writes_to(tmp_path):
    """Against a REAL database, because the fake store hid this.

    Every unit test above passed while `sync index` crashed on `relation "index_run" does not
    exist` -- a store double answers `start_index_run` whether or not the table is there. This is
    the first-run case exactly: somebody meeting Sync has a database that has never held anything.
    """
    import os

    from sync.cli import build_parser

    dsn = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
    repo = _repo_at(tmp_path / "demo")

    args = build_parser().parse_args(["index", "--repo", str(repo), "--dsn", dsn])

    assert args.func(args) == 0

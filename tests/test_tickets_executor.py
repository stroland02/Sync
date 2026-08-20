"""`sync tickets` is what makes the console's request button real.

The POST records a request and returns; this executor is the process that picks requests up.
These tests drive `cli.cmd_tickets` -- the production path -- with the heavy edges (clone,
vendor prep, checkpointer, remediation graph) faked and the store real, because the claim,
the finding load and the close are the wiring this verb adds and the database is where they
either converge or don't.
"""

from __future__ import annotations

import argparse
import contextlib
import os

import sync.cli as cli
from sync.core.models import CallSite, Finding, RepoRef, VendorChange
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

REPO = RepoRef(repo_id="acme", url="https://example.invalid/acme.git",
               local_path="unused", head_sha="abc123def456")


class _FakeGraph:
    def __init__(self, state: dict):
        self._state = state
        self.invocations: list[dict | None] = []

    def invoke(self, payload, config):
        self.invocations.append(payload)
        return self._state


def _seed_finding(store: GraphStore) -> str:
    site_id = store.upsert_call_site(
        CallSite(
            repo_id="acme", path="src/billing.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create", args_keys=["amount"],
            response_fields_read=["status"], sdk_version="18.0.0", content_hash="h-1",
        )
    )
    change_id = store.upsert_vendor_change(
        VendorChange(
            vendor_id="stripe", from_version="v2320", to_version="v2330",
            kind="response-property-removed", operation_id="PostCharges",
            path_ptr="/paths/x", severity="breaking", source="oasdiff",
        )
    )
    return store.insert_finding(
        Finding(
            detector="vendor_change", claim="response-field", call_site_id=site_id,
            vendor_change_id=change_id, severity="breaking", rationale="status removed",
            binding_rung="static",
        )
    )


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo=REPO.url, dsn=DSN, cache=".cache/specs", limit=0, run_id="test-run",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _wire_fakes(monkeypatch, graph: _FakeGraph) -> None:
    class _Adapter:
        def discard_contaminated_dependencies(self, repo):
            return False

    monkeypatch.setattr(cli, "prepare_vendor", lambda vendor, ctx: argparse.Namespace(adapter="prepared"))
    monkeypatch.setattr(cli, "_clone", lambda url, dest: REPO)
    monkeypatch.setattr(cli, "select_language_adapter", lambda repo, vendor: _Adapter())
    monkeypatch.setattr(cli, "load_catalogue", lambda: "catalogue")
    monkeypatch.setattr(cli, "build_remediator", lambda catalogue, repo_context: "remediator")
    monkeypatch.setattr(cli, "GitHubForge", lambda: "forge")
    monkeypatch.setattr(cli, "build_graph", lambda **kw: graph)
    monkeypatch.setattr(cli, "_thread_to_invoke", lambda g, base: (f"{base}:1", False))
    monkeypatch.setattr(cli, "_reset_clone", lambda repo: None)
    monkeypatch.setattr(cli, "RunHeartbeat", lambda dsn, thread_id: contextlib.nullcontext())

    class _FakeSaver:
        def setup(self):
            pass

    @contextlib.contextmanager
    def _fake_saver(dsn):
        yield _FakeSaver()

    monkeypatch.setattr(cli.PostgresSaver, "from_conn_string", staticmethod(_fake_saver))


def test_a_requested_ticket_runs_the_graph_and_closes_with_its_outcome(monkeypatch):
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()
    finding_id = _seed_finding(store)
    store.create_ticket(finding_id, "acme", source="operator")

    graph = _FakeGraph({"outcome": "opened", "pr_url": "https://github.com/x/y/pull/7"})
    _wire_fakes(monkeypatch, graph)

    assert cli.cmd_tickets(_args()) == 0

    assert len(graph.invocations) == 1
    invoked = graph.invocations[0]
    assert invoked is not None and invoked["finding"].id == finding_id
    settled = store.ticket_for_finding(finding_id)
    assert settled is not None
    assert settled["status"] == "done"
    assert settled["outcome"] == "opened"
    assert settled["detail"] == "https://github.com/x/y/pull/7"
    assert settled["thread_id"] == f"{finding_id}:test-run:1"


def test_a_ticket_whose_finding_was_retracted_closes_honestly(monkeypatch):
    # A scan can retract the finding between the request and the pickup. The ticket must close
    # saying so -- a row parked at picked_up forever would read as a runner that died.
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()
    store.create_ticket("f-gone", "acme", source="watch")

    graph = _FakeGraph({"outcome": "opened", "pr_url": "unreachable"})
    _wire_fakes(monkeypatch, graph)

    assert cli.cmd_tickets(_args()) == 0

    assert graph.invocations == []
    settled = store.ticket_for_finding("f-gone")
    assert settled is not None
    assert settled["status"] == "done"
    assert settled["outcome"] == "reported"
    assert settled["detail"] is not None and "retracted" in settled["detail"]


def test_the_limit_stops_the_loop_before_the_queue_is_empty(monkeypatch):
    store = GraphStore(DSN)
    store.apply_schema()
    store.truncate_all()
    finding_id = _seed_finding(store)
    store.create_ticket(finding_id, "acme", source="operator")
    store.create_ticket("f-2", "acme", source="watch")

    graph = _FakeGraph({"outcome": "abandoned", "abandon_reason": "tier refused"})
    _wire_fakes(monkeypatch, graph)

    assert cli.cmd_tickets(_args(limit=1)) == 0

    remaining = [t for t in store.tickets("acme") if t["status"] == "requested"]
    assert [t["finding_id"] for t in remaining] == ["f-2"]

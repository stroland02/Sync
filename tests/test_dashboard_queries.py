"""View-model queries: plain dicts out of the checkpointer tables.

The checkpoint fixtures insert rows the way langgraph-checkpoint-postgres 3.1.0
lays them out: `checkpoints(thread_id, checkpoint_ns, checkpoint_id,
parent_checkpoint_id, type, checkpoint, metadata)`, with primitive channel
values inlined under `checkpoint -> 'channel_values'` and only non-primitives
split out to `checkpoint_blobs` -- `PostgresSaver.put` is the reference. The
thread-id convention is `sync.cli`'s, not the plan's guess: a run's thread is
`{finding_id}:{run_id or head_sha[:12]}:{generation}`, so the queries must
match by prefix rather than by equality.
"""

import json
import os
import re
from pathlib import Path

import psycopg
import pytest

from sync.dashboard.queries import WORKFLOW_NODES, _EVIDENCE_KEYS, workflow_state

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FINDING_ID = "f" * 32


# --- the checkpointer side ---------------------------------------------------


@pytest.fixture()
def checkpointer_tables():
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(DSN) as saver:
        saver.setup()
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("TRUNCATE checkpoints, checkpoint_blobs, checkpoint_writes")
    yield


def _insert_checkpoint(
    thread_id: str,
    checkpoint_id: str,
    *,
    channel_values: dict,
    channel_versions: dict,
    versions_seen: dict,
    step: int,
) -> None:
    checkpoint = {
        "v": 4,
        "id": checkpoint_id,
        "ts": "2026-07-30T12:00:00.000000+00:00",
        "channel_values": channel_values,
        "channel_versions": channel_versions,
        "versions_seen": versions_seen,
    }
    metadata = {"source": "loop", "step": step, "parents": {}}
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id,
                                     parent_checkpoint_id, checkpoint, metadata)
            VALUES (%s, '', %s, NULL, %s, %s)
            """,
            (thread_id, checkpoint_id, json.dumps(checkpoint), json.dumps(metadata)),
        )


def _version(n: int) -> str:
    return f"{n:032}.0.123456"


def test_workflow_state_is_none_before_the_checkpointer_ever_ran():
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "DROP TABLE IF EXISTS checkpoints, checkpoint_blobs, "
            "checkpoint_writes, checkpoint_migrations"
        )

    assert workflow_state(DSN, FINDING_ID) is None


def test_workflow_state_is_none_when_the_finding_has_no_run(checkpointer_tables):
    _insert_checkpoint(
        "someotherfinding:abc123def456:0",
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened"},
        channel_versions={},
        versions_seen={},
        step=9,
    )

    assert workflow_state(DSN, FINDING_ID) is None


def test_workflow_state_reports_nodes_with_evidence_once_rows_exist(checkpointer_tables):
    # Mid-run: static_verify failed, the graph looped back, patch is due again.
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000005",
        channel_values={
            "prepare_ok": True,
            "verifiable": True,
            "tier": 2,
            "routing_row": "request-parameter-removed",
            "static_attempts": 1,
            "verify_ok": False,
            "diagnostics": "src/billing.ts(42,8): error TS2345",
        },
        channel_versions={
            "branch:to:patch": _version(5),
            "finding": _version(1),
            "repo": _version(1),
        },
        versions_seen={
            "__input__": {},
            "locate": {"branch:to:locate": _version(1)},
            "prepare": {"branch:to:prepare": _version(2)},
            "patch": {"branch:to:patch": _version(3)},
            "static_verify": {"branch:to:static_verify": _version(4)},
        },
        step=5,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert [n["name"] for n in state["nodes"]] == [
        "locate", "prepare", "patch", "static_verify",
        "replay", "push_branch", "await_ci", "open_pr",
    ]
    status = {n["name"]: n["status"] for n in state["nodes"]}
    assert status["locate"] == "done"
    assert status["prepare"] == "done"
    assert status["patch"] == "current"
    assert status["static_verify"] == "done"
    assert status["push_branch"] == "pending"
    assert status["open_pr"] == "pending"
    evidence = {n["name"]: n["evidence"] for n in state["nodes"]}
    assert evidence["static_verify"]["verify_ok"] is False
    assert evidence["static_verify"]["diagnostics"] == "src/billing.ts(42,8): error TS2345"
    assert evidence["locate"]["tier"] == 2
    assert state["outcome"] is None
    assert state["abandon_reason"] is None


def test_workflow_state_of_a_live_run_reports_no_outcome(checkpointer_tables):
    # `locate` writes `outcome: "running"` on the first hop of every run, so a live run's
    # newest checkpoint carries it for the whole rest of the run. The payload's `outcome`
    # is the console's terminal signal, and a run in flight has not reached one.
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000003",
        channel_values={
            "outcome": "running",
            "tier": 2,
            "routing_row": "request-parameter-removed",
            "prepare_ok": True,
        },
        channel_versions={"branch:to:patch": _version(3)},
        versions_seen={
            "__input__": {},
            "locate": {"branch:to:locate": _version(1)},
            "prepare": {"branch:to:prepare": _version(2)},
        },
        step=3,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["outcome"] is None
    status = {n["name"]: n["status"] for n in state["nodes"]}
    assert status["patch"] == "current"
    assert status["locate"] == "done"
    assert status["open_pr"] == "pending"


def test_workflow_state_of_an_abandoned_run_carries_the_reason(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000007",
        channel_values={
            "outcome": "abandoned",
            "abandon_reason": "static verification failed after 3 attempts",
            "verify_ok": False,
            "diagnostics": "error TS2345",
        },
        channel_versions={"branch:to:patch": _version(7)},
        versions_seen={
            "__input__": {},
            "locate": {"branch:to:locate": _version(1)},
            "prepare": {"branch:to:prepare": _version(2)},
            "patch": {"branch:to:patch": _version(3)},
            "static_verify": {"branch:to:static_verify": _version(4)},
            "abandon": {"branch:to:abandon": _version(6)},
        },
        step=7,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["outcome"] == "abandoned"
    assert state["abandon_reason"] == "static verification failed after 3 attempts"
    # A finished run has no current node, whatever the trigger channels say.
    assert all(n["status"] != "current" for n in state["nodes"])


def test_workflow_state_of_a_reported_run_carries_the_reason(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000008",
        channel_values={
            "outcome": "reported",
            "report_reason": "no patch is warranted for request-parameter-removed on "
                              "PostCharges: routed to tier -1 by row 'unrouted'",
            "tier": -1,
        },
        channel_versions={"branch:to:report": _version(6)},
        versions_seen={
            "__input__": {},
            "locate": {"branch:to:locate": _version(1)},
            "report": {"branch:to:report": _version(5)},
        },
        step=6,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["outcome"] == "reported"
    assert state["report_reason"] == (
        "no patch is warranted for request-parameter-removed on PostCharges: "
        "routed to tier -1 by row 'unrouted'"
    )


def test_workflow_state_of_a_reported_run_without_a_reason_reports_none(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:abc123def456:0",
        "1f069000-0000-6000-8000-000000000006",
        channel_values={"outcome": "reported"},
        channel_versions={"branch:to:report": _version(6)},
        versions_seen={
            "__input__": {},
            "locate": {"branch:to:locate": _version(1)},
            "report": {"branch:to:report": _version(5)},
        },
        step=6,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["outcome"] == "reported"
    assert state["report_reason"] is None


def test_workflow_state_reads_the_newest_run_not_the_first(checkpointer_tables):
    _insert_checkpoint(
        f"{FINDING_ID}:aaa111bbb222:0",
        "1f069000-0000-6000-8000-000000000009",
        channel_values={"outcome": "abandoned", "abandon_reason": "old run"},
        channel_versions={},
        versions_seen={"__input__": {}, "abandon": {"branch:to:abandon": _version(1)}},
        step=9,
    )
    _insert_checkpoint(
        f"{FINDING_ID}:aaa111bbb222:1",
        "1f069100-0000-6000-8000-000000000002",
        channel_values={"outcome": "opened", "pr_url": "https://github.com/x/y/pull/7"},
        channel_versions={},
        versions_seen={"__input__": {}, "open_pr": {"branch:to:open_pr": _version(1)}},
        step=11,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["outcome"] == "opened"
    evidence = {n["name"]: n["evidence"] for n in state["nodes"]}
    assert evidence["open_pr"]["pr_url"] == "https://github.com/x/y/pull/7"


def test_workflow_state_names_the_owning_thread_of_a_single_generation(checkpointer_tables):
    thread_id = f"{FINDING_ID}:abc123def456:0"
    _insert_checkpoint(
        thread_id,
        "1f069000-0000-6000-8000-000000000001",
        channel_values={"outcome": "opened", "pr_url": "https://github.com/x/y/pull/1"},
        channel_versions={},
        versions_seen={"__input__": {}, "open_pr": {"branch:to:open_pr": _version(1)}},
        step=3,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["thread_id"] == thread_id
    assert state["generation_count"] == 1


def test_workflow_state_of_three_generations_names_the_newest_threads_outcome(
    checkpointer_tables,
):
    # `f-multi-gen`'s own shape from the fleet-view review: retried across generations,
    # each with a different outcome. The fleet screen lists all three as separate rows;
    # this payload must say which one it is, not just which one it looks like.
    oldest = f"{FINDING_ID}:ccc333ddd444:0"
    middle = f"{FINDING_ID}:ccc333ddd444:1"
    newest = f"{FINDING_ID}:ccc333ddd444:2"
    _insert_checkpoint(
        oldest,
        "1f069200-0000-6000-8000-000000000001",
        channel_values={"outcome": "abandoned", "abandon_reason": "first attempt failed"},
        channel_versions={},
        versions_seen={"__input__": {}, "abandon": {"branch:to:abandon": _version(1)}},
        step=9,
    )
    _insert_checkpoint(
        middle,
        "1f069200-0000-6000-8000-000000000002",
        channel_values={"outcome": "abandoned", "abandon_reason": "second attempt failed"},
        channel_versions={},
        versions_seen={"__input__": {}, "abandon": {"branch:to:abandon": _version(1)}},
        step=9,
    )
    _insert_checkpoint(
        newest,
        "1f069200-0000-6000-8000-000000000003",
        channel_values={"outcome": "opened", "pr_url": "https://github.com/x/y/pull/9"},
        channel_versions={},
        versions_seen={"__input__": {}, "open_pr": {"branch:to:open_pr": _version(1)}},
        step=11,
    )

    state = workflow_state(DSN, FINDING_ID)

    assert state["generation_count"] == 3
    assert state["thread_id"] == newest
    assert state["outcome"] == "opened"
    evidence = {n["name"]: n["evidence"] for n in state["nodes"]}
    assert evidence["open_pr"]["pr_url"] == "https://github.com/x/y/pull/9"


# --- what the console mirrors from this module -------------------------------
#
# The console cannot import Python, so it restates the node order and the evidence keys
# this module owns. Nothing else holds the two sides together: `web/` has no CI gate, so a
# rename here and a stale copy there would both be correct on their own and wrong together.
# The parsing is deliberately loose -- it reads the names out of the TypeScript, not its
# formatting, because a guard that fails on a reflow is a guard that gets deleted.


def _web_source(relative: str) -> str:
    path = Path(__file__).resolve().parent.parent / "web" / relative
    if not path.is_file():
        pytest.skip(f"web/{relative} is absent; this checkout carries no console")
    return path.read_text(encoding="utf-8")


def _object_literal(source: str, name: str) -> str:
    """The body of a top-level `const <name> ... = { ... }`."""
    match = re.search(rf"const {name}\b[^{{]*\{{(.*?)\n\}}", source, re.S)
    assert match is not None, f"{name} is no longer a top-level object literal"
    return match.group(1)


def _array_literal(source: str, name: str) -> str:
    """The body of a top-level `export const <name> = [ ... ]`."""
    match = re.search(rf"export const {name}\b[^\[]*\[(.*?)\]", source, re.S)
    assert match is not None, f"{name} is no longer a top-level array literal"
    return match.group(1)


def test_the_consoles_node_order_matches_this_modules():
    # Bound to the exported array, not to the surrounding prose -- a docstring edit that
    # changes no code must not turn this suite red. `WORKFLOW_NODE_ORDER` is real code the
    # console type-checks `PURPOSE` against in `node-sequence.tsx`, not a decorative export.
    order = _array_literal(_web_source("src/api/types.ts"), "WORKFLOW_NODE_ORDER")
    assert re.findall(r'"([a-z_]+)"', order) == list(WORKFLOW_NODES)


def test_the_consoles_node_purposes_name_every_node_and_no_others():
    purposes = _object_literal(_web_source("src/features/workflows/node-sequence.tsx"), "PURPOSE")
    assert re.findall(r"^\s*([a-z_]+):", purposes, re.M) == list(WORKFLOW_NODES)


def test_the_consoles_evidence_fields_match_this_modules_keys():
    fields = _object_literal(_web_source("src/features/workflows/evidence.tsx"), "FIELDS")
    assert re.findall(r"^\s*([a-z_]+):\s*\[", fields, re.M) == list(WORKFLOW_NODES)

    rendered = re.findall(r'key:\s*"([^"]+)"', fields)
    assert len(rendered) == len(set(rendered)), "the console names an evidence key twice"
    assert set(rendered) == {key for keys in _EVIDENCE_KEYS.values() for key in keys}

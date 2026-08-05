"""Seed a development database with data every console screen renders, and remove it again.

Four separate verification rounds this milestone needed data to look at, found the database
empty, wrote a throwaway script to insert some, and deleted it. Each one re-derived the same
knowledge: which tables, which columns, and what shape the LangGraph `checkpoint` JSONB has to
carry for `sync.dashboard.queries._pending_node` to report a live node instead of nothing. This
script is that knowledge, committed once, so the next verification round points a browser at it
instead of writing SQL by hand.

It is a fixture, not a test -- `tests/test_seed_console.py` is the test, and it asserts through
the view models rather than through row counts alone.

Two databases, because they are two databases
-----------------------------------------------
The graph (`GraphStore`) and the LangGraph checkpointer are separate stores, exactly as
`sync.dashboard.queries`'s module docstring explains. `SYNC_GRAPH_DSN` and
`SYNC_CHECKPOINTER_DSN` are read the way `sync.api.__main__` reads them: the checkpointer DSN
defaults to the graph DSN when a deployment runs both on one Postgres, which every local
developer's does.

The marker
----------
Every row this script writes is reachable by one string: `MARKER` (`"seed-console"`), carried in
`call_site.repo_id`, `vendor_change.vendor_id` (and therefore `migration_outcome.vendor_id`, which
copies it from the change), and the run-id segment of every checkpoint `thread_id`. `finding` rows
are not marked directly -- they cascade-delete from `call_site` via the foreign key `schema.sql`
declares (`ON DELETE CASCADE`), which is also why the removal order below deletes call sites
before vendor changes. Marking the two columns that are already an *identity* (the repository, the
vendor) rather than adding a sentinel column means removal is a plain `LIKE` query against columns
the schema already has, and needs no schema change to stay exact.

Idempotent, because this pipeline's rule is
--------------------------------------------
Every `GraphStore` write used here already carries a natural key and a conflict clause --
`upsert_call_site`, `upsert_vendor_change`, `insert_finding`, `record_migration_outcome` -- so
running this script twice converges instead of doubling, without this script doing anything extra
to arrange it. The checkpoint rows get the same property by using a checkpoint id computed from a
fixed position in a fixed sequence (`_checkpoint_id`) rather than from wall-clock time or a random
UUID: `PostgresSaver.put`'s own conflict clause is keyed on `(thread_id, checkpoint_ns,
checkpoint_id)`, so the same id on the second run updates the same row instead of inserting a
second one.

Real models and real store methods throughout, deliberately
-------------------------------------------------------------
Every graph row is built from `sync.core` models and written through `GraphStore`'s own methods,
never a hand-written `INSERT`. A schema change that removes a column or renames a model field
breaks this script loudly instead of leaving it writing rows the rest of the code can no longer
read. The checkpoint rows go through `langgraph_checkpoint_postgres`'s own `PostgresSaver.put`
for the same reason -- there is no `GraphStore`-equivalent store for checkpoints, and hand-encoding
its JSONB shape would be a second copy of a format this script does not own.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import CallSite, Finding, MigrationOutcome, VendorChange
from sync.graph.store import GraphStore

MARKER = "seed-console"

REPO_A = f"{MARKER}-repo-a"
REPO_B = f"{MARKER}-repo-b"
VENDOR_STRIPE = f"{MARKER}-stripe"
VENDOR_TWILIO = f"{MARKER}-twilio"

# The checkpointer never sees a real host or a real repository. `sync.cli`'s convention is
# `{finding_id}:{run_id or head_sha[:12]}:{generation}` -- MARKER stands in for the run id, which
# both satisfies the convention and puts the marker directly in every thread_id this writes.
_THREAD_RUN_SEGMENT = MARKER


@dataclass(frozen=True)
class SeedSummary:
    """What got written, named so a caller -- a test or the CLI -- does not have to re-derive it."""

    repo_ids: tuple[str, ...]
    vendor_ids: tuple[str, ...]
    call_site_ids: tuple[str, ...]
    vendor_change_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    # The finding whose call site carries args_keys/response_fields_read and a known change --
    # the finding-detail screen's minimum bar.
    detailed_finding_id: str
    # The finding with two checkpointer generations -- the retried case `generation_count` exists
    # to report.
    retried_finding_id: str
    # The finding with a run still in flight -- no terminal outcome, a live current_node.
    live_finding_id: str
    # The finding with exactly one, finished run.
    terminal_finding_id: str
    thread_ids: tuple[str, ...] = field(default_factory=tuple)


def _looks_like_dev(dsn: str) -> bool:
    """Refuse anything whose host is not the loopback address a local Postgres binds to.

    This is the whole guard: a DSN naming any other host is refused outright, with no override
    flag. `docker-compose.yml` publishes Postgres on `127.0.0.1:5433`, so a legitimate local run
    always resolves here -- and a DSN that does not is, by construction, not this developer's own
    database. Seeding a real graph would be a genuinely bad afternoon; a hostname check that can
    be bypassed by a flag is not a guard, it is a warning with extra steps.
    """
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    host = (info.get("host") or "localhost").lower()
    return host in {"localhost", "127.0.0.1"}


def _describe(dsn: str) -> str:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    host = info.get("host") or "localhost"
    port = info.get("port") or "5432"
    dbname = info.get("dbname") or info.get("user") or "?"
    return f"{host}:{port}/{dbname}"


def _require_dev_dsn(dsn: str, label: str) -> None:
    if not _looks_like_dev(dsn):
        raise SystemExit(
            f"refusing to run: {label} {_describe(dsn)} does not look like a local development "
            f"database (host must be localhost or 127.0.0.1). This script writes and deletes "
            f"rows tagged '{MARKER}'; pointed at anything else, that is not a safe operation."
        )


# --- the graph side -----------------------------------------------------------


def _site(**kw) -> CallSite:
    base = dict(sdk_version="14.0.0", content_hash=f"{MARKER}-hash")
    base.update(kw)
    return CallSite(**base)


def _change(**kw) -> VendorChange:
    base = dict(source="oasdiff", raw={"text": "seeded for the console fixture"})
    base.update(kw)
    return VendorChange(**base)


def _finding(**kw) -> Finding:
    base = dict(detector="vendor-change", status="open")
    base.update(kw)
    return Finding(**base)


def _seed_graph(store: GraphStore) -> tuple:
    s1 = store.upsert_call_site(_site(
        repo_id=REPO_A, path="src/billing/charge.ts", line=42, col=8,
        vendor_id=VENDOR_STRIPE, operation_id="PostCharges", symbol="stripe.charges.create",
        content_hash=f"{MARKER}-hash-s1",
    ))
    s2 = store.upsert_call_site(_site(
        repo_id=REPO_A, path="src/billing/subscriptions.ts", line=77, col=4,
        vendor_id=VENDOR_STRIPE, operation_id="PostSubscriptions",
        symbol="stripe.subscriptions.create",
        args_keys=["customer", "items", "trial_period_days"],
        response_fields_read=["id", "status", "current_period_end"],
        content_hash=f"{MARKER}-hash-s2",
    ))
    s3 = store.upsert_call_site(_site(
        repo_id=REPO_A, path="src/billing/refunds.ts", line=15, col=2,
        vendor_id=VENDOR_STRIPE, operation_id="PostRefunds", symbol="stripe.refunds.create",
        loop_depth=1, content_hash=f"{MARKER}-hash-s3",
    ))
    s4 = store.upsert_call_site(_site(
        repo_id=REPO_B, path="src/notify/sms.ts", line=30, col=6,
        vendor_id=VENDOR_TWILIO, operation_id="CreateMessage", symbol="twilio.messages.create",
        sdk_version="4.19.0", content_hash=f"{MARKER}-hash-s4",
    ))
    s5 = store.upsert_call_site(_site(
        repo_id=REPO_B, path="src/notify/verify.ts", line=58, col=10,
        vendor_id=VENDOR_TWILIO, operation_id="CreateVerification",
        symbol="twilio.verify.v2.create", sdk_version="4.19.0",
        content_hash=f"{MARKER}-hash-s5",
    ))

    c1 = store.upsert_vendor_change(_change(
        vendor_id=VENDOR_STRIPE, from_version="2024-04-10", to_version="2024-06-20",
        kind="request-parameter-removed", operation_id="PostCharges",
        path_ptr="/paths/~1v1~1charges/post", severity="breaking",
        raw={"text": "charges lost a parameter"},
    ))
    c2 = store.upsert_vendor_change(_change(
        vendor_id=VENDOR_STRIPE, from_version="2024-06-20", to_version="2024-09-01",
        kind="response-field-type-changed", operation_id="PostSubscriptions",
        path_ptr="/paths/~1v1~1subscriptions/post", severity="warning",
        raw={"text": "current_period_end changed type"},
    ))
    store.upsert_vendor_change(_change(
        vendor_id=VENDOR_TWILIO, from_version="2024-01-01", to_version="2024-05-15",
        kind="field-deprecated", operation_id="CreateMessage",
        path_ptr="/paths/~1Messages/post", severity="deprecation", source="changelog",
        raw={"text": "status_callback deprecated"},
    ))

    f_a = store.insert_finding(_finding(
        claim="request-parameter-removed", call_site_id=s1, vendor_change_id=c1,
        severity="breaking",
        rationale="the call passes a parameter the vendor removed",
        binding_rung="static",
    ))
    f_b = store.insert_finding(_finding(
        claim="response-field-type-changed", call_site_id=s2, vendor_change_id=c2,
        severity="warning",
        rationale="the call reads a field whose type the vendor changed",
        binding_rung="resolved",
    ))
    f_c = store.insert_finding(_finding(
        detector="observed-drift", claim="shape-drift:/data/status", call_site_id=s4,
        severity="deprecation",
        rationale="traffic shows the field arriving deprecated, matching the vendor's changelog",
        binding_rung="observed",
    ))
    store.insert_finding(_finding(
        detector="efficiency", claim="loop", call_site_id=s3,
        severity="warning",
        rationale="the call runs inside a loop with no batching available",
        binding_rung="static",
    ))

    outcomes = [
        MigrationOutcome(
            finding_id=f_a, attempt_index=0, vendor_id=VENDOR_STRIPE,
            from_version="2024-04-10", to_version="2024-06-20",
            change_kind="request-parameter-removed", change_severity="breaking",
            operation_id="PostCharges", path_ptr="/paths/~1v1~1charges/post",
            language="typescript", sdk_version="14.0.0",
            symbol_shape="stripe.charges.create(object)", arg_arity=1,
            response_fields_touched_count=1, strategy="agent", tier=2,
            routing_row="request-parameter-removed", wall_ms=45_000,
            static_verify_passed=False, terminal_status="abandoned",
            abandon_reason="static verification failed after 3 attempts",
        ),
        MigrationOutcome(
            finding_id=f_a, attempt_index=1, vendor_id=VENDOR_STRIPE,
            from_version="2024-04-10", to_version="2024-06-20",
            change_kind="request-parameter-removed", change_severity="breaking",
            operation_id="PostCharges", path_ptr="/paths/~1v1~1charges/post",
            language="typescript", sdk_version="14.0.0",
            symbol_shape="stripe.charges.create(object)", arg_arity=1,
            response_fields_touched_count=1, strategy="agent", tier=2,
            routing_row="request-parameter-removed", wall_ms=52_000,
            static_verify_passed=True, terminal_status="opened",
            pr_number=101,
        ),
        MigrationOutcome(
            finding_id=f_b, attempt_index=0, vendor_id=VENDOR_STRIPE,
            from_version="2024-06-20", to_version="2024-09-01",
            change_kind="response-field-type-changed", change_severity="warning",
            operation_id="PostSubscriptions", path_ptr="/paths/~1v1~1subscriptions/post",
            language="typescript", sdk_version="14.0.0",
            symbol_shape="stripe.subscriptions.create(object)", arg_arity=3,
            response_fields_touched_count=3, strategy="codemod", tier=1,
            routing_row="response-field-type-changed", wall_ms=8_000,
        ),
        MigrationOutcome(
            finding_id=f_c, attempt_index=0, vendor_id=VENDOR_TWILIO,
            from_version="2024-01-01", to_version="2024-05-15",
            change_kind="field-deprecated", change_severity="deprecation",
            operation_id="CreateMessage", path_ptr="/paths/~1Messages/post",
            language="typescript", sdk_version="4.19.0",
            symbol_shape="twilio.messages.create(object)", arg_arity=2,
            response_fields_touched_count=1, strategy="codemod", tier=-1,
            routing_row="unrouted", wall_ms=1_200, terminal_status="reported",
        ),
    ]
    for outcome in outcomes:
        store.record_migration_outcome(outcome)

    return s1, s2, s3, s4, s5, c1, c2, f_a, f_b, f_c


# --- the checkpointer side -----------------------------------------------------


def _checkpoint_id(position: int) -> str:
    """A deterministic, sortable checkpoint id. Text order must be creation order.

    `checkpoints.checkpoint_id` is `TEXT`, and `sync.dashboard.queries.workflow_state` and
    `sync.dashboard.fleet.runs` both order by it to find the newest row -- `uuid6`'s own scheme,
    which `sync.cli` and langgraph itself rely on. A random or wall-clock id would make this
    script non-idempotent (`PostgresSaver.put`'s conflict clause is keyed on the id, so a fresh id
    every run inserts a fresh row every run instead of converging), so `position` is a fixed index
    into a fixed sequence this module defines, not a measurement of when the script ran.
    """
    return f"00000000-0000-6000-8000-{position:012x}"


def _version(n: int) -> str:
    return f"{n:032}.0.{MARKER}"


def _thread_id(finding_id: str, generation: int) -> str:
    return f"{finding_id}:{_THREAD_RUN_SEGMENT}:{generation}"


def _put(saver: PostgresSaver, thread_id: str, position: int, ts: str, step: int, *,
          channel_values: dict, channel_versions: dict, versions_seen: dict) -> None:
    checkpoint = {
        "v": 4,
        "id": _checkpoint_id(position),
        "ts": ts,
        "channel_values": channel_values,
        "channel_versions": channel_versions,
        "versions_seen": versions_seen,
        "pending_sends": [],
        "updated_channels": None,
    }
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    metadata = {"source": "loop", "step": step, "parents": {}}
    saver.put(config, checkpoint, metadata, {})


def _seed_checkpoints(checkpointer_dsn: str, f_a: str, f_b: str, f_c: str) -> tuple[str, ...]:
    """One finding retried across two generations, one live run, one single-generation finish.

    `f_a` gets two threads (an abandoned generation 0, an opened generation 1) so
    `workflow_state`'s `generation_count` has something to report greater than one. `f_b` gets one
    thread with no terminal `outcome`, so its `current_node` is live. `f_c` gets one thread that
    finished on its first generation. Values are read straight from `_EVIDENCE_KEYS` in
    `sync.dashboard.queries` -- every one of them is a primitive, which is what keeps
    `PostgresSaver.put` from splitting any of this into `checkpoint_blobs`.
    """
    thread_a0 = _thread_id(f_a, 0)
    thread_a1 = _thread_id(f_a, 1)
    thread_b0 = _thread_id(f_b, 0)
    thread_c0 = _thread_id(f_c, 0)

    with PostgresSaver.from_conn_string(checkpointer_dsn) as saver:
        saver.setup()

        _put(
            saver, thread_a0, 0, "2026-08-03T09:00:00.000000+00:00", step=6,
            channel_values={
                "tier": 2, "routing_row": "request-parameter-removed",
                "prepare_ok": True, "verifiable": True,
                "static_attempts": 3, "attempt_strategy": "agent",
                "verify_ok": False,
                "diagnostics": "src/billing/charge.ts(42,8): error TS2345: "
                               "argument of type 'undefined' is not assignable",
                "outcome": "abandoned",
                "abandon_reason": "static verification failed after 3 attempts",
            },
            channel_versions={"branch:to:patch": _version(6)},
            versions_seen={
                "__input__": {},
                "locate": {"branch:to:locate": _version(1)},
                "prepare": {"branch:to:prepare": _version(2)},
                "patch": {"branch:to:patch": _version(3)},
                "static_verify": {"branch:to:static_verify": _version(4)},
                "abandon": {"branch:to:abandon": _version(6)},
            },
        )

        _put(
            saver, thread_a1, 1, "2026-08-04T11:30:00.000000+00:00", step=10,
            channel_values={
                "tier": 2, "routing_row": "request-parameter-removed",
                "prepare_ok": True, "verifiable": True,
                "static_attempts": 1, "attempt_strategy": "agent",
                "verify_ok": True, "diagnostics": "",
                "replay_outcome": "passed",
                "replay_reason": "replayed against recorded traffic",
                "replay_evidence": "3 assertions passed",
                "branch": "sync/fix-post-charges-param",
                "ci_url": "https://github.com/example/repo/actions/runs/123456",
                "ci_attempts": 1, "attempt_ci_result": "success",
                "pr_url": "https://github.com/example/repo/pull/101", "pr_number": 101,
                "outcome": "opened",
            },
            channel_versions={"branch:to:open_pr": _version(9)},
            versions_seen={
                "__input__": {},
                "locate": {"branch:to:locate": _version(1)},
                "prepare": {"branch:to:prepare": _version(2)},
                "patch": {"branch:to:patch": _version(3)},
                "static_verify": {"branch:to:static_verify": _version(4)},
                "replay": {"branch:to:replay": _version(5)},
                "push_branch": {"branch:to:push_branch": _version(6)},
                "await_ci": {"branch:to:await_ci": _version(7)},
                "open_pr": {"branch:to:open_pr": _version(9)},
            },
        )

        _put(
            saver, thread_b0, 2, "2026-08-05T08:15:00.000000+00:00", step=4,
            channel_values={
                "tier": 1, "routing_row": "response-field-type-changed",
                "prepare_ok": True, "verifiable": True,
                "static_attempts": 1, "attempt_strategy": "codemod",
                "outcome": "running",
            },
            channel_versions={"branch:to:static_verify": _version(4)},
            versions_seen={
                "__input__": {},
                "locate": {"branch:to:locate": _version(1)},
                "prepare": {"branch:to:prepare": _version(2)},
                "patch": {"branch:to:patch": _version(3)},
            },
        )

        _put(
            saver, thread_c0, 3, "2026-08-02T16:45:00.000000+00:00", step=3,
            channel_values={
                "tier": -1, "routing_row": "unrouted",
                "outcome": "reported",
                "report_reason": "no patch is warranted for field-deprecated on "
                                  "CreateMessage: routed to tier -1 by row 'unrouted'",
            },
            channel_versions={"branch:to:report": _version(2)},
            versions_seen={
                "__input__": {},
                "locate": {"branch:to:locate": _version(1)},
                "report": {"branch:to:report": _version(2)},
            },
        )

    return thread_a0, thread_a1, thread_b0, thread_c0


# --- entry points ----------------------------------------------------------


def seed(graph_dsn: str, checkpointer_dsn: str) -> SeedSummary:
    """Write the fixture, converging if it is already there. Returns what got written."""
    store = GraphStore(graph_dsn)
    store.apply_schema()
    s1, s2, s3, s4, s5, c1, c2, f_a, f_b, f_c = _seed_graph(store)
    threads = _seed_checkpoints(checkpointer_dsn, f_a, f_b, f_c)

    return SeedSummary(
        repo_ids=(REPO_A, REPO_B),
        vendor_ids=(VENDOR_STRIPE, VENDOR_TWILIO),
        call_site_ids=(s1, s2, s3, s4, s5),
        vendor_change_ids=(c1, c2),
        finding_ids=(f_a, f_b, f_c),
        detailed_finding_id=f_b,
        retried_finding_id=f_a,
        live_finding_id=f_b,
        terminal_finding_id=f_c,
        thread_ids=threads,
    )


def remove(graph_dsn: str, checkpointer_dsn: str) -> None:
    """Delete exactly the rows `seed` writes, identified by `MARKER`, and nothing else.

    Recomputed from the marker rather than from a prior `seed()` call's return value, so `--remove`
    works standalone -- a caller need not have this process's memory of what got written, only the
    database and the marker.

    Deletion order matters for one reason: `finding.call_site_id REFERENCES call_site (id) ON
    DELETE CASCADE`, so deleting the marked call sites removes their findings for free, and the
    marked vendor changes and migration-outcome rows can be deleted afterwards with nothing left
    pointing at them.
    """
    with psycopg.connect(graph_dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM call_site WHERE repo_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM vendor_change WHERE vendor_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM migration_outcome WHERE vendor_id LIKE %s", (f"{MARKER}%",))

    with psycopg.connect(checkpointer_dsn, autocommit=True) as conn:
        has_checkpoints = conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0]
        if has_checkpoints is None:
            return
        pattern = f"%:{_THREAD_RUN_SEGMENT}:%"
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            conn.execute(f"DELETE FROM {table} WHERE thread_id LIKE %s", (pattern,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--remove", action="store_true",
        help="delete the seeded rows instead of writing them",
    )
    args = parser.parse_args(argv)

    graph_dsn = os.environ.get("SYNC_GRAPH_DSN", "postgresql://sync:sync@localhost:5433/sync")
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", graph_dsn)

    _require_dev_dsn(graph_dsn, "SYNC_GRAPH_DSN")
    _require_dev_dsn(checkpointer_dsn, "SYNC_CHECKPOINTER_DSN")

    if args.remove:
        print(f"removing rows tagged '{MARKER}' from:")
        print(f"  graph:        {_describe(graph_dsn)}")
        print(f"  checkpointer: {_describe(checkpointer_dsn)}")
        remove(graph_dsn, checkpointer_dsn)
        print("done.")
        return 0

    print(f"seeding rows tagged '{MARKER}' into:")
    print(f"  graph:        {_describe(graph_dsn)}")
    print(f"  checkpointer: {_describe(checkpointer_dsn)}")
    summary = seed(graph_dsn, checkpointer_dsn)
    print(
        f"wrote {len(summary.call_site_ids)} call sites, {len(summary.vendor_change_ids)} "
        f"vendor changes, {len(summary.finding_ids)} findings, {len(summary.thread_ids)} "
        f"checkpointer threads across {len(summary.repo_ids)} repositories and "
        f"{len(summary.vendor_ids)} vendors."
    )
    print(f"run with --remove to delete everything tagged '{MARKER}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

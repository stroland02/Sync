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
copies it from the change), `observed_call.repo_id`, `observed_shape.vendor_id`,
`observed_error_window.repo_id`, and the run-id segment of every checkpoint `thread_id`. `finding`
rows are not marked directly -- they cascade-delete from `call_site` via the foreign key
`schema.sql` declares (`ON DELETE CASCADE`), which is also why the removal order below deletes
call sites before vendor changes. Marking columns that are already an *identity* (the repository,
the vendor) rather than adding a sentinel column means removal is a plain `LIKE` query against
columns the schema already has, and needs no schema change to stay exact.

`observed_shape` carries no `repo_id` at all -- it is a vendor-wide baseline, not a per-repository
table (`schema.sql`'s own grain note) -- so its rows are marked and removed by `vendor_id` alone,
the same column `vendor_change` already uses.

Idempotent, because this pipeline's rule is
--------------------------------------------
Every `GraphStore` write used here already carries a natural key and a conflict clause --
`upsert_call_site`, `upsert_vendor_change`, `insert_finding`, `record_migration_outcome`,
`record_observed_call`, `record_observed_shape`, `record_observed_error_window` -- so running this
script twice converges on the same rows instead of doubling them, without this script doing
anything extra to arrange it. The checkpoint rows get the same property by using a checkpoint id
computed from a fixed position in a fixed sequence (`_checkpoint_id`) rather than from wall-clock
time or a random UUID: `PostgresSaver.put`'s own conflict clause is keyed on `(thread_id,
checkpoint_ns, checkpoint_id)`, so the same id on the second run updates the same row instead of
inserting a second one.

**One column does not converge on a value, by the table's own design, and it is named here rather
than left to be discovered.** `record_observed_shape` adds to `sample_count` for a traffic source
(`sync.graph.sources.TRAFFIC_SOURCES`) rather than holding it, because for real traffic a second
write is genuine evidence of a second response -- that is the whole point of the counter. The
seeded shape rows below use a traffic source so they are visible through
`GraphStore.observed_shapes`'s default (`traffic_only=True`), which every reader in
`sync.dashboard.graph_views` relies on, so `sample_count` grows by a fixed amount on every re-run
of this script. The row itself still converges -- same natural key, same identity, no duplicate --
and every other column on it is a fixed value that is unaffected. This is `record_observed_shape`
working as documented, not a defect in this script.

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
from datetime import datetime, timezone
from time import perf_counter as _perf_counter

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import (
    CallSite,
    Finding,
    MigrationOutcome,
    ObservedCall,
    ObservedErrorWindow,
    ObservedShape,
    VendorChange,
)
from sync.graph.store import GraphStore

MARKER = "seed-console"

REPO_A = f"{MARKER}-repo-a"
REPO_B = f"{MARKER}-repo-b"
VENDOR_STRIPE = f"{MARKER}-stripe"
VENDOR_TWILIO = f"{MARKER}-twilio"

# The scale repository, kept out of REPO_A/REPO_B on purpose: a caller measuring what ten
# thousand call sites cost the console must be able to remove exactly that load without
# touching the small, hand-shaped fixture the rest of this module writes.
SCALE_REPO_ID = f"{MARKER}-scale"

# Four vendors, several operations each, so a scale run exercises more than one row of the
# binding surface and more than one shape of path -- a uniform fixture would not have caught
# `packages/billing-service/src/infrastructure/adapters/stripe/charges/create-charge-handler.ts`,
# the longest path any fixture in this repository has carried before this one.
_SCALE_VENDORS = (
    (f"{MARKER}-scale-stripe", "stripe", ("charges", "subscriptions", "refunds", "payouts")),
    (f"{MARKER}-scale-twilio", "twilio", ("messages", "verify", "calls")),
    (f"{MARKER}-scale-github", "github", ("issues", "pulls", "actions")),
    (f"{MARKER}-scale-sendgrid", "sendgrid", ("mail", "templates")),
)
_SCALE_SERVICES = (
    "billing-service", "notifications-service", "identity-service", "orders-service",
)
_SCALE_SEVERITIES = ("breaking", "warning", "deprecation")
_SCALE_RUNGS = ("static", "resolved", "observed")
_SCALE_SDK_VERSIONS = ("14.0.0", "4.19.0", "2.3.1", "7.0.0")

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
    # `(vendor_id, operation_id)` more than one seeded call site is bound to -- the binding
    # surface's minimum bar, the way `detailed_finding_id` is the finding-detail screen's.
    shared_operation: tuple[str, str] = ("", "")
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
    # A second repository calling the same vendor operation as `s1` -- the binding surface's
    # whole reason to exist is a question that has more than one answer, and every other call
    # site above is the only site on its own operation.
    s6 = store.upsert_call_site(_site(
        repo_id=REPO_B, path="src/payments/create-charge.ts", line=21, col=6,
        vendor_id=VENDOR_STRIPE, operation_id="PostCharges", symbol="stripe.charges.create",
        content_hash=f"{MARKER}-hash-s6",
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
    # A fourth detector, reading telemetry rather than the static index or a vendor change --
    # `detector_accountability`'s whole point is that a detector's rung mix is a fact about the
    # kind of claim it makes, and one detector all-static plus one detector all-observed proves
    # less than a corpus where the same claim kind (`vendor-change`) shows up at more than one
    # rung, which `f_a` (static) and `f_b` (resolved) already give it.
    f_e = store.insert_finding(_finding(
        detector="status-rate", claim="error-rate-spike", call_site_id=s6,
        severity="warning",
        rationale="observed error rate for PostCharges exceeded its recorded baseline",
        binding_rung="observed",
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

    return s1, s2, s3, s4, s5, s6, c1, c2, f_a, f_b, f_c, f_e


# --- the observed rung ----------------------------------------------------------

# Fixed rather than `_now()`, for the same reason `_checkpoint_id` is fixed: `record_observed_call`
# and `record_observed_error_window` merge `first_seen`/`last_seen` with LEAST/GREATEST, so a
# wall-clock value would make every second run widen the window instead of converging on it.
_OBSERVED_SEEN = datetime(2026, 8, 1, tzinfo=timezone.utc)
_OBSERVED_LATER = datetime(2026, 8, 2, tzinfo=timezone.utc)
_WINDOW_START = datetime(2026, 8, 1, tzinfo=timezone.utc)
_WINDOW_END = datetime(2026, 8, 2, tzinfo=timezone.utc)


def _seed_observed(store: GraphStore) -> None:
    """The telemetry rung: what traffic showed up, what shape it had, how often it failed.

    Three tables, `sync.dashboard.graph_views.observed_telemetry`'s three reads:

    `observed_call` gets three rows. Two are `REPO_A` and `REPO_B` both calling Stripe's
    `PostCharges` -- the same shared operation `s1` and `s6` above give the binding surface,
    now with a telemetry rung on top of the static one. The third is deliberately uncorrelated
    (`operation_id=""`, `binding_rung="unresolved"`) so the console can render the case
    `ObservedCall`'s own docstring names: a request nothing could attribute to an operation.

    `observed_shape` gets two rows for Stripe's `PostCharges`, using a traffic source
    (`"interceptor"`) so `GraphStore.observed_shapes`'s traffic-only default surfaces them --
    see the module docstring for what that costs `sample_count` on a re-run.

    `observed_error_window` gets one row per repository, over the same fixed window, so
    `observed_telemetry` has a failure count to render for both repositories seeded above.
    """
    store.record_observed_call(ObservedCall(
        repo_id=REPO_A, vendor_id=VENDOR_STRIPE, operation_id="PostCharges",
        binding_rung="observed", server_address="api.stripe.com", http_method="post",
        trace_id=f"{MARKER}-trace-a", url_template="/v1/charges",
        spans={
            "span-1": {"target": f"{MARKER}-digest-1", "status": 200, "resend": 0},
            "span-2": {"target": f"{MARKER}-digest-2", "status": 500, "resend": 1},
        },
        first_seen=_OBSERVED_SEEN, last_seen=_OBSERVED_LATER,
    ))
    store.record_observed_call(ObservedCall(
        repo_id=REPO_B, vendor_id=VENDOR_STRIPE, operation_id="PostCharges",
        binding_rung="observed", server_address="api.stripe.com", http_method="post",
        trace_id=f"{MARKER}-trace-b", url_template="/v1/charges",
        # Two spans at the same target -- one repeated call, which is what
        # `ObservedCall.repeated_calls` exists to report.
        spans={
            "span-1": {"target": f"{MARKER}-digest-3", "status": 200, "resend": 0},
            "span-2": {"target": f"{MARKER}-digest-3", "status": 200, "resend": 0},
        },
        first_seen=_OBSERVED_SEEN, last_seen=_OBSERVED_LATER,
    ))
    store.record_observed_call(ObservedCall(
        repo_id=REPO_B, vendor_id=VENDOR_TWILIO, operation_id="", binding_rung="unresolved",
        server_address="api.twilio.com", http_method="post",
        trace_id=f"{MARKER}-trace-uncorrelated", url_template="",
        spans={"span-1": {"target": f"{MARKER}-digest-4", "status": None, "resend": 0}},
        first_seen=_OBSERVED_SEEN, last_seen=_OBSERVED_SEEN,
    ))

    store.record_observed_shape(ObservedShape(
        vendor_id=VENDOR_STRIPE, operation_id="PostCharges", field_path="/status",
        json_type="string", nullable_seen=False, spec_enum_values=["succeeded", "pending"],
        source="interceptor", sample_count=1,
        first_seen=_OBSERVED_SEEN, last_seen=_OBSERVED_LATER,
    ))
    store.record_observed_shape(ObservedShape(
        vendor_id=VENDOR_STRIPE, operation_id="PostCharges", field_path="/amount",
        json_type="number", nullable_seen=False, source="interceptor", sample_count=1,
        first_seen=_OBSERVED_SEEN, last_seen=_OBSERVED_LATER,
    ))

    store.record_observed_error_window(ObservedErrorWindow(
        repo_id=REPO_A, vendor_id=VENDOR_STRIPE, operation_id="PostCharges",
        binding_rung="observed", source="error-tracker-group", status_class="5xx",
        window_start=_WINDOW_START, window_end=_WINDOW_END,
        error_count=12, issue_count=2,
    ))
    store.record_observed_error_window(ObservedErrorWindow(
        repo_id=REPO_B, vendor_id=VENDOR_TWILIO, operation_id="CreateMessage",
        binding_rung="observed", source="error-tracker-group", status_class="4xx",
        window_start=_WINDOW_START, window_end=_WINDOW_END,
        error_count=3, issue_count=1,
    ))


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

    with PostgresSaver.from_conn_string(checkpointer_dsn) as saver:

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
    s1, s2, s3, s4, s5, s6, c1, c2, f_a, f_b, f_c, f_e = _seed_graph(store)
    _seed_observed(store)
    threads = _seed_checkpoints(checkpointer_dsn, f_a, f_b, f_c)

    return SeedSummary(
        repo_ids=(REPO_A, REPO_B),
        vendor_ids=(VENDOR_STRIPE, VENDOR_TWILIO),
        call_site_ids=(s1, s2, s3, s4, s5, s6),
        vendor_change_ids=(c1, c2),
        finding_ids=(f_a, f_b, f_c, f_e),
        detailed_finding_id=f_b,
        retried_finding_id=f_a,
        live_finding_id=f_b,
        terminal_finding_id=f_c,
        shared_operation=(VENDOR_STRIPE, "PostCharges"),
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
    pointing at them. `observed_call`, `observed_shape` and `observed_error_window` have no
    foreign key to anything else this script writes, so their order relative to the rest does not
    matter -- they are deleted here for the same reason everything else is: every row this script
    writes must have a way back to nothing.
    """
    with psycopg.connect(graph_dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM call_site WHERE repo_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM vendor_change WHERE vendor_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM migration_outcome WHERE vendor_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM observed_call WHERE repo_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM observed_shape WHERE vendor_id LIKE %s", (f"{MARKER}%",))
        conn.execute("DELETE FROM observed_error_window WHERE repo_id LIKE %s", (f"{MARKER}%",))

    with psycopg.connect(checkpointer_dsn, autocommit=True) as conn:
        has_checkpoints = conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0]
        if has_checkpoints is None:
            return
        pattern = f"%:{_THREAD_RUN_SEGMENT}:%"
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            conn.execute(f"DELETE FROM {table} WHERE thread_id LIKE %s", (pattern,))


def _executemany_values(
    conn: psycopg.Connection, prefix: str, suffix: str, columns_count: int,
    rows: list[tuple], *, chunk_size: int = 1000,
) -> None:
    """One multi-row `INSERT ... VALUES (...), (...), ...` per chunk, not one `INSERT` per row.

    `chunk_size` keeps each statement's parameter count (`columns_count * chunk_size`) well
    under Postgres's protocol limit of 65535 -- the widest table here is 13 columns, so 1000
    rows is 13000 parameters, comfortably inside it. Chunked round trips rather than one
    statement for all ten thousand rows for the same reason: the parameter count for the whole
    set would exceed the limit long before the row count did.
    """
    if not rows:
        return
    placeholder_row = "(" + ", ".join(["%s"] * columns_count) + ")"
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        values_sql = ", ".join([placeholder_row] * len(chunk))
        flat_params = [value for row in chunk for value in row]
        conn.execute(f"{prefix} {values_sql} {suffix}", flat_params)


def _scale_call_site_row(index: int) -> tuple:
    vendor_id, vendor_slug, resources = _SCALE_VENDORS[index % len(_SCALE_VENDORS)]
    resource = resources[index % len(resources)]
    service = _SCALE_SERVICES[index % len(_SCALE_SERVICES)]
    operation_id = f"Post{resource.capitalize()}"
    path = (
        f"packages/{service}/src/infrastructure/adapters/{vendor_slug}/{resource}/"
        f"create-{resource}-handler-{index:06d}.ts"
    )
    # Every third row carries the args/response detail the finding-detail screen looks for,
    # so a scale run has more than one call site shaped like that case -- the rest are the
    # common case, a call site with no static evidence beyond its own identity.
    if index % 3 == 0:
        args_keys = ["customer", "amount", "currency"]
        response_fields_read = ["id", "status"]
    else:
        args_keys, response_fields_read = [], []
    return (
        f"{MARKER}-scale-site-{index:06d}", SCALE_REPO_ID, path, (index % 500) + 1,
        (index % 20) + 1, vendor_id, operation_id, f"{vendor_slug}.{resource}.create",
        args_keys, response_fields_read, _SCALE_SDK_VERSIONS[index % len(_SCALE_SDK_VERSIONS)],
        f"{MARKER}-scale-hash-{index:06d}", index % 3,
    )


def _scale_finding_row(index: int) -> tuple:
    return (
        f"{MARKER}-scale-finding-{index:06d}", "vendor-change", f"synthetic-scale-load-{index % 7}",
        f"{MARKER}-scale-site-{index:06d}", None,
        _SCALE_SEVERITIES[index % len(_SCALE_SEVERITIES)], "synthetic finding seeded to measure",
        "open", _SCALE_RUNGS[index % len(_SCALE_RUNGS)],
    )


def seed_scale(graph_dsn: str, n: int) -> int:
    """Seed `n` synthetic call sites and `n` findings into `SCALE_REPO_ID`, beside the base
    fixture rather than instead of it. Returns `n`.

    Batched raw `INSERT`s rather than `upsert_call_site`/`insert_finding`, unlike everywhere
    else in this module -- those are one round trip per row, and looping them for ten thousand
    rows is the difference between seconds and minutes. Ids are computed from `index` rather
    than from content, the same idempotence argument `_checkpoint_id` makes: a fixed id per
    position converges a second run onto the same rows instead of accumulating a second set,
    and `ON CONFLICT (id) DO NOTHING` is sufficient because every column a given index produces
    is itself a deterministic function of that index.
    """
    store = GraphStore(graph_dsn)
    store.apply_schema()

    call_site_rows = [_scale_call_site_row(i) for i in range(n)]
    finding_rows = [_scale_finding_row(i) for i in range(n)]

    with psycopg.connect(graph_dsn, autocommit=True) as conn:
        _executemany_values(
            conn,
            "INSERT INTO call_site (id, repo_id, path, line, col, vendor_id, operation_id, "
            "symbol, args_keys, response_fields_read, sdk_version, content_hash, "
            "loop_depth) VALUES",
            "ON CONFLICT (id) DO NOTHING",
            13, call_site_rows,
        )
        _executemany_values(
            conn,
            "INSERT INTO finding (id, detector, claim, call_site_id, vendor_change_id, "
            "severity, rationale, status, binding_rung) VALUES",
            "ON CONFLICT (id) DO NOTHING",
            9, finding_rows,
        )

    return n


def remove_scale(graph_dsn: str) -> None:
    """Delete exactly the rows `seed_scale` writes, and nothing the base fixture wrote.

    An exact match on `SCALE_REPO_ID` rather than `remove`'s `LIKE f"{MARKER}%"` -- that pattern
    also matches `REPO_A`/`REPO_B`, so a `LIKE` here would delete the base fixture's call sites
    too. `finding.call_site_id REFERENCES call_site (id) ON DELETE CASCADE` removes the scale
    findings for free, the same reasoning `remove` gives for the base fixture's findings.
    """
    with psycopg.connect(graph_dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM call_site WHERE repo_id = %s", (SCALE_REPO_ID,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--remove", action="store_true",
        help="delete the seeded rows instead of writing them",
    )
    parser.add_argument(
        "--scale", type=int, metavar="N", default=None,
        help=(
            "seed N call sites (and N findings) into a synthetic scale repository, beside the "
            "base fixture rather than instead of it. Combine with --remove to delete them again "
            "-- N is not read on removal, only whether the flag is present. Does not affect what "
            "a plain run with no flags writes."
        ),
    )
    args = parser.parse_args(argv)

    graph_dsn = os.environ.get("SYNC_GRAPH_DSN", "postgresql://sync:sync@localhost:5433/sync")
    checkpointer_dsn = os.environ.get("SYNC_CHECKPOINTER_DSN", graph_dsn)

    _require_dev_dsn(graph_dsn, "SYNC_GRAPH_DSN")
    _require_dev_dsn(checkpointer_dsn, "SYNC_CHECKPOINTER_DSN")

    if args.scale is not None:
        if args.remove:
            print(f"removing scale rows tagged '{SCALE_REPO_ID}' from:")
            print(f"  graph: {_describe(graph_dsn)}")
            remove_scale(graph_dsn)
            print("done.")
            return 0

        print(f"seeding {args.scale} scale call sites tagged '{SCALE_REPO_ID}' into:")
        print(f"  graph: {_describe(graph_dsn)}")
        started = _perf_counter()
        count = seed_scale(graph_dsn, args.scale)
        elapsed = _perf_counter() - started
        print(f"wrote {count} call sites and {count} findings in {elapsed:.1f}s.")
        print(f"run with --scale {args.scale} --remove to delete them.")
        return 0

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

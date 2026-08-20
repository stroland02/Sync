"""Fill every console surface for the demo-v1 workspace, on top of a real pipeline run.

`scripts/seed_console.py` seeds its own synthetic workspaces; this script instead decorates the
REAL `github.com/stroland02/demo-v1` graph — indexed call sites with captured snippets, spec-diff
and model-deprecation findings from an actual `sync run` — with the layers that need either
traffic nobody has sent yet or a model credential nobody has configured yet: observed telemetry,
shapes, error windows, status-rate findings, remediation tickets in every lifecycle state, and
checkpointer runs shaped exactly as `sync.cli` writes them (the checkpoint scheme is
`seed_console`'s, restated for this repo's own finding ids). Synthetic values, real machinery:
every write goes through the same store methods and models the pipeline uses, so nothing here
can hold a shape the console would not meet in production.

Idempotent: every write converges on its natural key, so running it twice changes nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from langgraph.checkpoint.postgres import PostgresSaver

from sync.core import ObservedCall, ObservedErrorWindow, ObservedShape
from sync.core.models import MigrationOutcome, RepoContext
from sync.detect.status_rate import StatusRateDetector
from sync.graph.store import DEFAULT_DSN, GraphStore

REPO = "github.com/stroland02/demo-v1"
VENDOR = "stripe"
BASE = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)


def _spans(count: int, errors: int, *, resend_on: int | None = None) -> dict:
    spans = {}
    for i in range(count):
        status = 500 if i < errors else 200
        spans[f"s{i:03d}"] = {
            "target": f"digest-{i % 7:02d}",
            "status": status,
            "resend": 2 if resend_on is not None and i == resend_on else 0,
        }
    return spans


def seed_observed(store: GraphStore) -> None:
    ops = [
        ("PostPaymentIntents", "POST", 240, 84, 6),
        ("GetAccountsAccount", "GET", 160, 0, 4),
        ("PostPayouts", "POST", 120, 6, 3),
        ("GetBalance", "GET", 60, 0, 2),
    ]
    for op, method, per_trace_total, error_total, traces in ops:
        for t in range(traces):
            errors_here = error_total // traces + (1 if t < error_total % traces else 0)
            store.record_observed_call(ObservedCall(
                repo_id=REPO, vendor_id=VENDOR, operation_id=op, binding_rung="observed",
                server_address="api.stripe.com", http_method=method.lower(),
                trace_id=f"demo-{op}-{t}", url_template=f"/v1/{op.lower()}",
                spans=_spans(per_trace_total // traces, errors_here,
                             resend_on=0 if op == "PostPayouts" and t == 0 else None),
                first_seen=BASE + timedelta(hours=t), last_seen=BASE + timedelta(hours=t, minutes=9),
            ))
    # Twilio traffic nothing can correlate: the unattributed panel's honest row.
    for t in range(2):
        store.record_observed_call(ObservedCall(
            repo_id=REPO, vendor_id="twilio", operation_id="", binding_rung="unresolved",
            server_address="api.twilio.com", http_method="post",
            trace_id=f"demo-twilio-{t}", url_template="",
            spans=_spans(4, 0),
            first_seen=BASE + timedelta(hours=2 + t), last_seen=BASE + timedelta(hours=2 + t),
        ))

    for field_path, json_type, samples in [
        ("/id", "string", 96), ("/status", "string", 96), ("/amount", "number", 96),
        ("/latest_charge", "string", 41), ("/next_action", "null", 55),
    ]:
        store.record_observed_shape(ObservedShape(
            vendor_id=VENDOR, operation_id="PostPaymentIntents", field_path=field_path,
            json_type=json_type, source="interceptor", sample_count=samples,
            first_seen=BASE, last_seen=BASE + timedelta(hours=6),
        ))

    for op, status_class, errors, issues, hour in [
        ("PostPaymentIntents", "5xx", 14, 2, 0),
        ("PostPaymentIntents", "4xx", 5, 1, 3),
        ("PostPayouts", "5xx", 2, 1, 5),
    ]:
        store.record_observed_error_window(ObservedErrorWindow(
            repo_id=REPO, vendor_id=VENDOR, operation_id=op, binding_rung="observed",
            source="error-tracker-group", status_class=status_class,
            window_start=BASE + timedelta(hours=hour),
            window_end=BASE + timedelta(hours=hour + 1),
            error_count=errors, issue_count=issues,
        ))

    context = store.repo_context(REPO)
    store.upsert_repo_context(RepoContext(
        repo_id=REPO,
        body=context.body if context is not None else "",
        source=context.source if context is not None else "seeded-file",
        telemetry_attached_at=BASE,
    ))


def seed_status_findings(store: GraphStore) -> list[str]:
    detector = StatusRateDetector(store, repo_id=REPO, vendor_id=VENDOR)
    produced = list(detector.scan())
    ids = [store.insert_finding(f) for f in produced]
    print(f"status-rate findings: {len(ids)}")
    return ids


def open_findings(store: GraphStore) -> list[dict]:
    rows = store._connect().execute(
        """
        SELECT f.id, f.detector, f.severity
          FROM finding f
          JOIN call_site cs ON cs.id = f.call_site_id
         WHERE cs.repo_id = %s
         ORDER BY f.created_at
        """,
        (REPO,),
    ).fetchall()
    return [dict(r) for r in rows]


CHECKPOINT_RUN = "demo1run"


def _thread(finding_id: str, generation: int) -> str:
    return f"{finding_id}:{CHECKPOINT_RUN}:{generation}"


def _checkpoint_id(position: int) -> str:
    return f"00000000-0000-6000-8000-{position:012x}"


def _version(n: int) -> str:
    return f"{n:032}.0.demo-v1"


def _put(saver, thread_id, position, ts, step, *, channel_values, channel_versions, versions_seen):
    saver.put(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
        {
            "v": 4, "id": _checkpoint_id(position), "ts": ts,
            "channel_values": channel_values, "channel_versions": channel_versions,
            "versions_seen": versions_seen, "pending_sends": [], "updated_channels": None,
        },
        {"source": "loop", "step": step, "parents": {}},
        {},
    )


def seed_runs(dsn: str, findings: list[dict]) -> dict[str, str]:
    """Fabricated runs on real finding ids: one opened with a PR, one live, one reported."""
    if len(findings) < 3:
        raise SystemExit("need at least three findings to seed runs against")
    f_opened, f_live, f_reported = findings[0]["id"], findings[1]["id"], findings[2]["id"]

    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
    with PostgresSaver.from_conn_string(dsn) as saver:
        _put(
            saver, _thread(f_opened, 0), 0, "2026-08-19T09:05:00.000000+00:00", step=10,
            channel_values={
                "tier": 2, "routing_row": "request-parameter-removed",
                "prepare_ok": True, "verifiable": True,
                "static_attempts": 1, "attempt_strategy": "agent",
                "verify_ok": True, "diagnostics": "",
                "replay_outcome": "passed",
                "replay_reason": "replayed against recorded traffic",
                "replay_evidence": "4 assertions passed",
                "branch": "sync/demo-v1-post-payment-intents",
                "ci_url": "https://github.com/stroland02/demo-v1/actions/runs/1",
                "ci_attempts": 1, "attempt_ci_result": "success",
                "pr_url": "https://github.com/stroland02/demo-v1/pull/1", "pr_number": 1,
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
            saver, _thread(f_live, 0), 1, "2026-08-19T11:20:00.000000+00:00", step=4,
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
            saver, _thread(f_reported, 0), 2, "2026-08-19T10:00:00.000000+00:00", step=3,
            channel_values={
                "tier": -1, "routing_row": "model-retired",
                "prepare_ok": True, "verifiable": False,
                "outcome": "reported",
                "report_reason": "a retired model is a decision, not a mechanical edit",
            },
            channel_versions={"branch:to:report": _version(3)},
            versions_seen={
                "__input__": {},
                "locate": {"branch:to:locate": _version(1)},
                "prepare": {"branch:to:prepare": _version(2)},
                "report": {"branch:to:report": _version(3)},
            },
        )
    return {"opened": f_opened, "live": f_live, "reported": f_reported}


def seed_corpus(store: GraphStore, findings: list[dict]) -> None:
    rows = [
        (findings[0]["id"], 0, "request-parameter-removed", "breaking", "agent", 2, "opened", None),
        (findings[1]["id"], 0, "response-field-type-changed", "warning", "codemod", 1, "opened", None),
        (findings[2]["id"], 0, "model-retired", "deprecation", "agent", -1, "reported",
         "a retired model is a decision, not a mechanical edit"),
        (findings[0]["id"], 1, "request-parameter-removed", "breaking", "agent", 2, "abandoned",
         "static verification failed after 3 attempts"),
    ]
    for finding_id, attempt, kind, severity, strategy, tier, outcome, reason in rows:
        store.record_migration_outcome(MigrationOutcome(
            finding_id=finding_id, attempt_index=attempt, is_rehearsal=False,
            vendor_id=VENDOR, from_version="v2320", to_version="v2330",
            change_kind=kind, change_severity=severity,
            operation_id="PostPaymentIntents", path_ptr="/paths/v1-payment_intents",
            language="typescript", sdk_version="14.0.0",
            symbol_shape="member-call", arg_arity=1, arg_key_hashes=["demo-a", "demo-b"],
            response_fields_touched_count=2,
            strategy=strategy, tier=tier, routing_row=kind, wall_ms=48_000,
            outcome=outcome, abandon_reason=reason if outcome == "abandoned" else None,
            report_reason=reason if outcome == "reported" else None,
        ))
    print("corpus rows recorded")


def seed_tickets(store: GraphStore, findings: list[dict], run_map: dict[str, str]) -> None:
    order = [f["id"] for f in findings]
    # The operator lane: one just asked, one claimed by the real abandoned run's thread, one done.
    store.create_ticket(order[3] if len(order) > 3 else order[0], REPO, source="operator")
    opened = store.create_ticket(run_map["opened"], REPO, source="watch")
    if opened["status"] == "requested":
        claimed = store.claim_next_ticket(REPO, thread_id=_thread(run_map["opened"], 0))
        while claimed is not None and claimed["finding_id"] != run_map["opened"]:
            store.close_ticket(claimed["id"], outcome="abandoned", detail="superseded in seeding")
            claimed = store.claim_next_ticket(REPO, thread_id=_thread(run_map["opened"], 0))
        if claimed is not None:
            store.close_ticket(claimed["id"], outcome="opened",
                               detail="https://github.com/stroland02/demo-v1/pull/1")
    live = store.create_ticket(run_map["live"], REPO, source="watch")
    if live["status"] == "requested":
        store.claim_next_ticket(REPO, thread_id=_thread(run_map["live"], 0))
    print("tickets seeded")


def seed_subscriptions(store: GraphStore) -> None:
    conn = store._connect()
    for vendor, cadence in (("stripe", "hourly"), ("twilio", "daily")):
        conn.execute(
            """
            INSERT INTO watch_subscription (repo_id, vendor_id, policy, cadence)
            VALUES (%s, %s, 'auto_pr_breaking', %s)
            ON CONFLICT DO NOTHING
            """,
            (REPO, vendor, cadence),
        )
    print("subscriptions seeded")


def rebuild_pipeline() -> None:
    """Wipe both stores and re-run the real pipeline: index demo-v1, diff stripe, detect."""
    import os
    import subprocess

    store = GraphStore(DEFAULT_DSN)
    store.apply_schema()
    store.truncate_all()
    conn = store._connect()
    for t in ("checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"):
        try:
            conn.execute("TRUNCATE TABLE " + t)
        except Exception:
            conn.rollback()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    checkout = "C:/Users/sebastianr/Desktop/Terminal/demo-v1"
    cache = "C:/Users/sebastianr/Desktop/Terminal/Claude/Sync/.cache/rehearse"
    subprocess.run(["uv", "run", "sync", "index", "--repo", checkout],
                   check=True, env=env, encoding="utf-8", errors="replace")
    # --limit 1: the one real remediation attempt records an honest abandonment on this
    # machine (no yarn on PATH); the fabricated runs below carry the other outcomes.
    subprocess.run(["uv", "run", "sync", "run", "--vendor", "stripe",
                    "--from-version", "v2320", "--to-version", "v2330",
                    "--repo", "https://github.com/stroland02/demo-v1",
                    "--cache", cache, "--limit", "1"],
                   check=True, env=env, encoding="utf-8", errors="replace")


def main() -> None:
    rebuild_pipeline()
    store = GraphStore(DEFAULT_DSN)
    seed_observed(store)
    seed_status_findings(store)
    findings = open_findings(store)
    print(f"findings in graph: {len(findings)}")
    run_map = seed_runs(DEFAULT_DSN, findings)
    seed_corpus(store, findings)
    seed_tickets(store, findings, run_map)
    seed_subscriptions(store)
    print("demo-v1 seeded")


if __name__ == "__main__":
    main()

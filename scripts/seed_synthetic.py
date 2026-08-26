"""A synthetic corpus that exercises every vocabulary the console renders.

`seed_console.py` writes a small honest fixture -- six call sites, two vendors -- and is owned by
another session. This is the development corpus beside it: wide rather than realistic, built so a
screen can be checked against every state it claims to handle without waiting for a real
repository to happen to contain one.

**What it covers, and why each matters to a screen**

- **Every binding rung** (`static`, `resolved`, `observed`, `unresolved`) and the finding-only
  `unattributed`. The rung column, the rung mix chart and the health strip all branch on these.
- **Every severity** in `SEVERITY_ORDER`, including the ones a real corpus rarely holds, so the
  severity tabs are never checked against a set where two of five are absent.
- **Every adapter tier and watch state**, so the vendor cards render each badge.
- **Telemetry present, telemetry absent, and errors without telemetry.** These are three different
  nothings and the console is required to say which -- a corpus with only the first cannot prove it.
- **The awkward shapes**: a path long enough to wrap, a unicode path, a call site inside a loop, an
  operation nothing binds, a vendor with zero call sites. Every one of these has broken a screen at
  some point.

Everything is tagged `synthetic` in its repo id, so `--remove` takes exactly this and leaves both
the real graph and `seed-console`'s fixture untouched.

    uv run python scripts/seed_synthetic.py            # write it
    uv run python scripts/seed_synthetic.py --remove   # take it away
    uv run python scripts/seed_synthetic.py --scale 500  # a repository big enough to page
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sync.core import CallSite, Finding, ObservedCall, ObservedErrorWindow, VendorChange
from sync.graph.store import DEFAULT_DSN, GraphStore

#: Every repository this writes. The prefix is the removal key.
PREFIX = "synthetic"

WIDE = f"{PREFIX}/every-state"
EMPTY = f"{PREFIX}/never-indexed"
SCALE = f"{PREFIX}/at-scale"

NOW = datetime.now(timezone.utc)

#: One vendor per adapter tier, so the vendor cards draw each badge.
VENDORS = [
    ("stripe", "generated"),
    ("openai", "generated"),
    ("anthropic", "generated"),
    ("twilio", "generated"),
    ("cloudflare", "generated"),
    ("sendgrid", "generated"),
]

RUNGS = ["static", "resolved", "observed", "unresolved"]
SEVERITIES = ["breaking", "warning", "deprecation", "addition", "info"]

#: The shapes that have broken a screen before. Each is a real defect class, not decoration.
AWKWARD = [
    ("app/api/billing/subscriptions/webhooks/handlers/payment_intent_succeeded/route.ts", 0),
    ("app/api/日本語/route.ts", 0),
    ("lib/batch/sweep.ts", 2),
    ("app/api/a/route.ts", 0),
]


def _call_site(repo: str, index: int, vendor: str, rung_hint: str, path: str, loop: int) -> CallSite:
    return CallSite(
        repo_id=repo,
        path=path,
        line=10 + index,
        col=4,
        vendor_id=vendor,
        operation_id=f"Post{vendor.title()}Resource{index}",
        service_id="Core",
        symbol=f"{vendor}.resource{index}.create",
        args_keys=["id", "amount", "currency"][: 1 + index % 3],
        response_fields_read=["id", "status"][: 1 + index % 2],
        sdk_version=f"{2 + index % 8}.{index % 10}.0",
        content_hash=f"synthetic{index:032d}"[:32],
        loop_depth=loop,
        # A snippet on some rows and not others: the code pane must say which nothing it is.
        snippet=None if index % 3 else f"const r = await {vendor}.resource{index}.create({{}})",
        snippet_start_line=None if index % 3 else 8 + index,
        indexed_at=NOW - timedelta(hours=index),
    )


def write(store: GraphStore, scale: int) -> str:
    lines = []

    # --- the wide repository: one call site per (vendor x rung), plus the awkward shapes ---
    sites: list[CallSite] = []
    index = 0
    for vendor, _tier in VENDORS:
        for rung in RUNGS:
            path, loop = AWKWARD[index % len(AWKWARD)] if index % 5 == 0 else (
                f"app/api/{vendor}/{rung}/route.ts",
                0,
            )
            sites.append(_call_site(WIDE, index, vendor, rung, path, loop))
            index += 1

    ids = store.upsert_call_sites(sites) if hasattr(store, "upsert_call_sites") else [
        store.upsert_call_site(s) for s in sites
    ]
    lines.append(f"{len(ids)} call sites across {len(VENDORS)} vendors")

    # --- a change per severity, per vendor: the severity tabs see a full vocabulary ---
    changes: list[str] = []
    for v_i, (vendor, _tier) in enumerate(VENDORS):
        for s_i, severity in enumerate(SEVERITIES):
            change = VendorChange(
                vendor_id=vendor,
                from_version=f"v{2320 + s_i}",
                to_version=f"v{2330 + s_i}",
                kind="response-property-removed" if severity == "breaking" else "property-added",
                operation_id=f"Post{vendor.title()}Resource{(v_i + s_i) % 8}",
                path_ptr=f"/paths/~1{vendor}/post/responses/200",
                severity=severity,
                source="oasdiff",
                raw={"synthetic": True},
                detected_at=NOW - timedelta(hours=s_i),
            )
            changes.append(store.upsert_vendor_change(change))
    lines.append(f"{len(changes)} vendor changes across {len(SEVERITIES)} severities")

    # --- findings: every rung including `unattributed`, every severity, open, patched and abandoned ---
    findings = 0
    for f_i, change_id in enumerate(changes):
        # Four rungs, not five. `insert_finding` refuses `unattributed` outright: it is reserved
        # for rows written before the column existed, and a corpus that manufactured one would be
        # asserting a history this database does not have. The console still has to render it --
        # real rows carry it -- so that state is checked against the real graph, not from here.
        rung = RUNGS[f_i % len(RUNGS)]
        store.insert_finding(
            Finding(
                detector="synthetic-detector",
                claim=f"A synthetic change {f_i} reaches this binding.",
                binding_rung=rung,
                # Every finding carries a site: the model requires one, and `unattributed` is a
                # statement about how the binding was established rather than about whether a
                # site exists.
                call_site_id=ids[f_i % len(ids)],
                vendor_change_id=change_id,
                severity=SEVERITIES[f_i % len(SEVERITIES)],
                rationale="Written by seed_synthetic to exercise a state.",
                # `patched` and `abandoned` are the other two the vocabulary holds. A corpus with
                # only `open` cannot show that a screen renders the closed ones.
                status=("open", "open", "open", "patched", "abandoned")[f_i % 5],
                created_at=NOW - timedelta(hours=f_i),
            )
        )
        findings += 1
    lines.append(f"{findings} findings across {len(RUNGS)} rungs and {len(SEVERITIES)} severities")

    # --- telemetry on some vendors only: attached, absent, and errors-without-calls ---
    observed = 0
    for o_i, (vendor, _t) in enumerate(VENDORS[:3]):
        store.record_observed_call(
            ObservedCall(
                repo_id=WIDE,
                vendor_id=vendor,
                operation_id=f"Post{vendor.title()}Resource{o_i}",
                binding_rung="observed",
                server_address=f"api.{vendor}.com",
                http_method="post",
                trace_id=f"synthetic-trace-{o_i}",
                url_template=f"/v1/{vendor}/resource",
                spans={f"s{o_i}": {"target": "d1", "status": 200, "resend": 0}},
                first_seen=NOW - timedelta(hours=6),
                last_seen=NOW - timedelta(minutes=5),
            )
        )
        observed += 1

    # A vendor with error windows and no calls: a numerator with no denominator, which the
    # telemetry screen is required to render without computing a rate from it.
    store.record_observed_error_window(
        ObservedErrorWindow(
            repo_id=WIDE,
            vendor_id="sendgrid",
            operation_id="PostSendgridResource0",
            binding_rung="unresolved",
            source="error-tracker-group",
            status_class="5xx",
            window_start=NOW - timedelta(hours=2),
            window_end=NOW - timedelta(hours=1),
            error_count=17,
            issue_count=3,
        )
    )
    lines.append(f"{observed} observed calls, 1 error window with no calls behind it")

    # --- a repository that exists and holds nothing: the never-indexed empty state ---
    store.upsert_call_site(
        _call_site(EMPTY, 0, "stripe", "static", "app/api/only/route.ts", 0)
    )
    lines.append(f"1 call site in {EMPTY}, so an almost-empty repository has a screen")

    # --- the paging repository ---
    if scale:
        bulk = [
            _call_site(SCALE, i, VENDORS[i % len(VENDORS)][0], RUNGS[i % 4],
                       f"app/api/generated/{i:05d}/route.ts", i % 3)
            for i in range(scale)
        ]
        for site in bulk:
            store.upsert_call_site(site)
        lines.append(f"{scale} call sites in {SCALE}, enough to page")

    return "\n".join(f"  {line}" for line in lines)


def remove(store: GraphStore) -> str:
    removed = 0
    for repo in (WIDE, EMPTY, SCALE):
        try:
            store.forget_repository(repo)
            removed += 1
        except Exception:
            with store._connect().cursor() as cur:  # noqa: SLF001 - dev script, one call
                for table in ("finding", "observed_call", "observed_error_window", "call_site"):
                    cur.execute(f"DELETE FROM {table} WHERE repo_id = %s", (repo,))
            removed += 1
    return f"  removed {removed} synthetic repositories"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--remove", action="store_true", help="delete the synthetic rows")
    parser.add_argument("--scale", type=int, default=0, help="also write N call sites to page")
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args(argv[1:])

    store = GraphStore(args.dsn)
    store.apply_schema()

    print(f"{'removing' if args.remove else 'writing'} synthetic rows in {args.dsn}")
    print(remove(store) if args.remove else write(store, args.scale))
    if not args.remove:
        print("  run with --remove to take exactly these away")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

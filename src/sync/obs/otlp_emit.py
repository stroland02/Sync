"""OTLP spans for the vendor calls Sync itself makes.

**Why this exists.** The observed rung was empty because nothing produced traffic for it. The only
payloads available were vendor fixtures describing calls that never happened here, and ingesting
those would have made the console claim it observed traffic it did not -- the exact substitution
the product refuses. Sync does make real vendor calls: every agent run reaches
`api.anthropic.com`, and Sync's own index finds 43 Anthropic call sites in this codebase. So the
honest source of observed traffic is Sync watching itself.

**A span here records a call that happened.** Start and end are measured, the status is what came
back, and the operation is resolved by the same adapter that resolves a customer's traffic. Nothing
is synthesised: if no call is made, no span is written, and the rung stays empty and says so.

**Shapes, not values.** `graph-grain.md` forbids storing free-form values, and the boundary is
here rather than downstream: an attribute set carries the method, the host, the route and the
status code. No prompt, no completion, no token content, no identifier. That is a threat-model
commitment and this module is one of the places it would be easiest to break.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Where spans accumulate between ingests. Under the cache rather than the repository: this is a
# by-product of running, not a source artifact, and a run that crashes should not leave a diff.
DEFAULT_SPOOL = Path(".cache/telemetry/spans.jsonl")

# The environment switch. Off by default and explicitly opt-in: emitting telemetry is a side
# effect, and a library that wrote files because it was imported would be the kind of surprise
# `CLAUDE.md` treats as a defect rather than a feature.
ENABLE_VAR = "SYNC_EMIT_OTLP"


def emitting() -> bool:
    return os.environ.get(ENABLE_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def _spool() -> Path:
    return Path(os.environ.get("SYNC_OTLP_SPOOL", str(DEFAULT_SPOOL)))


@contextmanager
def span(
    *,
    method: str,
    url: str,
    server: str,
    spool: Path | None = None,
) -> Iterator[dict]:
    """Record one outbound vendor call, if emission is on.

    Yields a mutable dict the caller sets `status` on. The timing is measured around the block
    rather than passed in, so a span cannot claim a duration nothing took.

    A failure inside the block still writes a span -- a call that raised is a call that happened,
    and dropping it would make the observed rung quietly optimistic.
    """
    record = {"status": 0}
    if not emitting():
        yield record
        return

    started = time.time_ns()
    try:
        yield record
    finally:
        finished = time.time_ns()
        target = spool or _spool()
        target.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "traceId": uuid.uuid4().hex,
            "spanId": uuid.uuid4().hex[:16],
            "name": method,
            "kind": 3,
            "startTimeUnixNano": str(started),
            "endTimeUnixNano": str(finished),
            "attributes": [
                {"key": "http.request.method", "value": {"stringValue": method}},
                {"key": "url.full", "value": {"stringValue": url}},
                {"key": "server.address", "value": {"stringValue": server}},
                {
                    "key": "http.response.status_code",
                    "value": {"intValue": str(int(record.get("status") or 0))},
                },
            ],
        }
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")


def spooled(spool: Path | None = None) -> list[dict]:
    """Every span written since the last drain."""
    target = spool or _spool()
    if not target.is_file():
        return []
    return [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def export(service: str = "sync", spool: Path | None = None) -> dict:
    """The spool as one OTLP/JSON export request, in the shape `sync ingest` reads.

    Built here rather than by the caller so the envelope matches the reader's expectations in one
    place -- `tests/fixtures/otlp/stripe_client_spans.json` is the shape, and a second hand-built
    copy of it is a fact written twice.
    """
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service}},
                        {
                            "key": "telemetry.sdk.language",
                            "value": {"stringValue": "python"},
                        },
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "sync.obs.otlp_emit", "version": "1"},
                        "spans": spooled(spool),
                    }
                ],
            }
        ]
    }


def drain(spool: Path | None = None) -> None:
    """Forget what has been exported, so a second ingest does not double-count.

    `observed_call` converges on its natural key, so a re-ingest is not corrupting -- but a spool
    that grew forever would make every export larger than the last for no gain.
    """
    target = spool or _spool()
    if target.is_file():
        target.unlink()

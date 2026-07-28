"""Folding a batch of client spans into the graph.

One library function over a decoded OTLP payload. Not a server, and not yet a CLI subcommand.

The design document says "OTLP endpoint", and an endpoint is the right eventual shape. It is not
the right first shape: a server needs a port, a process supervisor, an authentication story
telling one customer's collector from another's, and a deployment this project does not have --
none of which makes a span mean more once it lands. What makes a span mean something is the
correlation below, and that is exercised against a captured payload today.

Becoming the endpoint later is a wrapper, not a rewrite. `POST /v1/traces` carrying OTLP/JSON is
`ingest_payload(json.loads(body), ...)`; the handler adds tenant authentication, takes `repo_id`
from the authenticated tenant rather than from an argument, and supplies the salt. Everything
below stays as it is.

Two things genuinely have to be decided before either a CLI subcommand or an endpoint exists,
and neither is decided here:

`salt` must be stable for the lifetime of a deployment and stored somewhere. It is a plain
argument today, which is right for a library function and a trap for a runnable command: the
same URL under two salts digests to two values, so a rotated salt makes repeat calls look
distinct and silently deletes the cache finding. Nothing in the schema can detect that having
happened.

Protobuf-encoded OTLP is not read. Most collectors default to it, so an endpoint that accepted
only JSON would reject the common configuration; `otlp.py` says why the protobuf decoder was
not taken on for this slice.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Protocol

from sync.core.models import ClientSpan, ObservedCall
from sync.telemetry.otlp import client_spans


class Correlator(Protocol):
    """The one thing an ingest needs from a vendor, and the only thing it may know about one.

    Structural rather than imported. `sync.core.protocols.RequestCorrelator` is the published
    form of this and an adapter satisfies both by having the method; restating it here keeps
    this module from importing anything a vendor implements.
    """

    vendor_id: str

    def operation_for_request(self, http_method: str, path: str) -> Any: ...


class Store(Protocol):
    def record_observed_call(self, call: ObservedCall) -> None: ...


@dataclass(frozen=True)
class IngestReport:
    """What one batch did.

    `uncorrelated` is the number worth watching. An ingest that correlates nothing produces a
    graph indistinguishable from a customer who does not call this vendor, and without this
    count the two look the same from every query downstream.
    """

    spans_read: int
    correlated: int
    uncorrelated: int
    rows_written: int


def ingest_payload(
    payload: dict[str, Any],
    store: Store,
    repo_id: str,
    correlator: Correlator,
    salt: str,
) -> IngestReport:
    """Fold one OTLP/JSON export request into `observed_call`.

    Spans are grouped by the row they belong to before anything is written, because the grain is
    one row per unit of work per operation: three calls in one trace are one row of three, and
    writing them one span at a time would be three round trips converging on the same row.

    A span that correlates to nothing is kept rather than dropped, under `binding_rung`
    'unresolved' and with no path at all. Dropping it would make the unresolved fraction
    invisible, and the unresolved fraction is the only measure of how good the correlation is.
    The cost of keeping no path is that history cannot be reinterpreted after the adapter
    improves -- a better correlation requires re-ingesting -- and that cost is accepted because
    the alternative is storing a URL with a customer's resource identifiers in it.
    """
    grouped: dict[tuple[str, str, str, str], list[ClientSpan]] = defaultdict(list)
    templates: dict[tuple[str, str, str, str], str] = {}
    correlated = 0

    for span in client_spans(payload):
        operation = correlator.operation_for_request(span.http_method, span.path)
        operation_id = operation.operation_id if operation is not None else ""
        correlated += operation is not None

        key = (span.trace_id, operation_id, span.server_address, span.http_method)
        grouped[key].append(span)
        templates[key] = operation.path if operation is not None else ""

    for key, spans in grouped.items():
        store.record_observed_call(
            ObservedCall.from_spans(
                repo_id=repo_id,
                vendor_id=correlator.vendor_id,
                operation_id=key[1],
                url_template=templates[key],
                spans=spans,
                salt=salt,
            )
        )

    spans_read = sum(len(spans) for spans in grouped.values())
    return IngestReport(
        spans_read=spans_read,
        correlated=correlated,
        uncorrelated=spans_read - correlated,
        rows_written=len(grouped),
    )

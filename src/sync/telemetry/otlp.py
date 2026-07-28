"""Reading OTLP/JSON export payloads into client HTTP spans.

Hand-written rather than taken from `opentelemetry-proto`. That package exists to give you
generated protobuf message classes, which costs a `protobuf` runtime -- a pinned C extension
that is the single most common source of unresolvable version conflicts in a Python dependency
tree -- to decode a wire format we are not reading. What arrives here is OTLP/**JSON**, whose
encoding is fixed by protobuf's canonical JSON mapping and by the OTLP specification, and the
part of it Sync reads is five attributes on one message type. A generated decoder would not
make that traversal more correct, and `sync.core` is the plugin SDK: a dependency added here to
save forty lines is a dependency every third-party adapter author inherits.

The two places that mapping surprises people are both covered below. A 64-bit field is written
as a JSON *string*, so `intValue` is `"200"` and never `200`. An enum is written as its name or
its number depending on which exporter produced the payload, so `kind` is `3` or
`"SPAN_KIND_CLIENT"` and a reader that handles one silently discards most of a real batch.

Attribute names follow OpenTelemetry semantic conventions for HTTP client spans, stable since
1.23.0. The pre-1.23 spellings (`http.method`, `http.url`, `net.peer.name`) are deliberately not
accepted: an exporter old enough to emit them also predates `http.request.resend_count`, so a
payload written that way could not answer the retry question anyway, and quietly half-reading it
would produce a baseline that looks complete and is not.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from sync.core.models import ClientSpan

METHOD = "http.request.method"
URL_FULL = "url.full"
SERVER_ADDRESS = "server.address"
STATUS_CODE = "http.response.status_code"
RESEND_COUNT = "http.request.resend_count"

# SpanKind.SPAN_KIND_CLIENT. Both spellings the JSON mapping permits.
_CLIENT_KINDS = frozenset({3, "3", "SPAN_KIND_CLIENT"})

_NANOS_PER_SECOND = 1_000_000_000


def _scalar(value: Any) -> Any:
    """The one value out of an OTLP AnyValue, or None for the shapes Sync does not read.

    Arrays and key-value lists are legal attribute values and no attribute read here is ever
    one, so they resolve to None and their attribute is treated as absent rather than as a
    parse failure.
    """
    if not isinstance(value, dict):
        return None
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return value[key]
    return None


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    attributes: dict[str, Any] = {}
    for entry in span.get("attributes") or []:
        if isinstance(entry, dict) and isinstance(entry.get("key"), str):
            attributes[entry["key"]] = _scalar(entry.get("value"))
    return attributes


def _as_int(value: Any) -> int | None:
    """A 64-bit OTLP field as an integer.

    The canonical mapping says string; some exporters write a JSON number anyway, and both are
    accepted because rejecting the number form would drop real payloads over a spelling. A
    string that is not a number is a malformed attribute and reads as absent -- inventing a
    status code is worse than not having one.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _started_at(span: dict[str, Any]) -> datetime | None:
    nanos = _as_int(span.get("startTimeUnixNano"))
    if nanos is None:
        return None
    return datetime.fromtimestamp(nanos / _NANOS_PER_SECOND, tz=timezone.utc)


def client_spans(payload: dict[str, Any]) -> Iterator[ClientSpan]:
    """Every outbound HTTP call in one OTLP/JSON export request.

    Client spans only. A server span describes somebody calling the customer, carries the same
    HTTP attributes, and is separated from a client span by `kind` and by nothing else. Reading
    both would attribute the customer's own inbound traffic to a vendor's bill, and would build
    the request-monitoring product that already exists rather than the one this is.

    A payload that is not OTLP, or a span missing a method, a URL or a start time, yields
    nothing rather than raising. This is a boundary -- the sender is a customer's collector --
    and one malformed span is not a reason to discard the batch around it. There is no partial
    row to write: without a method and a URL there is no request to correlate.
    """
    for resource_spans in payload.get("resourceSpans") or []:
        if not isinstance(resource_spans, dict):
            continue
        for scope_spans in resource_spans.get("scopeSpans") or []:
            if not isinstance(scope_spans, dict):
                continue
            for span in scope_spans.get("spans") or []:
                parsed = _client_span(span)
                if parsed is not None:
                    yield parsed


def _client_span(span: Any) -> ClientSpan | None:
    if not isinstance(span, dict) or span.get("kind") not in _CLIENT_KINDS:
        return None

    trace_id, span_id = span.get("traceId"), span.get("spanId")
    if not isinstance(trace_id, str) or not isinstance(span_id, str) or not trace_id or not span_id:
        return None

    attributes = _attributes(span)
    method, url = attributes.get(METHOD), attributes.get(URL_FULL)
    if not isinstance(method, str) or not isinstance(url, str) or not method or not url:
        return None

    started_at = _started_at(span)
    if started_at is None:
        return None

    # `server.address` is a convenience the instrumentation may omit; the URL always carries the
    # host, so falling back to it recovers a real value rather than substituting a placeholder.
    server_address = attributes.get(SERVER_ADDRESS)
    if not isinstance(server_address, str) or not server_address:
        server_address = urlsplit(url).hostname or ""

    return ClientSpan(
        trace_id=trace_id,
        span_id=span_id,
        http_method=method.upper(),
        url=url,
        server_address=server_address,
        status_code=_as_int(attributes.get(STATUS_CODE)),
        # Absence states a value here rather than hiding one: the convention omits the attribute
        # on a first attempt instead of writing zero.
        resend_count=_as_int(attributes.get(RESEND_COUNT)) or 0,
        started_at=started_at,
    )

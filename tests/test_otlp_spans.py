"""Reading OTLP/JSON into the only spans this product cares about.

The direction is the whole thesis. A *client* span is the customer's application calling a
vendor; a *server* span is somebody calling the customer. Every APM vendor already sells the
second one. Sync is built on the first, and a parser that quietly accepted both would build the
product everyone else has while looking like it worked.

The fixture is a captured export payload, kept verbatim rather than constructed, because the
encoding traps this module exists to survive are all in how OTLP/JSON really writes things --
64-bit fields as strings, enums as either a number or their name -- and a fixture written from
the parser's assumptions would exercise none of them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.telemetry.otlp import client_spans

FIXTURE = Path(__file__).parent / "fixtures" / "otlp" / "stripe_client_spans.json"


@pytest.fixture()
def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def spans(payload) -> list:
    return list(client_spans(payload))


# --- the direction filter ---------------------------------------------------------


def test_a_server_span_is_not_a_vendor_call(spans):
    """`POST https://shop.example.com/checkout` is the customer's own inbound request. It
    carries every attribute a client span carries, so nothing but `kind` separates them, and
    reading it as a vendor call would attribute the customer's own traffic to a vendor bill.
    """
    assert not any(span.server_address == "shop.example.com" for span in spans)


def test_the_span_kind_enum_is_accepted_in_both_encodings(spans):
    """Protobuf's JSON mapping permits an enum as its number or its name, and exporters differ:
    the Collector writes `SPAN_KIND_CLIENT`, several language SDKs write `3`. A parser that
    understood one of them would silently drop most of a real payload, and the drop looks like
    low traffic rather than like a bug.
    """
    ids = {span.span_id for span in spans}

    assert "eee19b7ec3c1b174" in ids, "numeric kind 3 was dropped"
    assert "eee19b7ec3c1b175" in ids, "named kind SPAN_KIND_CLIENT was dropped"


def test_a_client_span_that_is_not_an_http_call_is_skipped(spans):
    """The Postgres span is `kind: 3` and has `server.address`. Client-ness alone does not make
    a span a vendor API call -- without a method and a URL there is no request to correlate, so
    it is not a partial row, it is not a row.
    """
    assert not any(span.server_address == "db.internal" for span in spans)


def test_only_the_vendor_calls_survive(spans):
    """Seven spans in the fixture, four of them from one trace."""
    assert len(spans) == 7
    assert {span.server_address for span in spans} == {"api.stripe.com"}


# --- the attribute encodings ------------------------------------------------------


def test_an_int_attribute_arrives_as_a_string_and_is_read_as_a_number(spans):
    """OTLP/JSON writes every 64-bit field as a JSON string -- `"intValue": "200"`, not `200`.
    Comparing that to an integer status threshold is false for every span, so a detector looking
    for errors would find none and report a clean integration.
    """
    by_id = {span.span_id: span for span in spans}

    assert by_id["eee19b7ec3c1b174"].status_code == 200
    assert by_id["aa10b7ec3c1b1801"].status_code == 402


def test_the_resend_count_is_read(spans):
    """`http.request.resend_count` is the retry-storm signal, and it is the one efficiency
    finding a single span can carry on its own."""
    by_id = {span.span_id: span for span in spans}

    assert by_id["eee19b7ec3c1b176"].resend_count == 3


def test_an_absent_resend_count_is_zero_rather_than_unknown(spans):
    """The semantic convention omits the attribute on a first attempt rather than writing zero,
    so absence states a value here instead of hiding one. This is the only attribute where a
    default is a reading rather than a guess.
    """
    by_id = {span.span_id: span for span in spans}

    assert by_id["eee19b7ec3c1b174"].resend_count == 0


def test_an_absent_status_code_stays_unknown(spans):
    """A request that never got a response is a real outcome -- a timeout, a connection reset --
    and it is not a success. Defaulting it to 200 would hide the failures an efficiency detector
    most wants; defaulting it to 0 would invent a status the vendor never sent.
    """
    by_id = {span.span_id: span for span in spans}

    assert by_id["aa10b7ec3c1b1802"].status_code is None


def test_the_span_carries_the_identity_that_makes_ingest_idempotent(spans):
    """`(trace_id, span_id)` is unique by specification, and it is the only handle that survives
    at-least-once delivery. Everything the store does to converge rests on it."""
    identities = {(span.trace_id, span.span_id) for span in spans}

    assert len(identities) == len(spans)
    assert all(span.trace_id and span.span_id for span in spans)


def test_the_trace_groups_the_calls_one_unit_of_work_made(spans):
    """Four of the seven spans share a trace. That grouping is what separates "one request called
    the vendor four times" from "four requests called it once", which is the difference between
    a loop and ordinary traffic, and it is the reason the trace is in the table's grain.
    """
    per_trace: dict[str, int] = {}
    for span in spans:
        per_trace[span.trace_id] = per_trace.get(span.trace_id, 0) + 1

    assert sorted(per_trace.values()) == [3, 4]


def test_the_start_time_is_read_as_an_instant(spans):
    """`startTimeUnixNano` is nanoseconds since the epoch, written as a string. It is what dates
    the observation window, and a window that cannot be dated cannot be compared to a later one.
    """
    by_id = {span.span_id: span for span in spans}
    started = by_id["eee19b7ec3c1b174"].started_at

    assert started.year == 2026
    assert started.tzinfo is not None, "a naive timestamp compares wrongly against a TIMESTAMPTZ"


# --- what the parser refuses ------------------------------------------------------


def test_a_payload_that_is_not_otlp_yields_nothing_rather_than_raising():
    """Telemetry arrives from a customer's collector, which is a boundary, and a batch that is
    malformed at the envelope is not worth failing an ingest run over. It is worth yielding
    nothing, so the caller records that it folded no spans.
    """
    assert list(client_spans({"not": "otlp"})) == []


def test_a_span_without_a_url_is_skipped_rather_than_defaulted():
    """There is no safe default for the URL: an empty one correlates to whichever operation
    happens to sit on the empty path, which is a fabricated binding."""
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "a" * 32,
                                "spanId": "b" * 16,
                                "kind": 3,
                                "startTimeUnixNano": "1785283200000000000",
                                "attributes": [
                                    {"key": "http.request.method", "value": {"stringValue": "GET"}}
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }

    assert list(client_spans(payload)) == []

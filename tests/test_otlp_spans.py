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


# --- what the decoder rejects, and what it accepts that looks wrong ----------------
#
# Everything below this line was uncovered at the coverage re-measurement recorded in
# `docs/superpowers/specs/2026-07-29-sync-coverage-baseline-2.md`: twelve statements, every one
# of them a rejection or a fallback in a decoder over telemetry a customer's collector sends.
# The accepting paths above were exercised; nothing proved the module rejects what its docstring
# says it rejects, and a decoder that quietly accepts a malformed span writes a fabricated
# binding into the graph rather than failing.
#
# These are characterization tests over behaviour that already exists, so none of them was ever
# red on its own. Each was proven non-vacuous by mutation instead -- the guard removed, the test
# watched to fail, the guard restored -- and the mutations are listed in that document.


def _span(**over) -> dict:
    """One client span, with the fields every accepted span needs and nothing else.

    Written out rather than taken from the fixture because each test below removes or corrupts
    exactly one of them, and a fixture-derived span would carry whatever else the capture held.
    """
    span = {
        "traceId": "a" * 32,
        "spanId": "b" * 16,
        "kind": 3,
        "startTimeUnixNano": "1785283200000000000",
        "attributes": [
            {"key": "http.request.method", "value": {"stringValue": "GET"}},
            {"key": "url.full", "value": {"stringValue": "https://api.stripe.com/v1/charges"}},
        ],
    }
    span.update(over)
    return span


def _payload(*spans: dict, resource_spans=None) -> dict:
    if resource_spans is not None:
        return {"resourceSpans": resource_spans}
    return {"resourceSpans": [{"scopeSpans": [{"spans": list(spans)}]}]}


def test_a_status_code_written_as_a_json_number_is_read(spans):
    """The canonical mapping says a 64-bit field is a string, and the fixture above proves the
    string form is read. Some exporters write a JSON number anyway, and the module's docstring
    says both are accepted -- but the number branch had never run, so "accepted" was a claim
    about code nobody had executed. Rejecting it would drop real payloads over a spelling.
    """
    payload = _payload(_span(attributes=[
        {"key": "http.request.method", "value": {"stringValue": "GET"}},
        {"key": "url.full", "value": {"stringValue": "https://api.stripe.com/v1/charges"}},
        {"key": "http.response.status_code", "value": {"intValue": 200}},
    ]))

    assert [span.status_code for span in client_spans(payload)] == [200]


def test_a_status_code_that_is_not_a_number_reads_as_absent_rather_than_as_a_value():
    """`intValue: "not-a-number"` is a malformed attribute. Inventing a status code from it
    would put a fabricated rate into the status-rate detector, which decides whether a vendor is
    failing; absent is the only honest reading."""
    payload = _payload(_span(attributes=[
        {"key": "http.request.method", "value": {"stringValue": "GET"}},
        {"key": "url.full", "value": {"stringValue": "https://api.stripe.com/v1/charges"}},
        {"key": "http.response.status_code", "value": {"intValue": "not-a-number"}},
    ]))

    assert [span.status_code for span in client_spans(payload)] == [None]


def test_an_attribute_whose_value_is_not_an_any_value_is_treated_as_absent():
    """OTLP writes every attribute value as an AnyValue object. A bare scalar is a payload no
    conforming exporter produces, which is exactly why a boundary has to survive it -- and
    reading `"GET"` where `{"stringValue": "GET"}` belongs would accept a shape the format does
    not define."""
    payload = _payload(_span(attributes=[
        {"key": "http.request.method", "value": "GET"},
        {"key": "url.full", "value": {"stringValue": "https://api.stripe.com/v1/charges"}},
    ]))

    assert list(client_spans(payload)) == []


def test_an_array_valued_attribute_is_treated_as_absent_rather_than_flattened():
    """`arrayValue` and `kvlistValue` are legal AnyValue shapes and no attribute this module
    reads is ever one. Flattening a list into a URL would build a binding out of a value the
    customer never sent."""
    payload = _payload(_span(attributes=[
        {"key": "http.request.method", "value": {"stringValue": "GET"}},
        {"key": "url.full", "value": {"arrayValue": {"values": [{"stringValue": "https://a"}]}}},
    ]))

    assert list(client_spans(payload)) == []


def test_a_span_with_no_start_time_is_skipped():
    """`started_at` is what correlates a span to a run and what orders retries within a trace.
    Substituting now() would date a customer's call to whenever Sync happened to ingest it."""
    payload = _payload(_span(startTimeUnixNano=None))

    assert list(client_spans(payload)) == []


def test_a_start_time_that_is_not_a_number_is_skipped_rather_than_defaulted():
    payload = _payload(_span(startTimeUnixNano="the beginning of time"))

    assert list(client_spans(payload)) == []


def test_a_span_with_no_identity_is_skipped():
    """`trace_id` and `span_id` are the pair ingest is idempotent on. A span missing either
    would be re-folded on every replay of the same batch, inflating every count computed from
    the table."""
    assert list(client_spans(_payload(_span(spanId="")))) == []
    assert list(client_spans(_payload(_span(traceId=None)))) == []


def test_a_resource_entry_that_is_not_an_object_does_not_discard_the_batch_around_it():
    """One malformed entry is not a reason to drop the spans beside it: a collector batches many
    resources into one request, and a decoder that raised or returned early would lose a whole
    customer's window over one bad neighbour."""
    payload = _payload(resource_spans=[
        "not an object",
        {"scopeSpans": [{"spans": [_span()]}]},
    ])

    assert [span.span_id for span in client_spans(payload)] == ["b" * 16]


def test_a_scope_entry_that_is_not_an_object_does_not_discard_the_spans_beside_it():
    payload = {"resourceSpans": [{"scopeSpans": ["not an object", {"spans": [_span()]}]}]}

    assert [span.span_id for span in client_spans(payload)] == ["b" * 16]


def test_an_absent_server_address_falls_back_to_the_host_in_the_url():
    """`server.address` is a convenience the instrumentation may omit, and the URL always
    carries the host. Recovering it keeps the span correlatable to a vendor; leaving it empty
    would drop the call from every per-vendor rate."""
    payload = _payload(_span())

    assert [span.server_address for span in client_spans(payload)] == ["api.stripe.com"]


def test_a_status_code_written_as_a_floating_point_value_reads_as_absent():
    """`doubleValue` is a legal AnyValue and a nonsensical spelling for an integer field. The
    two accepted spellings are the string the mapping specifies and the number some exporters
    write; truncating a double would accept a third that no exporter produces and no
    specification defines, and 200.7 is not a status code."""
    payload = _payload(_span(attributes=[
        {"key": "http.request.method", "value": {"stringValue": "GET"}},
        {"key": "url.full", "value": {"stringValue": "https://api.stripe.com/v1/charges"}},
        {"key": "http.response.status_code", "value": {"doubleValue": 200.0}},
    ]))

    assert [span.status_code for span in client_spans(payload)] == [None]

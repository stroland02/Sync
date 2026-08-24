"""The table runtime telemetry lands in, and the grain that decides what a query can ask.

The grain is one row per (repo, vendor, operation, host, method, **trace**) -- one unit of
work's use of one operation. Two properties follow from that and both are tested here rather
than commented, because both are the kind of wrong that stays quiet:

A row is not a call. Three calls to one operation inside one request are one row whose
`call_count` is three, so a query counting calls by counting rows undercounts exactly where the
efficiency detector is looking. The counters are derived from the span map rather than stored,
which is what makes them impossible to drift.

Re-ingesting converges. Telemetry is at-least-once by design: a collector that does not get an
acknowledgement re-sends, and it re-sends whatever it still has buffered rather than the batch
it sent before. The span map is keyed by span id, so a span folded twice is folded once.
"""

from __future__ import annotations

from conftest import symbol_resolver

import json
import os
from pathlib import Path

import pytest

from sync.core.models import ObservedCall
from sync.graph.store import GraphStore
from sync.signals.stripe.symbols import build_symbol_map
from sync.telemetry import ingest_payload
from sync.telemetry.otlp import client_spans

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURES = Path(__file__).parent / "fixtures"
PAYLOAD = json.loads((FIXTURES / "otlp" / "stripe_client_spans.json").read_text(encoding="utf-8"))
SPEC = json.loads((FIXTURES / "specs" / "stripe_v2330_shape.json").read_text(encoding="utf-8"))

REPO = "acme/checkout"
SALT = "deployment-salt"

RETRIEVE_TRACE = "5b8efff798038103d269b633813fc60c"
CREATE_TRACE = "9c1e4f2a7b30d8156ea24c9f01b7de33"


@pytest.fixture()
def store() -> GraphStore:
    s = GraphStore(DSN)
    s.apply_schema()
    s.truncate_all()
    return s


@pytest.fixture()
def correlator(tmp_path: Path) -> object:
    map_path = tmp_path / "symbols.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    return symbol_resolver(map_path)


def _ingest(store, correlator, payload=None):
    return ingest_payload(
        payload if payload is not None else PAYLOAD,
        store=store,
        repo_id=REPO,
        correlator=correlator,
        salt=SALT,
    )


def _row(store, operation_id, trace_id):
    for row in store.observed_calls(REPO):
        if row.operation_id == operation_id and row.trace_id == trace_id:
            return row
    raise AssertionError(f"no row for {operation_id} in {trace_id}")


# --- the reduction, which is what replaces the URL ---------------------------------


def test_the_row_holds_the_published_template_and_not_the_request_path():
    """`/v1/charges/{charge}` is a string Stripe publishes. `/v1/charges/ch_3MtwBw...` contains
    a charge id, which is a customer's data and the thing a URL is most likely to leak."""
    call = ObservedCall.from_spans(
        repo_id=REPO, vendor_id="stripe", operation_id="GetChargesCharge",
        url_template="/v1/charges/{charge}",
        spans=[s for s in client_spans(PAYLOAD) if s.trace_id == RETRIEVE_TRACE][:1],
        salt=SALT,
    )

    assert call.url_template == "/v1/charges/{charge}"
    assert "ch_3MtwBwLkdIwHu7ix28a3tqPa" not in call.model_dump_json()


def test_the_target_digest_is_salted():
    """The URL space is enumerable -- an unsalted digest of `/v1/charges` is `/v1/charges` to
    anyone willing to hash a wordlist, and a table of those is a record of which vendor
    resources a customer touches."""
    spans = [s for s in client_spans(PAYLOAD) if s.trace_id == RETRIEVE_TRACE][:1]

    one = ObservedCall.from_spans(
        repo_id=REPO, vendor_id="stripe", operation_id="GetChargesCharge",
        url_template="/v1/charges/{charge}", spans=spans, salt="salt-one",
    )
    other = ObservedCall.from_spans(
        repo_id=REPO, vendor_id="stripe", operation_id="GetChargesCharge",
        url_template="/v1/charges/{charge}", spans=spans, salt="salt-two",
    )

    assert one.spans != other.spans, "the same URL digests identically under two salts"


def test_the_query_string_is_part_of_the_call_identity():
    """`?limit=10` and `?limit=100` are different calls against the same operation, and the
    difference is the entire page-size finding. Hashing the path alone would merge them."""
    spans = list(client_spans(PAYLOAD))
    listing = next(s for s in spans if s.url.endswith("?limit=10"))
    retrieve = next(s for s in spans if s.span_id == "eee19b7ec3c1b174")

    call = ObservedCall.from_spans(
        repo_id=REPO, vendor_id="stripe", operation_id="GetCharges",
        url_template="/v1/charges", spans=[listing, retrieve], salt=SALT,
    )

    assert call.distinct_targets == 2


# --- the grain --------------------------------------------------------------------


def test_one_row_is_not_one_span(store, correlator):
    """Three spans retrieving the same charge inside one request are one row. This is the whole
    reason the grain is declared: a query that counted calls by counting rows would see one
    where the customer paid for three."""
    _ingest(store, correlator)

    row = _row(store, "GetChargesCharge", RETRIEVE_TRACE)
    assert row.call_count == 3


def test_the_trace_separates_a_loop_from_ordinary_traffic(store, correlator):
    """The load-bearing assertion for the grain. `GetCharges` is called once in each of two
    traces, and that has to read as two rows of one call -- not as one row of two, which is what
    the same total looks like when one request makes both.

    Two requests each calling once is ordinary traffic. One request calling twice is a loop.
    They are the same call volume, and the trace is the only thing that tells them apart.
    """
    _ingest(store, correlator)

    rows = [r for r in store.observed_calls(REPO) if r.operation_id == "GetCharges"]

    assert sorted(r.trace_id for r in rows) == sorted([CREATE_TRACE, RETRIEVE_TRACE])
    assert [r.call_count for r in rows] == [1, 1]


def test_two_operations_in_one_trace_are_two_rows(store, correlator):
    """Retrieving a charge and listing charges are different operations and different costs."""
    _ingest(store, correlator)

    traced = [r for r in store.observed_calls(REPO) if r.trace_id == RETRIEVE_TRACE]
    assert sorted(r.operation_id for r in traced) == ["GetCharges", "GetChargesCharge"]


def test_the_repeated_identical_call_is_visible_without_storing_the_url(store, correlator):
    """The cache finding: three calls, one distinct target. `distinct_targets` is the
    cardinality of the salted digests, so the row can say "the same thing three times" while
    holding nothing that says what the thing was.
    """
    _ingest(store, correlator)

    row = _row(store, "GetChargesCharge", RETRIEVE_TRACE)
    assert row.call_count == 3
    assert row.distinct_targets == 1
    assert row.repeated_calls == 2


def test_a_retry_storm_survives_into_the_row(store, correlator):
    """`http.request.resend_count` is per span, and the row keeps the worst one. A sum would be
    meaningless across spans that each already count their own retries."""
    _ingest(store, correlator)

    assert _row(store, "GetChargesCharge", RETRIEVE_TRACE).max_resend_count == 3


def test_an_error_response_is_counted(store, correlator):
    """A 402 on a charge is a failed call the customer still paid for in latency."""
    _ingest(store, correlator)

    assert _row(store, "PostCharges", CREATE_TRACE).error_count == 1


# --- idempotence ------------------------------------------------------------------


def test_re_ingesting_the_same_payload_changes_nothing(store, correlator):
    """At-least-once is the delivery contract, not an edge case. A counter that added on every
    redelivery would inflate every call count, and an inflated count is a finding against code
    that is not actually being called that often -- a false positive nothing looks wrong about.
    """
    _ingest(store, correlator)
    before = {(r.operation_id, r.trace_id): r.call_count for r in store.observed_calls(REPO)}

    _ingest(store, correlator)
    after = {(r.operation_id, r.trace_id): r.call_count for r in store.observed_calls(REPO)}

    assert before == after
    assert len(store.observed_calls(REPO)) == len(before)


def test_a_partial_redelivery_of_overlapping_spans_converges(store, correlator):
    """The realistic redelivery: a collector re-sends what is still in its buffer, which is a
    *subset* of a previous batch repacked with newer spans. A dedup keyed on the batch would
    miss this entirely and double-count the overlap. Keying on the span id is what makes the
    overlap free.
    """
    everything = list(client_spans(PAYLOAD))
    first = _payload_of(everything[:4])
    overlapping = _payload_of(everything[2:])

    _ingest(store, correlator, first)
    _ingest(store, correlator, overlapping)
    once = {(r.operation_id, r.trace_id): r.call_count for r in store.observed_calls(REPO)}

    store.truncate_all()
    _ingest(store, correlator, _payload_of(everything))

    assert once == {(r.operation_id, r.trace_id): r.call_count for r in store.observed_calls(REPO)}


def test_the_first_sighting_is_held_and_the_last_advances(store, correlator):
    """Batches arriving in order. `first_seen` has to stay put while `last_seen` moves, which is
    what makes the window a window rather than a pair of timestamps from the newest batch.

    The mirror of the test below, and both are needed: taking the last write for both ends
    passes whichever of the two orders happens to end on the value being asserted, so a single
    test here cannot fail against a store that simply overwrites.
    """
    retrieves = _retrieve_spans()
    earliest = min(retrieves, key=lambda s: s.started_at)
    latest = max(retrieves, key=lambda s: s.started_at)

    _ingest(store, correlator, _payload_of([earliest]))
    _ingest(store, correlator, _payload_of([latest]))

    row = _row(store, "GetChargesCharge", RETRIEVE_TRACE)
    assert row.first_seen == earliest.started_at
    assert row.last_seen == latest.started_at


def test_a_rotated_salt_silently_breaks_the_repeat_signal(store, correlator):
    """Asserting the hazard rather than a guarantee, because there is no guarantee to assert:
    nothing in the schema can tell that a salt changed between two batches.

    The same URL under two salts digests to two values, so calls that repeated look distinct and
    the cache finding disappears with nothing looking wrong. The constraint -- one stable salt
    per deployment, stored -- has to be met by whatever eventually calls this, and this test is
    where a future CLI or endpoint author finds out before shipping it.
    """
    retrieves = _retrieve_spans()

    _ingest(store, correlator, _payload_of(retrieves[:1]))
    ingest_payload(
        _payload_of(retrieves[1:]), store=store, repo_id=REPO,
        correlator=correlator, salt="a-different-salt",
    )

    row = _row(store, "GetChargesCharge", RETRIEVE_TRACE)
    assert row.call_count == 3
    assert row.distinct_targets == 2, "one stable salt would have made these one target"


def test_the_window_widens_at_both_ends_rather_than_taking_the_last_write(store, correlator):
    """Batches do not arrive in order -- a collector's buffered backlog is flushed after the
    live stream resumes. Taking the last write for `first_seen` would move the start of the
    window forward every time an old batch landed."""
    retrieves = _retrieve_spans()
    latest = max(retrieves, key=lambda s: s.started_at)
    earliest = min(retrieves, key=lambda s: s.started_at)

    _ingest(store, correlator, _payload_of([latest]))
    _ingest(store, correlator, _payload_of([earliest]))

    row = _row(store, "GetChargesCharge", RETRIEVE_TRACE)
    assert row.first_seen == earliest.started_at
    assert row.last_seen == latest.started_at


# --- lineage ----------------------------------------------------------------------


def test_a_span_derived_binding_says_it_came_from_observation(store, correlator):
    """`static`, `resolved`, `observed`. A binding produced by watching traffic is a different
    kind of evidence from one read out of source, and a false positive that cannot be attributed
    to a rung cannot be fixed."""
    _ingest(store, correlator)

    assert _row(store, "GetChargesCharge", RETRIEVE_TRACE).binding_rung == "observed"


def test_a_span_that_correlates_to_nothing_is_kept_and_says_so(store, correlator):
    """`/v1/accounts/{account}/bank_accounts/{id}` derives no SDK symbol, so nothing can bind
    it. Dropping the span would make the unresolved fraction invisible, and the unresolved
    fraction is the only measure of how good the correlation is. Keeping it under a rung that
    claims a binding would be worse.
    """
    _ingest(store, correlator)

    unresolved = [r for r in store.observed_calls(REPO) if r.binding_rung == "unresolved"]
    assert len(unresolved) == 1
    assert unresolved[0].operation_id == ""
    assert unresolved[0].server_address == "api.stripe.com"


def test_the_report_states_how_much_correlated(store, correlator):
    """An ingest that silently correlated nothing looks exactly like a customer who does not
    call the vendor. The caller gets the counts rather than having to query for them."""
    report = _ingest(store, correlator)

    assert report.spans_read == 7
    assert report.correlated == 6
    assert report.uncorrelated == 1


def test_an_unresolved_row_holds_no_path_at_all(store, correlator):
    """There is no published template for a request nothing matched, and the request path is
    the customer's. So the row keeps the method, the host and a salted digest, and it cannot be
    re-derived into an operation later -- fixing the adapter requires re-ingesting rather than
    reinterpreting history. That is the cost of the threat model and it is real.
    """
    _ingest(store, correlator)

    unresolved = next(r for r in store.observed_calls(REPO) if r.binding_rung == "unresolved")
    assert unresolved.url_template == ""
    assert "acct_1032D82eZvKYlo2C" not in unresolved.model_dump_json()
    assert "ba_1032Q4" not in unresolved.model_dump_json()


def test_no_part_of_a_request_url_reaches_any_row(store, correlator):
    """Asserted against every row's serialised form after a real ingest, rather than against one
    row built by hand, so a future column cannot smuggle a URL in without failing here.

    Every identifier below is in the fixture's `url.full` attributes. `/v1/charges/{charge}` is
    in the payload's traffic too and is the one thing that survives -- the test is worthless if
    everything is dropped for lack of a rule, and the rule is that the vendor's published
    template is public and the customer's instance of it is not.
    """
    _ingest(store, correlator)

    serialised = " ".join(row.model_dump_json() for row in store.observed_calls(REPO))

    for identifier in (
        "ch_3MtwBwLkdIwHu7ix28a3tqPa", "acct_1032D82eZvKYlo2C", "ba_1032Q4",
        "api.stripe.com/v1", "limit=10", "https://",
    ):
        assert identifier not in serialised, f"{identifier} crossed the observation boundary"
    assert "/v1/charges/{charge}" in serialised, "the published template is public data and is kept"


# --- what the natural key separates -----------------------------------------------


def test_two_repositories_never_share_a_row(store, correlator):
    """Two customers' applications produce different trace ids in practice, but `repo_id` is in
    the key rather than relying on that: a collision would attribute one customer's traffic to
    another's graph, and every downstream finding would name the wrong repository."""
    _ingest(store, correlator)
    ingest_payload(PAYLOAD, store=store, repo_id="other/repo", correlator=correlator, salt=SALT)

    assert {r.repo_id for r in store.observed_calls(REPO)} == {REPO}
    assert len(store.observed_calls("other/repo")) == len(store.observed_calls(REPO))


def test_calls_are_read_back_for_one_repository_only(store, correlator):
    """Another repository is ingested first, so the emptiness below is the filter's doing rather
    than the table's. Against an empty table this passes however the query is written."""
    _ingest(store, correlator)

    assert store.observed_calls("never/indexed") == []


def _retrieve_spans() -> list:
    """One operation's spans, not the whole trace.

    The list call is later than every retrieve and belongs to a different row, so a window
    asserted across the trace would be another row's window.
    """
    return [
        s for s in client_spans(PAYLOAD)
        if s.trace_id == RETRIEVE_TRACE and s.path.startswith("/v1/charges/")
    ]


def _payload_of(spans) -> dict:
    """Re-encode parsed spans as an OTLP payload, so redelivery tests send the real shape."""
    return {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": s.trace_id,
                                "spanId": s.span_id,
                                "kind": 3,
                                "startTimeUnixNano": str(int(s.started_at.timestamp() * 1_000_000_000)),
                                "attributes": [
                                    {"key": "http.request.method", "value": {"stringValue": s.http_method}},
                                    {"key": "url.full", "value": {"stringValue": s.url}},
                                    {"key": "server.address", "value": {"stringValue": s.server_address}},
                                    *(
                                        [{"key": "http.response.status_code",
                                          "value": {"intValue": str(s.status_code)}}]
                                        if s.status_code is not None else []
                                    ),
                                    {"key": "http.request.resend_count",
                                     "value": {"intValue": str(s.resend_count)}},
                                ],
                            }
                            for s in spans
                        ]
                    }
                ]
            }
        ]
    }

"""What Sentry is actually for, which is not response shapes.

`src/sync/signals/sentry/` held one reader and it produced an `ObservedShape`. That is M2 work.
The thing M5 exists to join -- an error spike against an operation, tied to a deploy, tied to a
vendor change -- could not begin, because nothing in this repository ingested an error count at
all. This covers the first slice of that: a count per operation per window, landing in the graph,
attributable to a rung. Nothing downstream of the ingest is built here and no detector reads
these rows yet.

Driven through `cli.sentry_errors` rather than by constructing the reader, for the reason
`test_shape_ingest_command.py` gives at length: four complete components have shipped in this
repository with passing tests and no caller anywhere in `src/`, and a test that builds the object
itself proves the half that was never in doubt. The reader is constructed directly only for the
payloads a command cannot express -- a malformed issue is a fact about one record, not about a
file.

The fixture is committed and no test here reaches Sentry. It carries the values a leak would
arrive as: a Sentry issue id, a customer identifier inside an exception message, a source path
and a symbol from the customer's own codebase.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.cli import sentry_errors
from sync.graph.store import GraphStore
from sync.signals.registry import SYMBOL_MAP_FILENAME
from sync.signals.sentry import SENTRY_ISSUE_SOURCE, SentryErrorReader

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "sentry"

VENDOR = "stripe"
REPO = "acme/shop"

WINDOW_START = "2026-07-20T14:00:00+00:00"
WINDOW_END = "2026-07-20T15:00:00+00:00"

# Enough of a symbol map for the adapter to turn a recorded request back into an operation. The
# resolution is the vendor's own -- that is why the reader takes a callable instead of knowing
# anything about Stripe's URLs.
SYMBOLS = {
    "stripe.charges.create": {
        "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges",
    },
    "stripe.charges.list": {
        "operation_id": "GetCharges", "http_method": "get", "path": "/v1/charges",
    },
}

# Present in the fixture, and none of them is a count, a window or an operation. A Sentry issue
# title is an exception message and an exception message carries whatever the customer's code put
# in it; a culprit is a path and a symbol out of their repository.
FORBIDDEN_VALUES = (
    "4501234567",
    "BILLING-7K",
    "src/billing.ts",
    "createCharge",
    "ch_3NpqR2eZvKYlo2C41gK3TQzr",
    "cus_NffrFeUfNV2Hib",
    "Cannot read properties of undefined",
)


@pytest.fixture()
def store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


@pytest.fixture()
def cache(tmp_path: Path) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / SYMBOL_MAP_FILENAME).write_text(json.dumps(SYMBOLS), encoding="utf-8")
    return cache


@pytest.fixture()
def issues_file() -> Path:
    return FIXTURES / "stripe_charge_issues.json"


def _args(cache: Path, payload: Path, **over) -> argparse.Namespace:
    fields = dict(
        vendor=VENDOR, repo_id=REPO, payload=str(payload),
        since=WINDOW_START, until=WINDOW_END, dsn=DSN, cache=str(cache),
    )
    fields.update(over)
    return argparse.Namespace(**fields)


def _feed(cache: Path, payload: Path, times: int = 1, **over) -> None:
    for _ in range(times):
        assert sentry_errors(_args(cache, payload, **over)) == 0


def _rows(store: GraphStore) -> dict[tuple[str, str], tuple[int, int]]:
    """The window's rows as {(operation, status class): (errors, issues)}."""
    return {
        (row.operation_id, row.status_class): (row.error_count, row.issue_count)
        for row in store.observed_error_windows(REPO)
    }


# --- the count reaches the graph ---------------------------------------------------


def test_an_issue_export_lands_an_error_count_for_an_operation(store, cache, issues_file):
    """The whole gap in one assertion. Sentry was wired in and the only question anyone asked it
    was what a response body looked like."""
    _feed(cache, issues_file)

    assert _rows(store)[("PostCharges", "4xx")][0] == 357


def test_counts_are_pooled_per_operation_and_never_per_issue(store, cache, issues_file):
    """Two issues in the fixture are 402s on `PostCharges`, 312 and 45. One row of 357, and
    `issue_count` is what says the 357 came from two groups rather than one -- a number a reader
    cannot recover from the count, and the difference between one broken call path and a vendor
    who started refusing everything."""
    _feed(cache, issues_file)

    assert _rows(store)[("PostCharges", "4xx")] == (357, 2)


def test_status_classes_are_not_pooled_into_one_number(store, cache, issues_file):
    """`status_rate.py` makes this argument about `observed_call` and it is sharper here: a 402
    is a declined card and a 503 is the vendor being down. Summed into one error count they are a
    rate that describes neither, and the class cannot be recovered afterwards because this table
    cannot be backfilled."""
    _feed(cache, issues_file)
    rows = _rows(store)

    assert rows[("PostCharges", "4xx")] == (357, 2)
    assert rows[("PostCharges", "5xx")] == (8, 1)


def test_an_error_carrying_no_response_status_is_kept_and_says_so(store, cache, issues_file):
    """The design document's own example is a `TypeError` reading a field off a response, which
    has no status code at all. Dropping those would discard exactly the failure a removed
    response property causes; folding them into `5xx` would invent a status the vendor never
    sent. Empty is the third answer and it is the honest one."""
    _feed(cache, issues_file)

    assert _rows(store)[("PostCharges", "")] == (27, 1)


def test_a_second_operation_gets_its_own_row(store, cache, issues_file):
    """A count filed against the wrong operation is worse than no count, so the fixture reaches
    two operations through two methods on one path."""
    _feed(cache, issues_file)

    assert _rows(store)[("GetCharges", "4xx")] == (12, 1)


def test_a_count_sentry_serialises_as_a_string_is_read_as_a_number(store, cache, issues_file):
    """Sentry's issues endpoint returns `count` as a string and the fixture spells one issue's as
    an integer. A reader that took only one of the two would silently drop half a real export,
    and the surviving rows would look like a quiet week."""
    _feed(cache, issues_file)
    rows = _rows(store)

    assert rows[("PostCharges", "4xx")][0] == 357, "the string counts were read"
    assert rows[("GetCharges", "4xx")][0] == 12, "the integer count was read"


def test_an_issue_that_resolves_to_no_operation_is_not_recorded(store, cache, issues_file):
    """Most issues in a customer's Sentry project are their own bugs, and the fixture's largest
    count by far is an error against somebody else's API. Recording those as unresolved would
    make this table the customer's entire error volume, where `observed_call` can afford an
    unresolved row because an OTLP ingest is already scoped to outbound HTTP."""
    _feed(cache, issues_file)

    assert all(operation for operation, _ in _rows(store))
    assert 9001 not in {errors for errors, _ in _rows(store).values()}


def test_the_rung_names_the_binding_the_count_rests_on(store, cache, issues_file):
    """A recorded request URL matched against the vendor's own published template is the same
    binding `observed_call` produces from a span, and it fails the same way -- a template that
    matches the wrong operation files the count under a call the code never made."""
    _feed(cache, issues_file)

    assert {row.binding_rung for row in store.observed_error_windows(REPO)} == {"observed"}


def test_the_source_says_where_the_count_came_from(store, cache, issues_file):
    """In the natural key for the reason `observed_shape.source` is: a count Sentry grouped and a
    count derived from spans have different sampling stories, and merging them would let one
    masquerade as the other."""
    _feed(cache, issues_file)

    assert {row.source for row in store.observed_error_windows(REPO)} == {SENTRY_ISSUE_SOURCE}


# --- the window --------------------------------------------------------------------


def test_the_window_is_the_period_queried_not_the_extent_of_the_errors(store, cache, issues_file):
    """The bounds are a fact about the query somebody ran, and only the caller has them. Derived
    from the issues' own `firstSeen` and `lastSeen` the window would shrink to whatever happened
    to fail, so an hour with two errors and an hour with two thousand would both read as a busy
    minute and no two windows would be comparable."""
    _feed(cache, issues_file)
    row = store.observed_error_windows(REPO)[0]

    assert row.window_start == datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)
    assert row.window_end == datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc)


def test_two_windows_over_the_same_operation_are_two_rows(store, cache, issues_file):
    """A rollup that overwrote the previous window would answer "how many errors last hour" and
    never "did that rise", which is the only question this table is being built toward."""
    _feed(cache, issues_file)
    _feed(cache, issues_file, since="2026-07-20T15:00:00+00:00", until="2026-07-20T16:00:00+00:00")

    starts = {row.window_start for row in store.observed_error_windows(REPO)}
    assert len(starts) == 2


def test_a_window_that_ends_before_it_starts_is_refused(store, cache, issues_file):
    """User input at the command boundary. Reversed, the bounds still make a legal key, so the
    rows would land under a period no query could ever ask about again."""
    assert sentry_errors(_args(cache, issues_file, since=WINDOW_END, until=WINDOW_START)) == 2
    assert store.observed_error_windows(REPO) == []


# --- convergence -------------------------------------------------------------------


def test_the_same_export_ingested_twice_converges(store, cache, issues_file):
    """SIGNAL is bound by the idempotency rule and this is SIGNAL.

    Both halves matter and only one of them is a row count. `observed_shape` adds on conflict,
    because each observation is fresh evidence that a shape recurs; a count over a bounded window
    is a level rather than an increment, so the same clause here would double 357 to 714 on a
    re-run and hand the first detector that reads this table a spike that is an ingest artifact.
    """
    _feed(cache, issues_file, times=2)

    assert len(store.observed_error_windows(REPO)) == 4
    assert _rows(store)[("PostCharges", "4xx")] == (357, 2)


def test_an_export_re_queried_with_fewer_issues_replaces_the_window(store, cache, tmp_path):
    """The counterpart to convergence, and the reason the clause is a replacement rather than a
    maximum. A window re-exported after an issue was merged or deleted holds fewer errors, and a
    clause that could only ever increase would leave the graph asserting a level that Sentry no
    longer reports, with nothing able to bring it down."""
    full = json.loads((FIXTURES / "stripe_charge_issues.json").read_text(encoding="utf-8"))
    fewer = tmp_path / "fewer.json"
    fewer.write_text(json.dumps(full[1:]), encoding="utf-8")

    _feed(cache, FIXTURES / "stripe_charge_issues.json")
    _feed(cache, fewer)

    assert _rows(store)[("PostCharges", "4xx")] == (45, 1)


# --- the privacy rule --------------------------------------------------------------


def test_no_value_from_the_payload_reaches_a_row(store, cache, issues_file):
    """Asserted over the whole serialised row so a column added later cannot smuggle one in. A
    Sentry issue is richer than an error payload and worse to store: the title is an exception
    message, the culprit is a path and a symbol out of the customer's repository, and the id is a
    handle into their Sentry organisation."""
    _feed(cache, issues_file)
    rendered = json.dumps(
        [row.model_dump(mode="json") for row in store.observed_error_windows(REPO)]
    )

    for value in FORBIDDEN_VALUES:
        assert value not in rendered, f"{value} crossed the extraction boundary"


def test_the_shape_baseline_is_left_alone(store, cache, issues_file):
    """A count and a shape are different evidence from different samples. Folding an error count
    into `observed_shape` would inflate the sample floor the drift detector rests on with rows
    that describe no field."""
    _feed(cache, issues_file)

    assert store.observed_shapes(VENDOR, "PostCharges") == []
    assert store.observed_calls(REPO) == []


# --- records that are not what they claim to be ------------------------------------


def _reader(store: GraphStore) -> SentryErrorReader:
    def resolve(method: str, url: str) -> str | None:
        if method == "POST" and url.endswith("/v1/charges"):
            return "PostCharges"
        return None

    return SentryErrorReader(store, repo_id=REPO, vendor_id=VENDOR, resolve_operation=resolve)


def _issue(**over) -> dict:
    issue = {
        "id": "1",
        "count": "3",
        "latestEvent": {
            "request": {"url": "https://api.stripe.com/v1/charges", "method": "POST"},
            "contexts": {"response": {"status_code": 402}},
        },
    }
    issue.update(over)
    return issue


WINDOW = (
    datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 20, 15, 0, tzinfo=timezone.utc),
)


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param("not-a-mapping", id="scalar"),
        pytest.param({"id": "1", "count": "3"}, id="no-latest-event"),
        pytest.param(_issue(latestEvent={"request": 7}), id="request-not-a-mapping"),
        pytest.param(_issue(latestEvent={"request": {"url": 1, "method": 2}}), id="url-not-a-string"),
        pytest.param(_issue(count="many"), id="count-not-a-number"),
        pytest.param(_issue(count=-4), id="negative-count"),
        pytest.param(_issue(count=None), id="no-count"),
    ],
)
def test_a_malformed_issue_records_nothing_and_does_not_raise(store, malformed):
    """This reads data a third party produced, and one bad record must not stop the rest of an
    export. It yields no row rather than an exception."""
    assert _reader(store).ingest([malformed], *WINDOW) == 0
    assert store.observed_error_windows(REPO) == []


def test_one_malformed_issue_does_not_cost_the_rest_of_the_export(store):
    """The reason the record above is dropped rather than raised on, stated as a test: an export
    is a batch and the alternative is a single bad group silencing a whole window."""
    assert _reader(store).ingest([{"id": "1", "count": "3"}, _issue()], *WINDOW) == 1

    assert _rows(store)[("PostCharges", "4xx")] == (3, 1)


def test_a_dropped_issue_is_logged_rather_than_swallowed(store, caplog):
    """Silence on one bad record is correct; silence on all of them is a source that quietly
    stopped working, which looks identical to a week with no errors."""
    with caplog.at_level(logging.WARNING, logger="sync.signals.sentry"):
        _reader(store).ingest([_issue(count="many")], *WINDOW)

    assert caplog.records != []


def test_the_log_line_carries_no_issue_content(store, caplog):
    """A log file is a column with worse access control, and an exception message is the most
    quotable thing a Sentry issue holds."""
    with caplog.at_level(logging.WARNING, logger="sync.signals.sentry"):
        _reader(store).ingest(
            [_issue(count="many", title="TypeError on ch_3NpqR2eZvKYlo2C41gK3TQzr")], *WINDOW
        )

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert logged != "", "a dropped record has to log something for this to be worth asserting"
    assert "ch_3NpqR2eZvKYlo2C41gK3TQzr" not in logged


def test_an_export_holding_nothing_this_vendor_owns_writes_no_row(store):
    """Not a defect and not an error. A customer whose Sentry project is all their own bugs is
    the ordinary case, and a zero row would assert a window Sync observed nothing in."""
    assert _reader(store).ingest([_issue(count="500", latestEvent={
        "request": {"url": "https://api.example-crm.test/v3/contacts", "method": "POST"},
        "contexts": {"response": {"status_code": 500}},
    })], *WINDOW) == 0

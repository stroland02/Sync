"""The feeder the observed-shape baseline never had.

`ObservedDriftDetector` is the detector the drift specification calls the most valuable one Sync
has -- it fires on shape divergence alone, before the first exception -- and it has always run
against an empty baseline. `SentryShapeReader` and `DatadogShapeReader` both write
`observed_shape` and neither was ever constructed, so the detector correctly found nothing,
permanently.

Every test drives `cli.shapes`. One that constructed a reader would prove the reader works,
which was never in doubt, and re-create the exact situation this fixes. The lint cannot settle
it either: it matches bare names without resolving them, and both readers' `ingest` methods left
the baseline earlier by that coincidence.

Payloads are written here rather than fetched. No test may call a vendor API, and an error
payload is the most customer-sensitive input Sync touches -- a captured production response --
so the fixtures carry deliberately PII-shaped values and the tests assert none of them survives.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.cli import SHAPE_FORMATS, shapes
from sync.core import CallSite
from sync.detect.observed_drift import MIN_SAMPLES, DeclaredField, ObservedDriftDetector
from sync.graph.store import GraphStore
from sync.signals.registry import SYMBOL_MAP_FILENAME

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

VENDOR = "stripe"
OPERATION = "GetCharges"

# Enough of a symbol map for the adapter to turn `GET /v1/charges` into an operation. The
# resolution is the vendor's own -- that is the whole reason the readers take a callable rather
# than a URL convention.
SYMBOLS = {
    "stripe.charges.list": {
        "operation_id": OPERATION, "http_method": "get", "path": "/v1/charges",
    },
}

# A response body shaped like a real one, carrying exactly the values that must never be stored.
# `status` is the field the specification and the traffic will disagree about.
BODY = {
    "object": "list",
    "data": [
        {
            "id": "ch_3MtwBwLkdIwHu7ix28a3tqPa",
            "amount": 249900,
            "status": 402,
            "receipt_email": "ada.lovelace@example.com",
            "billing_details": {"name": "Ada Lovelace", "phone": "+44 7700 900123"},
            "client_secret": "pi_3MtwBw_secret_YrKJUKribcBjcG8HVhfZluoGH",
        }
    ],
}

# Every free-form value above, as the strings that must not appear in any stored row. Chosen to
# be the ones easiest to leak: a name, an email, a token, an amount, an identifier.
FORBIDDEN_VALUES = (
    "ada.lovelace@example.com",
    "Ada Lovelace",
    "+44 7700 900123",
    "pi_3MtwBw_secret_YrKJUKribcBjcG8HVhfZluoGH",
    "ch_3MtwBwLkdIwHu7ix28a3tqPa",
    "249900",
)

SENTRY_EVENT = {
    "event_id": "9fdc2e1a2b3c4d5e6f708192a3b4c5d6",
    "timestamp": "2026-07-20T10:15:00Z",
    "request": {"method": "GET", "url": "https://api.stripe.com/v1/charges?limit=1"},
    "contexts": {"response": {"status_code": 402, "data": BODY}},
}

DATADOG_RESPONSE = {
    "data": [
        {
            "id": "AAAAAYm5Zx",
            "attributes": {
                "timestamp": "2026-07-20T10:15:00Z",
                "attributes": {
                    "http": {
                        "method": "GET",
                        "url": "https://api.stripe.com/v1/charges?limit=1",
                        "status_code": 402,
                        "response": {"body": BODY},
                    }
                },
            },
        }
    ]
}


@pytest.fixture()
def store() -> GraphStore:
    """A store holding only this test's rows.

    Truncated rather than assumed empty: workers run against their own databases in parallel,
    and a baseline carrying another run's shapes would clear the sample floor for reasons that
    have nothing to do with what was ingested here.
    """
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


@pytest.fixture()
def cache(tmp_path) -> Path:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / SYMBOL_MAP_FILENAME).write_text(json.dumps(SYMBOLS), encoding="utf-8")
    return cache


def _args(cache: Path, payload: Path, source_format: str) -> argparse.Namespace:
    return argparse.Namespace(
        vendor=VENDOR, format=source_format, payload=str(payload),
        dsn=DSN, cache=str(cache),
    )


def _write(tmp_path: Path, name: str, payload) -> Path:
    path = tmp_path / name
    # `encoding="utf-8"` on the way in as well as the way out: a real error payload carries
    # user-supplied strings in any language, and on this machine the default is cp1252.
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _feed(tmp_path, cache, source_format: str, payload, times: int = 1) -> int:
    path = _write(tmp_path, f"{source_format}.json", payload)
    codes = [shapes(_args(cache, path, source_format)) for _ in range(times)]
    assert set(codes) == {0}
    return len(codes)


# --- both readers are reachable ----------------------------------------------------


def test_a_sentry_payload_lands_rows_in_the_shape_baseline(tmp_path, cache, store):
    """The first half of what was missing. Driven through the command, because a test that
    constructed `SentryShapeReader` would be the fourth thing in this repository to prove a
    component works while nothing reaches it.
    """
    _feed(tmp_path, cache, "sentry", SENTRY_EVENT)

    stored = store.observed_shapes(VENDOR, OPERATION)
    assert stored
    assert "/data/-/status" in {shape.field_path for shape in stored}


def test_a_datadog_payload_lands_rows_too(tmp_path, cache, store):
    """The second half, and the reason it is a separate test: a command that only ever reached
    one reader would satisfy the first one completely.
    """
    _feed(tmp_path, cache, "datadog", DATADOG_RESPONSE)

    stored = store.observed_shapes(VENDOR, OPERATION)
    assert stored
    assert {shape.source for shape in stored} == {"error-payload"}


def test_the_command_offers_exactly_the_registered_formats(tmp_path, cache, store):
    """Selection is data, and the table is what a third tracker is added to. A format the parser
    refuses is a reader registered and unreachable, which is the shape of defect this whole
    sequence has been closing.
    """
    assert set(SHAPE_FORMATS) == {"sentry", "datadog"}

    path = _write(tmp_path, "x.json", SENTRY_EVENT)
    assert shapes(_args(cache, path, "nosuchtracker")) == 2


# --- the privacy rule ---------------------------------------------------------------


def test_no_free_form_value_survives_ingestion(tmp_path, cache, store):
    """The one rule that must not bend. An error payload is a captured production response, and
    the specification is unconditional: values are never recorded, only shape.

    Asserted against the whole serialised row rather than against a column, because a leak would
    arrive in whichever column somebody added, and made non-vacuous by naming values that are
    easy to leak and present in the fixture -- a customer's name, their email, a client secret.
    """
    for source_format, payload in (("sentry", SENTRY_EVENT), ("datadog", DATADOG_RESPONSE)):
        _feed(tmp_path, cache, source_format, payload)

    rendered = json.dumps(
        [shape.model_dump(mode="json") for shape in store.observed_shapes(VENDOR, OPERATION)]
    )

    for value in FORBIDDEN_VALUES:
        assert value not in rendered, f"{value!r} reached the shape baseline"
    # And what did survive is the shape: paths and types, with nothing to identify anyone.
    assert "/data/-/billing_details/name" in rendered
    assert "string" in rendered


# --- idempotence, and what the counter means ---------------------------------------


def test_re_ingesting_converges_on_the_same_rows_and_counts_the_observation_again(
    tmp_path, cache, store
):
    """The decision, asserted rather than assumed.

    `observed_shape` converges on the same *rows*: the natural key is
    (vendor, operation, field_path, json_type, source) and a second ingest writes no new row.
    `sample_count` deliberately does not converge -- the conflict clause adds, because the
    counter is evidence that a shape recurs and two identical bodies from two different
    responses are two real observations.

    The consequence is that the store cannot tell a re-ingest from a genuine repeat, so feeding
    one export twice inflates the floor the detector depends on. That is an operator error this
    command cannot detect: de-duplicating would need a payload identity the table has no column
    for, and inventing one here would be a schema change made to paper over a usage mistake.
    """
    _feed(tmp_path, cache, "sentry", SENTRY_EVENT)
    first = {shape.field_path: shape for shape in store.observed_shapes(VENDOR, OPERATION)}

    _feed(tmp_path, cache, "sentry", SENTRY_EVENT)
    second = {shape.field_path: shape for shape in store.observed_shapes(VENDOR, OPERATION)}

    assert set(second) == set(first)
    assert all(second[path].sample_count == first[path].sample_count * 2 for path in first)


# --- the detector can finally fire --------------------------------------------------


def _seed_call_site(store: GraphStore) -> CallSite:
    """A call site for the operation, because a finding addresses one by id.

    The detector skips an operation nothing calls: it would have a divergence and nowhere to
    report it.
    """
    site = CallSite(
        repo_id="acme/billing", path="src/billing.ts", line=12, col=4, vendor_id=VENDOR,
        operation_id=OPERATION, symbol="stripe.charges.list",
        response_fields_read=["data"], sdk_version="18.0.0", content_hash="h1",
    )
    with store.transaction():
        site.id = store.upsert_call_site(site)
    return site


# What the vendor published for the field the traffic disagrees about: a string, required.
# Traffic sends `402`, an integer, which is the divergence.
DECLARED = {
    OPERATION: [
        DeclaredField(
            field_path="/data/-/status", json_types=frozenset({"string"}),
            required=True, nullable=False,
        )
    ]
}


def test_the_drift_detector_produces_a_finding_from_ingested_shapes(tmp_path, cache, store):
    """The point of the task. The detector has never produced a finding from real ingestion,
    because nothing had ever ingested.

    The floor is cleared by feeding the payload `MIN_SAMPLES` times, which is the counter doing
    exactly what the test above documents: each ingest is another observation of the same shape.
    """
    _seed_call_site(store)
    _feed(tmp_path, cache, "sentry", SENTRY_EVENT, times=MIN_SAMPLES)

    findings = list(ObservedDriftDetector(store, DECLARED, VENDOR).scan())

    diverged = [f for f in findings if "/data/-/status" in f.rationale]
    assert diverged, "the divergence the fixture was built around produced no finding"
    # The type disagreement by name, not merely "a finding mentioning the path": every other
    # field in the body is undeclared by this fixture's specification and produces a finding of
    # its own, so a looser assertion would pass on the wrong one.
    assert "arrives as number where the specification declares string" in diverged[0].rationale
    assert "src/billing.ts:12" in diverged[0].rationale


def test_below_the_sample_floor_the_detector_still_says_nothing(tmp_path, cache, store):
    """The counterweight, and it is load-bearing: the test above is satisfied by a detector with
    the floor removed. One observation of a divergence is one upstream incident, not a baseline.
    """
    _seed_call_site(store)
    _feed(tmp_path, cache, "sentry", SENTRY_EVENT, times=MIN_SAMPLES - 1)

    assert list(ObservedDriftDetector(store, DECLARED, VENDOR).scan()) == []


# --- the payload comes from outside, and nothing else does --------------------------


def test_a_payload_that_cannot_be_read_is_refused_rather_than_counted_as_empty(tmp_path, cache):
    """A file that is not there and a vendor that sent nothing are different facts. Reporting
    the first as zero rows would read as a quiet vendor, which is the false negative this whole
    signal exists to remove.
    """
    assert shapes(_args(cache, tmp_path / "absent.json", "sentry")) == 2


def test_a_vendor_with_no_symbol_map_is_refused_before_any_payload_is_read(tmp_path, store):
    """The correlator needs the map a `run` writes, and an ingest that correlates nothing
    produces a baseline indistinguishable from a customer who does not call this vendor.
    """
    empty_cache = tmp_path / "empty"
    empty_cache.mkdir()
    path = _write(tmp_path, "s.json", SENTRY_EVENT)

    assert shapes(_args(empty_cache, path, "sentry")) == 2

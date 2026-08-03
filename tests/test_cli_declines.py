"""Every statement `sync.cli` never executes, and what an operator sees when it fires.

The other decline reports on this project ask what a *caller* observes. This module is the
operator's interface, so the question is sharper and it is the one every table below carries: a
wrong answer here is not a missing finding or a wrong number, it is a person told something
false about what a command did. `docs/superpowers/reports/2026-08-03-cli-declines.md` holds the
classification; these are the assertions it rests on.

Assertions are on stdout, stderr and the exit code wherever the statement sits inside a
subcommand, because that is the whole of what an operator receives. The declared-response-field
group is the exception and is deliberate: those statements sit under `run`, whose only
operator-visible consequence is the per-detector count `_scan` prints, so the group is pinned
both ways -- on the map each guard produces, and once through `_scan` on the count an operator
actually reads.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sync.cli import (
    _declared_fields,
    _declared_response_fields,
    _detector_suite,
    _scan,
    ingest,
    shapes,
)
from sync.core import CallSite, ObservedShape, RepoRef
from sync.detect.observed_drift import MIN_SAMPLES
from sync.graph.store import GraphStore
from sync.remediate import corpus
from sync.signals.registry import SYMBOL_MAP_FILENAME

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

VENDOR = "stripe"
OPERATION = "GetCharges"
REPO = "acme/billing"


def _paths(document: dict) -> dict[str, set[str]]:
    """The declared map as `{operation_id: {field_path}}`, which is all any assertion here needs."""
    return {
        operation: {field.field_path for field in fields}
        for operation, fields in _declared_response_fields(document).items()
    }


def _operation(schema: dict, operation_id: str = OPERATION) -> dict:
    """One path item declaring one JSON response body, which is the shape every guard sits under."""
    return {
        "operationId": operation_id,
        "responses": {"200": {"content": {"application/json": {"schema": schema}}}},
    }


def _document(schema: dict, **components) -> dict:
    document: dict = {"paths": {"/v1/charges": {"get": _operation(schema)}}}
    if components:
        document["components"] = {"schemas": components}
    return document


# --- the response schema a `$ref` cannot be followed through -----------------------


def test_a_dangling_reference_at_the_response_root_drops_the_whole_operation():
    """`_resolve` answers None for a `$ref` naming a schema `components/schemas` does not hold.

    A specification assembled from several files and flattened badly is the ordinary source: the
    reference survives, the definition does not. The operation is omitted rather than recorded
    as declaring nothing, which is the same trade `_declared_response_fields` already makes for
    an operation with no JSON body -- an empty declaration reports every observed field as
    undeclared, which is the drift detector's loudest finding raised from an absence of
    information.
    """
    document = _document({"$ref": "#/components/schemas/Absent"}, Charge={"type": "object"})

    assert _declared_response_fields(document) == {}


def test_a_property_whose_reference_dangles_is_dropped_and_its_siblings_are_kept():
    """The narrower half, and the one that costs a finding rather than a whole operation.

    Scoped to the property: a response whose `card` cannot be resolved still declares `status`,
    so the operation stays in the map and only the unreachable subtree is missing from it.
    """
    document = _document(
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "card": {"$ref": "#/components/schemas/Absent"},
            },
        },
        Charge={"type": "object"},
    )

    assert _paths(document) == {OPERATION: {"/status"}}


# --- the three shapes a path item can hold that are not an operation ---------------


def test_a_path_whose_value_is_not_an_object_is_skipped_and_its_siblings_resolve():
    """A `paths` entry holding a list or a string rather than a Path Item Object.

    No vendor publishes one, and the guard is what keeps a malformed document from costing every
    operation in it rather than the one path that is wrong -- the same scoping
    `2026-07-29-hand-written-symbol-maps.md` found the Twilio map making and the Stripe map not.
    """
    document = _document({"type": "object", "properties": {"status": {"type": "string"}}})
    document["paths"]["/v1/broken"] = ["not", "a", "path", "item"]

    assert _paths(document) == {OPERATION: {"/status"}}


def test_a_path_item_key_that_is_not_an_operation_contributes_nothing():
    """`parameters`, `servers`, `summary` and `description` are legal Path Item fields.

    Twilio writes `servers` and `description` on every path of the product this repository
    commits, so this is a vendor fact rather than a defensive guard -- and without it the walk
    would read a list where it expects an operation object.
    """
    document = _document({"type": "object", "properties": {"status": {"type": "string"}}})
    document["paths"]["/v1/charges"]["servers"] = [{"url": "https://api.stripe.com"}]
    document["paths"]["/v1/charges"]["description"] = "Charges."
    document["paths"]["/v1/charges"]["parameters"] = [{"name": "limit", "in": "query"}]

    assert _paths(document) == {OPERATION: {"/status"}}


def test_an_operation_carrying_no_operation_id_declares_nothing():
    """`operation_id` is the key the graph, the detector and the symbol map all join on, so an
    operation without one has nothing a declaration could be filed under. Recording it under a
    generated name would put a declaration in the map that no observed shape can ever meet.
    """
    document = _document({"type": "object", "properties": {"status": {"type": "string"}}})
    del document["paths"]["/v1/charges"]["get"]["operationId"]

    assert _declared_response_fields(document) == {}


def test_one_operation_missing_its_id_costs_only_itself():
    """The scoping, asserted separately: the guard is a `continue` rather than a `return`, and a
    version that stopped the walk would empty the map for every later path in the document."""
    document = _document({"type": "object", "properties": {"status": {"type": "string"}}})
    del document["paths"]["/v1/charges"]["get"]["operationId"]
    document["paths"]["/v1/refunds"] = {
        "get": _operation(
            {"type": "object", "properties": {"status": {"type": "string"}}}, "GetRefunds"
        )
    }

    assert _paths(document) == {"GetRefunds": {"/status"}}


# --- the 3.1 spelling of nullable --------------------------------------------------


def test_a_field_nullable_in_the_openapi_31_spelling_is_recorded_as_nullable():
    """`nullable: true` is 3.0; 3.1 puts `null` in the type list, and both are in the wild.

    This is the one statement in the group that is capability rather than decline, and it is the
    one whose failure produces a *false* finding rather than a missing one: a nullable field read
    as non-nullable makes `_divergence` answer "arrives null where the specification requires a
    value" every time the vendor legitimately sends null.
    """
    document = _document(
        {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": ["string", "null"]}},
        }
    )

    field = _declared_response_fields(document)[OPERATION][0]

    assert field.nullable is True
    # And the type list still describes what the field can be. `null` is dropped from
    # `json_types` because nullability is carried in its own column, so a reader of either
    # column alone is told the truth.
    assert field.json_types == frozenset({"string"})


def test_the_30_spelling_still_answers_nullable():
    """The counterweight. Without it the test above passes against a `_nullable` that answers
    True for everything, which would report no null divergence for any field ever."""
    document = _document(
        {
            "type": "object",
            "required": ["status"],
            "properties": {
                "status": {"type": "string", "nullable": True},
                "amount": {"type": "integer"},
            },
        }
    )

    by_path = {f.field_path: f for f in _declared_response_fields(document)[OPERATION]}

    assert by_path["/status"].nullable is True
    assert by_path["/amount"].nullable is False


# --- what the operator reads when one of the above fires ---------------------------


@pytest.fixture()
def store() -> GraphStore:
    """A store holding only this test's rows.

    Truncated rather than assumed empty: workers run against their own databases in parallel,
    and a baseline carrying another run's shapes would clear the sample floor for reasons that
    have nothing to do with what this fixture wrote.
    """
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _seed_traffic(store: GraphStore) -> None:
    """One call site on the operation and one observed field above the sample floor.

    Written straight to the store rather than folded through `sync shapes`, because the reader
    is not what is under test here and thirty ingests of the same payload would only be
    re-proving `record_observed_shape`'s counter.
    """
    site = CallSite(
        repo_id=REPO, path="src/billing.ts", line=12, col=4, vendor_id=VENDOR,
        operation_id=OPERATION, symbol="stripe.charges.list",
        response_fields_read=["status"], sdk_version="18.0.0", content_hash="h1",
    )
    now = datetime.now(timezone.utc)
    with store.transaction():
        store.upsert_call_site(site)
        store.record_observed_shape(ObservedShape(
            vendor_id=VENDOR, operation_id=OPERATION, field_path="/settlement_state",
            json_type="string", source="error-payload", sample_count=MIN_SAMPLES,
            first_seen=now - timedelta(days=7), last_seen=now,
        ))


def _drift_line(store: GraphStore, document: dict, capsys) -> str:
    """The one line of `_scan`'s output an operator reads about the drift detector."""
    _scan(
        _detector_suite(
            store, spec_documents=[document], call_sites=[], deprecations=[],
            vendor_id=VENDOR, repo_id=REPO,
        ),
        store,
    )
    printed = [
        line for line in capsys.readouterr().out.splitlines()
        if line.startswith("observed-drift:")
    ]
    assert len(printed) == 1, printed
    return printed[0]


_HEALTHY_SCHEMA = {"type": "object", "properties": {"status": {"type": "string"}}}


def test_a_specification_the_walk_can_read_produces_a_drift_finding(store, capsys):
    """The control, and it is what makes the next test mean anything: with the operation in the
    declared map, traffic carrying a field the specification does not describe is a finding and
    the operator is told there is one."""
    _seed_traffic(store)

    assert _drift_line(store, _document(_HEALTHY_SCHEMA), capsys) == (
        "observed-drift: 1 finding(s), 0 declined"
    )


def test_an_operation_the_walk_dropped_reports_exactly_what_a_clean_repository_reports(
    store, capsys
):
    """**The finding this report exists to make.** A specification whose operation the walk
    declines never reaches the detector's `self._spec`, so no shape is queried, no divergence is
    computed, and the count printed is zero -- the same zero a vendor who changed nothing
    produces, from the same command, with the same exit code.

    `declined` does not close the gap either. The detector's own channel counts divergences it
    saw and did not report; an operation that never entered the map was never seen, so the
    channel that exists to make a silent decline countable reads zero as well.
    """
    dropped = _document(_HEALTHY_SCHEMA)
    del dropped["paths"]["/v1/charges"]["get"]["operationId"]

    line = _drift_line(store, dropped, capsys)

    assert line == "observed-drift: 0 finding(s), 0 declined"
    # Byte-identical to a scan of a vendor with nothing to report, which is the point: the two
    # are compared rather than described, so a future channel that distinguished them would
    # fail here and be noticed.
    _seed_traffic(store)
    assert _drift_line(store, {"paths": {}}, capsys) == line


def test_the_collision_drop_is_printed_where_the_walk_declines_are_not(capsys):
    """The one decline in this file's neighbourhood that an operator *can* see, kept beside the
    others because the contrast is the finding. `_declared_fields` prints to stderr when two
    documents declare one operation, so that narrowing is legible; every guard above narrows the
    same map by the same mechanism and says nothing at all.
    """
    left = _document(_HEALTHY_SCHEMA)
    right = _document({"type": "object", "properties": {"amount": {"type": "integer"}}})

    declared = _declared_fields([left, right])

    assert declared == {}
    assert OPERATION in capsys.readouterr().err


# --- the files the literal pass declines to read -----------------------------------


def test_the_literal_pass_reads_neither_an_installed_dependency_nor_a_declaration_file(tmp_path):
    """`_literal_call_sites` walks every `*.ts` in the tree and skips two kinds.

    `node_modules` is the vendor's own code. A model literal found in it is not a call the
    customer wrote, and a finding raised against it would propose a patch inside a directory
    the customer's CI reinstalls before it compiles -- an edit that cannot survive its own
    verification. `.d.ts` declares types and calls nothing.

    Asserted through the returned sites because they are the whole of what `run()` derives its
    finding count from: a walk that indexed either would inflate that count with call sites no
    patch can reach, and the operator has no other view of the difference.
    """
    from sync.cli import _literal_call_sites

    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "node_modules" / "anthropic").mkdir(parents=True)
    body = 'const r = client.messages.create({ model: "claude-3-opus-20240229" });\n'
    (root / "src" / "app.ts").write_text(body, encoding="utf-8")
    (root / "src" / "models.d.ts").write_text(body, encoding="utf-8")
    (root / "node_modules" / "anthropic" / "index.ts").write_text(body, encoding="utf-8")

    sites, unread = _literal_call_sites(
        RepoRef(repo_id=REPO, url="u", local_path=str(root), head_sha="0" * 40)
    )

    assert {site.path for site in sites} == {"src/app.ts"}
    # And a skipped file is not reported as one the run could not read. The coverage block
    # exists to say how much of the tree went unindexed, and counting a deliberate skip there
    # would make every repository with dependencies installed look partly unreadable.
    assert unread == []


# --- `sync shapes`: the vendor that cannot correlate, and the payload on stdin ------


_SHAPE_SYMBOLS = {
    "stripe.charges.list": {
        "operation_id": OPERATION, "http_method": "get", "path": "/v1/charges",
    },
}

_SENTRY_EVENT = {
    "event_id": "9fdc2e1a2b3c4d5e6f708192a3b4c5d6",
    "timestamp": "2026-07-20T10:15:00Z",
    "request": {"method": "GET", "url": "https://api.stripe.com/v1/charges?limit=1"},
    "contexts": {"response": {"status_code": 402, "data": {"object": "list", "id": "ch_1"}}},
}


@pytest.fixture()
def staged_cache(tmp_path) -> Path:
    """A cache carrying the symbol map a previous `sync run` would have written."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / SYMBOL_MAP_FILENAME).write_text(json.dumps(_SHAPE_SYMBOLS), encoding="utf-8")
    return cache


def _shape_args(cache: Path, payload: str, vendor: str = VENDOR, fmt: str = "sentry"):
    return argparse.Namespace(
        vendor=vendor, format=fmt, payload=payload, dsn=DSN, cache=str(cache)
    )


def test_shapes_refuses_a_vendor_whose_adapter_cannot_correlate_a_request(
    staged_cache, tmp_path, capsys
):
    """Four vendors this deployment offers are served by `GeneratedSpecAdapter`, which
    implements no `operation_for_request`. `sync shapes --vendor anthropic` is therefore an
    ordinary invocation reaching an adapter with no correlation story, and it has to say so.

    The alternative is an `AttributeError` from inside the fold, which reports a missing method
    where the answer is that this vendor has no way to turn an observed request back into an
    operation. `sync ingest` already refuses the same way and its refusal is exercised; this
    one, on the sibling command, never was.
    """
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(_SENTRY_EVENT), encoding="utf-8")

    assert shapes(_shape_args(staged_cache, str(payload), vendor="anthropic")) == 2

    printed = capsys.readouterr()
    assert printed.out == ""
    assert "anthropic" in printed.err
    assert "correlate" in printed.err


def test_shapes_refuses_before_it_reads_the_payload(staged_cache, tmp_path, capsys):
    """The ordering, and it is the operator-facing half: a payload is a captured production
    response, so a command that reads one and then discovers it has nowhere to fold it has held
    customer data for no reason. The refusal fires against a payload that is not there at all.
    """
    assert shapes(_shape_args(staged_cache, str(tmp_path / "absent.json"), "anthropic")) == 2

    assert "correlate" in capsys.readouterr().err


def test_shapes_reads_a_payload_from_stdin(staged_cache, store, monkeypatch, capsys):
    """`--payload -` is how an export reaches this command without landing in a file, which for
    a captured production response is the difference between a payload that exists on disk and
    one that does not. The file route is exercised throughout; the pipe never was.
    """
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_SENTRY_EVENT)))

    assert shapes(_shape_args(staged_cache, "-")) == 0

    assert "shape observation(s) recorded from sentry" in capsys.readouterr().out
    assert store.observed_shapes(VENDOR, OPERATION)


# --- `sync ingest`: the payload on stdin -------------------------------------------


def test_ingest_reads_a_payload_from_stdin(staged_cache, store, monkeypatch, capsys):
    """The same pipe on the span half. An OTLP export is large and is normally produced by
    another process, so the pipe is the ordinary invocation rather than the exotic one.
    """
    monkeypatch.delenv(corpus.SALT_VARIABLE, raising=False)
    monkeypatch.setattr(corpus, "SALT_FILE", Path(str(staged_cache)) / ".sync-corpus-salt")
    spans = (Path(__file__).parent / "fixtures" / "otlp" / "stripe_client_spans.json").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(spans))

    args = argparse.Namespace(
        vendor=VENDOR, payload="-", repo_id=REPO, dsn=DSN, cache=str(staged_cache)
    )

    assert ingest(args) == 0

    assert "span(s)" in capsys.readouterr().out
    assert store.observed_calls(REPO)

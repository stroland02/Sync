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
import hashlib
import hmac
import io
import json
import os
import secrets
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

import sync.cli as cli
from sync.cli import (
    _declared_fields,
    _declared_response_fields,
    _detector_suite,
    _scan,
    benchmark,
    feed_public_key,
    ingest,
    merge_outcome,
    run,
    shapes,
)
from sync.core import CallSite, Finding, ObservedShape, RepoRef
from sync.detect.observed_drift import MIN_SAMPLES
from sync.graph.store import GraphStore
from sync.remediate import corpus
from sync.signals.feed import load_public_key
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


# --- `sync merge-outcome`: the delivery that verifies and is not a pull request -----


def _sign(body: bytes, secret: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


@pytest.fixture()
def webhook_secret(monkeypatch) -> bytes:
    """A throwaway secret, generated here and never written beside a fixture. Committing one --
    even a fake -- teaches the pattern that a shared secret has a value this repository knows."""
    secret = secrets.token_hex(32).encode("ascii")
    monkeypatch.setenv(cli.WEBHOOK_SECRET_ENV, secret.decode("ascii"))
    return secret


def _merge_args(payload: Path, signature: str):
    return argparse.Namespace(
        payload=str(payload), signature=signature, secret_file=None, commits=None, dsn=DSN
    )


def test_a_verified_delivery_that_is_not_a_pull_request_event_is_rejected_by_name(
    tmp_path, store, webhook_secret, capsys
):
    """A webhook pointed at this command receives every event the repository is configured for,
    and only the pull request ones carry an outcome. The bytes are vouched for and still are not
    a delivery this receiver can read, which is a different fact from a forgery -- so the message
    says what was wrong with the payload where the signature failure deliberately says nothing.

    Exit 1 rather than 2. The two refusals above it -- no secret, and a payload that cannot be
    read -- exit 2 because the operator has to change the invocation; this one is a verdict about
    the delivery itself.
    """
    body = json.dumps({"action": "completed", "workflow_run": {"id": 7}}).encode("utf-8")
    payload = tmp_path / "delivery.json"
    payload.write_bytes(body)

    assert merge_outcome(_merge_args(payload, _sign(body, webhook_secret))) == 1

    printed = capsys.readouterr()
    assert printed.out == ""
    assert "delivery rejected: " in printed.err
    assert "pull_request" in printed.err


def test_a_rejected_delivery_says_more_than_a_forged_one_does(
    tmp_path, store, webhook_secret, capsys
):
    """The asymmetry is deliberate and this is what holds it. A signature failure describes
    nothing, because an "expected X, got Y" pasted into an issue is a free guess at how close a
    forgery came; a format failure describes the payload, because the operator has to fix it.
    """
    body = json.dumps({"action": "completed"}).encode("utf-8")
    payload = tmp_path / "delivery.json"
    payload.write_bytes(body)

    assert merge_outcome(_merge_args(payload, _sign(body, webhook_secret))) == 1
    rejected = capsys.readouterr().err

    assert merge_outcome(_merge_args(payload, _sign(body, b"a different secret"))) == 1
    forged = capsys.readouterr().err

    assert rejected != forged
    assert "does not verify" in forged


def test_a_malformed_delivery_and_an_uninteresting_one_are_told_apart_by_the_exit_code(
    tmp_path, store, webhook_secret, capsys
):
    """The distinction an operator scripts against. A pull request that decided nothing is the
    ordinary case and exits 0; bytes this receiver cannot read exit 1. Without the difference a
    wrapper would either retry every routine delivery or swallow every malformed one.
    """
    opened = (
        Path(__file__).parent / "fixtures" / "webhook" / "pull_request_opened.json"
    ).read_bytes()
    routine = tmp_path / "opened.json"
    routine.write_bytes(opened)

    assert merge_outcome(_merge_args(routine, _sign(opened, webhook_secret))) == 0
    assert "nothing to record" in capsys.readouterr().out


# --- `sync feed-public-key`: the subcommand nothing had ever run --------------------


@pytest.fixture()
def signing_key(monkeypatch, tmp_path):
    """A throwaway Ed25519 pair in PEM, which is what `openssl genpkey -algorithm ed25519`
    writes and therefore what an operator's key management already produces."""
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_file = tmp_path / "signing.pem"
    key_file.write_bytes(pem)
    monkeypatch.setenv(cli.FEED_SIGNING_KEY_ENV, pem.decode("ascii"))
    return private, key_file


def test_feed_public_key_prints_the_hex_sync_core_keys_holds(signing_key, capsys):
    """The command exists so somebody can derive the trust anchor from a key this repository
    must never hold, and the whole subcommand had never been run.

    Asserted by loading the printed hex back into a public key and verifying a signature the
    private half produced, rather than by comparing two strings. A command that printed a
    correctly-shaped 32-byte hex of the wrong key would pass any string comparison and would put
    a constant in `sync.core.keys` that rejects every feed as a forgery.
    """
    private, _ = signing_key

    assert feed_public_key(argparse.Namespace(key_file=None)) == 0

    printed = capsys.readouterr().out.strip()
    load_public_key(bytes.fromhex(printed)).verify(private.sign(b"payload"), b"payload")


def test_feed_public_key_reads_a_key_file_as_well_as_the_environment(
    signing_key, monkeypatch, capsys
):
    """Two sources and no third, which is the rule `_webhook_secret` established: a variable is
    how a process holds a credential without it reaching a file, a file is how an operator holds
    one without it reaching a process listing."""
    private, key_file = signing_key
    monkeypatch.delenv(cli.FEED_SIGNING_KEY_ENV)

    assert feed_public_key(argparse.Namespace(key_file=str(key_file))) == 0

    printed = capsys.readouterr().out.strip()
    assert bytes.fromhex(printed) == private.public_key().public_bytes_raw()


def test_feed_public_key_refuses_when_there_is_no_usable_key(monkeypatch, capsys):
    """Nothing is printed on stdout, which is the property that matters for a command whose
    output is meant to be pasted into a source file: a refusal that also wrote something to
    stdout would put whatever it wrote into `sync.core.keys`."""
    monkeypatch.delenv(cli.FEED_SIGNING_KEY_ENV, raising=False)

    assert feed_public_key(argparse.Namespace(key_file=None)) == 2

    printed = capsys.readouterr()
    assert printed.out == ""
    assert cli.FEED_SIGNING_KEY_ENV in printed.err


def test_feed_public_key_says_nothing_that_narrows_the_private_half(signing_key, capsys):
    """The docstring's stated reason for the command being this narrow: one that emitted the
    private half for convenience is how a key reaches a terminal scrollback. Asserted over both
    streams against the PEM, its body lines, and the raw private bytes."""
    private, _ = signing_key

    feed_public_key(argparse.Namespace(key_file=None))

    printed = capsys.readouterr()
    said = printed.out + printed.err
    raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    assert raw.hex() not in said
    assert os.environ[cli.FEED_SIGNING_KEY_ENV] not in said
    for line in os.environ[cli.FEED_SIGNING_KEY_ENV].splitlines():
        if line and "-----" not in line:
            assert line not in said


# --- `sync benchmark --score-pair`: the specification that cannot be honoured -------


def _benchmark_args(score_pair=None):
    return argparse.Namespace(
        dsn=DSN,
        score_pair=None if score_pair is None else str(score_pair),
        # Never connected to: every refusal below raises while reading the specification, which
        # happens before a store is built over this name.
        score_dsn=DSN + "_scoring_never_reached",
    )


def _corpus_spec(tmp_path: Path, spec: dict) -> Path:
    path = tmp_path / "corpus.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return path


_COMPLETE_SPEC = {
    "repo": "/nowhere",
    "vendor": "stripe",
    "cache": "/nowhere/cache",
    "from_version": "2026-05-01",
    "to_version": "2026-11-01",
    "change": {
        "kind": "request-property-removed",
        "operation": "PostCharges",
        "field": "receipt_email",
    },
}


def test_a_pair_specification_missing_a_top_level_key_is_refused_naming_the_file(
    tmp_path, store, capsys
):
    """Every field is required and a missing one raises naming the file. A corpus that quietly
    defaulted its checkout or its vendor would report a number over a pair nobody chose, and the
    number is the whole product of the command.

    The refusal happens before the vendor is loaded and before anything is indexed, so a
    specification an operator is still editing costs nothing.
    """
    spec = {key: value for key, value in _COMPLETE_SPEC.items() if key not in ("repo", "cache")}

    assert benchmark(_benchmark_args(_corpus_spec(tmp_path, spec))) == 2

    printed = capsys.readouterr()
    assert "pair specification: " in printed.err
    assert "corpus.yaml" in printed.err
    # Both, not the first one it noticed. An operator told about one missing key at a time edits
    # and re-runs once per field.
    assert "repo" in printed.err and "cache" in printed.err


def test_a_pair_specification_whose_change_is_incomplete_is_refused_the_same_way(
    tmp_path, store, capsys
):
    """The nested half, and it is a separate statement because the change block is where the
    mutation comes from: a pair whose change named no field would break nothing and report a
    flawless run over an empty positive set."""
    spec = dict(_COMPLETE_SPEC, change={"kind": "request-property-removed"})

    assert benchmark(_benchmark_args(_corpus_spec(tmp_path, spec))) == 2

    printed = capsys.readouterr()
    assert "pair specification: " in printed.err
    assert "change names no" in printed.err
    assert "operation" in printed.err and "field" in printed.err


def test_a_refused_pair_specification_prints_no_report_at_all(tmp_path, store, capsys):
    """The operator-facing half, and the one a wrapper could get wrong. `benchmark` renders the
    corpus report before it scores, so a refusal that still printed would put an unscored report
    on stdout under a non-zero exit -- a reader seeing axes and a failure has no way to know
    which half of the command produced them.
    """
    spec = {key: value for key, value in _COMPLETE_SPEC.items() if key != "vendor"}

    assert benchmark(_benchmark_args(_corpus_spec(tmp_path, spec))) == 2

    assert capsys.readouterr().out == ""


def test_the_report_still_renders_when_no_pair_is_asked_for(store, capsys):
    """The control. Without it the assertion above passes against a `benchmark` that prints
    nothing ever, which would be the same command with its only output removed."""
    assert benchmark(_benchmark_args()) == 0

    assert capsys.readouterr().out != ""


# --- `sync run`: what the two paths through the remediation loop print ---------------
#
# Both statements below sit inside `run()`, which normally reaches Postgres, the network and the
# Agent SDK. Every one of those is replaced, and the graph is a stand-in compiled against the
# same checkpointer contract -- the device `test_cli.py` already uses for `_thread_to_invoke`,
# for the reason it gives there: the question is what LangGraph does with an interrupted thread,
# and a fake `get_state` would only assert what this file believes.


class _RunState(TypedDict, total=False):
    finding: object
    repo: RepoRef
    branch: str
    outcome: str
    pr_url: str
    report_reason: str


class _LoopStore:
    """`GraphStore` for a run that reaches the remediation loop. Answers, records nothing."""

    def __init__(self, findings):
        self._findings = findings

    @contextmanager
    def transaction(self):
        yield

    def apply_schema(self):
        pass

    def truncate_all(self, keep=()):
        pass

    def replace_call_sites(self, repo_id, sites):
        return [f"cs-{index}" for index, _ in enumerate(sites)]

    def upsert_vendor_change(self, change):
        return "vc-1"

    def insert_finding(self, finding):
        return finding.call_site_id


class _LoopVendor:
    vendor_id = VENDOR

    def fetch_changes(self, from_version, to_version):
        return []


class _LoopAdapter:
    """A language adapter that claims the repository and finds nothing in it.

    `discard_contaminated_dependencies` is the whole variable: `_reset_clone` keeps ignored
    files on purpose, so a dependency tree the previous finding doctored survives into the next
    one, and this is what the adapter says about it.
    """

    contaminated = False

    def __init__(self, vendor_adapter=None):
        pass

    def matches(self, repo):
        return True

    def index(self, repo):
        return []

    def discard_contaminated_dependencies(self, repo):
        return type(self).contaminated


def _one_finding():
    return Finding(
        detector="vendor_change", claim="response-field", call_site_id="site-1",
        vendor_change_id="vc-1", severity="breaking", rationale="status removed",
    )


class _OneFindingDetector:
    def __init__(self, store, vendor_id: str = VENDOR, repo_id: str | None = None):
        self._vendor_id = vendor_id

    def scan(self):
        return [_one_finding()] if self._vendor_id == VENDOR else []


class _MemoryCheckpointer(InMemorySaver):
    def setup(self):
        pass

    @classmethod
    @contextmanager
    def from_conn_string(cls, dsn):
        yield cls()


def _remediation_graph(pushed_sha: str):
    """A stand-in for the remediation graph, carrying the two node names either side of a push.

    `await_ci` is written the way the real one behaves and that is the whole point of the
    fixture: it reads HEAD out of the clone and matches it against the commit the branch
    carries, because that is how a CI run is found. A resumed run whose clone was never moved
    onto the pushed branch polls for a commit no run exists for.
    """

    def push(state: _RunState) -> _RunState:
        return {"branch": "sync/api-drift-aaaa"}

    def await_ci(state: _RunState) -> _RunState:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=state["repo"].local_path,
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout.strip()
        if head != pushed_sha:
            return {
                "outcome": "no_ci_run",
                "report_reason": f"polled {head[:12]}, which no run was started for",
            }
        return {"outcome": "opened", "pr_url": "https://github.invalid/pull/1"}

    builder = StateGraph(_RunState)
    builder.add_node("push", push)
    builder.add_node("await_ci", await_ci)
    builder.add_edge(START, "push")
    builder.add_edge("push", "await_ci")
    builder.add_edge("await_ci", END)
    return builder.compile(checkpointer=InMemorySaver())


def _origin_with_a_pushed_branch(tmp_path: Path) -> tuple[Path, str]:
    """An origin carrying the branch a process that has since died pushed to it."""
    origin = tmp_path / "origin"
    origin.mkdir()
    identity = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
    (origin / "billing.ts").write_text("original\n", encoding="utf-8")
    for args in (
        ["add", "-A"], ["commit", "-q", "-m", "root"],
        ["checkout", "-q", "-b", "sync/api-drift-aaaa"],
    ):
        subprocess.run(["git", *identity, *args], cwd=origin, check=True)
    (origin / "billing.ts").write_text("patched\n", encoding="utf-8")
    for args in (["add", "-u"], ["commit", "-q", "-m", "fix: the finding"]):
        subprocess.run(["git", *identity, *args], cwd=origin, check=True)
    pushed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=origin,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    subprocess.run(["git", *identity, "checkout", "-q", "main"], cwd=origin, check=True)
    return origin, pushed


def _stub_the_run(monkeypatch, graph, store):
    """Everything `run()` touches outside the loop under test."""
    from sync.signals.registry import PreparedVendor

    monkeypatch.setattr(
        cli, "prepare_vendor",
        lambda vendor_id, context: PreparedVendor(adapter=_LoopVendor(), documents=()),
    )
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _OneFindingDetector)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _LoopAdapter)
    monkeypatch.setattr(cli, "http_fetch", lambda url, **kw: "")
    monkeypatch.setattr(cli, "PostgresSaver", _MemoryCheckpointer)
    monkeypatch.setattr(cli, "load_catalogue", dict)
    monkeypatch.setattr(cli, "build_graph", lambda **kwargs: graph)


def _run_args(origin: Path, tmp_path: Path, run_id: str):
    return argparse.Namespace(
        vendor=VENDOR, from_version="v2320", to_version="v2330", repo=str(origin),
        dsn="postgresql://unused", cache=str(tmp_path / "cache"), limit=1, run_id=run_id,
    )


def test_a_resumed_run_polls_the_commit_its_dead_predecessor_pushed(tmp_path, monkeypatch, capsys):
    """The two statements that put a resumed run's clone back where the checkpoint expects it.

    A run interrupted during the CI wait left its patch in a temporary directory that died with
    it; the pushed branch is the only durable part. This process clones fresh, so it sits on the
    default branch -- and `await_ci` matches CI runs against the commit HEAD names, so without
    the checkout it polls a commit no run exists for and reports that half an hour later.

    Asserted on the line the operator reads. The failure this prevents is not a missing answer
    but a wrong one: the run finishes, prints an outcome, and the outcome is about a commit
    nobody built.
    """
    origin, pushed = _origin_with_a_pushed_branch(tmp_path)
    graph = _remediation_graph(pushed)
    store = _LoopStore([_one_finding()])
    _stub_the_run(monkeypatch, graph, store)

    # What the process that died left behind: a thread interrupted after the push, carrying the
    # branch and a `repo` naming a working copy that is gone.
    thread = {"configurable": {"thread_id": "site-1:resumed:0"}}
    graph.update_state(thread, {
        "branch": "sync/api-drift-aaaa",
        "repo": RepoRef(repo_id=REPO, url=str(origin), local_path=str(tmp_path / "gone"),
                        head_sha=pushed),
    }, as_node="push")

    assert run(_run_args(origin, tmp_path, "resumed")) == 0

    assert "opened: https://github.invalid/pull/1" in capsys.readouterr().out


def test_without_the_checkout_the_resumed_run_reports_a_commit_nobody_built(
    tmp_path, monkeypatch, capsys
):
    """The counterweight, and it is what makes the test above mean something. With the clone
    left where a fresh checkout puts it, the same graph on the same thread finishes and prints a
    verdict about the wrong commit -- and an operator reading it has no way to tell that from a
    repository whose CI genuinely did not run.
    """
    origin, pushed = _origin_with_a_pushed_branch(tmp_path)
    graph = _remediation_graph(pushed)
    store = _LoopStore([_one_finding()])
    _stub_the_run(monkeypatch, graph, store)
    monkeypatch.setattr(cli, "_checkout_branch", lambda repo, branch: None)

    thread = {"configurable": {"thread_id": "site-1:unmoved:0"}}
    graph.update_state(thread, {
        "branch": "sync/api-drift-aaaa",
        "repo": RepoRef(repo_id=REPO, url=str(origin), local_path=str(tmp_path / "gone"),
                        head_sha=pushed),
    }, as_node="push")

    assert run(_run_args(origin, tmp_path, "unmoved")) == 0

    printed = capsys.readouterr().out
    assert "no_ci_run: polled " in printed
    assert "opened:" not in printed


def test_a_discarded_dependency_tree_is_announced_rather_than_done_quietly(
    tmp_path, monkeypatch, capsys
):
    """`_reset_clone` runs `git clean` without `-x`, so the dependency install the previous
    finding paid for survives -- which is the point, and also means an install that finding
    doctored survives too. The adapter discards it, and the discard is printed.

    An operator who does not see this line reads the next finding's wall clock as the cost of
    that finding. Silent, it is a reinstall attributed to the wrong work.
    """
    origin, pushed = _origin_with_a_pushed_branch(tmp_path)
    graph = _remediation_graph(pushed)
    store = _LoopStore([_one_finding()])
    _stub_the_run(monkeypatch, graph, store)
    monkeypatch.setattr(_LoopAdapter, "contaminated", True)

    assert run(_run_args(origin, tmp_path, "fresh")) == 0

    assert "discarded the previous finding's dependency tree" in capsys.readouterr().out


def test_an_untouched_dependency_tree_is_not_announced(tmp_path, monkeypatch, capsys):
    """The counterweight: the line prints on the adapter's answer rather than on every finding.
    A message an operator sees on every run is a message they learn to skip."""
    origin, pushed = _origin_with_a_pushed_branch(tmp_path)
    graph = _remediation_graph(pushed)
    store = _LoopStore([_one_finding()])
    _stub_the_run(monkeypatch, graph, store)
    monkeypatch.setattr(_LoopAdapter, "contaminated", False)

    assert run(_run_args(origin, tmp_path, "clean")) == 0

    assert "discarded" not in capsys.readouterr().out


# --- `python -m sync.cli`: the module entry point ------------------------------------
#
# `raise SystemExit(main())` runs only when this module is `__main__`, which no in-process test
# can arrange -- and a child process's lines are invisible to a coverage run that did not start
# it under coverage, so the statement stays in the missing list however hard these two press on
# it. That is a property of the instrument rather than of the code, and it is the same caveat
# `2026-07-30-sync-coverage-baseline-3.md` records for `mcp/server.py`.
#
# What they establish is the thing the number cannot: the guard exists and it carries the exit
# code out. Delete it and both go red -- an unguarded module runs `main()` never, exits 0 always,
# and every wrapper reading `$?` is told the command succeeded.


def _module_entry_point(*args: str, **env_overrides) -> subprocess.CompletedProcess:
    """`python -m sync.cli`, run the way an operator without an installed console script runs it.

    `PYTHONIOENCODING` in the child's environment as well as `encoding` on the call: the first
    says which bytes arrive and the second says how to decode them, and on this platform a
    Python child emits cp1252 unless told otherwise. `errors="replace"` because this output is
    read as diagnosis rather than as data.
    """
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8", **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "sync.cli", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment,
    )


def test_the_module_entry_point_carries_a_refusal_out_as_the_exit_code(monkeypatch):
    """A wrapper reads `$?`, and a refusal that exited 0 would tell it the command worked.

    `feed-public-key` with no key is the cheapest refusal to reach -- it opens no database and
    reads no file -- and it exits 2 through `raise SystemExit(main())` and nowhere else.
    """
    result = _module_entry_point("feed-public-key", **{cli.FEED_SIGNING_KEY_ENV: ""})

    assert result.returncode == 2
    assert result.stdout == ""
    assert cli.FEED_SIGNING_KEY_ENV in result.stderr


def test_the_module_entry_point_carries_a_success_out_too(signing_key):
    """The counterweight, and it is the half that fails against a module with no guard at all:
    without the block the process exits 0 having printed nothing, which passes any assertion
    that only reads the exit code of a refusal.
    """
    private, _ = signing_key

    result = _module_entry_point("feed-public-key")

    assert result.returncode == 0
    assert bytes.fromhex(result.stdout.strip()) == private.public_key().public_bytes_raw()


def test_the_module_entry_point_refuses_an_invocation_naming_no_subcommand():
    """Argparse's own refusal, reaching the shell. `main()` never returns here -- the parser
    raises `SystemExit` before `args.func` is consulted -- so this is the one path out of the
    module that does not travel through the `raise`, and it still has to be non-zero."""
    result = _module_entry_point()

    assert result.returncode != 0
    assert result.stdout == ""

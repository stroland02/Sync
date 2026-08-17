"""Vendor selection as data, asserted from the entry point rather than from the registry.

`CLAUDE.md` makes the plugin boundary a non-negotiable, and a second adapter existed to prove
the interface generalises past Stripe -- with `cli.py` constructing `StripeAdapter` by name in
two places, so no run could ever reach the second one. What was unreachable was not a feature
but the architectural claim.

So every test here drives `sync.cli`. One that called `prepare_vendor` and asserted the class
it returned would prove the registry works and say nothing about whether anything selects
through it, which is precisely the defect being fixed.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import os
from pathlib import Path

import pytest

import sync.cli as cli
from sync.cli import ingest, run
from sync.core import RepoRef
from sync.signals.registry import (
    VendorContext,
    available_vendors,
    load_vendor,
    prepare_vendor,
)
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.twilio.adapter import TwilioAdapter

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FROM_VERSION, TO_VERSION = "2.1.0", "2.3.0"

# A document with no paths. Nothing here exercises change detection -- what is under test is
# which adapter a run selects -- and an empty specification is enough to build a symbol map
# from without staging a megabyte of vendor JSON.
EMPTY_SPEC = {"openapi": "3.0.0", "paths": {}}

TWILIO_PRODUCTS = [
    {"filename": "twilio_insights_v1.json", "domain": "insights", "version": "v1"},
]


def _stage_twilio(cache: Path) -> None:
    """What a deployment stages for Twilio: the product manifest, and the documents it names.

    Twilio publishes 61 documents per tag and which of them a customer depends on is a
    per-deployment fact -- the adapter's own docstring calls it a scheduling decision and not an
    adapter's business -- so it arrives as configuration rather than as a default in code.
    """
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "twilio-products.json").write_text(json.dumps(TWILIO_PRODUCTS), encoding="utf-8")
    for version in (FROM_VERSION, TO_VERSION):
        (cache / version).mkdir(parents=True, exist_ok=True)
        (cache / version / "twilio_insights_v1.json").write_text(
            json.dumps(EMPTY_SPEC), encoding="utf-8"
        )


class _RecordingIndexer:
    """Stands in for `TypeScriptAdapter`, capturing the vendor adapter it was handed.

    `matches` answers False, which ends the run at exit code 2 before Postgres, the clone or the
    Agent SDK matter. What the run selected has already happened by then, and it is the only
    thing these tests are asking about.
    """

    selected: list = []

    def __init__(self, vendor_adapter) -> None:
        _RecordingIndexer.selected.append(vendor_adapter)

    def matches(self, repo) -> bool:
        return False


class _Store:
    def __init__(self, dsn) -> None: ...

    def apply_schema(self) -> None: ...


def _stub_run(monkeypatch, cache: Path) -> list:
    """Everything a run touches before it has selected a vendor, and nothing after.

    `fetch_spec` and `fetch_sdk_spec` are patched on the registry rather than on `cli`, because
    staging a vendor's artifacts moved there with the selection -- which is the change under
    test. Patching them where they no longer live would leave the suite reaching the network.
    """
    from sync.signals import registry

    def fake_fetch_spec(tag, dest, *args, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(EMPTY_SPEC), encoding="utf-8")
        return dest

    monkeypatch.setattr(registry, "fetch_spec", fake_fetch_spec)
    monkeypatch.setattr(registry, "fetch_sdk_spec", lambda tag, dest: None)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _RecordingIndexer)
    monkeypatch.setattr(cli, "GraphStore", _Store)
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(repo_id="r", url=url, local_path=str(dest), head_sha="0" * 40),
    )
    _RecordingIndexer.selected = []
    return _RecordingIndexer.selected


def _run_args(cache: Path, vendor: str) -> argparse.Namespace:
    return argparse.Namespace(
        vendor=vendor, from_version=FROM_VERSION, to_version=TO_VERSION,
        repo="https://example.invalid/r", dsn=DSN, cache=str(cache),
        limit=1, run_id=None,
    )


def test_a_twilio_run_reaches_the_twilio_adapter(monkeypatch, tmp_path):
    """The claim the project rests on, and the one that was false. `TwilioAdapter` implements
    both halves of `VendorAdapter` and had no path by which a run could reach it, so the
    generality lived in the type system and not in the product.
    """
    cache = tmp_path / "cache"
    _stage_twilio(cache)
    selected = _stub_run(monkeypatch, cache)

    run(_run_args(cache, "twilio"))

    assert selected and isinstance(selected[-1], TwilioAdapter)


def test_a_stripe_run_still_reaches_the_stripe_adapter(monkeypatch, tmp_path):
    """The regression that matters. A registry resolving everything to one adapter passes the
    test above, and this is the only thing that says which one it resolved to.
    """
    cache = tmp_path / "cache"
    selected = _stub_run(monkeypatch, cache)

    run(_run_args(cache, "stripe"))

    assert selected and isinstance(selected[-1], StripeAdapter)


def test_an_unknown_vendor_names_what_is_available_and_never_becomes_stripe():
    """A silent default is how "we support many vendors" becomes "we support one and lie about
    it". `deps.py` already refuses to substitute one package manager for another, because a
    different manager resolves a different tree; a different vendor resolves a different API.
    """
    context = VendorContext(cache_dir=Path("."), from_version="a", to_version="b")

    with pytest.raises(KeyError) as raised:
        prepare_vendor("shopify", context)

    message = str(raised.value)
    assert "shopify" in message
    for vendor in available_vendors():
        assert vendor in message


def test_the_command_line_offers_exactly_the_registered_vendors():
    """Selection being data means the parser's own choices come from the registry. A
    hand-maintained list beside it is a second place to add a vendor and the one somebody
    forgets, which is how a registered adapter stays unreachable while looking wired.
    """
    parser_source = inspect.getsource(cli.build_parser)

    assert "available_vendors()" in parser_source
    assert '["stripe"]' not in parser_source


def test_cli_imports_no_vendor_adapter_class():
    """A source-text assertion, and deliberately so -- said out loud because this file is not
    the place to be subtle about it.

    The property is structural: `cli.py` naming an adapter class is the defect, whatever it
    then does with it. No behavioural assertion catches an import that a later change adds back
    "just for this one case", and that is exactly the shape a regression here would take.
    """
    source = inspect.getsource(cli)

    assert "StripeAdapter" not in source
    assert "TwilioAdapter" not in source


def test_the_registry_is_handed_nothing_that_belongs_to_one_vendor():
    """The other way to re-hardcode: give the registry a union of every adapter's parameters.
    `StripeAdapter` takes `spec_dir` and `symbol_map_path`, which are Stripe's file layout;
    Twilio's are a directory per tag and a manifest. A context carrying either name would be the
    vendor knowledge just removed, moved one file over.
    """
    fields = {field.name for field in dataclasses.fields(VendorContext)}

    assert fields == {"cache_dir", "from_version", "to_version"}


def _document(operation_id: str, field: str, json_type: str) -> dict:
    return {
        "openapi": "3.0.0",
        "paths": {f"/{operation_id}": {"get": {
            "operationId": operation_id,
            "responses": {"200": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {field: {"type": json_type}},
            }}}}},
        }}},
    }


def test_declared_fields_span_every_document_a_vendor_published():
    """One vendor publishes one specification and another publishes one per product, and the
    drift detector asks a question about the vendor rather than about a document. Reading only
    the first would leave every operation in every other product with no declarations at all.
    """
    declared = cli._declared_fields([
        _document("GetRooms", "sid", "string"),
        _document("GetCalls", "duration", "number"),
    ])

    assert set(declared) == {"GetRooms", "GetCalls"}


def test_an_operation_two_documents_both_declare_is_dropped_rather_than_resolved(capsys):
    """The collision flattening would settle silently, in favour of whichever was read last.

    Nothing Twilio publishes promises operation ids are unique across its 61 documents -- the
    adapter records the source document in `raw` for exactly that reason. Keeping either side
    would compare one product's observed traffic against the other product's declarations, and
    every field the observed product really does return would be reported as undeclared: a
    confident wrong finding, in the detector whose whole justification is precision over recall.

    Dropping it costs findings for that operation instead, because `scan` iterates the declared
    map and never looks at an operation absent from it. A miss costs one incident and a false
    finding costs the reviewer's willingness to read the next one, which is the asymmetry this
    project has already committed to.
    """
    declared = cli._declared_fields([
        _document("ListRooms", "sid", "string"),
        _document("ListRooms", "duration", "number"),
    ])

    assert "ListRooms" not in declared
    # Dropped, and never quietly: an operation that stops being checked has to be traceable to
    # the vendor's own duplication rather than look like a detector that found nothing.
    assert "ListRooms" in capsys.readouterr().err


def test_loading_a_staged_vendor_fetches_nothing(monkeypatch, tmp_path):
    """`ingest` reads a cache a previous run staged and must not reach the network to do it, so
    selection has two entry points rather than a flag: one that stages artifacts and one that
    builds over what is already there.
    """
    from sync.signals import registry

    def refuse(*args, **kwargs):
        raise AssertionError("loading a staged vendor must not fetch")

    monkeypatch.setattr(registry, "fetch_spec", refuse)
    monkeypatch.setattr(registry, "fetch_sdk_spec", refuse)
    (tmp_path / "symbols.json").write_text("{}", encoding="utf-8")

    vendor = load_vendor(
        "stripe", VendorContext(cache_dir=tmp_path, from_version="v1", to_version="v2")
    )

    assert isinstance(vendor, StripeAdapter)


def test_the_ingest_refuses_a_vendor_that_cannot_correlate_a_request(tmp_path, capsys):
    """A real divergence between the two adapters, surfaced rather than crashed on.
    `RequestCorrelator` is deliberately separate from `VendorAdapter` -- its own docstring says
    a vendor whose traffic nobody instruments has no reason to implement it -- and `TwilioAdapter`
    does not. An ingest that discovered that as an `AttributeError` mid-fold would report a
    missing method where the answer is that this vendor has no correlation story yet.
    """
    cache = tmp_path / "cache"
    _stage_twilio(cache)
    (cache / "symbols.json").write_text("{}", encoding="utf-8")
    payload = tmp_path / "spans.json"
    payload.write_text(json.dumps({"resourceSpans": []}), encoding="utf-8")

    code = ingest(argparse.Namespace(
        vendor="twilio", payload=str(payload), repo_id="r", dsn=DSN, cache=str(cache),
    ))

    assert code == 2
    assert "twilio" in capsys.readouterr().err

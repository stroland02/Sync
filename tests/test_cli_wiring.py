"""The two components the spec audit found with no caller in `src/`.

Both were complete and tested, and both were unreachable from the only entry point the
product has. That is the defect these tests exist to hold shut, so every one of them drives
`sync.cli` -- the production path -- and none constructs `DeprecationAdapter` or calls
`ingest_payload` itself. A test that reached for either directly would re-create the exact
situation the audit reported: the component works, and nothing gets to it.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path

import pytest

import sync.cli as cli
from sync.cli import _detector_suite, _model_deprecations, _scan, ingest, run
from sync.core import CallSite, RepoRef
from sync.graph.store import GraphStore
from sync.remediate import corpus
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.signals.deprecations import ANTHROPIC, OPENAI

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

FIXTURES = Path(__file__).parent / "fixtures"

# One retired model with a named replacement, in the two-table shape both vendors publish: a
# lifecycle table saying what state each model is in, and an announcement table naming what to
# move to. `LiteralSwapRemediator` needs the replacement, so a page without one would exercise
# the wiring and stop short of the tier the wiring exists to feed.
ANTHROPIC_PAGE = """\
| API model name | Current state | Deprecated   | Tentative retirement date |
| -------------- | ------------- | ------------ | ------------------------- |
| claude-opus-9  | Active        | N/A          | Not sooner than May 1, 2028 |
| claude-old-1   | Retired       | June 5, 2026 | August 5, 2026            |

### 2026-06-05: an announcement

| Retirement date | Deprecated model | Recommended replacement |
| --------------- | ---------------- | ----------------------- |
| August 5, 2026  | `claude-old-1`   | `claude-opus-9`         |
"""

OPENAI_PAGE = """\
| API model name | Current state | Deprecated   | Tentative retirement date |
| -------------- | ------------- | ------------ | ------------------------- |
| gpt-old-1      | Retired       | June 5, 2026 | August 5, 2026            |

### 2026-06-05: an announcement

| Retirement date | Deprecated model | Recommended replacement |
| --------------- | ---------------- | ----------------------- |
| August 5, 2026  | `gpt-old-1`      | `gpt-new-1`             |
"""

# Keyed on each source's own URL, not on the vendor id appearing in it: Anthropic publishes at
# `platform.claude.com`, which carries no such substring. Keyed at all -- rather than returning
# one body for every call -- so a wiring that fetched one vendor twice and never reached the
# other shows up as a missing change instead of passing on a body that happens to parse.
PAGES = {ANTHROPIC.url: ANTHROPIC_PAGE, OPENAI.url: OPENAI_PAGE}


def _fetch_pages(url: str) -> str:
    if url not in PAGES:
        raise AssertionError(f"nothing fetched {url}")
    return PAGES[url]


# --- the model-retirement half ----------------------------------------------------


def test_a_retired_model_becomes_a_vendor_change_through_the_cli(tmp_path):
    """`DeprecationAdapter` had no caller in `src/`, so no `ModelDeprecation` ever became a
    `VendorChange` and `LiteralSwapRemediator` sat in the cascade with nothing to act on --
    the deprecation document's headline path, unreachable.

    Asserted through `cli._model_deprecations`, which is what `run()` calls, rather than by
    constructing the adapter here.
    """
    changes = _model_deprecations(tmp_path, "v2320", "v2330", fetch=_fetch_pages)

    retired = {change.operation_id: change for change in changes}
    assert "claude-old-1" in retired
    assert "gpt-old-1" in retired
    assert retired["claude-old-1"].kind.startswith("deprecation/model-")
    assert retired["claude-old-1"].raw["replacement"] == "claude-opus-9"
    # An active model is not a change. A wiring that emitted every row on the page would put a
    # finding against every model a codebase names.
    assert "claude-opus-9" not in retired


def test_a_retired_model_reaches_the_tier_zero_remediator_end_to_end(tmp_path):
    """Vendor page to a finding the codemod tier will accept, through the CLI's own assembly.

    The audit's complaint was not that any one step was wrong; it was that the steps were never
    joined. So this runs the join: the changes `run()` fetches, the literal call sites `run()`
    indexes, the detector suite `run()` builds, and the scan `run()` performs -- then asks the
    tier-0 remediator whether it can act, which is the claim the deprecation document makes and
    the one that was false.
    """
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()

        for change in _model_deprecations(tmp_path, "v2320", "v2330", fetch=_fetch_pages):
            store.upsert_vendor_change(change)

        site = CallSite(
            repo_id="acme/billing", path="src/summarise.ts", line=4, col=10,
            vendor_id="anthropic", operation_id="claude-old-1", symbol="claude-old-1",
            sdk_version="unknown", content_hash="h1",
        )
        site.id = store.upsert_call_site(site)

        findings = _scan(
            _detector_suite(
                store, spec_document={}, call_sites=[site], deprecations=[],
                vendor_id="stripe", deprecation_vendors=("anthropic", "openai"),
            ),
            store,
        )

    retirements = [f for f in findings if f.call_site_id == site.id]
    assert retirements, "the retired model produced no finding against the call site naming it"

    change = store.get_vendor_change(retirements[0].vendor_change_id)
    assert LiteralSwapRemediator().can_handle(retirements[0], change)


def test_the_run_fetches_model_deprecations_before_it_opens_the_ingest_transaction(monkeypatch, tmp_path):
    """The wiring itself, from `run()` rather than from a helper `run()` might not call.

    A helper with no caller is the defect this task exists to fix, so asserting the helper
    works would repeat it. The ordering is asserted alongside, because the ingest transaction
    holds an ACCESS EXCLUSIVE lock on the graph tables: two vendor pages fetched inside it
    would hold that lock for the length of a download.
    """
    store = _RecordingStore()
    _stub_collaborators(monkeypatch, store)

    order: list[str] = []
    real_model_deprecations = cli._model_deprecations

    def recording(*args, **kwargs):
        order.append("fetch")
        return real_model_deprecations(*args, **{**kwargs, "fetch": _fetch_pages})

    monkeypatch.setattr(cli, "_model_deprecations", recording)
    monkeypatch.setattr(store, "on_transaction", lambda: order.append("transaction"))

    assert run(_run_args(tmp_path)) == 0

    assert order[:2] == ["fetch", "transaction"]
    assert "claude-old-1" in {change.operation_id for change in store.changes}


def test_the_scan_joins_retirements_for_every_deprecation_vendor(tmp_path):
    """`VendorChangeDetector` is scoped to one vendor, and the suite built exactly one of them,
    for Stripe. Upserting an Anthropic retirement into the graph therefore changed nothing that
    any detector would ever read -- the wiring would have looked done and produced no finding.
    """
    suite = _detector_suite(
        store=GraphStore(DSN), spec_document={}, call_sites=[], deprecations=[],
        vendor_id="stripe", deprecation_vendors=("anthropic", "openai"),
    )

    names = [name for name, _ in suite]
    assert "vendor_change" in names
    assert any("anthropic" in name for name in names)
    assert any("openai" in name for name in names)


def test_a_vendor_page_that_cannot_be_fetched_costs_only_its_own_changes(tmp_path, capsys):
    """One vendor being unreachable must not take the other's retirements with it, and must not
    report as a quiet zero -- an empty answer is indistinguishable from a healthy vendor with
    nothing deprecated, which is the confusion this whole signal exists to end.
    """
    def half_broken(url: str) -> str:
        if url == ANTHROPIC.url:
            raise OSError("network is down")
        return OPENAI_PAGE

    changes = _model_deprecations(tmp_path, "v2320", "v2330", fetch=half_broken)

    assert {change.operation_id for change in changes} == {"gpt-old-1"}
    assert "anthropic" in capsys.readouterr().err


# --- the OTLP half ----------------------------------------------------------------

# Enough of a symbol map to correlate the fixture's spans. Written here rather than taken from
# a run's `symbols.json` so the test states which requests it expects to bind.
SYMBOLS = {
    "stripe.charges.retrieve": {
        "operation_id": "GetChargesCharge", "http_method": "get", "path": "/v1/charges/{charge}",
    },
    "stripe.charges.list": {
        "operation_id": "GetCharges", "http_method": "get", "path": "/v1/charges",
    },
    "stripe.charges.create": {
        "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges",
    },
}


def _empty_store() -> GraphStore:
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _targets(store: GraphStore) -> set[str]:
    """Every salted URL digest the graph holds. The digest is the only thing a rotated salt
    changes, so it is what a stability assertion has to read."""
    return {
        span["target"]
        for call in store.observed_calls("acme/billing")
        for span in call.spans.values()
    }


def _ingest_args(tmp_path, **overrides) -> argparse.Namespace:
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "symbols.json").write_text(json.dumps(SYMBOLS), encoding="utf-8")
    return argparse.Namespace(**{
        "vendor": "stripe",
        "payload": str(FIXTURES / "otlp" / "stripe_client_spans.json"),
        "repo_id": "acme/billing",
        "dsn": DSN,
        "cache": str(cache),
        **overrides,
    })


@pytest.fixture()
def deployment_salt(tmp_path, monkeypatch):
    """Point the deployment's salt at a throwaway file, and take the override out of the
    environment so the file path is what runs. Otherwise every ingest test writes
    `.sync-corpus-salt` into the repository root."""
    monkeypatch.delenv(corpus.SALT_VARIABLE, raising=False)
    monkeypatch.setattr(corpus, "SALT_FILE", tmp_path / ".sync-corpus-salt")
    return tmp_path / ".sync-corpus-salt"


def test_an_otlp_payload_lands_rows_in_observed_call_through_the_cli(tmp_path, deployment_salt):
    """`ingest_payload` had no caller in `src/` outside its own package `__init__`, so the
    decode and the fold both worked and no span ever reached the graph.

    The correlated row is what makes this more than a decode test: a span carries a URL and the
    graph is keyed by operation, so a row landing under `binding_rung` 'observed' is the only
    evidence the vendor correlator was wired in rather than left out.
    """
    store = _empty_store()

    assert ingest(_ingest_args(tmp_path)) == 0

    calls = store.observed_calls("acme/billing")
    assert calls
    correlated = [call for call in calls if call.binding_rung == "observed"]
    assert {call.operation_id for call in correlated} >= {"GetChargesCharge", "GetCharges"}
    # A span that correlates to nothing is kept rather than dropped: the unresolved fraction is
    # the only measure of how good the correlation is, and dropping it makes that invisible.
    assert any(call.binding_rung == "unresolved" for call in calls)


def test_the_ingest_starts_no_server_and_binds_no_port(tmp_path, monkeypatch, deployment_salt):
    """A stated strategic refusal, and this is what protects it.

    `2026-07-27-sync-pipeline-discipline.md` refuses ingestion *infrastructure*, not OTLP:
    there is no server, no port and no collector protocol, because a server needs a supervisor,
    an authentication story telling one customer's collector from another's, and a deployment
    this project does not have -- none of which makes a span mean more once it lands. The
    refusal is easy to erode by accident, since "wire the ingest" and "serve the ingest" sound
    alike, so binding a port or listening on one fails here.
    """
    def refuse(*args, **kwargs):
        raise AssertionError("the ingest path must not bind a port or start a listener")

    monkeypatch.setattr(socket.socket, "bind", refuse)
    monkeypatch.setattr(socket.socket, "listen", refuse)

    assert ingest(_ingest_args(tmp_path)) == 0


def test_the_ingest_salt_is_stable_across_invocations(tmp_path, deployment_salt):
    """The trap `ingest.py` names in as many words: the same URL under two salts digests to two
    values, so a salt generated per run makes repeat calls look distinct and silently deletes
    the repeated-call finding. Nothing in the schema can detect that having happened, which is
    why it is asserted here instead.
    """
    store = _empty_store()

    args = _ingest_args(tmp_path)
    assert ingest(args) == 0
    first = _targets(store)

    assert ingest(args) == 0
    second = _targets(store)

    assert first == second
    assert deployment_salt.read_text(encoding="utf-8").strip()


def test_the_ingest_salts_with_the_deployments_own_salt(tmp_path, monkeypatch, deployment_salt):
    """Reuse asserted rather than assumed. `corpus_salt` already answers the question
    `ingest.py` says has to be answered before this path can exist -- stable per deployment,
    unique to it, stored -- so a second salt store would be a second thing an operator carries
    between hosts and a second one they can lose. Changing the deployment's salt has to change
    the digests, or something else is salting them.
    """
    store = _empty_store()

    monkeypatch.setenv(corpus.SALT_VARIABLE, "salt-one")
    assert ingest(_ingest_args(tmp_path)) == 0
    under_one = _targets(store)

    monkeypatch.setenv(corpus.SALT_VARIABLE, "salt-two")
    assert ingest(_ingest_args(tmp_path)) == 0

    assert _targets(store) - under_one


def test_the_ingest_refuses_a_payload_it_cannot_correlate_against(tmp_path, capsys):
    """The symbol map is a run's output, and an ingest against a cache that never held one
    would otherwise correlate nothing and report a healthy-looking batch of unresolved rows --
    a customer who does not call this vendor and a missing file look identical downstream.
    """
    args = _ingest_args(tmp_path)
    Path(args.cache, "symbols.json").unlink()

    assert ingest(args) == 2
    assert "symbols.json" in capsys.readouterr().err


# --- stubs for driving `run()` without Postgres, the network or the Agent SDK ------


class _RecordingStore:
    """Enough `GraphStore` for `run()` to reach the scan, recording what it was given."""

    def __init__(self) -> None:
        self.changes: list = []
        self.on_transaction = lambda: None

    def apply_schema(self) -> None: ...

    def transaction(self):
        self.on_transaction()

        class _Nothing:
            def __enter__(self): return None
            def __exit__(self, *exc): return False

        return _Nothing()

    def truncate_all(self) -> None: ...

    def upsert_call_site(self, site) -> str:
        return "cs-1"

    def upsert_vendor_change(self, change) -> None:
        self.changes.append(change)

    def insert_finding(self, finding) -> str:
        return "f-1"


class _NoFindings:
    detector_id = "stub"

    def __init__(self, *args, **kwargs) -> None: ...

    def scan(self):
        return []


class _StubVendor:
    vendor_id = "stripe"

    def __init__(self, *args, **kwargs) -> None: ...

    def fetch_changes(self, from_version, to_version):
        return []


class _StubAdapter:
    def __init__(self, *args, **kwargs) -> None: ...

    def matches(self, repo) -> bool:
        return True

    def index(self, repo):
        return []


def _stub_collaborators(monkeypatch, store) -> None:
    monkeypatch.setattr(cli, "GraphStore", lambda dsn: store)
    monkeypatch.setattr(cli, "VendorChangeDetector", _NoFindings)
    monkeypatch.setattr(cli, "ParameterDeprecationDetector", _NoFindings)
    monkeypatch.setattr(cli, "ObservedDriftDetector", _NoFindings)
    monkeypatch.setattr(cli, "StripeAdapter", _StubVendor)
    monkeypatch.setattr(cli, "TypeScriptAdapter", _StubAdapter)
    monkeypatch.setattr(cli, "http_fetch", lambda url, **kw: "")
    # Stubbed whole rather than through the fetch: the parameter half writes each vendor's page
    # into the cache the model half reads, which is the sharing that keeps a real run to one
    # download per vendor. Left live against a fetch returning nothing, it would seed an empty
    # page and the model half would read that instead of what this test injects.
    monkeypatch.setattr(cli, "_parameter_deprecations", lambda cache: [])
    monkeypatch.setattr(cli, "_literal_call_sites", lambda repo: [])
    monkeypatch.setattr(cli, "fetch_spec", _write_empty_spec)
    monkeypatch.setattr(cli, "fetch_sdk_spec", lambda tag, dest: None)
    monkeypatch.setattr(cli, "build_symbol_map", lambda spec, sdk: {})
    monkeypatch.setattr(
        cli, "_clone",
        lambda url, dest: RepoRef(repo_id="repo", url=url, local_path=str(dest), head_sha="0" * 40),
    )


def _write_empty_spec(tag, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"paths": {}}), encoding="utf-8")
    return dest


def _run_args(tmp_path) -> argparse.Namespace:
    return argparse.Namespace(
        vendor="stripe", from_version="v2320", to_version="v2330",
        repo="https://example.invalid/r", dsn="postgresql://unused",
        cache=str(tmp_path / "cache"), limit=1, run_id=None,
    )

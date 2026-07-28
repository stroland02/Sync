import json
import subprocess
from pathlib import Path

import pytest

from sync.core import VendorAdapter
from sync.signals.stripe import adapter as adapter_module
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import SymbolCollision, build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures" / "specs"

SPEC = {
    "paths": {
        "/v1/charges": {
            "post": {"operationId": "PostCharges"},
            "get": {"operationId": "GetCharges"},
        },
        "/v1/charges/{charge}": {
            "get": {"operationId": "GetChargesCharge"},
            "post": {"operationId": "PostChargesCharge"},
        },
        "/v1/payment_intents": {"post": {"operationId": "PostPaymentIntents"}},
        "/v1/customers/{customer}": {"delete": {"operationId": "DeleteCustomersCustomer"}},
    }
}


def test_collection_post_maps_to_create():
    assert build_symbol_map(SPEC)["stripe.charges.create"]["operation_id"] == "PostCharges"


def test_collection_get_maps_to_list():
    assert build_symbol_map(SPEC)["stripe.charges.list"]["operation_id"] == "GetCharges"


def test_instance_get_maps_to_retrieve():
    assert build_symbol_map(SPEC)["stripe.charges.retrieve"]["operation_id"] == "GetChargesCharge"


def test_instance_post_maps_to_update():
    assert build_symbol_map(SPEC)["stripe.charges.update"]["operation_id"] == "PostChargesCharge"


def test_instance_delete_maps_to_del():
    assert build_symbol_map(SPEC)["stripe.customers.del"]["operation_id"] == "DeleteCustomersCustomer"


def test_snake_case_resource_becomes_camel_case_symbol():
    assert "stripe.paymentIntents.create" in build_symbol_map(SPEC)


def test_two_operations_deriving_one_symbol_raise_rather_than_overwrite():
    """A silent overwrite makes the losing operation permanently unreachable.

    No call site can ever resolve to it, so a breaking change against it can
    never produce a finding -- the failure is invisible at every later stage.
    Both operation ids appear in the message because the loser is exactly what
    a plain overwrite destroys.
    """
    colliding = {
        "paths": {
            "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
            "/v1/charges/{id}": {"get": {"operationId": "GetChargesId"}},
        }
    }

    with pytest.raises(SymbolCollision) as excinfo:
        build_symbol_map(colliding)

    message = str(excinfo.value)
    assert "stripe.charges.retrieve" in message
    assert "GetChargesCharge" in message
    assert "GetChargesId" in message


# Reduced from stripe/openapi at tag v2330: every path key and every operationId
# kept intact, and of each GET's 200 response schema only the part that separates
# a list envelope from a single resource. The path set is therefore the real
# denominator, which is the whole point of pinning coverage against it.
SHAPE_FIXTURE = FIXTURES / "stripe_v2330_shape.json"


def _shape_spec():
    return json.loads(SHAPE_FIXTURE.read_text(encoding="utf-8"))


def test_coverage_names_the_paths_the_derivation_reaches():
    """Coverage is pinned as a set of named expectations, not as a threshold.

    A threshold can be lowered in a one-line diff and nobody notices. Naming
    both what must resolve and what must not means a change to the path pattern
    has to state which way it moved.
    """
    spec = _shape_spec()
    mapping = build_symbol_map(spec)
    reached = {entry["path"] for entry in mapping.values()}

    assert len(spec["paths"]) == 414
    assert len(reached) == 105

    assert mapping["stripe.charges.create"]["path"] == "/v1/charges"
    assert mapping["stripe.charges.list"]["path"] == "/v1/charges"
    assert mapping["stripe.charges.retrieve"]["path"] == "/v1/charges/{charge}"
    assert mapping["stripe.charges.update"]["path"] == "/v1/charges/{charge}"
    assert mapping["stripe.customers.del"]["path"] == "/v1/customers/{customer}"
    assert mapping["stripe.paymentIntents.create"]["path"] == "/v1/payment_intents"


def test_coverage_names_the_paths_the_derivation_cannot_reach():
    """Three shapes account for the unreached three quarters.

    A call site on any of them produces no symbol, so no finding can be raised
    against it however breaking the vendor change is.
    """
    spec = _shape_spec()
    reached = {entry["path"] for entry in build_symbol_map(spec).values()}

    for unreachable in (
        "/v1/customers/{customer}/sources",           # nested sub-resource collection
        "/v1/accounts/{account}/persons/{person}",    # nested sub-resource instance
        "/v1/checkout/sessions",                      # namespaced resource
    ):
        assert unreachable in spec["paths"]
        assert unreachable not in reached


def test_a_collection_path_returning_one_resource_uses_the_instance_verbs():
    """`GET /v1/balance` returns a balance, not a page of balances.

    The specification says so itself: its 200 schema is a bare `$ref`, where a
    collection's is the `data`/`has_more` envelope. A path that addresses one
    resource takes the instance verbs, so the SDK exposes `.retrieve` and
    `.update` -- confirmed against stripe-node's generated `Balance.ts` and
    `BalanceSettings.ts` rather than inferred from the name.
    """
    mapping = build_symbol_map(_shape_spec())

    assert mapping["stripe.balance.retrieve"]["path"] == "/v1/balance"
    assert "stripe.balance.list" not in mapping

    assert mapping["stripe.balanceSettings.retrieve"]["path"] == "/v1/balance_settings"
    assert mapping["stripe.balanceSettings.update"]["http_method"] == "post"
    assert "stripe.balanceSettings.create" not in mapping


def test_v1_account_still_derives_a_resource_name_the_sdk_does_not_expose():
    """Known limitation, pinned rather than guessed at.

    The verb is now right -- `/v1/account` returns one account -- but stripe-node
    binds that operation under the *plural* namespace: `stripe.accounts.retrieve()`
    called with no id, and `stripe.accounts.retrieveCurrent()`. Nothing in the
    specification carries the plural, so deriving it would mean inventing a
    singular-to-plural rule, which is the vendor-specific assumption the design
    document names as the top risk.

    Two consequences, both live: no call site on `GET /v1/account` resolves, and
    `stripe.accounts.retrieve` resolves to `/v1/accounts/{account}` alone even
    though the SDK dispatches it on argument count across both operations. A
    path-shaped derivation cannot express that; it needs a source for SDK naming.
    """
    mapping = build_symbol_map(_shape_spec())

    assert mapping["stripe.account.retrieve"]["path"] == "/v1/account"
    assert "stripe.accounts.retrieveCurrent" not in mapping
    assert mapping["stripe.accounts.retrieve"]["path"] == "/v1/accounts/{account}"


def test_adapter_satisfies_the_vendor_protocol(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert isinstance(adapter, VendorAdapter)
    assert adapter.vendor_id == "stripe"


def test_operation_for_symbol_resolves_a_known_call(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    ref = adapter.operation_for_symbol("stripe.charges.create")
    assert ref is not None
    assert ref.operation_id == "PostCharges"
    assert ref.http_method == "post"
    assert ref.path == "/v1/charges"


def test_operation_for_symbol_returns_none_for_unknown(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert adapter.operation_for_symbol("stripe.nonexistent.create") is None


def test_fetch_changes_reads_two_local_specs(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    changes = list(adapter.fetch_changes("charges_base", "charges_revision"))
    assert changes
    assert all(c.vendor_id == "stripe" for c in changes)


def test_fetch_changes_filters_noise_records_before_they_become_vendor_changes(monkeypatch, tmp_path):
    """A noise-kind record must never reach a VendorChange, not just an intermediate list.

    Stubs `run_oasdiff_breaking` at module scope -- the same substitution point
    `test_agent_patch.py` uses for `query` -- so the assertion is on what
    `StripeAdapter.fetch_changes` actually returns, not on filtering logic
    exercised in isolation from the method that is supposed to apply it.
    """

    def fake_run_oasdiff_breaking(base, revision):
        return [
            {"id": "response-property-enum-value-added", "text": "added `mastercard_compliance`",
             "operationId": "PostCharges", "path": "/v1/charges"},
            {"id": "response-optional-property-removed", "text": "removed the optional property `status`",
             "operationId": "PostCharges", "path": "/v1/charges"},
        ]

    monkeypatch.setattr(adapter_module, "run_oasdiff_breaking", fake_run_oasdiff_breaking)

    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    (tmp_path / "base.json").write_text("{}", encoding="utf-8")
    (tmp_path / "revision.json").write_text("{}", encoding="utf-8")
    stripe_adapter = StripeAdapter(spec_dir=tmp_path, symbol_map_path=tmp_path / "map.json")

    changes = list(stripe_adapter.fetch_changes("base", "revision"))

    assert len(changes) == 1
    assert changes[0].kind == "response-optional-property-removed"


def test_fetch_spec_returns_the_cached_file_without_invoking_gh(tmp_path, monkeypatch):
    """A tag names an immutable commit, so a populated cache entry is already
    byte-identical to whatever `gh` would return -- refetching it would only
    spend 8 MB of network for the same bytes. Asserting on the recorded call
    list, not just the return value, is the point: the return value would
    look the same whether `gh` ran or not.
    """
    calls = []
    monkeypatch.setattr(adapter_module.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    dest = tmp_path / "v2330.json"
    dest.write_bytes(b'{"openapi": "3.0.0"}')

    result = adapter_module.fetch_spec("v2330", dest)

    assert result == dest
    assert calls == []
    assert dest.read_bytes() == b'{"openapi": "3.0.0"}'


def test_fetch_spec_refetches_when_the_cached_file_is_empty(tmp_path, monkeypatch):
    """A zero-byte file is what an interrupted or failed previous write
    leaves behind, not a valid cache hit -- treating it as one would hand a
    truncated spec to oasdiff instead of a fetch failure.
    """
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b'{"openapi": "3.0.0"}', stderr=b"")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    dest = tmp_path / "v2330.json"
    dest.write_bytes(b"")

    result = adapter_module.fetch_spec("v2330", dest)

    assert result == dest
    assert len(calls) == 1
    assert dest.read_bytes() == b'{"openapi": "3.0.0"}'


def test_fetch_spec_fetches_when_the_file_is_missing_entirely(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b'{"openapi": "3.0.0"}', stderr=b"")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    dest = tmp_path / "specs" / "v2330.json"

    result = adapter_module.fetch_spec("v2330", dest)

    assert result == dest
    assert len(calls) == 1
    assert dest.read_bytes() == b'{"openapi": "3.0.0"}'

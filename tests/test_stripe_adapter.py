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


def test_a_stable_id_supplies_the_method_name_the_http_verb_gets_wrong():
    """`DELETE /v1/subscriptions/{id}` is `.cancel` in the SDK, not `.del`.

    stripe-node's generated `Subscriptions.ts` exposes `cancel` and no `del` at
    all, so the HTTP-verb rule is not merely unidiomatic here, it names a method
    that does not exist. The stable id says `cancel_billing_subscription`, and
    the vendor is the authority on its own SDK.
    """
    spec = {"paths": {"/v1/subscriptions/{subscription_exposed_id}": {"delete": {"operationId": "DeleteSubscription"}}}}
    sdk = {"paths": {"/v1/subscriptions/{subscription_exposed_id}": {"delete": {"x-stableId": "cancel_billing_subscription"}}}}

    mapping = build_symbol_map(spec, sdk)

    assert mapping["stripe.subscriptions.cancel"]["operation_id"] == "DeleteSubscription"
    assert "stripe.subscriptions.del" not in mapping


def test_a_stable_id_that_qualifies_its_verb_still_yields_the_verb():
    """The verb is not always the leading token.

    `top_level_retrieve_invoice_payment` and `unified_list_tax_ids` both put a
    qualifier in front of it. Reading token zero would find no verb and fall
    silently back to the HTTP rule, which for a collection path answers `list`.
    The path here carries the real stable id on a collection GET so the two
    readings disagree and the test can tell them apart.
    """
    spec = {"paths": {"/v1/invoice_payments": {"get": {"operationId": "GetInvoicePayments"}}}}
    sdk = {"paths": {"/v1/invoice_payments": {"get": {"x-stableId": "top_level_retrieve_invoice_payment"}}}}

    mapping = build_symbol_map(spec, sdk)

    assert mapping["stripe.invoicePayments.retrieve"]["operation_id"] == "GetInvoicePayments"
    assert "stripe.invoicePayments.list" not in mapping


def test_a_stable_id_holding_several_ids_is_read_from_its_first_entry_only():
    """`x-stableId` is sometimes a comma-separated list, not one id.

    Eight operations in v2330 carry one; `/v1/tokens` POST carries six. Reading
    the raw string lets a later entry speak for the operation -- scanning
    `create_bank_account_token,...,create_cvc_update_token` for a verb finds an
    `update` sitting inside the last entry's resource name.

    The value below is constructed, and deliberately so. Every list in v2330
    agrees on its leading verb and every one of those verbs sits at token zero,
    so no real value tells the two readings apart -- the split is defensive
    rather than load-bearing today, and a test using a real value would pass
    whichever reading it exercised. This one puts the first entry's verb out of
    the table's reach and a sibling's within it, on an instance path so the
    HTTP fallback answers `retrieve` where the borrowed verb would answer `list`.
    """
    spec = {"paths": {"/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}}}}
    sdk = {"paths": {"/v1/charges/{charge}": {"get": {"x-stableId": "expire_charge,top_level_list_charges"}}}}

    mapping = build_symbol_map(spec, sdk)

    assert mapping["stripe.charges.retrieve"]["operation_id"] == "GetChargesCharge"
    assert "stripe.charges.list" not in mapping


def test_delete_becomes_the_method_name_javascript_left_room_for():
    """The stable id says `delete`; every SDK resource spells the method `del`.

    Checked in stripe-node's generated `Customers.ts`, `TaxIds.ts`, `Coupons.ts`,
    `InvoiceItems.ts` and `Accounts.ts` -- five resources, all `del`, none
    `delete`. It is the one entry in the table that is not its own method name.
    """
    spec = {"paths": {"/v1/coupons/{coupon}": {"delete": {"operationId": "DeleteCoupon"}}}}
    sdk = {"paths": {"/v1/coupons/{coupon}": {"delete": {"x-stableId": "delete_coupon"}}}}

    mapping = build_symbol_map(spec, sdk)

    assert mapping["stripe.coupons.del"]["operation_id"] == "DeleteCoupon"
    assert "stripe.coupons.delete" not in mapping


def test_a_verb_the_table_does_not_name_leaves_the_operation_on_the_http_rule():
    """Sixty-odd leading tokens appear across the document; six are checked.

    Accepting an unchecked one would invent a method name from a word nobody
    verified, which is the failure this whole change exists to stop. Falling
    back is the conservative direction: it yields the answer the map already
    gave rather than a new and unverified one.
    """
    spec = {"paths": {"/v1/charges": {"get": {"operationId": "GetCharges"}}}}
    sdk = {"paths": {"/v1/charges": {"get": {"x-stableId": "search_charges"}}}}

    mapping = build_symbol_map(spec, sdk)

    assert mapping["stripe.charges.list"]["operation_id"] == "GetCharges"
    assert "stripe.charges.search" not in mapping


def test_without_an_sdk_document_the_map_is_what_it_always_was():
    """`spec3.sdk.json` carried no `x-stableId` at all before roughly v2320.

    Measured, not assumed: the file exists at v1900 -- 8.8 MB, 366 paths -- and
    holds zero extensions of any kind. A version like that has to degrade to the
    HTTP rule, so absence is a supported input rather than an error.
    """
    assert build_symbol_map(SPEC, None) == build_symbol_map(SPEC)
    assert build_symbol_map(SPEC, {"paths": {}}) == build_symbol_map(SPEC)


def test_the_collision_guard_fires_when_the_stable_id_is_what_causes_the_clash():
    """A new verb source is a new way for two operations to claim one symbol.

    The guard has to cover the verb wherever it came from, or this change
    reintroduces exactly the silent overwrite it was added to stop.
    """
    spec = {
        "paths": {
            "/v1/charges": {"get": {"operationId": "GetCharges"}},
            "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
        }
    }
    sdk = {
        "paths": {
            "/v1/charges": {"get": {"x-stableId": "top_level_retrieve_charge"}},
            "/v1/charges/{charge}": {"get": {"x-stableId": "retrieve_charge"}},
        }
    }

    with pytest.raises(SymbolCollision) as excinfo:
        build_symbol_map(spec, sdk)

    assert "stripe.charges.retrieve" in str(excinfo.value)


# Reduced from stripe/openapi at tag v2330: every path key and every operationId
# kept intact, and of each GET's 200 response schema only the part that separates
# a list envelope from a single resource. The path set is therefore the real
# denominator, which is the whole point of pinning coverage against it.
SHAPE_FIXTURE = FIXTURES / "stripe_v2330_shape.json"

# The same release's `spec3.sdk.json`, reduced to the one extension that is read
# from it. It describes what the SDK surfaces, so it is a subset of the paths
# above rather than a superset.
SDK_SHAPE_FIXTURE = FIXTURES / "stripe_v2330_sdk_shape.json"


def _shape_spec():
    return json.loads(SHAPE_FIXTURE.read_text(encoding="utf-8"))


def _sdk_shape_spec():
    return json.loads(SDK_SHAPE_FIXTURE.read_text(encoding="utf-8"))


def test_the_sdk_document_changes_exactly_one_symbol_across_a_whole_release():
    """The measured effect of this change, pinned so it cannot drift unnoticed.

    Consulting the vendor for 521 verbs corrects one symbol out of 179 and moves
    coverage by nothing: the path pattern decides which operations resolve, and
    the stable id only decides what the resolved one is called. Pinning the delta
    as a set rather than a count means a future release that corrects a second
    symbol has to say so here.
    """
    spec, sdk = _shape_spec(), _sdk_shape_spec()
    before, after = build_symbol_map(spec), build_symbol_map(spec, sdk)

    assert len(sdk["paths"]) == 381
    assert set(after) - set(before) == {"stripe.subscriptions.cancel"}
    assert set(before) - set(after) == {"stripe.subscriptions.del"}
    assert len(after) == len(before) == 179
    assert {e["path"] for e in after.values()} == {e["path"] for e in before.values()}


def test_coverage_names_the_paths_the_derivation_reaches():
    """Coverage is pinned as a set of named expectations, not as a threshold.

    A threshold can be lowered in a one-line diff and nobody notices. Naming
    both what must resolve and what must not means a change to the path pattern
    has to state which way it moved.

    Both documents are passed, because both are what the pipeline builds from.
    Consulting the sdk document leaves these numbers untouched: it renames one
    symbol and reaches no new operation, since the path pattern alone decides
    what resolves.
    """
    spec = _shape_spec()
    mapping = build_symbol_map(spec, _sdk_shape_spec())
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
    reached = {entry["path"] for entry in build_symbol_map(spec, _sdk_shape_spec()).values()}

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

    Deliberately built without the sdk document. That document names the verb
    for these three paths and would carry the assertion on its own, leaving the
    heuristic untested — and the heuristic still decides every operation the
    document does not cover. The two agree here, which is corroboration rather
    than a reason to stop testing one of them.
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

    Asserted with the sdk document in hand, which is what makes it worth keeping:
    Stripe's own generator input names the verb for `GET /v1/account`
    (`retrieve_connect_account`) and still says nothing about the namespace, so
    the limitation survives the change that was meant to be its answer.
    """
    mapping = build_symbol_map(_shape_spec(), _sdk_shape_spec())

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


def test_fetch_sdk_spec_asks_github_for_the_sdk_document(tmp_path, monkeypatch):
    """Asserting on the argv, not the return value, is the point.

    Both documents live in the same repository at the same tags and both would
    write bytes to `dest`, so a call that fetched the wrong one would return a
    result indistinguishable from a correct run.
    """
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b'{"openapi": "3.0.0"}', stderr=b"")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    result = adapter_module.fetch_sdk_spec("v2330", tmp_path / "v2330.sdk.json")

    assert result == tmp_path / "v2330.sdk.json"
    assert len(calls) == 1
    assert "openapi/spec3.sdk.json" in calls[0][2]
    assert "openapi/spec3.json?" not in calls[0][2]


def test_fetch_sdk_spec_returns_none_when_the_tag_has_no_sdk_document():
    """The sdk document is an enhancement, so its absence must not end a run.

    A tag that predates it, or a fork that never published it, has to degrade to
    the HTTP-verb derivation. This swallows every `gh` failure rather than only
    a 404, which is affordable because the base specification is fetched first
    and still raises — a real outage surfaces there, not here.
    """
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout=b"", stderr=b"gh: Not Found (HTTP 404)")

    original = adapter_module.subprocess.run
    adapter_module.subprocess.run = fake_run
    try:
        assert adapter_module.fetch_sdk_spec("v0001", Path("does-not-exist") / "v0001.sdk.json") is None
    finally:
        adapter_module.subprocess.run = original


def test_fetch_sdk_spec_returns_the_cached_file_without_invoking_gh(tmp_path, monkeypatch):
    """The sdk document is 10 MB, larger than the specification it accompanies.

    Fetching a second document per version doubles the download, so the cache
    has to hold for it exactly as it does for the first.
    """
    calls = []
    monkeypatch.setattr(adapter_module.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    dest = tmp_path / "v2330.sdk.json"
    dest.write_bytes(b'{"openapi": "3.0.0"}')

    assert adapter_module.fetch_sdk_spec("v2330", dest) == dest
    assert calls == []

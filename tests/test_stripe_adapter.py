import json
from pathlib import Path

from sync.core import VendorAdapter
from sync.signals.stripe import adapter as adapter_module
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

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


def test_adapter_satisfies_the_vendor_protocol(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert isinstance(adapter, VendorAdapter)
    assert adapter.vendor_id == "stripe"


def test_operation_for_symbol_resolves_a_known_call(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    ref = adapter.operation_for_symbol("stripe.charges.create")
    assert ref is not None
    assert ref.operation_id == "PostCharges"
    assert ref.http_method == "post"
    assert ref.path == "/v1/charges"


def test_operation_for_symbol_returns_none_for_unknown(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
    adapter = StripeAdapter(spec_dir=FIXTURES, symbol_map_path=tmp_path / "map.json")
    assert adapter.operation_for_symbol("stripe.nonexistent.create") is None


def test_fetch_changes_reads_two_local_specs(tmp_path):
    (tmp_path / "map.json").write_text(json.dumps(build_symbol_map(SPEC)))
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

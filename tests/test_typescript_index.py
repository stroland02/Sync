import json
from pathlib import Path

from sync.core import LanguageAdapter, RepoRef
from sync.index.typescript import TypeScriptAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
TS = FIXTURES / "ts"

SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
    }
}


def _adapter(tmp_path) -> TypeScriptAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)
    return TypeScriptAdapter(vendor_adapter=vendor)


def _repo(name: str) -> RepoRef:
    return RepoRef(repo_id=name, url=f"https://example.invalid/{name}", local_path=str(TS / name), head_sha="0" * 40)


def test_adapter_satisfies_the_language_protocol(tmp_path):
    assert isinstance(_adapter(tmp_path), LanguageAdapter)


def test_matches_a_repo_that_depends_on_stripe(tmp_path):
    assert _adapter(tmp_path).matches(_repo("simple")) is True


def test_finds_the_call_site_and_resolves_the_operation(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("simple")))
    assert len(sites) == 1
    site = sites[0]
    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.path == "src/billing.ts"
    assert site.line == 6


def test_captures_argument_keys_passed_at_the_call_site(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert sorted(site.args_keys) == ["amount", "currency"]


def test_captures_response_fields_the_code_actually_reads(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert sorted(site.response_fields_read) == ["id", "status"]


def test_records_the_sdk_version_from_package_json(tmp_path):
    site = list(_adapter(tmp_path).index(_repo("simple")))[0]
    assert site.sdk_version == "18.0.0"


def test_resolves_a_renamed_import_and_renamed_client_variable(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("aliased")))
    assert len(sites) == 1
    assert sites[0].symbol == "stripe.charges.create"
    assert sites[0].response_fields_read == ["status"]


def test_resolves_a_client_imported_from_another_module(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("wrapped")))
    assert len(sites) == 1
    assert sites[0].symbol == "stripe.charges.retrieve"
    assert sites[0].operation_id == "GetChargesCharge"


def test_content_hash_is_stable_across_runs(tmp_path):
    first = list(_adapter(tmp_path).index(_repo("simple")))[0].content_hash
    second = list(_adapter(tmp_path).index(_repo("simple")))[0].content_hash
    assert first == second

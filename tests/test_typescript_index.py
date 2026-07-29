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


def test_destructured_response_fields_record_the_api_key_not_the_renamed_binding(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("destructured")))
    assert len(sites) == 1
    assert sorted(sites[0].response_fields_read) == ["id", "status"]


def test_response_fields_do_not_leak_across_functions_with_the_same_result_name(tmp_path):
    sites = list(_adapter(tmp_path).index(_repo("scoped")))
    assert len(sites) == 1
    assert sorted(sites[0].response_fields_read) == ["status"]


def test_argument_keys_record_a_nested_object_literal_as_a_path(tmp_path):
    """A nested key is recorded under its parent, and the parent stays.

    Every prefix is recorded, so a change naming only `metadata` still matches
    a call site that passes `metadata.internal_id` -- the detector's rule
    compares a call site's path against the change's, and it only has to look
    in one direction if both sides carry their prefixes.
    """
    sites = list(_adapter(tmp_path).index(_repo("nested_args")))
    assert len(sites) == 1
    assert sorted(sites[0].args_keys) == [
        "amount",
        "currency",
        "metadata",
        "metadata.enabled",
        "metadata.internal_id",
    ]


def test_response_fields_record_the_whole_chain_the_code_reads(tmp_path):
    """A member chain deeper than one hop is recorded as a dotted path.

    Real vendor changes are nested -- measured across Stripe's own
    specification, none is depth-1 -- so a call site that records only the
    first hop can never meet one. Each prefix is recorded alongside the full
    chain, so the chain matches a change at any depth along it.

    `result.data[0].customer` stops at `data`: the subscript is where syntax
    alone stops being able to follow the value, and oasdiff spells the same
    boundary as an `items` segment.
    """
    sites = list(_adapter(tmp_path).index(_repo("nested_response")))
    assert len(sites) == 1
    assert sorted(sites[0].response_fields_read) == [
        "data",
        "error",
        "error.payment_method",
        "payment_method_details",
        "payment_method_details.card",
        "payment_method_details.card.brand",
    ]


def test_a_nested_destructuring_pattern_records_its_path(tmp_path):
    """Destructuring reaches nested fields too, and must record them the same way."""
    sites = list(_adapter(tmp_path).index(_repo("nested_destructured")))
    assert len(sites) == 1
    assert sorted(sites[0].response_fields_read) == [
        "id",
        "payment_method_details",
        "payment_method_details.card",
        "payment_method_details.card.brand",
    ]


def test_does_not_match_a_repo_without_the_stripe_dependency(tmp_path):
    assert _adapter(tmp_path).matches(_repo("no_stripe")) is False


def test_does_not_match_a_repo_with_no_manifest_at_all(tmp_path):
    assert _adapter(tmp_path).matches(_repo("nonexistent")) is False


def test_a_malformed_manifest_is_not_a_match_rather_than_a_traceback(tmp_path):
    """A customer's manifest is untrusted input, so it is a boundary to validate.

    An unparseable `package.json` used to raise `JSONDecodeError` out of
    `run()`. The honest answer is the one the CLI already has a path for:
    this repository does not demonstrably depend on the SDK.
    """
    assert _adapter(tmp_path).matches(_repo("malformed_manifest")) is False


def _by_line(sites) -> dict[int, object]:
    return {s.line: s for s in sites}


def test_a_call_outside_a_loop_has_no_loop_depth(tmp_path):
    """The ordinary case, and the one that must stay zero: a call made once per request is
    not an efficiency finding and a detector must be able to say so cheaply."""
    sites = _by_line(_adapter(tmp_path).index(_repo("in_loop")))
    assert sites[6].loop_depth == 0


def test_a_call_inside_a_loop_records_depth_one(tmp_path):
    """One page of results becoming N vendor calls is the first efficiency signal the design
    document names, and it is visible in the syntax tree rather than needing telemetry."""
    sites = _by_line(_adapter(tmp_path).index(_repo("in_loop")))
    assert sites[11].loop_depth == 1


def test_nesting_is_counted_rather_than_flagged(tmp_path):
    """A boolean cannot distinguish linear from quadratic. Two loops deep is the difference
    between N calls and N*M, and that is the whole reason the column is a depth."""
    sites = _by_line(_adapter(tmp_path).index(_repo("in_loop")))
    assert sites[18].loop_depth == 2


def test_a_call_in_a_map_callback_counts_as_a_loop(tmp_path):
    """`.map` is not a loop node, and it is the shape a real N+1 usually takes -- an array of
    ids turned into one vendor call each. Counting only `for` would miss the common case and
    report zero with confidence.
    """
    sites = _by_line(_adapter(tmp_path).index(_repo("in_loop")))
    assert sites[24].loop_depth == 1


def test_the_indexer_tells_the_adapter_which_language_it_indexed(tmp_path):
    """The language axis is worth nothing if the indexer does not use it.

    A vendor whose two SDKs spell mounts differently can only resolve a call site when it is
    told which SDK produced it. This repository has shipped built-but-unwired components more
    than once -- a tier table nothing constructed, a detector nothing ran -- and each time the
    unit tests passed because the component itself was correct. This asserts the call, not the
    component.
    """
    seen: list[tuple[str, str | None]] = []

    class Recording:
        vendor_id = "stripe"
        # The indexer reads the package to bind from here rather than holding a constant, so a
        # stub that declares none is a vendor whose SDK nothing can recognise -- it would bind
        # no client and record no symbol, and this test would pass by proving nothing.
        sdk_bindings = {"typescript": {"package": "stripe"}}

        def operation_for_symbol(self, symbol, *, language=None):
            seen.append((symbol, language))
            return None

        def fetch_changes(self, since):
            return []

    adapter = TypeScriptAdapter(vendor_adapter=Recording())
    list(adapter.index(_repo("simple")))

    assert seen, "the indexer resolved no symbols, so this proves nothing"
    assert {language for _, language in seen} == {"typescript"}

"""Correlating an observed request back to the operation it addressed.

`operation_for_symbol` answers "which operation does this SDK method call". A span has no
symbol -- it has a URL and a method -- so telemetry needs the inverse, and the inverse is
vendor knowledge exactly as much as the forward direction is. Stripe's path templates, its
`/v1` prefix, the fact that an instance path carries the id in a segment rather than a query
parameter: none of that is a fact about APIs, all of it is a fact about Stripe. It lives in
`sync.signals.stripe` and `sync.telemetry` asks for it through a protocol.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core.conformance import check_request_correlator
from sync.core.protocols import RequestCorrelator
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
SPEC = json.loads((FIXTURES / "specs" / "stripe_v2330_shape.json").read_text(encoding="utf-8"))


@pytest.fixture()
def adapter(tmp_path: Path) -> StripeAdapter:
    map_path = tmp_path / "symbols.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    return StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)


def test_the_adapter_satisfies_the_correlator_protocol(adapter):
    """The protocol is what `sync.telemetry` depends on. If the adapter drifts out of it the
    ingest silently correlates nothing, which reads as a customer who does not call Stripe."""
    assert isinstance(adapter, RequestCorrelator)


# --- the inverse map --------------------------------------------------------------


def test_an_instance_path_resolves_through_its_template(adapter):
    """`ch_3MtwBwLkdIwHu7ix28a3tqPa` is an identifier the specification never names. Matching it
    against `/v1/charges/{charge}` is the entire correlation: a table of literal URLs could
    never be built, because there is one per charge that ever existed.
    """
    operation = adapter.operation_for_request("GET", "/v1/charges/ch_3MtwBwLkdIwHu7ix28a3tqPa")

    assert operation is not None
    assert operation.operation_id == "GetChargesCharge"


def test_a_collection_path_resolves_to_the_list_operation(adapter):
    operation = adapter.operation_for_request("GET", "/v1/charges")

    assert operation is not None
    assert operation.operation_id == "GetCharges"


def test_the_method_selects_between_operations_on_one_path(adapter):
    """`/v1/charges` is two operations. Correlating on the path alone would merge a read with a
    write, and the efficiency detector's whole subject is how often each happens."""
    assert adapter.operation_for_request("GET", "/v1/charges").operation_id == "GetCharges"
    assert adapter.operation_for_request("POST", "/v1/charges").operation_id == "PostCharges"


def test_the_method_is_matched_case_insensitively(adapter):
    """The specification keys operations by a lowercase verb; HTTP and every exporter write it
    uppercase. A case-sensitive comparison correlates nothing at all, and nothing at all is
    indistinguishable from a customer who does not use this vendor."""
    assert adapter.operation_for_request("get", "/v1/charges").operation_id == "GetCharges"


def test_a_trailing_slash_does_not_prevent_a_match(adapter):
    assert adapter.operation_for_request("GET", "/v1/charges/").operation_id == "GetCharges"


def test_the_returned_path_is_the_published_template_not_the_request(adapter):
    """What gets stored. The template is Stripe's own published string and carries no customer
    data; the request path carries a charge id. This is the line between the two, and it is
    where it has to be drawn -- before anything reaches a column.
    """
    operation = adapter.operation_for_request("GET", "/v1/charges/ch_3MtwBwLkdIwHu7ix28a3tqPa")

    assert operation.path == "/v1/charges/{charge}"
    assert "ch_3MtwBwLkdIwHu7ix28a3tqPa" not in operation.path


# --- what it refuses to answer ----------------------------------------------------


def test_an_unknown_path_correlates_to_nothing(adapter):
    assert adapter.operation_for_request("GET", "/v1/not_a_resource/x") is None


def test_a_method_the_operation_does_not_support_correlates_to_nothing(adapter):
    """Guessing here would bind a span to an operation the customer never called, and a binding
    that is wrong is worse than a binding that is missing: the missing one is visibly
    unresolved, the wrong one produces a confident finding against the wrong code."""
    assert adapter.operation_for_request("DELETE", "/v1/charges") is None


def test_a_segment_count_mismatch_does_not_match_a_template(adapter):
    """A template segment matches one segment, never a run of them. `{charge}` matching
    `ch_x/refunds` would bind a sub-resource call to its parent operation."""
    assert adapter.operation_for_request("GET", "/v1/charges/ch_x/refunds/re_y") is None


def test_a_template_segment_does_not_match_an_empty_interior_segment(adapter):
    """`/v1//charges` has an empty segment in the middle. A placeholder that matched it would
    let a malformed URL resolve to a real operation, with the empty string standing in for an
    id nobody sent.

    A *trailing* double slash is the other case and is deliberately not this one: `/v1/charges//`
    differs from `/v1/charges/` only by a slash every URL normaliser collapses, and the test
    above requires that form to match. Rejecting one while accepting the other would be a rule
    about spelling rather than about meaning.
    """
    assert adapter.operation_for_request("GET", "/v1//charges") is None


def test_a_path_the_symbol_map_never_covered_correlates_to_nothing(adapter):
    """A nested path such as `/v1/accounts/{account}/bank_accounts/{id}` derives no SDK symbol,
    so `build_symbol_map` never emits it and no call site is ever bound to it. Correlating a
    span to it would produce an observed binding pointing at an operation the index cannot
    reach, which is a finding no remediation could ever locate in source.

    This is the correlation's real ceiling and it is asserted rather than commented: the inverse
    map covers exactly the operations the forward map covers, no more.
    """
    path = "/v1/accounts/acct_1032D82eZvKYlo2C/bank_accounts/ba_1032Q4"

    assert adapter.operation_for_request("GET", path) is None


# --- the boundary that makes the plugin story true --------------------------------


def test_telemetry_never_imports_a_vendor(adapter):
    """`sync.telemetry` receives a correlator; it does not reach for one. The import-boundary
    contract covers `sync.core` and would not catch this, so it is asserted here against the
    module's own imports rather than left to a linter that is not looking.
    """
    import sync.telemetry.ingest as ingest
    import sync.telemetry.otlp as otlp

    for module in (ingest, otlp):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "stripe" not in source.lower(), f"{module.__name__} names a vendor"


# --- the conformance kit, run against the real thing ------------------------------


def test_the_adapter_passes_the_correlator_conformance_kit(adapter):
    """The kit is what an outside author runs, and a kit nobody points at a real implementation
    is a kit whose rules have only ever been read.

    `isinstance` above establishes that the method name exists. This establishes the rest of what
    the protocol's docstring promises and `runtime_checkable` cannot reach: that a live identifier
    does not survive the call, that an unresolvable request answers None rather than raising or
    guessing, that the operation returned is under the method that was asked about, and that the
    same span correlates the same way twice.

    The identifier is the one from `test_an_instance_path_resolves_through_its_template`, so the
    two tests fail together if `build_symbol_map` ever stops emitting `/v1/charges/{charge}` --
    which is a fixture problem, and the kit says so in those words rather than blaming the
    adapter.
    """
    check_request_correlator(
        adapter,
        known_request=("GET", "/v1/charges/ch_3MtwBwLkdIwHu7ix28a3tqPa"),
        identifier="ch_3MtwBwLkdIwHu7ix28a3tqPa",
    )

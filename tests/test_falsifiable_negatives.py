"""Which labelled negatives the detector could have fired on, and why the count has to be printed.

`2026-07-29-frozen-corpus-first-binding-numbers.md` reports binding precision 1.0000 at n=12 and
records a suspicion about it. The suspicion is right and its stated cause is not. The rung on an
unaffected label is a literal written by `generate_pair`, never a measurement, and
`compute_binding_accuracy` reads a label's rung only when the label is affected -- so counting
`unresolved` over the negative set says nothing about what the indexer did with those sites.
Every labelled site, negative included, is a call site the indexer bound to an operation, because
the sites come from `adapter.index` and the adapter yields nothing it could not resolve.

The real cause is the targeting rule: `cli._score_corpus` targets every indexed site on the
changed operation. So a same-operation site is either broken -- and labelled affected -- or a
target the mutation could not attach to. The residue is worse than small. A request-side mutation
attaches exactly where the call passes an object argument, which is exactly where the indexer
records `args_keys`; a response-side mutation attaches exactly where the result is bound in a
declarator, which is exactly where the indexer records `response_fields_read`. **A site the
mutation cannot reach is a site whose field list is empty, and `_deepest_match` over an empty list
returns None for every change there has ever been.** So the unreachable targets cannot be false
positives either, and no choice of repository or specification changes that.

That makes precision a constant over this corpus, and a directional floor on a constant is the
"never fires and provides false assurance" half of the failure `2026-07-27-sync-benchmark-gates.md`
warns about. The floor cannot be added until a negative exists that could have gone the other way.

These tests pin the count that says whether one does. They are pure -- labels, call sites and a
change in, identities out -- so they need no database and no network.
"""

from __future__ import annotations

from sync.benchmark.binding import BindingLabel
from sync.benchmark.score import falsifiable_negatives
from sync.core import CallSite, VendorChange

CHANGE_ID = "vc1"


def _change(kind: str = "request-property-removed", operation: str = "PostCharges") -> VendorChange:
    return VendorChange(
        id=CHANGE_ID, vendor_id="stripe", from_version="v1", to_version="v2",
        kind=kind, operation_id=operation, path_ptr="/v1/charges",
        severity="breaking", source="oasdiff",
        raw={"id": kind, "text": f"removed `amount_details` from {operation}"},
    )


def _site(
    site_id: str,
    operation: str = "PostCharges",
    args_keys: list[str] | None = None,
    response_fields_read: list[str] | None = None,
) -> CallSite:
    return CallSite(
        id=site_id, repo_id="r1", path="src/billing.ts", line=1, col=0,
        vendor_id="stripe", operation_id=operation, symbol="stripe.charges.create",
        args_keys=args_keys or [], response_fields_read=response_fields_read or [],
        sdk_version="18.0.0", content_hash=site_id,
    )


def _label(site_id: str, affected: bool) -> BindingLabel:
    return BindingLabel(call_site_id=site_id, vendor_change_id=CHANGE_ID, affected=affected)


def test_a_negative_on_the_changed_operation_carrying_arguments_is_an_opportunity() -> None:
    """The case the corpus does not have. The detector reaches this site, has a field list to
    test it against, and has to decline -- which is the only shape in which precision can fall."""
    sites = {"s1": _site("s1", args_keys=["amount", "currency"])}

    assert falsifiable_negatives([_label("s1", False)], sites, _change()) == ("s1",)


def test_a_negative_on_another_operation_is_not_an_opportunity() -> None:
    """`call_sites_for_operation` never returns it, so no detector examines it at all. Eighty-three
    of the frozen corpus's ninety-four negatives are this."""
    sites = {"s1": _site("s1", operation="PostRefunds", args_keys=["amount"])}

    assert falsifiable_negatives([_label("s1", False)], sites, _change()) == ()


def test_a_same_operation_negative_with_no_recorded_arguments_is_not_an_opportunity() -> None:
    """`_deepest_match` over an empty list returns None for every change, so this site declines
    before any property of the binder is consulted. The eleven unreachable targets are this."""
    sites = {"s1": _site("s1", args_keys=[])}

    assert falsifiable_negatives([_label("s1", False)], sites, _change()) == ()


def test_the_side_that_is_read_follows_the_change_kind() -> None:
    """A response change is tested against what the site reads and a request change against what
    it passes. Reading the wrong list would count a site as an opportunity on evidence the
    detector never consults for that kind."""
    passes_only = {"s1": _site("s1", args_keys=["amount"])}
    reads_only = {"s1": _site("s1", response_fields_read=["status"])}
    response = _change(kind="response-property-removed")

    assert falsifiable_negatives([_label("s1", False)], passes_only, response) == ()
    assert falsifiable_negatives([_label("s1", False)], reads_only, response) == ("s1",)
    assert falsifiable_negatives([_label("s1", False)], reads_only, _change()) == ()


def test_an_affected_label_is_never_an_opportunity() -> None:
    """A positive is precision's numerator, not a candidate for its false-positive term."""
    sites = {"s1": _site("s1", args_keys=["amount_details"])}

    assert falsifiable_negatives([_label("s1", True)], sites, _change()) == ()


def test_a_kind_that_names_neither_side_counts_every_same_operation_negative() -> None:
    """The detector emits on the operation match alone for a kind it cannot place, so every
    same-operation negative is genuinely at risk and the count must say so rather than reading a
    field list the detector will not consult."""
    sites = {
        "s1": _site("s1", args_keys=[]),
        "s2": _site("s2", operation="PostRefunds"),
    }
    labels = [_label("s1", False), _label("s2", False)]

    assert falsifiable_negatives(labels, sites, _change(kind="api-operation-removed")) == ("s1",)


def test_the_result_is_ordered_so_two_runs_over_one_input_agree() -> None:
    """The corpus is scored twice and the outputs compared byte for byte, so anything derived
    from a set has to be ordered before it is serialised."""
    sites = {name: _site(name, args_keys=["amount"]) for name in ("s3", "s1", "s2")}
    labels = [_label(name, False) for name in ("s3", "s1", "s2")]

    assert falsifiable_negatives(labels, sites, _change()) == ("s1", "s2", "s3")


def test_a_label_naming_a_site_the_index_does_not_hold_is_not_counted() -> None:
    """A displaced label is refused upstream by `DisplacedLabel`; this must not raise on the way
    to that refusal, because the error naming every displaced site is the more useful one."""
    assert falsifiable_negatives([_label("gone", False)], {}, _change()) == ()

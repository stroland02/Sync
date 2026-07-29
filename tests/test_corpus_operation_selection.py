"""Which operations the corpus rule proposes, and on which side's evidence.

The rule took the operations with the most call sites where at least one call passes an object
argument, and then generated both a request pair and a response pair over each. That condition is
request-side, and it decided response coverage too: every response pair the corpus holds is there
because its operation also happened to qualify on the request side.

`virtual-lab-GetProductsId-response-property-removed` is what that cost. Three call sites, all
`client.products.retrieve(cfg.product_id)`, all positional, so `args_keys` is empty at every one
and the operation could never be a candidate however many sites it had. It is the strongest pair
in the corpus -- two labelled positives, a held-back site producing a falsifiable negative, and a
GET, so no request pair competes for the operation -- and it had to be written by hand.

The evidence a pair needs is the field list the detector judges that pair's kind on, which is the
rule `hold_back` already applies one clause later: `args_keys` for a request change and
`response_fields_read` for a response change. Applying it at selection as well is what makes the
two clauses agree, and `_judged_by` is the one place either asks.

**The request-side condition is not relaxed.** A request-property mutation needs a call passing an
object argument to mutate; an operation qualifying only on response evidence must not acquire a
request pair, because that pair's every target would be unreachable. Qualification is per side, not
on either side pooled.
"""

from __future__ import annotations

from scripts.build_corpus_specs import operations_for
from sync.core import CallSite

REQUEST = "request-property-removed"
RESPONSE = "response-property-removed"


def _site(
    site_id: str, operation: str, *, args_keys=("amount",), reads=(),
) -> CallSite:
    return CallSite(
        id=site_id, repo_id="r1", path="src/billing.ts", line=6, col=23, vendor_id="stripe",
        operation_id=operation, symbol="stripe.charges.create", args_keys=list(args_keys),
        response_fields_read=list(reads), sdk_version="18.0.0", content_hash=f"h{site_id}",
    )


def _by_operation(*groups: tuple[str, list[CallSite]]) -> dict[str, list[CallSite]]:
    return dict(groups)


# --- the side each kind is qualified on ---------------------------------------------


def test_an_operation_passing_an_object_argument_is_proposed_for_a_request_pair():
    """The condition that was already there, unchanged. A request-property mutation writes a
    property into an argument object, so a call passing one is what it needs."""
    by_operation = _by_operation(
        ("PostCharges", [_site("a", "PostCharges")]),
    )

    assert [name for name, _ in operations_for(by_operation, REQUEST)] == ["PostCharges"]


def test_an_operation_reading_a_response_field_is_proposed_for_a_response_pair():
    """The condition that was missing. `client.products.retrieve(id)` passes no object argument
    and binds a result the repository reads fields off, which is everything a response pair
    needs and nothing the old rule could see."""
    by_operation = _by_operation(
        ("GetProductsId", [_site("a", "GetProductsId", args_keys=(), reads=("tax_code",))]),
    )

    assert [name for name, _ in operations_for(by_operation, RESPONSE)] == ["GetProductsId"]


def test_an_operation_reading_a_response_field_is_not_proposed_for_a_request_pair():
    """The half that must not be relaxed with the other. A request pair over an operation whose
    calls pass no object argument has nowhere to write the mutation: every target comes back
    unreachable, the pair contributes no positive, and it still moves `pairs_scored` and
    therefore its floor.
    """
    by_operation = _by_operation(
        ("GetProductsId", [_site("a", "GetProductsId", args_keys=(), reads=("tax_code",))]),
    )

    assert operations_for(by_operation, REQUEST) == []


def test_an_operation_passing_an_object_argument_is_not_proposed_for_a_response_pair():
    """The mirror, and the reason qualification is per side rather than on either side pooled.
    A site passing a rich argument object and reading nothing off its result is a negative a
    response change can never fire on -- which is the sentence `hold_back` already carries about
    the same call site one clause later.
    """
    by_operation = _by_operation(
        ("PostCharges", [_site("a", "PostCharges")]),
    )

    assert operations_for(by_operation, RESPONSE) == []


def test_an_operation_with_neither_field_list_is_proposed_for_neither_kind():
    """A call passing nothing and reading nothing is a site the detector declines against every
    change there has ever been, on either side."""
    by_operation = _by_operation(
        ("GetBalance", [_site("a", "GetBalance", args_keys=(), reads=())]),
    )

    assert operations_for(by_operation, REQUEST) == []
    assert operations_for(by_operation, RESPONSE) == []


def test_one_site_carrying_the_evidence_qualifies_the_operation():
    """`any`, not `all`. An operation whose calls are written several ways is one the mutation
    can attach to at the sites that carry the evidence, and holding it to every site would
    exclude an operation for having one convenience wrapper."""
    by_operation = _by_operation(
        ("GetProductsId", [
            _site("a", "GetProductsId", args_keys=(), reads=()),
            _site("b", "GetProductsId", args_keys=(), reads=("tax_code",)),
        ]),
    )

    assert [name for name, _ in operations_for(by_operation, RESPONSE)] == ["GetProductsId"]


# --- the ranking, which decides what the two slots hold -------------------------------


def test_operations_are_ranked_by_call_site_count_and_ties_by_operation_id():
    """Unchanged, and asserted here because the ranking now runs over a different candidate set
    per kind. Most sites first, because a pair over one site has the least room to hide a miss;
    ties by id ascending, so the choice is not the dictionary's insertion order."""
    by_operation = _by_operation(
        ("PostRefunds", [_site("a", "PostRefunds")]),
        ("PostCharges", [_site("b", "PostCharges")]),
        ("PostPaymentIntents", [_site("c", "PostPaymentIntents"),
                                _site("d", "PostPaymentIntents")]),
    )

    assert [name for name, _ in operations_for(by_operation, REQUEST)] == [
        "PostPaymentIntents", "PostCharges",
    ]


def test_at_most_two_operations_are_proposed_per_kind():
    """The cap is per kind rather than per repository, which is the shape change this makes. Two
    request operations and two response operations is four pairs, the same ceiling the rule had
    when both kinds were taken over one pair of operations."""
    by_operation = _by_operation(
        ("PostCharges", [_site("a", "PostCharges")]),
        ("PostRefunds", [_site("b", "PostRefunds")]),
        ("PostPayouts", [_site("c", "PostPayouts")]),
    )

    assert len(operations_for(by_operation, REQUEST)) == 2


def test_an_operation_the_symbol_map_did_not_resolve_is_never_proposed():
    """A call site the vendor adapter answered no operation for is grouped under a falsy key.
    Proposing it would name an operation the specification cannot resolve and the change cannot
    address."""
    by_operation = _by_operation(
        ("", [_site("a", "", reads=("id",))]),
    )

    assert operations_for(by_operation, REQUEST) == []
    assert operations_for(by_operation, RESPONSE) == []


# --- the shape the hand-written pair had, end to end through the rule -----------------


def test_the_rule_now_proposes_the_pair_that_had_to_be_written_by_hand():
    """`virtual-lab` in miniature, and the closing condition of the task that changed this.

    `GetCustomers` and `GetSubscriptions` pass `params={...}` and read nothing off their results;
    `GetProductsId` passes a positional id and reads fields off two of its three. Under the old
    rule the first two took both slots and both kinds, and `GetProductsId` was unreachable. The
    response slots now go to the operation that can carry a response pair, and the request slots
    still go to the operations that can carry a request one.
    """
    by_operation = _by_operation(
        ("GetCustomers", [_site(f"c{n}", "GetCustomers", args_keys=("params",)) for n in "123"]),
        ("GetSubscriptions",
         [_site(f"s{n}", "GetSubscriptions", args_keys=("params",)) for n in "123"]),
        ("GetProductsId", [
            _site("p1", "GetProductsId", args_keys=(), reads=("id", "name", "tax_code")),
            _site("p2", "GetProductsId", args_keys=(), reads=("id", "tax_code")),
            _site("p3", "GetProductsId", args_keys=(), reads=()),
        ]),
    )

    assert [name for name, _ in operations_for(by_operation, RESPONSE)] == ["GetProductsId"]
    assert [name for name, _ in operations_for(by_operation, REQUEST)] == [
        "GetCustomers", "GetSubscriptions",
    ]

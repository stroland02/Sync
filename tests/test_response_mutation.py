"""The response half of the corpus, and the two reasons it measured nothing.

`2026-07-29-frozen-corpus-first-binding-numbers.md` reports binding recall 1.0000 at n=12 over
twelve labelled positives that are all request-side. Every `response-property-removed` pair scored
zero affected and zero findings, so the response axis contributed nothing to either number, and
two further pairs were refused outright as `displaced-label`.

Two independent causes, and only one of them is the one that was diagnosed.

**The guard inserted lines.** A response mutation wrote a three-line `if` block after the statement
binding the call's result, and `upsert_call_site` keys a call site's identity on line and column --
so every call below it in that file became a different row and its label addressed nothing. That
is what refused two pairs entirely, and it would have refused more as soon as the other cause was
fixed. A guard that occupies no new lines removes the interaction rather than trading it, which is
why it is preferred here over changing what identity is keyed on: identity is `sync.graph`'s to
define, the corpus is a consumer of it, and a benchmark that needed the production key changed to
score itself would be measuring a pipeline nobody runs.

**`_result_binding` read only declarations.** `intent = await stripe.paymentIntents.create(...)`
binds the result to a name the guard could read, and was refused because the name is bound by an
assignment rather than by `const` or `let`. Four of the eleven unreachable targets in the recorded
run are exactly this.

The other seven are not a generator limitation and must not be made to look like one. Five discard
the result -- `await stripe.paymentIntents.create({...});` with nothing bound -- and two forward it
out of the function with `return`. **A call that never reads the response does not depend on a
response property, so `unaffected` is the correct label rather than a missed positive.** Turning
either class into a positive would mean editing the tree into a shape nobody wrote, and the label
would then describe the generator's restructuring rather than a dependency the vendor's change
breaks. These tests pin that they stay unreachable.
"""

from __future__ import annotations

from pathlib import Path

from sync.benchmark.mutate import depends_on_change, generate_pair
from sync.core import CallSite, VendorChange

FIXTURE = Path(__file__).parent / "fixtures" / "mutation_response"
FIELD = "amount_details"


def _sources() -> dict[str, str]:
    return {
        path.relative_to(FIXTURE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(FIXTURE.rglob("*.ts"))
    }


def _change(kind: str = "response-property-removed") -> VendorChange:
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind=kind, operation_id="PostPaymentIntents", path_ptr="/v1/payment_intents",
        severity="breaking", source="oasdiff",
        raw={"id": kind,
             "text": f"removed the optional property `{FIELD}` from the response"},
    )


def _site(sources: dict[str, str], site_id: str, occurrence: int) -> CallSite:
    """Addressed by position, computed from the fixture so an edit cannot strand a test."""
    source = sources["src/orders.ts"]
    offset = -1
    for _ in range(occurrence + 1):
        offset = source.index("stripe.paymentIntents.create(", offset + 1)
    return CallSite(
        id=site_id, repo_id="fixture", path="src/orders.ts",
        line=source.count("\n", 0, offset) + 1,
        col=offset - (source.rfind("\n", 0, offset) + 1),
        vendor_id="stripe", operation_id="PostPaymentIntents",
        symbol="stripe.paymentIntents.create", sdk_version="18.0.0", content_hash="h",
    )


def _all_sites(sources: dict[str, str]) -> list[CallSite]:
    """One call per binding form, in one file, which is what makes displacement testable."""
    return [
        _site(sources, "cs-declared", 0),
        _site(sources, "cs-assigned", 1),
        _site(sources, "cs-forwarded", 2),
        _site(sources, "cs-ignored", 3),
    ]


def _labels(pair) -> dict[str, bool]:
    return {label.call_site_id: label.affected for label in pair.labels}


# --- the guard must not move anything ---------------------------------------------


def test_a_response_mutation_inserts_no_new_line() -> None:
    """The whole displaced-label interaction in one assertion. `upsert_call_site` keys identity
    on line and column, so a mutation that adds a line renames every call site below it in the
    file and its label addresses a row the mutated tree no longer holds."""
    sources = _sources()
    pair = generate_pair(sources, _change(), _all_sites(sources), targets=["cs-declared"])

    before = sources["src/orders.ts"]
    after = pair.sources["src/orders.ts"]

    assert after != before
    assert after.count("\n") == before.count("\n")


def test_every_call_below_the_mutation_keeps_its_line_and_column() -> None:
    """The property the line count is a proxy for, asserted directly against the positions the
    indexer records. A guard on the first call must leave the other three addressable."""
    sources = _sources()
    pair = generate_pair(sources, _change(), _all_sites(sources), targets=["cs-declared"])

    after = _all_sites(pair.sources)
    assert [(s.line, s.col) for s in after] == [(s.line, s.col) for s in _all_sites(sources)]


def test_two_targets_in_one_file_are_both_broken_and_neither_displaces_the_other() -> None:
    """`furever-GetCharges-response-property-removed` and its sibling were refused entirely for
    this, and a file with several calls could not carry a response-side pair at all."""
    sources = _sources()
    pair = generate_pair(sources, _change(), _all_sites(sources),
                         targets=["cs-declared", "cs-assigned"])

    assert pair.unreachable == ()
    assert _labels(pair) == {
        "cs-declared": True, "cs-assigned": True,
        "cs-forwarded": False, "cs-ignored": False,
    }
    after = _all_sites(pair.sources)
    assert [(s.line, s.col) for s in after] == [(s.line, s.col) for s in _all_sites(sources)]


# --- which binding forms the guard can attach to ----------------------------------


def test_a_result_bound_by_a_plain_assignment_is_reachable() -> None:
    """Four of the eleven unreachable targets in the recorded run are this form -- `furever`
    writes `paymentIntent = await ...` and `turbo` writes `intentOrCheckout = await ...` into a
    variable declared earlier. The name is there to read the field off; only the statement kind
    differed."""
    sources = _sources()
    change = _change()
    pair = generate_pair(sources, change, _all_sites(sources), targets=["cs-assigned"])

    assert pair.unreachable == ()
    assert _labels(pair)["cs-assigned"] is True


def test_the_mutated_tree_really_carries_the_dependency_the_label_claims() -> None:
    """`generate_pair` labels from the edit it made and `depends_on_change` reads the fact back
    out of the source. Two independent derivations, so agreement is worth asserting and
    disagreement is a generator bug rather than a score."""
    sources = _sources()
    change = _change()
    sites = {site.id: site for site in _all_sites(sources)}
    pair = generate_pair(sources, change, list(sites.values()),
                         targets=["cs-declared", "cs-assigned"])

    assert depends_on_change(pair.sources, change, sites["cs-declared"]) is True
    assert depends_on_change(pair.sources, change, sites["cs-assigned"]) is True
    assert depends_on_change(pair.sources, change, sites["cs-ignored"]) is False


def test_a_discarded_result_stays_unreachable_because_it_depends_on_nothing() -> None:
    """Five of the eleven. A call whose response nobody binds cannot be broken by a response
    property being removed, so `unaffected` is the correct answer and not a missed positive.
    Manufacturing one here would put a label on a dependency the tree does not have."""
    sources = _sources()
    pair = generate_pair(sources, _change(), _all_sites(sources), targets=["cs-ignored"])

    assert pair.unreachable == ("cs-ignored",)
    assert _labels(pair)["cs-ignored"] is False
    assert pair.sources["src/orders.ts"] == sources["src/orders.ts"]


def test_a_forwarded_result_stays_unreachable() -> None:
    """Two of the eleven -- `return stripe.paymentMethods.list({...})`. The value escapes the
    function and whatever reads the field is somewhere this mutation cannot see, so there is no
    local name to guard. Binding it to one first would be a restructuring rather than an
    insertion, and the label would describe the restructuring."""
    sources = _sources()
    pair = generate_pair(sources, _change(), _all_sites(sources), targets=["cs-forwarded"])

    assert pair.unreachable == ("cs-forwarded",)
    assert _labels(pair)["cs-forwarded"] is False
    assert pair.sources["src/orders.ts"] == sources["src/orders.ts"]


def test_the_mutated_source_still_parses_as_the_statement_it_replaced() -> None:
    """A single-line guard is appended to the binding statement, so it has to be separated from
    it. A statement terminated by newline rather than by `;` would otherwise be joined to the
    guard into one expression, and the tree would stop compiling for a reason nothing reports."""
    sources = _sources()
    sources["src/orders.ts"] = sources["src/orders.ts"].replace(
        "const intent = await stripe.paymentIntents.create({ amount, currency: 'usd' });",
        "const intent = await stripe.paymentIntents.create({ amount, currency: 'usd' })",
    )
    change = _change()
    sites = {site.id: site for site in _all_sites(sources)}
    pair = generate_pair(sources, change, list(sites.values()), targets=["cs-declared"])

    mutated = pair.sources["src/orders.ts"]
    assert "})" + "; if (intent." in mutated
    assert depends_on_change(pair.sources, change, sites["cs-declared"]) is True

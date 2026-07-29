"""A corpus specification naming call sites held out of the mutation, and what that buys.

Binding precision over the frozen corpus reads 1.0000 and could not read anything else:
`docs/superpowers/reports/2026-07-29-precision-has-no-negative-to-fail-on.md` measured zero
labelled negatives the detector could have fired on, in every scored pair. The cause was that
`_score_corpus` targeted every indexed call site on the changed operation, so a same-operation
site was either broken -- and labelled affected -- or a target the mutation could not attach to,
and neither class can produce a false positive.

A site held out of `targets` is never edited, so nothing writes the changed dependency into it,
so it is unaffected by construction rather than by anyone's judgement. That is the negative
precision needs, and it is why the hold-back is declared by the specification rather than
derived by the harness: which sites a corpus breaks is a distribution choice, and
`_score_corpus` already refuses to make one silently.

`tests/test_mutation_pairs.py::test_a_site_that_already_depends_on_the_changed_field_is_refused`
is what keeps the label honest and is not repeated here. `generate_pair` walks every site in the
tree -- not only its targets -- and raises when one already carries the changed field, so a
held-back site that genuinely reads the changed property refuses the pair rather than joining
the negative set.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.build_corpus_specs import hold_back
from sync.cli import _corpus_targets, _score_corpus
from sync.core import CallSite, VendorChange


def _site(
    site_id: str, path: str, line: int, col: int, operation: str = "PostCharges",
    args_keys=("amount",), reads=(),
) -> CallSite:
    return CallSite(
        id=site_id, repo_id="r1", path=path, line=line, col=col, vendor_id="stripe",
        operation_id=operation, symbol="stripe.charges.create", args_keys=list(args_keys),
        response_fields_read=list(reads), sdk_version="18.0.0", content_hash=f"h{site_id}",
    )


def _change(operation: str = "PostCharges") -> VendorChange:
    return VendorChange(
        vendor_id="stripe", from_version="v1", to_version="v2",
        kind="request-property-removed", operation_id=operation, path_ptr="/v1/charges",
        severity="breaking", source="oasdiff",
        raw={"id": "request-property-removed", "text": "removed `receipt_email` from PostCharges"},
    )


SPEC = Path("benchmark/corpus/pairs/example.yaml")


# --- what the specification decides ------------------------------------------------


def test_a_specification_holding_nothing_back_targets_every_site_on_the_operation():
    """The behaviour every specification written before this key had, unchanged. A corpus that
    starts holding sites back by default would move recall's denominator on twelve pairs without
    any of them saying so."""
    sites = [_site("a", "src/billing.ts", 6, 23), _site("b", "src/billing.ts", 11, 23)]

    assert _corpus_targets(SPEC, [], sites, _change()) == ["a", "b"]


def test_a_site_the_specification_holds_back_is_not_a_target():
    """The whole point. An untargeted site is never edited, so the tree never carries the changed
    dependency at it -- which makes it a labelled negative the detector reaches and can be wrong
    about, rather than one it was never asked."""
    sites = [_site("a", "src/billing.ts", 6, 23), _site("b", "src/billing.ts", 11, 23)]

    targets = _corpus_targets(
        SPEC, [{"path": "src/billing.ts", "line": 6, "col": 23}], sites, _change()
    )

    assert targets == ["b"]


def test_a_site_on_another_operation_is_never_a_target():
    """Unchanged and asserted because the hold-back now filters the same list. A change to one
    operation says nothing about a call to another, and targeting one would break a site the
    label then has to call affected."""
    sites = [_site("a", "src/billing.ts", 6, 23),
             _site("b", "src/billing.ts", 11, 23, operation="GetChargesCharge")]

    assert _corpus_targets(SPEC, [], sites, _change()) == ["a"]


# --- a specification that does not describe this checkout ---------------------------


def test_holding_back_a_position_the_checkout_does_not_have_is_refused_by_name():
    """The failure this has to be loud about. A specification pinned to a commit whose tree has
    moved would otherwise hold nothing back, target every site as before, and report a corpus
    with a negative in it that has none -- the exact wrong answer the number is being fixed to
    stop telling."""
    sites = [_site("a", "src/billing.ts", 6, 23), _site("b", "src/billing.ts", 11, 23)]

    with pytest.raises(KeyError) as raised:
        _corpus_targets(SPEC, [{"path": "src/billing.ts", "line": 7, "col": 23}], sites, _change())

    assert "src/billing.ts:7:23" in str(raised.value)
    assert SPEC.name in str(raised.value)


def test_holding_back_a_site_on_another_operation_is_refused():
    """A site the change does not reach is already a negative nothing could fire on, so holding
    it back buys no candidate and costs no positive. Silently accepted it reads as a corpus that
    declared a witness when it declared nothing."""
    sites = [_site("a", "src/billing.ts", 6, 23),
             _site("b", "src/billing.ts", 11, 23, operation="GetChargesCharge")]

    with pytest.raises(KeyError, match="src/billing.ts:11:23"):
        _corpus_targets(SPEC, [{"path": "src/billing.ts", "line": 11, "col": 23}], sites, _change())


def test_a_hold_back_entry_that_names_no_position_is_refused():
    """Three keys, all required. An entry missing one addresses no call site at all, and the
    resolution below would report it as a position the checkout does not have -- a true sentence
    about the wrong problem."""
    sites = [_site("a", "src/billing.ts", 6, 23)]

    with pytest.raises(KeyError, match="line"):
        _corpus_targets(SPEC, [{"path": "src/billing.ts", "col": 23}], sites, _change())


def test_holding_back_every_site_on_the_operation_is_refused():
    """A pair with no target is a tree nothing broke: every site labelled unaffected, no finding
    to judge, and a run that reads as flawless because it measured nothing. The specification
    asked for that, so the specification is what is named."""
    sites = [_site("a", "src/billing.ts", 6, 23)]

    with pytest.raises(KeyError, match="every indexed call site"):
        _corpus_targets(SPEC, [{"path": "src/billing.ts", "line": 6, "col": 23}], sites, _change())


def test_a_change_no_indexed_call_site_reaches_is_still_refused_as_an_empty_corpus():
    """Distinct from the one above and it has to stay distinct. No site on the operation is a
    property of the repository; every site held back is a property of the specification, and a
    reader told the wrong one looks in the wrong place."""
    sites = [_site("a", "src/billing.ts", 6, 23, operation="GetChargesCharge")]

    with pytest.raises(LookupError) as raised:
        _corpus_targets(SPEC, [], sites, _change())

    assert "no indexed call site reaches PostCharges" in str(raised.value)


# --- the rule that chose them, which is executable rather than argued -----------------

# The sites below are synthetic: their paths name files nothing ever wrote. `hold_back` reads
# this root only to ask whether a candidate shares an enclosing scope and a result name with a
# site it still targets, and a path it cannot read answers "not bound" -- so that clause cannot
# apply here and these tests exercise the selection rule alone. That separation is deliberate:
# the scope clause has its own file, `tests/test_hold_back_scope.py`, where the sources exist.
NO_CHECKOUT = Path(__file__).parent / "fixtures" / "no-checkout-on-disk"


def test_the_rule_holds_back_the_first_call_site_on_the_operation_by_position():
    """First rather than any other, and for a reason rather than a preference. Every insertion
    the generator makes lands at or after the call it breaks, and `upsert_call_site` keys a call
    site's identity on its position -- so the earliest site is the only one guaranteed to still
    be where the specification says once its siblings have been mutated."""
    sites = [
        _site("b", "src/billing.ts", 11, 23),
        _site("a", "src/billing.ts", 6, 23),
        _site("c", "src/refunds.ts", 4, 10),
    ]

    assert hold_back(sites, "request-property-removed", NO_CHECKOUT) == [
        {"path": "src/billing.ts", "line": 6, "col": 23}
    ]


def test_the_rule_holds_one_site_back_and_never_two():
    """Every held-back site is a site recall no longer measures, and recall at n=12 is the only
    genuine quality measurement this benchmark has. One negative per pair is what makes precision
    falsifiable; a second buys nothing and costs another positive."""
    sites = [_site(name, "src/billing.ts", line, 23)
             for name, line in (("a", 6), ("b", 11), ("c", 16), ("d", 21))]

    assert len(hold_back(sites, "request-property-removed", NO_CHECKOUT)) == 1


def test_an_operation_with_one_indexed_call_site_holds_nothing_back():
    """Holding back the only site empties the target list, and a pair with no target is refused
    outright -- so the whole specification would leave the corpus rather than contribute a
    negative to it."""
    assert hold_back([_site("a", "src/billing.ts", 6, 23)], "request-property-removed", NO_CHECKOUT) == []


def test_a_first_site_passing_no_arguments_holds_nothing_back():
    """`_deepest_match` over an empty list returns None for every change there has ever been, so
    such a site is a negative the detector was never asked. Holding it back would cost a positive
    and buy no candidate."""
    sites = [_site("a", "src/billing.ts", 6, 23, args_keys=()),
             _site("b", "src/billing.ts", 11, 23)]

    assert hold_back(sites, "request-property-removed", NO_CHECKOUT) == []


def test_a_response_change_reads_the_response_field_list_rather_than_the_arguments():
    """The side the detector judges on follows the kind, so the side the rule tests has to as
    well. A site passing a rich argument object and reading nothing off its result is a negative
    a response change can never fire on."""
    passes_only = [_site("a", "src/billing.ts", 6, 23), _site("b", "src/billing.ts", 11, 23)]
    reads_too = [_site("a", "src/billing.ts", 6, 23, reads=("id",)),
                 _site("b", "src/billing.ts", 11, 23)]

    assert hold_back(passes_only, "response-property-removed", NO_CHECKOUT) == []
    assert hold_back(reads_too, "response-property-removed", NO_CHECKOUT) == [
        {"path": "src/billing.ts", "line": 6, "col": 23}
    ]


# --- end to end, through the command's own scorer -----------------------------------

SPEC_JSON = json.dumps({"openapi": "3.0.0", "info": {"title": "t", "version": "1"}, "paths": {}})

# Two calls to one operation, so one can be broken and one held back. Their argument objects
# differ, because two identical calls would let a positional bug pass by naming either.
TWO_CHARGES_TS = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY!);

export async function chargeInEuros(amount: number) {
  const charge = await stripe.charges.create({ amount, currency: 'eur' });
  return charge.id;
}

export async function chargeInDollars(amount: number, customer: string) {
  const charge = await stripe.charges.create({ amount, currency: 'usd', customer });
  return charge.id;
}
"""

HELD_BACK = {"path": "src/billing.ts", "line": 6, "col": 23}


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    """A pair specification holding one of two same-operation call sites back."""
    checkout = tmp_path / "checkout"
    (checkout / "src").mkdir(parents=True)
    (checkout / "package.json").write_text(
        json.dumps({"dependencies": {"stripe": "^18.0.0"}}), encoding="utf-8"
    )
    (checkout / "src" / "billing.ts").write_text(TWO_CHARGES_TS, encoding="utf-8")

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "symbols.json").write_text(
        json.dumps({
            "stripe.charges.create": {
                "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges"
            },
        }),
        encoding="utf-8",
    )
    for version in ("2026-05-01", "2026-11-01"):
        (cache / f"{version}.json").write_text(SPEC_JSON, encoding="utf-8")

    spec = tmp_path / "corpus.yaml"
    spec.write_text(
        yaml.safe_dump({
            "repo": str(checkout),
            "vendor": "stripe",
            "cache": str(cache),
            "from_version": "2026-05-01",
            "to_version": "2026-11-01",
            "change": {
                "kind": "request-property-removed",
                "operation": "PostCharges",
                "field": "receipt_email",
            },
            "hold_back": [HELD_BACK],
        }),
        encoding="utf-8",
    )
    return spec


@pytest.fixture()
def score_dsn() -> str:
    """A database of its own, because scoring truncates the graph it scores in."""
    import os

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    parts = conninfo_to_dict(os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync"))
    name = f"{parts['dbname']}_hold_back"
    admin = make_conninfo(**{**parts, "dbname": "postgres"})
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return make_conninfo(**{**parts, "dbname": name})


def test_a_held_back_site_is_scored_as_a_negative_the_detector_could_have_fired_on(
    corpus, score_dsn
):
    """The join this whole change exists for, driven through the scorer the command runs.

    Two assertions rather than one: the held-back site has to be labelled unaffected, which is
    what makes a finding on it a false positive, and it has to survive `falsifiable_negatives` --
    a negative on another operation or with no argument list is one the detector was never
    asked, and counting it would report a coverage the corpus does not have.
    """
    scored = _score_corpus(corpus, score_dsn)

    assert scored.affected_sites == 1
    assert len(scored.falsifiable_negatives) == 1

    held = scored.falsifiable_negatives[0]
    assert not next(label for label in scored.labels if label.call_site_id == held).affected


def test_a_corpus_holding_nothing_back_has_no_negative_to_fail_on(corpus, score_dsn, tmp_path):
    """The measured before-state, pinned so the fix cannot be undone silently. The same checkout
    with the same change scores both call sites affected and offers precision nothing to be
    wrong about."""
    spec = yaml.safe_load(corpus.read_text(encoding="utf-8"))
    del spec["hold_back"]
    unheld = tmp_path / "unheld.yaml"
    unheld.write_text(yaml.safe_dump(spec), encoding="utf-8")

    scored = _score_corpus(unheld, score_dsn)

    assert scored.affected_sites == 2
    assert scored.falsifiable_negatives == ()

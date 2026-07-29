"""A held-back site must not share a result name and a scope with a site still targeted.

`hold_back` picks one same-operation call site the mutation deliberately does not touch, so
precision has a negative it could be wrong about. Without one it is computed over zero candidates
and gates a constant.

The rule had no clause about where the held-back site sits relative to the ones still targeted,
and for a response change that matters. The mutation writes a guard reading a field off the
result at the targeted site; `_response_fields` collects reads rooted at the result name **within
the enclosing function**. So when two assignments in one function bind the same name from the same
SDK call, that read is credited to both — including the held-back one. The held-back site then
genuinely does carry the removed property, and calling it a negative is a false label.

B50 measured it rather than reasoning about it. `furever`'s
`app/api/setup_accounts/create_charges/route.ts` declares `let paymentIntent;` once and assigns it
from `stripe.paymentIntents.create` at both line 104 and line 154; holding back 104 while
targeting 154 produced binding precision 0.9615 over n=26, and the single false positive was the
held-back site itself.

**The binder is not wrong here and is not what this fixes.** It cannot tell which of two
assignments produced the value being read — that is data flow, and tree-sitter does not do data
flow. Crediting both is the conservative direction, which is the correct direction for a tool
whose expensive failure is a missed break. What was wrong is a corpus that held back a site the
binder was always going to reach.

The two cases below are the ones that make the clause legible rather than arbitrary: it must
refuse `furever`'s shape and still accept `turbo`'s, whose two sites live in different files. A
clause refusing every hold-back would be exactly as wrong as one refusing none — it would take
falsifiable negatives to zero and put the precision floor back to gating a constant. The last two
tests are the discriminators that stop it collapsing into "same file" or "same name".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from build_corpus_specs import hold_back  # noqa: E402

from sync.core import CallSite  # noqa: E402

RESPONSE = "response-property-removed"

SHARED_SCOPE = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.KEY!);

export async function seed() {
  let paymentIntent;
  paymentIntent = await stripe.paymentIntents.create({ amount: 1 });
  paymentIntent = await stripe.paymentIntents.create({ amount: 2 });
  return paymentIntent.status;
}
"""

SEPARATE_SCOPES = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.KEY!);

export async function first() {
  let intentOrCheckout;
  intentOrCheckout = await stripe.paymentIntents.create({ amount: 1 });
  return intentOrCheckout.status;
}

export async function second() {
  let intentOrCheckout;
  intentOrCheckout = await stripe.paymentIntents.create({ amount: 2 });
  return intentOrCheckout.status;
}
"""

DISTINCT_NAMES = """import Stripe from 'stripe';

const stripe = new Stripe(process.env.KEY!);

export async function seed() {
  const first = await stripe.paymentIntents.create({ amount: 1 });
  const second = await stripe.paymentIntents.create({ amount: 2 });
  return [first.status, second.status];
}
"""


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _sites(root: Path, files: dict[str, str]) -> list[CallSite]:
    """Every `stripe.paymentIntents.create` in the tree, addressed as the indexer addresses it."""
    needle = "stripe.paymentIntents.create"
    sites = []
    for relative, text in files.items():
        offset = -1
        while True:
            offset = text.find(needle, offset + 1)
            if offset < 0:
                break
            sites.append(CallSite(
                repo_id="fixture", path=relative,
                line=text.count("\n", 0, offset) + 1,
                col=offset - (text.rfind("\n", 0, offset) + 1),
                vendor_id="stripe", operation_id="PostPaymentIntents",
                symbol="stripe.paymentIntents.create",
                response_fields_read=["status"], sdk_version="18.0.0", content_hash="h",
            ))
    return sorted(sites, key=lambda s: (s.path, s.line, s.col))


@pytest.fixture()
def tree(tmp_path):
    def build(files: dict[str, str]):
        _write(tmp_path, files)
        return _sites(tmp_path, files), tmp_path

    return build


def test_a_site_sharing_a_scope_and_a_name_with_a_target_is_refused(tree) -> None:
    """`furever`'s shape. Holding back the first assignment while targeting the second credits
    the second's guard to both, so the held-back site is not a negative at all."""
    files = {"app/api/setup_accounts/create_charges/route.ts": SHARED_SCOPE}
    sites, root = tree(files)

    assert len(sites) == 2
    assert hold_back(sites, RESPONSE, root) == []


def test_sites_in_different_files_are_still_held_back(tree) -> None:
    """`turbo`'s shape, and the half that stops this clause refusing everything. Two files share
    no enclosing function, nothing is cross-credited, and the hold-back is sound."""
    files = {
        "src/routes/arnsPurchaseQuote.ts": SEPARATE_SCOPES.split("export async function second")[0],
        "src/routes/topUp.ts": SEPARATE_SCOPES,
    }
    sites, root = tree(files)

    held = hold_back(sites, RESPONSE, root)

    assert held == [{"path": "src/routes/arnsPurchaseQuote.ts", "line": 7, "col": 27}]


def test_two_functions_in_one_file_are_still_held_back(tree) -> None:
    """The discriminator against reading the rule as "same file". `_response_fields` scopes to the
    enclosing function, so two functions in one file cross-credit nothing even when they bind the
    same name — which is exactly what `SEPARATE_SCOPES` does."""
    files = {"src/routes/both.ts": SEPARATE_SCOPES}
    sites, root = tree(files)

    assert len(sites) == 2
    assert hold_back(sites, RESPONSE, root) != []


def test_one_scope_with_two_names_is_still_held_back(tree) -> None:
    """The discriminator against reading it as "same scope". A guard on `second` reads
    `second.status`, which is rooted at a name the held-back site never bound."""
    files = {"src/routes/named.ts": DISTINCT_NAMES}
    sites, root = tree(files)

    assert len(sites) == 2
    assert hold_back(sites, RESPONSE, root) != []


def test_a_request_change_is_unaffected(tree) -> None:
    """`args_keys` come from the call's own argument list and no scope is walked, so nothing is
    cross-credited on the request side. Applying the clause there would refuse sound hold-backs
    and take falsifiable negatives down with them."""
    files = {"app/api/setup_accounts/create_charges/route.ts": SHARED_SCOPE}
    sites, root = tree(files)
    for site in sites:
        site.args_keys = ["amount"]

    assert hold_back(sites, "request-property-removed", root) != []

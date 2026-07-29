# Python binding accuracy cannot be measured yet, and the reason is three binder limitations

B37 set out to pin at least one Python repository into the frozen corpus so binding precision and
recall would describe the Python indexer as well as the TypeScript one. **No repository was
pinned and no corpus number moved.** Seventeen candidate repositories were measured with the real
`PythonAdapter` against the real symbol map, and between them they yield **one** indexable call
site in a repository that is pinnable.

That is a finding about the binder rather than about the search. Three limitations compose, and
each is measured below rather than argued. None of them was fixed here: `src/sync/index/` is
outside this task's files, and the standing rule on this build is that a worker who changes both
the corpus and the binder has destroyed the evidence.

## What the corpus needed and did not get

Nothing in `benchmark/corpus/` changed. `repositories.yaml` still pins four TypeScript
repositories, `pairs/` still holds twelve specifications, and `scripts/gate_corpus.py` still
records `pairs_scored` at 12 with both rates at 1.0000 over n=16. **No floor was restated, because
no denominator moved.** The gate is green for the same reason it was this morning.

## Limitation 1 — half the symbol map cannot be spelled in Python

The symbol map is built from Stripe's **TypeScript** SDK document, so it spells multi-word
resources in camelCase. The Python SDK spells them with underscores.

```
total symbols 179 | resource has a capital (TypeScript-only spelling) 93 | all-lowercase 86
TypeScript-only examples: stripe.accountLinks.create, stripe.applicationFees.list,
                          stripe.balanceSettings.retrieve, ...
```

**93 of 179 symbols are unreachable from Python at any call site whatsoever.** Among them is
`paymentIntents`, which is the single most-used modern Stripe resource and the operation eight of
the twelve existing corpus pairs are built on.

The 24 resources spelled identically in both SDKs are the whole of what Python can currently
reach:

```
account, accounts, balance, charges, coupons, customers, disputes, events, files,
invoiceitems, invoices, mandates, payouts, plans, prices, products, quotes, refunds,
reviews, sources, subscriptions, tokens, topups, transfers
```

## Limitation 2 — the client Stripe's own Python documentation constructs is not recognised

Measured directly, five shapes through `PythonAdapter.index`:

| source shape | call sites indexed |
|---|---:|
| `import stripe` … `stripe.charges.create(...)` | **1** |
| `from stripe import StripeClient` … `client = StripeClient(k)` … `client.charges.create(...)` | **1** |
| `import stripe` … `client = stripe.StripeClient(k)` … `client.charges.create(...)` | **0** |
| `import stripe` … `client = stripe.StripeClient(k)` … `client.customers.create(...)` | **0** |
| `import stripe` … `stripe.Charge.create(...)` | **0** — documented and deliberate |

The third row is the one that matters. `stripe.StripeClient(...)` is a module-attribute
constructor rather than an imported name, and the binding rule matches an imported name — which
is the rule `sync.index.typescript` states and this module mirrors. It is also the spelling
Stripe's own Python documentation uses.

## Limitation 3 — a receiver that is not a bare identifier binds nothing

Across the twelve repositories found by searching for the *indexable* client shape, the calls
themselves are written the way production Python is written:

```
get_stripe_client().customers.create({"name": organization.name})   # a factory call
self.client.customers.create(params=params)                          # an attribute
self.client.customers.retrieve(subscription["customer"])
```

Neither a call expression nor an attribute is a bare identifier, so neither resolves. Dependency
injection and a client held on `self` are the normal shapes for the code most worth measuring.

## The measurement: seventeen repositories

Every one cloned at its default branch and indexed with the real adapter and the real symbol map.

| repository | licence | `matches` | indexable call sites |
|---|---|---|---:|
| `hashicorp-forge/grove` | MPL-2.0 | yes | **1** |
| `TechWithTy/fast_stripe_python_template` | **none** | no | 10 |
| `DanielAguilarJ/RestoNext` | **none** | no | 2 |
| `kintsugi-tax/kintsugi-stripe-payments` | MIT | yes | 0 |
| `jwpconsulting/projectify` | NOASSERTION | yes | 0 |
| `openinvoiceio/openinvoice` | AGPL-3.0 | — | 0 |
| `kupio-app/kupio-backend` | none | yes | 0 |
| `dusanmlynarcikdev/pro-plan-api` | — | yes | 0 |
| `aipotheosis-labs/gate22` | — | no | 0 |
| `jifalops/api-python` | — | no | 0 |
| `Kamil118/Soup-Site` | — | no | 0 |
| `MyTeslaMate/chatbot-swarm`, `oskarjolofsson/GSA1.0`, `LilithB92/Online_training_DRF`, `sjcahill/mainttracker_functions_core_lib`, `qubitpage/qubgpu`, `darvid/ultrasync` | — | — | 0 |

**One repository is both pinnable and non-empty, and it contributes one call site.** The brief's
own bar — *"a repository contributing two positives is not worth the pin"* — rules it out.

The two repositories with real call-site counts fail on other grounds, and not narrowly:

- `TechWithTy/fast_stripe_python_template` has ten sites but **no licence at all**, and **no
  `requirements.txt` or `pyproject.toml` anywhere**, which is why `matches` is false and why
  `sync.cli` would never select an adapter for it. Its ten sites are also one per operation —
  every pair would be a single-site pair, so the `hold_back` rule could never fire and the
  repository would contribute **zero** falsifiable negatives while moving both denominators.
- `DanielAguilarJ/RestoNext` has two sites on one operation, which is the minimum shape a
  hold-back needs, and also no licence.

## How rare the indexable shape is

Searching GitHub's code index for the one module-level form that does resolve:

```
"stripe.charges.list("        language:python    2 files
"stripe.customers.list("      language:python    3
"stripe.invoices.list("       language:python    3
"stripe.products.list("       language:python    3
"stripe.subscriptions.retrieve(" language:python 4
"stripe.customers.create("    language:python   11
"stripe.refunds.create("      language:python   17
```

Against `"from stripe import StripeClient"` at 143 files — the shape that is common, and whose
call sites are then written in the two forms limitation 3 rules out.

## What would unblock this, in the order it would pay

1. **Bind a client constructed as a module attribute.** `client = stripe.StripeClient(k)` is one
   rule away from the imported-name case already handled, and it is what Stripe documents. This
   alone converts eleven of the seventeen repositories measured here from zero to non-zero.
2. **Bind a receiver that is an attribute of `self`.** `self.client.customers.create(...)` is the
   shape production code uses, and it is the one this corpus most wants to measure.
3. **Give the symbol map a Python spelling.** 93 of 179 symbols are currently unreachable from
   Python, including `paymentIntents`. This is a map built from one SDK being asked to serve two,
   and it belongs to `sync.signals.stripe.symbols` rather than to the indexer.

Each is a change to what is measured, so each wants a corpus that can see it — which is this
task, run again after the fix. The order above is the order of how many repositories each unlocks.

## What this says about the two defects fixed today

The brief noted that two real Python indexer defects — a false attribution through `dict(...)` and
a missed walrus assignment — were fixed against hand-written fixtures because fixtures were the
only evidence available, and that closing that gap was the point of this task.

The gap is not closed and it is now measured. Both of those defects concern what happens *after* a
call site is bound. Every limitation above concerns whether it is bound at all, so a corpus that
existed today would not have exercised either fix in any of the seventeen repositories: sixteen of
them bind nothing, and the seventeenth binds one call that is neither shape.

That is a stronger statement than "the corpus is missing Python". The corpus cannot currently be
given Python, and the first three fixes above are what would change that.

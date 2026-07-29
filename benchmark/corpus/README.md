# The frozen specimen corpus

`sync benchmark --score-pair` scores one pair. This directory is the set: four real repositories
pinned by commit, twelve corpus specifications generated from a stated rule, and the recorded
score over all of them.

`docs/superpowers/specs/2026-07-29-sync-verification-regime.md` names why it had to exist.
`2026-07-27-sync-benchmark-gates.md` is explicit that an unfrozen benchmark measures the
benchmark: a pair regenerated fresh each run scores a different input set each run, so a movement
in the number means nothing. Freezing is what turns a score into a benchmark.

## Running it

```
uv run python scripts/fetch_corpus_repositories.py                     # once; the only network step
uv run python scripts/fetch_measurement_inputs.py --measurement symbol-coverage-105-of-414
uv run python scripts/score_corpus.py --score-dsn postgresql://sync:sync@localhost:5433/<a database of its own>
```

Run from the repository root: the specifications name paths relative to it.

The second command puts the pinned Stripe specification in `.cache/specs/`; the symbol map
`stripe` resolves through is built from it once with `sync.signals.stripe.symbols.build_symbol_map`
over `v2330.json` and `v2330.sdk.json`. Scoring itself reaches no network, which is the offline
contract `_score_corpus` already keeps by loading the vendor rather than staging it.

`--score-dsn` is truncated per pair. It must not name a database holding anything you want.

## Which repositories, and why these

Real repositories pinned by SHA, fetched into the gitignored `.cache/corpus/` by a setup step,
with only the manifest committed. The alternative was committed fixture repositories, which are
fully deterministic and need no fetch — and which measure the fixtures. This project's own
fixtures were written to exercise the indexer, so a binding score over them would be a score over
code shaped by the thing being scored. `2026-07-29-sync-ground-truth-quality.md` chose synthetic
mutation of *real* repositories for the same reason, and this follows it.

| name | repository | commit | why |
|---|---|---|---|
| `furever` | `stripe/stripe-connect-furever-demo` | `5114c96` | Stripe's own Connect demo, and the repository M0's acceptance test targets. `tests/fixtures/ts/two_payment_intents` was already shaped after one of its route handlers. |
| `turbo` | `ardriveapp/turbo-payment-service` | `6c7aac0` | A production payment service rather than a sample: third-party code with no relationship to Stripe or to this project. |
| `remix` | `cjavilla-stripe/remix-stripe-sample` | `25982ff` | Small, and a different framework. It contributes the single-call-site case, which is where a pair has the least room to hide a miss. |
| `fireship-server` | `fireship-io/stripe-payments-js-course` | `d4a5fc4` | Course code, written to be read rather than to ship, and the only one calling subscriptions and customers. Its `package.json` is under `server/`, which is what `subpath` names. |

All four are TypeScript, declare `stripe` in a `package.json`, and call operations the Stripe
symbol map covers. That last condition is doing more work than it looks: the map covers 105 of
414 `/v1/` paths, so a repository whose Stripe usage is `checkout.sessions.create` — which is a
nested sub-resource the path pattern does not match — contributes nothing and was not selectable.

**What this sample is not.** Four repositories, three of them demonstration or teaching code.
Nothing here was chosen for being representative of the population of repositories that depend on
Stripe, because no measurement of that population exists.

## What is committed and what is fetched

Committed: `repositories.yaml`, the twelve specifications under `pairs/`, and the recorded score
under `recorded/`. Fetched: the checkouts themselves, into `.cache/corpus/`, which `.gitignore`
already excludes.

`repositories.yaml` pins each entry three ways — the commit, the subpath, and a `tree_digest`
over every materialised path and the SHA-256 of its bytes. The commit pins what the vendor
published; the digest pins what the fetch produced from it, and the fetch refuses when the two
disagree.

**The materialised tree is pruned and that is a real transformation.** `sync.cli._score_corpus`
reads every file under the checkout with `read_text(encoding="utf-8")`, so one PNG anywhere ends
the run — the Connect demo carries 63 files that are not UTF-8. The fetcher materialises only the
files that decode, and prints how many it dropped. Nothing an indexer reads is lost by that;
`package.json`, `tsconfig.json` and every `.ts` file are text. It is still not the vendor's tree,
and the digest is over what was scored rather than over what was published.

## Which pairs, and why those

`scripts/build_corpus_specs.py` generates the specifications and is the record of the rule. A
corpus assembled by picking pairs that score well measures the picker, so the selection is
executable and the score is whatever it produces — including the pairs the harness then refuses.

- **Operations.** Per repository, the two with the most indexed call sites where at least one
  call passes an object argument, ties broken by operation id ascending. An operation whose calls
  take no object argument is excluded because neither mutation can attach to one.
- **Kinds.** `request-property-removed` and `response-property-removed`, the two mechanically
  different inversions `sync.benchmark.mutate` implements. The third supported kind,
  `request-parameter-removed`, mutates identically to the first.
- **Field.** The alphabetically first property of that operation in the pinned `v2330`
  specification that no indexed call site in the repository already passes, for a request change,
  or already reads, for a response change. Real properties of the real operation, so the mutation
  writes something the vendor could have removed; alphabetically first so the choice is not a
  judgement.
- **Held back.** The first call site on the changed operation by position, when the operation has
  more than one indexed call site and that site carries a non-empty field list on the side the
  change is on. One per specification and never more. It goes into the specification as a
  `hold_back` entry naming a path, a line and a column, and `sync.cli._corpus_targets` drops it
  from the target list; the next section is what it is for.

Two combinations produced no specification and the generator said so rather than substituting
one: `furever/GetCharges` and `fireship-server/GetPaymentMethods` are GETs with no request body,
so `request-property-removed` has no property to name.

The hold-back rule selected a site in four of the twelve specifications and passed over the other
eight, which carry no `hold_back` key and are byte-identical to what the generator wrote before
the rule existed. Each clause of it is doing work:

- **The first by position**, because every insertion `mutate.py` makes lands at or after the call
  it breaks and `upsert_call_site` keys a call site's identity on its position. Only the earliest
  site on the operation is guaranteed to still be where the specification says once its siblings
  have been mutated. `furever-GetCharges` is what the other choice costs: one response guard
  inserted above three later calls displaces all three labels and the whole pair leaves the score.
- **Non-empty field list on the change's side**, because that is the branch
  `VendorChangeDetector.scan` takes, and `_deepest_match` over an empty list declines against
  every change there has ever been. Holding such a site back would cost a positive and buy no
  candidate.
- **More than one site on the operation**, because holding back the only one leaves the mutation
  nothing to break, and a pair with no target is refused rather than scored.
- **One and never more**, because every held-back site is a site binding recall no longer
  measures.

## Reading the recorded score

`recorded/` holds three runs of the same twelve specifications, each byte-identical to a second
run from a clean database. Read the newest; the older two are kept because they are what the
reports argue over.

| file | corpus | what it added |
|---|---|---|
| `2026-07-29-score.{txt,json}` | before the hold-back | the first binding numbers over the frozen set |
| `2026-07-29-falsifiable-negatives.{txt,json}` | before the hold-back | the count of negatives the detector could have fired on: zero |
| `2026-07-29-held-back-negatives.{txt,json}` | current | one site held back per eligible pair, and the first non-zero count |

`docs/superpowers/reports/2026-07-29-frozen-corpus-first-binding-numbers.md` carries what the
first set of numbers does and does not support,
`2026-07-29-precision-has-no-negative-to-fail-on.md` is the diagnosis the second one measured, and
`2026-07-29-precision-gets-its-first-negative.md` is the change between the second and the third.

Three things those reports insist on and this directory must keep:

- **Every axis carries its sample size.** In the current recording precision and recall are each
  over nine labelled affected call sites. Nine — it was twelve before three were held back, and
  a recall that changed because its denominator moved is not a regression.
- **Excluded pairs are counted and named.** Two of the twelve specifications are refused, both
  `displaced-label`.
- **A pair that contributed no positives is visible.** Five of the ten scored pairs contribute
  zero affected call sites — every response-side pair that is not refused outright — because the
  response mutation cannot attach to any of their calls. The corpus total cannot show that and
  the per-pair table does.

## Precision now has a negative it could be wrong about

`falsifiable negatives` counts the labelled negatives this change gave the detector any chance of
firing on: the site is on the changed operation, so `call_sites_for_operation` returns it, and it
carries a non-empty field list on the side the change is on, so `_deepest_match` has something to
test. It read **zero** in every one of the ten scored pairs before the hold-back, which meant
precision's false-positive term had no candidates rather than few — 1.0000 was what building the
corpus that way guaranteed, and it would have survived a binder regression that only affected
same-operation discrimination.

It reads **3** now, and precision still reads 1.0000. Those two sentences belong together: the
binder was offered three same-operation call sites it could have claimed and declined all three,
which is the first evidence that axis has ever carried. One of the three is a near miss rather
than a formality — `turbo` passes `amount` at a site where the changed property is
`amount_details`, and a match on segment prefixes rather than whole segments would fire on it.

What remains constant is that a hold-back can only help where the mutation had somewhere to
attach. Every response-side pair reads no response field at any of its call sites, so a site held
back there has an empty field list and declines against every change regardless; the two
single-site request pairs cannot spare their only target. Three is therefore the whole of what
this corpus can currently offer, not a sample of it.

So no choice of repository or specification fixes this while that rule stands, and adding
repositories would raise the negative count without adding a single candidate. What the corpus
needed was a same-operation call site deliberately held back from the target list — which
`generate_pair` already supported, since the caller names its targets, and which nothing asked it
for until `hold_back` landed.

While that was true a directional floor on binding precision would have gated a constant, which
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` names as the failure that is worse
than having no gate at all.

## The response axis exists now, and recall fell when it did

`recorded/2026-07-29-response-axis.txt` and `.json` are the run after the response mutation
stopped moving the calls below it and learned to attach to a result bound by assignment.
Byte-identical across two runs from two clean databases
(`8d5b39830546b2d5958f72f310cc358aa97eeb0807f3dff731a1a2ebde0e11ff`).

```
  pairs scored          12          was 10
  binding precision     1.0000  n=16    was 1.0000  n=12
  binding recall        0.8000  n=20    was 1.0000  n=12
  call sites affected   20          was 12
```

**Recall's denominator moved, so the two numbers are not comparable and the fall is not a
regression.** Eight response-side positives entered a corpus that had none: four from targets the
mutation can now attach to, and four from the two pairs that were previously refused outright as
`displaced-label`. No pair is excluded now.

The four misses are all response-side and they are a real finding about the binder rather than
about the corpus. `sync.index.typescript._response_fields` walks up to a `variable_declarator` and
returns nothing otherwise, so a call whose result is assigned to a variable declared earlier
records an empty `response_fields_read` — measured directly: the same guard after
`const intent = await …` records `['amount_details', 'id']` and after `intent = await …` records
`[]`. **No response-side vendor change can be detected on that shape at all**, which is the same
limitation the generator had until this change, on the other side of the pipeline.

Seven targets remain unreachable and are correctly labelled unaffected. Five discard the result
outright and two return it out of the function; neither reads a response field, so neither is
broken by a response property being removed. They are not a sample the corpus is missing.

## Which files can carry a response-side pair

All of them, now. The guard is appended to the statement it follows rather than occupying lines of
its own, so a mutation no longer renames the calls below it and a file with several calls is no
longer disqualified.

One narrower case survives and is deliberately left: two calls **sharing a line**. The guard adds
characters before the second call's column, `upsert_call_site` keys identity on the column too, and
the pair is refused as `displaced-label` — correctly. `tests/test_binding_score.py` asserts the
refusal against exactly that shape, because a refusal whose common case has disappeared is no
longer being tested.

Three is also small. A directional floor on binding precision still needs a variance measurement
over the new corpus before it would mean anything, and
`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` is what says an invented threshold is
worse than no threshold at all. Nothing here is gated.

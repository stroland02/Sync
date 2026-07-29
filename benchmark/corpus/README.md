# The frozen specimen corpus

`sync benchmark --score-pair` scores one pair. This directory is the set: five real repositories
pinned by commit, seventeen corpus specifications generated from a stated rule, and the recorded
score over all of them.

Seventeen held and twelve proposed, which is not a contradiction — "The corpus is a superset of
what the rule proposes" below is why, and it is the one thing to read before concluding this
directory has drifted.

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
| `virtual-lab` | `openbraininstitute/virtual-lab-api` | `a2577bb` | The first entry that is not TypeScript. Apache-2.0, declares `stripe` in a `pyproject.toml`, 21 indexed call sites over 12 operations. It contributes no pair yet, and the section below is why. |

Four of the five are TypeScript and declare `stripe` in a `package.json`; the fifth is Python and
declares it in a `pyproject.toml`. All five call operations the Stripe symbol map covers. That
last condition is doing more work than it looks: the map covers 105 of 414 `/v1/` paths, so a
repository whose Stripe usage is `checkout.sessions.create` — which is a nested sub-resource the
path pattern does not match — contributes nothing and was not selectable.

**What this sample is not.** Five repositories, three of them demonstration or teaching code.
Nothing here was chosen for being representative of the population of repositories that depend on
Stripe, because no measurement of that population exists.

## The corpus once held a repository and no pair over it, and why that is over

`virtual-lab` was pinned for several hours contributing nothing, and the reason is worth keeping
because it is the sharpest thing this corpus has caught.

The selection rule then took the two operations with the most call sites passing an object
argument, which in `virtual-lab` are `GetCustomers` and `GetSubscriptions`. Both are GETs, so no
request pair exists; both response pairs generated, and both labelled a dependency the repository
does not have. Every one of those six call sites is written

```python
customers = list(self.client.customers.list(params={"limit": 100}).auto_paging_iter())
```

and the response mutation appended its guard to the statement binding the result:

```python
customers = list(...auto_paging_iter()); assert customers.has_more is not None
```

`customers` is a Python list built from the pager, `customers.has_more` is an `AttributeError`,
and removing `has_more` from that response cannot break that code. The generator and the indexer
disagreed about what binding a result means:

| | rule |
|---|---|
| `sync.benchmark.mutate._result_binding` | climbed to an `assignment` whose value **contained** the call |
| `sync.index.python_lang._result_target` | requires the value to **be** the call |

Containment against identity. Scored as generated, those two pairs read as two missed breaks and
would have taken pooled recall from 1.0000 to 0.8889 — a number measuring the generator's
permissiveness rather than the binder's accuracy, and a recall floor lowered to admit it would
have certified a mislabel. They were refused instead, and
`docs/superpowers/reports/2026-07-29-the-corpus-refuses-to-certify-itself.md` is the measurement.

Both halves are closed now. `_result_binding` requires identity, so those targets are recorded
`unreachable` rather than mislabelled; and the selection rule judges an operation on the side its
own change is judged on, so `GetProductsId` — three positional `products.retrieve` calls reading
fields off the result — is proposable where it was invisible. `virtual-lab` contributes two
response pairs and three of the corpus's twenty-seven positives.

## What is committed and what is fetched

Committed: `repositories.yaml`, the seventeen specifications under `pairs/`, and the recorded score
under `recorded/`. Fetched: the checkouts themselves, into `.cache/corpus/`, which `.gitignore`
already excludes.

`repositories.yaml` pins each entry three ways — the commit, the subpath, and a `tree_digest`
over every materialised path and the SHA-256 of its bytes. The commit pins what the vendor
published; the digest pins what the fetch produced from it, and the fetch refuses when the two
disagree.

**The materialised tree is the vendor's subtree, minus `.git` and `node_modules`.** It was not
always. The fetcher used to remove every file that does not decode as UTF-8, because
`_score_corpus` read the whole checkout with `read_text(encoding="utf-8")` and one PNG anywhere
ended the run — the Connect demo carries 63 files that are not UTF-8. So the digest pinned what
our own filter left behind rather than what the vendor published.

`sync.benchmark.checkout.read_checkout` now skips what it cannot read as source and names those
paths beside the score, so the fetch has no filtering left to do and copies bytes verbatim. Two
digests moved on 2026-07-29 and no pinned commit did: `furever` gained 63 images and fonts,
`remix` gained one, and `turbo` and `fireship-server` carry no undecodable file at all. Neither
corpus axis moved — `docs/superpowers/reports/2026-07-29-one-png-ends-a-corpus-run.md` carries the
measurement.

Both components walk the tree through one function, `sync.benchmark.checkout.tree_files`, rather
than through two implementations of one rule. A divergence there would leave the digest pinning
one set of files while the score was taken over another, and nothing in either would notice.

## Which pairs, and why those

`scripts/build_corpus_specs.py` generates the specifications and is the record of the rule. A
corpus assembled by picking pairs that score well measures the picker, so the selection is
executable and the score is whatever it produces — including the pairs the harness then refuses.

- **Operations.** Per repository **and per kind**, the two with the most indexed call sites where
  at least one site carries a non-empty field list on the side that kind's change is judged on —
  `args_keys` for a request change, `response_fields_read` for a response one — ties broken by
  operation id ascending. Per kind because the two mutations need different things: a request
  mutation needs a call passing an object argument, so `products.retrieve(id)` has nowhere to put
  a property; a response mutation needs a call binding a result something reads a field off, and
  asking the request question of that operation excluded it for the wrong reason. Response
  coverage was a side effect of request coverage until that split landed.
- **Kinds.** `request-property-removed` and `response-property-removed`, the two mechanically
  different inversions `sync.benchmark.mutate` implements. The third supported kind,
  `request-parameter-removed`, mutates identically to the first.
- **Field.** The alphabetically first property of that operation in the pinned `v2330`
  specification that no indexed call site in the repository already passes, for a request change,
  or already reads, for a response change. Real properties of the real operation, so the mutation
  writes something the vendor could have removed; alphabetically first so the choice is not a
  judgement. The scan behind "already reads" is coarse and reads the repository's **own**
  language: a Python repository scanned for `*.ts` reads nothing at all, which is an absent guard
  rather than a loose one, and a TypeScript repository scanned for `*.py` would read the one
  stray script `furever` carries and move a frozen field.
- **Held back.** The first call site on the changed operation by position, when the operation has
  more than one indexed call site and that site carries a non-empty field list on the side the
  change is on. One per specification and never more. It goes into the specification as a
  `hold_back` entry naming a path, a line and a column, and `sync.cli._corpus_targets` drops it
  from the target list; the next section is what it is for.

Five combinations produce no specification and the generator says so rather than substituting one.
`furever/GetCharges`, `fireship-server/GetPaymentMethods`, `virtual-lab/GetCustomers` and
`virtual-lab/GetSubscriptions` are GETs with no request body, so `request-property-removed` has no
property to name; `fireship-server/GetCustomersCustomer` has no response property the repository
does not already read.

The hold-back rule selects a site in six of the seventeen specifications and passes over the other
eleven, which carry no `hold_back` key. Each clause of it is doing work:

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

## The corpus is a superset of what the rule proposes

Seventeen specifications are committed and the rule proposes twelve. **Every operation the rule
proposes is in the corpus**; the five extra are pairs it no longer proposes and which score
honestly anyway. That relationship is deliberate and is the invariant to hold this directory to —
not equality.

The gap opened when selection was corrected to judge an operation per kind. Measured against the
pinned set afterwards, the corrected rule differed in four places. Each was checked for whether it
was an addition or a substitution, because the answer decides the work:

| the rule now proposes | classification | what the corpus gained |
|---|---|---|
| `virtual-lab-GetBalance-response` | **addition** — `GetProductsId` keeps its slot and this fills the second, previously empty | one response positive, Python's second pair |
| `furever-GetAccountsAccount-response` | **substitution** — the rule picks it instead of `furever-GetCharges-response` | six response positives, the most of any pair, and the sixth falsifiable negative |
| `turbo-GetPaymentIntentsIntent-response` | **substitution** — instead of `turbo-PostRefunds-response` | one response positive on a GET, where the corpus had only POST response coverage for `turbo` |
| `fireship-server-DeleteSubscriptionsSubscriptionExposedId-response` | **substitution** — the rule's two response slots displace both `PostPaymentIntents-response` and `GetPaymentMethods-response` | one response positive on a DELETE, the only one in the corpus |

All four were added and none of the five was replaced. What replacing would have cost, pair by
pair:

- `furever-GetCharges-response` is one positive and the worked example behind the hold-back rule's
  first-by-position clause — a response guard inserted above three later calls displaced all three
  labels and the whole pair left the score. Dropping it drops a documented regression witness.
- `fireship-server-PostPaymentIntents-response` is two positives.
- `turbo-PostRefunds-response`, `fireship-server-GetPaymentMethods-response` and
  `remix-PostPaymentIntents-response` each contribute a labelled negative rather than a positive:
  their targets discard the result, so the response mutation cannot attach and the site is
  correctly unaffected. They are the corpus's record that "cannot attach" is distinguishable from
  "attached and missed", and `remix` is the single-call-site repository, where a pair has the least
  room to hide a miss.

The general argument is that the corpus's job is to be a stable ruler, not to be reproducible from
the current rule. A pair that scores honestly is evidence whether or not today's selection would
have chosen it, and a rule will be corrected again. Discarding a measured, gated, byte-identical
baseline for the tidiness of exact reproducibility trades the thing the corpus is for against a
property it never needed.

`remix` is the one place the rule proposes nothing where the corpus holds something: no `remix`
operation reads a response field at any indexed call site, so there is no response candidate at
all, and nothing was available to add.

**Two committed specifications also differ in content from what the generator writes today, and
the drift is in the hold-back.** Re-running it writes a `hold_back` entry into
`furever-PostPaymentIntents-response-property-removed` and
`turbo-PostPaymentIntents-response-property-removed` that the committed versions do not carry.
Nothing about those checkouts moved. The binder did: B34 taught it to record fields off a result
the call reaches through a wrapper, so the first site on each of those operations now has a
non-empty `response_fields_read` where it had none, and the hold-back rule's third clause fires.
Both are left as pinned. Adopting them would trade two positives for two negatives on pairs that
already score, which is a distribution change with its own measurement rather than a side effect of
adding four pairs — and it is the one difference here that would move a rate rather than a
denominator.

## Reading the recorded score

`recorded/` holds every run the reports argue over, each byte-identical to a second run from a
clean database. Read the newest; the older ones are kept because they are the before-states those
reports measure against.

| file | corpus | what it added |
|---|---|---|
| `2026-07-29-score.{txt,json}` | 10 pairs | the first binding numbers over the frozen set |
| `2026-07-29-falsifiable-negatives.{txt,json}` | 10 pairs | the count of negatives the detector could have fired on: zero |
| `2026-07-29-held-back-negatives.{txt,json}` | 10 pairs | one site held back per eligible pair, and the first non-zero count |
| `2026-07-29-response-axis.{txt,json}` | 12 pairs | the response mutation attaching, and the recall fall that exposed a binder defect |
| `2026-07-29-symbol-map-pinned.{txt,json}` | 12 pairs | the symbol map pinned, and a Python repository added contributing no pair |
| `2026-07-29-first-python-pair.{txt,json}` | 13 pairs | `virtual-lab-GetProductsId`, the first Python pair to score |
| `2026-07-29-the-rule-and-the-corpus-agree.{txt,json}` | **current, 17 pairs** | the four pairs the corrected selection rule proposes and the pinned set lacked |

`docs/superpowers/reports/2026-07-29-frozen-corpus-first-binding-numbers.md` carries what the
first set of numbers does and does not support,
`2026-07-29-precision-has-no-negative-to-fail-on.md` is the diagnosis the second one measured, and
`2026-07-29-precision-gets-its-first-negative.md` is the change between the second and the third.

Three things those reports insist on and this directory must keep:

- **Every axis carries its sample size.** In the current recording precision and recall are each
  over twenty-seven labelled affected call sites, twenty-four of them TypeScript and three Python.
  A rate that changed because its denominator moved is not a regression, and the sample size is
  what lets a reader tell the two apart.
- **Excluded pairs are counted and named.** None of the seventeen is refused. When two were, both
  were `displaced-label`.
- **A pair that contributed no positives is visible.** Three of the seventeen contribute zero
  affected call sites — `fireship-server-GetPaymentMethods-response`,
  `remix-PostPaymentIntents-response` and `turbo-PostRefunds-response` — because every target
  discards its result and the response mutation has nothing to attach to. The corpus total cannot
  show that and the per-pair table does.

## Precision now has a negative it could be wrong about

`falsifiable negatives` counts the labelled negatives this change gave the detector any chance of
firing on: the site is on the changed operation, so `call_sites_for_operation` returns it, and it
carries a non-empty field list on the side the change is on, so `_deepest_match` has something to
test. It read **zero** in every one of the ten scored pairs before the hold-back, which meant
precision's false-positive term had no candidates rather than few — 1.0000 was what building the
corpus that way guaranteed, and it would have survived a binder regression that only affected
same-operation discrimination.

It reads **6** now, and precision still reads 1.0000. Those two sentences belong together: the
binder was offered six same-operation call sites it could have claimed and declined all six, which
is the only evidence that axis carries. One of the six is a near miss rather than a formality —
`turbo` passes `amount` at a site where the changed property is `amount_details`, and a match on
segment prefixes rather than whole segments would fire on it.

The count grew with the corpus rather than with any change to the rule: three when the hold-back
landed, five when the first Python pair did, and six with `furever-GetAccountsAccount`. What stays
constant is that a hold-back can only help where the mutation had somewhere to attach. A pair
whose call sites read no response field has an empty field list at the site it would hold back, so
that site declines against every change regardless; a single-site pair cannot spare its only
target. Six is the whole of what this corpus offers, not a sample of it, and the way to raise it
is another operation carrying several call sites that bind their results — not another repository.

What the corpus needed to have any negative at all was a same-operation call site deliberately
held back from the target list — which `generate_pair` already supported, since the caller names
its targets, and which nothing asked it for until `hold_back` landed.

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

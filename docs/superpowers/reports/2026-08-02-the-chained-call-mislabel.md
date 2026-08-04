# The mutation attached to the pager, and the fix moved nothing

**Date:** 2026-08-02
**Task:** M3-W121
**Answer taken:** `_call_at` now resolves a recorded position by the indexer's own callee
condition rather than by a length tie-break. The frozen corpus was regenerated in the same commit
and came out byte-identical, which is a result and is explained below rather than celebrated.

## The rule, and the indexer fact it rests on

`_call_at` matched a start position exactly and then broke a tie with
`max(..., key=(object_argument is not None, length))`. A chained call and its receiver start at the
same line and column, so both matched and the longest — the outer call — won. The field the vendor
removed from the operation was written into the pager's argument list while the label still said
the site was affected.

**The rule that replaced it is not "prefer the shorter call".** It is the condition both indexers
apply before they record anything:

| | what it requires of a call before recording it |
|---|---|
| `sync.index.python_lang.index` | `function` is an `attribute`, and `_attribute_chain` flattens it — a walk through `attribute` nodes terminating on an `identifier` |
| `sync.index.typescript.index` | `function` is a `member_expression`, and `_member_chain` flattens it — the same walk over `member_expression` |

A chained call's callee has another *call* as its object, so neither walk terminates and
**the outer call is never recorded at all**. A position the indexer emitted therefore cannot denote
it. `_recorded_shape` is that walk, duplicated rather than imported for the reason `_RESULT_WRAPPERS`
already is: `mutate.py` imports nothing from `sync.index`, because a generator that consulted the
binder would be scoring the binder against its own opinion.

## Preferring the innermost call is right in general, and here is why rather than which examples

Two calls share a start position **if and only if** one is the other's receiver. An argument begins
after the opening parenthesis, so nothing in an argument list can start where the call does;
therefore a second call at the same position must lie in the callee subtree, at the callee's own
start, which means the receiver chain bottoms out in a call.

From that, two things follow without appeal to examples:

- **At most one match can satisfy the rule.** A callee that flattens to identifiers contains no
  call for another match to start at.
- **The old tie-break only ever fired on a chain.** Every other position has exactly one match, so
  `max` over a one-element list. There was no case in which it was doing correct work.

Measured against the pinned checkouts rather than reasoned about alone: over all **71** indexed call
sites in the five repositories, the predicate leaves **exactly one** surviving candidate at every
one, and never two.

Where nothing survives, `_call_at` returns `None`. That is a position no indexer could have
produced — `a["b"].list(...).auto()` is the shape, and neither `_member_chain` nor `_attribute_chain`
flattens either of its calls — so it is the same broken input as a position naming no call at all,
and the caller records the target as unreachable rather than mislabelling it.

## The corpus score, before and after

Both runs used the same score DSN (`sync_w121_score`), the same pinned symbol map
(`5f71dcd3bec1302c`), serially, one process. The `before` run was taken on the tree at `995e05a`
before any edit, and is byte-identical to
`recorded/2026-07-29-the-hold-back-the-binder-earns.{txt,json}` — which is what says the checkouts
and the harness were in the state that recording was taken in.

| axis | before | after | moved |
|---|---|---|---|
| pairs specified | 17 | 17 | no |
| pairs scored | 17 | 17 | no |
| binding precision | 1.0000 n=26 | 1.0000 n=26 | no |
| binding recall | 1.0000 n=26 | 1.0000 n=26 | no |
| call sites affected | 26 | 26 | no |
| call sites unaffected | 216 | 216 | no |
| unlabelled findings | 0 | 0 | no |
| falsifiable negatives | 7 | 7 | no |
| paths not read | 71 | 71 | no |
| excluded pairs | none | none | no |
| unreachable targets | 7 | 7 | no |

Not merely equal per axis: the rendered text and the JSON are byte-identical, and every per-pair row
is unchanged. `scripts/gate_corpus.py --score` clears every floor.

### Why it did not move, measured rather than assumed

Nine indexed call sites in the pinned checkouts sit at a position naming two calls. All nine are in
`virtual-lab`, in `scripts/manage_stripe_coupons.py` and `scripts/migrate_to_tax_billing.py`, over
five list operations — `GetCoupons`, `GetCustomers`, `GetInvoices`, `GetPrices`, `GetSubscriptions`.
The other four repositories have none at all.

Walking every committed specification and resolving each of those sites under both the old
tie-break and the new rule:

```
call sites at a shared start position whose resolution moved: 18
...of which are targets of any committed specification:        0
```

Eighteen because the nine appear in both specifications `virtual-lab` contributes, and both are
`response-property-removed` on operations whose own call sites do not chain — `GetBalance` and
`GetProductsId`, written `client.balance.retrieve(...)` and `client.products.retrieve(...)`. So the
nine are labelled negatives and never targets.

The one remaining route by which a negative could have moved the score is `generate_pair`'s
already-depends refusal, which runs over *every* site rather than only the targets. It answers
`False` at all eighteen under both resolutions: a response change takes the `_result_binding` branch,
and a chained pager binds its result to nothing a guard could read, so the branch declines whichever
call it is asked about.

### What a reader may not conclude from the number not moving

- **Not that the defect was harmless.** It is that this corpus never held a pair positioned to see
  it. The mislabel is real in both languages and is demonstrated by test.
- **Not that the corpus covers chained call sites.** Nine of them are in it, as negatives, on the
  axis that cannot reach them.
- And the standing caveat still applies with full force: **precision over a flat pair has almost no
  way to fail.** All seventeen pairs are one change kind, `1.0000` at n=26 is what building the
  corpus this way guarantees, and it would have read the same through this defect either way. Had a
  rate risen here, it would have risen because the mutation started landing on the right call —
  which is the corpus becoming a more honest ruler, not the binder becoming a better binder.

## The three urgency claims, checked — and two of them corrected

W117's handoff argued the defect was more urgent than latent. The argument stands, but two of the
three facts it rests on do not survive being asked directly.

**"Thirteen chained pager sites across two of five pinned checkouts."** Thirteen is the count of
textual `auto_paging_iter` / `autoPagingToArray` occurrences. **Nine** of them are indexed call
sites, and they are in **one** of the five checkouts. The four in `furever/scripts/setup-accounts.py`
are never indexed: `furever` declares `stripe` in a `package.json`, so `select_language_adapter`
gives it the TypeScript adapter and its `.py` files are not walked at all — and the first of them is
`stripe.Account.list()`, the resource-class idiom `python_lang.py`'s own docstring says resolves to
no operation.

**The corpus header says what W117 said it says.** Verified verbatim in
`benchmark/corpus/pairs/virtual-lab-GetProductsId-response-property-removed.yaml`: "The two
candidate operations B45 proposed both bound through `list(...auto_paging_iter())` and were refused
for it."

**"A `request-property-removed` pair on any of those five operations is one specification away and
the rule would accept it." This is false**, and running `scripts/build_corpus_specs.py` into a
scratch directory is what says so. The five operations *do* reach the candidate stage on the request
side — every chained site carries a non-empty `args_keys`, because `params={...}` is read as a
keyword argument — and the rule then declines at the field step:

```
virtual-lab/GetCustomers/request-property-removed: no unused property; skipped
virtual-lab/GetSubscriptions/request-property-removed: no unused property; skipped
```

All five are GETs and all five have **zero** `requestBody` properties in `v2330`. That is the same
clause that already excludes `furever/GetCharges` and `fireship-server/GetPaymentMethods`, and the
README already names it. The rule proposes the same twelve specifications it proposed before this
change, so the superset invariant is untouched.

**What survives, and it is enough.** The kind these operations actually take is
`request-parameter-removed` — a query parameter on a GET. It is in `SUPPORTED_KINDS`, it dispatches
through the same `_insert_property` branch, and W117 measured that it produces a well-formed pair.
`KINDS` in the rule holds two kinds and this is not one of them, so nothing *generated* reaches the
shape. The defect is therefore one **hand-written** specification away rather than one rule-generated
one. That is a materially weaker claim than the handoff made, and it is still close enough that
landing the fix before the specification is the right order.

## What `depends_on_change` and the audit half now see

The audit half exists so a label can be checked against what the tree says rather than against what
the generator recorded. It could not catch this, because it resolves the position through the same
`_call_at`: both halves were wrong about the same call, and their agreement was a mirror rather than
a check. Three things it now sees that it did not:

- **On a mutated chained tree it still answers `True`, and now for the right call.** Unchanged in
  value, changed in meaning.
- **A field the pager carries is no longer read as the call site's own dependency.**
  `auto_paging_iter(created=...)` used to make `depends_on_change` answer `True` for a change
  removing `created` from `GET /v1/coupons`, which it cannot break. It answers `False`.
- **`generate_pair`'s exactness guard reaches a chained site.** A site already passing the removed
  field on the operation's own call used to slip past — the guard asked whether the *pager* passed
  it, found it did not, and built a pair whose target already carried the change. That is a second
  mislabel route, distinct from the one W117 found, and it is closed by the same rule.

Inside the corpus, none of this changes an answer: all eighteen resolutions that moved answer `False`
before and after, as above.

## `sync.route.templates._call_at` — the two now diverge, and that is correct

The benchmark's docstring already said the two differ in that the route accepts a merely-containing
call as a fallback. They now differ in the tie-break too. Measured on three shapes:

| shape | `route._call_at` | `mutate._call_at` |
|---|---|---|
| `stripe.charges.list({limit:3}).autoPagingToArray({limit:5})` | the pager | the operation's call |
| `stripe.charges.list({limit:3}).then(h)` | the operation's call | the operation's call |
| `wrap(cfg)({ receipt_email: 'x' })` | the outer call | the inner call |

The divergence is correct because the two answer different questions. The route asks *which call can
this edit act on*, and `omit_property_at` removes a property from an object argument — so a curried
`wrap(cfg)({...})` genuinely wants the outer call, which `_preferred`'s own docstring argues at
length and which nesting depth could never express. The benchmark asks *which call did the indexer
record*, which has exactly one answer and is never the outer one on a chain. A single rule serving
both was right for one of them.

**One observation about the route, not acted on because `templates.py` is not this task's to
change.** The first row is the same class of defect the benchmark just fixed: `_preferred`'s
object-argument key does not discriminate when the pager takes its own options, so length decides
and `omit_property_at` would remove the property from `autoPagingToArray`'s options rather than from
`list`'s. Row two is why it has not been noticed — `.then(h)` passes no object, so the first key
separates them there. This is reported rather than repaired; it is a change to the remediation path
and belongs behind its own argument.

## Candidate 3 weighed and declined, with the reason it is two operations

W117 rejected candidate 3 — widening the generator to express a nested change — as out of scope
because it regenerates the frozen ruler, and pointed it here on the grounds that this task
regenerates it anyway. Taking it would have been wrong, and the brief's own test is what decides it:
one operation or two.

It is two, on four counts:

- **It needs a second regeneration with a second argument.** This one produced a byte-identical
  score and an argument for why nothing moved. Candidate 3's would move numbers. Landing both in one
  commit makes any movement unattributable to either.
- **It needs the selection rule widened as well as the generator.** No committed specification names
  a nested field because `changed_field` takes the leaf; expressing one also requires
  `build_corpus_specs.py` to choose nested properties, which means reading nested schemas out of the
  pinned document.
- **Its whole point is to make precision able to fall, and precision is floored at exactly
  1.0000.** `scripts/gate_corpus.py` carries no tolerance by design. A pair that gives the partial
  path match something to fire on is a pair that can trip that floor, and moving a floor is a
  separate reviewable act the gate's own docstring prescribes: restate the recorded figure beside
  the change that moved it.
- **The fix is the deliverable and it is complete without it.** Candidate 3 is an opportunity that
  became available, not an obligation that came attached.

It remains the right next task on the corpus axis, and W117's measurement — five of seven reachable
negatives in the pinned checkouts would give a partial path match something to fire on, with no
repository fabricated — is still the argument for it.

## Which assertions changed direction, and why that is not weakening them

Eight of the twelve. Six were equalities over the whole mutated file asserting the field landed
inside the pager's argument list; they now assert it lands in the operation's own. They are still
whole-file equalities, still paired with the negative form, and the Python ones are still parsed with
`ast` rather than only compared — the strength of the assertion is identical and only the expected
value moved. Two are new and could not have been stated before, because the old resolution made both
questions unanswerable: `depends_on_change` answering `False` on a pager-only dependency, and
`generate_pair` refusing a site that already passes the field on the operation's own call.

The four that did not change direction are what make the other eight a statement about chaining
rather than about these call shapes: the two unchained controls assert the same text they asserted
before, and the two audit-half agreements hold in both regimes.

Two tests are new beyond those: the shape `virtual-lab` actually writes
(`list(self.client.customers.list(params={...}).auto_paging_iter())`, a two-segment client root with
the pager's result handed to `list`), and a three-call chain, which is what separates "prefer the
receiver" from "prefer the second-longest".

## Every assertion was proved able to fail, including against the defect returning

Six mutants, one per claim, applied to a copy of the tree and reverted afterwards. Baseline
`exit=0 passed=12 failed=0` before and after restore, and the failing node ids collected per mutant
rather than only the counts — a count cannot show that *every* test was covered, only that some were.

| mutant | verdict | detail | aimed at |
|---|---|---|---|
| `reinstate-the-old-tie-break` | killed | 8 failed | every assertion that changed direction fails when the defect returns |
| `recorded-shape-accepts-any-root` | killed | 8 failed | the callee has to flatten to an identifier, not merely stop somewhere |
| `python-keyword-insert-declines` | killed | 4 failed | the Python mutation attaches, and to which call |
| `ts-property-insert-declines` | killed | 4 failed | the TypeScript mutation attaches, and to which call |
| `audit-half-ignores-keywords` | killed | 2 failed | the audit half reads the Python keyword branch |
| `audit-half-object-branch-declines` | killed | 6 failed | the audit half reads the object-literal branch |

Twelve of twelve distinct tests proved able to fail. No mutant produced a false-verdict mode: nothing
failed to compile, nothing exited outside `{0,1}`, no pass count drifted, and every anchor was
checked for being unique in the file before it was applied, so an ambiguous target could not be
misread as a survival.

**The first mutant is the one that matters**, and it is the check the brief asked for against a pin
that keeps passing. It is `_call_at`'s body as committed at `995e05a`, byte for byte, not a
perturbation of it. It kills exactly the eight assertions that changed direction and leaves the two
unchained controls and the two audit-half agreements green — which is simultaneously the evidence
that the changed assertions genuinely describe the fix, and the evidence that the fix does not
regress the ordinary single-call site.

`src/sync/benchmark/mutate.py` is byte-identical after the run: `git diff --exit-code` exits 0.

Scheduler: `-n0` (serial) for every pytest run, in the harness and in the focused runs. The full
suite before committing was the default scheduler from `addopts`. The corpus runs are
`scripts`-level and single-process. Score DSN `sync_w121_score`, graph DSN `sync_w121`, both created
by this task and neither shared with another.

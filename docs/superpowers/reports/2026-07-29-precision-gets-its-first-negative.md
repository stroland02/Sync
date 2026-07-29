# Precision gets its first negative, and declines it

**Date:** 2026-07-29
**Scope:** B32 — hold a same-operation call site back from the mutation, so binding precision has
something it could be wrong about.
**Outcome:** built and measured. `falsifiable negatives` moves from 0 to 3, binding recall's
denominator moves from 12 to 9, and precision stays at 1.0000 — which is now a result rather than
an artefact.

## The numbers, both axes, before and after

`benchmark/corpus/recorded/2026-07-29-falsifiable-negatives.txt` is the before and
`2026-07-29-held-back-negatives.txt` is the after. Each is byte-identical across two runs from two
freshly created databases.

| | before | after |
|---|---:|---:|
| binding precision | 1.0000 | 1.0000 |
| precision's n (findings judged) | 12 | 9 |
| **falsifiable negatives** | **0** | **3** |
| binding recall | 1.0000 | 1.0000 |
| recall's n (call sites genuinely affected) | 12 | 9 |
| call sites affected | 12 | 9 |
| call sites unaffected | 94 | 97 |
| unlabelled findings | 0 | 0 |
| pairs specified / scored | 12 / 10 | 12 / 10 |
| excluded pairs | 2, both `displaced-label` | 2, both `displaced-label` |

```
sha256  1694c3a21f25fad839a47d32c2c1c1b4b1125b718a49a52686c7397d903a4001  ...held-back-negatives.txt
sha256  fb57291738e7d27277083733107cfe4ba55f1e93c25cfab585fc01adf312b664  ...held-back-negatives.json
```

**Recall did not fall.** Its denominator moved, because three call sites that used to be broken
are now deliberately not broken. Nine of nine affected sites produced a finding, the same as
twelve of twelve did. A reader handed only the rates cannot tell that apart from a regression,
which is why both denominators are in the table.

**Precision did not move either, and that is the first time that has meant anything.** Before,
the corpus held no negative the detector could fire on, so 1.0000 was guaranteed by construction
and would have survived a binder regression that only affected same-operation discrimination.
After, three same-operation call sites were offered to the binder with a non-empty argument list
each, and it claimed none of them. One is a genuine near miss rather than a formality: `turbo`
passes `amount` at `src/routes/arnsPurchaseQuote.ts:223`, and the changed property is
`amount_details`. A field match on segment prefixes rather than on whole segments fires there.
`_leads_into` compares whole segments, so it declines.

## How the hold-back is declared, and why that shape

Two decisions, and the second is the one the brief called the design question.

**The mechanism.** A pair specification may carry a `hold_back` key, a list of entries naming a
`path`, a `line` and a `col`. `sync.cli._corpus_targets` resolves each against the indexed call
sites on the changed operation and drops it from the target list. Everything else about the
harness is unchanged: `generate_pair` still takes its targets from the caller and still refuses to
choose them, which is what B31 said it would need and it needed nothing.

```yaml
hold_back:
- col: 33
  line: 223
  path: src/routes/arnsPurchaseQuote.ts
```

**By position rather than by call site id**, because a position is checkable by a reader against
the pinned commit and an id is a hash of one. `02c042e6fed8dd5f4a0100d6c9fe01f5` is exact and says
nothing; a path and a line can be opened.

**Named in the specification rather than derived by the harness**, which is the same argument
`_score_corpus` already makes for why it takes a file instead of eight flags: which sites a corpus
breaks is a distribution, and a harness that picked one would be choosing it without saying so.
There is a real cost to the alternative here and it is not stylistic — a rule applied at scoring
time would silently move recall's denominator on every specification at once, including ones
written before the rule existed.

**The rule that chose them is executable and lives in `scripts/build_corpus_specs.py`**, which is
already the record of how the field was chosen. `hold_back(sites, kind)` returns the first call
site on the changed operation by `(path, line, col)`, when the operation has more than one indexed
call site and that site carries a non-empty field list on the side the change is on. One per
specification, never more. That mirrors what the corpus already does with `field`: a stated rule
in the generator, its concrete answer frozen into the committed specification, and a header
comment in the file naming the rule that produced it.

Each clause earns its place:

- **First by position**, because every insertion `mutate.py` makes lands at or after the call it
  breaks, and `upsert_call_site` keys a call site's identity on its position. Only the earliest
  site on the operation is guaranteed to still be at the position the specification names once its
  siblings have been mutated. This is not hypothetical: `furever-GetCharges` is excluded from the
  score today because one response guard inserted above three later calls displaced all three
  labels.
- **Non-empty field list on the change's side**, because that is the branch
  `VendorChangeDetector.scan` takes, and `_deepest_match` over an empty list declines against every
  change there has ever been. Holding such a site back costs a positive and buys no candidate.
- **More than one site on the operation**, because holding back the only one leaves the mutation
  nothing to break and the pair is refused outright.
- **One and never more**, because every held-back site is a site recall no longer measures.

Running the generator again rewrote four of the twelve specifications and left the other eight
byte-identical, which is the check that the rule is the whole of the choice.

## Three is the maximum available, not a minimum I picked

The brief asked for the minimum that makes precision falsifiable. It turns out there was no
choice to make: three is simultaneously the floor and the ceiling this corpus can offer.

- **Every response-side pair is out.** All five scored response pairs read no response field at
  any call site on the changed operation — that is the same fact that makes the response mutation
  unable to attach anywhere, since it attaches where the result is bound in a declarator and the
  indexer records `response_fields_read` in exactly that place. A site held back there carries an
  empty field list and declines against every change, so it is a silent negative rather than a
  falsifiable one.
- **Two request pairs have one site each.** `remix-PostPaymentIntents` and `turbo-PostRefunds`
  index a single call site on the changed operation. Holding it back empties the target list and
  the whole specification leaves the score.

That leaves `fireship-server-PostPaymentIntents`, `furever-PostPaymentIntents` and
`turbo-PostPaymentIntents`, all request-side, all with two or more sites. Three held back, three
falsifiable negatives, three positives given up.

A fourth specification carries a `hold_back` entry and contributes nothing:
`furever-GetCharges-response-property-removed` is the one response pair whose call sites do read a
response field, so the rule selected it, and it is excluded from the score as `displaced-label`
both before and after. The rule does not know which pairs the harness will refuse and should not —
one that skipped them would be selecting on the outcome.

## Every held-back site is genuinely unaffected, and here is the reading

This was the one unrecoverable mistake available: a site that genuinely reads the changed property
labelled a negative would corrupt the ground truth every future score is compared against. Three
independent things say it did not happen.

**Structural.** An untargeted site is never passed to `_mutate`, so no edit writes the dependency
into it.

**Already enforced, and not by me.** `generate_pair` walks *every* site in the tree — not only its
targets — and raises when one already carries the changed field.
`tests/test_mutation_pairs.py::test_a_site_that_already_depends_on_the_changed_field_is_refused`
pins that on a non-target specifically. Every one of these pairs generated, so none did.

**Read back out of the mutated tree.** `depends_on_change` answers what the source now says about
one named call site, independently of what the generator recorded. Run against each held-back
position, in both the original and the mutated tree:

| pair | held-back site | depends, original | depends, mutated |
|---|---|---|---|
| `fireship-server-PostPaymentIntents-request` | `src/payments.ts:8:32` | False | False |
| `furever-PostPaymentIntents-request` | `app/api/setup_accounts/create_charges/route.ts:104:28` | False | False |
| `turbo-PostPaymentIntents-request` | `src/routes/arnsPurchaseQuote.ts:223:33` | False | False |
| `furever-GetCharges-response` | `app/api/list_charges/route.ts:16:26` | False | False |

Two of those files do contain the string `amount_details` after the mutation, because a *sibling*
call in the same file was broken. That is why the check has to be `depends_on_change` at the named
position rather than a search of the file: the coarser question answers True and means nothing.

## What was not built

**No threshold and no gate.** `2026-07-27-sync-benchmark-gates.md` forbids inventing one, and a
floor on precision would still need a variance measurement over the new corpus before it could
mean anything. Three candidates is a small denominator to gate on even once that exists.

**No change to the rendered caveat.** `score_corpus.render` prints "binding precision above is not
a measurement" only while `falsifiable negatives` is zero, which B31 built deliberately — a caveat
that prints unconditionally is a banner and the next reader learns to skip it. It is now absent
from the recorded output, which is the intended behaviour and worth saying out loud since its
disappearance is the largest visible diff in the report text.

**Nothing under `src/sync/graph/`, `src/sync/remediate/`, `src/sync/core/conformance.py`, or
`sync.benchmark.mutate._result_binding`.** The last is B29's, and the response-side coupling
described above is a fact this task measured rather than a change to that function.

## The denominator will move again

B29 is extending response-side binding, which is intended to turn currently-unreachable response
targets into labelled positives. This change removed three positives; that one adds some. The
numbers above are the delta against the corpus as it stands today and are not a prediction of the
combined figure — reconciling the two after both land is the coordinator's, deliberately.

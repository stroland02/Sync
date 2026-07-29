# The response axis exists, and the first thing it measured was a hole in the binder

**Date:** 2026-07-29
**Scope:** B29 — give the response half of the frozen corpus a sample, so binding recall stops
describing only request-side breaks.
**Outcome:** eight response-side positives where there were none, no pair excluded, and recall
falls from 1.0000 at n=12 to 0.8000 at n=20 because the corpus can now ask a question it could
not ask before.

## Read this line first

**Recall's denominator moved: n=12 → n=20.** The two rates are not comparable and the fall is not
a regression. Twelve request-side positives are unchanged and all twelve are still found. Eight
response-side positives are new, and four of them are missed.

## What `_result_binding` was actually missing

The brief's diagnosis — that it recognised only `const` and `let` — is correct as far as it goes
and accounts for **four of the eleven** unreachable targets. I located all eleven in source before
building. They fall into three classes, not one:

| shape | count | example |
|---|---:|---|
| bound by a plain assignment | 4 | `paymentIntent = await stripe.paymentIntents.create(` — `furever` ×2, `turbo` ×2 |
| result discarded | 5 | `await stripe.paymentIntents.create({…});` — `furever` ×4, `turbo` ×1 |
| result returned | 2 | `return stripe.paymentMethods.list({…})` — `fireship-server`, `remix` |

Only the first class is a generator limitation. The other seven are **correctly labelled
unaffected and must stay that way**: a call that never reads the response is not broken by a
response property being removed. Turning either class into a positive would mean restructuring the
tree into a shape nobody wrote, and the label would then describe the restructuring rather than a
dependency the vendor's change breaks — which is the one unrecoverable mistake this task had
available.

So the second cause mattered more than the first, and it was not in `_result_binding` at all.

## The displacement, handled rather than discovered

The response guard occupied three lines of its own. `upsert_call_site` keys identity on line and
column, so every call below the mutation became a different row and its label addressed nothing.
That is what refused `furever-GetCharges-response-property-removed` and
`fireship-server-PostPaymentIntents-response-property-removed` outright — and, left alone, it would
have converted the four newly-reachable targets into fresh `displaced-label` exclusions rather than
into positives, which is precisely the failure the brief said to report rather than paper over.

**The guard is now appended to the statement it follows and occupies no new line.** That removes
the interaction rather than trading it.

The alternative — keying call-site identity on something stable across insertion — was rejected
and the reason is worth keeping. The key belongs to `sync.graph` and every stage depends on it. A
benchmark that needed the production identity changed in order to score itself would be measuring
a pipeline nobody runs, and the corpus is a consumer of that key rather than an author of it.

Accepting the limit and declaring which files can carry a response-side pair was the third option
and is now unnecessary: all of them can.

One narrower case survives deliberately. Two calls **on one line** still displace, because the
guard adds characters before the second call's column. It is refused, correctly, and
`tests/test_binding_score.py` now asserts `DisplacedLabel` against exactly that shape — its
previous premise was the guard occupying lines, and a refusal whose common case has disappeared is
no longer being tested at all.

## The numbers

`benchmark/corpus/recorded/2026-07-29-response-axis.{txt,json}`, byte-identical across two runs
from two freshly created databases:

```
sha256  8d5b39830546b2d5958f72f310cc358aa97eeb0807f3dff731a1a2ebde0e11ff
```

| | before | after |
|---|---:|---:|
| pairs scored | 10 | **12** |
| pairs excluded | 2 (`displaced-label`) | **0** |
| call sites affected | 12 | **20** |
| binding precision | 1.0000 n=12 | 1.0000 n=16 |
| binding recall | 1.0000 n=12 | **0.8000 n=20** |
| unreachable targets | 11 | **7** |
| falsifiable negatives | 0 | 0 |

Of the eleven unreachable targets: **four became labelled positives**, **zero became
`displaced-label` exclusions**, and seven remain unreachable for the two honest reasons above. The
two pairs that were previously excluded entirely now score, contributing four more positives — so
the eight new positives are four from reachability and four from un-exclusion.

Every response-side pair that scored ran the `UnbrokenLabel` check, which re-reads the dependency
out of the mutated source rather than trusting the edit record. None raised, so all twenty
positives describe dependencies the tree genuinely carries.

## What the response axis caught immediately

Recall's four misses are all response-side, and they are a **defect in the binder, not in the
corpus**.

`sync.index.typescript._response_fields` walks up from the call to a `variable_declarator` and
returns `[]` if it does not find one. So a call whose result is assigned to a variable declared
earlier records no response fields at all. Measured directly, with the identical guard on both:

```
const intent = await stripe.paymentIntents.create({…}); if (intent.amount_details === undefined) …
  ->  response_fields_read = ['amount_details', 'id']

let intent;
intent = await stripe.paymentIntents.create({…}); if (intent.amount_details === undefined) …
  ->  response_fields_read = []
```

**No response-side vendor change can be detected on that shape in production.** It is the same
limitation the generator had, on the other side of the pipeline, and the corpus could not see it
until the generator's half was fixed — the generator and the binder were blind in the same place,
so the benchmark agreed with the binder by construction.

That is the whole value of this task, and it argues for the shape of the next one: fixing
`_response_fields` should be measured against **this** corpus, by someone who is not also changing
the corpus. Fixing it here would have destroyed the evidence — the recall miss is what proves the
gap exists.

## Found and deliberately not fixed

- **`_response_fields` in `sync/index/typescript.py`**, above. Outside this task's boundary, and
  fixing the binder in the change that first gave the corpus the ability to see the gap would mean
  measuring my own fix. Recall should return toward 1.0 when it lands, over an unchanged n=20.
- **The five discarded and two returned results.** Correct as unaffected; not a sample to recover.
- **Two calls on one line still displace.** Real, rare, correctly refused, and asserted.
- **`falsifiable negatives` is still 0**, so binding precision remains a constant over this corpus.
  That is B32 and untouched here; nothing in this change adds or removes a negative the detector
  could have fired on.

## Boundaries

`src/sync/cli.py`, `src/sync/graph/`, `src/sync/remediate/` and `src/sync/core/conformance.py` were
not modified. `src/sync/index/typescript.py` was read and measured, not edited.

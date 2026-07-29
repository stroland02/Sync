# The depth measurement, re-run: the count is not a property of the window

`2026-07-29-measurement-provenance.md` pinned the two inputs and reported that the corpus stated
this measurement two ways:

> `src/sync/signals/stripe/adapter.py` records "86,368 of 107,396 records between v2320 and
> v2330" beside `NOISE_KINDS`, while the design document records 672,286 raw and 327,124 filtered
> over what the duplicate specifications collapse to the same window. Both cannot be a count of
> the same thing.

Both can, and both are. **They are two draws from a nondeterministic process.** Running the same
command on the same hash-verified bytes nine times produced nine different counts spanning a
factor of thirty-one, and both documented figures fall inside that range. Neither is wrong in the
sense of having been miscounted; both are wrong in the sense of being reported as facts about a
window when they are facts about a run.

Nothing here is a correction of one figure by another. Every absolute record count over this
window has to go, including the ones this document produced.

## The inputs

Fetched by the pinned path and verified before use:

```
$ uv run python scripts/fetch_measurement_inputs.py --measurement breaking-record-depth-327124
.cache\specs\v2320.json fetched (7830636 bytes, blob c5d6078dd0b1)
.cache\specs\v2330.json fetched (7866866 bytes, blob 634a4b329a8e)

2 inputs verified against their pins.
```

Both blobs match the provenance table. `oasdiff version 1.26.0`, the binary in `tools/`.

## The command, run nine times

Exactly what `run_oasdiff_breaking` runs — `oasdiff breaking <base> <revision> --format json`, no
flags, no filter — against those two files, in one session, on one machine, with nothing else
changing between runs.

| run | raw records | after the noise filter | `response-property-enum-value-added` | `response-optional-property-removed` |
|---|---:|---:|---:|---:|
| 1 | 43,496 | 8,248 | 35,248 | 8,248 |
| 2 | **1,375,504** | 676,580 | 698,924 | 676,580 |
| 3 | 145,354 | 9,248 | 136,106 | 9,248 |
| 4 | 292,322 | 8,576 | 283,746 | 8,576 |
| 5 | 127,520 | 24,756 | 102,764 | 24,756 |
| 6 | 76,402 | 6,656 | 69,746 | 6,656 |
| 7 | 68,318 | 33,848 | 34,470 | 33,848 |
| 8 | 180,340 | 31,112 | 149,228 | 31,112 |
| 9 | 29,768 | 8,496 | 21,272 | 8,496 |

**Lowest 29,768, highest 1,375,504.** The two documented figures — 107,396 and 672,286 — both sit
inside that interval, which is the whole explanation of the disagreement. So does every number
this document measured.

The two counts do not co-vary: run 6 has the third-highest raw count and the lowest filtered one,
run 7 the reverse. The walk reaches different regions of the schema each time, not merely more or
less of the same region.

## Why it varies

The changed properties sit inside a cyclic schema graph, and how far a run walks it before the
cycle guard stops is what the record count measures. The deepest path from one run:

```
data/items/action/collect_payment_method/payment_method/sepa_debit/generated_from/setup_attempt/
setup_intent/on_behalf_of/external_accounts/data/items/customer/subscriptions/data/items/
latest_invoice/payments/data/items/payment/payment_record/payment_method_details/card/
stored_credential_usage
```

Twenty-six segments, twenty distinct: `data` and `items` each appear four times. A subscription's
latest invoice's payment's payment-record's card leads back to a customer with external accounts
whose data items have customers, and so on. Four underlying schema changes are re-reported once
per distinct route to them, and the number of routes a run finds is not fixed.

That is consistent with everything above and with the design document's own phrasing — "exploded
across … distinct paths under `error/payment_method/card/generated_from/…`" is a description of a
cycle. The observed maximum depth moves with the count: 32 in one run, 22 in another.

## What is stable, and it is the part the argument rests on

Measured on two independent runs whose raw counts differ by a factor of 2.3 (68,318 and 29,768):

| property | run A | run B |
|---|---|---|
| distinct change kinds | 2 | 2 |
| filtered records at depth 1 | **0** | **0** |
| shallowest filtered record | **3 segments** | **3 segments** |
| distinct leaves after filtering | **4** | **4** |
| which leaves | `description`, `iin`, `issuer`, `stored_credential_usage` | the same four |
| records per leaf | 8,462 each | 2,124 each |

And from a single run, which the count instability does not touch because they are properties of
the specification rather than of the walk: **587 distinct `operationId`s** and **414 distinct
paths**, every record on a `/v1/` path, every record `warning` level in oasdiff's own catalogue.

The four leaves appear in exactly equal numbers within every run. That is the signature of one
change per leaf re-reported once per route: the routes are shared, so the counts move together.

The noise filter and the depth floor turn out to be the same cut. In both runs where both were
measured, the number of depth-1 records equals the number of `response-property-enum-value-added`
records exactly — 34,470 and 21,272 — so the filter removes precisely the depth-1 population and
nothing else. "None is depth-1" after filtering is therefore not a coincidence of this window; it
is what the filter does.

**The structural claim reproduces and the counts do not.** "None is depth-1", "the shallowest is
three segments", and "the whole population reduces to four underlying schema changes — leaves
`description`, `iin`, `issuer` and `stored_credential_usage`" are all reproducible, and they are
what the detector's path-anchoring rests on. The claim that no static indexer reaches that depth
survives untouched.

## What each of the two disagreeing figures actually counts

Neither counts something the other does not. Both count `oasdiff breaking` records over
`v2320 → v2330` after or before one noise kind, and both are internally consistent:
86,368 + 21,028 = 107,396, and 672,286 − 327,124 = 345,162. The window is the same one; the
duplicate blob hashes in the provenance table confirm `v2300` and `v2320` are byte-identical, so
there was never a second window to confuse it with.

What separates them is the run, not the question. A third possibility worth ruling out explicitly:
they are not different invocations. Flags do change the count — `--flatten-allof` gave 126,925 and
`--flatten-allof --flatten-params` gave 278,774 on this pair — but the spread from flags is
smaller than the spread from repetition alone, and neither documented figure needs a flag to be
explained.

## The median is not reproducible either

`2026-07-25-sync-self-maintaining-apis-design.md` states "the median about twenty-five". Measured
here: **24** in one run and **15** in another. The median tracks how deep the walk got, so it is a
property of the run in exactly the way the counts are. The minimum is not — it was 3 in both, and
3 is what the argument needs.

## What this means for anyone re-taking it

A count over this window is not a measurement. It is a sample, and reporting one without its
distribution is what produced two irreconcilable numbers in one corpus. If a count is ever needed
here, it needs a stated number of runs and a stated spread, and the honest summary of nine runs is
that the interval is 29,768 to 1,375,504 and the shape of the distribution is unknown.

The properties that are stable — zero at depth 1, minimum depth 3, four leaves, 587 operations,
414 paths — are the ones worth citing, and they are the ones the corpus actually uses.

## What was corrected, and what could not be

**Corrected.** `2026-07-25-sync-self-maintaining-apis-design.md`, the two sentences carrying
672,286, 327,124, 295,848, 81,781, 7,468 and "median about twenty-five". The structural claims in
those paragraphs are unchanged because they reproduced.

**Not corrected, and named here instead.**

- `src/sync/signals/stripe/adapter.py` carries "86,368 of 107,396 records between v2320 and
  v2330" beside `NOISE_KINDS`, and `src/sync/detect/vendor_change.py` cites "327,124 breaking
  records after noise filtering" twice. `src/` was outside this task's granted files. Both are
  citations of counts this document shows are not reproducible; the surrounding arguments in both
  are structural and survive.
- `docs/superpowers/plans/2026-07-25-sync-m0-vendor-change.md` states 107,396 / 86,368 / 21,028 in
  three places. A plan is a record of what was believed while it was executed, and editing one
  rewrites that record rather than correcting a claim; it is left alone deliberately.
- The two spec audit logs refer to "the 327,124-record depth measurement" as the *name* of the
  measurement they could not verify, not as an assertion of its value. Renaming it there would
  make the audit trail harder to follow, not easier.

## Reproducing this

```
uv run python scripts/fetch_measurement_inputs.py --measurement breaking-record-depth-327124
tools/oasdiff.exe breaking .cache/specs/v2320.json .cache/specs/v2330.json --format json
```

Run it more than once. The point of this document is what changes between those runs.

Nothing here touches the database, and no test added by this work fetches anything: the vendor
artifacts are fetched by the documented script, outside the suite, exactly as
`2026-07-29-measurement-provenance.md` established.

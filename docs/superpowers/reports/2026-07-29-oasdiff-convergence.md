# The convergence curve, and what it does to the proposed fix

**Date:** 2026-07-29
**Answers:** `2026-07-29-oasdiff-determinism.md` §6, which recommended a union over N runs and named
the curve as the one thing missing before it could ship.

**The union converges at one level and not at the other, and that split kills option (1) as it was
written.** Operation-level coverage converged on run 1 and did not move across 23 further runs. The
natural-key union — the rows that would actually be written — was still growing on run 24, at
2,135,168 and climbing. Nesting held on every run.

24 runs, 1,949 seconds, oasdiff 1.26.0, the pinned `v2320 → v2330` pair with both blob hashes
verified before the first run.

## 1. The curve

| run | records | rows | key union | new keys | ops | op union | new ops | nested | secs |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 1 | 146,888 | 146,888 | 146,888 | 146,888 | 1,174 | 1,174 | 1,174 | yes | 103.8 |
| 2 | 33,412 | 33,412 | 177,278 | 30,390 | 706 | 1,174 | 0 | yes | 6.0 |
| 3 | 397,536 | 397,536 | 560,732 | 383,454 | 1,174 | 1,174 | 0 | yes | 118.0 |
| 4 | 58,820 | 58,820 | 578,438 | 17,706 | 1,174 | 1,174 | 0 | yes | 38.7 |
| 5 | 145,556 | 145,556 | 579,878 | 1,440 | 1,174 | 1,174 | 0 | yes | 59.9 |
| 6 | 7,194 | 7,194 | 585,652 | 5,774 | 394 | 1,174 | 0 | yes | 17.2 |
| 7 | 737,850 | 737,850 | 1,277,666 | 692,014 | 1,174 | 1,174 | 0 | yes | **672.3** |
| 8 | 53,442 | 53,442 | 1,312,862 | 35,196 | 368 | 1,174 | 0 | yes | 19.7 |
| 9 | 50,280 | 50,280 | 1,356,416 | 43,554 | 432 | 1,174 | 0 | yes | 183.9 |
| 10 | 57,870 | 57,870 | 1,398,564 | 42,148 | 783 | 1,174 | 0 | yes | 22.0 |
| 11 | 21,232 | 21,232 | 1,400,448 | 1,884 | 737 | 1,174 | 0 | yes | 5.1 |
| 12 | 31,792 | 31,792 | 1,427,886 | 27,438 | 428 | 1,174 | 0 | yes | 83.0 |
| 13 | 17,962 | 17,962 | 1,430,342 | 2,456 | 1,174 | 1,174 | 0 | yes | 25.4 |
| 14 | 10,978 | 10,978 | 1,431,026 | 684 | 737 | 1,174 | 0 | yes | 4.7 |
| 15 | 10,360 | 10,360 | 1,437,746 | 6,720 | 364 | 1,174 | 0 | yes | 17.1 |
| 16 | 29,842 | 29,842 | 1,444,152 | 6,406 | 1,174 | 1,174 | 0 | yes | 5.5 |
| 17 | 101,818 | 101,818 | 1,513,040 | 68,888 | 682 | 1,174 | 0 | yes | 15.6 |
| 18 | 328,282 | 328,282 | 1,823,992 | 310,952 | 1,174 | 1,174 | 0 | yes | 59.9 |
| 19 | 297,342 | 297,342 | 1,962,560 | 138,568 | 1,174 | 1,174 | 0 | yes | 87.6 |
| 20 | 49,504 | 49,504 | 1,964,444 | 1,884 | 276 | 1,174 | 0 | yes | 88.5 |
| 21 | 15,062 | 15,062 | 1,964,444 | **0** | 1,174 | 1,174 | 0 | yes | 13.5 |
| 22 | 106,828 | 106,828 | 2,049,332 | 84,888 | 775 | 1,174 | 0 | yes | 28.6 |
| 23 | 27,526 | 27,526 | 2,050,556 | 1,224 | 688 | 1,174 | 0 | yes | 6.5 |
| 24 | 314,834 | 314,834 | 2,135,168 | 84,612 | 1,174 | 1,174 | 0 | yes | 266.7 |

Reproduce with `uv run python scripts/measure_oasdiff_convergence.py --runs 24`.

## 2. Operation-level coverage: converged, immediately and completely

**1,174 on run 1, and zero new operation-level rows across all 23 runs that followed.** The
`(kind, path, operationId)` union never moved. That is a strong result for the *coverage* question:
whichever operations are affected, repeated running finds them and stops.

**Nesting held on every one of the 24 runs**, which is what the determinism report said option (1)
rests on. No run ever contributed an operation-level row that a larger run had not found. The
failure mode is lost work, never invented work, confirmed over four times the sample that
established it.

But a single run cannot be trusted to have found them. Individual runs ranged from **276 to 1,174**
operations, and only **11 of 24 runs (46%)** reached full coverage. Run 20 found 276 of 1,174 — 24%
of the affected surface — and nothing in its output says so.

## 3. Natural-key rows: never converged

The key `upsert_vendor_change` hashes includes `raw["text"]`, and that is where oasdiff writes the
recursive property path. So the union of rows a union-over-N strategy would write is the union of
every distinct text any run produced, and it does not converge:

- After 24 runs: **2,135,168 rows**, growing by 84,612 on the final run.
- Exactly **one run out of 24** added zero new keys, and two runs later the union grew by 84,888.
- The last eight runs added 68,888 / 310,952 / 138,568 / 1,884 / 0 / 84,888 / 1,224 / 84,612.

There is no flattening. A union over N runs writes roughly N × 90,000 rows to `vendor_change` for
one vendor and one version pair, and each is a legitimately distinct natural key rather than a
duplicate the conflict clause can absorb.

**This is the finding that changes the recommendation.** Option (1) was proposed as a union over
runs, on the strength of nesting. Nesting is real, and it is a property of the *operation-level*
sets, not of the natural-key sets. At the level the rows are actually keyed, the sets are not
nested and the union does not converge.

## 4. What it costs

| | |
|---|---|
| mean run | **81.2 s** |
| fastest | 4.7 s |
| slowest | **672.3 s** (11 min 12 s) |
| 24 runs | 1,949 s (32 min 29 s) |
| peak memory, one run | **9.3 GB** resident, observed during run 7 |

The determinism report's 10–45 s estimate was measured over three runs and is low. The distribution
has a long tail in both directions, and run 7 produced 737,850 records — a **103× spread** against
run 6's 7,194, wider than the 46× the depth report found.

`2026-07-25-sync-latency-architecture.md` is binding on pipeline shape, and its rule is that every
agent must shorten the critical path or improve a result. A union strategy improves the result — it
recovers up to 76% of the affected operations a single run can miss — and it costs, per vendor per
invocation, N × 81 s on the mean with an observed single-run worst case of 11 minutes and 9.3 GB.
At any N large enough to be safe, this is minutes of serial work per vendor on a path the
architecture already describes as dominated by the customer's CI. It is affordable only because
SIGNAL is precomputable and off the per-finding path; it would not be affordable inline.

## 5. Is there a defensible N?

Read off the curve rather than chosen: full coverage was reached on runs
1, 3, 4, 5, 7, 13, 16, 18, 19, 21, 24. The longest observed run of consecutive partial results is
**five** (runs 8–12), so in this sample any window of six consecutive runs contained at least one
complete run.

**Six is not the answer and must not be recorded as one.** It is the maximum of one sample of 24
from a distribution whose shape is unknown, and `2026-07-27-sync-benchmark-gates.md` forbids exactly
this move — picking a number off a measurement and then justifying it. What the sample supports is
the *shape* of a rule, not its constant:

> Run until the operation-level union has been unchanged for K consecutive runs.

and the honest statement about K is that a sample where the worst observed gap is 5 cannot bound the
tail, so K would have to be justified by a stopping-criterion argument this measurement does not
supply. Establishing it needs the distribution, not a longer single sample.

## 6. What this means for the recommendation

Option (1) as written — union over N runs — **does not work on its own**, and the curve is why:

| goal | union over N runs |
|---|---|
| stable *coverage* (which operations changed) | works; needs a stopping rule with an unestablished K |
| stable *rows* (`vendor_change` contents) | **does not converge**; 2.1 M rows after 24 runs and growing |

The determinism report listed dropping `raw["text"]` from the natural key as option (2) and rejected
it as "wrong fix for this problem", because it does not recover the lost operations. That
assessment was right about what option (2) alone achieves and it now reads as the missing half
rather than a rejected alternative: **(1) recovers the coverage and (2) makes the rows converge, and
neither does the other's job.** Together the union stabilises at 1,174 rows, which is the number
both this curve and the determinism report arrive at independently.

That combination is what a follow-up should evaluate, and it has a real cost the report should not
hide: dropping the text from the key discards the property path `changed_field` reads, so the
combination needs somewhere else for that to live before it can ship.

**Until then the exemption stands**, and `2026-07-27-sync-pipeline-discipline.md` now records it.

## 7. What was verified rather than assumed

- Both input blobs hashed before the first run: `v2320.json`
  `c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3`, `v2330.json`
  `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d`, matching `scripts/fetch_measurement_inputs.py`.
- Nesting checked on every run rather than sampled, and reported per run in the table.
- The measurement is on 1.26.0. The determinism report established that 1.26.1 is unstable in the
  same way over three runs; this curve was not re-run on it, and **that is a gap.** The shape of
  the instability matched across versions, so the curve is expected to as well, but expected is not
  measured and 24 runs on 1.26.1 is another 32 minutes nobody has spent.
- One run consumed 9.3 GB. A memory ceiling was not tested, and a machine with less would have
  failed rather than produced a small answer — which would surface as a raised `RuntimeError`
  from `run_oasdiff_breaking` rather than as a silent undercount, so it fails in the safe
  direction.

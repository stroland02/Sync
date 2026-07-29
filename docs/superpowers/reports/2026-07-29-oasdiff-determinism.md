# Does oasdiff's nondeterminism reach VendorChange?

**Date:** 2026-07-29
**Answers:** `2026-07-29-depth-measurement.md`, which measured a 46× swing in raw record counts and
correctly stopped at "these are facts about a run, not about a window".

**Yes, and it breaks idempotence.** It reproduces on both oasdiff versions, it reaches
`vendor_change` rows rather than stopping at a count, and the noise filter removes the alarming
number while removing none of the reproducibility problem.

## 1. The version question, settled first

`.github/workflows/ci.yml:39` pins `OASDIFF_VERSION: 1.26.1`. `tools/oasdiff.exe` is **1.26.0**.
The depth report's nine runs were on 1.26.0 — the version CI does not use — so the instability had
to be re-measured on 1.26.1 before anything could be concluded.

**Both are unstable.** Same command, same two hash-verified inputs, one machine, one session:

| version | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| 1.26.0 | 58,906 | 193,934 | 184,636 |
| 1.26.1 | 106,036 | 33,914 | 215,126 |

So this is not "our local binary is wrong". The version discrepancy is real and worth closing on
its own merits — CI and local development should run the same differ — but it is not the cause and
fixing it would fix nothing here. **No version change is proposed by this report.**

Inputs verified before use: `v2320.json` blob `c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3`,
`v2330.json` blob `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d`, both matching
`scripts/fetch_measurement_inputs.py`.

## 2. It reaches VendorChange, and the natural key is why

`to_vendor_changes` filters nothing and maps every record to a row. The graph's natural key is

```python
_stable_id(vendor_id, from_version, to_version, kind, path_ptr, operation_id, raw["text"])
```

— and `raw["text"]` is exactly where oasdiff writes the recursive property path
(`error/payment_intent/customer/anyOf[subschema #2: Customer]/subscriptions/data/items/…`). A run
that expands one branch further than the last does not produce a differently-worded version of an
existing row. It produces a **new row**.

In every run measured, distinct records equalled total records: there are no duplicates for the
conflict clause to absorb.

| | 1.26.0 r1 | 1.26.0 r2 | 1.26.0 r3 | 1.26.1 r1 | 1.26.1 r2 | 1.26.1 r3 |
|---|---:|---:|---:|---:|---:|---:|
| records = rows | 58,906 | 193,934 | 184,636 | 106,036 | 33,914 | 215,126 |
| operation-level rows | 1,174 | 1,174 | 707 | 1,174 | 750 | 1,174 |

Pairwise on the real key, 1.26.0 run 1 against run 2: **23,674 shared, 35,232 only in the first,
170,260 only in the second.** Re-running SIGNAL on unchanged input does not converge on the same
rows; it appends tens of thousands of rows that were never there and leaves the previous ones in
place, because the conflict clause is `DO UPDATE` on an id that differs.

**This violates the idempotence rule in `2026-07-27-sync-pipeline-discipline.md`** — *"re-running
INDEX, SIGNAL or DETECT on the same input converges on the same rows"*. `efcc19d` was this bug
once already, from a different cause.

## 3. The failure mode is lost work, not invented work

The operation-level row sets are **strictly nested**. Sorted by size across all six runs, every
run's set is a subset of every larger run's:

```
1.26.0 run3:   707
1.26.1 run2:   750
1.26.0 run1: 1,174   1.26.0 run2: 1,174   1.26.1 run1: 1,174   1.26.1 run3: 1,174
every run is a subset of every larger run: True
```

Union 1,174, intersection 707 — **467 operation-level rows appear in some runs and not others.**
No run ever reported a row a larger run did not find. oasdiff truncates its walk early and loses
findings; it does not fabricate them.

That is the difference between a reproducibility problem and a correctness problem, and it is the
single most useful property here: it means a union over repeated runs converges upward on a fixed
answer rather than accumulating noise.

**467 findings that appear on one run and not the next is a false negative nobody can reproduce**,
which is the failure this system exists to prevent.

## 4. Where the exposure actually sits — not where the raw numbers suggest

Only two rule ids appear at all across all 792,552 records measured, and **both are `level: 2`**,
oasdiff's *warning*. This specification pair produces no level-3 records whatsoever.

| rule id | records across six runs | in `NOISE_KINDS`? |
|---|---:|---|
| `response-property-enum-value-added` | 738,972 (93%) | **yes — dropped** |
| `response-optional-property-removed` | 53,580 (7%) | no — kept |

The brief asked whether the variance concentrates in kinds the noise filter drops. It concentrates
there **by volume and nowhere near there by coverage**:

- After `NOISE_KINDS`, records fall to between **816 and 19,104** — still a 23× swing.
- Rows: union 27,956, intersection **596**. 27,360 vary.
- Operation-level: union 587, intersection 120. **All 467 varying operation-level rows are
  `response-optional-property-removed`** — the kind the filter keeps.

So the filter removes 93% of the frightening number and 0% of the reproducibility problem. The
depth report's observation that the enum kind "swings wildly" while optional-property-removed
"moves much less" is true of record volume and inverted for coverage: the enum kind produces the
volume, the other kind loses the operations.

**And `src/sync/signals/generated/adapter.py:314` applies no noise filter at all.** The four
generated vendors take the unfiltered set, so their exposure is the full 46× swing.

## 5. A second defect, found on the way and not fixed

`to_vendor_changes` stamps `severity="breaking"` on every record unconditionally. Every one of the
792,552 records measured is `level: 2` — a warning in oasdiff's own catalogue. So the severity on
a `VendorChange` from this source is a constant, not evidence, and a triage queue ordered by it is
ordered by nothing.

Not fixed here. Severity feeds routing and triage, and changing what it means has a blast radius
well outside this task's question.
`test_every_record_becomes_a_breaking_change_whatever_oasdiff_called_it` pins the current
behaviour so it is deliberate rather than accidental, and will fail when somebody acts on this.

## 6. What Sync should do about it

Not fix oasdiff — it is a pinned third-party binary, and this report characterises rather than
patches it. Four options, with what each costs:

1. **Union over N runs.** Sound *because* the sets are nested: the union converges upward on the
   1,174-row answer. Costs N× a 10–45 second diff, and picking N is picking a number — the
   benchmark spec's rule against inventing thresholds applies, so N would have to be justified by
   a measured convergence curve nobody has produced.
2. **Drop `raw["text"]` from the natural key.** Collapses 194,000 rows to 1,174 and makes the row
   set stable across runs that reach full depth. But it does not touch the 467 lost operations,
   and it discards the property path `changed_field` depends on. Wrong fix for this problem.
3. **Filter to `level: 3`.** Would drop everything from this pair, including the real
   `response-optional-property-removed` findings. Too blunt.
4. **Accept and record.** Treat SIGNAL as an at-least-once producer, state in the pipeline-
   discipline spec that oasdiff-derived `vendor_change` rows are exempt from convergence, and
   carry the exemption where somebody reads it.

**Recommendation: (1) with a measured N, and (4) in the interim.** The nesting property is what
makes (1) principled, and it is measured rather than assumed. What is missing before (1) can ship
is the convergence curve — how many runs before the union stops growing — which is a follow-up
measurement, not a guess.

**Spec correction to make, not made here** (`docs/superpowers/specs/` is forbidden to this task):
`2026-07-27-sync-pipeline-discipline.md`'s idempotence rule names SIGNAL, and SIGNAL does not
satisfy it for oasdiff-derived changes. That sentence needs the exemption or the rule needs the
fix; it should not silently be both.

## 7. What is pinned in tests

`tests/test_oasdiff_determinism.py`. Deliberately **not** an assertion that oasdiff is unstable —
that fails the day somebody fixes it, and two runs can agree by luck.

| test | claim | mutation that killed it |
|---|---|---|
| `..._adds_no_nondeterminism_of_its_own` | every difference came from the binary | per-call value into `raw` |
| `..._differing_only_in_their_message_are_two_changes` | the amplification mechanism | drop `text` from `raw` |
| `..._drops_the_volume_and_keeps_the_kind_that_loses_operations` | where exposure sits | empty `NOISE_KINDS`; widened `NOISE_KINDS` |
| `..._becomes_a_breaking_change_whatever_oasdiff_called_it` | §5, pinned not fixed | severity read from `level` |
| `..._are_nested_rather_than_divergent` | §3, opt-in | — |

Five mutations, five killed by exactly the intended test. The last test is behind
`SYNC_OASDIFF_DETERMINISM=1` because it costs ~116 s and its subject is a third-party executable;
it skips cleanly when the binary or the pinned specifications are absent, and it fails if oasdiff
ever starts producing divergent rather than nested sets — a worse problem than this one.

**One trap worth carrying forward.** The first two attempts at the purity mutation survived, and
both times the mutation was wrong rather than the test. `id(record)` is stable across calls, and
`time.monotonic_ns()` on Windows has ~15.6 ms granularity — two consecutive calls return the
identical value, measured. `time.perf_counter_ns()` does not. This is the same coarse-clock trap
as the `st_mtime_ns` rule in `CLAUDE.md`, in a different clock, and it has now cost this project
three separate investigations.

## 8. Commands, so a reader can re-run this

```bash
uv run python scripts/fetch_measurement_inputs.py     # if .cache/specs is empty

tools/oasdiff.exe breaking .cache/specs/v2320.json .cache/specs/v2330.json --format json > run1.json
tools/oasdiff.exe breaking .cache/specs/v2320.json .cache/specs/v2330.json --format json > run2.json

python - <<'PY'
import json
def rows(p):
    r = json.load(open(p, encoding="utf-8"))
    return (len(r),
            {(x["id"], x["path"], x.get("operationId") or "", x["text"]) for x in r},
            {(x["id"], x["path"], x.get("operationId") or "") for x in r})
n1, k1, o1 = rows("run1.json"); n2, k2, o2 = rows("run2.json")
print(f"records {n1:,} vs {n2:,}")
print(f"rows shared {len(k1 & k2):,} of {len(k1 | k2):,}")
print(f"operation-level shared {len(o1 & o2):,}; nested: {o1 <= o2 or o2 <= o1}")
PY

SYNC_OASDIFF_DETERMINISM=1 uv run pytest tests/test_oasdiff_determinism.py -q -n0
```

Two runs may agree by chance. The measurement in this report is six runs across two versions; a
single disagreeing pair is sufficient to reproduce the finding, and an agreeing pair refutes
nothing.

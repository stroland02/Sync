# Sync — the verification regime as the milestones close

**Date:** 2026-07-29
**Status:** Review of the existing corpus plus a sequence. Every status claim below was measured
against the running system on the date above, not read off another document.
**Scope:** What Sync's testing, measurement and production verification must become as M0–M3
close, and which parts are blocked on what.

## Why this document exists rather than a fourth benchmark spec

Three documents already carry most of this argument and none of them is superseded here:

- `2026-07-27-sync-benchmark-gates.md` defines the three gate tiers and the five quality axes,
  and states the rule that governs all of it — **do not invent a threshold.**
- `2026-07-28-sync-ground-truth-count.md` settled sample size for mined migrations.
- `2026-07-29-sync-ground-truth-quality.md` settled label quality and returned a verdict:
  mined Stripe migrations **cannot** serve as ground truth, and the fallback is synthetic
  mutation of real repositories.

What none of them does is state, in one place and against measurement, how much of the regime is
actually running. That gap matters now because the machinery is nearly complete and the corpus
is empty, and those two facts together are easy to mistake for progress.

## What is actually true, measured 2026-07-29

**The computation exists. The corpus does not.**

`src/sync/benchmark/` holds `axes.py`, `binding.py`, `mutate.py`, `report.py` and `score.py`.
`sync benchmark` is wired and reachable, and `--score-pair` generates a labelled pair from a
corpus specification and scores the pipeline against it. Every dead-links entry those modules
once held is gone.

Against the databases on this machine:

| | measured |
|---|---|
| databases holding pipeline rows | 48 |
| databases holding **any** `migration_outcome` row | **1** |
| rows in that table, total, everywhere | **3** |
| rows with a `pr_number` | **0** |
| rows with a `ci_result` | **0** |
| rows with `pr_merged` set | **0** |

The three rows are one finding and three attempts, written by `tests/test_pipeline_composes.py`
rather than by a run: `sdk_version` is `unknown`, `symbol_shape` is `<verb>`, and the third
attempt terminates `abandoned` with `abandon_reason` "the remediator produced no change".

So three of the five tier B axes — merge rate, routing accuracy, cost per merged patch — have a
denominator of zero and cannot be computed at all. Not "compute to a low number": they have
never had a sample. **The pipeline has never opened a pull request.**

This is not a defect. It is the honest state of a system whose acceptance run has not been
authorised to execute. But it has to be said plainly, because the shape of the failure it invites
is a founder reading `sync benchmark` output, seeing structure and column headings and no error,
and concluding something has been measured.

## The three blockers, and who owns each

### 1. No real run has produced an outcome row — owned by the user

`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request` is M0's definition
of done. It is `@pytest.mark.e2e` and deselected by `addopts`, so nothing in CI or in any
worker's gates has ever exercised it. Since it last ran, the pipeline gained the tier cascade,
the property-omit codemod, a push guard, branch deletion on abandonment, checkpoint serialiser
registration, the dependency-edit guard, staged-new-file support and dependency-tree discarding —
every one of them on the acceptance path.

**This is the unblocker for the entire measurement regime, not merely a milestone checkbox.**
The first real run is what puts the first row in `migration_outcome` with a `pr_number` in it,
and until one exists, three of five axes stay uncomputable no matter what else is built.

It stays user-gated for the reasons already recorded: it opens a pull request on a real
repository and spends `xhigh` model time. Run it with `-n0`, because `addopts` carries `-n auto`
and that applies to the e2e test too.

### 2. No frozen specimen corpus — **closed the same day this was written**

When this section was written, `--score-pair` took one specification and scored one pair, there
was no set, and nothing was frozen. All three are now false.

`benchmark/corpus/` holds twelve pair specifications over four repositories pinned by commit SHA
and validated by tree digest, and the whole set scores in one run. The reason freezing was
non-negotiable is the one `2026-07-27-sync-benchmark-gates.md` gives: a pair regenerated each run
scores a different input set each run, so a movement in the number means nothing.

What it measures today:

```
  pairs specified       12        pairs scored          12
  binding precision     1.0000    n=16
  binding recall        1.0000    n=16
  falsifiable negatives  4        paths not read        64
```

Three things happened on the way that are worth more than the numbers. The corpus caught a real
binder defect the moment its response half started measuring — recall fell to 0.8000 before the fix
because the corpus and the binder had shared a blind spot, so the benchmark had been agreeing with
the binder by construction. Precision was a **constant** until `hold_back` gave it negatives the
binder could fail on; it declined all four. And the fetcher's own pre-filter is gone, so the corpus
scores the vendor's subtree rather than a locally transformed copy of it.

### 3. No regression thresholds — deliberately, and still correctly

`2026-07-27-sync-benchmark-gates.md` records that the research pass which would have established
step detection, sample counts and noise handling died on a session limit on 2026-07-27, and draws
the right conclusion: **do not invent a threshold.** A gate at an invented number either fires
constantly and gets disabled or never fires and gives false assurance.

That rule holds and this document does not weaken it. The one gate available without statistics
is named there too — a directional floor on a deterministic axis, because binding precision over
a *frozen* corpus is deterministic given a fixed pipeline and a fixed input set, so a drop is a
real change rather than sampling noise.

**That gate is now available, and it needed two things rather than the one this section named.**
Blocker 2 closing was necessary and not sufficient. Determinism had to stop being an assumption —
it is now measured, byte-identical across four independent runs from clean databases. And
precision had to stop being a constant: while every same-operation site was targeted, no negative
existed that the binder could fail on, so a floor would have gated something that could never fire.
Queued as B36, with the distinction it turns on written down — a floor at the recorded value is
derived from measurement, a floor at a round number is invented and still forbidden.

## What "enhanced testing" should mean here, concretely

The suite is 1877 tests and green, the four gates run clean, and the conformance kit now covers
five protocols against nineteen shipped implementations. Adding more unit tests of the same kind
is not where the remaining risk is. The risk is concentrated in four places, and each has a
different instrument.

**Behaviour nobody has observed.** The pipeline end to end, against a real repository, producing
a real pull request. One acceptance run buys more information than any number of unit tests,
because every unit test in this repository asserts against a fixture the author chose. Blocker 1.

**Numbers computed over nothing.** An axis that reports a null for want of samples is honest; an
axis reported without its sample size is not. `axes.py` already reports sample size per axis and
`report.py` refuses to score without a reference — those refusals are the feature and must not be
softened when the first thin corpus makes them inconvenient.

**Rules that pass without exercising anything.** The conformance work found two live instances:
`check_vendor_adapter` certifies an adapter that resolves no symbol when `known_symbol` is
`None`, and `check_remediator` reads an empty diff as a decline, so a remediator that claims
everything and writes nothing satisfies it. Both were found only because someone asked why
everything passed. That question — *what would have failed here?* — is the one this project keeps
being rewarded for asking, and it belongs in the regime rather than in a person's habits.

**Environmental failures wearing a test's clothing.** Measured today: one suite peaked at 105
concurrent Postgres connections against a ceiling of 100, and the resulting
`psycopg.OperationalError` landed on whichever database-touching test happened to be running. It
moved between runs and survived every soak, so it read as a flaky test for hours across two
coordinators. Raising the ceiling to 300 fixed it and cut suite wall clock from 187s to 103s —
the limit had been costing retries throughout, not only the visible failures. **A red gate whose
failure is a connection error is not evidence about the code**, and the regime should say so where
people will read it rather than leaving each person to rediscover it.

## Sequence

1. **Freeze a specimen corpus** — a set of corpus specifications pinned by commit SHA, the
   generated pairs, and the first real binding precision and recall numbers reported with their
   sample sizes and their excluded cases counted. Unblocked. Dispatched as B27.
2. **Add the directional floor** on binding precision over that frozen corpus, once it exists and
   its variance is known to be zero across two identical runs. Not before. **Both conditions are now
   met** — the corpus is frozen and digest-validated, variance is measured byte-identical across
   four independent runs, and precision stopped being a constant when `hold_back` gave it four
   falsifiable negatives. Queued as B36.
3. **The M0 acceptance run**, when the user authorises it, producing the first `migration_outcome`
   row with a `pr_number`. Then merge rate, routing accuracy and cost per merged patch have a
   denominator of one, which is not a measurement but is the difference between one and zero.
4. **The routing row still has nowhere durable to land.** `_decide_tier` computes it and carries
   it on `RunState`, `TieredRemediator` asks the table again, and `on_route` has no caller
   anywhere in `src/`. `migration_outcome` has no column for it. Until that changes, "tier 0 was
   wrong for this change kind" stays an archaeology project rather than a query — which is the
   exact question routing accuracy exists to answer.
5. **The tier C statistics**, re-attempted at a scale that does not die on a session limit, before
   any threshold beyond the directional floor is written down.

## What this document does not claim

It does not claim the regime is nearly done. Three of five axes have never had a sample, no pull
request has ever been opened by the pipeline, and the labelled corpus does not exist. It claims
that the machinery to compute all of it is built and reachable, that the remaining work is
data rather than code, and that one of the three blockers is a decision rather than a task.

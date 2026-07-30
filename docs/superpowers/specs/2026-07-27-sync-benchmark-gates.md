# Sync — The Pipeline as a Benchmark

**Date:** 2026-07-27
**Status:** Gate tier A is built and running. Tiers B and C are specified, with their
preconditions named. No threshold in this document is invented.
**Scope:** Treating Sync's own output quality as a measured, versioned, CI-gated benchmark
rather than an impression.

## The premise

Sync's product claim is quantitative — that a binding-driven, CI-verified patch lands more
often than a general autonomous pull request. A claim like that is either measured or it is
marketing. The pipeline's quality has to be a number that a change can move, that CI can gate
on, and that gets recorded before anyone has an opinion about it.

The obstacle was that four of the five interesting numbers could not be computed at all, because
the table they read from did not exist. It exists now — `migration_outcome` in
`src/sync/graph/schema.sql:60` — and `src/sync/benchmark/axes.py` computes the axes from it, so
the obstacle has moved: the table holds no rows, because no real pipeline run has produced one.
The distinction that matters is between the computation and the gate, and it is drawn in tier B
below. This document separates what can be gated today from what
is waiting on data, and it is explicit about which is which — a benchmark spec that quietly
mixes aspirational thresholds into a live gate produces a red build nobody trusts, which is
worse than no gate.

## Gate tier A — built, running today

`.github/workflows/ci.yml`. These assert correctness, need no corpus, and are the entire gate
until tier B's precondition is met.

| Check | What it establishes | Failure mode it catches |
|---|---|---|
| `python scripts/lint_encoding.py src scripts tests` | Every text call names its encoding | The cp1252 default that no test can catch, because every fixture is ASCII |
| `lint-imports` | `sync.core` imports nothing from a sibling | A third-party adapter author inheriting Postgres in their dependency tree |
| `pytest` | The suite, e2e deselected | Ordinary regression |

Two properties make this tier worth having rather than ceremonial.

**The lints run before the suite.** A lint failure is a fact about the source; it needs no
database, no downloaded binary, and no test run to establish. Ordering them first means the
cheapest signal arrives first.

**oasdiff is pinned to 1.26.1.** Its rule identifiers are `VendorChange.kind`'s entire domain,
so an unpinned version would silently change the set of change kinds the pipeline can see —
and would silently change what any completeness test over that domain is asserting.

## Gate tier B — the quality axes, computed but not gated

Five axes. All five read from `migration_outcome`, specified in
`2026-07-25-sync-migration-corpus.md` and now built: the table is
`src/sync/graph/schema.sql:60`, the model is `MigrationOutcome` in `src/sync/core/models.py`,
and `GraphStore.record_migration_outcome` writes it.

Three of the five are computed today by `src/sync/benchmark/axes.py` — merge rate split by
`change_kind` and by `tier`, routing accuracy, and cost per merged patch — alongside the counts
binding precision will divide into. Each reports its sample size, and an axis with no samples
reports a null rather than a zero, which is the distinction the Verification section below
demands.

**What remains blocked is the gate, not the computation.** The corpus holds no rows from a real
pipeline run, because none has yet produced one, so against a deployment's own database every
axis reports zero samples. Confirmed against the running Postgres on 2026-07-29 rather than
inferred from the tree — `docs/superpowers/reports/2026-07-29-database-state.md` has the counts.
That measurement qualifies the sentence in one way worth knowing before reading an axis: a
database the test suite has been pointed at is not empty. `tests/test_pipeline_composes.py`
drives the real remediation graph and writes three attempts against one finding, and a pinned
database is deliberately not truncated afterwards, so `sync benchmark` aimed at a developer's own
database reports three samples of a fixture rather than the null this section describes. Nothing
is
wired into `.github/workflows/ci.yml` and no threshold is asserted anywhere, per the tier C rule
below. Binding precision and recall are no longer uncomputable for want of arithmetic —
`src/sync/benchmark/binding.py` scores them and splits both by the rung the binding came from,
and `src/sync/benchmark/mutate.py` produces the labelled pairs it takes. What they still lack is
a corpus of those pairs: the label source moved from mined migrations to synthetic mutation
(`2026-07-29-sync-ground-truth-quality.md`), and no pair set has been generated and frozen.
`sync benchmark` (`src/sync/cli.py:1333`) calls `render_report(store.migration_outcomes())` and
passes no labels, so the score it prints is computed over an empty reference. The shape of the
blockage is now the same as for the other three axes — the computation exists and there is
nothing to run it over.

| Axis | Definition | Why it is the one that matters |
|---|---|---|
| **Binding precision** | Of findings emitted, the share whose call site genuinely depends on the changed operation | A false finding spends reviewer trust, and trust does not recover at the rate it is spent |
| **Binding recall** | Of call sites genuinely affected, the share that produced a finding | A missed break is the failure the product exists to prevent |
| **Merge rate** | `pr_merged / pr_opened`, split by `change_kind` and `tier` | The direct test of the product claim. Unsplit it is meaningless — a high rate driven by one easy kind says nothing |
| **Routing accuracy** | Of findings routed to tier 0, the share that passed verification without falling back | The economic claim. A tier-0 route that fails to codemod is worse than never having tried |
| **Cost per merged patch** | Tokens and `wall_ms` per merged pull request | What makes the margin real rather than assumed |

**Precision is gated harder than recall, deliberately.** That follows the precision-over-recall
position already committed in `2026-07-26-sync-review-integration.md`, and it is the right
asymmetry for a tool a reviewer can switch off: a missed finding costs one incident, a false
finding costs the reviewer's willingness to read the next one.

### The precondition, stated as a task rather than a hope

Tier B cannot be built before `migration_outcome` is written to. Three properties of that
writing are load-bearing for the benchmark specifically, beyond what the corpus spec already
requires. One holds outright, one holds mechanically with an operational gap, and one holds in
part:

- **Abandoned attempts are written, not only successes.** A corpus of successes cannot compute
  precision, cannot compute routing accuracy, and cannot evaluate any future router. The
  `abandon` node's `abandon_reason` is the negative class. **Holds.**
  `src/sync/remediate/graph.py` installs the recorder from `src/sync/remediate/corpus.py`, and
  `nodes.py:653` writes the abandoned attempt for exactly this reason.
- **`pr_merged` and `human_edits_before_merge` are populated from a real webhook**, not
  inferred. Merge outcome arrives days after the run. A field that silently stays null for six
  months destroys the only measurement that tests the product claim. **Holds mechanically, and
  the remaining gap is operational.** Both things that stood between the receiver and a
  numerator have been closed. `open_pr` records the number it opened —
  `src/sync/remediate/nodes.py:571` passes `pr_number=pull_request.number`, and it is passed
  rather than read off `RunState` so a retried attempt keeps a null by construction — and
  `sync merge-outcome` (`src/sync/cli.py:1150`) is the caller of `record_merge_outcome`, which
  verifies the HMAC-SHA256 signature before parsing, acts only on `pull_request.closed`, and
  calls `GraphStore.set_merge_outcome`. What is left is that nothing delivers on its own: the
  receiver is still a function over bytes with no HTTP framework, deliberately, so a delivery
  arrives only when an operator hands one in. The same refusal `sync ingest` and `sync shapes`
  already make.
- **The routing decision that fired is recorded**, including the decision-table row. Otherwise
  "tier 0 was wrong for this change kind" is an archaeology project rather than a query.
  **Holds.** `tier` and `strategy` record which tier ran, and the row itself now lands.
  `_decide_tier` at `src/sync/remediate/nodes.py:72` calls `sync.route.matrix.route()` in the
  `locate` node and stores the row on `RunState` as `routing_row`, which the report node names
  in its reason; `sync.remediate.corpus` writes it through, defaulting to `'unrouted'` where the
  table had no jurisdiction, so an unrouted attempt stays distinguishable from an unrecorded one;
  and `migration_outcome` carries `tier` and `routing_row` at the table's one-row-per-attempt
  grain, persisted by `sync.graph.store`.

  Two qualifications, because the gate is about what can be *queried* rather than what is
  stored. **No attempt predating that column can be backfilled**, since the row a run routed on
  is a fact about the table as it stood, and `schema.sql` says so where the column is declared.
  And **`on_route` still has no caller in `src/`** — but that is now deliberate rather than
  unfinished wiring: the recorder already holds the state, which `sync.remediate.corpus` and
  `sync.remediate.tiered` each say beside the callback. A reader hunting for the missing caller
  is hunting for nothing.

  See `2026-07-27-sync-routing-matrix.md` for the jurisdiction the table currently has.

## Ground truth without customers

This is the part with no obvious answer, and it is the reason this document exists now rather
than after the corpus is built: the corpus records what Sync *did*, not what was *correct*.
Precision and recall need a labelled reference, and a solo founder with no users has no
labels.

**The proposal: mine migrations that already happened.** Open-source repositories pin a Stripe
API version. Some later bump it across a breaking release. The human's own migration commit is
a labelled patch — a correct answer, authored by someone with full context, available at
whatever scale a search finds. Run Sync's pipeline against the parent commit and compare its
findings and patch to what the human actually did.

Why this is the strongest option available:

- The label is free and was not produced by Sync, so it is not circular.
- It exercises INDEX, SIGNAL, DETECT, LOCATE, and PATCH end to end against real code, not a
  synthetic fixture shaped to pass.
- It is reusable — the same mined pairs re-score every future pipeline change, which is what
  makes it a benchmark rather than a one-off study.

Its weaknesses, stated because a benchmark whose bias is undocumented is worse than none:

- **Survivorship.** Repositories that migrated successfully are over-represented. Integrations
  abandoned rather than migrated are invisible.
- **The human is not always right.** A merged migration commit is evidence, not ground truth.
  Some are incomplete and were fixed later.
- **Commit granularity.** A migration bundled into a large refactor cannot be isolated, and
  those cases must be excluded rather than scored — excluding them biases toward simple
  migrations, which must be recorded alongside the score.

**The first deliverable is measurement, not construction.** Before building a harness, count:
how many public repositories pin a Stripe API version, and of those, how many contain a commit
that bumps it across a release Stripe classifies as breaking? If the answer is a handful, the
approach fails on sample size and something else is needed — synthetic mutation of real
repositories is the fallback, at the cost of realism. **Do not build the harness before
running the count.** That is the whole discipline of this section.

## Gate tier C — regression detection, and why no threshold appears here

Once tiers A and B produce numbers over time, the question becomes which movement is a
regression and which is noise. That question has real answers in the continuous-benchmarking
literature — step detection versus fixed-percentage thresholds, sample counts, instruction
counting instead of wall time to escape shared-runner variance, and how anyone gates a
probabilistic score that legitimately moves run to run.

**This document does not state those answers, because the research pass that would have
established them did not complete** — a ten-agent fan-out died on the session limit on
2026-07-27 without returning. Every number in that area is therefore unknown here.

What follows from that is a rule, not a gap to paper over: **do not invent a threshold.** A
gate at an invented number either fires constantly and gets disabled, or never fires and
provides false assurance. Until the numbers are established, tier B axes are **recorded, not
gated** — written to the corpus every run, reviewed by a human, and reported with their sample
size. Recording early is free and cannot be backfilled; gating early is a self-inflicted wound.

The one gate that is safe without statistics is a **directional floor on a deterministic
axis**: binding precision computed over a *frozen* mined corpus is deterministic given a fixed
pipeline and a fixed input set, so a drop is a real change and not sampling noise. That is the
first tier-C gate to add, and it is available as soon as the mined corpus is frozen.

## Verification

- **The lints are proven able to fail.** `tests/test_lint_encoding.py` asserts the CLI exits
  non-zero on a known-bad file, which is what CI actually gates on. A lint only ever run
  against clean input has not been shown to detect anything.
- **The mined corpus is frozen and versioned.** Its contents are pinned by commit SHA so a
  score is comparable across runs. An unfrozen benchmark measures the benchmark.
- **Excluded repositories are counted and reported alongside the score.** Silent exclusion
  turns a biased sample into an unqualified number.
- **Every tier B axis reports its sample size.** A merge rate over four pull requests is not a
  merge rate, and presenting it as one is how a solo founder talks themselves into a wrong
  conclusion with nobody in the room to object.

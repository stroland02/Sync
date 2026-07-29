# The first binding numbers taken over anything

**Date:** 2026-07-29
**Scope:** B27 — freeze a specimen corpus and score binding precision and recall over it, with
sample sizes, exclusions, and a measured answer to whether the score is deterministic.

`docs/superpowers/specs/2026-07-29-sync-verification-regime.md` recorded that the computation
existed and the corpus did not, and that this was the one blocker needing no pull request, no
model API and no decision. It is closed. What follows is the number, and rather more space spent
on what the number does not support, because that is the part a founder reading his own benchmark
is least likely to supply for himself.

## The result

```
  pairs specified       12
  pairs scored          10
  binding precision     1.0000       n=12
  binding recall        1.0000       n=12
  call sites affected   12
  call sites unaffected 94
  unlabelled findings   0
```

Twelve. Both axes are over twelve labelled affected call sites, in four real repositories, and
every one of those twelve is a request-side property insertion. The full run is recorded verbatim
at `benchmark/corpus/recorded/2026-07-29-score.txt` and `.json`.

| scored pair | affected | unaffected | findings | unreachable |
|---|---:|---:|---:|---:|
| `fireship-server-GetPaymentMethods-response-property-removed` | 0 | 12 | 0 | 1 |
| `fireship-server-PostPaymentIntents-request-property-removed` | 2 | 10 | 2 | 0 |
| `furever-PostPaymentIntents-request-property-removed` | 6 | 25 | 6 | 0 |
| `furever-PostPaymentIntents-response-property-removed` | 0 | 31 | 0 | 6 |
| `remix-PostPaymentIntents-request-property-removed` | 1 | 1 | 1 | 0 |
| `remix-PostPaymentIntents-response-property-removed` | 0 | 2 | 0 | 1 |
| `turbo-PostPaymentIntents-request-property-removed` | 2 | 2 | 2 | 0 |
| `turbo-PostPaymentIntents-response-property-removed` | 0 | 4 | 0 | 2 |
| `turbo-PostRefunds-request-property-removed` | 1 | 3 | 1 | 0 |
| `turbo-PostRefunds-response-property-removed` | 0 | 4 | 0 | 1 |

Excluded, counted by reason:

| reason | count | which |
|---|---:|---|
| `displaced-label` | 2 | `furever-GetCharges-response-property-removed` (3 labels displaced), `fireship-server-PostPaymentIntents-response-property-removed` (1) |

No pair was excluded for any other reason, and no failure fell outside the classified set — the
runner re-raises an unrecognised error rather than folding it into a named reason, so the absence
of an `unclassified` row is a statement rather than a default.

## Determinism, measured rather than assumed

`2026-07-27-sync-benchmark-gates.md` names exactly one gate that is safe without the statistics
research that never completed: a directional floor on a deterministic axis, because binding
precision over a frozen corpus is deterministic given a fixed pipeline and a fixed input set. That
was an assumption. It is now a measurement.

Both databases were dropped and recreated, and the full corpus was scored twice, once into each.
The two JSON outputs are byte-identical:

```
01fbf01365c3ff796a7d3612959f06f3511b4a2f0ae68ca34e4fb6da54c1ea05  run 1
01fbf01365c3ff796a7d3612959f06f3511b4a2f0ae68ca34e4fb6da54c1ea05  run 2
```

Identical field by field, not merely in the two headline rates: the comparison is over the whole
document, which carries every finding, every label, every call site id, the per-pair counts and
the exclusion detail strings. `diff` reports no difference in the rendered text either.

**Verdict: the directional floor is available.** A drop in binding precision over this corpus is a
real change and not sampling noise. Wiring that floor was explicitly out of scope here and remains
step 2 of the regime's sequence.

Two caveats on the scope of that verdict, neither of which weakens it. It was measured across two
runs on one machine on one day, not across machines or Python versions. And it is a statement
about *this* corpus: the pinned inputs are what make it hold, and it lapses the moment a
specification names something unpinned.

## What would have produced a low number, and why this one is not trivially satisfied

The brief for this task said not to assume the pipeline is correct because a score came out. The
worry has a specific shape: `_score_corpus` targets *every* indexed call site on the changed
operation, so if the detector emitted a finding for every call site on the changed operation
regardless of the field, it would score 1.0 on both axes against any corpus whatsoever, and the
number would be a tautology.

The corpus refutes that by accident, and the refutation is the most useful thing in it. The five
response-side pairs that scored have call sites on the changed operation — `furever`'s has six —
and no mutation attached to any of them, so nothing in those trees was broken. An
operation-matching detector would have emitted six findings there and precision would have
collapsed. It emitted **zero**. Across the whole corpus, 94 unaffected call sites produced no
findings and 12 affected ones produced 12.

So the detector is joining on the changed field and not merely on the operation, and the 1.0 is
not the tautology it could have been. That is worth exactly as much as it says and no more.

## What the number does not support

`SYNTHETIC_REFERENCE` in `src/sync/benchmark/score.py` ends: *a binder that scores well here has
been shown to handle the mechanical case, and nothing more.* That sentence travels with every
result the harness renders, and it survives into this document rather than being dropped now that
the number looks good.

Three specific limits, in descending order of how much they cost the reading.

**Every positive is request-side. The response half of the corpus measures nothing.** All twelve
affected call sites come from request-property insertions. Not one response-side pair contributed
a single affected site, and the cause is mechanical: `mutate._insert_response_guard` needs the
call's result bound by a `const` or `let` declaration to a plain identifier, and real Stripe code
frequently does something else. `furever` writes `paymentIntent = await stripe.paymentIntents
.create(…)` into a variable declared earlier; `turbo` writes `intentOrCheckout = await …`;
`remix` and `fireship-server` write `return stripe.paymentMethods.list(…)` and
`await stripe.refunds.create(…)` with the result discarded. Eleven targets across five pairs were
unreachable for that reason. **So recall 1.0 describes request-side breaks only**, and the corpus
currently says nothing about the response side except that nothing false was emitted over it.

**Precision has almost no way to fail here, and this is stated in the code rather than discovered
by me.** `generate_pair` refuses a tree where an untargeted call site already carries the changed
dependency, and carrying it is the only thing the detector's field match fires on, so a false
positive needs a partial path match and cannot arise at all from a flat change. Every change in
this corpus is flat. A precision of 1.0 over it is closer to a property of the corpus than a
property of the binder.

**The sample is twelve call sites in four repositories, three of which are demonstration or
teaching code.** Nothing was selected for being representative of the population of repositories
that depend on Stripe, because no measurement of that population exists. Four repositories is not
a distribution.

One further constraint bounds what could have been selected at all. The Stripe symbol map covers
105 of 414 `/v1/` paths, so a repository whose Stripe usage runs through `checkout.sessions
.create` — a nested sub-resource the path pattern does not match — contributes nothing and was not
selectable. The corpus is therefore drawn from the quarter of the API surface the binder can
already address, which flatters it in a way no amount of adding repositories would fix.

## What was built

| | |
|---|---|
| `benchmark/corpus/repositories.yaml` | Four repositories pinned by commit, subpath and tree digest. |
| `benchmark/corpus/pairs/*.yaml` | Twelve corpus specifications, generated rather than chosen. |
| `benchmark/corpus/recorded/2026-07-29-score.{txt,json}` | The run, recorded verbatim. |
| `benchmark/corpus/README.md` | Which repositories, why those, and what the sample is not. |
| `scripts/fetch_corpus_repositories.py` | The setup step: fetch each pinned commit, materialise, verify the digest. |
| `scripts/build_corpus_specs.py` | The selection rule, executable. |
| `scripts/score_corpus.py` | The runner: pools the set, counts exclusions, refuses to render without the reference. |
| `tests/test_corpus_set.py` | Seventeen tests over the pure aggregation, from constructed results. No database, no network. |

Nothing under `src/sync/` was touched. `src/sync/cli.py` was imported and not modified:
`_score_corpus` is the definition of the specification format, and a second copy in the runner
would let the set and the single-pair command drift apart silently.

### Pinned three ways

The commit pins what each vendor published. The `tree_digest` — SHA-256 over every materialised
path and the SHA-256 of its bytes — pins what the fetch produced from it, and the fetcher refuses
when the two disagree. The Stripe specification the symbol map is derived from is pinned by
`scripts/fetch_measurement_inputs.py`, which was landed for the measurement-provenance task and
verifies a git blob hash before writing. Deleting `.cache/corpus/` and re-running reproduced all
four digests exactly.

### The corpus is generated from a stated rule

A corpus assembled by picking pairs that score well measures the picker. `build_corpus_specs.py`
holds the rule — per repository, the two operations with the most indexed call sites that take an
object argument; both mutable change kinds for each; the alphabetically first real property of
that operation in `v2330` that no call site already uses — and the score is whatever it produced,
including the two pairs the harness then refused and the five that contributed nothing.

## Findings for sequencing, none of them fixed here

**`_score_corpus` cannot read a real repository.** It reads every file under the checkout with
`read_text(encoding="utf-8")`, so a single PNG ends the run; the Stripe Connect demo carries 63
files that are not UTF-8. The corpus works around it by materialising only the files that decode
and printing how many it dropped, which is a documented transformation of the vendor's tree rather
than a fix. The fix belongs in `cli.py`, which this task was told not to edit — skipping a file
that does not decode is what the indexers effectively want anyway, since nothing they read is
binary.

**The response-side generator is where the corpus is weakest, and the repair is in `mutate.py`.**
Extending `_result_binding` past `const`/`let` declarations — to a plain assignment and to a
returned call — would convert eleven currently-unreachable targets into labelled positives and
give the response axis a sample for the first time. It is a change to a generator rather than to
the pipeline, so it moves the corpus and not the score's meaning.

**`displaced-label` is structural, not incidental.** `upsert_call_site` keys identity on line and
column, so any mutation that inserts lines renames every call site below it in that file. Two
pairs were refused for it and both were response-side, where the mutation inserts a three-line
guard. It is correctly refused rather than mis-scored — the refusal is the feature — but it means
a file with several calls can never carry a response-side pair, which compounds the previous
finding rather than being independent of it.

**The suite baseline moved under this branch and it was not mine.** Noted under Gates below.

## Gates

Run from the worktree root at `coordinator/solo-a`.

```
uv run pytest -q
uv run lint-imports
uv run python scripts/lint_encoding.py src scripts tests
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

The summary lines are quoted verbatim in the completion message rather than transcribed here, so
that the two cannot disagree.

One thing about the tree they ran against has to be said rather than left for someone to find.
This worktree carried another worker's changes to `src/sync/core/conformance.py` and
`tests/test_adapter_conformance.py` throughout — the conformance hardening the task brief named as
out of bounds. They were uncommitted while this work was written, were left untouched, and landed
on the same branch as `fc27d0e` before this commit. The suite that produced the gate line above
ran over their content, so the pass describes `fc27d0e` plus this work rather than `origin/main`
plus this work. Nothing here staged either file; this commit names its files explicitly.

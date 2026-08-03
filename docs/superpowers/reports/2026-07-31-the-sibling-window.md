# The sibling window gets the floor it grades findings against

**Date:** 2026-07-31
**Task:** M3-W122
**Answer taken:** candidate 1 — `MIN_SAMPLES` applied to the sibling window, with the argument
that no second number is needed because the first one was never derived from a role.

Two people recorded this defect before this task existed and neither fixed it. The pin at
`tests/test_detector_declines.py:359` made it visible in the suite; M3-W119 measured it again from
the other direction while building the traffic filter, and reported it as its second finding in
`docs/superpowers/reports/2026-07-31-traffic-and-non-traffic-shapes.md`. Nothing here re-measures
what they established. This task is the decision they both declined to make.

## What the `breaking` grade actually claims

The sentence a reviewer reads, from `_rationale`:

> The same field was seen arriving differently before this shape appeared, so the vendor's
> behaviour changed rather than the specification having always been wrong.

Two claims are packed into that, and only the first survives one observation. "The same field was
seen arriving differently" is a claim about *presence*, and one row genuinely proves it: a `null`
really did arrive. "So the vendor's behaviour changed" is an inference from it, and the inference
needs the earlier shape to have been the field's behaviour rather than a stray. One misbehaving
account is consistent with the specification having always been wrong *and* that account having
produced one odd response — which is the hypothesis the grade exists to rule out.

**The rationale made this worse than an overclaim**, and this is the part neither predecessor
recorded. `_evidence` quotes the sample count of the row the finding is *raised* on, and never the
sibling's:

> Observed 30 time(s) from error-payload between 2026-07-20 and 2026-07-20.

So a reviewer holding an escalation sourced from a single observation saw the number 30 next to
it. The count in front of them belonged to the other row. The finding did not merely assert more
than it could support; it displayed a figure that made the assertion look supported.

## Whether one number can serve both claims

**It can, and the reason is that `MIN_SAMPLES` was never derived from a role.**

M3-W119's doubt — the doubt this task had to answer rather than inherit — was framed around use:
"the sample size that makes 'this field used to behave differently' credible is not obviously the
sample size that makes a divergence worth reporting." That framing assumes the number was chosen
for the reporting role and would have to be re-derived for the corroborating one. It was not. The
module docstring gives two justifications and the second is decisive:

> By the rule of three, an outcome not seen in 30 independent samples has a 95% upper bound of
> about 3/30 -- ten per cent -- so 30 is roughly the smallest sample at which "the declared shape
> did not appear" is worth saying at all. Below it, one upstream incident or one misbehaving
> account supplies the whole count.

The second sentence is a property of a **count**, not of the use a count is put to. "Could one
incident or one account supply the whole of this row's count?" is a question about a row. It has
the same answer at `sample_count=1` whether that row is being reported or being compared against.
Nothing in the derivation refers to what the row will be used for, so nothing in it has to be
re-derived when the use changes.

The module had already committed to this and was contradicting itself. Its first section says a
shape below the floor **"is not a baseline"**. Its third says a `breaking` grade means the
divergence is "corroborated by **the baseline's own history**". The sibling window read sub-floor
rows as that history. Applying the floor does not choose between those two sentences; it makes
them agree. **No threshold is invented here, because the module already contains exactly one
answer to "is this shape a baseline" and the sibling window was the one place not asking it.**

`CLAUDE.md`'s prohibition is therefore satisfied by not needing a second number rather than by
justifying one. Had a second number been required, there would have been nothing to derive it
from: `vendor_change` refuses a depth cut-off for want of labelled data, and the same absence
binds here.

**The codebase already had this shape, in the detector that says it inherited this one's
principle.** `sync/detect/status_rate.py` states that whether a rate rose "is used exactly as
`observed_drift` uses its own window comparison: as enrichment of severity on a finding some other
rule already raised... That module states the principle and this one inherits it unchanged." Its
`_periods` then requires the earlier block and the later block *each* to clear
`MIN_STATUSED_CALLS` on its own, with no row in common, and refuses the change claim otherwise —
one floor, both sides of the comparison. `observed_drift` was the odd one out.

That module also documents the codebase's own rule for when a *second* number is warranted:

> That gap is why the floor is a hundred rather than the thirty `observed_drift` could justify:
> its question is "has this been seen enough times to be a baseline", and this one is "could this
> proportion have come from a harmless one".

A new number is derived when the **question** changes. Here it does not. The sibling window asks
"has this been seen enough times to be a baseline", which is verbatim the question `MIN_SAMPLES`
is the answer to.

## Which direction the error runs, and why this trade suits this detector

Before, one observation graded `breaking`: a **precision** loss on severity, in the module whose
own docstring calls it "the detector most able to violate precision-over-recall" and names the
sample floor as the first of three rules holding it to the committed position. After, a thin
sibling no longer escalates: a **recall** loss on severity, in the case where the thin earlier row
was a real change.

The trade is right here for a reason narrower than "precision beats recall", which is a slogan
that would license almost anything:

- **The recall cost is a reordering, not a loss.** No finding disappears. The divergence is still
  raised, still against the same call site, with a rationale that now names the earlier shape and
  its count. What moves is where it sits in a reviewer's queue.
- **Nothing downstream drops an `info` finding.** Checked rather than assumed.
  `AgentRemediator.can_handle` gates on `finding.severity in ("breaking", "deprecation")`, and
  that gate has no caller: `nodes.make_patch` calls `propose()` directly, and `TerminalTier`
  answers `can_handle` with `True` for everything. `TieredRemediator` consults `can_handle`, but
  the agent reaches it wrapped. The live consumers of severity are read surfaces —
  `mcp/tools.py:116` filters findings by severity when a caller asks, and
  `dashboard/queries.py:100` displays it. So severity decides what a reviewer sees first, not what
  the pipeline repairs.
- **The precision cost was a false statement of fact.** "The vendor's behaviour changed" is not a
  ranking, it is an assertion about a third party, printed beside a sample count belonging to a
  different row.

A reordering traded against a false claim is not a close call, and the asymmetry is what makes the
trade specific to this detector rather than general.

## What it does to a database already holding thin siblings

**Nothing, and this is a complete sweep rather than a sample or an inference.** Every database on
the server was queried, not a handful:

| | |
|---|---|
| databases matching `sync%` | 250 |
| of those, holding an `observed_shape` table | 166 |
| of those, holding any row at all | 5 |
| of those, holding a field with more than one `json_type` — the only shape that has a sibling window | **1** |

The single database with a sibling window is `sync_w119_mut`, W119's own mutation scratch database,
and both of its rows sit at `sample_count=30` — at the floor, so corroborating before this change
and corroborating after it. **No finding anywhere on this machine changes grade.**

The other four hold one or two rows each (`sync_b8`, `sync_w30`, `sync_w122d_mut`) or, in
`sync_w57`, eleven rows across eleven distinct field paths, every one at `sample_count=30`. A field
observed as exactly one shape has no sibling, so it has no grade to change.

There is also no production baseline behind these: `observed_shape` does not exist in the primary
`sync` database, because the schema has never been applied there. The module already says as much
in `declined`'s own docstring — "the live baseline holds one row carrying one sample".

So the honest summary is that the change is real but currently unexercised by data, and the useful
statement is the rule rather than the count. A finding's grade moves from `breaking` to `info` if
and only if, for the field it is raised on, **every** sibling row of a different `json_type` with an
earlier `first_seen` has `sample_count < MIN_SAMPLES`. Where at least one such sibling clears the
floor, the grade is untouched. No row is rewritten and no column is added, so nothing needs
backfilling and `CLAUDE.md`'s `unattributed` precedent does not arise.

## The `info` rationale had to change, or the fix would have bought precision with a new lie

The existing sentence for an uncorroborated divergence is:

> No earlier observation shows this field behaving differently, so an inaccurate specification is
> at least as likely an explanation as a change in behaviour.

After the floor reaches the sibling window, that sentence is **false** whenever a thin sibling
exists. There was an earlier observation; it was too thin to count. Printing "no earlier
observation" would have removed one untrue sentence and added another, and it would have hidden
the single fact most likely to make a reviewer look harder.

So `_history` has three branches where it had two, which is the shape `status_rate._history`
already uses for the same reason. A divergence discounted for thinness now reads:

> An earlier observation shows this field arriving as string, seen 1 time(s) against a floor of
> 30 -- too thin to be a baseline, so it is not read as the vendor's behaviour having changed.

The count is named, so the honest half of candidate 3 arrives as a consequence of stating
candidate 1 truthfully rather than as a second change. Counts are deliberately not summed across
sibling rows: each row is a different shape, and a total would quote a baseline no single
observation supports. The largest is reported, because the strongest evidence that still failed to
reach the floor is what a reviewer needs to judge the decision.

## The four candidates

**Taken: candidate 1, `MIN_SAMPLES` applied to the sibling window.** The argument is above and
rests entirely on the number's existing derivation being role-independent. Taken with the third
rationale branch, without which it would trade one false sentence for another.

**Rejected: candidate 2, a separate derived threshold for corroboration.** Honest only if it can
be derived, and it cannot. Nothing in this repository calibrates "how much earlier evidence makes
'it used to be different' believable" — there is no labelled corpus of real vendor changes with
their observation counts, which is the same absence that makes `vendor_change` refuse a depth
cut-off. Any number would have been chosen because it felt right, which `CLAUDE.md` rates worse
than the asymmetry. The candidate also assumes its own premise: it is only needed if the two
claims require different numbers, and the section above concludes they do not.

**Rejected: candidate 3, report the corroboration count and leave the grade alone.** The most
tempting rejection, and it fails on where this module puts its confidence. The module's own
docstring says the corroborated/uncorroborated distinction "cannot live anywhere but severity,
because both produce the same divergence". Candidate 3 leaves the wrong answer in the field the
module designates as the answer, and moves the correction into prose beside it. That matters
because severity is machine-readable and the rationale is not: `mcp/tools.py` filters on severity,
so an agent asking for `breaking` findings still receives the thin-evidence one in the same list
as a real break, and `AgentRemediator`'s dormant severity gate would act on it the day anything
wires it. Nothing anywhere parses a rationale. The candidate's real contribution — that a reviewer
should see the corroboration count — is kept, and is in the change.

**Rejected: candidate 4, nothing, and record why the asymmetry is correct.** This would have
needed the evidence to show that a thin earlier sibling genuinely is enough, and it shows the
opposite. The module's own justification for the floor — "one upstream incident or one misbehaving
account supplies the whole count" — describes the sibling row exactly as well as the reported one,
and the module cannot call a shape not-a-baseline in one paragraph and rest a severity on it as
one in the next. Choosing this would have meant defending a contradiction rather than closing a
question.

## What happened to the two deliberate pins

Both were retired by inversion, in place, with their fixtures unchanged so that the verdict moved
and the question did not. Neither was deleted and neither lost an assertion; both gained one.

`test_a_single_earlier_observation_is_enough_to_grade_a_divergence_breaking` becomes
`test_a_single_earlier_observation_is_too_thin_to_grade_a_divergence_breaking`. Its docstring
carries the argument above rather than only the new expectation, because the original was a
careful statement of a real problem and a replacement that merely asserted the opposite would
discard the reasoning that made it worth writing.

`test_a_traffic_row_under_the_floor_still_escalates` — W119's, in
`tests/test_observed_shape_sources.py`, a file outside this task's named scope but not among its
forbidden paths — becomes `test_a_traffic_row_under_the_floor_no_longer_escalates`. It keeps two
traffic sources and no synthetic row, so it still records that this was never about provenance.

**The controls are the part that needed care, and one of them nearly went vacuous.**
`test_the_same_divergence_with_no_earlier_sibling_at_all_is_informational` existed to prove the
pin above it was a statement about the sibling rather than about the divergence, and it did that
by grading `info` where the pin graded `breaking`. After this change both grade `info`. Severity
can no longer separate them, so the rationale does: the thin case asserts the sibling's count and
the floor, and the control asserts "No earlier observation" *and* that no floor is mentioned.
Without both halves the pair would have agreed on every assertion it made, and a detector that had
collapsed the two `info` explanations into one would have satisfied it.

Mutation `M5` is exactly that collapse — the thin-sibling branch deleted, so a discounted sibling
reports as no sibling — and it is killed. That is what establishes the pair still isolates the
sibling as the variable rather than merely agreeing about it. The complementary direction is
`M6`, severity never escalating, killed by the two at-the-floor tests.

The same hazard hit W119's other pin from the opposite side.
`test_one_replay_row_no_longer_escalates_an_uncorroborated_divergence` wrote its replay row at
`_shape`'s default of one sample. After this change that row would have been excluded by the floor
as well as by the source filter, so the test would have kept passing through W119's traffic filter
being reverted — proving nothing it was written to prove. Its row is now written **at** the floor,
where provenance is the only thing that can keep it out of the window. Mutation `M7` is that
filter reverted, and it kills the test.

Two new boundary tests keep the narrowing from becoming a removal: a sibling at exactly
`MIN_SAMPLES` still grades `breaking`, and one at `MIN_SAMPLES - 1` does not. Without the first,
every assertion in the group would be satisfied by a detector that had stopped escalating at all.

## A second defect, found by mutation and fixed here

`_earlier_windows` filters siblings on `json_type` **and** on `first_seen < shape.first_seen`.
Dropping the second predicate left all 69 tests green — it had never had a test that fails when it
is removed, in the old shape of the function or the new one, because every fixture reaching it
happens to put the differing sibling first.

The input it guards is ordinary: a divergent shape observed early, with a differently-shaped
observation arriving after it. Without the predicate, that grades `breaking` on the claim that the
vendor's behaviour changed, sourced from an observation that had not happened yet.
`test_a_later_sighting_of_a_different_shape_is_not_an_earlier_window` asserts both directions from
one baseline, with both rows above the floor so the floor is not the variable. This is a separate
commit from the change it was found beside.

## What was needed from `src/sync/graph/` and not taken

**Nothing.** The answer needed no store change and no schema change: `observed_shapes` already
returns `sample_count` on every row, and the floor is applied where the rows are compared. No
count filter on the reader was wanted, and one would have been wrong — the detector needs the thin
sibling in hand in order to name it in the rationale, so a store that filtered thin rows out would
have made the third branch impossible to write.

`src/sync/graph/store.py` was mutated for measurement (`M7`) and restored byte-for-byte from bytes
read before the edit, in a `finally`, with the restore asserted in-process; `git diff --exit-code`
over that path returned 0 afterwards.

## What was left alone, and why

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` is **not edited**. This task
may touch it only if the answer changes what the specification claims about severity, and it does
not: the spec's severity claim is that observed-versus-observed is "useful as severity enrichment
rather than as a lone trigger", which is untouched, and its safe-miss paragraph says a shape seen
too few times is not a baseline, which this change extends rather than contradicts. The floor's
scope is a module-level commitment and the module docstring is where it is stated.

One sentence in that spec's **Status** block is stale, and it was stale before this task: "one
replay row is enough to turn an uncorroborated divergence into a `breaking` finding" stopped being
true when W119 landed the source filter, and is now untrue twice over. It is left for whoever owns
that document, because correcting it is correcting a different task's leftover and falls outside
the narrow permission above.

## Verification

Every measurement against a real Postgres 16 on port 5433. Databases `sync_w122d` and
`sync_w122d_mut`, **both created by this task** — `sync_w122` and `sync_w122_mut` already existed
from an earlier attempt at this brief and were left untouched.

Mutation baseline: **70 passed, exit 0, `-n0`**, over the four test files that can reach this
change.

| Mutation | Verdict | Killed |
|---|---|---|
| M1 the sibling window loses the floor (the defect reinstated) | killed | `test_a_single_earlier_observation_is_too_thin_...`, `test_a_traffic_row_under_the_floor_no_longer_escalates`, `test_an_earlier_observation_one_short_of_the_floor_does_not` |
| M2 the floor becomes exclusive on the sibling (off-by-one) | killed | `test_an_earlier_observation_at_the_floor_still_grades_the_divergence_breaking`, `test_a_traffic_row_at_the_floor_still_escalates`, `test_a_divergence_the_earlier_window_contradicts_is_the_stronger_finding` |
| M3 the earlier window drops its `first_seen` predicate | **survived, then killed** | `test_a_later_sighting_of_a_different_shape_is_not_an_earlier_window` — the second defect above |
| M4 the earlier window drops its `json_type` predicate | killed | `test_an_earlier_sighting_of_the_same_shape_is_not_a_contradiction` |
| M5 the thin-sibling rationale branch is removed | killed | the same three as `M1` — this is the mutation that proves the control is not vacuous |
| M6 severity never escalates | killed | the same three as `M2` |
| M7 the traffic filter is ignored (W119's change reverted) | killed | `test_one_replay_row_no_longer_escalates_an_uncorroborated_divergence` and four more |

No mutation survives on the committed tree, and **no false-verdict mode fired**. The harness
separates killed, survived, did-not-compile (`compile()` before writing), unreadable (exit
∉ {0,1}, and exit 1 with no `FAILED` line), baseline-drifted (pass count off baseline),
not-applied (anchor absent or ambiguous) and anchor-missed (anchor present in LF form but not in
the file's own newline form, reported separately from not-applied).

**The mixed newlines made that last mode load-bearing rather than ceremonial.**
`observed_drift.py`, `test_detector_declines.py` and `store.py` are CRLF in the working tree and
`test_observed_shape_sources.py` is LF. Anchors are written LF and rewritten per file to that
file's own newline before matching, so a silent zero-hit replace cannot be scored as a survival.

`M3` is the one that mattered. It compiles, it is a one-line deletion, and it left the entire
baseline green — a harness that stopped at "no mutation survived" would have reported a clean
sheet over a predicate nothing tested. The rule that the fault is usually outside the production
code held in the other direction here: the mutation was sound, the code was right, and the test
was missing.

### The gates

Run on `stroland02/m1-window` at `df34689`, branched from `origin/main` at `d24f61f`.

| Gate | Scheduler | Result | Exit |
|---|---|---|---|
| `pytest -q` | `-n auto` (the `addopts` default) | 2777 passed, 2 skipped, in 138s | 0 |
| `pytest -q -n0` | `-n0` | 2777 passed, 2 skipped, 1 deselected, in 511s | 0 |
| `lint_encoding.py src scripts tests` | — | no output | 0 |
| `lint-imports` (unredirected, `PYTHONIOENCODING=utf-8`) | — | `Contracts: 1 kept, 0 broken` | 0 |
| `lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | — | no output | 0 |

2777 is the pre-change baseline of 2773 plus this task's four new tests: the two boundary tests
either side of the floor, the traffic counterpart at the floor, and the directional test. Nothing
was lost and no test was deleted — both retired pins were inverted in place, so neither shows up as
a subtraction.

This worktree's baseline before any edit was **2773 passed, 2 skipped** under `-n auto`. `main`
reads 2774 passed, 1 skipped in a checkout whose gitignored `.cache/specs/` is populated; the extra
skip here is `test_symbol_map_pin.py`, which wants a staged symbol map this worktree has not
fetched, and `test_oasdiff_determinism.py` wants `SYNC_OASDIFF_DETERMINISM=1`. Both are
environmental and neither is this change. Recorded so a mutation harness does not read the
difference as drift.

# Six declines in the detectors, five of which cannot happen

M3-W103. `src/sync/detect/` is where graph state becomes a `Finding`, and six of its statements
had never executed — three in `status_rate`, two in `observed_drift`, one in `efficiency`. Every
one is a decline: an input that yields no finding. **Five of the six are unreachable through the
only entry point a detector has**, and this report says why rather than reaching them by calling a
private function. The sixth is ordinary, fires on every healthy multi-vendor repository, and the
failure it prevents is not a lost finding but a cost claim attributed to the wrong vendor.

This is the first of these surfaces where the coverage gap is mostly not a gap. The preceding
reports found declines that were real and untested; here the number was hiding a structural fact —
that three detectors guard a column their store cannot return null from, and two guard a block
their own caller has already guaranteed exists.

## Coverage, before and after

Both figures come from the same command, run over the whole suite:

    uv run pytest -q -p no:randomly --color=no --cov=sync.detect --cov-report=term-missing

Before, at `6dbfe1d` (`origin/main` when this branch was cut), with no edit in the tree:

    src\sync\detect\__init__.py                    0      0   100%
    src\sync\detect\efficiency.py                 58      1    98%   158
    src\sync\detect\observed_drift.py             77      2    97%   173, 209
    src\sync\detect\parameter_deprecation.py      44      0   100%
    src\sync\detect\status_rate.py               106      3    97%   187, 230, 295
    src\sync\detect\vendor_change.py              51      0   100%
    TOTAL                                        336      6    98%
    2460 passed, 2 skipped in 163.54s

After:

    src\sync\detect\__init__.py                    0      0   100%
    src\sync\detect\efficiency.py                 58      0   100%
    src\sync\detect\observed_drift.py             77      2    97%   173, 209
    src\sync\detect\parameter_deprecation.py      44      0   100%
    src\sync\detect\status_rate.py               106      3    97%   187, 230, 295
    src\sync\detect\vendor_change.py              51      0   100%
    TOTAL                                        336      5    99%
    2474 passed, 2 skipped in 238.41s

**No statement was added or removed from any of the five modules** — 336 in both columns — so the
line numbers are identical on both sides. `efficiency.py:158` is covered and `efficiency.py` is at
100%. The other five are unchanged and deliberately so: covering them means calling
`_leading_block`, `_periods`, `_undeclared` or `_diverged` directly, and a test that does that
proves the function runs rather than that the guard protects anything.

The pass count moved from 2460 to 2474, and the two figures are **not over an identical suite**:
eleven of the fourteen are this task's new tests, and the remaining three arrived with the merge of
`origin/main`, whose `tests/test_decode_handlers.py` was rewritten in the interval. The merged tree
without this task's tests was not measured separately, so that split is arithmetic rather than
observation. What *is* over an identical suite is the thing the comparison is about: `sync.detect`
holds 336 statements on both sides, and the missing-line list moved by exactly one entry.

## The six

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `efficiency:158` — `continue` on a row from another vendor | any `observed_call` row for this repository whose `vendor_id` is not the detector's. Ordinary rather than exotic: a repository calling two vendors produces them on every ingest | Yes, and **the failure it prevents is not a missing finding**. `strongest` is keyed `(operation_id, claim.kind)` with no vendor component, so without the guard a Twilio unit of work five times as loud wins the key and its call volume is quoted in a Stripe rationale against a Stripe call site | **Nothing.** The row contributes no claim, and the findings are equal field-for-field to a graph that never held it |
| 2 | `observed_drift:173` — `site.id is None` in `_undeclared` | **Nothing.** `sites` reaches it only from `call_sites_for_operation`, which is `SELECT * FROM call_site`, whose `id` is `TEXT PRIMARY KEY` | Unanswerable — the condition cannot occur | — |
| 3 | `observed_drift:209` — the same guard in `_diverged` | **Nothing.** Same clause | Unanswerable | — |
| 4 | `status_rate:230` — the same guard in `scan` | **Nothing.** Same clause | Unanswerable | — |
| 5 | `status_rate:187` — `_leading_block` falls out of its loop | **Nothing.** `scan` will not call `_periods` until `_tally(rows).statused` has reached `self._floor`, and `_leading_block` counts statused requests by the identical predicate over the identical rows, so the cumulative count reaches the floor before the rows run out | Unanswerable, **and redundant** — Python returns `None` off the end of a function | — |
| 6 | `status_rate:295` — `return None, None` when a block is absent | **Nothing.** Same clause as row 5, on both the leading and the reversed side | Unanswerable | — |

One decline observed, five unanswerable. That is the inverse of the four surfaces before this
one, and the reason is in the next two sections.

## Why three of them are dead: a primary key

`observed_drift._undeclared`, `observed_drift._diverged` and `status_rate.scan` each open with

```python
for site in sites:
    if site.id is None:
        continue
```

and in all three `sites` arrives from `GraphStore.call_sites_for_operation`, which is
`SELECT * FROM call_site` fed into `CallSite(**row)`. `schema.sql:2` declares
`id TEXT PRIMARY KEY`, which is `NOT NULL` by definition, so the attribute is never `None`.
`upsert_call_site` agrees from the other end: the id is `_stable_id(...)`, a string, never
absent.

**The interesting part is that the same guard is load-bearing one module away.**
`parameter_deprecation.py:79` carries it and is at 100%, because that detector takes its call
sites from its **caller** rather than from the store — `cli.py:939-943` keeps the list it upserted —
and `CallSite.id` is `str | None = None`, so an in-memory site legitimately has no id.
`vendor_change.py` carries no guard at all and passes `site.id` straight into
`Finding(call_site_id=...)`, which is correct: `Finding.call_site_id` is `str` with no default,
so the alternative to guarding is a `ValidationError` at construction rather than a finding that
resolves to nothing.

Four detectors, three answers, and the difference is entirely **where the sites come from**. That
is worth having on record, because a reader comparing the four functions side by side will read
the inconsistency as drift and it is not: one of the three answers is required, one is dead, and
one is dead and looks required.

`test_the_column_a_call_site_id_is_read_from_cannot_be_null` is the clause asserted rather than
described, and it is asserted against the live schema through `information_schema.columns`. It
reads two columns in one query: `call_site.id` must come back `NO` and `finding.vendor_change_id`
must come back `YES`. The second is the control. A query that returned `NO` for everything — a
mistyped name reading as absent, a filter matching nothing — would satisfy the first assertion
for the wrong reason, and this repository has shipped exactly that failure once already in the
import-boundary test.

## Why the other two are dead: the gate and the split share a floor

`status_rate.scan` reaches `_periods` only after

```python
overall = _tally(rows)
if overall is None or overall.statused < self._floor:
    continue
```

and `_periods` then calls `_leading_block(rows, self._floor)` and
`_leading_block(list(reversed(rows)), self._floor)`. `_tally` counts a span when
`isinstance(status, int)`; `_statused`, which `_leading_block` sums, uses the identical
predicate. So `sum(_statused(row) for row in rows) == overall.statused >= self._floor`, the
cumulative sum inside `_leading_block` reaches the floor at some index on both the forward and
the reversed pass, and neither call can return `None`. Line 187 never executes and line 295
never fires. Reversing the rows does not change the total, and `_populations` never produces an
empty group, so no constructor argument opens a path either: a negative or zero floor returns at
the first row.

What survives at 297 is the case the module docstring is actually about — two blocks that each
clear the floor but **share a row** — and that one is covered.

`test_the_floor_that_gates_a_finding_is_the_floor_that_splits_the_periods` asserts the coupling
the argument rests on, from outside, without touching a private function. One graph of two rows
carrying ten statused requests each, and two detectors differing only in `min_statused_calls`:

- at **10**, two disjoint blocks of ten exist, so a comparison is stated and the finding is
  `breaking`;
- at **20**, the population still clears the gate — twenty statused requests in total — and the
  leading block now consumes both rows, so the blocks overlap and the rationale says it holds
  only a level.

In neither case is a block *absent*. A `_periods` measured against a different floor from the
gate loses the comparison at ten, and both halves of that mutation are killed below.

## Whether a detector's decline is visible to anything, and what channel it should use

**Row 1 is invisible, completely.** `EfficiencyDetector.scan` yields `Finding` objects and
nothing else — no count, no list, no log line, no exception.
`test_a_declined_observation_leaves_no_trace_the_caller_could_count` asserts it rather than
describing it: a graph holding a foreign vendor's traffic produces findings equal, field for
field, to a graph that never held it. Rows 2 to 6 cannot occur, so the question does not arise
for them.

**No channel should be built for these six, and the reason is not that a third convention would
be worse — it is that there is nothing to report.** Five declines cannot happen. The sixth is
correct vendor scoping, and a count of it would be a count of every other vendor's traffic on
every run, which is a number that means "this repository calls more than one API".

**The declines in these modules that do cost findings are all covered, and none of them was in
scope.** Naming them is the useful output, because a later task looking for the reporting channel
should point it at these and not at the six:

| Statement | What is lost |
|---|---|
| `observed_drift:112-113`, `:118-119` — `if not shapes` / `if not sites` | an operation with a baseline and no indexed caller, or the reverse |
| `observed_drift:127-128` — `sample_count < MIN_SAMPLES` | every divergence below the floor, which today is every divergence there is |
| `observed_drift:210-211` — the read filter | a divergence in a field no call site reads |
| `status_rate:212-213`, `:214-215` — the floor and the threshold | an operation failing under the floor or under the rate |
| `status_rate:218-219` — `if not sites` | traffic to an operation nothing indexed resolves to |
| `efficiency:180` — an empty `reachable` list, which is a skip without a statement | the same, and quieter: there is no `continue` here for coverage to have missed |

**The shape it should use already exists inside `sync/detect/`.**
`ParameterDeprecationDetector.unlinked` is a `list[str]` attribute on the detector, populated by
a `scan` made deliberately eager for exactly that reason, and logged at `warning`. Its own
docstring makes the argument: *"Counted rather than merely skipped. A row this pipeline discards
in silence is the defect that keeps being found by hand here, and a number is what makes it
answerable later without re-reading a run's output."* That is the in-package instance of the
`IntakeReport.unreadable` convention the two sibling reports recommend one level down, the print
site already exists — `cli._scan` prints a per-detector count, including zero, on the stated
ground that a detector silently producing nothing is indistinguishable from one that is broken —
and adopting it needs no signature change on any of the three `scan` methods, because the count
lives on the instance. **That is the next task, and its subject is the table above.**

## `MIN_SAMPLES = 30`: chosen, from a citation, at a tolerance nobody argued for

The brief asked whether it was measured, cited, or chosen. It is **chosen**, and the choice is
documented rather than hidden — but no measurement stands behind it and none can today.

**It was chosen, and the instruction said so.** The number arrived whole in `23d1c5a` (2026-07-28),
the commit that created the module; `git log -S MIN_SAMPLES` over the file returns that commit and
nothing since. The brief that produced it, archived at
`docs/superpowers/reports/2026-07-29-m3-task-archive.md:252`, reads: *"Choose the floor, state your
reasoning, and make it a named constant rather than a literal."*

**The specification does not supply it.**
`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md:149` requires *a* sample floor
and names no number. Line 208 does name 30 — by pointing back at
`src/sync/detect/observed_drift.py:66`. The spec cites the implementation, not the other way
round, so there is no external number this one was derived from or checked against.

**The stated derivation is a real citation, correctly applied.** The rule of three (Hanley &
Lippman-Hand, 1983): an outcome absent from *n* independent samples has a 95% upper confidence
bound of about 3/*n*. At *n* = 30 that is ten per cent. The module docstring and the commit
message both give this argument, and it is the distinction the other three modules organise
themselves around: `efficiency` and `status_rate` each defer to it by name — *"the thirty
`observed_drift` could justify"* — and `vendor_change` states the objection it answers, refusing a
depth cut-off because *"there is still no labelled data to calibrate either against."* Of the
five thresholds in this package, this is the only one with an argument behind the number.

**What is chosen is the tolerance.** Inverting the rule of three requires picking the upper bound
you will accept before it yields an *n*, and nothing in the repository says why ten per cent
rather than five (which gives 60) or twenty (which gives 15). So the derivation is sound and its
input is a preference. That is a materially better position than `efficiency`'s three thresholds,
which are policy floors with no distribution-free argument at all, and it is not a measurement.

**Nobody can measure the right value yet, which is why it was not moved.** The spec's Sequencing
table (lines 204-209) records that the baseline is empty until somebody feeds it:
`record_observed_shape` has no caller outside the two readers, and the readers are constructed
only by `sync shapes`, which reads an export an operator hands it.
`docs/superpowers/reports/2026-07-29-database-state.md:131-132` measured the live table at one row
carrying `sample_count = 1` — twenty-nine short of the floor. A number nobody can justify still
beats a number somebody quietly moved.

**And the counter it gates on is not a clean measurement even once the baseline exists.** `sync
shapes` says so itself (`cli.py:1142-1145`): re-ingesting the same export converges on the same
rows and adds to `sample_count`, because the store cannot tell one export fed twice from two real
responses carrying identical bodies. So the quantity 30 is compared against is inflatable by an
operator error the command cannot detect. That does not make the floor wrong; it means the
distribution somebody would eventually calibrate it against will need a deduplicating feeder
before it is a distribution of observations rather than of ingests.

**A second reason not to move it, which is easy to miss.** `sync.verify.mock_response` imports it
(`mock_response.py:71`, defaulting two signatures at 135 and 249), so 30 is also the precedence
floor deciding whether an observed shape or the specification supplies a replay mock.
`test_mock_response.py:144-151` pins that the two stay one number by moving the detector's
constant and reloading. Changing the detector's floor silently changes what patched code is
verified against.

### The floor gates the row a finding is raised on, and not the row that grades it

Found while establishing the above, and it is the sharper half.

`_contradicts_earlier_window` decides `breaking` against `info`, which is where this module says
its confidence lives: *"Severity says what the finding rests on."* It reads **every** sibling row
for the field, whatever that sibling's `sample_count`. So a single observation — the count the
module's own docstring calls *"one upstream incident or one misbehaving account"* — promotes a
divergence from `info` to `breaking`.

The sibling need not even be the declared type. A lone earlier `null` is a divergence in its own
right, too thin to report on its own, and sufficient to grade a *different* divergence as the
vendor's behaviour having changed.

`test_a_single_earlier_observation_is_enough_to_grade_a_divergence_breaking` pins it, with
`test_the_same_divergence_with_no_earlier_sibling_at_all_is_informational` as the control so the
assertion is about the sibling rather than about the divergence. Both lines (238-242) are covered,
so this is not a defect this task fixes, and the fix is a severity policy the drift specification
should make rather than a detector edit — the honest options are to gate the sibling at the same
floor, to introduce a third severity for a corroborated-but-thin divergence, or to state in the
docstring that corroboration is deliberately ungated. The test exists so the asymmetry is visible
in the suite rather than only here.

## Whether any of the six can fire on a healthy vendor

**Row 1: constantly, on any healthy repository that calls two vendors.** That is correct scoping
rather than a false negative — but following it out finds two things that are not.

**Only one instance of each traffic-derived detector is ever constructed.**
`cli._detector_suite` builds `VendorChangeDetector` once per deprecation vendor, and says why:
*"`VendorChangeDetector` is scoped to one vendor, so a retired Anthropic model upserted into the
graph is invisible to the Stripe instance however correctly it was written."* The identical
argument applies to `ObservedDriftDetector`, `StatusRateDetector` and `EfficiencyDetector`, and it
is not applied — all three are constructed once, with the single `--vendor`. So a repository's
Twilio telemetry is declined at `efficiency:158` and at `status_rate:269-270`, no second instance
exists to read it, and the scan reports clean. That is a whole vendor's efficiency, status-rate
and drift findings absent, by construction, for the exact reason the file already rejected one
line above.

**Sharper: inside `sync run` the decline cannot be reached at all.** `store.truncate_all()`
(`cli.py:934`) empties every table the schema declares, and `_scan` runs inside the same
`with store.transaction():` block. Nothing between them writes `observed_call` or
`observed_shape`; the only writers are the separate `sync ingest` and `sync shapes` subcommands.
So during a run all three telemetry-derived detectors read empty tables, and row 1 is reachable
against the graph but not against the pipeline as sequenced. This is pre-existing and was noted
once in passing when `status_rate` shipped
(`docs/superpowers/reports/2026-07-29-orchestration-archive.md:2166`); it is restated here because
it is the honest answer to the brief's question. **Zero of the six are reachable during a
`sync run`. One of the six is reachable against a graph an operator populated out of band, which is
what the covering test constructs.**

Neither is this task's to change — `cli.py` belongs to the other coordinator — and neither is a
defect in `src/sync/detect/`.

**Rows 2 to 6: no.** They cannot fire on any vendor, healthy or otherwise.

## Unreachable, redundant, and which each of the five is

Three independent kinds of evidence, and the third is decisive.

1. **Structural.** Rows 2-4: `call_site.id` is a `TEXT PRIMARY KEY` and `upsert_call_site`
   derives it from `_stable_id`, so no path produces a null. Rows 5-6: the gate and the split
   measure the same floor with the same predicate over the same rows, proved above.
2. **The clause asserted in the suite.** `test_the_column_a_call_site_id_is_read_from_cannot_be_null`,
   `test_every_call_site_the_store_hands_a_detector_carries_an_id` and
   `test_the_floor_that_gates_a_finding_is_the_floor_that_splits_the_periods` pin the three claims
   the argument rests on, so a change that revives any guard turns a test red rather than passing
   unnoticed.
3. **Each of the five replaced by `raise AssertionError`, against the whole suite.** All five
   survive. The control is the sixth statement given the same treatment: `efficiency:158` as
   `raise AssertionError` is **killed, 3 failed**, so the probe discriminates reachable from
   unreachable rather than being blind.

**Which kind each is.** Rows 2, 3, 4 and 6 are **unfalsifiable by any fixture** — the condition
cannot occur, no input makes them observable, and nobody should go looking for the fixture. None
of the four is redundant: delete row 2, 3 or 4 and a `None` would reach `Finding(call_site_id=…)`,
which is a `ValidationError`; delete row 6 and `leading > len(rows) - trailing` would be
`None > int`, which is a `TypeError`. Each is a guard against a state that cannot arise, which is
a different thing from a clause a later clause subsumes.

Row 5 is **unfalsifiable and redundant**: `_leading_block`'s trailing `return None` is what Python
does off the end of a function anyway, so it is explicitness rather than logic — and therefore no
mutation that *deletes* it can ever be informative. That is the same category as `mutate.py`'s 539
and 572, reached independently.

**Nothing here is reachable-and-redundant**, which is the category
`2026-07-29-mutation-engine-declines.md` found at `mutate.py:528` and
`2026-07-29-hand-written-symbol-maps.md` found twice. **Nothing was removed.** Every earlier report
reaching this verdict left the clause, and the reason transfers unchanged: it is a production change
no test proves necessary, and in rows 2-4 the guard is the one place a reader learns that
`CallSite.id` is optional in the type and mandatory in the table.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the
statement each covers. Harness at `%TEMP%\w103\mutate.py`, not committed. It asserts each mutation
string matches exactly once, `compile()`s the mutated source before pytest sees it, classifies from
the summary **counts** rather than from line prefixes, and asserts the restored baseline green at
the same pass count before and after — so a survival is distinguishable from a blind harness.

The killable set ran over `test_detector_declines.py`, `test_efficiency_detector.py`,
`test_status_rate_detector.py` and `test_observed_drift.py` with `-n0`. The unreachability probe
ran over the whole of `tests/` with `-n auto`.

| # | Statement | Mutation | Outcome | Killed by |
|---|---|---|---|---|
| E-158a | `efficiency:158` | `continue` → `pass` (the foreign row is read) | KILLED, 3 failed | `…another_vendor_s_traffic_against_a_shared_operation_id_raises_nothing`, `…another_vendor_s_louder_trace_never_displaces_the_quoted_one`, `…declined_observation_leaves_no_trace…` |
| E-158b | `efficiency:158` | guard compares `repo_id` instead of `vendor_id` — a plausible wrong guard, and inert because `observed_calls` already filters by repository | KILLED, 3 failed | the same three |
| U-EFF158 | `efficiency:158` | `continue` → `raise AssertionError` — **the control for the probe below** | KILLED, 3 failed | the same three |
| S-COUPLE | `status_rate:292` | the leading block measured against `self._floor * 2` | KILLED, 2 failed | `…floor_that_gates_a_finding_is_the_floor_that_splits_the_periods`, `…rate_that_rose_between_the_earliest_and_latest_samples_is_breaking` |
| S-COUPLE2 | `status_rate:293` | the trailing block measured against `self._floor * 2` | KILLED, 2 failed | the same two |
| D-SEV | `observed_drift:238-242` | the corroborating sibling gated at `MIN_SAMPLES` | KILLED, 1 failed | `…single_earlier_observation_is_enough_to_grade_a_divergence_breaking` |
| U-OD173 | `observed_drift:173` | `continue` → `raise AssertionError` | **SURVIVED** | unfalsifiable by any fixture |
| U-OD209 | `observed_drift:209` | `continue` → `raise AssertionError` | **SURVIVED** | unfalsifiable by any fixture |
| U-SR230 | `status_rate:230` | `continue` → `raise AssertionError` | **SURVIVED** | unfalsifiable by any fixture |
| U-SR187 | `status_rate:187` | `return None` → `raise AssertionError` | **SURVIVED** | unfalsifiable and redundant |
| U-SR295 | `status_rate:295` | `return None, None` → `raise AssertionError` | **SURVIVED** | unfalsifiable by any fixture |

Six killable mutations, six killed — three at the one reachable decline and three at covered lines
the new tests pin. Five unreachability probes, five survived. **The three mutations at
`efficiency:158` are what make the survivals readable**: `U-EFF158` is the identical
`raise AssertionError` treatment given to a statement an input does reach, and it kills. So the five
survivals are the statement not being reached rather than the probe not working.

Two baselines, both asserted green before and after. The killable run: **82 passed** before, 82
after, over the four detector test files with `-n0`. The unreachability probe: **2474 passed**
before, 2474 after, over the whole of `tests/` with `-n auto`. Nothing failed to compile and
nothing came back UNREADABLE.

`S-COUPLE` and `S-COUPLE2` also kill a test that predates this task
(`test_a_rate_that_rose_between_the_earliest_and_latest_samples_is_breaking`), which is worth
noticing rather than counting: the floor coupling was already load-bearing for an existing
assertion, and the new test is what says *why* out loud.

### The four false-verdict modes, and which one bit

All four were answered by construction and **none produced a verdict**, which is what "answered by
construction" is supposed to look like:

- `--color=no`, and classification from pytest's summary counts rather than from a `FAILED ` prefix.
- `-n0` for the focused runs rather than `-p no:xdist`, so no plugin flag collides with the repo's
  `-n auto`; and any exit code that is not 0 or 1, or any run yielding no parseable counts, is
  UNREADABLE rather than a survival.
- `compile()` on the mutated source before pytest is invoked, so a `SyntaxError` is
  DID-NOT-COMPILE up front instead of arriving as an `ERROR`.
- `PYTHONIOENCODING=utf-8` in the child's environment and `errors="replace"` on the decode.
  `encoding="utf-8"` on the call chooses how to decode arriving bytes rather than which bytes
  arrive.

**On that fourth mode, the measured position rather than the assumed one.** All five modules under
`src/sync/detect/` are **pure ASCII** — they write `--` rather than an em dash throughout — so
unlike the two surfaces where this mode produced a false verdict, the production source could not
have triggered it. The hazard was still live, one file over: `tests/test_efficiency_detector.py:299`
carries `E2 80 94` in a docstring, and that file is in the harness's path set, so pytest renders it
whenever a test in it fails. Byte census over all nine files the harness touches:

    src\sync\detect\*.py                     none
    tests\test_detector_declines.py          none
    tests\test_observed_drift.py             none
    tests\test_status_rate_detector.py       none
    tests\test_efficiency_detector.py        [226, 128, 148]

So the guard's subject is the test tree rather than the module under mutation, which is worth
recording because three earlier reports attributed the risk to the mutated module's own prose and
that is not where it lives here. **And it was never exercised:** the em dash sits in
`test_a_cost_reaching_one_call_site_is_not_described_as_shared`, and no mutation in this run made
that test fail, so pytest never rendered the frame. Answered by construction, and the honest note
is that the run did not test the answer.

Two mutations are worth naming for what they would have shown had the harness been careless.
`E-158b` and `U-EFF158` differ only in what replaces the decline, and a two-outcome harness reading
exit codes alone would have scored `U-EFF158` — which raises rather than fails an assertion — as
indistinguishable from `E-158a`. The distinction is the whole probe: an `AssertionError` at a
*reachable* statement kills, and at an unreachable one it is invisible, so the same mutation used
twice is what separates "no test covers this" from "no input can reach this".

### The fixture the mutation forced, and why the obvious one could not fail

`E-158a` and `E-158b` are only killable if the two vendors' populations can **collide**, and they
collide on `operation_id` — the key `strongest` holds its per-claim winner under, with no vendor
component. The obvious fixture gives one vendor `GetCharges` and the other `ListMessages`, and it
cannot fail however the guard is broken: the foreign claim is produced, `call_sites_for_operation`
finds nothing for the foreign operation, and the finding is lost one line later for an unrelated
reason. The fixture therefore gives both vendors an operation id they both plausibly publish
(`GetAccount`), which is what makes the deletion observable — and which is also how the
`strongest`-key observation was found rather than reasoned about.

This is the fourth task running in which the fault behind a first-pass survival was the fixture
rather than the code.

## Three docstrings describing a state their code no longer has

Checked deliberately rather than assumed, because two files elsewhere in the repository were found
this way on the same day.

**1. `observed_drift.py:73-78` is false.** `DeclaredField`'s docstring says it lives in the
detector *"because nothing in the repository parses a response schema yet; the first component that
does should own the type and this module should import it."* `cli._declared_response_fields`
(`cli.py:436`) parses one now — and **its own docstring records the same fact from the other side**:
*"nothing in the repository turned a specification into declared fields — the detector shipped able
to run and with no way to be given its own input."* Two docstrings in one repository, contradicting
each other, and the stale one is carrying an instruction that is now due and invisible to anyone
reading the module. The sentence wants to become: the type lives here, `cli._declared_response_fields`
is the component that parses a specification into it, and whether it should move to `sync.core` is a
decision somebody now has to make.

**2. `status_rate:176-181` and `:281-291` describe the absent-block case as live.**
`_leading_block`'s summary is *"…or `None`"* and `_periods`' is *"The earliest and latest samples
large enough to be rates, **if two exist**"*, and `_periods` then argues *"Anything less is a rate
compared against an impression."* Only the overlapping-block case at 297 is live; the absent-block
case at 187 and 295 cannot occur. A reader takes those two summaries as describing two live
outcomes and there is one.

**Neither 1 nor 2 was edited.** This task's brief permits modifying the three detector modules
**only if a test proves a defect**, and no test proves a stale sentence. Both are reported with the
replacement named, which is the same trade five earlier reports made on production changes no test
demanded.

**3. `tests/test_efficiency_detector.py:318` and `:339` named `_rationales`, a method that does not
exist. Fixed.** The method is `_claims`, and the second reference belongs to `scan`, whose docstring
carries the "N findings would assert N savings that do not exist" argument. The file is this task's
to modify. Worth one line on why it rotted: the gate is
`lint_dead_links.py src --baseline …`, which does not read `tests/`, so a test docstring can name a
symbol that has been renamed and nothing notices.

## No defect was found in the production code, and nothing in it changed

Six statements accounted for, one covered, five unreachable with three independent kinds of
evidence, and **no change to any file under `src/`**. `git diff --stat` against the merge base is
two test files and this report.

Four things are reported rather than repaired, each for a stated reason:

- **`MIN_SAMPLES = 30` is a chosen tolerance behind a cited derivation**, and the observed-drift
  baseline is empty, so nobody can measure the right value. Not moved, deliberately.
- **The floor gates the divergent row and not the sibling that grades its severity**, so one
  observation can promote a finding to `breaking`. Covered lines; the fix is a severity policy the
  drift specification should make.
- **Three traffic-derived detectors are constructed once for one vendor** where
  `VendorChangeDetector` is constructed per vendor for the identical reason, and inside `sync run`
  all three read tables `truncate_all` emptied moments earlier. `cli.py` is the other coordinator's.
- **Two stale docstrings**, named above with their replacements.

## Fixtures and provenance

**No fixture file was created.** Every input is an inline model construction at the assertion,
which is how all three existing detector test files state a shape, and every one of them is a
graph state rather than a document — a call site, an `observed_call`, an `observed_shape`. There is
nothing to put in a file.

One test reads no fixture at all: `test_the_column_a_call_site_id_is_read_from_cannot_be_null`
queries `information_schema.columns` on the live database, because the claim being made is about
the schema and asserting it against a Python constant would prove only that the constant was
copied correctly.

No test here calls a vendor API or a model API.

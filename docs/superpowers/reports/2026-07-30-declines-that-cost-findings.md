# Eight declines that cost findings, and one that costs nothing

M3-W106, following `2026-07-29-detector-declines.md`. That report examined the six *uncovered*
declines in `src/sync/detect/` and found five of them cannot happen. Its closing finding is this
task: **the declines that actually lose a finding are all covered**, so no coverage number will
ever point at them, and until now not one of them left anything a caller could count.

Seven are counted now, on three detectors, through the channel the eighth already had. The four
things the count is deliberately *not* are as load-bearing as the seven, and each is argued below
rather than assumed and held by a test of its own.

## The channel, and the one deviation

`ParameterDeprecationDetector.unlinked` was the named precedent and it is the one used: a
counted `list[str]` on the detector, reset by an eager `scan`, each entry naming its subject and
its cause, and `cli._scan` printing the count. No `scan` signature changed — all four still
return `Iterable[Finding]`, and three that were generators now return a list for the reason the
precedent's own docstring gives: *"a generator nobody finished consuming would leave the count
describing part of the work."*

**The deviation is the name.** `unlinked` is now `declined`, on all four detectors.

`_scan` has to read one attribute. The alternatives were a table in `cli.py` mapping each
detector to its own vocabulary — per-detector knowledge in the one file whose whole job is not
to hold any — or a `getattr` checking two names, which is the fourth convention for this fact
that the brief rules out in substance if not in spelling. One name across one package is the
reuse; `unlinked`'s docstring moved onto `declined` unchanged, because the argument in it is
about counting and not about linking.

Nothing outside `src/sync/detect/parameter_deprecation.py` referred to `unlinked`. Three test
assertions moved with it.

**A detector with no channel prints no decline clause.** `vendor_change` is read-only to this
task and has none, and `vendor_change: 0 finding(s), 0 declined` would be a claim it never made.
Present-and-empty is the position for a detector that *has* the channel — a wired channel with
nothing in it prints `0 declined` — and that is the distinction `report.unreadable` already
draws one function away in the same file.

**One thing `unlinked` does that the three new channels do not: log each entry at `warning`.**
The count is printed at the one output site and the entries stay on the instance, addressable by
a test or by a later `--explain`, which is what `IntakeReport.unreadable` does — *"returned
rather than printed here, and counted by the caller."* Emitting the reasons as well is a
decision about operator output that this task was not asked to make and that has a real noise
cost, and it is listed below as a next task rather than taken quietly.

## What is counted

| Detector | Decline | What it costs |
|---|---|---|
| `parameter-deprecation` | a deprecation with no `VendorChange` id | pre-existing; renamed only |
| `efficiency` | a claim whose operation resolves to no indexed call site | the cost finding outright |
| `status-rate` | a failing population under `MIN_STATUSED_CALLS` | the rate, to the sample floor |
| `status-rate` | a failing population under `ERROR_RATE_THRESHOLD` | the rate, to a policy number |
| `status-rate` | a rate that resolves to no indexed call site | the finding outright |
| `observed-drift` | a baseline no indexed call site resolves to | every divergence on that operation |
| `observed-drift` | a divergence or undescribed field under `MIN_SAMPLES` | today, every divergence there is |
| `observed-drift` | a divergence in a field no call site reads | the finding outright |

Two of these are the numbers the modules admit they cannot calibrate. `ERROR_RATE_THRESHOLD`
*"gets no argument and is a policy floor"* by its own docstring, and `MIN_SAMPLES` is a chosen
tolerance behind a cited derivation. Until now the only way to see what either silenced was to
move it and re-run a scan.

`observed_drift` computes the divergence **before** applying the floor rather than after, because
whether a thin shape was a finding the floor cost is exactly what the count has to know. That is
the one structural change inside a scan loop; it moves no emission.

## What is not counted, and why each exclusion is a test

A count that fires on every ordinary input is not a measurement of lost work — it is a
description of the traffic, and it would drown the eight above. Each of the four exclusions has a
test whose whole job is to fail if the counter becomes indiscriminate, and a mutation in the table
below that makes it fire.

**A row belonging to another vendor.** `efficiency` and `status_rate` both decline these, and
both declines are correct scoping rather than a lost finding: the finding belongs to an instance
scoped to the other vendor. Counting them puts a number on every run that says "this repository
calls more than one API". `test_a_foreign_vendor_s_traffic_is_declined_without_being_counted` and
`test_a_foreign_vendor_s_population_is_declined_without_being_counted` hold it, and `E4`/`S6`
below are the mutations that make them non-vacuous.

**A population that returned no failures.** A thin population with zero errors, or one clearing
the floor with zero errors, declined nothing — there was no rate to state. Without this
discrimination the status-rate count would be a count of healthy operations.

**A thin shape that agrees with the specification.** Same shape of argument one detector over:
below the floor and matching what the vendor published is not a divergence the floor silenced.

**`observed_drift`'s `if not shapes`.** This is the one the preceding report tabled that is *not*
carried, and the reason is worth stating rather than glossing.

The branch fires once for every operation the specification declares. `_declared_fields` hands
the detector every operation Stripe publishes, and inside `sync run` `truncate_all` has emptied
`observed_shape` moments earlier, so the count would be the size of the vendor's specification,
every run, forever. That is precisely the number the preceding report refused for the
cross-vendor guard: one that means "this vendor publishes more operations than this customer
calls".

The half of that row which *is* a lost finding — a baseline with no indexed caller — is carried,
because by then the detector holds shapes it computed nothing from. The other half — an indexed
caller with no baseline — is genuinely informative and **is not reachable at that branch**:
distinguishing "the customer calls this and we have no traffic" from "the customer never calls
this" needs the call-site query the branch exists to skip. Running it for every declared
operation doubles this detector's query count against a specification of that size, which is a
latency decision rather than a detector edit. Named below as a next task with its cost stated.

## The cross-vendor guard: the construction is the defect, the key is not

The preceding report found that `efficiency`'s `strongest` is keyed `(operation_id, claim.kind)`
with no vendor component, and asked whether the real defect is that key or the fact that three
telemetry detectors are constructed once for one vendor where `VendorChangeDetector` is
per-vendor. They are different fixes and the answer is the second.

**The key is safe as written, and only because the guard is there.** `strongest` is a local in
`scan`, and every row that reaches it has already passed `call.vendor_id == self._vendor_id`. One
vendor's rows are the only rows the dict ever holds, so the missing vendor component cannot
contaminate anything. The guard is not compensating for a bad key; it is what makes the key
correct.

**And it stays necessary after the fix.** `GraphStore.observed_calls(repo_id)` returns every
vendor's rows, so a per-vendor `EfficiencyDetector` still has to filter to its own. Making the
detectors per-vendor does not retire the guard — it gives the rows it declines somewhere to
land instead of nowhere.

**What is wrong is that no second instance exists.** `cli._detector_suite` builds
`VendorChangeDetector` once per deprecation vendor and states why: *"`VendorChangeDetector` is
scoped to one vendor, so a retired Anthropic model upserted into the graph is invisible to the
Stripe instance however correctly it was written."* The identical argument applies to
`ObservedDriftDetector`, `StatusRateDetector` and `EfficiencyDetector`, and it is not applied —
all three take the single `--vendor`. A two-vendor repository loses the whole of the second
vendor's efficiency, status-rate and drift findings, by construction, one line below the file's
own statement of the rule.

**So: a defect, not a decision.** `cli._detector_suite` is not this task's to change — this
brief permits only the per-detector print site in that file, and the surrounding line belongs to
the other coordinator — so it is reported.

### A second key defect, found while establishing the first

`strongest`'s key is missing `server_address`, and that one is not covered by the guard.

`status_rate` keys its populations `(operation_id, server_address, http_method)` and puts the
host into `Finding.claim` on the stated ground that *"one operation failing on a sandbox host
and on a live one is two integrations and two claims."* `efficiency` merges them: a sandbox
trace looping five hundred times displaces a production trace looping twelve for the same
operation, and the rationale that survives names the sandbox host.

**Widening `strongest`'s key alone would not fix it and would introduce a worse bug.**
`Finding.claim` is `claim.kind` with no host, and `insert_finding` derives its id from
`_stable_id(detector, call_site_id, vendor_change_id, claim)`. Two entries differing only by
host would produce the same id and `ON CONFLICT (id) DO NOTHING` would drop the second in
silence — the family of defect `efcc19d` was and that `schema.sql`'s grain comment exists to
prevent. The fix is to put the host in the claim as `status_rate` does, which changes finding
identity in the graph. That is a decision about grain, not a detector edit, and it is reported
rather than made.

## The instruction that came due, and what was done about it

`observed_drift.py`'s `DeclaredField` said:

> This lives here rather than in `sync.core` because nothing in the repository parses a response
> schema yet; the first component that does should own the type and this module should import
> it.

`cli._declared_response_fields` parses one, so the sentence was an instruction whose condition
had already arrived and which nobody could see had fallen due. Correcting the tense would not
have been enough: the next reader assumes the condition has not happened.

**It is settled, and the type stays.** The condition arrived in a form the instruction did not
anticipate. The component that parses a specification into `DeclaredField`s is the CLI, which
sits *above* the detector — `cli.py:27` imports `DeclaredField` from
`sync.detect.observed_drift` — and a detector importing a CLI symbol inverts the dependency. So
a parser existing is not on its own a reason to move the type.

The home that would serve both is `sync.core`. That is a published contract a third party
writing a vendor adapter depends on, and `src/sync/core/` is forbidden to this task for exactly
that reason. Putting a detector's type into it is a decision about that contract rather than a
refactor, and the docstring now says so. A reader inherits a position instead of a stale
instruction; a next task is listed below.

## The two docstrings, before and after

Two in the brief's counting, three sites: `observed_drift.DeclaredField`, and `status_rate`'s
pair at `_leading_block` and `_periods`.

**1. `observed_drift.DeclaredField`.**

Before: *"This lives here rather than in `sync.core` because nothing in the repository parses a
response schema yet; the first component that does should own the type and this module should
import it."*

After: *"The component that parses a specification into these is `cli._declared_response_fields`,
which sits above this module: a detector importing a CLI symbol inverts the dependency, so a
parser existing is not on its own a reason to move the type. The home that would serve both is
`sync.core`, and that is a published contract a third party writing a vendor adapter depends on
— putting a detector's type into it is a decision about that contract, and it has not been
made."*

**2. `status_rate._leading_block`.**

Before, the summary line: *"How many rows from the front it takes to reach `floor` statused
requests, or `None`."*

After: the `or None` is gone from the summary, and a paragraph says the `None` cannot arrive at
the only caller there is — `scan` reaches `_periods` only once the same rows cleared the same
floor under the same predicate — and why the return stays anyway: a caller measuring against a
different floor would need it, and deleting it makes `leading > len(rows) - trailing` a
`TypeError` rather than a refusal.

**3. `status_rate._periods`.**

Before: *"The earliest and latest samples large enough to be rates, if two exist."*

After: *"…when they do not overlap"*, with a paragraph stating that two blocks always exist
because the gate and the split measure the same floor over the same rows, that the absent-block
return is unreachable from `scan`, and that the only question the function really answers is
whether the two ends are disjoint.

A reader took 2 and 3 as descriptions of two live outcomes — a block that is absent and two
blocks that overlap. There is one, and it is the overlap.

## Mutation table

Harness at `%TEMP%\w106\mutate.py`, not committed. Every test here pins a behaviour this task
added, so "fails first" was established by writing the test against absent code and watching the
`AttributeError` — the channels did not exist — and then by these mutations once they did.

The harness asserts each mutation string matches **exactly once**, `compile()`s the mutated
source before pytest sees it, classifies from pytest's summary **counts** rather than from any
line prefix, and asserts the restored baseline green at the same pass count before and after.
It ran over eight files with `-n0`: the four detector test files, this task's new file, both
parameter-deprecation files, and `tests/test_cli.py` for the output site.

**Baseline 177 passed, exit 0, before and after.** Nothing failed to compile, nothing came back
UNREADABLE, and nothing came back BASELINE-DRIFTED.

| # | Statement | Mutation | Outcome | Killed by |
|---|---|---|---|---|
| C1 | `cli._scan` | the decline clause is never built (`note = ""`) | KILLED, 2 failed | `…scan_output_names_the_detector_and_its_decline_count`, `…clean_scan_reports_its_declines_as_zero…` |
| C2 | `cli._scan` | an absent channel defaults to `[]`, so a channelless detector prints `0 declined` | KILLED, 1 failed | `…detector_with_no_channel_claims_nothing_about_its_declines` |
| P1 | `parameter_deprecation._drop` | the append becomes a bare expression | KILLED, 2 failed | `…dropped_deprecation_is_observable`, `…drop_counter_resets…` |
| P2 | `parameter_deprecation.scan` | the per-scan reset removed | KILLED, 1 failed | `…drop_counter_resets_rather_than_accumulating_across_scans` |
| E1 | `efficiency.scan` | the whole decline block replaced by a bare `continue` | KILLED, 2 failed | `…cost_claim_with_no_indexed_call_site_is_counted`, `…every_channel_reports_the_same_declines…` |
| E2 | `efficiency.scan` | `if not reachable` becomes `if True` | KILLED, 15 failed | 15, including every finding test in the file — **see below** |
| E3 | `efficiency.scan` | the per-scan reset removed | KILLED, 1 failed | `…every_channel_reports_the_same_declines_on_a_second_scan` |
| E4 | `efficiency.scan` | the foreign-vendor row is counted | KILLED, 1 failed | `…foreign_vendor_s_traffic_is_declined_without_being_counted` |
| E5 | `efficiency.scan` | a spurious append **after** a non-empty `reachable`, leaving every finding intact | KILLED, 2 failed | `…cost_claim_that_reaches_a_call_site_is_not_counted_as_declined`, `…foreign_vendor_s_traffic_is_declined_without_being_counted` |
| S1 | `status_rate.scan` | the floor decline drops its `errors` condition | KILLED, 1 failed | `…operation_with_no_failures_under_the_floor_declines_nothing` |
| S2 | `status_rate.scan` | the floor decline never fires | KILLED, 1 failed | `…operation_failing_under_the_sample_floor_is_counted` |
| S3 | `status_rate.scan` | the threshold decline never fires | KILLED, 2 failed | `…operation_failing_under_the_rate_threshold_is_counted`, `…every_channel_reports…` |
| S4 | `status_rate.scan` | the threshold decline fires unconditionally | KILLED, 1 failed | `…operation_clearing_the_floor_with_no_failures_declines_nothing` |
| S5 | `status_rate.scan` | the no-call-site decline never fires | KILLED, 1 failed | `…rate_that_resolves_to_no_indexed_call_site_is_counted` |
| S6 | `status_rate._populations` | the foreign-vendor row is counted | KILLED, 1 failed | `…foreign_vendor_s_population_is_declined_without_being_counted` |
| S7 | `status_rate.scan` | the per-scan reset removed | KILLED, 1 failed | `…every_channel_reports_the_same_declines_on_a_second_scan` |
| D1 | `observed_drift.scan` | the no-call-site decline never fires | KILLED, 2 failed | `…baseline_no_indexed_call_site_resolves_to_is_counted`, `…every_channel_reports…` |
| D2 | `observed_drift.scan` | `if not shapes` is counted | KILLED, 1 failed | `…operation_with_no_observed_shape_at_all_is_not_counted` |
| D3 | `observed_drift.scan` | the floor decline never fires | KILLED, 2 failed | `…divergence_under_the_sample_floor_is_counted`, `…undescribed_field_under_the_sample_floor_is_counted` |
| D4 | `observed_drift.scan` | the floor decline fires for every thin shape | KILLED, 1 failed | `…thin_shape_that_matches_the_specification_is_not_counted` |
| D5 | `observed_drift.scan` | the read-filter decline never fires | KILLED, 1 failed | `…divergence_no_call_site_reads_is_counted` |
| D6 | `observed_drift.scan` | the per-scan reset removed | KILLED, 1 failed | `…every_channel_reports_the_same_declines_on_a_second_scan` |

Twenty-two mutations, twenty-two killed. Twenty-one ran through the harness over the eight-file
set; E5 was run by hand afterwards over three of them (this file, `test_efficiency_detector.py`
and `test_detector_declines.py`, 53 tests) because it was written in response to E2.

**Eight of the twenty-two are the exclusions**: C2, E4, E5, S1, S4, S6, D2 and D4 each make a
counter fire where it should not, and each is killed by the one test whose job is to say so.
Without them the seven counted kinds would be proved and the four refusals would be decoration.

**E2 is coarse and E5 exists because of it.** Replacing `if not reachable` with `if True` also
takes the `continue` with it, so no efficiency finding is emitted at all and fifteen tests die —
which proves nothing about whether the *count* is discriminating. E5 is the surgical form: an
unconditional append placed after a non-empty `reachable`, leaving every finding exactly as it
was. It kills `test_a_cost_claim_that_reaches_a_call_site_is_not_counted_as_declined` on the
count alone. E2 is kept in the table because deleting a mutation whose verdict was weak
evidence, rather than saying so, is how a table starts flattering itself.

### P2 survived on the first run, and the fault was the test

The first complete run scored **P2 as SURVIVED**. Suspecting the mutation first: it deletes
`self.declined = []` from `ParameterDeprecationDetector.scan`, so the count accumulates across
scans and a second scan reports twice the dropped work. Real defect, matched exactly once,
compiled. The mutation was sound.

The fault was the test. `test_scanning_twice_gives_the_same_answer` carried the comment *"The
drop counter is part of the answer now, so it has to reset per scan rather than accumulate across
them"* and asserted `detector.declined == []` — over a fixture whose deprecations are all
**linked**, so nothing is ever dropped and the counter is empty with the reset or without it. A
test that could not fail on the claim its own comment made.

`test_the_drop_counter_resets_rather_than_accumulating_across_scans` scans twice over an unlinked
deprecation and asserts the count is one. It kills P2. The overclaiming comment now points at it
instead of claiming the coverage itself.

**That is the tenth consecutive time on this project that the fault behind a first-pass survival
was outside the production code**, and the fourth in a row that it was the fixture or the
assertion rather than the mutation.

### The five false-verdict modes, and which one could have bitten

All five were answered by construction and none produced a verdict.

- `--color=no`, and classification from the summary **counts**, never from a `FAILED ` prefix.
  The prefix is parsed too, but only for the *names* in the last column, so a colourised summary
  would have emptied that column rather than turning a kill into a survival.
- `-n0` rather than `-p no:xdist`, so no plugin flag collides with the repo's `-n auto`; and any
  exit code outside `(0, 1)`, or any run yielding no parseable counts, is UNREADABLE rather than
  a survival.
- `compile()` on the mutated source before pytest is invoked, so a `SyntaxError` is
  DID-NOT-COMPILE up front instead of arriving as an `ERROR`.
- `PYTHONIOENCODING=utf-8` in the child's environment, output captured as **bytes** and decoded
  here with `errors="replace"` — because `subprocess.run(..., text=True, encoding="utf-8")`
  chooses how to decode arriving bytes, not which bytes arrive.
- The exit code is read off the `CompletedProcess`, never from a shell after a pipe, so
  `pytest -q; echo $?` cannot report `echo`'s status in its place.

**On the encoding mode, the measured position rather than the assumed one.** W103 measured all
five `src/sync/detect/*.py` as pure ASCII and that still holds after this task's edits — every
new docstring writes `--` rather than an em dash. So the production source could not have
triggered it. The census over all fourteen files this task touched or the harness reads:

    src\sync\detect\*.py                       none
    src\sync\cli.py                            none
    tests\test_declines_that_cost_findings.py  none
    tests\test_detector_declines.py            none
    tests\test_status_rate_detector.py         none
    tests\test_observed_drift.py               none
    tests\test_parameter_deprecation_link.py   none
    tests\test_parameter_detector.py           none
    tests\test_cli.py                          none
    tests\test_efficiency_detector.py          [128, 148, 226]

The one hazard is where W103 found it: two em dashes at `tests/test_efficiency_detector.py:299`
and `:300`, in a file the harness renders whenever a test in it fails. Checked rather than
inherited — they sit inside
`test_a_cost_reaching_one_call_site_is_not_described_as_shared`, and **E2 failed that test**,
among the fifteen it killed. So unlike W103, where the answer was answered by construction and
never exercised, pytest did render that frame here and the decode came back clean.

## Next tasks this produced

Four, each blocked by a boundary this brief drew rather than by an unknown.

1. **`_detector_suite` should construct `ObservedDriftDetector`, `StatusRateDetector` and
   `EfficiencyDetector` per vendor**, as it already does for `VendorChangeDetector` and for the
   reason it already gives. Today a two-vendor repository loses the whole of the second vendor's
   telemetry findings. `cli.py` belongs to the other coordinator.
2. **`EfficiencyDetector.claim` should carry `server_address`**, as `status_rate`'s does, and
   `strongest` should key on it. Without the first half the second silently drops a row at
   `ON CONFLICT DO NOTHING`. This is a decision about finding identity in the graph.
3. **`DeclaredField` should move to `sync.core`**, which is the home the retired instruction
   meant. `src/sync/core/` is a published contract with third-party consumers and was forbidden
   here.
4. **The decline reasons should reach an operator, not only the count.** They are on the
   instance and printed nowhere. `report.unreadable`'s one-line-per-problem-to-stderr is the
   established shape; whether a detector that declines a few hundred rates should use it is the
   open question.

And one thing measured rather than fixed: `observed_drift` cannot distinguish an operation the
customer calls and has no traffic for from one the customer never calls, because that needs a
call-site query per declared operation. For a specification of Stripe's size that doubles the
detector's query count, which makes it a latency decision.

## Gates

Run on a tree with `origin/main` merged in — twice, because it moved twice while this task's
harness and gates were running. The second merge brought `2026-07-30-mcp-tool-surface-declines`
and the MCP tool tests, none of which touch `src/sync/detect/`, `src/sync/cli.py` or any file
this task's mutations read, so the table above stands over it unchanged.

| Gate | Result | Exit |
|---|---|---|
| `uv run pytest -q` | 2604 passed, 2 skipped in 111.42s | 0 |
| `uv run python scripts/lint_encoding.py src scripts tests` | clean | 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | Analyzed 95 files, 201 dependencies. 1 contract kept, 0 broken | 0 |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | clean | 0 |

`pytest` was run unpiped, with its exit code read from the process rather than from a shell after
a pipe; `lint-imports` unredirected with `PYTHONIOENCODING=utf-8`.

**The arithmetic closes.** `origin/main` collected 2584 of 2585 with 1 deselected, which is 2582
passing beside the 2 skipped; this branch passes 2604. The difference is 22, and 22 is exactly
this task's new tests — 21 in `tests/test_declines_that_cost_findings.py` and one in
`tests/test_parameter_deprecation_link.py`. No pre-existing test was deleted or renamed.

`lint_dead_links.py` reads `src` only, so identifier references in *test* docstrings are checked
by hand. This task added three:
`test_the_drop_counter_resets_rather_than_accumulating_across_scans`,
`test_scanning_twice_gives_the_same_answer` and
`test_a_foreign_vendor_s_traffic_is_declined_without_being_counted`, plus `ReachabilityRanking`
and `IntakeReport` — all five resolve.

### The `binding_rung` column B65 and B66 made mandatory

`GraphStore.insert_finding` now refuses a finding whose rung is `unattributed` and names the
detector that raised it. **Nothing here had to change.** All four detectors already declared a
rung on every finding they emit — `static` in `parameter_deprecation` and both
`observed_drift` paths, `call.binding_rung` in `efficiency`, `_weaker_rung(rows)` in
`status_rate` — and this task added no emission, only counts of emissions that did not happen.
Checked rather than assumed: the merged tree's suite is green, including
`tests/test_finding_rung.py`.

## Fixtures and provenance

**No fixture file was created.** Every input is an inline model construction at the assertion,
which is how all four existing detector test files state a shape, and every one is a graph state
rather than a document — a call site, an `observed_call`, an `observed_shape`. There is nothing
to put in a file.

No test here calls a vendor API or a model API. The one non-local dependency is the Postgres
container, which is what `GraphStore` needs to answer a query at all.

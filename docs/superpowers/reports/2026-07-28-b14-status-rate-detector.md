# B14 — the status-rate detector

`src/sync/detect/status_rate.py`, `tests/test_status_rate_detector.py`, and two lines in
`src/sync/cli.py`. Nothing else was touched: `schema.sql`, `src/sync/telemetry/`, and the other
detectors are unchanged.

One line outside that set had to move. `tests/test_cli.py::test_the_suite_runs_every_detector`
asserts the detector suite's exact contents, so adding a detector fails it by construction; the
expected list now names `status-rate` between `observed-drift` and `efficiency`. That is the
direct consequence of the authorised `cli.py` line, and leaving it would have failed the gate.

## What was built, and what was not

M2 asks for "a change in 4xx or 5xx rate on one vendor operation". What ships is the honest
subset the brief allowed for: a **level** — an error rate at or above a floor, over enough
requests to be a rate — raised as a `Finding`, with a **change comparison used only to set
severity**, never to raise a finding.

That split is not a compromise invented here. `observed_drift` faced the same structure and
resolved it the same way, and its docstring states the principle outright: its
observed-now-against-observed-before comparison "never raises a finding by itself … It is
enrichment of a divergence found against the specification." This module inherits that unchanged.

### Why "change" cannot be the primary rule

Two obstacles, and the second is the larger one.

**There is no change point.** `observed_call` has `first_seen` and `last_seen` per row and the
grain is per trace. Rows sorted by `first_seen` are a time-ordered stream, so periods can be
*derived* — but nothing searches for *when* a rate moved. Any split chosen from the data (the
median trace, the midpoint of the time span) sits where the data happens to be divided rather
than where the behaviour changed: it dilutes a break that started late, and manufactures one out
of sampling noise when the rate never moved at all.

**The table does not hold history.** `cli.py:730` calls `store.truncate_all()` at the start of
every `sync run`, and that statement includes `observed_call`. So the table contains whatever
`sync ingest` folded in since the last run — for a single captured payload, possibly minutes of
traffic. Calling the first half of one ingested window "before" and the second half "after" would
be quoting a trend that does not exist. This is the fact that decides the question, and it is
stated in the module docstring rather than left for a reader to discover.

A side effect worth flagging separately: because `run` truncates `observed_call` and nothing
inside `run` repopulates it, **both traffic-derived detectors — this one and `efficiency` — read
an empty table during a `sync run`.** `sync ingest` is a separate subcommand. That is
pre-existing behaviour I did not introduce and did not change, since `telemetry/` and `cli.py`'s
run flow were out of scope, but it means this detector is wired and will produce nothing until
ingest and detection share a window. It is worth a follow-up task.

### What the change comparison does do

When the stored traffic supports it, the detector compares the **earliest requests held** against
the **latest requests held**. Both sides must independently clear the sample floor and must share
no row; rows between the two blocks belong to neither, so the comparison does not depend on where
a split fell. Severity is `breaking` only when the earlier block is below the threshold and the
later block is at or above it — one threshold, not a second uncalibrated number.

Everything else is `info`: a rate that was already at this level in the earliest sample, a rate
that fell, and — importantly — traffic that cannot supply two separated floor-sized samples at
all. In that last case the rationale says so in words rather than going quiet: "the traffic held
does not contain two separated samples large enough to compare, so no earlier rate is stated."

When it does claim a rise, the rationale carries its own qualification: "Those are the earliest
and latest requests stored, not the earliest and latest that happened — a run empties this table
— and nothing here searches for when the rate moved, so no start date is claimed."

### What a real change detector would need

A windowed rollup of statused spans per operation that **survives a run**: one row per
`(repo_id, vendor_id, operation_id, server_address, http_method, bucket)` carrying an error count
and a total count, where `bucket` is an hour or a day. That is a new table, so it is named here
and not built — the schema is shared and another worker may be in it.

Note that a rollup is additive and therefore cheap to keep, and it does *not* reopen the privacy
question: counts of status codes are already stored per span, and a bucketed count stores strictly
less.

## The denominator

**Failed requests over requests that carried a status, pooled across every row in the population.**
A request is a span. One span is one request and one response, and the status is a property of
that pair, so the span is the only unit the fraction can honestly use.

Three decisions inside that sentence:

**Not rows, and not traces.** `observed_call` is keyed per trace, so "traces containing an error,
over traces" is one cheap query away and gives a different number. A row is not a call — its own
docstring says so — and under that query one trace of two hundred clean requests weighs the same
as one trace of a single failure.

**A request with no status leaves the fraction entirely**, from numerator and denominator both.
`ObservedCall.error_count` already refuses to count one as an error, on the grounds that a request
that got no response is a real outcome and a separate question. Putting them in the denominator
would report every operation whose collector dropped responses as healthier than it is; putting
them in the numerator would assert a failure nobody observed. The count is quoted in the rationale
instead, so a reviewer can discount a rate computed over a shrunken sample.

**The population is `(operation_id, server_address, http_method)`** — the row's natural key without
the trace. `server_address` is in that key because, as `schema.sql` puts it, one operation reached
through two hosts is two integrations and merging them "would average a test workload into a
production bill". The argument is sharper for a rate than for a cost: a sandbox failing at forty
per cent, averaged into healthy production traffic, produces a number that describes neither
integration. `http_method` is carried along to mirror the natural key exactly; for a correlated
call it is nearly redundant, and mirroring is cheaper to defend than explaining an exception.

## The sample floor

`MIN_STATUSED_CALLS = 100` statused requests. Below it, no rate is stated at all.

The justification is not a policy, unlike `efficiency`'s thresholds. Healthy traffic carries a
background of failures that break nothing — a declined card, a 404 on a resource somebody deleted
— and the floor's job is to stop that background reaching the threshold by chance.

At a background rate of 2%, the chance that 100 requests show 10 or more failures is roughly one
in twenty thousand. At 30 requests — the floor `observed_drift` justifies — the same background
produces 3 failures in 30 about one time in forty, which across a few dozen operations is a false
finding most scans. That gap is the whole reason this floor is higher than `observed_drift`'s:
its question is "has this been seen enough times to be a baseline", and this one is "could this
proportion have come from a harmless one". Different question, different answer.

**The honest limit of that argument is the 2% it assumes.** An operation whose ordinary failure
rate is genuinely 5% clears the threshold by chance about three times in a hundred, and nothing
here holds a per-operation baseline to calibrate against. The rationale therefore quotes counts
and codes rather than asserting the rate is abnormal, and the docstring says this rather than
implying the floor is exact.

The cost is recall, and it is real: two disjoint floor-sized samples means 200 statused requests
before any `breaking` severity is reachable. Precision over recall is the committed direction, and
I would rather this detector be silent on a thin sample than confident on one.

`ERROR_RATE_THRESHOLD = 0.10` gets no such argument and is a policy floor in `efficiency`'s sense.
One request in ten failing is well clear of traffic anyone would call healthy, and the counts are
quoted so a finding can be judged without trusting the number that surfaced it. Both are
constructor arguments.

## Vendor fault versus caller fault

**It cannot be distinguished, and the module never tries.**

The 4xx/5xx line is not a fault line. A 429 is a limit the caller provoked, a 401 can be a rotated
key or a revoked one, a 400 can be a client that started sending a field the vendor removed, and a
500 can be a malformed request the vendor handled badly. Splitting the rate along that line and
calling one half "theirs" would be an attribution the table cannot support.

So: both go into one rate; the observed status codes are listed as evidence, most frequent first
and bounded at three so the rationale does not become a histogram; and every rationale carries the
sentence "A status code records what came back, not who caused it". The codes are what let a
reviewer tell a rate limit from a rotated credential — the detector supplies the evidence and
declines the conclusion.

This is pinned by a test rather than by intention:
`test_client_and_server_errors_are_reported_the_same_way` builds one population of 429s and one of
500s and asserts they come out at the same severity. A detector that graded them differently would
fail it.

## Mutations run

Every test below was written before the implementation and watched fail. The first run was
`ModuleNotFoundError: No module named 'sync.detect.status_rate'`.

Two things were caught and repaired during this phase, and both are the failure mode
`.claude/rules/test-discipline.md` names:

- `test_the_denominator_is_requests_and_not_traces` **could not fail as first written**. The
  two-row version (99 clean requests in one trace, 1 failure in another) is silenced by the sample
  floor before the denominator matters, so a row-counting detector passed it. It was rebuilt at
  100 traces — twelve traces of twenty requests with one failure each, eighty-eight traces of one
  clean request — so that the row count clears a row-shaped floor and the span count clears a
  span-shaped one. Every arrangement of the wrong query now reaches the threshold check.
- **The mutation harness itself was broken.** Its first run reported 15/15 killed. It passed
  `-p no:xdist`, which collides with `-n auto` in `addopts`, so pytest exited on a usage error
  before running a single test and every non-zero exit read as a kill. The harness now requires a
  `passed`/`failed` summary line before trusting a result, and carries a control mutation that
  must survive. The control did survive, which is the evidence the harness can still report one.

Final battery — 14 of 16 killed, both survivors expected and explained:

| # | Mutation | Test that killed it |
|---|---|---|
| M1 | `_tally` counts rows and `row.error_count` instead of spans | `test_the_denominator_is_requests_and_not_traces`, `test_many_requests_inside_one_trace_count_individually` (2 failed) |
| M2 | `statused += 1` moved above the `isinstance(status, int)` guard, so unstatused requests join the denominator | `test_requests_with_no_status_leave_the_fraction_entirely`, `test_the_rationale_states_the_denominator_it_used` (2 failed) |
| M3 | unstatused requests also increment `errors` | `test_requests_with_no_status_never_raise_a_finding_on_their_own` |
| M4 | group key `(operation_id, "", http_method)` — hosts merged | `test_two_hosts_are_never_averaged_together` |
| M5 | `if overall is None or overall.statused < self._floor` → `if overall is None` | `test_a_high_rate_below_the_sample_floor_stays_silent`, `test_a_rate_just_under_the_sample_floor_stays_silent` (2 failed) |
| M6 | `if overall.rate < self._threshold` → `if overall.errors == 0` | `test_a_rate_one_error_below_the_threshold_stays_silent` |
| M7 | the disjointness check in `_periods` deleted, so the two periods may share a row | `test_two_samples_that_cannot_be_separated_make_no_change_claim` |
| M8 | `earlier.rate < self._threshold <= later.rate` → `earlier.rate != later.rate` | `test_a_rate_that_fell_is_not_reported_as_a_change` (`test_a_rate_already_at_this_level…` passed — identical rates make `!=` false, so that mutation does not reach it) |
| M9 | `severity="breaking" if any(c >= 500 for c in overall.codes) else "info"` | `test_client_and_server_errors_are_reported_the_same_way` |
| M10 | `for site in sites[:1]` — one finding per operation | `test_every_call_site_for_the_operation_is_told` |
| M11 | sites with empty `response_fields_read` skipped | `test_a_call_site_that_reads_no_response_field_is_still_told` |
| M12 | `call.vendor_id != self._vendor_id` dropped from the filter | `test_another_vendor_traffic_is_never_read` |
| M13 | `not call.operation_id` dropped from the filter | **survived** — see below |
| M14 | `observed_calls(self._repo_id)` → `observed_calls("other")` | `test_another_repository_traffic_is_never_read` |
| M15 | `severity="info"` unconditionally | `test_a_rate_that_rose_between_the_earliest_and_latest_samples_is_breaking` |
| control | `CODES_IN_RATIONALE = 3` → `2` | **survived** by design — nothing asserts how many codes are named |

**M13 survived, and the code now says so.** Dropping the uncorrelated-row guard leaves every test
green, because no `call_site` row carries an empty `operation_id` — both indexers drop a site whose
symbol did not resolve — so `call_sites_for_operation(vendor, "")` returns nothing either way. This
is the same result `efficiency.py` records for the same guard, and both the module docstring and
`test_an_uncorrelated_observation_yields_no_finding` now state it rather than claiming a coverage
the assertion does not have. The line stays because `uncorrelated` is the count `IngestReport`
calls the one worth watching, so the query it skips is not a rare one.

## On additivity

**I agree the efficiency ruling does not extend here, and the ordinary one-per-call-site rule
applies.** An efficiency finding is one cost incurred once per trace, so counting it at every call
site would multiply a single dollar figure. A status-rate finding is a report that an operation is
returning errors, and every call site that calls that operation is a separate place a human has to
look and potentially change. Two call sites is two pieces of work, not one counted twice.

There is a second axis, and it is also additive: one operation reached through two hosts produces
two findings against the same call site. That is intentional. A sandbox failing while production is
healthy is a different fact from both failing, and the rationale names the host so the two do not
read as a duplicate.

Unlike `observed_drift`, **no `response_fields_read` filter applies.** That module filters because a
divergence in a field nobody consumes cannot break the site that ignores it. An operation returning
an error breaks its caller whatever fields the caller reads, so filtering would drop true findings.
`test_a_call_site_that_reads_no_response_field_is_still_told` pins this.

## Things the brief did not mention

**These findings will abandon in remediation, and that is correct.** `Finding.vendor_change_id` is
`None` — there is no vendor change, only traffic — and `make_locate` calls
`store.get_vendor_change(None)`, which raises and routes to `abandon` with a recorded reason.
`observed_drift` and `efficiency` already have this property; `route_after_locate`'s own docstring
names it. It is right for this detector: there is no mechanical patch for "this operation is
returning 500s", and `.claude/rules/remediate-stage.md` treats abandoned attempts as the corpus's
most informative rows rather than as a drain. Flagged because "reaches the pipeline" and "produces
a pull request" are different claims and only the first is true.

**`severity="breaking"` puts these in front of the remediation limit.** `_select` takes findings in
scan order under `--limit`, and `status-rate` is placed before `efficiency` in the suite. A
breaking status-rate finding will therefore consume a remediation slot and abandon it. Not wrong,
but worth knowing before the limit is tuned.

**Placement in the suite.** Directly before `efficiency`. The existing docstring's rule —
`efficiency` runs last because it is the only one answering a question about cost rather than
breakage — decides this without amendment, so the docstring was left alone.

**The detector is deterministic across scans.** Groups are sorted, and rows within a group are
sorted by `(first_seen, trace_id)`. The tiebreak matters: rows ingested from one batch commonly
share a `first_seen` to the second, and without it the period boundaries would move between scans.
`test_scanning_twice_returns_the_same_findings` covers it.

**Shared worktree.** Another worker was committing into
`C:/Users/strol/orca/workspaces/Sync/m1-forge` throughout this task, which blocked the opening
rebase (`cannot rebase: You have unstaged changes` against files that were not mine). This was
escalated rather than worked around. The closing rebase onto `origin/main` was done by stashing
only my three paths; it fast-forwarded with no conflict, and the resulting `cli.py` diff is exactly
the two lines above.

## Gates

All four run after the final rebase onto `origin/main`, with
`SYNC_DSN=postgresql://sync:sync@localhost:5433/sync_b14`.

- `uv run pytest` — `1404 passed in 166.12s`
- `uv run lint-imports` — `Contracts: 1 kept, 0 broken` (83 files, 161 dependencies)
- `uv run python scripts/lint_encoding.py src scripts tests` — clean
- `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` — clean,
  which is the gate that proves `StatusRateDetector` is constructed and not merely written. The
  baseline file was not touched.

### One flake, recorded rather than swept up

The first full-suite run reported `1 failed, 1385 passed, 1 error`. The failure was the
`test_cli.py` suite assertion above, and is fixed. The error was
`tests/test_observed_drift.py::test_a_long_standing_mismatch_is_reported_as_information`, in a file
this task did not touch.

It has not recurred: the test passes in isolation, and two subsequent full runs were clean. The
likeliest cause is the cold start — that run took 253s against 96s and 166s for the warm ones, the
difference being `conftest.py` creating and schema-loading a per-worker database for each xdist
worker at once. An error at setup rather than a failed assertion fits that. Noted here because a
flake nobody wrote down is a flake somebody rediscovers, but I could not reproduce it and did not
change anything to chase it.

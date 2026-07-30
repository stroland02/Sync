# Eight declines that cost findings, and one that costs nothing

M3-W106, following `2026-07-29-detector-declines.md`. That report examined the six *uncovered*
declines in `src/sync/detect/` and found five of them cannot happen. Its closing finding is this
task: **the declines that actually lose a finding are all covered**, so no coverage number will
ever point at them, and until now not one of them left anything a caller could count.

Seven are counted now, on three detectors, through the channel the eighth already had. Three
things the count is deliberately *not* is the load-bearing part, and they are argued below
rather than assumed.

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
description of the traffic, and it would drown the seven above. Each exclusion has a test whose
whole job is to fail if the counter becomes indiscriminate.

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

## The three docstrings, before and after

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

A reader took the first and third as descriptions of two live outcomes. There is one.

## Mutation table

<!--MUTATION-TABLE-->

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

<!--GATES-->

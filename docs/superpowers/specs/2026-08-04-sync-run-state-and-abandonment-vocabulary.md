# Sync — Run state and the abandonment vocabulary

**Date:** 2026-08-04
**Status:** Specified. Binding on `sync.core.models`, `sync.remediate`, `sync.dashboard` and
`web/src/api/types.ts`. Nothing here is built.
**Scope:** What states a remediation run can be in, where that list lives, and how an abandoned
run says why in a form a query can aggregate.

## The defect this exists to prevent

`sync.remediate.state` declares `Outcome = Literal["running", "opened", "abandoned", "reported"]`
(`src/sync/remediate/state.py:14`) and `make_locate` writes `"outcome": "running"` on the first hop
of every run (`src/sync/remediate/nodes.py:121`). `sync.dashboard.queries` declared
`_FINISHED = ("opened", "abandoned", "reported")`, used it to decide which node is current, and
passed `outcome` through unfiltered. Any non-null outcome read as terminal, so every live run
rendered in the operator console as a finished run that had decided to do nothing, and the poll
stopped.

The filter is in the working tree as I write this — `src/sync/dashboard/queries.py:206-210` now
admits only a member of `_FINISHED` and reports `None` otherwise, and
`web/src/api/types.ts:154` widens `WorkflowOutcome` to carry `running`. Both files are modified and
uncommitted; `git log` for them ends at `f6e6a1c`, which predates the fix.

The filter is correct and it is not the fix. One `Literal` holds two vocabularies: `running`
answers *is this run still going*, and `opened`/`abandoned`/`reported` answer *how did it end*.
Those are different questions about different things, and a value that answers one is not a value
that answers the other. Every consumer of that union has to know, out of band, which of its four
members mean what — and the console was the third consumer to have to know it and the first to get
it wrong. A filter at the query layer teaches the fourth consumer nothing.

**Conflating liveness with disposition is the root cause. The missing filter is the symptom.**

## What actually holds an opinion today

Five surfaces, none of which imports the vocabulary from another.

| Surface | Vocabulary it holds | Where |
|---|---|---|
| `sync.remediate.state` | `running`, `opened`, `abandoned`, `reported` | `state.py:14` |
| `sync.dashboard.queries` | `opened`, `abandoned`, `reported` | `queries.py:58` |
| `sync.mcp.propose` | `proposed`, `unverified`, `blocked`, `no_patch_warranted`, `unavailable` | `propose.py:43-49` |
| `migration_outcome.terminal_status` | `retried`, `opened`, `abandoned` | `nodes.py:217,571,653`; column is bare `TEXT` at `schema.sql:221` |
| `web/src/api/types.ts` | `opened`, `abandoned`, `reported`, `running` | `types.ts:154` |

The third row is the one worth reading twice. `sync.mcp.propose.run_to_static_verify` drives a
truncated graph and `_finish` overwrites `state["outcome"]` with one of its own five values
(`propose.py:107-109`), and `sync.mcp.tools` returns that value to an agent verbatim
(`tools.py:265`). So `RunState["outcome"]` already carries, in the tree today, five values that
`Outcome` does not contain. The type does not describe the key. That is not a hypothetical fourth
module holding a fifth opinion; it is a fourth module that already holds one, and the type system
is silent about it because `RunState` is a `TypedDict` and nothing checks the writes.

The fourth row is a second, quieter divergence. `terminal_status` and `Outcome` overlap on two
values, disagree on `reported` (`make_report` writes no corpus row at all —
`nodes.py:608-616`) and disagree on `retried`, which is not an outcome but the closing of a
superseded attempt.

## 1. The run-state vocabulary

### Decision

Split the two questions. Keep one key, give it one meaning, and let absence carry liveness.

```python
# sync/core/models.py, beside FindingStatus
Disposition = Literal["opened", "abandoned", "reported"]
```

`RunState["outcome"]` holds a `Disposition` **and is not written until the run ends**.
`make_locate` stops writing `"running"`. A run is live exactly when its newest checkpoint carries
no `outcome` key.

`sync.mcp.propose` keeps its own five values under the same key and they are named as a second,
deliberately disjoint vocabulary in that module — `PreviewOutcome` — because `sync.mcp.tools:265`
reads `state["outcome"]` and that surface is frozen. `RunState["outcome"]` is therefore typed
`Disposition | PreviewOutcome`, which is what it has always held and has never said. See the
owner questions: the alternative is a separate key, and that is a change to a frozen surface.

### Why absence rather than a `running` value

Writing `running` at `locate` bought nothing that a checkpoint's existence does not already say.
A checkpoint row exists only because a run started; `sync.dashboard.queries.workflow_state` returns
`None` outright when there is no checkpoint (`queries.py:198-199`). So "started" was already
recorded by the row, and `running` was a second encoding of it. The Critical is what two encodings
of one fact cost when they disagree.

Where the run currently *is* stays answerable and is answered by a different mechanism that already
works: `_pending_node` reads langgraph's `branch:to:<node>` trigger channels against `versions_seen`
and returns the node the graph owes a visit (`queries.py:230-244`). Position is a per-node fact and
belongs in the node sequence. Disposition is a per-run fact and belongs in one key.

### Where the list lives

`sync.core.models`, next to `FindingStatus`, `Severity` and `PatchStrategy`.

Not `sync.remediate.state`, even though `Outcome` is there today, and the reason is the import
graph rather than tidiness. `sync.core` imports nothing from any sibling
(`CLAUDE.md`, enforced by `tests/test_import_boundary.py`), and every sibling already imports it —
`state.py:7` does, `MigrationOutcome` lives in it, and `sync.dashboard` can reach it without
reaching into the graph package. It is the only module that every consumer can depend on and that
can depend on none of them, which is the whole requirement. `FindingStatus` is already a
remediation vocabulary living there (`models.py:26`), so this is the existing convention rather
than a new one.

Three of the four Python surfaces then import instead of restating:

- `sync.remediate.state` re-exports it as the type of `RunState["outcome"]`.
- `sync.dashboard.queries` replaces `_FINISHED` with `get_args(Disposition)`. The stated
  constraint on that package is that it reads checkpoint rows and never graph code
  (`queries.py:34-36`), and the node *order* is mirrored for a real reason: a row cannot state an
  order. A row does state its own outcome, and which values are terminal is a fact the vocabulary
  owns. `sync.core.models` is not graph code and importing it drags no runtime in.
- `sync.remediate.corpus` keeps `terminal_status` as it is. It is a different vocabulary at a
  different grain — one attempt, not one run — and `retried` proves it. It should be typed as its
  own `Literal["retried", "opened", "abandoned"]` in `sync.core.models` for the same reason, but
  it must not be merged with `Disposition`.

TypeScript cannot import a Python `Literal`, so `web/src/api/types.ts` restates it. That fourth
surface is closed by a test rather than by discipline — see Verification.

## 2. Is `awaiting_human` a state Sync needs?

### Decision: no. Neither `awaiting_human` nor an `awaiting_ci` beside it.

Superlog needs `awaiting_human` because its runs suspend for a person. Sync's do not.
`build_graph` compiles with no `interrupt_before` and no `interrupt_after`
(`src/sync/remediate/graph.py:108`), so no run stops for a decision anywhere. There is no state
because there is no wait.

The wait that does exist is the customer's CI, and it is not a suspended graph. `await_ci` is a
blocking poll *inside* a node: `GitHubForge.await_ci` sets `deadline = time.monotonic() + timeout`
and loops on `time.sleep(self._poll)` until it can return `(green, detail)`
(`src/sync/forge/github.py:480-543`). The graph does not yield during that wait, so no checkpoint
could carry a state describing it. What the newest checkpoint carries instead is `await_ci` as the
node the graph owes a visit, which `_pending_node` already reports as `current`
(`queries.py:230-244`).

So "waiting on something outside our control" is already expressed, by the node sequence, and
adding a run-level state for it would be a second encoding of a fact the sequence already carries.
That is precisely the shape of the defect at the top of this document.

### What the console should show differently, concretely

All of this is presentation over data the checkpoint already holds. None of it needs a new state
value.

- When `current == "await_ci"`, `RunOutcome` renders "Sync is waiting on the customer's CI" rather
  than the generic "This run is still in flight" (`web/src/features/workflows/run-outcome.tsx:58-68`).
  The distinction matters because it tells the reader that nothing Sync does will make this faster,
  which is what `.claude/rules/remediate-stage.md:19-21` says about the critical path.
- It names the run: `ci_url` is already in that node's evidence set
  (`_EVIDENCE_KEYS["await_ci"]`, `queries.py:54`).
- It shows `ci_attempts` against `MAX_CI_ATTEMPTS` (2, `state.py:17`), so a reader can see how much
  budget the run has left rather than inferring it.
- Elapsed time, if the console ever shows it, is split at this node. A single elapsed figure
  attributes the customer's CI to Sync's latency, and the latency architecture is explicit that
  the critical path is dominated by that run and that nothing Sync adds makes it faster.

**Could not verify:** I did not execute a run. That the newest checkpoint renders `await_ci` as
`current` while the poll blocks is read from `_pending_node` and langgraph's trigger-channel
convention as `queries.py:230-244` describes it, not observed against a live run. If it turns out
langgraph writes no checkpoint between `push_branch` returning and `await_ci` starting, this
section's premise fails and the answer to the question changes.

## 3. The abandonment vocabulary

### Every abandonment site in the tree

There is exactly one *write*: `make_abandon` sets `abandon_reason` to
`state.get("diagnostics") or "unknown"` (`nodes.py:643`). So the reasons that exist are the
distinct producers of `diagnostics` on a path that routes to `abandon`. Read from
`src/sync/remediate/nodes.py` and the modules it calls:

| # | Router | Condition | What `abandon_reason` gets today |
|---|---|---|---|
| 1 | `route_after_locate:132` | `store.get_call_site` or `get_vendor_change` raised (`nodes.py:109-110`). Commonly `vendor_change_id` is `None` (`nodes.py:129-131`) | `_describe(exc)` |
| 2 | `route_after_prepare:176` | `adapter.prepare` raised (`nodes.py:147-149`) — clone, dependency install, broken registry, lockfile out of sync | `_describe(exc)` |
| 3 | `route_after_patch:278` | `remediator.propose` raised `NoTierApplies` (`tiered.py:83-89`), on the last of 3 attempts | `"NoTierApplies: ..."` |
| 4 | `route_after_patch:278` | `remediator.propose` raised anything else, including `TierFailed` (`tiered.py:184-195`) | `_describe(exc)` |
| 5 | `route_after_patch:278` | The remediator returned an empty diff (`nodes.py:248-257`) | `"the remediator produced no change"` |
| 6 | `route_after_patch:278` | `NoPatchWarranted` raised inside `propose` (`tiered.py:82-101`) when `locate` had no catalogue and could not route it to `report` first | `"NoPatchWarranted: no patch is warranted for ..."` |
| 7 | `route_after_static:309` | `dependency_edits` refused the tree: the patch edited an installed dependency (`index/dependency_edits.py:213-229`, `.claude/rules/remediate-stage.md:50-53`) | the `describe()` sentence naming the path |
| 8 | `route_after_static:309` | `adapter.static_verify` raised for any other reason (`nodes.py:288-292`) | `_describe(exc)` |
| 9 | `route_after_static:321` | `verify_ok` false on the last of 3 attempts | raw `tsc` output |
| 10 | `route_after_replay:486` | `replay_outcome` in `threw`/`unsatisfied`/`timed-out` on the last attempt (`nodes.py:329`) | `"replay (<outcome>): <reason>"` |
| 11 | `route_after_push:507` | `forge.push_branch` raised — protected branch, expired token, non-fast-forward | `_describe(exc)` |
| 12 | `route_after_ci:532` | `forge.await_ci` raised, so there is no verdict at all (`nodes.py:530-532`) | `_describe(exc)` |
| 13 | `route_after_ci:538-543` | CI returned red and a budget is spent | `"CI failed: <url or message>"` |
| 14 | `nodes.py:643` | Every route above set no diagnostics | `"unknown"` |

Row 13 hides a distinction the rule cares about. `GitHubForge.await_ci` returns `(False, message)`
for a genuinely failing check *and* for each of its four timeout cases — nothing appeared, a
required check never reported, checks were still running at the deadline, checks completed without
a confirmed green verdict (`github.py:533-543`). "The customer's CI rejected this patch" and "the
customer's CI produced no verdict" are different facts about different things, and routing needs
them apart: the first is evidence about a change kind, the second is evidence about a repository's
CI configuration. Today they are one string, and telling them apart means parsing the message,
which `.claude/rules/remediate-stage.md:56-60` forbids as routing on the incidental shape of an
output.

Row 6 is a defect this specification makes visible rather than fixes. `state.py:9-13` and
`make_report`'s docstring (`nodes.py:598-602`) both state that a tier -1 decision must never be
written to `abandon_reason`, because "this kind never needed a patch" corrupts exactly the signal
that field carries. `route_after_prepare` enforces that only when `locate` had a catalogue to route
with; when it did not, `TieredRemediator` asks the table again inside `propose`, raises
`NoPatchWarranted`, and `make_patch` renders the message into `diagnostics` — which
`tiered.py:95-97` states as intended behaviour. Two modules disagree about a rule both of them cite.

### The codes

Sixteen. Each is defined by the condition that produces it, and each is produced by exactly one
routing predicate. The node is therefore recoverable from the code by a fixed lookup, which is why
this specification adds no second column for it.

| Code | The condition that produces it |
|---|---|
| `graph_lookup_failed` | The store could not resolve the finding's call site or vendor change. Row 1. |
| `environment_unprepared` | `adapter.prepare` raised. The clone, the install, or the lockfile — not something a different patch could fix. Row 2. |
| `no_tier_applies` | Every tier was offered the finding and none accepted it. Row 3. |
| `patch_failed` | A tier accepted the finding, ran, and raised. Row 4. |
| `patch_empty` | A tier accepted the finding, ran, and produced no change. Row 5. |
| `no_patch_warranted` | The table decided no patch is warranted and the decision arrived too late to route to `report`. Row 6. |
| `dependency_tree_edited` | The patch modified a file inside an installed dependency, so the typecheck describes a tree no push would carry. Row 7. |
| `verifier_unavailable` | The verifier could not run. An environment fault at verification time, not a patch that failed to compile. Row 8. |
| `static_verify_exhausted` | The patch failed `tsc` on the last of `MAX_STATIC_ATTEMPTS` attempts. Row 9. |
| `replay_exhausted` | The patched call path threw, read fields the new response does not carry, or did not return — on the last attempt. Row 10. |
| `push_rejected` | The forge refused the push. Row 11. |
| `ci_unavailable` | The CI poll raised. No verdict was produced. Row 12. |
| `ci_rejected` | A required check concluded in a blocking state. The patch is wrong and the budget is spent. Row 13, failing-check case. |
| `ci_no_verdict` | The deadline passed with no confirmed verdict, in any of the four ways `await_ci` distinguishes. Row 13, timeout cases. |
| `pr_open_failed` | The forge refused to open the pull request — rate limit, or a branch that already has one. `route_after_open_pr:590`. |
| `unclassified` | A run reached `abandon` and no code applied. Row 14. |

Three of these are not merges of each other and must not become so. `no_tier_applies` against
`patch_failed` is the split `sync.remediate.corpus`'s own docstring demands
(`corpus.py:38-43`): "nothing was attempted" and "the agent tier ran and failed" are different
facts, and squashing them loses exactly the signal `migration_outcome` exists to capture.
`environment_unprepared` against `verifier_unavailable` is the split `route_after_prepare` and
`route_after_static` already make with two different state keys. `ci_rejected` against
`ci_no_verdict` is the split argued above.

Two of them have a target count of zero, and a nonzero count is a bug report rather than a
measurement:

- `no_patch_warranted` should never be written, because tier -1 is `reported` and not abandoned.
  Its count is the number of runs that reached the decision table too late.
- `unclassified` should never be written, because the classifier is total over every edge into
  `abandon`. Its count is the number of edges added without a code.

Naming them as codes rather than leaving them unrepresented is the point: a defect that has a
row is a defect somebody can query for.

`ci_no_verdict` cannot be assigned from the state that exists today. Splitting it from
`ci_rejected` requires `await_ci` to say which happened rather than returning a bare boolean —
either a third value from the `Forge` protocol or an explicit key set by `make_await_ci`. That
protocol is declared in `nodes.py:20-29` and is not exported from `sync.core`, so widening it is
internal and costs the one production implementation plus the test fakes. Until it is widened,
`classify` must return `ci_rejected` for the whole of row 13, and the count of `ci_rejected` is an
upper bound rather than a measurement. Say that in the console legend; do not launder it.

### How a new code is added

The vocabulary is keyed to the graph's edges, not to the space of things that can go wrong. That
is what makes it closable and what gives it a growth path that does not decay into free text:

**Adding a conditional edge whose destination is `abandon` requires naming its code in the same
change.** No edge, no code; new edge, new code. The count of codes is bounded by the count of
abandonment predicates, which is fourteen today and grows one at a time under review.

This is enforced by a test rather than by a rule alone: `classify` is total, and a test asserts
that the set of codes it can return is exactly `get_args(AbandonCode)`. An edge added without a
code makes `classify` fall through to `unclassified`, which is a value with a target count of zero
and a test that asserts it. The precedent is `tests/test_severity_vocabulary.py`, which pins a
vocabulary by asserting an identity rather than by restating its members.

### What happens to the free-text field

**It survives, beside the code, and the two carry different things.**

`abandon_reason` is not a worse version of `abandon_code`. It carries the one detail that lets an
operator act, and in at least one case the code cannot carry it: `dependency_edits.describe()`
names the path that was edited, and its docstring states why — "verification failed" against a
compiler that reported nothing is the one situation that cannot be diagnosed from a category
(`index/dependency_edits.py:213-219`). The same holds for a CI run URL and for `tsc` output. A code
answers "which class of thing went wrong"; the text answers "which thing".

The code, not the text, is what converges. `_describe(exc)` renders an exception message, and those
carry paths, identifiers and occasionally clock-dependent detail, so two executions of the same run
can produce two different strings for one condition. This is the same failure the pipeline
discipline spec measured on oasdiff and the same fix: its recorded remedy for non-convergent
`vendor_change` rows is "a natural key that does not carry the free-text message"
(`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md:84-86`). An aggregation key that
carries free text is not a key.

So: `RunState` gains `abandon_code`; `abandon_reason` stays exactly as it is. `migration_outcome`
gains an `abandon_code` column and keeps `abandon_reason`. Every aggregate groups by the code and
never by the text, and the console renders the code as a filterable chip with the text beneath it,
which is what `docs/superpowers/references/notes/competitor-interfaces.md:59-66` recommends.

There is a problem with `migration_outcome.abandon_reason` that this specification found and does
not solve — see Deliberately out of scope.

## 4. Where the vocabulary is enforced

Four candidate mechanisms. Two are unreachable on this codebase, and the reason is measured rather
than assumed.

**A Postgres enum type: rejected.** `GraphStore.apply_schema` converges an existing database by
issuing every declared column as `ADD COLUMN IF NOT EXISTS`, and its docstring states exactly what
it cannot express: rename a column, change a type, add or drop a constraint, or backfill
(`src/sync/graph/store.py:163-168`). A `CREATE TYPE` plus a column of that type is the "real
migration — a version table, an ordered history and a workflow" the same docstring says is
deliberately unbuilt, on the argument that a framework bought now is carried for a year before it
is needed. The cost of an enum is that framework. This column does not justify it.

**A `CHECK` constraint: rejected, and the argument is already written and already measured.**
`schema.sql:84-115` carries it for `severity` and `tests/test_severity_vocabulary.py` pins it: a
`CHECK` riding on a column definition never reaches a database that already has the column, because
`apply_schema` skips the whole item — constraint included — when the column is there. The
constraint would land on every database created after the edit, where every write already goes
through a validated model, and on none of the databases that predate it, which is the only place a
hand-written row can be. Absent and believed present is worse than absent. Ten model fields are
closed `Literal`s, nine of them are columns, and not one is constrained in DDL; a `CHECK` here
would make `schema.sql` a second declaration of a vocabulary `sync.core` owns.

**A Pydantic `Literal`: adopted.**

```python
# sync/core/models.py
AbandonCode = Literal["graph_lookup_failed", ...]   # sixteen members
```

`MigrationOutcome.abandon_code` is typed `AbandonCode | None` and is **required rather than
defaulted**, for the reason `routing_row` gives at `models.py:265-283`: a default is what a writer
silently falls back to after somebody forgets to set it, and that fallback would be
indistinguishable from a measured value. `| None` because a row read back out of the database may
carry the NULL that predates the column — required governs whether a caller must supply it, not
whether the value can be absent.

**A refusing write: adopted, as the backstop.** `GraphStore.record_migration_outcome` refuses a row
whose `terminal_status` is `abandoned` and whose `abandon_code` is `None`, naming the finding. This
is the house pattern: `insert_finding` already refuses a finding whose rung is `unattributed`, and
`.claude/rules/graph-grain.md:44-48` states why the check sits at the write rather than on the
model.

One thing has to be right about that backstop or it is decoration. `sync.remediate.corpus.record`
catches every exception out of the write and logs it (`corpus.py:234-242`), deliberately, because
bookkeeping that can fail a run is worse than bookkeeping that is missing — and that is exactly the
failure `make_recorder` already solved once, by checking the store's contract at construction
instead of at the write (`corpus.py:22-30`). So the refusal at the store can only ever be a
backstop for a hand-written row. What makes the code present on every real write is that there is
one producer and it is total:

```python
# sync/remediate/classify.py
def classify(state: RunState) -> AbandonCode: ...
```

A pure function of `RunState`, called by `make_abandon`, returning `unclassified` rather than
raising. `make_abandon` writes both `abandon_code` and `abandon_reason`, and passes the code to
`record`. One producer, one vocabulary, one total function — and a total function is what makes the
classification idempotent, which the next section needs.

## 5. Migration

**Existing rows keep `NULL` and are never backfilled.**

`abandon_code TEXT` — nullable, no constraint — is precisely what `apply_schema` can already
deliver: it is an added column and nothing else (`store.py:158-161`). That is the entire migration.

Backfilling by pattern-matching the existing `abandon_reason` strings is rejected on the same
argument `routing_row`'s comment makes at `models.py:265-273`. A guessed value and a measured value
in one column cannot be told apart afterwards, and the column exists to answer a question that
depends on the difference. A regex over `_describe(exc)` output would produce exactly that: a
`patch_failed` derived from a string is not the same claim as a `patch_failed` derived from the
routing predicate that fired, and nothing downstream could tell.

This gives the column two distinct absences, which follow the split `routing_row` already
establishes:

- `NULL` means the column was never written for this row — it predates the column.
- `'unclassified'` means the run abandoned and no code applied. A value, and a bug.

Every query that aggregates by code must either filter `abandon_code IS NOT NULL` or report the
null bucket by name. A rate computed over a denominator that silently includes pre-column rows is
the failure `schema.sql`'s natural-key comment exists to prevent.

**Could not verify:** I did not query a database. `store.py:169-170` states that the only databases
are a developer's and a test run's, which suggests the population of affected rows is small, but I
have no row count and did not attempt one.

## 6. Does a confidence scale belong in Sync?

### Decision: no. Not on the finding, and not on the repair.

**On the finding, the rung is already the answer, and it is a stronger one.** `static`, `resolved`
and `observed` are a claim about what kind of evidence produced a binding, which is structurally
what Superlog's 0–10 scale claims to be. The difference is that Sync's is a column the write path
refuses to omit (`.claude/rules/graph-grain.md:44-48`) and Superlog's is a number a model emits.
The reference note reaches this conclusion for itself
(`docs/superpowers/references/notes/competitor-interfaces.md:216-222`): two numbers meaning roughly
"how much should I trust this" on one row is worse than one, and the score is the one that loses,
because nobody can audit it. Adding a second axis here would also violate the standing constraint
that the binding is the product: a scalar beside the rung invites a reader to weigh them against
each other, and the moment anyone does, the rung has been blurred.

**On the repair, Sync does not score — it gates, and the gates are strictly stronger.** Superlog's
confidence attaches to a root-cause claim, and the object in Sync that corresponds to a claim is
the patch. Sync's patches pass `tsc`, then replay, then the customer's own CI. Those are three
verdicts with named evidence attached, and `state.py:40-58` already records the one distinction a
confidence number would destroy: `replay_outcome` keeps `declined` and `not-attempted` apart from
`passed`, precisely so a run replay could not execute never reads as a run replay verified. Collapse
that into a number and the number for "we could not check" sits on the same axis as the number for
"we checked and it passed", differing only in magnitude. That is the false precision.

**What to borrow is Superlog's sentence, not its number.** The reference note's §2.1 is right that
what Sync lacks is a plain-English line telling a reviewer what to do differently at each rung.
That is a legend, and it costs nothing.

**Concretely, and this is the one thing to build:** the console renders a derived verification
level over `(verify_ok, replay_outcome, attempt_ci_result)` — typechecked, replayed, CI-green —
naming which gates ran and which did not, in the order they ran. Derived at render time and never
stored, because a stored derivation of three columns is a fourth thing that has to be kept in
agreement with them, and this document exists because two things that had to agree did not.

## Standing constraints, checked

**Idempotence.** `classify` is a pure function of the checkpointed `RunState` and reads no clock,
no URL and no exception text. A run re-executed from its checkpoint converges on the same code.
`migration_outcome` is `UNIQUE (finding_id, attempt_index)` with `ON CONFLICT DO NOTHING`
(`schema.sql:232-235`, `store.py:536-545`), so a re-recorded attempt keeps the first row — which
converges only because the classifier agrees with itself, not because the conflict clause hides a
disagreement. The free-text `abandon_reason` may differ between two executions; the code cannot.
That asymmetry is the reason the code is the aggregation key.

**The binding is the product, not the repair.** Nothing here touches `BindingRung`,
`Finding.binding_rung`, or the refusal in `insert_finding`. `Disposition` and `AbandonCode` sit
beside them in `sync.core.models` and describe a run, never a binding. The confidence decision in
§6 exists specifically to keep a second trust axis away from the rung.

**Corpus grain.** `abandon_code` is a column on `migration_outcome`, whose grain is one attempt.
The code describes the attempt that ended, and a finding abandoned after three attempts writes the
code on the third row only, because `record` is called once by `make_abandon`.

**Three codes can never appear in the corpus, and this is a real gap.** `corpus._record` returns
early when `attempt_index < 1` (`corpus.py:260-270`), so `graph_lookup_failed` and
`environment_unprepared` — both of which abandon before `patch` has ever run — write no row.
`no_tier_applies` writes no row either, for a different reason: `_attempted_strategy` falls back to
`TieredRemediator.strategy`, which is `"tiered"`, and `tier_for("tiered")` returns `None`, so
`_record` omits the row (`corpus.py:155-165, 272-280`). All three are correct at that table's
grain — zero attempts is zero rows — and all three are exactly the abandonments a routing analysis
would want. They are queryable only through the checkpointer today, which is why `abandon_code` is
written to `RunState` as well as passed to `record`. The durable fix is a run-grain table, which is
out of scope below.

## Verification

Properties a test can hold, not aspirations.

- **`classify` is total and closed.** The set of codes reachable from `classify` equals
  `set(get_args(AbandonCode))`. Pattern: `tests/test_severity_vocabulary.py`.
- **Every edge into `abandon` has a code.** Drive each of the fourteen conditions in the table
  above through `classify` and assert the expected code. This is the test that fails when somebody
  adds an edge without one.
- **`unclassified` and `no_patch_warranted` do not occur** on any run in the fixture corpus.
- **The console's terminal set is the vocabulary.** `sync.dashboard.queries` reports an outcome for
  exactly `get_args(Disposition)` and `None` for anything else, asserted against the values rather
  than against a restated tuple.
- **The TypeScript union matches.** A test reads the `WorkflowOutcome` union out of
  `web/src/api/types.ts` and asserts its members are `get_args(Disposition)` plus nothing. This is
  the only mechanism available for that surface, since it cannot import the Python type.
- **A live run is not reported as finished.** Given a checkpoint holding no `outcome`, the
  workflow payload's `outcome` is `None`. This is the Critical, pinned.
- **An abandoned run carries a code.** `GraphStore.record_migration_outcome` refuses a row with
  `terminal_status='abandoned'` and a null code, and the refusal names the finding.
- **Classification converges.** Classify one `RunState` twice, assert identity. Then record the
  same attempt twice and assert the row count and the stored code are unchanged.

## Questions only the owner can settle

1. **`sync.mcp.propose` writing five foreign values into `RunState["outcome"]`, which
   `sync.mcp.tools:265` returns verbatim.** The clean design is a separate `preview_outcome` key,
   and that changes a frozen surface. *Recommendation: leave `outcome` as the key, name
   `PreviewOutcome` as a second vocabulary in `sync.mcp.propose`, and type
   `RunState["outcome"]` as the union of the two.* This documents what is already true and touches
   nothing frozen. Asking as a question rather than designing it: does the MCP surface want
   `preview_outcome` as a new field, alongside the existing one for compatibility?
2. **Row 6 — `NoPatchWarranted` reaching `abandon_reason`.** Two modules cite one rule and disagree
   about it: `state.py:9-13` and `nodes.py:598-602` say tier -1 must never be written there,
   `tiered.py:95-97` says `make_patch` renders it there on purpose. *Recommendation: `route_after_patch`
   routes a `NoPatchWarranted` to `report` rather than to `abandon`, and `no_patch_warranted` stays
   in the vocabulary as a zero-target code that measures the remaining gap.* This is a routing
   change in a package under active edit and I did not make it.
3. **Widening the `Forge` protocol so `ci_no_verdict` can be assigned.** `await_ci` returns
   `(green, detail)` and folds four timeout cases into the same falsy answer as a failing check
   (`github.py:533-543`). *Recommendation: widen it, because the two facts route differently — a
   red check is evidence about a change kind and a timeout is evidence about a repository's CI.*
   The protocol is internal (`nodes.py:20-29`), so the cost is one implementation and the test
   fakes.
4. **Whether `migration_outcome.abandon_reason` should keep storing raw `tsc` output.**
   `static_verify_error_class` exists specifically to classify a failure "without carrying a
   message that quotes the customer's own identifiers" (`corpus.py:80-82`), and
   `abandon_reason` then stores the whole message anyway. *Recommendation: with `abandon_code` in
   place, the corpus stores the code and the error class, and the free text stays in the checkpoint
   where the console already reads it (`queries.py:226`).* This deletes content from an existing
   column, which is a decision about stored customer data and not mine to make.
5. **Whether `terminal_status` becomes a typed `Literal` in the same change.** It is bare `TEXT`
   (`schema.sql:221`) holding three values from three call sites. *Recommendation: yes, in
   `sync.core.models`, and keep it separate from `Disposition` — the grains differ and `retried`
   proves it.*
6. **Whether sixteen codes is the right granularity for a corpus this size.** Fewer codes
   aggregate sooner; more codes stay honest longer. *Recommendation: ship sixteen. Every one is
   produced by a distinct routing predicate that already exists, so none of them is an invention,
   and merging two later is a query change while splitting one later is a backfill.*

## Deliberately out of scope

- **A run-grain outcome table.** Three codes can never reach `migration_outcome` because its grain
  is one attempt and those runs made none. The right answer is a table whose grain is one run, and
  it is a schema design of its own.
- **Redacting `migration_outcome.abandon_reason`.** Named in question 4. It is a threat-model
  question about stored data, not a vocabulary question.
- **`report_reason` reaching the console.** `sync.dashboard.queries.workflow_state` returns
  `abandon_reason` and not `report_reason` (`queries.py:223-227`), so a `reported` run arrives with
  the reason `make_report` wrote (`nodes.py:619-636`) discarded, and
  `run-outcome.tsx:105-115` substitutes static prose. One field, and the same family of problem —
  but it is a transport gap rather than a vocabulary decision.
- **A codename per finding.** Recommended by the reference note (§2.8) and unrelated to run state.
- **Filtering and charting abandonment codes in the console.** This specification defines the
  vocabulary and where it is enforced. What the console does with it is M4's.
- **Retiring `unattributed` from `BindingRung`.** Adjacent in shape — a vocabulary member that
  exists only for history — and untouched here.

## What could not be verified

- No run was executed. Every claim about what a checkpoint holds mid-run is read from
  `sync.dashboard.queries._pending_node` and the langgraph trigger-channel convention it describes,
  not observed.
- No database was queried. The count of existing `migration_outcome` rows with a free-text
  `abandon_reason` is unknown.
- `src/sync/dashboard/queries.py`, `web/src/api/types.ts` and
  `web/src/features/workflows/run-outcome.tsx` were modified and uncommitted in the working tree
  when I read them. Line numbers cited for those three files describe the working tree as of
  2026-08-04 and not any commit.
- The claim that `RunState["outcome"]` holds `PreviewOutcome` values in production is read from
  `sync.mcp.propose._finish` and `sync.mcp.tools:265`. I did not run the MCP server.

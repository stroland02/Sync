---
paths:
  - "src/sync/remediate/**"
---

# Remediation stage rules

You are editing the LangGraph pipeline that turns a `Finding` into a pull request.

## `locate → patch → verify` is a data dependency

Not an accident of ordering. Parallelising it produces a race, not speed. The latency spec
(`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md`) is binding here and should
be read before any stage is added, removed, or reordered.

## Every agent must earn its place

An agent must shorten the critical path or improve a result. One that does neither is latency
and cost with extra steps. The critical path is dominated by the customer's CI run, which
nothing added here makes faster — so the wins available are precomputation and staged
delivery, not more concurrency.

## Reducers on parallel state keys

Any `RunState` key written by parallel branches **must** declare a reducer. Without one,
concurrent writes are dropped silently: no error, no warning, missing results.

## Abandonment is a recorded outcome

`abandon_reason` is never null on an abandoned run. An abandoned run with no reason is a
dropped record with extra steps.

Abandoned attempts carry the most information in the corpus — they are where routing learns
which change kinds are not mechanically safe. Treat the `abandon` node as a dead-letter queue
to be queried, not a drain.

## The corpus grain is per attempt

One `migration_outcome` row is one attempt, not one finding. `static_attempts` and
`ci_attempts` in `RunState` are the retry budgets; `attempt_index` in the corpus is which
attempt this row describes. A finding that took three tries writes three rows.

## Nothing reaches a pull request unverified

Every patch passes `tsc`, then the customer's own CI. One qualification currently holds,
recorded in `CLAUDE.md`: the patch agent executes the customer's *toolchain* even though it
never runs their application. Say the qualified version; do not restore the stronger sentence.

`tsc` keeps the installed dependencies inside the tree it measures and so cannot see an edit
under `node_modules`. That is answered outside the compiler: `sync.index.dependency_edits`
compares mtimes against the install and raises before `static_verify` compiles anything, which
`route_after_static` reads as `static_fatal` and abandons on — the edit stays in the clone, so
every remaining attempt would meet the same doctored declaration.

A forge-less graph (`forge=None`) is the supported way to run the pipeline without a remote. It
structurally omits `push_branch`, `await_ci`, and `open_pr` from the compiled graph rather than
guarding them at runtime. Adding a push node back to a forge-less graph is a breaking change to a
non-negotiable safety property.

## Route on evidence, not on emptiness

`route_after_static` trusts `verify_ok`, not whether `diagnostics` is non-empty — a real `tsc`
failure can exit non-zero with nothing on either stream, which would otherwise read as
success. Keep that discipline for any new routing predicate: branch on an explicit boolean the
node set deliberately, never on the incidental shape of an output.

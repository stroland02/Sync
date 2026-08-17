# Sync to beta: the whole remaining scope, and the decisions it rests on

This document scopes everything left between the tree as it stands on 2026-08-17 and a beta anyone
outside this project can use. It is written to be executed by six agents working concurrently, so
every item below belongs to exactly one lane in
`docs/superpowers/orchestration/2026-08-17-lane-charters.md`.

It makes decisions rather than listing options. Each is marked as a ruling and each is reversible at
the cost of one fix round; a plan that surveys alternatives and defers is a plan that gets read
twice and executed never.

## Where the code actually is, measured rather than remembered

| Milestone | State | The one sentence that matters |
|---|---|---|
| M0 walking skeleton | ~90% | Every component exists; the proof is over a thousand commits stale and has never been re-run |
| M1 runtime signals | ~85% | Built; the dollar estimate is deliberately unbuilt |
| M2 error detector | ~85% | Built; never exercised against real telemetry |
| M3 multi-vendor, MCP, plugin SDK | ~95% | Nothing structural left |
| M4 hosted control plane | ~50% | Nine levels and a read-only Settings screen exist; nothing is hosted, and auth, tenancy and the write path have no code |
| M4.5 console quality | ~90% | Closed into M7 |
| M5 integration layer | ~35% | Sentry feeds counts in; nothing correlates anything |
| M6 show it rather than describe it | 0% | Needs a product worth filming |
| M7 console as product | ~98% | All nine levels on the vendored substrate |
| M8 runner seam | done | `M8-W228` |
| M9 outcome vocabulary | done | Built behind the seam |
| M10 durable runs | 0% | Sync opens a pull request and stops watching it; `pull_request_outcome` landed as the primitive |
| M11 fan-in | 0% | Eight call sites of one vendor change are eight pull requests |
| M12 dashboards | 0% | The useful panels need aggregates `sync.dashboard` does not compute |
| M13 dynamic visuals | 0% | Proposed |

Three facts about that table matter more than the percentages, because they are what a sceptical
reader will find first:

- **The acceptance run has not executed since the pipeline changed underneath it.** `B7`. Ten graph
  nodes exist where eight did when it last passed, and four of the ten postdate it.
- **Merge rate has never had a sample.** The consumer has existed for weeks; the producer landed
  today as `M10-W229` and nothing calls it yet.
- **Three of five quality axes have never had a sample either.** The benchmark computes them from a
  corpus that real runs have barely written to.

## Ruling 1: beta means a design-partner beta, not a self-serve hosted product

**Decided.** Beta is us running Sync against a partner's repository, with the console served
somewhere they can watch it, read-only. It is not sign-up, not multi-tenant, and not self-serve.

The argument is that the alternative is not reachable and would not help if it were. M4's hosted
half is three deliverables with no code -- auth, tenancy, and the write path -- and each drags
operational burden that teaches us nothing about whether the product works. What a design partner
tests is the only open question: does the loop produce pull requests a human merges. Tenancy tests
whether we can bill them for it.

**What this changes:** M4's beta obligation shrinks to *the console is reachable by somebody who is
not on this machine, and it shows their repository's real data.* Auth becomes a single shared
credential rather than a user system. Tenancy is out. The write path is out, and the read-only
Settings screen that landed today is exactly the right shape for it.

## Ruling 2: the gate on beta is evidence, not features

**Decided.** Feature completeness does not gate beta. Four pieces of evidence do, and any feature
not on their critical path is post-beta.

Sync's whole position is that competing tools present a black box and a result and ask a reviewer to
trust it. A beta that ships without evidence of its own behaviour ships the thing it exists to
replace, and it would be the most expensive possible moment to discover the loop does not close.

## What beta requires: four gates

Beta is ready when all four are true and demonstrable, not when a milestone list is ticked.

**Gate 1 -- the loop closes.** One `sync run` against a real repository produces a CI-green pull
request, and a pull request that receives a review comment resumes the run and pushes a follow-up
commit with nobody re-running anything. That is `B7` plus M10, and it is the product claim stated as
a test.

**Gate 2 -- the evidence exists.** The corpus carries real samples, written by real runs rather than
fixtures, for merge rate and at least three of the five quality axes. Merge rate needs
`pull_request_outcome` wired to something that updates the corpus; the rest need runs to have
happened.

**Gate 3 -- the console tells the truth about that evidence.** Every honesty distinction still
renders -- provenance at two levels, absence apart from zero, staleness apart from liveness,
never-measured apart from nothing-here -- and no screen asserts a number nothing computed. The
`observed` rung must be real by then or it must stop being offered, which is Ruling 4.

**Gate 4 -- the containment story is true as written.** Nothing reaches a pull request unverified,
and `specs/2026-07-25-sync-threat-model.md` matches the code. `B97` is the ranked-first item there.

## Ruling 3: M10 is in scope for beta and M11 is not

**Decided.** M10 closes the loop and is Gate 1's second half; without it Sync opens a pull request
and stops watching, which means a rejected patch is a stale branch and a red build a human has to
clean up. That is worse than not having patched.

M11 (fan-in: one vendor change across N call sites becoming one pull request) is a quality and
volume improvement on top of a loop that already works. Eight pull requests where one would do is
ugly and it is honest, and a design partner can tell us whether it is actually the problem we think
it is before we build the grouping layer. Post-beta.

## Ruling 4: M5's correlator is in scope, because the console already promises it

**Decided.** `RequestCorrelator` is a protocol in `sync.core` with no production implementation
joining runtime telemetry to a static call site. Until that join exists, the `observed` rung is a
promise rather than a rung -- and the console renders provenance rungs on real screens today.

That makes it a Gate 3 item rather than an M5 nicety. Either the rung becomes real, or the console
stops offering it; the first is better and the second is the fallback if the correlator proves
harder than a lane iteration.

## Ruling 5: M6 and M13 are post-beta, and so is most of M12

**Decided.** M6 is a film of a product and needs the product. M13 is Remotion motion diffs and a
live agent execution stream -- both are strong and both are decoration on an unproven loop.

M12 is split. The two things the owner named on 2026-08-07 -- the layout is one vertical stack where
it should be a grid, and Fleet carries more prose than data -- are in scope, because they are what a
design partner sees first. They need two aggregates `sync.dashboard` does not compute. The rest of
M12 is post-beta.

## Ruling 6: the M1 dollar estimate stays unbuilt

**Decided, and it was already the standing decision.** The efficiency detector reports call volume
and a change's shape; it does not estimate what a vendor's pricing makes that cost. A dollar figure
we cannot source is exactly the composite score the console refuses. Unchanged for beta.

## The queues, by lane

Ordered. A lane takes the top item, lands it, and takes the next. Items marked **[Gate N]** are on
the beta critical path; everything else is real work that does not block the gate.

### Lane A -- the remediation loop

1. **[Gate 1]** M10 durable runs and the human turn: parked states, event ingress, and the rule that
   a parked run is not ticked until something wakes it.
2. **[Gate 1]** Resume on a pull request event: a review comment wakes the run and it pushes a
   follow-up commit.
3. **[Gate 2]** Make abandoned and parked distinguishable in the corpus, so a beta run that is
   waiting is not counted as one that gave up.
4. M11 fan-in. Post-beta, and the first thing after it.

### Lane B -- the console

1. **[Gate 3]** Finish the mock-parity plan, landing task by task.
2. **[Gate 3]** Mock-to-build Task 1, the measurement pass. Nobody has put a mock screen and its
   shipped counterpart side by side under `getComputedStyle`, which means every other task in that
   plan argues from a drawing.
3. **[Gate 3]** The grid layout and Fleet's prose-to-data ratio, against Lane E's aggregates.
4. **[Gate 3]** A pass over every screen asking one question per screen: does anything here assert a
   number nothing computed. That is the Gate 3 sign-off and it is Lane B's to sign.
5. The second drawer, which is what mock-to-build Task 3 actually contains. Post-beta.

### Lane C -- pipeline health

1. **[Gate 4]** `main` is red on `test_lint_dead_links`; every lane is currently gating around it and
   is therefore one step from mistaking a real regression for it.
2. Postgres bounces under six sessions and costs a diagnosis every time it does.
3. `test_disconnect_network_does_not_stop_an_already_open_socket` fails under `-n auto` and passes
   alone.
4. **[Gate 4]** Reconcile `specs/2026-07-25-sync-threat-model.md` against the code that now exists,
   and close or re-scope `B97`. The sandbox landed; the spec should say what is actually true.
5. Gate wall-clock. Eight to fourteen minutes, paid by every lane on every iteration, is the largest
   single tax on this workspace.

### Lane D -- signals and adapters

1. **[Gate 3]** The request correlator, per Ruling 4.
2. **[Gate 2]** Adapter conformance against a configured vendor rather than only the coded pair, so
   the plugin claim has a sample behind it.
3. The producer half of `B136`, the intake attempt record.
4. M2 against real telemetry. Post-beta unless a design partner supplies it, in which case it moves
   to the top.

### Lane E -- graph, dashboard and API

1. **[Gate 2]** Wire `pull_request_outcome` to something that updates the corpus. Merge rate is the
   direct test of the product claim and has never had a numerator. Needs repository resolution per
   corpus row, and `store.record_merge_outcome` stamps `pr_merged_at = now()` rather than the instant
   GitHub holds, which is a fidelity gap to close on the way past.
2. **[Gate 3]** The two M12 aggregates the console needs: the Fleet change-unit grain and the
   cross-detector rung tally.
3. The schema half of `B136`, one row per attempt with a closed-vocabulary reason.
4. **[Gate 2]** A corpus health view: which axes have samples, which have none, and how many runs
   produced them. Beta's own evidence has to be readable before it is quotable.

### Coordinator

1. Keep `main` moving and keep the register honest.
2. Arbitrate cross-lane requests; they are the only thing that can deadlock this workspace.
3. Track the four gates and say plainly which are met.
4. Surface the three human decisions below at the moment they become blocking, not before.

## The three decisions that are the human's, named now

None of these blocks a lane today. Each will block a gate, and naming them now means nobody
discovers them at the moment they are urgent.

- **`B7`, the acceptance run.** It opens a pull request on a real GitHub repository and spends
  `xhigh` model time. Its own backlog entry says it is not a worker's to run unattended. Gate 1
  cannot close without it, so it needs a human to say when.
- **Where the beta console is served, and under what credential.** Ruling 1 makes this small -- one
  shared credential, no user system -- but it is a spend and an outward-facing deployment.
- **Which repository the design partner brings, and whether Sync may open pull requests against it.**
  Gate 2's real samples come from real runs against real code.

## What is deliberately not in this document

No estimates in days. Six agents at unpredictable token budgets make a date a fiction, and the gates
above are checkable in a way a date is not.

No task breakdown below the item level. Each lane's charter says to take one reviewable unit and
land it; a plan that pre-decomposed forty items would be stale within a day, and it would be stale
in the specific way that is hardest to notice -- individually plausible, collectively wrong.

## Reversing any of this

Every ruling above is one fix round to reverse. If a design partner arrives who needs tenancy on day
one, Ruling 1 changes and M4's hosted half moves onto the critical path. If the loop turns out to
close easily, M11 moves in. Record the reversal here, with the date and the reason, rather than
letting the queues quietly drift away from the document that ordered them.

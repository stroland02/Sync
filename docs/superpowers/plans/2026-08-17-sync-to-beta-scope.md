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

## Measured, not asserted: `uv run python scripts/beta_gates.py`

**Gate 3 is MET as of 2026-08-17 -- the first to clear, and cleared by measurement rather than by
assertion.** It took three attempts and the two failures are the interesting part: the first
signature went stale within forty-four minutes, and the second was invisible because the meter had
one report path compiled in, which made the gate unclearable by a lane doing exactly what it asked.
Both were found by the lane being blocked, not by the coordinator, and the meter now names its own
remedy when it cannot tell.

**1 of 4 met, 1 cannot be told.** The gates stopped being a coordinator's prose
the moment `CI-W289` landed, and the first thing the tool did was contradict this document.

- **Gate 1 -- NOT MET.** Four real attempts in the corpus, none with a pull request that went green.
  The resume-on-review-comment path *is* built; what has never happened is `B7`.
- **Gate 2 -- CANNOT TELL.** Zero of five axes carry samples; one pull request opened, none merged.
  The tool refuses to call that a failure, correctly: unmeasured is absence rather than a value of
  zero, so there is nothing here to pass or fail yet.
- **Gate 3 -- CANNOT TELL.** The pass was signed at 11:10 and the console changed at 11:54, so the
  signature describes an earlier tree. **This document recorded it as signed and that was stale
  within forty-four minutes.** Re-signing is Lane B's call, not the tool's and not the
  coordinator's.
- **Gate 4 -- NOT MET, and this is the finding of the day.** There are no unbaselined dead links --
  and `ephemeral_container`, `copy_between_containers` and `ensure_image_built` are *baselined* as
  reached from nowhere. **The sandbox is built and unwired, so no patch run is contained.** `B97` is
  the threat model's ranked-first item, and the baseline mechanism -- which this document sanctions
  for a producer landing ahead of its consumer -- is what let it sit that way while the gate read
  green.

The lesson is the one the product is built on, turned inward: a green check that was never wired to
anything is worse than a red one, because it is trusted.

**Gate 3 -- signed 2026-08-17, superseded by the measurement above.** Evidence:
`docs/superpowers/reports/2026-08-17-gate-3-screen-pass.md`. Ten of ten screens, every number traced
to a named payload field or a named derivation, read live off the API and compared against what the
screen renders; a number seen in only one of the two is not sourced. No product code changed to
produce the report. The pass also found what a weaker one would have accepted: `CONTEXT SAVINGS`
was originally passed on pattern-consistency with another screen, which is not provenance, and
chasing it to `graph_views` showed it computed as a row count times a fixed per-read constant --
which clears this gate and files `B145`, because no tokens are ever counted and the console
discloses the modelling only on the bounded-scan branch. The sharpest positive finding is Settings,
the one screen where the mock itself invents fixture numbers and the built console refuses to render
them.

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

## Gate 2's machinery is proven; only its data is missing

`M5-W308` separated the two questions hiding inside "Gate 2 CANNOT TELL", and the answer to the
dangerous one is the good one.

**Rehearsal rows cannot reach Gate 2's metrics.** `is_rehearsal` is recorded on every rehearsal row
and `GraphStore.migration_outcomes` filters `WHERE NOT is_rehearsal` -- confirmed in the source, not
taken from a report: the conflict clause is keyed on it at `store.py:1355`, and `:1363` states the
reason it is filtered there rather than handed to every caller. This was the finding that would have
been serious. Had a rehearsal row been indistinguishable from a customer run, every axis would have
been quotable as evidence it had not earned, and the first person to notice would have been a design
partner reading a number we gave them.

**All five axes compute correctly** over a wide population -- `merge_rate_by_change_kind`,
`merge_rate_by_tier`, `routing_accuracy`, `tokens_per_merged_patch`, `wall_ms_per_merged_patch` --
and `corpus_health` and `beta_gates`' Gate 2 evaluate with zero computational defects.

So Gate 2 is no longer "we do not know whether this works." It is "this works and has no data yet,"
and the only thing that produces the data is real runs -- which is `B7`, which is the owner's call.
The gate correctly still reads CANNOT TELL, because a proven calculation over zero rows is still
zero rows.

## `B7`'s risk changed materially on 2026-08-17, and the decision is now better informed

`B7` was frightening for one stated reason: the acceptance run had not executed since the pipeline
gained four graph nodes, so authorising it meant possibly discovering a months-old break while
spending a real pull request and `xhigh` model time on somebody's repository.

**Both halves have now been exercised without spending either.**

- `M5-W306` drove INDEX and SIGNAL end to end -- both coded vendors' change extraction, TypeScript
  and Python AST indexing, OpenAPI symbol resolution, intake assessment, finding creation. Zero
  defects.
- `M5-W307` drove all twelve remediation nodes individually *and* across compiled `StateGraph`
  routing paths -- the rehearsal path, remote CI passing through to a pull request being opened, and
  remote CI failing through retry to abandonment -- over the zero-remote rehearsal fixture against a
  real pinned corpus repository. Transition conditions and retry budgets behave. Zero regressions.

That does not make `B7` pass; only `B7` passing does that, and the gate meter still reads
`0 with a pull request that went green`. What it removes is the specific fear that authorising it
would be an experiment on unknown code. The nodes work. What has never been tested is the whole
thing against a real repository with a real vendor change and a real CI run.

The decision is still the owner's, for the reasons it always was -- a real pull request on a real
repository, and real model spend.

## Gate 4 is not blocked on wiring, and the coordinator was wrong about that

I spent several cycles pressing Lane A to "wire the sandbox", on the meter's reading that
`ephemeral_container`, `copy_between_containers` and `ensure_image_built` are baselined as reached
from nowhere. Lane A declined and cited this repository's own re-scope of `B97`. It was right.

**`B97`'s remainder is four items and two of them block hard.**

1. Compose the risky/safe container pair into one patch attempt. The primitives exist; the assembly
   does not. This is the only one that is actually wiring.
2. **An Anthropic-only forward proxy, unbuilt and undesigned beyond a sketch.** A `network="none"`
   container has no route for the SDK's own traffic -- which must flow for the whole run, from
   inside the namespace the mitigation exists to cut off. `ClaudeAgentOptions`' own
   `SandboxNetworkConfig` carries `httpProxyPort`, so a proxy is assumed by that surface too rather
   than avoidable through it.
3. **Nobody has established which credential the CLI needs to reach Anthropic.** No
   `ANTHROPIC_API_KEY` reference exists anywhere in `src/`, and the environment snapshot carried no
   `ANTHROPIC_*` variable at all -- only `CLAUDE_CODE_EXECPATH`, pointing at an already-authenticated
   binary. A container that cannot authenticate cannot host a patch run, so this blocks item 1 as
   hard as the proxy does. It is the cheapest of the four to answer and **it is a credential
   question, which makes it the owner's.**
4. Mitigation 5's remaining properties.

So Gate 4 reads NOT MET for a truthful reason and will keep reading NOT MET until a proxy is
designed and a credential is established. **The baseline entries are honest**, not a dodge: neither
a worker process nor a scheduler exists to call the image builder, and inventing one would be an
abstraction with no caller.

The coordinator lesson is worth keeping: the meter said "reached from nowhere", which is true, and I
read it as "somebody forgot to call this", which was not. A gate saying *what* is missing does not
tell you *why*, and the lane that owns the file had the answer the whole time.

## Ruling 7: B97's proxy and its credential are one piece of work, not two

**Decided 2026-08-17, on `B156`'s evidence.** Lane D established the CLI's credential discovery order
empirically -- `ANTHROPIC_AUTH_TOKEN`, then `ANTHROPIC_API_KEY`, then on-disk OAuth at
`.credentials.json`, then `apiKeyHelper`, then third-party providers, then failure with
`authentication_failed` -- and confirmed that `build_container_env()` passes none of them, so an
isolated container fails with *"Not logged in"* before a patch begins. **A forward proxy alone is
therefore insufficient.** That was not known before; it was assumed the proxy was the whole of the
network problem.

Three container options exist and two of them defeat the thing the sandbox is for:

- **`auth_env` injection** puts a live credential inside the container. The whole premise of B97 is
  that the patch agent holds `Bash` and is not trusted with what is reachable from inside; handing
  it a credential is the same mistake the mitigation exists to prevent, differing only in whose
  secret is at risk.
- **Mounted credentials** are the same objection plus a filesystem path to exfiltrate.
- **A credential-injecting proxy** keeps the credential outside the container entirely. The
  container gets no egress except through the proxy, and the proxy attaches authentication to
  Anthropic-bound traffic that the container itself never holds.

**The third is the design, and it means B97's item 2 and item 3 are one piece of work.** The proxy
that restricts egress to Anthropic is the same component that supplies the credential; building it
twice, or building the proxy first and discovering the credential problem afterwards, is the failure
this ruling exists to prevent.

**What is still the owner's:** which credential Sync's own runs authenticate with -- an operator
OAuth session, a dedicated API key, or a third-party provider. That is an account and a spend, and
it decides what the proxy holds.

## The one console gap that would block a design-partner beta

`reports/2026-08-17-console-beta-stock-take.md`, from the lane that has walked every screen twice
with a measurement in hand and once through the production runtime.

**Every walk this console has had ran against the seeded fixture. A design partner's first five
minutes are the opposite state: configured, nothing indexed, every table empty.** That is the one
screen state nobody has examined, and on a console whose entire argument is that absence is not
zero, a screen reading zero where it means never-measured fails on the axis the product is sold on.

The claim is carefully limited and worth repeating in its own words: *"I do not claim it does; I
claim nobody has looked, and it is one seeded database away from being checkable."*

Four smaller gaps sit under it, none blocking: a failed panel offers no way to re-ask, nothing on
screen names which deployment the console is bound to, route changes do not move focus, and the
abandoned-run workflow screen is unit-tested but has never been rendered. Two things are argued
*against*: restyling, because every measured bar is clear and nothing is asking for it, and the
second drawer, which still has one consumer.

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

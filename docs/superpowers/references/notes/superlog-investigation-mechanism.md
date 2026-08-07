# Superlog, read as source — the mechanism behind an automated resolution

**2026-08-06.** `github.com/superloglabs/superlog`, Apache-2.0, read from a full local checkout at
commit `b11acc1`. Every path below is relative to that repository's root, never to ours. The
running instance was seeded and driven through its own UI first, so the claims about what a screen
shows were checked against a screen; the claims about how it works were read from source.

**What this note is and is not.** Mechanism, data model, pipeline and stated reasoning. **No
component was copied and no class string appears below.** `.claude/rules/interface-originality.md`
separates the conventions of the form from identity; this note stays on the mechanism side of that
line, and where a section is about a screen it describes what the screen is *composed of* rather
than what it looks like. The standard is the same one
`references/notes/supabase-control-plane-mechanism.md` set, including its named failure mode: a
note describing what a component looks like is worthless.

**The boundary of what could be read.** Superlog's investigation *runner* is not open source.
`apps/worker/src/infra/agent-runner/backend.ts:44-50` resolves the real runtime through
`await import(process.env.AGENT_RUNNER_ANTHROPIC_MODULE)`, an external module shipping with their
hosted product. What is open is a static `community` runner that calls no model
(`infra/agent-runner/community.ts`), and every piece of orchestration around the seam.

That is the more useful half, and it is worth saying why. An implementation is one way of
satisfying a contract. The contract, the state machine, the persistence grain and the queue
topology are the parts another system has to get right, and all four are fully legible here.

---

## 1. The unit of work is an Incident, and Issues fan into it

The distinction is the load-bearing one, and Sync has no equivalent.

An **Issue** is one recurring error or one alert episode — a fingerprint with a count. An
**Incident** is the thing an agent investigates and a human reads, and many Issues join one. A
seeded run observed here produced 25 Issues and 25 Incidents; a real one read from their cloud
produced a single Incident carrying **eight** Issues resolved in one call.

`packages/db/src/schema.ts:886` — `incidents` carries three relationship columns that are worth
taking as a set, because each answers a lifecycle question separately:

- **`mergedIntoId`** — duplicate Incidents collapse. Their comment: *"Merged incidents have their
  `incident_issues` repointed to the survivor; lookups should follow the chain to find the live
  row."* Merge is a pointer, not a delete, so a link into a merged Incident still resolves.
- **`previousIncidentId`** — a recurrence chain. The comment states the decision explicitly:
  *"when a resolved issue recurs we open a NEW incident rather than reopening the old one, and
  point it at its predecessor here. Agent runs on the new incident get the predecessors' findings
  injected as context."*
- **`noiseReason` / `noiseResolvedAt`** — a status of `autoresolved_noise` carves out
  reopen-on-recurrence: *"recurring events bump `issue_count`/`last_seen` but keep the noise
  status until weekly review."*

**What transfers.** Sync's grain is one finding per claim per call site. One vendor change touching
eight call sites is eight findings, and today that is eight remediation runs against one
repository. The Incident layer is the fix, and Sync's grouping key is stronger than theirs:
findings sharing a `vendor_change_id` against one repository are deterministically one unit of
work. Superlog needs a model to decide whether two exceptions are the same incident, and that step
is exactly what fails when no API key is configured — the running instance showed *"Grouping
Failed"* on every error for that reason.

**What does not transfer.** The noise carve-out is about human-reported error streams. Sync's
findings come from a diff of two specifications; there is no noise class of that shape.

## 2. One event table, two join keys, and a check constraint that earns its place

`packages/db/src/schema.ts:1274` — `incident_events` is the spine of the Activity feed, and its
shape is the most directly reusable thing in the repository.

Both parent columns are nullable, and the comments say why each exists:

- `agentRunId` nullable *"so incident-lifecycle events (manual resolves from the dashboard or
  Slack, sweep proposal confirmations, anything that isn't tied to a specific agent run) can still
  land in the timeline."*
- `incidentId` always set for incident-scoped events, *"regardless of which agent run (if any)
  produced it. Surviving without an `agent_run_id` is the whole point of this column."*

Then four **partial** unique indexes rather than two coalesced ones — dedupe scoped per
`(agent_run, key)` when the event belongs to a run, per `(incident, key)` otherwise, for both
`providerEventId` and `dedupeKey`. Their stated reason: *"Postgres unique indexes treat NULL as
distinct, so two partial indexes are cleaner than a single coalesced one."*

And the constraint that makes the nullable pair safe:

```sql
CHECK (agent_run_id IS NOT NULL OR incident_id IS NOT NULL)
```

*"Every event must link to at least one parent. Without this, a row could land with both columns
NULL and bypass every dedupe / lookup index above — invisible orphan that the timeline UI also
can't reach."*

**Visibility is a naming convention, not a column.** `packages/db/src/incident-event-visibility.ts`
exports `INTERNAL_INCIDENT_EVENT_KIND_PREFIX = "internal_"`, and the timeline query filters with
`notLike(kind, INTERNAL_INCIDENT_EVENT_KIND_SQL_PATTERN)` (`apps/api/src/index.ts:3274`). Machine
bookkeeping and human-facing progress share one table and one writer; only the prefix separates
them.

**What transfers.** All of it. Sync writes run progress nowhere durable — LangGraph checkpoints
hold state, not a narrative — so an operator asking "what did this run actually do" has the
`migration_outcome` row and nothing else. This table is the shape of the answer, and the check
constraint plus the partial indexes are the two details a first attempt would omit and regret.

## 3. The timeline is assembled, not stored

`apps/api/src/index.ts:3258` onward. The Activity feed is not a query against one table. It is a
merge of four sources: `incident_events`, `agent_pull_requests`, `agent_pr_events`, and
`agent_linear_tickets`, fetched concurrently and interleaved by timestamp.

That is a deliberate inversion worth noticing. The durable record stays normalised per subsystem —
a pull request is a PR row, a ticket is a ticket row — and the *narrative* is a read-time
projection. Nothing writes a denormalised timeline, so nothing can write a timeline entry that
disagrees with the record it describes.

**What transfers.** Directly, to `graph_views`. The console already reads the graph through view
functions returning primitives; a run narrative is the same kind of function over four tables, and
building it as a stored feed would create the drift this design forecloses.

## 4. The run state machine, and the two states that matter

`apps/worker/src/agent-runs/domain.ts:1-34`. Ten states, partitioned three ways — `ACTIVE_STATES`
the worker ticks, `TERMINAL_STATES`, and `DORMANT_STATES`.

```
queued → repo_discovery → running → { awaiting_human | awaiting_events | complete | failed }
                                          ↓ a human replies, or a PR event arrives
                                      resuming → running
```

The two that do not exist in Sync:

- **`awaiting_events`** — *"a run whose turn ended with PRs out for review: the session stays
  durable and PR events (comment/merge/close) resume it."*
- **`resuming`** — *"a previously-terminal run that a human message reactivated: the tick resumes
  its durable provider session in place (no re-investigation) — the heart of 'talking to an
  investigation'."*

`blocked_no_github` is the dormant one, and the reason it is dormant rather than failed is
recorded: those rows *"sit dormant until a GitHub install webhook or manual restart requeues
them"*, and the revival is a bulk update over every blocked row under the affected project rather
than a per-row lifecycle method — *"exposing one would create the illusion of a shared governed
path while the bulk update bypasses it."*

**What transfers.** `awaiting_events` is the milestone. Sync opens a pull request and exits, so CI
rejecting that pull request reaches nobody. Sync already holds the hard half: LangGraph checkpoints
in Postgres are a durable session store, and the forge is authenticated for webhook ingress. What
is missing is the parked states and the rule that a parked run is not ticked until something wakes
it.

## 5. The outcome contract — how an agent is allowed to finish

`apps/worker/src/agent-outcome-tools.ts`. Two tiers.

**Non-terminal:** `report_findings`. Callable repeatedly; every call revises. Its merge rule is
stated in the description and is not the obvious one — *"every other field overwrites its previous
value when provided and is kept when omitted"* — so a summary-only revision must not drop the root
cause. A naive object replace fails this silently.

**Terminal, one per turn:** `propose_pr`, `resolve_incident`, `complete_investigation`,
`ask_human`, `report_external_cause`. Two of them (`propose_pr`, `resolve_incident`) are dispatched
server-side *before* their final acknowledgement, so a delivery or validation failure is
correctable inside the same turn rather than ending the run.

Three rules come with it, each written down with its reason:

- **Flat schemas only.** No `oneOf`/`allOf` at the top level of a tool's `input_schema` — *"some
  runner APIs reject composition keywords at the top level of a custom tool's input_schema, and a
  rejected schema blocks every run at agent-create time."* The failure is fleet-wide and lands
  before any work starts.
- **Re-validate server-side, and address the error to the model.** *"Schemas are not enforced
  server-side by every runner, so `validateOutcomeToolInput` re-validates each call worker-side;
  its error strings are written for the model, which sees them as tool errors and can correct the
  call within the same session."* A rejected call is a retry, not a failed run.
- **Retired names redirect.** `RETIRED_OUTCOME_TOOL_NAMES` exists because *"sessions created
  against an old toolset can outlive a deploy (a parked run resumes days later), so a call to one
  of these must be error-acked with redirect guidance — not routed to the unknown-tool path, which
  hard-fails the run."*

**The atomic fan-in.** `resolve_incident` requires *"exactly one outcome for every linked Issue"*,
each carrying `issueId`, `status` (`resolved` | `silenced` | `under_observation`), `reason` and
`evidence`. The platform applies all of them and the Incident resolution together: *"If any entry
is invalid, nothing changes and the turn stays active."*

**Evidence discipline, which is the part closest to Sync's existing culture.**
`rootCauseConfidence` is an integer 0–10 with a written calibration rubric rather than a vibe:
*"10 = every claim backed by a verbatim quote from a file read this session AND you observed /
reproduced the failure; 7-9 = quote-backed, reproduction inferred; 4-6 = code path identified,
mechanism is hypothesis; 1-3 = speculative; 0 = no evidence (prefer ask_human then)."* A separate
`EVIDENCE_FORMAT` constant requires a bold `path:line` header followed by a fenced block quoting
the file verbatim, and it is appended into several tool descriptions rather than restated.

**What transfers.** The whole tier structure. Sync's remediation can currently say two things — a
diff, or an abandonment — so a run correctly concluding "the vendor's endpoint is down, there is
nothing to patch" has to spell that as a failure. The confidence rubric and the evidence format
are the strongest fit: Sync already refuses an unattributed finding and makes every binding carry
its rung, and this is the same discipline applied to a run's conclusion rather than to a binding.

**What does not transfer as written.** `propose_pr` requires patches as unified diffs under
`/mnt/session/outputs/`, which is a fact about their container runtime. Sync's equivalent is a
patch already applied in a clone that `static_verify` then compiles.

## 6. The runner seam

`apps/worker/src/agent-runner-backend.ts` declares the contract — ten methods plus
`maxRepoResources`, a runner's own ceiling on how many repositories it will hold.
`infra/agent-runner/backend.ts` resolves a runtime string to an implementation, and the open
runtimes are `community` (static, model-free) and `disabled` (throws on everything).

The seam is what makes their orchestration testable: every state-machine test in
`apps/worker/src/agent-runs/*.test.ts` runs against a runner that never calls a model.

**What transfers.** This is the cheapest item in the whole note and the one to take first.
`sync/remediate/agent_patch.py` constructs `ClaudeAgentOptions` and calls `query()` inline, so the
model, the prompt, the tool surface and the driving loop are one unit and the pipeline's tests
cannot run without a key. A protocol in `sync.core.protocols` — which already holds
`RequestCorrelator` and imports nothing — plus a static implementation, is a pure refactor with no
product surface that makes the remediation suite key-free.

## 7. Repository selection, and the one piece worth borrowing

`apps/worker/src/agent-run-context.ts:319`, `scoreRepos`. A pure token heuristic, no model: +35
when the incident's service name is a substring of the repository's full name, +25 per matching
token of the service, +4 per token drawn from a stack frame in the linked issues. Sorted, then
capped at the runner's `maxRepoResources`. Installation tokens are then minted per installation in
chunks of 500 repositories — *"a 100-request burst previously triggered GitHub's secondary rate
limit."*

**Mostly not applicable.** Superlog scores candidates because it discovers repositories from a
GitHub App installation and must guess which one an exception came from. Sync is told which
repository to work on.

**One piece is worth taking.** Before handing a candidate over, they probe its default branch for
`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.cursor/rules/*` and
`.github/copilot-instructions.md`, *"so the agent reads them after cloning and follows the repo's
conventions"* (`agent-runner-backend.ts:15-21`). That is the same instinct as `B122`,
per-repository context, arrived at independently — and it is evidence for the seed-file half of
that design rather than for the operator-written half.

## 8. Infrastructure notes

Three, briefly, each read from `apps/worker/src/index.ts`.

**Side effects run on a queue, not inline.** Issue-transition work — incident intake, its grouping
call, notifications, agent-run routing — is enqueued on pg-boss *"so a burst of new fingerprints
can't stall the ingest cursor for other projects."* Registration failure degrades to inline
execution rather than crashing boot.

**Every periodic step is its own recurring chain**, *"so one slow step can't delay the others"*.
When pg-boss is up, chain-owned steps are skipped in the local tick even if their own registration
failed — because *"a local tick fallback could run the step concurrently with another process's
live chain (double webhook deliveries)"*. A failed step goes dormant and loud rather than
duplicating work.

**The telemetry discovery cursor crawls in bounded windows.** Five minutes per pass by default,
which is the reason a locally seeded instance showed zero errors for a long time: the cursor sat
days behind and had to walk forward to reach the data. A fresh cursor is allowed to start at the
current horizon rather than at the epoch, and the comment says why — *"crawling from Unix epoch in
five-minute windows would otherwise take years before the first candidate."*

**What transfers.** The second one, most. Sync's tick is a single sequence; a slow stage delays
every other. The rule that a step which cannot own its chain goes dormant rather than falling back
locally is the non-obvious half, and the reason given — concurrent duplicate side effects — applies
to Sync's forge the moment more than one process ticks.

## 9. What this note deliberately does not cover

**The incident screen's layout.** It was viewed, and it is theirs.
`.claude/rules/interface-originality.md` governs, and nothing about arrangement, spacing, colour or
component choice is recorded here. What is recorded is the composition question a screen has to
answer — a header of incident facts, a chronological feed merged from four sources, a findings
view, and a reply box that reactivates a terminal run — because that is a data-shape question, not
an appearance one.

**Their prompts.** The `report_findings` description is quoted where it states a *contract* the
implementation must honour. The parts that are prompt engineering for a particular model are not
transferable and are not recorded.

**Anything about the runner's internals**, which could not be read at all.

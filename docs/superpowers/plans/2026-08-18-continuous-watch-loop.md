# The continuous watch loop: staying current with every connected API, on a heartbeat

**Owner's question, 2026-08-18 (night):** once a user has set up integrations and connections, how
does Sync *constantly* stay up to date with those API services — using the practices and loops
already built? Research what exists, plan how it should function, say what still needs building.

**Researched against the tree, not from memory.** Every claim below names the module or spec that
carries it.

## The finding, stated first

Sync today is a **complete reactor with no clock**. Every stage of the loop exists and is tested —
acquisition, detection, routing, remediation, PR reconciliation, even resume-on-review-comment —
but every one of them runs when a person types a command. Nothing anywhere runs on a cadence:
no scheduler, no daemon, no watch command. The continuous loop is therefore not a new pipeline;
it is a **subscription store, a version cursor, and one idempotent command a clock can call.**

## What already exists, per stage (measured)

| Loop stage | What exists | Where |
|---|---|---|
| Change acquisition | `prepare_vendor` stages specs per vendor; the generated route already detects change by **manifest hash move** — "fetches the specification it names when its hash moves" | `sync.signals.registry`, `sync.signals.generated` |
| Change distribution | The **signed public change feed** — publisher, verifying consumer, `FeedCache`, MCP resource `sync://feed/{vendor}` — built, tested, **unpublished**: no hosting, no production keypair | `sync.signals.feed`, spec `2026-07-26-sync-public-change-feed.md` |
| Detection | Detectors over the graph; one `Finding` type; idempotent stages with natural keys (oasdiff exemption recorded) | `sync.detect`, pipeline-discipline spec |
| Reaction | `sync run` (end-to-end), `sync ingest` (offline over staged artifacts), routing matrix, checkpointed remediation | `sync.cli`, `sync.route`, `sync.remediate` |
| Aftercare | `sync reconcile-pull-requests` polls merge outcomes; **resume-on-review-comment is built** (beta gates report it); abandoned runs feed routing | `sync.cli`, corpus tables |
| Observed rung | Telemetry adapters (Datadog, Sentry) fold runtime evidence in | `sync.signals.datadog`, `sync.signals.sentry` |
| Per-repo policy | **Designed, partially built**: the design doc's M4 scope names "per-repository policy: which vendors are watched, and which severities open a pull request automatically versus requiring review" (`:390`); the agent-settings API (`merge_policy`, refused values) landed via the console lane | design doc, `sync.api` |

What does **not** exist, verified by search: any scheduler, daemon, `watch` command, or cadence
configuration. `sync context` is prompt context for the patch agent, not a subscription registry.

## What the record already decided (swept: 33 specs, 36 plans, BACKLOG, WORKLOG, the public docs)

Three parallel researchers read the full documentary record on 2026-08-18. The original intent is
consistent and specific, and this plan now defers to it where it spoke:

- **Cheap-poll cascade is an architectural requirement, not an option.** Poll a small text
  artifact — a Stainless `openapi_spec_hash`, a registry `list.json` timestamp, an ETag, a
  deprecation page — and fetch the specification only when it moves. *"A tier that must download
  every specification to learn nothing changed does not belong in this architecture"*
  (`2026-07-29-sync-adaptive-vendor-substrate.md:441`; also `2026-07-27-sync-adapter-targets.md:86-89`).
- **Cadence is vendor-driven and self-clocking.** The feed regenerates *"on every new pinned
  version pair a VendorAdapter processes, not on a fixed schedule… never on a fixed clock"*
  (`2026-07-26-sync-public-change-feed.md:98-102,172`). The clock drives *adapter runs*; feed
  publication follows runs.
- **Streaming is refused; the workload is documents per day.** Watermarks, windowing and
  exactly-once delivery deliberately do not apply (`2026-07-27-sync-pipeline-discipline.md:188-195`).
  The tick is a batch, and idempotence-plus-natural-key is the delivery guarantee.
- **MCP is the one tier that *requires* a timer.** No vendor-side change signal exists for tool
  schemas; Sync owns the snapshot store, one row per `(server, observed_at)`, which *"should
  start as soon as the adapter exists"* (`2026-07-25-sync-mcp-drift-measurement.md:89-101`).
- **The original adapter signature was `fetch_changes(since: Version)`**
  (`2026-07-25-sync-self-maintaining-apis-design.md:111`) — the cursor restores the founding
  intent that the hand-pinned `--from/--to` pair later displaced.
- **Inbound GitHub webhooks were designed; vendor webhooks were not.** M2's lever is a push
  webhook re-indexing changed files (`latency-architecture.md:73,167`); the merge-outcome
  webhook *"arrives days later"* and its receiver already exists as a pure function with *"no
  HTTP framework, deliberately"* (`migration-corpus.md:133`, `benchmark-gates.md:106-118`); M10
  names the PR-event ingress that wakes a parked run. So the earlier "no webhooks in v1" ruling
  is refined: **vendors are polled; GitHub is the one designed push source**, and wiring its
  already-written receivers is part of this loop, not an addition to it.
- **Batch-priced work goes to the Batches API.** *"Nightly vendor scans and full-fleet
  re-indexes belong in the Batches API at 50% cost. Interactive work never does"*
  (`latency-architecture.md:153`) — the tick's model-tier remediation is batch work.
- **The precedents for periodic work are already in the tree**: the sandbox image pre-warm is
  specified as worker-start plus a daily check, off the critical path (`b97-sandbox:238-243`,
  its `ensure_image_built` sitting in the dead-links baseline *"because neither a worker process
  nor a scheduler exists"* — the watch tick is the caller that retires that baseline entry); and
  B194's heartbeat sweep shipped **read-triggered**, *"because a local-first deployment owns no
  supervisor"* — the honest interim shape for any periodic job here.
- **The subscription vocabulary already exists**: intake's *watched / watchable-but-unconfigured /
  not-watchable* artifact (`adaptive-vendor-substrate.md:242-243`), which the catalog's
  supported/recognized split mirrors. The `watch_subscription` table adopts it rather than
  inventing a fourth vocabulary.
- **The public docs promise a watcher and document a reactor.** Every entry-point doc says
  "watches" with no cadence, and `writing-a-vendor-adapter.md` — the file third parties receive —
  never tells an author `fetch_changes` will be called repeatedly, while its neighbouring
  protocols carry explicit twice-over-unchanged-input rules. Closing that documentation gap is a
  deliverable of this plan, not a footnote.
- **What was deliberately deferred stays deferred**: console-triggered runs (an unauthenticated
  spend surface — a security ruling), the scheduled rehearsal (harness ticks die with sessions;
  CI's nightly at 03:43 UTC is the clock that exists today), autonomous B7 (a human decides when
  real money and a real repository are spent), and feed hosting + the production keypair (owner
  decisions named since July).

## How the continuous loop should function

### 1. Subscriptions are derived from the graph, not configured by hand

A repository is watched against **every vendor its indexed call sites bind to**. The graph already
knows this — INDEX writes the bindings, `sync intake` reports watchability — so connecting an
integration *is* indexing it. A `watch_subscription` table (grain: one row = one repo × vendor
pair) is **seeded from bindings automatically** and carries only the operator's overrides:
cadence, pause, and the severity policy the design doc already names. The catalog's
recognized-but-unwatched vendors surface here as named absence, never as silent scope.

### 2. A version cursor replaces hand-pinned versions

`sync run` takes `--from-version/--to-version` by hand. Continuous operation needs a **cursor per
(vendor)**: the last version successfully scanned. Each tick resolves "newest available" per
vendor kind (generated: the manifest's current state — the hash-move detection already exists;
coded: the adapter's newest staged tag; MCP: current capture) and runs `last_seen → newest` only
when they differ. The cursor is a table write in the same transaction as the scan's rows, so
at-least-once delivery composes with the idempotent stages instead of double-counting.

### 3. One idempotent tick, callable by any clock

`sync watch --once`: for each due subscription — refresh artifacts (or consume the feed, below),
advance the cursor, DETECT, ROUTE, remediate per the repo's policy, then `reconcile-pull-requests`
and resume-on-comment in the same tick. Exit 0 having printed what it decided per subscription,
including "nothing moved", because a silent tick is indistinguishable from a dead one.

**The clock is deliberately not ours.** `--once` composes with cron, Windows Task Scheduler, a CI
schedule, or a compose service running `while true; sleep`. A `--forever` convenience loop can
exist, but the contract is the idempotent tick — the same shape as every other stage.

Cadence defaults by cost, overridable per subscription: generated-manifest probe (one file fetch)
hourly; coded spec staging daily; MCP capture daily; telemetry is already continuous on its own
path. Jitter per vendor so a fleet of deployments does not synchronize against one vendor's CDN.

### 4. The feed turns N deployments × M vendors into 1 × M (phase two)

Today each deployment would poll vendors directly. The already-built signed feed is the designed
end state: **one scanner (ours) watches vendors and publishes signed per-vendor feeds; every
deployment's watch tick consumes the feed** through the existing verifying `FeedCache`. Deployments
get faster, vendors see one scanner, and the feed becomes the public artifact the positioning spec
commits to. Blocked on two owner decisions the spec already names: hosting, and a production
keypair (the committed key is development-only by name).

### 5. What the operator sees

The console already renders findings, runs, and absence honestly; the Setup panel probes
prerequisites. The watch loop adds two facts to render, both already representable: when each
subscription last ticked (staleness, which the console distinguishes from liveness), and the
cursor each vendor sits at (the "which Stripe is this" question the beta plan already asks of the
baked spec).

## What still needs building, in dependency order

1. **`watch_subscription` table + derivation from bindings** — schema + seed-on-index. Small.
2. **The version cursor** — table + per-kind "newest available" resolution. The generated kind is
   nearly free (hash tracking exists); coded needs "newest tag" per adapter.
3. **`sync watch --once`** — composition of existing commands over due subscriptions. The largest
   piece and still mostly plumbing; every stage it calls already exists and is tested.
4. **A shipped clock** — a compose service in the demo stack and a documented cron/Task Scheduler
   line for local installs; `npm start` gains nothing (the doorbell brings up services; the tick
   is the API host's job or an OS timer's).
5. **Feed publication** — owner decisions: hosting and a production keypair. Everything else is
   already written.
6. **Policy UI** — the Settings surface for pause/cadence/severity, over the settings API the
   console lane owns. Not blocking: derived subscriptions with defaults work headless.
7. **The adapter invocation contract, documented** — `writing-a-vendor-adapter.md` gains the
   repeat-invocation rules its neighbouring protocols already have: `fetch_changes` twice over an
   unchanged pair converges, staged artifacts are the cache, rate expectations per the cheap-poll
   requirement. Third parties build against this file; today it lets them assume one-shot.
8. **The GitHub ingress** — wire the already-written pure-function receivers (merge outcome;
   M10's PR-event resume) behind the one authenticated surface the threat model permits, so a
   parked run wakes without a human re-running anything.

## What this deliberately does not do

- No push/webhook intake **from vendors** — the record's cheap-poll cascade is the requirement,
  and a vendor webhook is a spoofing surface the threat model would have to rule on. GitHub's
  webhooks are different: designed since M2/M10, receivers already written, wiring them is item 8.
- No autonomous merge. The loop opens verified PRs; `merge_policy` already refuses `immediately`.
- No watching for recognized-only vendors — the catalog names them, the loop skips them, and the
  skip is visible per subscription rather than silent.
- No fixed publication clock for the feed — it republishes per adapter run, exactly as specified.

## Open questions the record never answered (for the owner, none blocking item 1-3)

Collected by the sweep as genuinely unaddressed, recorded so they are decisions rather than
surprises:

1. **Rate budgets against vendors** — jitter is named; retry, 429 handling, and a per-vendor
   request budget across a fleet are not.
2. **Where a critical finding gets delivered** — B94 records that the human-surface signal role
   has *no delivery destination at all*; a tick that finds a breaking change tonight has only the
   console to show it in.
3. **Tick overlap** — what a new tick does while a previous tick's remediation is parked on CI,
   and how a parked run interacts with the next cursor window.
4. **Cursor replay** — re-scanning a window after a detector fix; advancing on partial failure.
5. **Cost ceilings** — the per-run agent cost that `2026-08-05` said is *"the input to any future
   decision about cadence"* still has no measured value; the Batches API halves it for batch work.
6. **Unattended credentials** — the tick inherits an authenticated `gh` and a model credential;
   nothing yet says how those live in a scheduled, headless context.
7. **Feed operations** — hosting provider, data licence, key generation and rotation.

## Proposed backlog entries (the sweep found zero B-numbers for any of this)

- B-next: `watch_subscription` + cursor tables (items 1-2).
- B-next: `sync watch --once` (item 3), with the shipped clock (item 4) as its closing condition.
- B-next: the adapter invocation contract documented (item 7) — cited from `releasing-sync-core.md`,
  because the package metadata names the guide.
- B-next: GitHub ingress wiring (item 8), which is also M10's missing half.
- B-next: feed publication operations (item 5), blocked on the two owner decisions by name.

## Ledger

- **2026-08-18** Ruling: subscriptions derive from graph bindings rather than manual setup;
  operator input is overrides only. Reversible; the table shape carries both.
- **2026-08-18** Ruling: the tick is `--once`-idempotent and clock-agnostic; Sync ships no
  daemon of its own in v1.
- **2026-08-18** Ruling (after the record sweep): the earlier no-webhooks line is narrowed to
  vendor webhooks only; GitHub's designed ingress is in scope as item 8. The cheap-poll cascade
  and the never-on-a-fixed-clock feed rule are adopted as constraints from the specs rather than
  re-decided here.
- **2026-08-18 (owner, multiple choice).** Four decisions taken directly:
  1. **Triggers: all three families**, in tick form so no listener exists in a local-first
     deployment — vendor-artifact polls; a repo-HEAD poll that re-indexes on movement (the
     local-honest form of M2's push webhook, since a webhook cannot reach loopback); and a
     detection pass over the observed-telemetry store so drift already ingested escalates
     severity. Listeners stay refused per the standing rulings.
  2. **Default reaction: auto-PR for mechanically-safe breaking changes only**; everything else
     is a notified finding. Per-repo policy overrides later via the settings surface.
  3. **Cost: budget-capped ticks** — a per-day model-spend ceiling and a findings-per-tick
     limit, overflow queued visibly to the next tick, batch remediation routed to the Batches
     API per `latency-architecture.md:153`. Cheap polls are never budgeted; they are near-free
     by architectural requirement.
  4. **Notification: GitHub-native.** The verified pull request is itself the notification for
     remediated changes; non-PR findings open a GitHub issue on the watched repository. This is
     B94's first delivery destination; outbound webhooks remain open question 2.

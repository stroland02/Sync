# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

## Ready

### B7 — The M0 acceptance run has not executed since the pipeline changed underneath it

`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request` is the
milestone's definition of done and it is `@pytest.mark.e2e`, deselected by default, so
nothing in CI or in any worker's gates has exercised it. Since it last ran the pipeline
gained: the tier cascade, the property-omit codemod, a push guard over the discarded-commit
range, branch deletion on abandonment, checkpoint serialiser registration, the
dependency-edit guard, staged-new-file support, and dependency-tree discarding. Every one of
those sits on the acceptance path.

Checked cheaply and it is not obviously broken: the test still collects, and the production
graph compiles with the real `StripeAdapter`, `TypeScriptAdapter`, `TieredRemediator`,
`GitHubForge` and store, exposing all eight nodes. That establishes the wiring survived. It
establishes nothing about behaviour.

**Run it with `-n0`.** `addopts` now carries `-n auto`, which applies to the e2e test too.

**This one is not a worker's to run unattended.** It opens a pull request on a real GitHub
repository and spends `xhigh` model time on the patch agent. It needs a human to decide
when, which is why it is recorded here rather than dispatched.

**Closes when:** one `sync run` produces a CI-green pull request again, or the failure is
recorded with which change broke it.

### B25 — No shipped adapter is asserted against the conformance kit

The kit covers all five protocols and every rule is proved able to fail, but almost every one of
those proofs runs against a stub written for the purpose. `StripeAdapter` and `TwilioAdapter` are
what `sync.signals.registry` registers and what a customer's run loads, and neither is asserted
against `check_vendor_adapter` anywhere. The one exception is Stripe's correlator, added with
`check_request_correlator` in `tests/test_span_correlation.py`.

A kit whose own project never runs it against its own adapters is a kit nobody has evidence works
on real code, and the plugin story rests on it.

**Closes when:** every implementation the registry holds is asserted against its protocol's check,
with the list derived from the registry rather than restated, failing loudly for a registered
vendor that has no fixture rather than skipping it.

## In flight

- **B24** — `task_8e675882a386`, in `sync-solo-b`. Builds B25's closing condition. Redispatched:
  the first worker held the task for half an hour without starting and did not answer two nudges.

## Done

- **The flaky database failures were never flaky.** Measured with a sampler through one full
  suite: peak **105** concurrent connections, mean 67.6, against the postgres default ceiling of
  **100** — `-n auto` gives one xdist worker per core and several worktrees run suites at once.
  Over the ceiling the failure is a `psycopg.OperationalError` on connect, landing on whichever
  database-touching test was running, which is why it moved between runs and never reproduced
  under a soak. Both coordinators lost time to it. `fba1f6e` raises the ceiling to 300 and takes
  effect on the next `docker compose up -d`, so it is landed but not yet active.
  **Reading rule while it is inactive: an assertion failure is real, a connection failure is not.**

- **B23** — the conformance kit covers all five protocols. `check_request_correlator` guards a
  privacy boundary rather than a correctness one: an observed path carries a live customer
  identifier and what comes back must address the operation with the vendor's published template.
  Verified by isolating the rule — a correlator returning the raw path is rejected, one returning
  `/v1/charges/{charge}` is accepted. Landed `ec080ee`. Two corrections from that worker, both
  right: the `cli.py` guards are at 1032 and 1102, and they should NOT call the kit, because the
  check needs a resolving request and its identifier that the ingest entry point cannot know.
- **B22** — the shipped `generated-vendors.yaml` is now gated. Its stale-exemption test fired
  against a real event within the hour: `symbols_speakeasy.py` landed, the one pending entry
  stopped describing anything, and the test named both the pair and the remedy. `PENDING_EXTRACTORS`
  is now empty. Landed `e5ee571`.

- **B21** — an existing database now gains columns added after it was created. `apply_schema`
  derives each table's columns from `schema.sql` and issues `ADD COLUMN IF NOT EXISTS` for
  whatever is missing, rather than executing a create-only script. The ALTERs are derived rather
  than hand-maintained, because a hand-kept list reintroduces the original bug the first time
  someone adds a column and forgets the migration. Landed `8a5cd89`, on main at `245382f`.
  Mutation-tested two ways before landing: reverting `apply_schema` to its create-only form fails
  2 of the 6 new tests, and the small SQL parser's documented limit is real — a semicolon inside a
  string literal fails 5 tests loudly rather than mis-parsing in silence.

- The conformance kit now covers four of five protocols, with 29 rules each proved to fire.
  Landed via `fc7090f`. It found the finding-collision defect below.
- `Finding.claim` joins the natural key, so three detectors stop overwriting themselves.
  Landed `c88f240`. Reproducing first revealed a second, unnamed axis in efficiency that a
  key-only fix would have turned from silent loss into a flood of rows.
- The indexer takes the SDK package from the vendor adapter rather than a module constant,
  delivered by the other coordinator's workers; `symbol_root` followed after a scoped-package
  defect that no fixture could see.

- An MCP vendor adapter, M3's last unstarted item. Landed via `28b0772`.
- The status-rate detector, M2's missing half. Landed via `28b0772`. It reports a *level* rather
  than a change, because `cli.py` truncates `observed_call` every run so "earlier" means earlier
  within one ingested window — and said so rather than quoting a trend it does not have.
- A language axis on the binding path. Landed `19834b6`.
- Efficiency findings state that a cost is shared across call sites rather than counted once
  each. Landed `0f980da`.
- The plugin SDK conformance kit and authoring guide. Landed `bb425ba`. Running it against the
  real adapters disproved one of its own rules within a minute.
- The orchestration archive: 147 worker reports, escalations and decisions, exported before the
  terminals were cleaned up. Landed `aef675a`.

- A language axis on the binding path. Landed `19834b6`. Every Twilio map key is snake_case
  (`twilio-python`), so a TypeScript call site could never resolve and failed silently. A
  mismatched spelling now refuses rather than being rewritten into a match. Written by the
  coordinator after the dispatched worker never started.

- The efficiency detector, M1's second half. Landed via `cb0ee3e`. Three findings — calls in a
  loop, uncached repeats, retry storms — and deliberately **no dollar figure**: a call count is
  a fact, a cost needs a price per call no table here holds.
- Loop context on `call_site`. Landed `e8076be`. A depth rather than a flag, counting array
  callbacks alongside loop statements. Written by the coordinator after two dispatched attempts
  had their work destroyed in shared worktrees.

- The M1 span store: `observed_call`, OTLP ingest, and correlation behind a `RequestCorrelator`
  protocol. Landed `ecab0bd`. Grain is one row per trace — per unit of work — which is what lets
  a loop be told apart from ordinary traffic, and what makes ingest idempotent with no counter.
- A second vendor adapter (Twilio), the first real second implementation of
  `operation_for_symbol`. Landed `14394e4`. It inverted the assumption the symbol map was built
  around; the design document now records it.

- Run the suite in parallel, one database per worker. Landed `b590a5e`. Measured **2.18x** on
  an idle 12-core machine, not the 3.0x first reported — that baseline was taken while other
  workers were running. The load-bearing find was `conftest` returning early on a set
  `SYNC_DSN`, which put all twelve workers on one database and deadlocked them on `TRUNCATE`.
- Discard a dependency tree the previous finding doctored. Landed `0fd1623`. Written by the
  coordinator after three dispatches to a worker failed to start.

- Let a patch ship a file it had to create. Landed `aeecde4`, with the install-mark fix at
  `12f9dc9`. Staging is the agent's assertion that the patch needs the file; untracked
  debris stays excluded because neither `git add -u` nor `git diff HEAD` reads it.
- Catch a patch that edited an installed dependency instead of the source. Landed `a891f65`.
  The cheap path guard's reasoning held but its mechanism did not — git cannot answer the
  question either way — so it compares filesystem mtimes instead. Residual recorded as B6.
- Refuse a push that would discard any non-Sync commit, not merely one at the tip. Landed
  `7adeb08`. The worker found a case the brief missed: a stranger's commit the push carries
  forward is not at risk, so refusing it would abandon findings needlessly.

- Register `sync.core` types with LangGraph's checkpoint serialiser. Landed `05c11f5`.
  The warning is read-side only and nothing fell back to pickle — the brief was wrong about
  that and the worker corrected it. Future failure returns a raw dict silently.

- Derive the SDK verb from `spec3.sdk.json`'s `x-stableId` rather than the URL shape.
  Landed `b289a9e`. Coverage unmoved at 105 of 414; one symbol corrected.
- Refuse a push lease against a tip Sync did not author; delete the branch an abandoned
  finding leaves behind. Landed `38ec2c7` and wired at `9627f65`.
- Run the tier cascade and give it the change class the acceptance run hit.

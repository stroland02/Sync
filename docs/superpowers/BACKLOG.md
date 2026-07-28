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

### B8 — M1 has no span store, so the efficiency detector cannot be built

Surveyed on `main` at `d6538fe`: there is no telemetry package. `src/sync/` holds core,
graph, index, signals, detect, remediate, forge, route, mcp and cli, and nothing ingests
runtime spans. `detect/` holds `vendor_change`, `parameter_deprecation` and `observed_drift`.
The design document's M1 — an OTLP endpoint over client spans, then an efficiency detector
finding calls in loops, default page sizes, uncached repeats and retry storms — is entirely
unwritten.

`observed_shape` does not substitute for it, and the distinction matters. That table records
response *shape* — `field_path`, `json_type`, `nullable_seen`, `spec_enum_values` — which is
the right evidence for contract drift and the wrong evidence for efficiency, which needs call
volume, timing, retry counts and repetition. They are different signals from different
sources and one is not a cheaper version of the other.

Split deliberately: the store and its correlation first, the detector second, and the detector
should not start until the store has real rows. The hard part of the first slice is the
table's grain — one row is not one span, and a query that counts calls by counting rows would
be wrong quietly.

**Closes when:** a captured OTLP payload committed as a fixture produces rows correlated to
call sites, re-ingesting it changes nothing, and the grain is written in `schema.sql`.

## In flight

- **B8** — `task_4c181a760d91`, worktree `m1-forge`. Owns a new `src/sync/telemetry/`, one new
  table in `schema.sql`, and its tests. Dispatched without waiting for the other coordinator's
  answer on M1 ownership; if they come back holding it, the collision is one table in
  `schema.sql` and the `operation_id` correlation, both named in the brief.


## Done

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

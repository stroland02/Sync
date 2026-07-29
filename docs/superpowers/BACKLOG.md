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

### B32 — Hold a same-operation site back, so precision has something to fail on

`falsifiable_negatives` now counts negatives the detector could have fired on and prints beside
precision. It reads **0** for all ten scored pairs, so the corpus states its own vacuousness in
its output rather than requiring a reader to know.

The cause is one line, `cli.py:1473`:

```python
targets = [site.id for site in sites if site.operation_id == change.operation_id]
```

Every same-operation site is targeted, so none is ever left untargeted, so no falsifiable negative
can exist. Verified empirically: `affected + unreachable` equals the same-operation count each
spec header records, for all ten pairs.

**Not fixed, deliberately, and the reason is a real trade rather than a boundary.** Holding a
same-operation site back from `targets` creates the negative — `generate_pair` already supports it,
since the caller names its targets — but it also **moves recall's denominator**, and recall at
n=12 is currently the only genuine quality measurement this project has. Trading the one real
number for a second one needs a decision, not a patch.

**Start from the diagnosis, do not re-derive it.**
`docs/superpowers/reports/2026-07-29-precision-has-no-negative-to-fail-on.md` is the finished
investigation — B31 diagnosed this and is closed. The remaining work is one edit to the target
list at `cli.py:1473` plus a declaration in the pair specifications naming which sites are held
back. `generate_pair` needs no change, since the caller already names its targets, and
`falsifiable_negatives` will report whether the new corpus actually bought a candidate.

**Closes when:** that trade is decided and, if taken, precision is recomputed with
`falsifiable_negatives` non-zero and recall's new denominator stated beside it.

### B29 — The binding score's response axis has never had a sample

Every `response-property-removed` pair in the frozen corpus scored **0 affected and 0 findings**,
and eleven labels landed in `unreachable`. The corpus's twelve labelled positives are all
request-side, so binding precision and recall are computed **entirely over the request side** and
the response half cannot move either number. That is why 1.0000 at n=12 is a narrower result than
it reads.

Two causes, and the second compounds the first rather than being independent of it.

`mutate.py`'s `_result_binding` only recognises `const`/`let` declarations. Extending it to a
plain assignment and to a returned call converts the eleven unreachable targets into labelled
positives. It changes a generator, not the pipeline, so it moves the corpus without moving the
score's meaning.

`upsert_call_site` keys call-site identity on line and column, so a mutation that inserts lines
renames every call site below it in that file. The response-side mutation inserts a three-line
guard, so two pairs were refused as `displaced-label`. The refusal is correct — it is the feature,
not a bug — but it means a file with several calls can never carry a response-side pair.

**Closes when:** the response axis reports a number over a non-zero sample, with the displaced-label
interaction either resolved or stated as the reason a given file cannot carry a pair.

### B30 — `_score_corpus` cannot read a real repository

It reads every file under the checkout with `read_text(encoding="utf-8")`, so one PNG ends the run.
The Stripe Connect demo carries 63 files that are not UTF-8. The corpus currently works around it
by materialising only the files that decode and printing how many it dropped — a documented
transformation of the vendor's tree, not a fix.

`CLAUDE.md` already names the correct shape: when handling bytes that are not text, use
`read_bytes` and do not decode at all. Skipping a file that does not decode is what the indexers
want anyway, since nothing they read is binary.

**Closes when:** a corpus specification naming a repository with binary files scores without a
pre-filtering step, and the count of skipped files is reported rather than silent.

### B28 — The routing row still has nowhere durable to land

`_decide_tier` computes the decision-table row in the `locate` node and stores it on `RunState`;
`TieredRemediator` asks the same table again; the report node names it in its reason. Nothing
persists it. `migration_outcome` has no column for it, `sync.remediate.corpus` takes no such
argument, and `on_route` has no caller anywhere in `src/`.

Routing accuracy is one of the five quality axes, and it is the one that answers "was tier 0
wrong for this change kind". Without the row it is an archaeology project rather than a query,
and it stays that way however much corpus data arrives.

**Closes when:** the row a run actually routed on is queryable from the outcome it produced.

## In flight

- **B28** — `task_d36a5c6e7443`, in `sync-solo-b`. Freezes a specimen corpus and measures whether
  binding precision is actually deterministic, which is the precondition for the only tier C gate
  that is safe without the statistics research that never completed.

- **B24** — `task_8e675882a386`, in `sync-solo-b`. Builds B25's closing condition. Redispatched:
  the first worker held the task for half an hour without starting and did not answer two nudges.

## Done

- **B31** — diagnosed and closed; `falsifiable_negatives` reads 0 for all ten pairs and the
  cause is `cli.py:1473`. The follow-up is **B32**, deliberately a different number.
- **B27** — a specimen corpus is frozen and scored: 12 pairs across 4 repositories pinned by commit
  SHA, checkouts materialised into gitignored space, exclusions counted by reason. Landed
  `c6e18a0` after its worker died holding 1091 lines uncommitted; preserved as `4631c01` on the
  worker branch first, then verified and landed.

  **Determinism is measured, not assumed** — two runs byte-identical, which is what the only
  safely-addable tier C gate rested on and nobody had ever tested.

  Two caveats that must travel with the number. Both axes are computed over the **request side
  only**: every `response-property-removed` pair scored 0 affected and 0 findings, with 11 labels
  unreachable. And **precision 1.0 is a constant, not a measurement** — `cli.py:1473` targets
  every same-operation site, so no negative the detector could have fired on exists. Recall 1.0 at
  n=12 is real. See B31.

- **B26** — the conformance kit no longer certifies what it never exercised. `check_vendor_adapter`
  refused nothing when `known_symbol` was `None` or resolved to `None`; `check_remediator` read an
  empty diff as a decline, so a remediator claiming everything and writing nothing passed. Landed
  `f297e47`. The two refusals carry distinct messages, because "you gave me no symbol" and "your
  adapter did not resolve it" are different problems and an author who conflates them edits the
  wrong thing.

  The new rule fails four generated vendors, and the exemption's wording was the hard part. They
  are **not** unable to resolve: `_load_generated` (`registry.py:362`) passes `sources={}` because
  it promises to reach no network, while `_prepare_generated` (`registry.py:319`) passes
  `sources=sources` and is the path a real run takes. The kit is handed the offline one. Its
  staleness test fails in **both** directions — verified by mutation, dropping a vendor and adding
  one that resolves.

  The limit worth remembering: **this suite certifies an adapter shape no customer ever meets.**
  That closes with a staged fixture, not a bug fix.

- **B24** — nineteen shipped implementations are now asserted against the conformance kit, with
  every list derived from the registry rather than restated and a registered implementation that
  has no case failing **by name** rather than being skipped. Landed `52303b6`. No shipped
  implementation failed, and the worker did the more valuable thing: it asked why everything
  passed, and found **two checks that pass without exercising anything** — `check_vendor_adapter`
  certifies an adapter resolving no symbol when `known_symbol` is `None`, and `check_remediator`
  reads an empty diff as a decline. Both confirmed independently. B26 moves those fixes into the
  kit, where outside authors will actually meet them.

- **The flaky database failures were never flaky.** Measured with a sampler through one full
  suite: peak **105** concurrent connections, mean 67.6, against the postgres default ceiling of
  **100** — `-n auto` gives one xdist worker per core and several worktrees run suites at once.
  Over the ceiling the failure is a `psycopg.OperationalError` on connect, landing on whichever
  database-touching test was running, which is why it moved between runs and never reproduced
  under a soak. Both coordinators lost time to it. `fba1f6e` raises the ceiling to 300 and takes
  effect on the next `docker compose up -d`. **The container was recreated and the ceiling is now
  live at 300**, confirmed against the running server.

  Re-measured after the recreate, same machine, same suite:

  | | before | after |
  |---|---|---|
  | result | 1 failed, 13 errors | **1851 passed** |
  | wall clock | 187s | **103s** |
  | peak connections | 105 of 100 | 75 of 300 |
  | sampler connections refused | 16 of 322 | 0 |

  The halved runtime was not expected and is the part worth remembering: exhausting the ceiling
  was costing refused connections and retries throughout the run, not only the visible failures.
  A resource limit read as both a flaky test *and* a slow suite, and neither symptom pointed at it.

  Peak 75 against 300 leaves real headroom, but that was one suite alone. Nobody has yet measured
  the peak with two or three concurrent suites, which is the case that broke the old ceiling.

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

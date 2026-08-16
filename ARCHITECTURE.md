# Architecture

How Sync is built, in the terms it is built from. This is the engineering document; the
[README](README.md) is the product one. Every claim here cites the module that holds it, because a
diagram that has drifted from its code is worse than no diagram.

---

## 1. The shape of the whole thing

Sync is a **data pipeline with an agentic tail**. Four stages, three of them deterministic:

```
  INDEX          SIGNAL         DETECT              REMEDIATE
  ─────          ──────         ──────              ─────────
  parse the      fetch vendor   query the graph     turn one Finding into a
  customer's     changes and    for joins that      merge-ready pull request
  source into    runtime        mean something
  call sites     telemetry
      │              │              │                       │
      └──────────────┴──────┬───────┘                       │
                            ▼                               ▼
                  ┌───────────────────┐            ┌─────────────────┐
                  │  API Dependency   │──Finding──►│   LangGraph     │
                  │      Graph        │            │   state machine │
                  │    (Postgres)     │◄───────────│   + checkpointer│
                  └───────────────────┘   outcome  └─────────────────┘
```

**The load-bearing idea is that there is only one graph and one `Finding` type.** A breaking vendor
change, a wasteful call pattern and a production error are three *queries*, not three pipelines.
Adding a detector adds no orchestration. If a component neither reads from nor writes to the graph,
it probably does not belong.

### The four data-pipeline rules

These are enforced, not encouraged. Each failed silently at least once first.

| Rule | What it prevents | Where |
|---|---|---|
| **Declare a table's grain as a comment before adding a column** | One `migration_outcome` row is one *attempt*, not one finding. A query counting findings by counting rows is wrong, and wrong quietly | `src/sync/graph/schema.sql` |
| **Every stage is idempotent** | Re-running INDEX, SIGNAL or DETECT on the same input converges on the same rows. Every table has a natural key and an explicit conflict clause | commit `efcc19d` was this bug |
| **Every binding carries its rung** | A false positive that cannot be attributed to a class of evidence cannot be fixed | `.claude/rules/graph-grain.md` |
| **Abandoned runs are data** | `abandon_reason` stays queryable — abandoned attempts are where routing learns which change kinds are not mechanically safe | `RunState.diagnostics` → `migration_outcome` |

**One named exemption.** oasdiff-derived `vendor_change` rows do not converge, because
`oasdiff breaking` returns a different answer between runs over identical bytes on both pinned
versions. That source is treated as at-least-once and its row count is not read as a measurement.
Nothing else is exempt, and the exemption ships with the condition that retires it.

---

## 2. Provenance rungs — the alternative to a confidence score

Every binding between a call site and a vendor operation carries **the class of evidence it rests
on**. This is the single most important design decision in the system.

```
  observed   ── a real client span was seen calling this operation
      ▲
  resolved   ── the symbol resolved through an import graph to a known SDK export
      ▲
  static     ── the symbol matched an adapter's naming convention
      ▲
 unresolved  ── a call site exists; nothing binds it
      ▲
unattributed ── the default a write refuses to leave in place
```

**It is a column, not a join** (`schema.sql:162`, `:353`, `:421`), and deliberately outside the
natural key: *the rung describes the binding a count rests on, rather than which count it is*
(`schema.sql:442`). The write refuses an unattributed finding.

**Why not a 0–10 confidence score.** A scalar collapses *"we could not check"* onto the same axis as
*"we checked and it passed"*. A rung says which class of evidence a claim rests on and is
**attributable** — when a false positive appears, you can ask which rung produced it and fix that
rung. A `9` is neither. This is why the console renders no composite score, health figure, traffic
light or green dot anywhere.

---

## 3. The remediation state machine

`src/sync/remediate/graph.py`. A LangGraph `StateGraph` over `RunState`, checkpointed to Postgres at
every node. Solid arrows are the happy path; every node can reach `abandon`.

```
                          START
                            │
                            ▼
                      ┌──────────┐
                      │  locate  │  find the call sites the change touches
                      └────┬─────┘
                           ▼
                      ┌──────────┐
                      │ prepare  │  clone, install deps with --ignore-scripts
                      └────┬─────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          [report]     ┌───────┐    [abandon]
       nothing to try  │ patch │◄──────────────┐
                       └───┬───┘               │
                           ▼                   │
                  ┌─────────────────┐          │ feedback
                  │  static_verify  │  tsc     │ ≤3 attempts
                  └────────┬────────┘          │
                           ├───────────────────┤
                           ▼                   │
                      ┌─────────┐              │
                      │ replay  │  execute the patched path if it can
                      └────┬────┘              │
                           ├───────────────────┤
                           ▼                   │
                    ┌─────────────┐            │
                    │ push_branch │            │
                    └──────┬──────┘            │
                           ▼                   │
                    ┌─────────────┐            │
                    │  await_ci   │  the customer's own CI, 3–30 min
                    └──────┬──────┘            │
                           ├───────────────────┘  ≤2 attempts
                           ▼
                    ┌─────────────┐
                    │   open_pr   │
                    └──────┬──────┘
                           ▼
                          END
```

**Three details a diagram usually hides, all of them deliberate:**

- **A router's decision name and its destination differ in exactly one place.** A passing typecheck
  still decides `"push_branch"` — the *name is the decision*, "the path that ends in a push" — and
  that path now begins at `replay`. Renaming the decision would have reached into
  `sync.mcp.propose`, which reads the same string to establish that a patch is verified without ever
  building a node to push from (`graph.py:83-92`).
- **A replay that could not run is not a failure.** No resolvable export, a language it cannot
  execute, a file the index has outlived — none of those is a verdict on the patch. They reach the
  push path carrying the fact that the run was **not replay-verified**, because "the patched path
  was executed" is a sentence that goes in front of a reviewer.
- **`reported` is not a kind of abandonment.** Abandonment means Sync tried and could not finish;
  `reported` means the decision table found there was correctly nothing to try. Writing the second
  into `abandon_reason` would corrupt the signal routing learns from (`state.py:9-14`).

### Retry budgets

`MAX_STATIC_ATTEMPTS = 3`, `MAX_CI_ATTEMPTS = 2` (`state.py`). A failed typecheck and a failed CI
run both re-enter `patch` carrying `feedback` — which is a **different key from `diagnostics`**, on
purpose: `diagnostics` is one line for an operator, `feedback` is several paragraphs and a diff for
the next attempt. Serving both from one key means one of them gets the other's format.

### Routing on booleans, never on string shape

`verify_ok` and `replay_ok` exist because *a real `tsc` failure can exit non-zero with nothing on
either stream* — a silent `npx` fetch failure, for instance — which would otherwise read as success.
A router branches on a boolean a node set deliberately, never on whether a diagnostics string is
non-empty.

---

## 4. The tier cascade — do not call a model if you do not have to

`src/sync/route/matrix.py`. The tier decision table is **data**, so "tier 0 was wrong for this change
kind" is a query rather than an excavation.

| Tier | Name | Cost | When |
|---:|---|---|---|
| `-1` | `NO_PATCH` | free | The change needs no code edit. *The cheapest patch is the one you do not write* |
| `0` | `CODEMOD` | deterministic | The change maps to a known AST transform and the graph says the site is shaped for it |
| `1` | `TEMPLATED` | deterministic | A parameterised template covers it |
| `2` | `AGENT` | a model call | Everything else |

The table reads **`RoutingFacts`** — what the graph actually knows about the sites a change touches:
whether the changed field could be named at all (`field_resolved`; oasdiff records frequently name
none, and that is not a defect), how many indexed call sites read it, and whether it is passed as a
**literal rather than a variable** — because *a codemod can remove a literal; it cannot reason about
where a variable came from*.

Every routing decision records **the name of the row that decided it**, so the choice is auditable
after the fact.

---

## 5. Durable execution

A customer's CI takes 3–30 minutes and dominates the critical path. A worker restart mid-wait must
not lose the run — so state is checkpointed to Postgres at **every** node, and `await_ci` is a
resumable park rather than a blocking sleep.

**Two constraints this creates:**

- **Any state key written by parallel branches must declare a reducer.** Without one, concurrent
  writes are silently dropped — no error, no warning, missing results. This is the failure mode that
  binds everywhere because it never announces itself.
- **The checkpoint serialiser has an allowlist.** `serde.CHECKPOINTED_TYPES` is exactly
  `(CallSite, Evidence, Finding, Patch, RepoRef, VendorChange)`. A checkpoint is data that comes back
  into the process later; deserialising arbitrary types out of it is a remote-code-execution shape,
  so the msgpack decoder is constrained to those six.

---

## 6. Containing the agent

The patch agent holds `Bash`, `Write` and `Edit` **inside a customer's clone** — a directory that
routinely carries `.env`, `.npmrc` and fixture credentials. Three independent mechanisms, because
each covers what the others cannot.

### 6.1 A predicate on the run, not on the artifact

`src/sync/remediate/tool_gate.py`. `tsc`, `shipped_tree`, `dependency_edits` and the customer's CI
are all predicates on **the artifact** — they ask what the branch would contain. The threat ranked
first in the threat model does not want to ship anything: the taking happens *while the run is in
progress*, and the diff afterwards can be a perfectly correct migration.

So the tool gate asks what the run is **doing**. It refuses by default: any tool outside
`PERMITTED_TOOLS`, any shell command that is not one of `PERMITTED_COMMANDS`, and any write under
`.git/`. Everything it permits it records; everything it refuses it records **with the command
verbatim**.

> **Why a `PreToolUse` hook and not `can_use_tool`** — and this is measured against the installed
> SDK, not inferred. `claude_agent_sdk.types._get_can_use_tool_shadowed_warning` states that an
> `allowed_tools` entry allowing a whole tool auto-approves it *before* the permission callback is
> consulted. Every entry in the patch agent's allow-list is a whole-tool entry, so a `can_use_tool`
> gate would have been consulted for nothing **and looked like it was working**. `can_use_tool` also
> forces streaming mode; the hook sees every call under the options this pipeline actually passes.

`WebSearch` and `WebFetch` are denied, and that is real — but `curl` is a program rather than a tool,
which is the whole reason the gate exists.

### 6.2 Untrusted text is data, never instruction

`src/sync/remediate/untrusted.py`. The prompt that starts the patch agent is assembled from bytes
nobody at Sync wrote: a vendor's published prose, a customer's paths and symbol names, a compiler's
output over both. Until this module existed they were interpolated into the same flat string as
Sync's own instructions, with nothing marking which was which.

**The decision it encodes: vendor and repository text is data the agent reads *about*, never
instruction it follows.** Content is fenced with markers that exist nowhere but here — and a fence
whose content carries a marker is **refused rather than escaped**. Escaping is the usual choice and
the wrong one: a marker cannot occur in a deprecation table or in TypeScript by accident, so its
presence is adversarial by construction and the honest response is to stop.

### 6.3 What ships is not what the agent left behind

`static_verify` holds every untracked and every ignored path out of the clone before compiling, so
the verdict describes **the branch a push would create** rather than the working directory
(`sync.index.shipped_tree`). Installed dependencies are kept, because the customer's CI installs its
own — and an edit *inside* one would satisfy a gate their CI will not, so `sync.index.dependency_edits`
compares mtimes against the install and fails the verification naming the path, before the compiler
runs.

A file the patch creates ships only if the agent **staged** it. `git add -u` refreshes what the index
already holds and never reads the working tree for an unknown path, so a staged addition is carried
and an unstaged one is held out and fails the gate. That staging is the agent asserting the patch
needs the file, and it is deliberately the only such route: nothing here can separate a module a fix
requires from a byproduct sitting beside it, and a rule keyed on names or extensions would be wrong
on somebody's repository and wrong silently.

> **The honest limit.** *"We never execute customer code"* is the intent, not the invariant. Sync
> never runs the customer's application, and dependency installs pass `--ignore-scripts` so no
> lifecycle script runs — but it does execute their **toolchain**: `run_tsc` prefers the clone's own
> `node_modules/.bin/tsc`, resolved through their `.npmrc`. Say that, rather than the stronger
> sentence.
>
> We never hold customer secrets. That one is unqualified.

---

## 7. The verification chain

Four gates, cheapest first, and **no path skips them**:

```
  patch ──► tsc ──► replay ──► push ──► the customer's own CI ──► PR
            │        │                   │
         seconds   seconds            3–30 min
         (fast,    (executes the      (the final word;
          local)    patched path       their config,
                    when it can)       their runners)
```

The ordering is a **data dependency**, not a convention: `locate → patch → verify` cannot be
reordered, and the critical path is dominated by the customer's CI, which is why the whole pipeline
is built to park rather than block.

---

## 8. Plugin architecture

**`sync.core` imports nothing from any sibling package.** Not `sync.graph`, not `sync.signals`,
nothing. A third party writing a vendor adapter depends on `sync.core` alone and never inherits
Postgres. `tests/test_import_boundary.py` and `lint-imports` enforce it.

```
                 ┌─────────────────────────────────┐
                 │           sync.core             │  imports nothing
                 │  Finding · CallSite · Patch     │
                 │  VendorChange · the protocols   │
                 └─────────────────────────────────┘
                    ▲        ▲        ▲        ▲
              index │  graph │ signals│  forge │
                    │        │        │        │
              detect ────────┘        │        │
              remediate ──────────────┴────────┘
              dashboard / api ────────┘
```

The three protocols a third party implements:

| Protocol | Package | The hinge |
|---|---|---|
| `VendorAdapter` | `sync.signals` | `operation_for_symbol` maps `stripe.charges.create` → `POST /v1/charges`. **Without it, spec diffs and source code live in unconnected universes** |
| `LanguageAdapter` | `sync.index` | Turns source into `CallSite` rows via tree-sitter |
| `Detector` | `sync.detect` | A query against the graph that emits `Finding` |

**A `runtime_checkable` Protocol is not enough.** The standard library verifies only that method
*names* exist, so an adapter can satisfy `isinstance` completely and be wrong in every way that
matters. `sync.core.conformance` is the kit that checks the guarantees the type system cannot.

---

## 9. Terms

| Term | Meaning here |
|---|---|
| **ADG** | API Dependency Graph — one per customer; call sites joined to vendor operations and telemetry |
| **Binding** | The edge between a call site and a vendor operation |
| **Rung** | The class of evidence a binding rests on. A column, never a join |
| **Finding** | The one type every detector emits and the pipeline consumes |
| **Grain** | What one row of a table means. Declared as a comment before a column is added |
| **Tier** | How expensive a repair strategy is: `NO_PATCH` → `CODEMOD` → `TEMPLATED` → `AGENT` |
| **Abandon** | Sync tried and could not finish. Carries a reason, and the reason is queryable data |
| **Reported** | The decision table found nothing to try. **Not** an abandonment |
| **Checkpoint** | One durable state snapshot per node, in Postgres. The only evidence a run exists |
| **Shipped tree** | What a push would actually carry, which is not what is in the working directory |
| **Corpus** | 17 labelled pairs across 5 repositories, pinned by commit SHA and tree digest, that gate the binder |

---

## 10. Where the reasoning lives

Every decision in this document was argued somewhere before it was built. The specifications state
**what they measured**, not what they assumed.

| Document | What it settles |
|---|---|
| [Design](docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md) | The system, its milestones, its risk register |
| [Latency architecture](docs/superpowers/specs/2026-07-25-sync-latency-architecture.md) | Why every agent must shorten the critical path or improve a result |
| [Pipeline discipline](docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md) | Grain, idempotence, rungs — and what deliberately does not apply |
| [Threat model](docs/superpowers/specs/2026-07-25-sync-threat-model.md) | What a malicious vendor feed can and cannot do |
| [Benchmark gates](docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md) | What is gated, what is recorded, why no threshold is invented |
| [Verification regime](docs/superpowers/specs/2026-07-29-sync-verification-regime.md) | How much of the measurement actually runs today |
| [Adaptive vendor substrate](docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md) | How coverage scales by artifact tier rather than by vendor |

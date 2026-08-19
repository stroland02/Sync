# How Sync works

The mechanism: rungs, the state machine, the tier cascade, durable execution, containment,
and the two invariants. Moved out of `README.md` verbatim.

## How it works

The unifying primitive is the **API Dependency Graph** — one per customer, holding every
third-party call site in the codebase, joined against vendor specifications and the customer's own
production telemetry.

```
  EXTERNAL SIGNALS          ADG                    REMEDIATION
  vendor spec diff  ─┐   ┌──────────────┐        ┌───────────────┐
  vendor changelog  ─┼──►│ call sites   │        │ locate        │
  SDK releases      ─┘   │ endpoints    │        │ strategize    │
                         │ fields read  ├Finding►│ patch         │
  RUNTIME SIGNALS        │ versions     │        │ static verify │
  OTel client spans ────►│ volumes      │        │ push branch   │
  error rates       ────►│ status mix   │        │ await CI      │
  call patterns     ────►│ latency      │        │ open PR       │
                         └──────────────┘        └───────────────┘
```

Every detector is a query against that graph, and all of them emit the same `Finding` type into
one remediation pipeline:

- **Vendor change** — a vendor shipped something that breaks you.
- **Efficiency** — you are paying for calls you do not need: loops, absent caching, retry storms.
- **Production error** — an endpoint is failing, or its responses no longer match its spec.

**Patching is deterministic first.** If a change maps to a known transform — a renamed field, a
moved parameter — a codemod applies it, with no model call. Otherwise an agent produces the patch.
Neither path is trusted: `tsc` runs first because it is fast, then the customer's own CI is the
final word.

### Provenance rungs — the alternative to a confidence score

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

It is a **column, not a join** (`schema.sql:162`), and deliberately outside the natural key: *the
rung describes the binding a count rests on, rather than which count it is.* A scalar confidence
score collapses "we could not check" onto the same axis as "we checked and it passed". A rung is
**attributable** — when a false positive appears you can ask which rung produced it, and fix that
rung. A `9` is neither.

### The remediation state machine

A LangGraph `StateGraph` over `RunState`, checkpointed to Postgres at **every** node
(`src/sync/remediate/graph.py`). Every node can also reach `abandon`.

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
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          [report]     ┌───────┐    [abandon]
       nothing to try  │ patch │◄──────────────┐
                       └───┬───┘               │
                           ▼                   │
                  ┌─────────────────┐          │
                  │  static_verify  │  tsc     │  feedback
                  └────────┬────────┘          │  ≤3 attempts
                           ▼                   │
                      ┌─────────┐              │
                      │ replay  │  execute the patched path if it can
                      └────┬────┘              │
                           ▼                   │
                    ┌─────────────┐            │
                    │ push_branch │            │
                    └──────┬──────┘            │
                           ▼                   │
                    ┌─────────────┐            │
                    │  await_ci   │  3–30 min  │
                    └──────┬──────┘            │
                           ├───────────────────┘  ≤2 attempts
                           ▼
                    ┌─────────────┐
                    │   open_pr   │ ──► END
                    └─────────────┘
```

Three details a diagram usually hides, all deliberate:

- **A replay that could not run is not a failure.** No resolvable export, a language it cannot
  execute, a file the index has outlived — none is a verdict on the patch. They reach the push path
  carrying the fact that the run was **not replay-verified**, because *"the patched path was
  executed"* is a sentence that goes in front of a reviewer.
- **`reported` is not a kind of abandonment.** Abandonment means Sync tried and could not finish;
  `reported` means the decision table found there was correctly nothing to try. Writing the second
  into `abandon_reason` would corrupt the signal routing learns from.
- **Routers branch on booleans a node set deliberately, never on the shape of a string.** A real
  `tsc` failure can exit non-zero with nothing on either stream — a silent `npx` fetch failure, for
  instance — which would otherwise read as success.

### The tier cascade — do not call a model if you do not have to

The tier decision table is **data** (`src/sync/route/matrix.py`), so *"tier 0 was wrong for this
change kind"* is a query rather than an excavation.

| Tier | Name | Cost | When |
|---:|---|---|---|
| `-1` | `NO_PATCH` | free | The change needs no code edit. *The cheapest patch is the one you do not write* |
| `0` | `CODEMOD` | deterministic | The change maps to a known AST transform and the graph says the site is shaped for it |
| `1` | `TEMPLATED` | deterministic | A parameterised template covers it |
| `2` | `AGENT` | a model call | Everything else |

It reads **`RoutingFacts`** — what the graph actually knows about the sites a change touches:
whether the changed field could be named at all, how many call sites read it, and whether it is
passed as a **literal rather than a variable**, because *a codemod can remove a literal; it cannot
reason about where a variable came from.* Every decision records the name of the row that made it.

### Durable execution

A customer's CI takes 3–30 minutes and dominates the critical path, so `await_ci` is a **resumable
park rather than a blocking sleep**, and state is checkpointed at every node. Two constraints follow:

- **Any state key written by parallel branches must declare a reducer.** Without one, concurrent
  writes are silently dropped — no error, no warning, missing results.
- **The checkpoint serialiser has an allowlist.** A checkpoint is data that re-enters the process
  later, so deserialising arbitrary types out of it is a remote-code-execution shape.
  `serde.CHECKPOINTED_TYPES` is exactly six types, and the msgpack decoder is constrained to them.

### The watch loop — how "watches" stops being a verb and becomes a mechanism

Everything above is a reactor: it runs when something asks. The watch loop is the thing that asks,
and it is deliberately **one idempotent tick, callable by any clock** — `sync watch --once` from
cron, Windows Task Scheduler, or a CI schedule. Sync ships no daemon; a tick that can be re-run
safely composes with whatever clock a deployment already has, which is the same idempotency
contract every pipeline stage carries.

**Subscriptions are derived, not configured.** A repository is watched against every vendor its
indexed call sites bind to — connecting an integration *is* indexing it. The `watch_subscription`
table is seeded from the graph and carries only the operator's overrides: pause, cadence, and the
reaction policy. The default policy opens a pull request automatically for **mechanically-safe
breaking changes only** — safe meaning the routing table settles the fix below the agent tier, so
nothing marked safe can become an open-ended agent run.

**Detection is a cheap-poll cascade, because checking must cost almost nothing.** The tick never
downloads a specification to learn nothing changed: it reads the tiny artifact a vendor's SDK
generator already publishes — a manifest hash — and fetches the spec only when that moved. A
**version cursor** per vendor records the last version scanned and advances **in the same
transaction as the scan's rows**, so a tick that dies mid-scan rescans the same window onto the
same natural keys instead of double-counting. Spend on remediation is capped per tick, and
overflow is queued *visibly* — a silent tick is indistinguishable from a dead one, so every
subscription prints what was decided, including "nothing moved."

**Notification is GitHub-native.** A remediated change's notification *is* the verified pull
request. A finding that does not get one — policy said notify-only, routing said not mechanically
safe, or the budget deferred it — opens a **deduplicated GitHub issue** on the watched repository:
a deterministic title built from the finding's graph identity, the affected call sites, the
provenance rung, the reason Sync did not act, and the exact command to act by hand. The same
finding never opens a second issue.

Honest boundaries, stated rather than discovered: coded and MCP vendors do not yet have a cheap
probe, and the tick says so instead of faking one; the tick currently **records** its remediation
decisions rather than invoking the remediation composition, and prints exactly that; and the spend
cap counts findings rather than dollars, because no cost figure is recorded anywhere yet — the
tick tells you that too.

### Containing the agent

The patch agent holds `Bash`, `Write` and `Edit` **inside a customer's clone** — a directory that
routinely carries `.env`, `.npmrc` and fixture credentials. Three independent mechanisms:

| Mechanism | What it covers that the others cannot |
|---|---|
| **A predicate on the run** (`tool_gate.py`) | Every other gate asks what the *branch would contain*. The top-ranked threat does not want to ship anything — the taking happens mid-run, and the diff afterwards can be a correct migration. So this asks what the run is **doing**: it refuses by default, and records every refusal with the command verbatim |
| **Untrusted text is data** (`untrusted.py`) | The prompt is assembled from a vendor's prose and a customer's source. Those are fenced as text the agent reads **about**, never instruction it follows — and a fence whose content carries a marker is **refused rather than escaped**, because a marker cannot appear there by accident |
| **The shipped tree** (`shipped_tree`, `dependency_edits`) | `tsc` compiles what a *push would carry*, not the working directory. A file ships only if the agent **staged** it, which is the agent asserting the patch needs it |

> **Why a `PreToolUse` hook and not `can_use_tool`** — measured against the installed SDK, not
> inferred. `_get_can_use_tool_shadowed_warning` states that an `allowed_tools` entry allowing a
> whole tool auto-approves it *before* the permission callback runs. Every entry in the patch
> agent's allow-list is a whole-tool entry, so a `can_use_tool` gate would have been consulted for
> nothing **and looked like it was working**.

`WebSearch` and `WebFetch` are denied, and that is real — but `curl` is a program rather than a
tool, which is the whole reason the gate exists.

### The vocabulary

| Term | Meaning here |
|---|---|
| **ADG** | API Dependency Graph — call sites joined to vendor operations and telemetry |
| **Binding** | The edge between a call site and a vendor operation |
| **Rung** | The class of evidence a binding rests on. A column, never a join |
| **Finding** | The one type every detector emits and the pipeline consumes |
| **Grain** | What one row of a table means. Declared as a comment before a column is added |
| **Tier** | How expensive a repair strategy is |
| **Abandon** | Sync tried and could not finish. Carries a queryable reason |
| **Reported** | The decision table found nothing to try. **Not** an abandonment |
| **Checkpoint** | One durable state snapshot per node. The only evidence a run exists |
| **Shipped tree** | What a push would carry, which is not what is in the working directory |

### Two invariants

**Nothing reaches a pull request unverified.** Every patch passes `tsc` and then the customer's own
CI. There is no path that skips the gate.

Two honest qualifications on that, both measured rather than theorised. `tsc` verifies **the tree a
push would carry** — every untracked and ignored path is held out of the clone before it compiles,
so the verdict describes the branch, not whatever the agent left behind. And *"we never execute
customer code"* is the intent rather than the invariant: dependency installs pass `--ignore-scripts`
and Sync never runs the customer's application, but it does run their toolchain.

**`sync.core` imports nothing from any sibling package.** That is what makes this genuinely
pluggable rather than pluggable-shaped: a third party writing a vendor adapter depends on
`sync.core` alone and never inherits Postgres. `tests/test_import_boundary.py` and `lint-imports`
enforce it.

We never hold customer secrets. That one is unqualified.

---

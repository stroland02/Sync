# Sync — Latency Architecture

**Date:** 2026-07-25
**Status:** Specified. Not implemented at M0 — see Sequencing.
**Scope:** How Sync produces a verified solution in the shortest time a user can perceive, and which techniques are actually load-bearing for that.

This document is binding on the pipeline design. Any change that lengthens the critical path, or that adds an agent without shortening it, has to answer this specification.

## The goal, stated precisely

A user should see a trustworthy solution to an API break in **under two minutes**, and should never wait on work that could have been done before they asked.

"Trustworthy" is doing real work in that sentence. Sync's whole value rests on the verification gate, and the gate's final step — the customer's own CI — takes between three and thirty minutes. So the two-minute goal and the verification promise appear to contradict each other. Resolving that contradiction is the central design problem, and it is resolved in Lever 3, not by making anything faster.

## Measure first: where the time actually goes

Optimising without this table is guesswork. Approximate wall clock for one finding, cold:

| Stage | Time | Nature | Attackable by parallelism? |
|---|---|---|---|
| Fetch vendor specification (8 MB) | ~5 s | Network | Yes — and better, precomputable |
| `oasdiff` | ~3 s | Subprocess | Yes — precomputable |
| Clone repository | 10–60 s | Network | Yes — precomputable |
| Index with tree-sitter | ~5 s | CPU | Yes — precomputable |
| Detect | ~50 ms | Database | Irrelevant |
| **Patch** | **30 s – 5 min** | **LLM** | **Yes — the real agent target** |
| `tsc` | 10–60 s | Subprocess | Partially |
| **Await CI** | **3–30 min** | **External** | **No. Nothing we build changes this.** |

Two conclusions follow, and both are uncomfortable for a parallelism-first design:

**Agent parallelism addresses roughly a fifth of the wall clock.** Everything an agent could overlap sums to well under the CI wait. Amdahl's law is not a slogan here; it is the binding constraint. A design that answers "make it fast" by adding agents optimises the small number.

**The largest wins are not parallelism at all.** They are moving work off the request path entirely, and removing the external wait from the user's perception of the path. Those are Levers 2 and 3.

---

## Lever 1 — Structural parallelism

Real, bounded, and worth doing. Two forms.

### Independent branches overlap

The vendor branch and the repository branch share no inputs. Today they run in sequence, which is simply wasted time:

```
sequential (now)        ~23 s
  fetch spec -> diff -> clone -> index -> detect

parallel (target)       ~15 s
  fetch spec -> diff  ─┐
  clone -> index      ─┴─> detect
```

LangGraph runs this natively. When multiple edges leave a node into independent nodes, both targets execute in the same superstep. The saving is the shorter branch's duration, and it costs one graph edit.

### Fan out across findings

One vendor release affects many call sites. Remediating them one at a time makes latency linear in finding count, when the findings are entirely independent of each other.

LangGraph's `Send` API constructs edges at runtime rather than at compile time: a routing function emits one `Send` per finding, the runtime launches all of them in a single superstep, and the graph proceeds when every branch reports. Ten findings take as long as the slowest one, not the sum of ten.

> **Landmine, and it is a silent one.** Any state key written by parallel branches **must** declare a reducer. Without one, concurrent writes to the same key drop data with no error and no warning. In a fan-out over findings this would mean losing patches — the failure would present as "some findings mysteriously produced nothing." Every fan-out key gets a reducer, and a test asserts that N parallel branches produce N results.

---

## Lever 2 — Precomputation: the largest win

The fastest work is work already finished when the request arrives. Most of Sync's pipeline does not need to be on the request path at all.

**Vendor diffs are computed once per vendor, not once per customer.** A Stripe release is the same event for every customer who calls Stripe. Diffing it once and fanning the resulting `VendorChange` rows out to every affected graph turns an O(customers) cost into O(1). This is the single highest-leverage property in the whole system, and it improves as the customer base grows.

**Repository indexes are maintained incrementally, not rebuilt on demand.** A webhook on push re-indexes only the changed files — `content_hash` on `call_site` already exists for exactly this. A warm index answers in milliseconds where a cold clone-and-index costs 15 to 65 seconds.

The result is that the request path shrinks to the part that genuinely cannot be precomputed:

```
cold path   fetch, diff, clone, index, detect, patch, verify   ~90 s + CI
warm path   detect, patch, verify                              ~40 s + CI
```

Nothing was made faster. Work was moved off the path. That is the difference between an optimisation and an architecture.

---

## Lever 3 — Perceived latency: where the contradiction resolves

The CI wait cannot be shortened. It can be removed from the user's critical path.

The insight is that **a patch that has passed `tsc` is already useful to a human**, and it exists roughly a minute into the run. CI is a merge gate, not a display gate. So the interface delivers in stages:

```
t ≈ 0s     finding appears, with the affected call sites
t ≈ 15s    patch streaming in, live
t ≈ 60s    diff complete, typecheck green      <- user has a solution here
t ≈ 4-20m  CI green, pull request opened       <- merge gate resolves later
```

The user has something real at sixty seconds. The verification promise is unchanged: nothing is *merged* without a green CI run, and the pull request is not opened until it is. What changed is that the user stopped waiting on a gate that was never for them.

This is also why the workflow view renders live checkpointed graph state rather than a progress bar — a decision already recorded in the M4 information architecture. Streaming is consistently the highest-return latency technique available, because it changes what the user experiences without changing what the machine does.

**Nielsen's thresholds set the budget**: 0.1 s feels instantaneous, 1 s keeps a train of thought intact, 10 s is the limit of attention. Time-to-first-token above one second breaks flow. Our budget is therefore: finding visible within 1 s of a warm-path request, first patch token within 5 s, complete verified diff within 60 s.

---

## The cascade, done correctly

The intuition behind "cascading agents" is right; the mechanism is not one agent triggering another. It is **matching cost and latency to difficulty, and paying for the expensive tier only when the cheap one fails.**

### Tiered effort

Claude Opus 5 performs unusually well at `low` and `medium` effort — strongly enough that the expensive tier is wasted on mechanical work. Most API breaks are mechanical: a renamed field, a removed parameter, a moved argument.

```
tier 0   deterministic codemod        ~100 ms    no model call at all
tier 1   Opus 5, effort=low, fast     ~8 s       mechanical edits
tier 2   Opus 5, effort=xhigh         30s-5m     genuine reasoning
```

Escalation is driven by the verification gate, which is what makes it safe: a tier fails `tsc`, so the next tier takes over with the diagnostics attached. Correctness is never traded for speed, because the gate is the same at every tier. If tier 1 handles the common case — and it should — median latency is dominated by an eight-second call rather than a multi-minute one.

### Speculation

For findings where the tier is genuinely ambiguous, run tier 1 and tier 2 concurrently and take whichever verifies first, cancelling the loser. This spends tokens to buy latency, which is the correct trade when a human is waiting and the wrong one for a nightly batch. It is therefore a policy setting, not a default.

### What must stay sequential

Serialisation is not always waste. `locate → patch → verify` is a genuine data dependency: there is nothing to verify before a patch exists. Retry rounds are sequential by necessity, because each one consumes the previous one's diagnostics. Parallelising a data dependency does not produce speed, it produces a race.

---

## Claude-specific levers

These are concrete and measurable, and they apply directly to the patch node.

**Fast mode.** `speed: "fast"` with beta `fast-mode-2026-02-01`, on the beta messages endpoint, delivers up to 2.5× output tokens per second on Opus 5 at $10/$50 per MTok. It is a research preview on the first-party Claude API only — not Bedrock, Vertex, or Foundry — and draws on a separate rate-limit pool. This is the right setting for an interactive patch and the wrong one for a batch scan.

**Prompt caching, with a deliberate boundary.** A stable, anchored prefix cuts time-to-first-token by 30–60%. Opus 5's minimum cacheable prefix is 512 tokens, half of Opus 4.8, so our repository-context prefixes qualify easily.

The boundary placement is what matters, and getting it wrong is worse than not caching. Naive whole-context caching can *increase* latency. The correct arrangement for a retry loop:

```
[ cached ]  system prompt, tool definitions, repository context, call site
            ^ cache_control breakpoint here — byte-identical across retries
[ volatile] tsc diagnostics from the failed attempt
```

Diagnostics change on every round, so anything cached after them is invalidated every time. Verify with `usage.cache_read_input_tokens`; a persistent zero across retries means a silent invalidator sits in the prefix.

**Effort as the primary control.** `low` through `xhigh`, per the tier table above. It governs both latency and cost more directly than any other single parameter.

**Batch API for work nobody is waiting on.** Nightly vendor scans and full-fleet re-indexes belong in the Batches API at 50% cost. Interactive work never does.

---

## Sequencing

**None of this is in M0, and none of it should be.** M0's target is one verified pull request produced unattended. It runs one finding at a time against one repository, and its latency is irrelevant because nobody is waiting on it.

Building a parallel pipeline before a sequential one produces a correct result would mean optimising something not yet known to work. Worse, the fan-out reducer landmine is a class of bug that is far harder to diagnose when the underlying pipeline is also unproven.

| Milestone | Latency work |
|---|---|
| M0 | None. Instrument only: record per-stage timings so later claims are measured rather than asserted. |
| M1 | Lever 1 — parallel vendor and repository branches; `Send` fan-out across findings, with reducers and a fan-out test. |
| M2 | Lever 2 — incremental indexing on push webhooks; vendor diffs computed once and fanned out across customers. |
| M3 | The tier cascade and prompt-cache boundaries. |
| M4 | Lever 3 — staged delivery in the interface; speculation as a policy option. |

## The rule this document exists to enforce

**Every proposed agent must shorten the critical path or improve a result. An agent that does neither is latency and cost with extra steps.**

Concurrency is a means. The measurements at the top of this document are the judge, which is why M0 instruments before M1 optimises. A pipeline that is fast on a whiteboard and unmeasured in production is not fast.

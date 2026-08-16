# Sync — M8 to M11, the resolution loop

**Date:** 2026-08-06
**Status:** Proposed. Nothing scheduled, nothing started. Written now so the shape is settled
before it comes up.
**Source study:** [`references/notes/superlog-investigation-mechanism.md`](../references/notes/superlog-investigation-mechanism.md)
— the read this plan rests on, with the `path:line` citations for every claim below.
**Numbering:** M0–M6 are the design document's. M7 is the console. These take M8 onward.

## Why these four exist

Sync opens a verified pull request and stops. That is the whole product today, and it is a
narrower claim than "self-maintaining" makes.

Superlog's investigation pipeline was studied on 2026-08-06 down to the source, and it closes a
loop Sync leaves open. The parts worth taking are not its models or its prompts — those are
replaceable. They are four structural decisions, each of which Sync currently makes implicitly
and would benefit from making explicitly.

A note on where the study could and could not reach. Superlog's open-source repository carries
the entire orchestration — the runner contract, the run state machine, the outcome tool schemas,
the repository scoring, the chat lifecycle. It does **not** carry the runner implementation:
`infra/agent-runner/backend.ts` resolves the real runtime through
`await import(process.env.AGENT_RUNNER_ANTHROPIC_MODULE)`, an external module that ships with
their hosted product. Only a static `community` runner is open, and it calls no model.

That turned out to be the useful half. An implementation would have been one way of satisfying a
contract; the contract is the thing worth copying, and it is fully specified.

## The four, and the order

Ordered by what unblocks the most rather than by size. M8 is a seam with no product surface, and
everything below attaches to it.

| | Milestone | One sentence |
|---|---|---|
| **M8** | The runner seam | `sync.remediate` calls `claude_agent_sdk` directly; nothing can be substituted, faked, or replaced |
| **M9** | The outcome vocabulary | A run's outcome is a diff or an abandonment; there is no way to say "external cause" or "I need a human" |
| **M10** | Durable runs and the human turn | A run ends when the pull request opens, so nothing in Sync watches what happens to it |
| **M11** | Fan-in: many findings, one remediation | One vendor change across eight call sites is eight findings and eight pull requests |

M8 → M9 → M10 is a dependency chain. M11 needs M9 and is otherwise independent of M10.

---

## M8 — The runner seam

**What is wrong.** `sync/remediate/agent_patch.py` constructs `ClaudeAgentOptions` and calls
`query()` inline. The model, the prompt, the tool surface and the driving loop are one unit, so a
test that wants to assert what the pipeline does with a patch has to either call a real model or
monkeypatch a library. Neither is a seam.

**What to build.** A protocol in `sync.core.protocols` — the package that already holds
`RequestCorrelator` and imports nothing — naming what a runner must do. Superlog's version is ten
methods; Sync needs the four that matter for a batch pipeline: `start`, `collect`, `terminate`,
and a declaration of how many repository resources the runner can hold.

Two implementations ship with it. The existing Claude Agent SDK path, moved behind the protocol
unchanged. And a static one that returns a fixed result, which is what lets the pipeline's tests
run without a key — Superlog's `community` runner is exactly this, and its existence is why their
orchestration is testable at all.

**Why first.** It is pure refactor. No new product surface, no schema, no user-visible change, and
it is the only one of the four that can land without touching the graph.

**Evidence that closes it.** `sync.remediate` imports no model SDK. The remediation suite runs
green against the static runner with no network access.

---

## M9 — The outcome vocabulary

**What is wrong.** A remediation run produces a diff, or it abandons with an `abandon_reason`.
Those are the only two things it can say. A run that correctly concludes "the vendor's staging
environment is down, there is nothing to patch" has to abandon, and the abandonment is
indistinguishable from a failure to route.

**What to build.** A tool contract in two tiers, which is Superlog's shape:

- **Non-terminal:** `report_findings` — summary, root cause, confidence, estimated impact.
  Callable repeatedly; every call revises.
- **Terminal, one per run:** `propose_patch`, `report_external_cause`, `ask_human`, `abandon`.

Three implementation rules come with it, each of which Superlog learned the hard way and wrote
down in `agent-outcome-tools.ts`:

- **Flat schemas only.** No `oneOf`/`allOf` at the top level of a tool's input schema. Their
  comment: *"some runner APIs reject composition keywords at the top level of a custom tool's
  input_schema, and a rejected schema blocks every run at agent-create time."* A whole fleet
  fails at once, before any work starts.
- **Re-validate server-side, and write the error for the model.** The runner may not enforce the
  schema. Validation runs in the pipeline, and its error strings are addressed to the model,
  which sees them as tool errors and corrects within the same session. A rejected call is a
  retry, not a failed run.
- **Retired names get a redirect, not an unknown-tool error.** A parked run can resume after a
  deploy that removed a tool. Superlog keeps `RETIRED_OUTCOME_TOOL_NAMES` and error-acks those
  calls with guidance, because routing them to the unknown-tool path hard-fails the run.

**What Sync gains that Superlog does not have.** Sync already requires every binding to carry its
rung, and refuses an unattributed finding. Extend that discipline to the outcome: a confidence
integer with a written calibration rubric, and an evidence format requiring a `path:line` header
and a fenced quote. Superlog's rubric is worth copying nearly verbatim — 10 means every claim is
backed by a verbatim quote from a file read this session *and* the failure was reproduced; 4–6
means the code path is identified and the mechanism is a hypothesis.

**Evidence that closes it.** A run can report an external cause without abandoning, and the corpus
can distinguish the two. Every terminal outcome carries a confidence and at least one `path:line`
citation, enforced by validation rather than by review.

---

## M10 — Durable runs and the human turn

**What is wrong.** `sync run` opens a pull request and exits. Whether CI passed, whether a reviewer
asked for changes, whether it merged — none of it reaches Sync. Merge rate has never had a sample
partly because nothing is watching for one.

**What to build.** A run that parks instead of ending. Superlog's state machine is the reference:

```
queued → repo_discovery → running → { awaiting_human | awaiting_events | complete | failed }
                                          ↓ a human replies, or a PR event arrives
                                      resuming → running
```

`awaiting_events` is a run whose pull requests are out for review; the session stays durable and
PR events resume it. Their comment on `resuming` names the point: *"the heart of talking to an
investigation."*

Sync has the harder half already. LangGraph checkpoints in Postgres are a durable session store,
and `langgraph-checkpoint-postgres` is a declared dependency. What is missing is the parked states,
the event ingress (a GitHub webhook, which the forge is already authenticated for), and the rule
that a parked run is not ticked until something wakes it.

**Why this is the milestone that earns the product's name.** Everything before it makes a better
patch. This one closes the loop: a vendor breaks something, Sync patches it, CI rejects the patch,
and Sync fixes its own patch rather than leaving a stale branch and a red build.

**Evidence that closes it.** A run whose pull request receives a review comment resumes and pushes
a follow-up commit, without a human re-running anything. Abandoned and parked are distinguishable
in the corpus.

---

## M11 — Fan-in: many findings, one remediation

**What is wrong.** The grain is one finding per claim per call site. A vendor removing one field
that eight call sites read is eight findings, and today that is eight remediation runs and eight
pull requests against one repository, each with a fraction of the context.

**What to build.** A grouping layer above findings — Superlog calls it an Incident, and the
relationship is worth stating precisely because it is what makes their resolution tool work: many
Issues join one Incident, one investigation runs, and the terminal `resolve_incident` call carries
**exactly one outcome for every linked Issue**, each with its own status, reason and evidence,
applied atomically. Their description is the load-bearing sentence: *"If any entry is invalid,
nothing changes and the turn stays active."*

The `honey-jackal` incident studied on 2026-08-06 resolved eight issues in one call that way.

For Sync the grouping key is available without a model: findings sharing a `vendor_change_id`
against one repository are one unit of work. That is a stronger key than Superlog has — they need
an LLM to decide whether two exceptions are the same incident, and it is the step that fails when
no API key is configured.

**Evidence that closes it.** One vendor change across N call sites produces one pull request with
N edits and one resolution carrying N dispositions. The corpus records one attempt, not N.

---

## What is deliberately not here

**No console work.** Every one of these is pipeline. The console renders what the pipeline
produces, and M7 owns that.

**No chat surface.** Superlog has a Slack chat layer over durable sessions. M10 delivers the
durable session; whether a human talks to a run through Slack, the console, or a pull request
comment is a separate decision and probably a later one. Pull request comments are the cheapest
ingress and Sync is already authenticated for them.

**No repository scoring.** Superlog scores candidate repositories with a token heuristic because
it discovers repositories from a GitHub App installation and must guess which one an exception
came from. Sync is told which repository to work on. The one piece worth borrowing is their
instruction-file probe — they read `CLAUDE.md`, `AGENTS.md`, `.cursorrules` and
`.github/copilot-instructions.md` from the default branch so the agent follows the repository's
conventions — and that is already designed as `B126`, per-repository context.

## Sequencing against everything else

These sit behind M7. The console is the current focus and none of this is visible in it.

M8 is the cheapest and could be taken opportunistically — it is a refactor that makes the existing
remediation suite faster and key-free, and it pays for itself before any of M9 through M11 is
scheduled.

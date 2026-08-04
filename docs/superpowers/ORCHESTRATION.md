# Orchestration

How work is divided across agents on this project, and how a session picks up the lead without a
transcript. Read this before dispatching anything.

The governing rule is `.claude/rules/autonomous-development.md`: while executing a plan, decide and
continue. Everything here assumes it.

## The four kinds of agent, and what each is for

**The lead session.** One at a time. It holds a plan, dispatches its tasks, adjudicates review
findings, and records rulings in that plan's SDD ledger. It does not write implementation code
itself — a controller that fixes a finding by hand pollutes its own context and skips review. Its
scarce resource is context, so artifacts move as file paths rather than as pasted text.

**A second terminal agent.** Also a full session, in its own terminal, working a different stream —
the backlog, a different milestone, or the Python side while the lead holds the frontend. It is not
a subordinate: it plans and dispatches its own subagents. What the lead owes it is a clear boundary,
stated as directories rather than intentions.

**Subagents.** Dispatched per task by whichever session owns the plan. Fresh context every time,
carrying a brief file, a report file path, and the interfaces the brief cannot know. One implementer
at a time per worktree — two implementers in one tree is how a morning gets lost.

**Workflows.** A scripted fan-out for work that is wide rather than deep: auditing fifteen
references, sweeping a codebase for a pattern, reviewing along several dimensions at once. Use one
when the shape is known in advance and the parts do not depend on each other. Use subagents when the
next step depends on what the last one found.

**Cron ticks.** A repeating prompt that re-enters a loop on a schedule, so improvement does not
depend on somebody remembering. `docs/superpowers/loops/console-improvement-tick.md` is the console's.
Ticks are session-only in the current harness — they die with the session that scheduled them, which
is a real limit and not a detail.

## Cost and speed are the same lever, and it is not more agents

Both improve by spending less, so treat a request to go faster and a request to spend less as the
same instruction rather than as a trade-off.

**Measured on 2026-08-04.** A fourteen-agent workflow relaunched into an exhausted account limit
burned 618,000 tokens in seventy seconds and produced one usable note; twelve of its agents failed on
the same error. Nothing about that was fast. Width is the most expensive thing an orchestrator can
choose, and it is expensive whether or not it works.

**Model tier per role.** Defaulting everything to the most capable model is the other half of the
bill, and it is slower — a bigger model is not quicker at a mechanical diff, it is merely dearer.

| Role | Tier |
|---|---|
| Whole-branch review, architecture, a plan revision | the most capable model |
| Task review of a substantial diff | mid tier |
| Scoped re-review of a fix, a mechanical fix, a single-file change, a config edit | cheapest tier that can do it |
| An implementer transcribing code the plan already contains | cheapest tier |

Turn count beats token price. The cheapest model takes two or three times the turns on multi-step
work and costs more overall, so the floor for anything reasoning from prose is mid tier, not the
bottom.

**Width discipline.** Fan out only where the parts are genuinely independent and the shape is known
before dispatch. Four agents that each return something usable beat fourteen that mostly duplicate
each other's reading. Before launching a workflow, name what each agent will return that the others
cannot — if that sentence is hard to write for an agent, delete it.

**A tick is not a fan-out.** A scheduled loop exists to make small, steady progress. Cap it at two
subagents, never let it launch a workflow, and let it stop early: a tick that correctly does nothing
costs almost nothing, and a tick that starts work on top of another agent's uncommitted changes costs
a day. Space ticks widely enough that idle firings do not accumulate — hourly was too often while
work was blocked, and every firing still paid for the reading.

**Do not re-dispatch into a limit.** A resumed workflow re-runs its failed agents rather than
skipping them, so a resume during an outage pays the full price for the same failure twice.

## Reaching the other terminal

`orca terminal list --json` gives handles. Then:

```bash
orca terminal read --terminal <handle> --limit 25          # see its screen
orca terminal send --terminal <handle> --text "..." --enter # type into it
```

Reading first is not optional. A session can be mid-question with a half-typed answer already in its
input, and sending blind either submits somebody else's partial text or appends to it. If a question
is open, read the whole question before answering it — and if the answer is one of the three things
`.claude/rules/autonomous-development.md` reserves for the human, leave it alone rather than
answering on their behalf.

Messages sent while the other session is mid-turn are queued and picked up when it finishes. That is
the normal case, not a failure.

## The orchestration board, and why it is not used

`orca orchestration task-list` requires a bound run, and `run-use` refuses:

```
consumer_fenced — This adopted Run still has live legacy work.
legacy_read_only — Legacy takeover must be invoked by the live coordinator agent terminal it will bind.
```

The second message is the operative one. The CLI wants the identity of the terminal it is binding,
and a command issued through a tool call does not carry one — so the board cannot be bound from
inside an agent's tool use, only from a human typing into the terminal directly.

**So plan state lives in the SDD ledger, not on the board.** Each plan owns
`.superpowers/sdd/<plan-basename>/progress.md`, whose first line names its plan file. A task with a
`Task <N>: complete` line is done; a task whose last line is a fix round is mid-loop. The ledger
survives compaction, which is the property that matters — a session that loses its memory can
recover from the ledger and `git log`, and one that trusts its recollection instead has re-dispatched
whole completed sequences.

## Boundaries between concurrent sessions

State them as paths. Intentions are not enforceable and get misremembered.

The division in force while M4 is being built:

| Owner | Paths |
|---|---|
| Lead (M4 console) | `web/`, `docs/superpowers/plans/2026-07-30-sync-m4-dashboard.md`, the `sync-m4-dashboard` worktree |
| Second terminal | `src/`, `tests/`, `docs/superpowers/BACKLOG.md`, the main checkout |

Two habits keep this honest:

- **Read `main` before dispatching.** Both sessions push there. On 2026-08-04 the second terminal
  landed M4's HTTP transport (`8e6d3b0`) while the lead was still on Task 1; one `git log --oneline`
  was the only thing between that and dispatching a rebuild of work that already existed.
- **Commit path-limited when a subagent is live in your worktree.** `git commit -- <path>` takes only
  that path and leaves the implementer's staged work alone. A bare `git commit` sweeps it in.

## Handing work across the boundary

When a defect belongs to the other session's paths, do not fix it — describe it and hand it over.
A good handover says what is wrong, what proves it, where it lands, and how urgent it is. The
transport's `/api/overview` route omitting `context_savings` was found by the console consuming it
and fixed by the session that owns `src/sync/api/`, which is the shape to copy.

Say explicitly what you own while you are asking, so the other session does not reach into it while
answering.

## When the lead session ends

Leave three things behind, and a cold session will resume without a transcript:

1. The ledger current, with the last completed task naming its commit range.
2. Every parked finding and deferred minor written down with its ruling, so the final review sees
   both sides of a decision rather than only its outcome.
3. A note in `docs/superpowers/reports/` saying where the work stopped and what the next session
   should pick up first, in the order it should be picked up.

Name commits, never intentions. "Task 2 complete" is not resumable. "Task 2 complete (`8e6d3b0`,
landed on `main` by another session)" is.

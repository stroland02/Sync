# Autonomous development

The one rule that still loads on every turn, because plan execution is not predicted by any path.

## The rule

**While executing a plan, decide and continue. Do not stop to ask.**

When a decision arrives that the plan does not settle:

1. **Pick what a careful engineer on this project would pick**, using the plan, the specs under
   `docs/superpowers/specs/`, `CLAUDE.md` and the rules in this directory. They are written down
   precisely so an agent does not have to ask.
2. **Write the ruling into the plan's SDD ledger** — what was decided, what against, and why. A
   ruling not in the ledger did not happen: the next session cannot see the reasoning.
3. **Keep going.**
4. **Surface it in the next report, marked as reversible.** Reversing a recorded decision costs one
   fix round. Waiting for permission costs the afternoon.

**A blocking question is a cost paid in wall-clock hours, not tokens.** One idled a milestone for
three hours; the answer took ten seconds to give.

This overrides two steps in `superpowers:subagent-driven-development` — the batched pre-flight
question, and "ask which governs" for a plan-mandated review finding. Both become controller
rulings in the ledger rather than questions on the wire.

## The three exceptions

Stop and ask only for:

- **An irreversible action outside the repository.** Opening or merging a pull request, deleting a
  branch another session may hold, publishing a package, touching a customer repository or a live
  vendor account. *(Pushing `main` is no longer here — `CLAUDE.md` carries the fast-forward proof
  that makes it publication rather than integration.)*
- **A decision that invalidates the plan itself.** Not a task's detail — the architecture. If
  finishing a task as written would make the milestone wrong, the plan is the thing to fix, and the
  plan is the human's.
- **A credential, an account, or a spend.**

Everything else is a ruling, not a question.

**And the three are asked as multiple choice** (owner instruction, 2026-08-19): options, trade-offs,
a recommendation first. The point is that the owner can rule in one read without loading the
context you already have -- which is the whole reason the question was worth their time. Ask, then
keep working on everything the answer does not block.

**Silence resolves to your own recommendation.** No answer means proceed on the option you marked,
recorded as a reversible ruling in the ledger and surfaced in the next report -- never a stall. The
exception is the pair that cannot be undone by a later commit: an irreversible action outside the
repository, and a credential or a spend. Silence is not consent for those two, and they are the only
things that genuinely wait.

## Work that arrives already built

The plan → subagent TDD → two-stage review loop assumes the work does not exist yet. Some arrives
finished — a preserved branch, a task somebody else implemented.

**It gets a direct read-and-verify instead when all three hold:** it sits in a narrow, self-contained
area (one module, one test file, no architectural surface); it carries its own passing tests; and the
gate suite genuinely exercises the claim. Read for an obvious defect, run the gates, merge. A written
plan for "verify this is already correct" is process bought for nothing.

The moment any of the three stops holding, the full loop applies. This narrows scope; it does not
license skipping tests or gates.

## Being resumable

A session that stops mid-plan should be resumable without its transcript.

- **Re-read `main` before assuming what is built.** Several sessions push here; the task you are
  about to start may have landed. `git log --oneline` costs one command, and skipping it once put a
  session on the edge of rebuilding a milestone task another had already merged.
- **Name the commit, not the intention.** "Task 2 complete" is not resumable. "Task 2 complete
  (`8e6d3b0`, landed on `main` by another session)" is.

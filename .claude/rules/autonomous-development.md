# Autonomous development

Read this when executing a plan. It governs what an agent does when it meets a decision the plan
does not settle.

## The failure this exists to prevent

A plan execution paused for three hours because the controlling agent asked its human partner a
question and then waited for the answer. The question was real and the answer took ten seconds to
give — but the session was idle for three hours, and every task behind that question was idle
with it.

**A blocking question is a cost paid in wall-clock hours, not in tokens.** Price it that way.

## The rule

While executing a plan, decide and continue. Do not stop to ask.

When a decision arrives that the plan does not settle:

1. Pick what a careful engineer on this project would pick, using the plan, the specs under
   `docs/superpowers/specs/`, `CLAUDE.md`, and the other rules in this directory as the
   authorities. They are written down precisely so an agent does not have to ask.
2. Write the ruling into the plan's SDD ledger: what was decided, what it was decided against,
   and why. A ruling that is not in the ledger did not happen — the next session cannot see the
   reasoning, and a reviewer cannot check it.
3. Keep going.
4. Surface the ruling in the session's next report, marked as a decision the human can reverse.
   Reversing a recorded decision costs one fix round. Waiting for permission costs hours.

This overrides two steps in `superpowers:subagent-driven-development`: the batched question its
pre-flight scan asks before execution, and the "ask which governs" step for a plan-mandated
review finding. Both still happen — as controller rulings in the ledger, not as questions on the
wire.

## The three exceptions

Stop and ask only for:

- **An irreversible action outside the repository.** Pushing to `main`, opening or merging a pull
  request, deleting a branch another session may hold, publishing a package, touching a customer
  repository or a live vendor account.
- **A decision that invalidates the plan itself.** Not a task's detail — the plan's architecture.
  If finishing a task as written would make the milestone wrong, the plan is the thing to fix, and
  the plan is the human's.
- **A credential, an account, or a spend.** Anything needing an authorization the agent does not
  hold.

Everything else is a ruling, not a question.

## Being a good ancestor to the next session

A session that stops mid-plan should be resumable without its transcript. That is what the ledger
is for, and it is why rulings belong there rather than in chat. Two habits carry most of it:

- **Re-read `main` before assuming what is built.** Several sessions push to this repository, and
  the task you are about to start may already have landed. `git log --oneline` against `main`
  costs one command; skipping it once put a session on the edge of rebuilding a milestone task
  another session had already merged.
- **Name the commit, not the intention.** "Task 2 complete" is not resumable. "Task 2 complete
  (`8e6d3b0`, landed on `main` by another session)" is.

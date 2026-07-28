# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

## Ready

### B1 — A patch that needs a new file abandons instead of shipping one
`push_branch` stages with `git add -u`, which never stages an untracked path, and the
gate now measures the same tree — so a fix requiring a new module fails verification
rather than pushing a branch missing it. Truthful, useless. `git add -A` was rejected
because it commits whatever else the agent left behind: a build directory, a log, a
stray install. The unsolved part is separating a new source file the patch needs from
that debris. The patch agent can already stage a file itself, since anything in the
index is both verified and committed, but its scope rules still tell it only to run
`npx tsc --noEmit` until clean — an instruction that now names a different tree from
the one the gate measures.
**Closes when:** a finding whose fix requires a new file produces a branch containing
that file, and a run where the agent leaves debris behind still does not commit the
debris. Both proven against a real clone.

### B2 — The authorship check reads only the branch tip
`push_branch` refuses a tip Sync did not author, which stops the common case of a
reviewer pushing a fixup. A stranger's commit sitting *beneath* a later Sync-authored
one is invisible to it and would still be replaced. Walking the range from the merge
base to the tip closes it.
**Closes when:** a branch whose history contains any non-Sync author between the merge
base and the tip refuses the push, with that commit intact afterwards. Note this is
not a security control — `git commit --author` sets the field freely — so do not
describe it as one.

### B3 — The static gate cannot see inside `node_modules`
`static_verify` holds untracked and ignored paths out of the clone before compiling, so
its verdict describes the branch `push_branch` creates. Installed dependencies are the
exception, because the customer's CI installs its own. An agent that edits a type
declaration inside `node_modules` therefore satisfies a gate the customer's CI will not.
Typechecking a second pristine checkout closes it, at the cost of a checkout and a
dependency install per verification — three per finding at the current retry budget,
the largest avoidable cost in the pipeline.
**Closes when:** an edit inside `node_modules` fails verification, and the added
wall-clock cost per finding is measured and stated rather than estimated.

### B4 — LangGraph will stop serialising `sync.core` types
The checkpointer warns that msgpack serialisation of `sync.core.models` types "will be
blocked in a future version". Today it degrades to pickle; when it stops, every
resumable run breaks at once and the failure lands on the durability guarantee that
justified choosing LangGraph.
**Closes when:** the types are registered explicitly, the warning is gone, and a run
checkpoints and resumes across a process restart.

## In flight

_(none)_

## Done

- Derive the SDK verb from `spec3.sdk.json`'s `x-stableId` rather than the URL shape.
  Landed `b289a9e`. Coverage unmoved at 105 of 414; one symbol corrected.
- Refuse a push lease against a tip Sync did not author; delete the branch an abandoned
  finding leaves behind. Landed `38ec2c7` and wired at `9627f65`.
- Run the tier cascade and give it the change class the acceptance run hit.

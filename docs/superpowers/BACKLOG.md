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

### B2 — done, see Done below

_Superseded._ Original text kept out of the Ready list deliberately; the closing evidence is
recorded in the design document's limitations section.

<!-- former B2 —
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

### B5 — The suite is subprocess-bound, and Postgres was never the cause

**Measured, and it refutes what both coordinators assumed.** The slowdown is not database
contention. Numbers from `main` at `9b13cce`, 757 tests, 121s total:

| | tests | time |
|---|---|---|
| `test_github_forge.py`, `test_tsc_verify.py`, `test_cli.py` | 121 | **95.5s** |
| everything else | 636 | 29.6s |
| `test_graph_store.py` (the Postgres-heaviest file) | 19 | 4.2s |

Three files holding 16% of the tests carry 79% of the wall clock, and every slow test in
them spawns a real `git` or `tsc` process. Postgres showed 2 connections with 1 active
while six workers were running; the server is idle. The 77s-to-122s growth tracks tests
being added — B2 alone added seven bare-remote git tests at roughly 3s each.

So this is not a regression to fix, it is a cost to decide about. `pytest-xdist` is not
installed and the machine has 12 cores; subprocess-bound tests parallelise almost
perfectly, so `-n auto` is the obvious lever and nobody has measured it.

Unrelated but found while measuring: 24 `sync*` databases exist on the server. I first
recorded this as a silent leak in `conftest`. **That was wrong** — 21 of them are the
per-worker databases our own briefs hand out (`sync_w1`…`sync_w19`, `sync_b2`, `sync_b4`),
and `pytest_configure` returns early whenever `SYNC_DSN` is set, so it never creates or
drops those by design. Only three are `sync_test_<pid>` databases from runs killed before
`pytest_unconfigure`, and `conftest` already drops-before-create on pid reuse, so those are
self-healing and bounded by the pid space. There is no bug here. What there is: nobody
drops a worker's database when its task finishes.

**Closes when:** someone measures `-n auto` against the current suite and either adopts it
with the number stated, or records why it does not work here (the bare-remote and clone
fixtures may not be parallel-safe — that is the thing to check, not assume). The worker
databases are housekeeping rather than a fix — a finished task's database can be dropped,
and the only care needed is not dropping one a live worker is still pointed at.

## In flight

- **B3** — `task_b233d7d7237d`, dispatched to `m2-symbols`. Its brief
  proposes a cheaper closure than the second checkout and explicitly asks the worker to
  argue with that proposal rather than accept it.
- **B1** — `task_627dab9b3617`, dispatched to `m1-forge` now that B2 has landed. Told not to
  edit `src/sync/index/`, which B3 holds; if it concludes `shipped_tree` must change, it
  reports the change rather than making it.

## Done

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

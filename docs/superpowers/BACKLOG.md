# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

## Ready

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

### B6 — A clone contaminated by a dependency edit outlives the finding that abandoned

`static_verify` now refuses a patch that edited an installed dependency, and the finding
abandons. The edit stays in the clone: `_reset_clone` returns the tree to the commit it was
cloned at but keeps ignored files, and `node_modules` is ignored. So the doctored
declaration is still there for the next finding processed against that clone, which either
meets a compiler lying in the same direction or abandons on an edit it did not make.

Raised by B3's worker, which deliberately did not close it because the fix is a policy
choice rather than a mechanism: quarantine the clone and re-clone for the next finding, or
force a dependency reinstall measured in minutes, or narrow `_reset_clone` to restore only
the dependency directories. Each trades correctness against the pipeline's largest cost,
which is why it is not a worker's call to make alone.

**Closes when:** a run that abandons on a dependency edit leaves no clone that a later
finding can be verified against in its contaminated state, and the wall-clock cost of
whichever route is chosen is measured and stated rather than estimated. Note the second
finding is the one that matters — a test proving the first finding abandons proves nothing
about the contamination surviving it.

## In flight

- **B5** — `task_365c23bf0920`, worktree `m1-forge`. Owns `pyproject.toml`, `tests/conftest.py`
  and test files; forbidden from touching `src/`. A measured "not worth it" is an acceptable
  result and the brief says so.
- **B6** — `task_63bec222ec75`, worktree `m2-symbols`. Owns `src/sync/index/`. Four routes are
  named with their trade-offs; choosing and defending one is the task.

## Done

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

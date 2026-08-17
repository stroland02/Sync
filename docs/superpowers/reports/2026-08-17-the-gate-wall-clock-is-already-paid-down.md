# The gate wall-clock, measured

**2026-08-17, Lane C, `CI-W363`.** The charter's queue item 4 says the full suite is "eight to
fourteen minutes and every lane pays it on every iteration. That is the single largest tax on this
whole workspace."

**Measured today across eight runs on this host: 152–230 seconds.** The tax was real and it has
already been paid, by `CI-W287` (1215/1741/3270s → 233s) and by the `-n 4` → `-n auto` switch. The
figure in the charter is roughly four times the truth, and it is worth correcting because five lanes
plan against it.

## The runs

All `uv run pytest tests/ -q -n auto` from `C:/Users/strol/orca/workspaces/Sync/lane-c-pipeline`,
against a host running six concurrent agent sessions.

| Run | Wall clock | Result |
|---|---|---|
| 1 | 211.50s | 3989 passed |
| 2 | 152.20s | 2 failed (the `B183` reproduction) |
| 3 | 168.61s | 3990 passed |
| 4 | 183.01s | 3990 passed |
| 5 | 183.49s | 3992 passed |
| 6 | 230.38s | 3995 passed |
| 7 | 161.13s | 3999 passed |
| 8 | 167.15s | 3999 passed |

Median about 175s for roughly 4000 tests. The spread is host load from the other five sessions, not
the suite.

## Why there is no single fix left, and this is the part that decides the item

`os.cpu_count()` is 12, so `-n auto` runs twelve workers. At 167s wall clock that is roughly **2000
CPU-seconds** of work. The slowest single test is 35.64s.

**The suite is throughput-bound, not latency-bound.** Makespan approaches the longest single test
only once parallelism is ample; here 167s is far above 35.6s, so wall clock is set by total work
divided by workers. The consequence is arithmetic: the twenty-five slowest tests together account
for about 400s, a fifth of the total, and the remaining 3974 tests carry the other 1600s. Removing
the single worst test entirely would return about 3s of wall clock — under 2 percent.

So there is no hotspot to attack. A meaningful further cut would have to come from the long tail,
which is thousands of tests each costing milliseconds, and that is a rewrite of how the suite talks
to Postgres rather than an optimisation.

## The twenty-five slowest, so a future pass does not have to re-measure

```
35.64s  test_red_run_capture.py::test_a_red_run_is_kept_and_the_next_green_run_does_not_take_it
25.05s  test_patch_sandbox.py::test_never_networked_container_receives_nothing_after_...
24.83s  test_pipeline_composes.py::test_this_hand_composed_driver_writes_no_row_that_...
23.61s  test_pipeline_composes.py::test_no_run_here_ever_reaches_a_forge
20.14s  test_leaked_database_sweep.py::test_a_server_that_cannot_be_reached_is_not_an_error
19.73s  test_isolated_network.py::test_a_container_on_an_isolated_network_cannot_reach_the_internet
19.50s  test_remediation_graph.py::test_a_patch_that_only_typechecks_with_untracked_files_...
18.06s  test_gate_dev_loop.py::test_nothing_is_started_when_a_precondition_is_missing
17.89s  test_gate_dev_loop.py::test_a_missing_precondition_is_named_with_the_command_that_fixes_it
17.44s  test_sandbox_image.py::test_ensure_image_built_builds_on_miss_then_is_a_no_op_on_repeat_call
```

The rest are 15s and below. The shape is consistent: every one of them either drives a real
container, a real child pytest, a real `tsc`, or a real Postgres. **None of them is slow because it
sleeps.** That is the difference between a suite that is slow and a suite that is doing work, and it
is why this item closes as measured rather than as optimised.

## One deliberate non-fix

`test_a_server_that_cannot_be_reached_is_not_an_error` spends 20.14s proving that an unreachable
server returns `[]` rather than raising. That is two `ADMIN_CONNECT_TIMEOUT_SECONDS` waits of 10s
each, and 10s is the production-correct value — the bound exists so a starved admin connection
cannot hang the gate, which is `B132`'s whole subject.

Making the test faster means adding a connect-timeout parameter to `admin_connection` and threading
it through `sweep_leaked_databases`, for one test's convenience. `CLAUDE.md` calls that debt with no
asset behind it: an abstraction added for an anticipated caller that does not exist. It buys 20 of
2000 CPU-seconds, which is 1 percent of a suite that is not the constraint. **Left alone on purpose,
and recorded here so the next person to notice it does not re-derive the same conclusion.**

## What this means for the charter

Two sentences in `docs/superpowers/orchestration/2026-08-17-lane-charters.md` are now wrong, and
that file is the coordinator's rather than this lane's, so they are reported rather than edited:

- Queue item 4's "eight to fourteen minutes" should read about three minutes.
- "That is the single largest tax on this whole workspace" no longer holds. At roughly 175s a run,
  the gate is no longer the largest cost any lane pays.

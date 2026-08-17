# B183: the B97 positive controls, and a deadline anchored to the wrong event

**2026-08-17, Lane C, `CI-W360`.** Both of B97's positive controls passed alone and failed inside a
full `-n auto` run. The cause is named below with the measurement that names it, and it is none of
the three things the entry listed as candidates.

## What it was

The container's exfiltration process **connected in 0.022 seconds** and sent continuously. The
host-side listener never heard it, because its `accept()` had already raised `TimeoutError`.

```
seconds since listener started: 11.359   (accept timeout is 10s)
accept_error: "TimeoutError('timed out')"
accepted_at: None
bytes: 0
--- /tmp/exfil.log ---
connected 192.168.65.254 after 0.022s
```

`_start_attacker_listener` began a ten-second deadline the moment it bound its socket. Between that
moment and the container being able to connect, the test itself performs five serialized Docker
daemon round-trips — `create`, `start`, `exec` to resolve the host name, `exec` to read
`/proc/net/route`, and `exec -d` to start the exfiltration. Under a full `-n auto` run those took
11.359s, and the budget was gone before the thing it was budgeting for could begin.

**So the defect is the anchor, not the load.** A deadline was measured from the wrong event. Load
only decided whether the anchor's error was large enough to show, which is exactly why this
reproduced under `-n auto` and never alone.

The same error sat in a second, smaller place: the controls slept a fixed 0.5s and then asked
whether a byte had arrived. That asserts a latency budget while appearing to assert that data flows.

## What it was not, and how each was eliminated

The entry named three candidates and warned against assuming contention, because `CI-W280` closed a
near-identical symptom whose real cause was `host.docker.internal` not resolving on Linux. That
warning was right and the framing it warned against would have been wrong again.

- **Container-name collision — eliminated from the source.** `ephemeral_container` names containers
  `f"sync-patch-sandbox-{uuid.uuid4().hex[:12]}"` (`src/sync/remediate/sandbox.py:194`). Two
  concurrent tests cannot collide.
- **The leaked nine-hour container — eliminated by measurement.** `sync-patch-sandbox-f3def5d5859c`
  was up on the default bridge at `172.17.0.2` throughout a full suite run that passed **3989 passed,
  4 skipped**. A cause that is present during a clean pass is not the cause.
- **`CI-W280`'s cause — eliminated by the evidence.** `host.docker.internal` resolved correctly, to
  Docker Desktop's `192.168.65.254`, and the connection succeeded in 22ms. The network was never
  involved.
- **Daemon contention — real, and not the defect.** `docker version` measured 432–2552ms under suite
  load against roughly 100–200ms idle. That is what made the setup take 11.359s. It is the trigger;
  the ten-second deadline starting in the wrong place is the bug.

## The fix

Both in `tests/test_patch_sandbox.py`. Nothing in `src/sync/remediate/` is touched: the module under
test was never at fault, and this is the harness measuring itself badly.

- The listener does not start its accept deadline until `_exfiltrate_in_background` arms it, so the
  budget covers "the container connects" and not "the daemon got round to us". Waiting is safe
  because `listen()` has already been called, so a connection made before `accept()` runs waits in
  the backlog rather than being refused.
- The positive controls wait for a byte to arrive instead of sleeping a fixed interval and asking
  afterwards.
- A failing control now prints the container's own account of what it did. "Connected in 0.022s and
  sent continuously" and "never connected at all" are the two outcomes that matter, and a byte count
  of zero cannot tell them apart. Not having that distinction is most of why this entry stayed open.

## Before and after

All from `C:/Users/strol/orca/workspaces/Sync/lane-c-pipeline`, this lane's own worktree.

| | Result |
|---|---|
| Before, full `-n auto` | **2 failed**, 3987 passed, 4 skipped, 152.20s |
| After, full `-n auto` | **3990 passed**, 4 skipped, 0 failed, 168.61s |
| `tests/test_patch_sandbox.py` alone | 9 passed in 16.46s (was 8; the ninth is the regression test) |

The count rises by three rather than by one because the two controls stopped failing and the
regression test is new.

A second measurement worth keeping, because it is what made the setup expensive enough to matter:
`docker version` alone took **432–2552ms** while the suite ran, against roughly 100–200ms idle. That
is a property of this host under six concurrent sessions, not of the change.

## The regression test, and why it needs no Docker

`test_the_listener_waits_from_the_moment_exfiltration_starts_not_from_the_bind` pins the anchor with
a plain loopback socket and a delay standing in for the setup. It fails against the old code with
`accept_error="TimeoutError('timed out')"` — the same error the real failure produced — and passes
against the new code in 2.17s.

A test that needed a loaded daemon in order to fail would be the same unreadable thing this entry is
about. The defect is in the harness's own timing, so it is pinned as timing.

**The controls were proven still able to fail.** Pointing the exfiltration at `10.255.255.1`, which
nothing answers, turns the control red with `failed 10.255.255.1 after 5.035s` and `no candidate
connected`. A positive control that could no longer fail would have replaced an unreadable boundary
claim with a false one.

## One thing found next door and deliberately not changed

`tests/conftest.py` skips every `docker`-marked test when `docker_unavailable_reason()` answers, and
that probe's budget is `DOCKER_PROBE_TIMEOUT_SECONDS = 30`. Measured against the 2552ms this run saw
under load there is ample headroom, so nothing is wrong today — but the probe runs once per xdist
worker at collection, which puts sixteen `docker version` calls on the daemon at the same instant,
and the failure mode if it ever did expire is a **silent mass skip** of exactly the tests that carry
B97's boundary claim. Filed as `B184` rather than pre-emptively widened: a workaround with no
measurement behind it is the thing this report is about.

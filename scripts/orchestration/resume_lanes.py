"""Re-dispatch any lane whose worker has stopped, so the development loop survives a dead session.

Six agents develop this repository continuously. Every one of them, including the coordinator, will
eventually stop mid-loop -- a token budget runs out, a session is closed, a runtime drops a
connection. When that happens the lane goes quiet and nothing notices, because the thing that would
have noticed is the session that died.

This script is what notices. It is idempotent, it takes no arguments in its normal form, and it can
be run by anything: a scheduled task, another agent, or a person typing it. Run it and any lane that
has stopped is dispatched again against its own terminal; a lane that is genuinely working is left
alone.

**It never creates work.** It re-attaches an existing Task to an existing terminal. If a Task has
been completed, this script has nothing to do for that lane and says so -- deciding what a lane
should do next is a coordinator judgement, and a script that invented one would quietly turn a
finished milestone into busywork.

Why the checks are what they are
--------------------------------
A dispatch with no assignee never reached a terminal, whatever its status says: `worker-start` waits
for the agent's TUI to go idle and gives up after a minute, and a busy agent is the normal reason.
That is the single most common stall here and it is invisible from the task list alone, which shows
`dispatched`.

A dispatch whose assignee handle no longer appears in `terminal list` lost its terminal. A dispatch
whose terminal has produced no output for longer than the silence threshold has either finished
without reporting -- which has happened, and a coordinator blocking on the mailbox would wait forever
-- or has stopped. Both are re-dispatchable; re-dispatching a worker that was merely thinking costs
one interrupted turn, and leaving a dead lane costs the rest of the day.

`--dry-run` prints the verdict for every lane and changes nothing, which is the right first call when
you are not sure what state the workspace is in.
"""

from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# A worker that has emitted nothing for this long is treated as stopped rather than thinking. Ten
# minutes is above the longest observed quiet stretch inside a real task here (a full `pytest -n auto`
# run is eight to fourteen minutes but streams output throughout) and well below the cost of leaving
# a lane dead.
DEFAULT_SILENCE_MINUTES = 10

# Which terminal each lane belongs to, for the case a dispatch never recorded one. A dispatch
# stores its assignee only once `worker-start` succeeds, and the most common stall is that it
# never did -- so precisely the lanes that most need resuming are the ones with no handle on
# them. The coordinator writes this map beside the script; it is read next to the script rather
# than from a repository path, because this script is installed outside any worktree so that it
# survives one being deleted.
LANE_TERMINALS = Path(__file__).resolve().parent / "lane_terminals.json"

# An agent out of budget cannot answer, and retrying it is worse than doing nothing: Orca
# circuit-breaks a task after three consecutive dispatch failures, so a sweep running every
# twenty minutes would permanently fail a healthy lane about an hour into an outage that
# resolves itself. Measured 2026-08-17, when two lanes hit their limit at once with a two-hour
# reset ahead of them. These are the substrings the agent CLIs print when they stop for budget.
BUDGET_EXHAUSTED = (
    "hit your session limit",
    "usage limit",
    "rate limit",
    "quota exceeded",
    "quota reached",          # Gemini's wording; "exceeded" alone missed a real outage
    "upgrade your subscription",
    "insufficient credit",
)

_WINDOWS_INSTALL = Path(
    os.environ.get("LOCALAPPDATA", "")
) / "Programs" / "orca" / "resources" / "bin" / "orca"


def resolve_cli() -> str:
    """The Orca executable, by the skill's own precedence rules.

    Never bare `orca` on Linux outside an Orca terminal: there it normally resolves to the GNOME
    Orca screen reader and starts speech on the user's machine.
    """
    explicit = os.environ.get("ORCA_CLI_COMMAND")
    if explicit:
        return explicit
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev"
    if _WINDOWS_INSTALL.exists():
        return str(_WINDOWS_INSTALL)
    if sys.platform.startswith("linux"):
        return "orca-ide"
    found = shutil.which("orca")
    if found is None:
        raise SystemExit("no Orca CLI found; set ORCA_CLI_COMMAND")
    return found


def call(cli: str, *args: str) -> dict:
    """One Orca RPC, decoded.

    `encoding="utf-8"` and `PYTHONIOENCODING` both, because on Windows the parent's decode setting
    says how to read the bytes and not which bytes the child chooses to emit. A decode error here is
    raised on the reader thread and never propagates: the call returns with `stdout` set to `None`
    and the next line that touches it raises somewhere unrelated.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [cli, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if not result.stdout:
        return {"ok": False, "error": {"message": (result.stderr or "").strip()[:400]}}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": result.stdout.strip()[:400]}}


def live_terminals(cli: str) -> dict[str, int]:
    """Every connected terminal handle, with the epoch-millis of its last output."""
    payload = call(cli, "terminal", "list", "--json")
    terminals = (payload.get("result") or {}).get("terminals") or []
    return {
        t["handle"]: t.get("lastOutputAt") or 0
        for t in terminals
        if t.get("connected") and not t.get("orphaned")
    }


# How close to the end of the tail a budget notice must sit to still count. A recovered agent
# pushes its banner up the scrollback as it produces output, so a notice buried further back than
# this is history rather than a live state -- without the bound, one exhausted afternoon would hold
# a healthy lane for as long as the banner stayed in the buffer.
BUDGET_NOTICE_WITHIN_LAST = 6


def reset_seconds(notice: str) -> int | None:
    """How long the agent said its outage would last, in seconds, or `None` if it did not say.

    Reads the `Resets in 2h3m21s` / `resets 10:20am` shapes the agent CLIs print. Only the
    duration form is parseable into a deadline; a wall-clock time would need the machine's timezone
    to mean anything, and guessing that is how a hold ends an hour early.
    """
    match = re.search(r"resets?\s+in\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?", notice, re.I)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


HOLD_CLOCK = Path(__file__).resolve().parent / "hold_clock.json"


def hold_elapsed(path: Path, task_id: str, notice: str, now: int) -> int:
    """Seconds since *this* notice was first seen, remembering across sweeps.

    A hold's remaining time cannot be measured from the terminal's last-output timestamp. Those
    agree only while the notice is the last thing the agent printed *and* Orca's timestamp is
    tracking, and on 2026-08-17 neither held: Lane D reported 23 minutes of silence while carrying a
    `Resets in 17m34s` banner printed seconds earlier. The sweep compared a new window against an old
    clock, called the hold expired, and retried straight into the same wall -- and the pass after
    that reported the lane STALE, which is the classification that invites an interrupt.

    So a *changed* notice restarts the clock: a fresh banner is proof the last retry already failed.
    """
    state: dict = {}
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # The safety net exists to run when nobody is watching, so it never dies on its own
            # state file. A corrupt clock costs one held lane one extra window, not the sweep.
            state = {}

    entry = state.get(task_id)
    if not isinstance(entry, dict) or entry.get("notice") != notice:
        entry = {"notice": notice, "seen_at": now}
        state[task_id] = entry
        path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        return 0
    return max(0, now - int(entry.get("seen_at", now)))


def budget_held(cli: str, handle: str, silent: bool = False) -> str | None:
    """The reset notice on a terminal that has stopped for budget, or `None`.

    Read from the terminal's own tail rather than inferred from silence, because silence is
    ambiguous -- a thinking agent and an exhausted one look identical from the outside, and only
    one of them should be left alone.

    While the terminal is still producing output, only the last few lines are examined: a banner
    further back means the agent has written since, which is proof it recovered.

    `silent` lifts that bound, and it has to. An outage that lands mid-tool-call leaves the agent's
    own chrome drawn *underneath* the banner -- an in-flight tool line, a permissions footer, a
    prompt -- and none of it is new output. The banner leaves the window pushed by furniture rather
    than by writing, and the lane reads as dead. Measured on Lane E, 2026-08-17: fifty-five minutes
    classified STALE, and the interrupt sent to unwedge it ended the session. When the tail has not
    moved, everything in it describes now.
    """
    payload = call(cli, "terminal", "read", "--terminal", handle, "--json")
    terminal = (payload.get("result") or {}).get("terminal") or {}
    lines = terminal.get("tail") or []
    recent = lines if silent else lines[-BUDGET_NOTICE_WITHIN_LAST:]
    tail = " ".join(recent).lower()
    if not any(marker in tail for marker in BUDGET_EXHAUSTED):
        return None
    # Only a line that ALSO carries a budget marker may supply the reset time. Measured 2026-08-18:
    # the coordinator queued work into two held terminals with the word "resets" in it -- "start here
    # the moment your quota resets" -- and the scan, reading newest-first, returned that sentence as
    # the notice. `reset_seconds` then found no duration, so the hold had no deadline and could never
    # expire. **A tail contains whatever anybody typed into it**, so a marker-free line matching one
    # keyword is not evidence of anything.
    for line in reversed(recent):
        lowered = line.lower()
        if "resets" in lowered and any(marker in lowered for marker in BUDGET_EXHAUSTED):
            # ASCII-folded before it is ever printed. A terminal tail carries box-drawing and
            # spinner glyphs, and stdout on this machine is cp1252, so returning the raw line
            # crashes the sweep on the one path that exists for an outage -- the failure would
            # arrive precisely when nobody is watching and the lane most needs to be held.
            folded = "".join(c if 32 <= ord(c) < 127 else " " for c in line)
            return " ".join(folded.split())[:120]
    return "no reset time printed"


def recorded_run(cli: str) -> str | None:
    """The Run to sweep, named explicitly rather than inherited from a terminal binding.

    **This is what made the scheduled task inert.** `orchestration task-list` answers for the Run
    bound to the invoking terminal, and a Windows scheduled task is not an Orca terminal, so it has
    no binding and sees no tasks. The sweep then printed "no open lane tasks; nothing to resume" and
    exited zero -- healthy-looking, and wrong, three times in a row while five lanes were open. A
    safety net that reports success while doing nothing is worse than one that fails loudly.

    The coordinator records the Run id beside the terminal map. Absent that, the newest Run is a
    reasonable guess and is stated as one.
    """
    if LANE_TERMINALS.exists():
        try:
            recorded = json.loads(LANE_TERMINALS.read_text(encoding="utf-8")).get("_run")
        except (json.JSONDecodeError, OSError):
            recorded = None
        if isinstance(recorded, str) and recorded.startswith("run_"):
            return recorded

    runs = (call(cli, "orchestration", "run-list", "--json").get("result") or {}).get("runs") or []
    if not runs:
        return None
    newest = runs[-1]
    print(f"note: no Run recorded beside this script; guessing the newest, {newest.get('id')}")
    return newest.get("id")


def recorded_terminals() -> dict[str, str]:
    """The coordinator's task-to-terminal map, or empty when it is absent.

    Absent is a legitimate state -- the map is an aid, not a requirement -- so a missing or
    unreadable file degrades to "no fallback placement" rather than stopping the sweep.
    """
    if not LANE_TERMINALS.exists():
        return {}
    try:
        loaded = json.loads(LANE_TERMINALS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: v for k, v in loaded.items() if k.startswith("task_") and isinstance(v, str)}


def lane_name(spec: str) -> str:
    """The lane label out of a task spec, for a log line a human can scan."""
    head = (spec or "").strip().split(".")[0]
    return head[:60] if head else "unnamed task"


def verdict(
    dispatch: dict,
    terminals: dict[str, int],
    silence_ms: int,
    fallback_handle: str | None = None,
) -> tuple[bool, str]:
    """Whether this lane needs re-dispatching, and the reason to print either way.

    **A lane is stalled when its agent has stopped, not when Orca's record of it went bad**, and the
    two come apart constantly: `worker-start` gives up after about a minute waiting for a busy TUI
    and marks the dispatch failed while the agent it was attaching to works straight through.
    Measured 2026-08-17 -- Lane C spent six minutes inside one `npm install` while every sweep read
    its dispatch as failed and created another retry dispatch against a lane that needed nothing.

    So a bad record is checked against the terminal before it is believed. The terminal is evidence;
    the record is a hypothesis. `fallback_handle` is the lane's recorded terminal from
    `lane_terminals.json`, which is the only handle available when the dispatch never carried one.
    """
    status = dispatch.get("status")
    assignee = dispatch.get("assignee_handle")
    record_is_bad = status in {"failed", "stopped"} or not assignee

    if record_is_bad:
        handle = assignee or fallback_handle
        # No terminal to check is not evidence of health: without one the record is all there is.
        if handle and handle in terminals:
            quiet_ms = int(time.time() * 1000) - terminals[handle]
            if quiet_ms <= silence_ms:
                return False, f"working ({quiet_ms // 1000}s since last output, despite the record)"
        if status in {"failed", "stopped"}:
            return True, f"dispatch {status} ({dispatch.get('last_failure') or 'no reason recorded'})"
        return True, f"never attached to a terminal (status {status})"

    if assignee not in terminals:
        return True, "assigned terminal is gone"

    quiet_ms = int(time.time() * 1000) - terminals[assignee]
    if quiet_ms > silence_ms:
        return True, f"silent for {quiet_ms // 60000} minutes"
    return False, f"working ({quiet_ms // 1000}s since last output)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report verdicts, change nothing")
    parser.add_argument(
        "--silence-minutes",
        type=int,
        default=DEFAULT_SILENCE_MINUTES,
        help="treat a worker quiet this long as stopped",
    )
    args = parser.parse_args()

    cli = resolve_cli()
    status = call(cli, "status", "--json")
    if not status.get("ok"):
        print("orca runtime unreachable; nothing to resume")
        return 1

    run_id = recorded_run(cli)
    listing = ["orchestration", "task-list", "--json"]
    if run_id:
        listing = ["orchestration", "task-list", "--run", run_id, "--json"]
    tasks = (call(cli, *listing).get("result") or {}).get("tasks") or []
    if not tasks and run_id is None:
        print("no Run could be resolved; this sweep saw nothing and that is a failure, not a quiet "
              "workspace -- record a _run key beside this script")
        return 1
    open_tasks = [t for t in tasks if t.get("status") not in {"completed"}]
    if not open_tasks:
        print("no open lane tasks; nothing to resume")
        return 0

    terminals = live_terminals(cli)
    recorded = recorded_terminals()
    silence_ms = args.silence_minutes * 60 * 1000
    restarted = 0

    for task in open_tasks:
        shown = call(cli, "orchestration", "dispatch-show", "--task", task["id"], "--json")
        dispatch = (shown.get("result") or {}).get("dispatch") or {}
        needs, why = verdict(dispatch, terminals, silence_ms, recorded.get(task["id"]))
        label = f"{task['id']} [{lane_name(task.get('spec', ''))}]"

        if not needs:
            print(f"OK      {label}: {why}")
            continue

        # Asked before the dry-run branch on purpose: a dry run has to report the verdict a real
        # run would reach, or it is not a preview of anything. An earlier version checked budget
        # only on the mutating path, so `--dry-run` claimed it would restart a lane it would in
        # fact have held.
        handle = dispatch.get("assignee_handle") or recorded.get(task["id"])
        if handle and handle in terminals:
            # A tail that has not moved is a tail describing now, so the whole of it is read rather
            # than its last few lines. `why` already carries the distinction: only the silence
            # branch says "silent for".
            held = budget_held(cli, handle, silent=why.startswith("silent for"))
            if held:
                # The countdown in the notice was captured when the agent stopped, not now, so it
                # is reported alongside how long ago that was. Printing a frozen "resets in 2h" an
                # hour later reads as a live figure and overstates the outage by exactly the time
                # already served.
                window = reset_seconds(held)
                # Measured from when *this* notice was first seen rather than from the terminal's
                # last-output time, which is a proxy that fails in both directions -- see
                # `hold_elapsed`.
                quiet_s = hold_elapsed(HOLD_CLOCK, task["id"], held, int(time.time()))

                # **A hold must expire.** An exhausted agent produces no output, so its banner never
                # scrolls out of the tail -- without a deadline the lane stays held forever, which
                # is the outage made permanent by the very thing meant to survive it. When the
                # agent's own stated window has elapsed since it printed the notice, stop believing
                # the banner and try.
                if window is not None and quiet_s > window:
                    print(f"RESUME  {label}: stated window of {window // 60} min elapsed "
                          f"({quiet_s // 60} min since the notice); retrying")
                else:
                    remaining = "unknown" if window is None else f"{max(0, (window - quiet_s)) // 60} min"
                    print(f"HELD    {label}: out of budget, not retried "
                          f"[{held}] -- captured {quiet_s // 60} min ago, {remaining} left")
                    continue

        # Re-attach to the terminal the lane already owns when we still know it, so a lane keeps its
        # worktree and its conversation. Without a handle there is nothing to re-attach to, and
        # choosing a new placement is a coordinator decision rather than this script's.
        if not handle or handle not in terminals:
            print(f"MANUAL  {label}: {why}; no live terminal to re-attach, coordinator must place it")
            continue

        # `--retry-of` is only valid against a dispatch the runtime considers settled. Passing it
        # for a still-active one is rejected with "cannot retry from Dispatch <id>", which is how
        # three healthy lanes were reported as failures. A dispatch that is still `dispatched` with
        # a live terminal is not ours to restart at all: Orca believes it is running, and forcing a
        # retry is how a merely-quiet worker gets circuit-broken.
        status = dispatch.get("status")
        if status not in {"failed", "stopped"} and dispatch.get("assignee_handle"):
            print(f"STALE   {label}: {why}; dispatch still active, not retried "
                  f"(read the terminal before deciding it is dead)")
            continue

        # Every verdict above is reached identically with and without `--dry-run`, which is the
        # whole point: a preview that takes a different path from the run it previews predicts
        # nothing. Only the mutation itself is skipped.
        if args.dry_run:
            print(f"WOULD   {label}: {why}")
            restarted += 1
            continue

        start = ["orchestration", "worker-start", "--task", task["id"], "--terminal", handle, "--json"]
        if dispatch.get("id") and status in {"failed", "stopped"}:
            start += ["--retry-of", dispatch["id"]]
        before = dispatch.get("id")
        outcome = call(cli, *start)
        if outcome.get("ok"):
            print(f"RESTART {label}: {why}")
            restarted += 1
            continue

        # A dropped response is not proof the mutation failed. `runtime_unavailable` means Orca
        # closed the connection before answering, and twice here the retry dispatch was created
        # anyway -- so believing the error would report a lane as dead while it was in fact queued.
        # Ask the runtime what actually happened instead of trusting the transport.
        message = (outcome.get("error") or {}).get("message", "unknown error")
        after = ((call(cli, "orchestration", "dispatch-show", "--task", task["id"], "--json")
                  .get("result") or {}).get("dispatch") or {})
        if after.get("id") and after.get("id") != before:
            print(f"QUEUED  {label}: {why}; retry dispatch {after['id']} created, "
                  f"attach pending (transport said: {message[:80]})")
            restarted += 1
        else:
            print(f"FAILED  {label}: {why}; {message}")

    print(f"\n{restarted} lane(s) {'would be ' if args.dry_run else ''}restarted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

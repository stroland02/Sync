"""Re-run the suite until it goes red, keeping the whole output of every run.

A failure that arrives about once in eight runs was lost twice, both times because only the tail
of the output survived and the tail of a `-q` run is a count. The name of the failing test is in
the body, so the body is what this keeps.

Nothing here changes how the suite is invoked. The command is exactly the one that failed --
`uv run pytest -q`, with `addopts` supplying `-m 'not e2e' -n auto` -- because a capture that
alters the run may not capture the thing it was written for. In particular the worker count stays
`auto`: xdist distributes tests to workers dynamically, so which worker runs which test differs
between runs, and that is one of the few things that varies at all in a suite with no random
ordering plugin installed.

Every run is written whole, red or green. A green run before the red one is evidence too: it is
what says the failure is intermittent rather than introduced by the previous command.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# `[gw3]` in a failure header names the xdist worker. Kept because order dependence under xdist
# means "after some other test on the same worker" rather than "after some other test".
WORKER = re.compile(r"\[(gw\d+)\]")
FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)


def run_once(index: int, outdir: Path, command: list[str]) -> tuple[int, str]:
    """One full run, its entire output written before anything is parsed out of it."""
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    body = (result.stdout or "") + (result.stderr or "")
    path = outdir / f"run-{index:02d}.txt"
    path.write_text(
        f"$ {' '.join(command)}\nexit={result.returncode}\n\n{body}", encoding="utf-8"
    )
    return result.returncode, body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=12, help="how many times to try")
    parser.add_argument(
        "--outdir", default=".cache/flake", help="where every run's whole output is kept"
    )
    parser.add_argument(
        "--keep-going", action="store_true",
        help="do not stop at the first red run; measures the rate rather than catching one",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    command = ["uv", "run", "pytest", "-q"]

    red: list[int] = []
    for index in range(1, args.runs + 1):
        code, body = run_once(index, outdir, command)
        summary = next(
            (line for line in reversed(body.splitlines()) if " in " in line and "==" not in line),
            "",
        )
        print(f"run {index:02d}: exit={code}  {summary.strip()}", flush=True)

        if code == 0:
            continue

        red.append(index)
        names = FAILED.findall(body)
        workers = sorted(set(WORKER.findall(body)))
        print(f"  FAILED: {names or '(no FAILED line; see the file)'}", flush=True)
        print(f"  workers named in the output: {workers}", flush=True)
        print(f"  whole output: {outdir / f'run-{index:02d}.txt'}", flush=True)
        if not args.keep_going:
            return 1

    if red:
        print(f"\n{len(red)} of {args.runs} runs were red: {red}", flush=True)
        return 1
    print(f"\n{args.runs} runs, none red.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

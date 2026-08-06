"""Profile what CI actually spends its time on, from GitHub's own record.

Run it against the last N workflow runs; it writes a dated report under
`docs/superpowers/reports/` and prints the same table. The point is that a CI optimisation
argued from a guess is worth nothing: this repository has already spent a day treating a
runner-allocation failure as a red build, and the difference was visible in the job record.

**Only successful jobs are measured.** A cancelled job records a start and an end fifteen
minutes apart while running zero steps, and averaging that into a duration would report the
suite getting slower when what happened is that nothing ran at all. `zero_step_jobs` counts
those separately, because their number is itself a signal worth watching.

Usage:

    uv run python scripts/profile_ci.py --runs 30
    uv run python scripts/profile_ci.py --runs 30 --no-write   # print only

`gh` supplies authentication. Everything here is read-only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = "stroland02/Sync"
REPORTS = Path(__file__).resolve().parents[1] / "docs" / "superpowers" / "reports"

# A step below this is noise in a report about where minutes go. It is a display threshold and
# nothing is dropped from the underlying totals.
_INTERESTING_SECONDS = 3.0


def _gh_json(path: str) -> object:
    """One `gh api` call, decoded as UTF-8 explicitly.

    `text=True` alone decodes with the locale codepage, which on Windows is cp1252 and raises on
    the reader thread rather than at the call site -- `stdout` comes back `None` and the next line
    fails somewhere unrelated. `CLAUDE.md` carries the full argument.
    """
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(result.stdout)


def _seconds(started: str | None, completed: str | None) -> float | None:
    if not started or not completed:
        return None
    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
    end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
    return (end - start).total_seconds()


def collect(run_count: int) -> dict[str, object]:
    runs = _gh_json(f"repos/{REPO}/actions/runs?per_page={run_count}")
    assert isinstance(runs, dict)

    job_durations: dict[str, list[float]] = defaultdict(list)
    step_durations: dict[tuple[str, str], list[float]] = defaultdict(list)
    critical_path: list[float] = []
    zero_step_jobs = 0
    measured_runs = 0

    for run in runs["workflow_runs"][:run_count]:
        jobs = _gh_json(f"repos/{REPO}/actions/runs/{run['id']}/jobs")
        assert isinstance(jobs, dict)
        run_longest = 0.0
        counted_this_run = False

        for job in jobs["jobs"]:
            steps = job.get("steps") or []
            if not steps:
                zero_step_jobs += 1
                continue
            if job.get("conclusion") != "success":
                continue
            duration = _seconds(job.get("started_at"), job.get("completed_at"))
            if duration is None:
                continue
            job_durations[job["name"]].append(duration)
            run_longest = max(run_longest, duration)
            counted_this_run = True
            for step in steps:
                step_seconds = _seconds(step.get("started_at"), step.get("completed_at"))
                if step_seconds is not None:
                    step_durations[(job["name"], step["name"])].append(step_seconds)

        if counted_this_run:
            # Jobs run concurrently, so a run costs its slowest job rather than their sum. This is
            # only the critical path of the jobs that succeeded; a run where one job never started
            # understates it, and that is the honest direction to be wrong in.
            critical_path.append(run_longest)
            measured_runs += 1

    return {
        "jobs": job_durations,
        "steps": step_durations,
        "critical_path": critical_path,
        "zero_step_jobs": zero_step_jobs,
        "measured_runs": measured_runs,
        "requested_runs": run_count,
    }


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def render(data: dict[str, object]) -> str:
    jobs: dict[str, list[float]] = data["jobs"]  # type: ignore[assignment]
    steps: dict[tuple[str, str], list[float]] = data["steps"]  # type: ignore[assignment]
    critical: list[float] = data["critical_path"]  # type: ignore[assignment]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# CI profile — {stamp}",
        "",
        f"Measured over the last {data['requested_runs']} workflow runs, of which "
        f"**{data['measured_runs']}** contributed at least one successful job. "
        f"**{data['zero_step_jobs']} jobs ran zero steps** — a job that records a start and an end "
        "without running a step was never acquired by a runner, and its elapsed time is not a "
        "duration.",
        "",
        f"**Critical path, median: {_median(critical):.0f}s.** Jobs run concurrently, so a run "
        "costs its slowest job rather than the sum of them; shortening anything else buys nothing.",
        "",
        "## Jobs",
        "",
        "| Job | n | median | min | max |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, values in sorted(jobs.items(), key=lambda kv: -_median(kv[1])):
        lines.append(
            f"| `{name}` | {len(values)} | {_median(values):.0f}s | "
            f"{min(values):.0f}s | {max(values):.0f}s |"
        )

    lines += [
        "",
        f"## Steps above {_INTERESTING_SECONDS:.0f}s",
        "",
        "| Median | n | Job | Step |",
        "|---:|---:|---|---|",
    ]
    for (job, step), values in sorted(steps.items(), key=lambda kv: -_median(kv[1])):
        median = _median(values)
        if median < _INTERESTING_SECONDS:
            continue
        lines.append(f"| {median:.0f}s | {len(values)} | `{job}` | {step} |")

    lines += [
        "",
        "## Reading this",
        "",
        "A step is worth attacking only if it sits on the critical path — inside whichever job the",
        "table above shows slowest. A saving inside a faster job is real compute and zero",
        "wall-clock, and the two are different currencies: compute is billed, wall-clock is what a",
        "reviewer waits for. Say which one a change buys.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=30, help="how many recent runs to read")
    parser.add_argument("--no-write", action="store_true", help="print without writing a report")
    args = parser.parse_args()

    report = render(collect(args.runs))
    print(report)

    if not args.no_write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = REPORTS / f"ci-profile-{stamp}.md"
        path.write_text(report, encoding="utf-8")
        print(f"\nwrote {path}")


if __name__ == "__main__":
    main()

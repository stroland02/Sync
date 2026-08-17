"""Whether a pytest run's verdict can be believed at all.

A gate answers one question and this module answers a prior one: did the run finish well enough
for its answer to mean anything. Those are different, and conflating them cost this workspace a
morning on 2026-08-17 — a run reported roughly thirty `F` marks after a worker died, which read
as a catastrophic regression, and the same tree run to completion reported one failure.

A dead worker's marks are not failures. They are absences wearing a failure's glyph, and pytest
prints them identically. This repository already refuses that distinction being lost elsewhere:
a finding carries the rung it came from, absence renders apart from zero, and a vendor that can
bind nothing says so rather than reporting no findings. A run whose verdict cannot be attributed
is the same class, so it is reported rather than counted.

Read as a library by `tests/test_gate_verdict.py`, and runnable as
`uv run python scripts/gate_verdict.py <pytest-output-file>` so a lane can check a run it has
already saved without repeating it. Exit code 0 means trustworthy, 2 means it is not; a failing
suite is still exit 0 here, because whether the suite passed is the other question.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# `[gw3] node down: Not properly terminated` -- xdist's own words when a worker dies.
_NODE_DOWN = re.compile(r"\[(?P<worker>gw\d+)\] node down")

# `worker 'gw0' crashed while running 'tests/test_x.py::test_y'`. Printed after the fact, and it
# is the only line that names what the worker was doing, which is where a diagnosis starts.
_CRASHED_ON = re.compile(r"worker '(?P<worker>gw\d+)' crashed while running '(?P<test>[^']+)'")

# xdist's bookkeeping failing on its own -- a different shape with the same consequence, and it
# ends in `no tests ran`, which a reader skimming the last line records as nothing to see.
_INTERNAL_ERROR = re.compile(r"^INTERNALERROR>", re.MULTILINE)

# pytest's final tally. Matched from the line start so a test name quoting the words in its own
# body cannot be mistaken for the summary.
_SUMMARY = re.compile(
    r"^(?P<summary>(?:\d+ (?:failed|passed|skipped|error|errors|xfailed|xpassed|deselected|warnings?)"
    r"(?:, )?)+ in [\d.]+s.*)$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Verdict:
    """Whether the run's own answer can be believed, and why not when it cannot."""

    trustworthy: bool
    summary: str | None
    crashed_workers: list[str] = field(default_factory=list)
    crashed_on: list[str] = field(default_factory=list)
    internal_error: bool = False

    @property
    def reason(self) -> str | None:
        """Stated only when the run is untrustworthy.

        Silence is the ordinary case, in the same direction `sdk_bindings` and
        `unbindable_reason` take: a run that is fine asserts nothing, and a gap is something the
        run has to declare.
        """
        if self.trustworthy:
            return None
        if self.crashed_workers:
            where = f" while running {', '.join(self.crashed_on)}" if self.crashed_on else ""
            return (
                f"{', '.join(self.crashed_workers)} died{where}. Every mark printed after a worker "
                f"dies belongs to a test that never reached a verdict, so the tally below counts "
                f"absences as failures."
            )
        if self.internal_error:
            return (
                "xdist raised INTERNALERROR, so the run ended on its own bookkeeping rather than "
                "on the suite. Whatever it reported describes the scheduler, not the tests."
            )
        return "the run printed no summary line, so it did not reach a verdict."

    def render(self) -> str:
        head = "TRUSTWORTHY" if self.trustworthy else "UNTRUSTWORTHY"
        tail = self.summary or "no summary line"
        return f"{head}: {tail}" if self.trustworthy else f"{head}: {self.reason} Tally: {tail}"


def read_verdict(output: str) -> Verdict:
    """Judge a pytest run from its captured output.

    Deliberately reads the text rather than hooking pytest. The runs this exists to catch are the
    ones that died, and a plugin inside a dead worker reports nothing -- the output file is the
    only artifact that survives both shapes.
    """
    crashed_workers = [m["worker"] for m in _NODE_DOWN.finditer(output)]
    crashed_on = [m["test"] for m in _CRASHED_ON.finditer(output)]
    internal_error = bool(_INTERNAL_ERROR.search(output))
    matches = _SUMMARY.findall(output)
    summary = matches[-1] if matches else None

    trustworthy = not crashed_workers and not internal_error and summary is not None
    return Verdict(
        trustworthy=trustworthy,
        summary=summary,
        crashed_workers=crashed_workers,
        crashed_on=crashed_on,
        internal_error=internal_error,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gate_verdict.py <pytest-output-file>", file=sys.stderr)
        return 64
    path = Path(argv[1])
    if not path.exists():
        # The same refusal `lint_dead_links` and `lint_test_skips` make: a checker pointed at
        # nothing must not report success, or a mistyped path silently becomes a green.
        print(f"gate_verdict: {path} does not exist", file=sys.stderr)
        return 64
    verdict = read_verdict(path.read_text(encoding="utf-8", errors="replace"))
    print(verdict.render())
    return 0 if verdict.trustworthy else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

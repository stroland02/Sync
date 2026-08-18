"""Split a failing suite into failures that are real and failures that are interference.

`gate_verdict.py` answers whether a run's verdict can be **believed** — a dead worker's marks are
absences wearing a failure's glyph. This answers the question after it: given failures the run
does report, which of them are genuine?

**A test that passes alone and fails in company has not failed. It has interfered.** The two look
identical in a summary line, and telling them apart by hand is what every lane has been doing:
three runs of one tree here gave seven failures, then two, then a worker collection mismatch, and
each reader re-derived the same list.

This is not a convenience. It is the distinction this repository enforces everywhere else —
absence rendered apart from zero, a binding carrying the rung it came from, a run that could not be
checked refusing to report as checked. A failure nobody has isolated is a claim about the tree that
the measurement does not support.

**Interference does not have to raise to be a defect**, which is the reason this tool earns its
place rather than saving typing. `sync.index.codebase._load_or_create_vendor_adapter` reads its
cache from a CWD-relative path and silently substitutes a fallback adapter when any exception is
raised, so a test that runs after something which changed directory gets a *different answer*
rather than an error: `CreateCharges` where the real adapter says `PostCharges`. Interference that
returns wrong data is exactly what a summary line cannot show you.

Run it: `uv run python scripts/isolate_failures.py <nodeid> [<nodeid> ...]`, or pipe a previous
run's output in with `--from-output <path>`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

# pytest prints one of these per failure in its short summary. The node id runs to the first
# space, because a summary line carries ` - AssertionError: ...` after it.
_FAILED_LINE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)

REAL = "real"
INTERFERENCE = "interference"


@dataclass(frozen=True)
class Isolated:
    """One failure, re-run by itself."""

    node_id: str
    verdict: str
    detail: str

    @property
    def is_real(self) -> bool:
        return self.verdict == REAL


def node_ids(text: str) -> list[str]:
    """Every failing node id in a pytest run's output, in the order reported, without duplicates.

    Deduplicated because a run that reports the same node twice — a rerun plugin, or a summary
    printed per worker — would otherwise have it isolated twice and counted twice.
    """
    seen: dict[str, None] = {}
    for match in _FAILED_LINE.finditer(text):
        seen.setdefault(match.group(1), None)
    return list(seen)


def _run_alone(node_id: str) -> tuple[int, str]:
    result = subprocess.run(
        ["uv", "run", "pytest", node_id, "-q", "-n0"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # The child is a Python process and this machine's locale codepage is not utf-8, so
        # without this it emits cp1252 and the reader thread raises on the first em dash --
        # returning stdout as None and failing somewhere unrelated. CLAUDE.md carries the
        # measurement that cost.
        env={**_child_env(), "PYTHONIOENCODING": "utf-8"},
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _child_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def isolate(
    ids: Sequence[str], *, run: Callable[[str], tuple[int, str]] | None = None
) -> list[Isolated]:
    """Re-run each node id by itself and say which kind of failure it is.

    `run` is injected so the classification is testable without a suite. Everything interesting
    here is the classification; the subprocess is not the part that can be wrong.
    """
    runner = run if run is not None else _run_alone
    results = []
    for node_id in ids:
        code, output = runner(node_id)
        if code == 0:
            results.append(
                Isolated(
                    node_id,
                    INTERFERENCE,
                    "passes alone, so the failure came from something else in the run",
                )
            )
        elif "no tests ran" in output or "ERROR: not found" in output:
            # A node id that no longer exists is neither real nor interference. Reporting it as
            # real would invent a failing test; reporting it as interference would clear it.
            results.append(
                Isolated(node_id, REAL, "could not be collected alone -- the node id may be stale")
            )
        else:
            results.append(Isolated(node_id, REAL, "fails alone"))
    return results


def render(results: Sequence[Isolated]) -> str:
    real = [r for r in results if r.is_real]
    interference = [r for r in results if not r.is_real]
    lines = [
        f"{len(results)} failure(s) isolated: {len(real)} real, {len(interference)} interference",
        "",
    ]
    if real:
        lines.append("REAL -- these fail on their own:")
        lines += [f"  {r.node_id}  ({r.detail})" for r in real]
        lines.append("")
    if interference:
        lines.append("INTERFERENCE -- these pass on their own, so something else in the run broke them:")
        lines += [f"  {r.node_id}  ({r.detail})" for r in interference]
        lines.append("")
        lines.append(
            "Interference is not automatically harmless. Shared state that changes an answer "
            "rather than raising -- a CWD-relative path, a cached adapter, a leaked database -- "
            "produces wrong data in a real run and no error anywhere."
        )
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("node_ids", nargs="*", help="failing test node ids")
    parser.add_argument(
        "--from-output",
        metavar="PATH",
        help="read failing node ids from a saved pytest run instead of naming them",
    )
    args = parser.parse_args(list(argv[1:]))

    ids = list(args.node_ids)
    if args.from_output:
        ids += node_ids(Path(args.from_output).read_text(encoding="utf-8"))
    if not ids:
        # Nothing to isolate is not success. It means the caller gave this tool no failures, and
        # printing "0 real" would read as a measured all-clear.
        print("no failing node ids given, so nothing was isolated and nothing is claimed")
        return 2

    results = isolate(ids)
    print(render(results))
    return 1 if any(r.is_real for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

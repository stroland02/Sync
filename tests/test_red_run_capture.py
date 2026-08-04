"""A failing run's output has to still be readable after the next run.

The run this file exists for came back `1 failed, 2897 passed, 4 skipped, 12 warnings, 6 errors`,
all of it in one file. The immediate rerun was green and that file has passed every time since, so
nobody can say whether it was a flake or an intermittent defect -- the text that would have
answered it was overwritten by the rerun before anyone read it. Those two possibilities are
indistinguishable once the output is gone.

Nothing pytest ships keeps it. `--last-failed` persists node ids and no output at all, and a
following green run empties `lastfailed` outright; `--junitxml` does carry the failure text, and
writes it to the one path the flag names, so the next run overwrites it. Both measured here rather
than read off the documentation.

The mechanism is `red_run_capture`, wired from `conftest`. This file drives it the only way the
claim can be checked: a child pytest that really fails, then a child that really passes, then the
first one's output read back off disk.

A child rather than an in-process assertion on the capture function, because the claim is about the
harness under a real failing run and a function called by hand is not that. The child runs the
repository's own suite -- its own `conftest`, its own `pytest_configure`, its own database -- with
one node id selected and a plugin that makes it fail.

**The child's database.** `test_serial_run_isolation` established the shape and this follows it:
`SYNC_DSN` is stripped so the child creates and owns a database named for its own pid rather than
borrowing this run's, and the server it reached travels separately in `SYNC_TEST_SERVER`. The child
fails a test; it does not crash, so it reaches `pytest_unconfigure` and drops what it created. A
deliberately-red run leaves nothing for the sweep to find.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROBE_CASE = (
    "tests/test_serial_run_isolation.py"
    "::test_template_dsn_prefers_the_pin_then_the_server_then_the_default"
)
"""One node id, chosen because it touches nothing: no database, no subprocess, no fixture.

A node id rather than `-k`, for the reason `test_serial_run_isolation` gives: a rename makes pytest
exit 4 on a collection error, which a test reading the exit code sees, while a `-k` expression that
stopped matching selects nothing and exits 5 having asserted about a run of no tests.
"""

EM_DASH = "—"

FORCED_RED = (
    "def pytest_runtest_call(item):\n"
    f'    raise AssertionError("forced red {EM_DASH} an em dash pytest will echo back")\n'
)
"""A plugin that fails whatever is selected, carrying a character cp1252 cannot round-trip.

The em dash is the point rather than decoration. What this mechanism captures is the output of a
failing test, and a failing test echoes the source lines around it -- this repository's docstrings
are full of em dashes, so the first real red this ever records will carry non-ASCII. A capture that
raised on it would fail at exactly the moment it exists for. Both routes are covered here: the
message the assertion carries, and the source line pytest reads back out of this file.

Deliberately non-ASCII, which every other fixture in this repository is not --
`.claude/rules/test-discipline.md` says a fixture added specifically to exercise a decode path is
welcome, and this is one.
"""

WORKERS = "-n2"
"""Two workers, not `-n auto`.

The scheduler matters here -- under xdist every worker is a separate pytest session running this
same `conftest`, and one file per worker instead of one per run is the obvious way for this to go
wrong. Two workers reach that case. `-n auto` spins up twelve for four seconds and reaches nothing
the second worker did not.
"""


def _child_env(capture_dir: Path, plugin_dir: Path) -> dict[str, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    # The parent's DSN names the one server this run actually reached, wherever the suite is
    # executing. The child must not inherit it as a pin: `database_for` returns None for a pinned
    # serial run, so a pinned child creates no database and the isolation this relies on is gone.
    parent_dsn = env.get("SYNC_DSN")
    if parent_dsn:
        env["SYNC_TEST_SERVER"] = parent_dsn
    for inherited in (
        "SYNC_DSN",
        "PYTEST_XDIST_WORKER",
        "PYTEST_XDIST_TESTRUNUID",
        "PYTEST_CURRENT_TEST",
    ):
        env.pop(inherited, None)
    env["SYNC_RED_RUN_DIR"] = str(capture_dir)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(plugin_dir), *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])]
    )
    return env


def _run_child(env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            WORKERS,
            "--color=no",
            "-p",
            "no:cacheprovider",
            *extra,
            PROBE_CASE,
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )


def _captures(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.log")) if directory.exists() else []


def test_a_red_run_is_kept_and_the_next_green_run_does_not_take_it(tmp_path: Path):
    """Red, then green, then read the red back. The whole claim in one test.

    Split into two tests it would need the red run twice, and the second half is only meaningful
    against a capture the first half just made.
    """
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / "forced_red.py").write_text(FORCED_RED, encoding="utf-8")
    capture_dir = tmp_path / "red-runs"
    env = _child_env(capture_dir, plugin_dir)

    red = _run_child(env, "-p", "forced_red")

    assert red.returncode == 1, (
        f"the child was meant to fail one test and exited {red.returncode}\n"
        f"--- stdout ---\n{red.stdout}\n--- stderr ---\n{red.stderr}"
    )
    assert "1 failed" in red.stdout, f"expected one real failure, got:\n{red.stdout}"

    kept = _captures(capture_dir)
    assert len(kept) == 1, (
        f"one red run, one capture -- found {[p.name for p in kept]}. More than one means every "
        f"xdist worker wrote its own.\n--- stdout ---\n{red.stdout}"
    )
    captured = kept[0].read_text(encoding="utf-8")

    assert f"{EM_DASH} an em dash pytest will echo back" in captured, (
        "the capture lost the non-ASCII character it exists to survive:\n" + captured
    )
    assert "1 failed" in captured, (
        "the run's final counts are written after every `pytest_sessionfinish` hook, so a capture "
        "that stops there keeps the traceback and loses the verdict:\n" + captured
    )
    assert captured in red.stdout, (
        "what survives has to be the output rather than a rendering of it"
    )

    before = kept[0].read_bytes()
    green = _run_child(env)

    assert green.returncode == 0, (
        f"the second child was meant to pass and exited {green.returncode}\n"
        f"--- stdout ---\n{green.stdout}\n--- stderr ---\n{green.stderr}"
    )
    assert _captures(capture_dir) == kept, (
        "a green run writes nothing and removes nothing -- the directory changed"
    )
    assert kept[0].read_bytes() == before, "the green run overwrote the red run's output"

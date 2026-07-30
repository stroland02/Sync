"""A serial run must still have its own database when it finishes.

`addopts` pins `-n auto`, so an ordinary suite run never reaches the case this file is about and
the canary it drives can never fail in-process. That is not a hypothetical gap: `-n0` was broken
on `main` for an unknown length of time -- 186 errors in a full run -- and two deliberate decisions
kept it invisible. `addopts = "-m 'not e2e' -n auto"` means nobody reaches `-n0` by accident, and
CI's coverage step carries `|| true`. `docs/superpowers/reports/2026-07-30-n0-is-broken.md`.

`-n0` is not a debugging convenience here. `pyproject.toml` names it for a focused run, and
`2026-07-29-sync-verification-regime.md` names it as the way to run the e2e test, because
`addopts` deselects that test and pins the scheduler in the same string. So the serial
configuration is contracted, and something has to run it.

A child process is the only way to assert on a scheduler the parent is not using. The child gets
`SYNC_DSN` and xdist's own variables removed from its environment, so it creates and owns a
database of its own rather than borrowing this run's -- a child that inherited `SYNC_DSN` would
reproduce the defect against the parent's database, which is the failure this test exists to stop.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SERIAL_CASE = [
    "tests/test_leaked_database_sweep.py::test_a_database_in_use_is_refused_rather_than_force_dropped",
    "tests/test_leaked_database_sweep.py::test_a_database_that_cannot_be_dropped_does_not_fail_the_run",
    "tests/test_leaked_database_sweep.py::test_the_run_s_own_database_survives_every_sweep_in_this_file",
]
"""The two sweeps that lie about liveness, then the canary that reports whether they overreached.

Node ids rather than `-k`, because a rename makes pytest exit 4 with a collection error, which
this test reads as a failure. A `-k` expression that stopped matching would select nothing and
exit 5, and an earlier version of that idea is exactly how a test in this repository passed
without running anything.
"""


def test_template_dsn_prefers_the_pin_then_the_server_then_the_default():
    """The selection order the child below depends on.

    `SYNC_TEST_SERVER` exists for exactly one caller: a parent test that must launch an
    *unpinned* child -- pinning would hide the defect the child reproduces, because a pinned
    serial run creates no database of its own -- on whatever server the parent actually
    reached. Without it the child falls back to `DEFAULT_DSN`, which names this machine's
    5433 mapping and no CI runner's.
    """
    from tests import conftest

    assert conftest.template_dsn("postgresql://u:p@h:1/pin") == "postgresql://u:p@h:1/pin"
    assert (
        conftest.template_dsn(None, server="postgresql://u:p@h:2/any")
        == "postgresql://u:p@h:2/any"
    )
    assert conftest.template_dsn(None, server=None) == conftest.DEFAULT_DSN


def test_a_serial_run_does_not_sweep_away_its_own_database():
    """The whole point of the child, and it fails today without the `exclude` on those two sweeps.

    Measured red before the fix: `1 failed, 2 passed`, with
    `sync_test_32080 is the database this run is using and a sweep in this file took it`.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    # The parent's DSN names the one server this run has actually reached, wherever the suite
    # is executing. The child must not inherit it as a *pin* -- a pinned serial run creates no
    # database of its own, which hides the exact defect this test reproduces -- so the server
    # travels via SYNC_TEST_SERVER and the pin is stripped. Without this, the child falls back
    # to DEFAULT_DSN, which names this machine's 5433 mapping and no CI runner's.
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

    child = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-n0", "--color=no", "-p", "no:cacheprovider",
         *SERIAL_CASE],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )

    assert child.returncode == 0, (
        f"a serial run of the sweep file exited {child.returncode}\n"
        f"--- stdout ---\n{child.stdout}\n--- stderr ---\n{child.stderr}"
    )
    # Exit 0 alone does not say three tests ran: pytest exits 0 on a run where everything was
    # deselected, and a stale node id exits 4 rather than running the other two.
    assert "3 passed" in child.stdout, (
        f"expected three tests to run serially, got:\n{child.stdout}"
    )

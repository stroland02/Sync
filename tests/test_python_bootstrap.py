"""Decision 98's bootstrap, and the machine that already has half of it.

`uv` fetching a pinned 3.12 is the easy half and it is not what these test. They test the half that
breaks a second run: a `uv`, a Python or a virtualenv already on the machine.

The rule underneath all of it is **reuse what is provably the same, rebuild what is merely
similar** — because both wrong reuses fail silently. A virtualenv built from a different lockfile
runs versions nobody pinned, and the resulting bug cannot be reproduced by whoever reports it.

Nothing here reaches the network, spawns `uv`, or creates an environment. Every branch is an
injected probe, which is why this can be tested before the bootstrap exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "bin" / "python-bootstrap.mjs"

PYTHON = "3.12"


def _call(expression: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is absent from this machine, and this executes the installer's own JavaScript")

    script = (
        f"import * as m from {MODULE.as_uri()!r};"
        f"console.log(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the bootstrap module would not load: {result.stderr}"
    return json.loads(result.stdout.strip())


def _env(**kw):
    fields = {
        "exists": "true",
        "lockDigest": "'abc'",
        "recordedDigest": "'abc'",
        "pythonVersion": f"'{PYTHON}'",
        "wantedPython": f"'{PYTHON}'",
    }
    fields.update(kw)
    args = ", ".join(f"{k}: {v}" for k, v in fields.items())
    return _call(f"m.environmentVerdict({{{args}}})")


def test_an_environment_built_from_a_different_lockfile_is_rebuilt():
    """The silent failure this whole module is arranged around.

    Reusing it would run dependency versions nobody pinned, and the bug that produces is the kind
    the reporter cannot reproduce because their environment is the one thing they did not change.
    """
    verdict = _env(recordedDigest="'a-different-lock'")

    assert verdict["action"] == "rebuild"
    assert "not the pinned ones" in verdict["message"]


def test_sameness_is_a_digest_rather_than_a_timestamp():
    """Pinned by asserting the shape of the input, because the wrong version passes by accident.

    `CLAUDE.md` measured 184 of 200 identical-byte rewrites leaving `st_mtime_ns` untouched, so an
    mtime comparison fires only when a write happens to cross a tick. It reads as flaky and is
    actually a check that mostly does not check. The same defect shipped twice here in one day.
    """
    same = _env(lockDigest="'same'", recordedDigest="'same'")
    differing = _env(lockDigest="'same'", recordedDigest="'other'")

    assert same["action"] == "reuse"
    assert differing["action"] == "rebuild"


def test_an_environment_on_the_wrong_interpreter_is_not_adopted():
    """A pinned 3.12 is a guarantee the project relies on, not a preference."""
    verdict = _env(pythonVersion="'3.11'")

    assert verdict["action"] == "rebuild"
    assert "3.11" in verdict["message"] and PYTHON in verdict["message"]


def test_a_matching_environment_is_reused_and_says_it_downloaded_nothing():
    verdict = _env()

    assert verdict["action"] == "reuse"
    assert "no download" in verdict["message"].lower()


def test_no_environment_at_all_is_a_first_run_rather_than_a_fault():
    verdict = _env(exists="false")

    assert verdict["action"] == "rebuild"
    assert "Creating" in verdict["message"]


def test_using_the_machines_uv_is_not_reported_as_installing_one():
    """The same distinction as adopting a Postgres rather than starting it.

    An installer that claims work it did not do teaches the reader to discount its output, and it
    does so in the first line they read.
    """
    verdict = _call(f"m.uvVerdict({{foundVersion: '0.5.11', minimumVersion: '0.5.0'}})")

    assert verdict["action"] == "use-existing"
    assert "Nothing was installed" in verdict["message"]


def test_a_uv_too_old_is_fetched_rather_than_upgraded_underneath_somebody():
    """Changing a tool the machine already had is not ours to do; fetching our own is."""
    verdict = _call(f"m.uvVerdict({{foundVersion: '0.4.0', minimumVersion: '0.5.0'}})")

    assert verdict["action"] == "fetch"
    assert "rather than changing the one you have" in verdict["message"]


def test_no_uv_at_all_promises_nothing_else_is_needed():
    verdict = _call("m.uvVerdict({foundVersion: null, minimumVersion: '0.5.0'})")

    assert verdict["action"] == "fetch"
    assert "nothing else is needed from you" in verdict["message"]


@pytest.mark.parametrize(
    "older, newer",
    [("0.5", "0.5.11"), ("0.4.9", "0.5.0"), ("1.0.0", "1.0.1")],
)
def test_a_missing_version_component_counts_as_zero(older, newer):
    """`0.5` against `0.5.11` is the comparison a naive string compare gets backwards."""
    assert _call(f"m.isOlder({older!r}, {newer!r})") is True
    assert _call(f"m.isOlder({newer!r}, {older!r})") is False


def test_an_environment_this_installer_did_not_build_says_so_rather_than_blaming_the_lockfile():
    """A nearly-right label, caught by running the check rather than by reading the code.

    With no record, the first version reported *the lockfile has changed since this
    environment was built* -- which is false and misleading in the same breath. The
    environment was built by a developer's own `uv sync`; what is unknown is what it came
    from, not that it drifted. A reader told the lockfile changed goes looking at the
    lockfile.
    """
    verdict = _env(recordedDigest="null")

    assert verdict["action"] == "rebuild"
    assert "did not build it" in verdict["message"]
    assert "unknown is not the same as current" in verdict["message"]
    assert "lockfile has changed" not in verdict["message"]


def test_an_unreadable_interpreter_is_not_printed_as_a_version():
    """`runs Python null` is the absence-as-a-value defect, in a terminal instead of on screen.

    Found by running the check against this repository, where the probe was reading the wrong
    key out of pyvenv.cfg. The probe was fixed; this pins the module against rendering the
    hole even when a probe fails again.
    """
    verdict = _env(pythonVersion="null")

    assert verdict["action"] == "rebuild"
    assert "null" not in verdict["message"]
    assert "could not be read" in verdict["message"]


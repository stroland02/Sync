"""The lifecycle decisions behind a zero-prerequisite install, executed rather than read.

Decision 97 takes Docker out of the install and hands us what Docker was doing for free: a process
lifecycle. The owner named the failure that matters and it is not the first run — **a Postgres left
running after a crash makes the second run worse than the first**, and the second run is the one
that happens on stage.

So these tests are almost entirely about finding something already there. That is the case a
first-run script never reaches, nobody exercises by hand, and a demo reaches immediately after
anything goes wrong.

**Nothing here downloads or starts a database.** Every branch is reachable with an injected probe,
which is the only reason this is testable at all before the binaries exist. The functions are
imported and called for `test_container_install.py`'s reason: asserting a phrase appears in the
file would pass on a source that never reaches the branch printing it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "bin" / "embedded-postgres.mjs"

WANTED = "16.4"


def _node() -> str | None:
    return shutil.which("node")


def _call(expression: str) -> dict:
    node = _node()
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
    assert result.returncode == 0, f"the installer module would not load: {result.stderr}"
    return json.loads(result.stdout.strip())


def _verdict(record: str, alive: str) -> dict:
    return _call(f"m.previousRunVerdict({{record: {record}, alive: {alive}, wantedVersion: {WANTED!r}}})")


def test_a_server_already_running_is_adopted_rather_than_duplicated():
    """Starting a second Postgres would work, and leave the first running forever.

    That is how a laptop ends up with four of them, each holding a port and a few hundred
    megabytes, and none of them owned by anything that will stop them.
    """
    verdict = _verdict(f"{{pid: 4242, port: 55432, version: {WANTED!r}}}", "true")

    assert verdict["action"] == "adopt"


def test_adopting_a_server_does_not_report_starting_one():
    """The distinction this whole module exists to keep, in the one line a reader sees.

    An installer that says "started Postgres" when it started nothing has told its first lie in
    its first sentence, and the thing it lied about is the thing that will confuse the next
    person to debug it.
    """
    verdict = _verdict(f"{{pid: 4242, port: 55432, version: {WANTED!r}}}", "true")

    assert "started nothing" in verdict["message"]
    assert "Starting" not in verdict["message"]


def test_a_server_of_another_version_is_not_ours_to_adopt():
    """New schema against an old server is worse than either alone."""
    verdict = _verdict('{pid: 4242, port: 55432, version: "15.6"}', "true")

    assert verdict["action"] == "reap"
    assert "15.6" in verdict["message"] and WANTED in verdict["message"], (
        "the reader has to be told which version is being stopped and which is wanted"
    )


def test_a_record_with_no_process_behind_it_reports_the_crash():
    """Recovering silently hides that the previous run died, which is the fact worth having.

    The recovery itself is easy and correct. What must not happen is the second run looking
    exactly like a clean first run, because then nobody ever learns the first one crashed.
    """
    verdict = _verdict(f"{{pid: 4242, port: 55432, version: {WANTED!r}}}", "false")

    assert verdict["action"] == "fresh"
    assert "did not shut down cleanly" in verdict["message"]


def test_a_first_run_says_it_is_starting_one():
    verdict = _verdict("null", "false")

    assert verdict["action"] == "fresh"
    assert "No previous server recorded" in verdict["message"]


def test_a_cache_hit_announces_itself():
    """A silent re-download and a silent reuse are identical until somebody is on hotel wifi."""
    verdict = _call(f"m.cacheVerdict({{cachedVersion: {WANTED!r}, wantedVersion: {WANTED!r}}})")

    assert verdict["action"] == "reuse"
    assert "No download" in verdict["message"]


def test_a_first_download_states_the_size_and_that_it_happens_once():
    verdict = _call(f"m.cacheVerdict({{cachedVersion: null, wantedVersion: {WANTED!r}}})")

    assert verdict["action"] == "download"
    assert "55MB" in verdict["message"]
    assert "next run reuses" in verdict["message"], (
        "a download with no promise that it is one-off reads as something that happens every time"
    )


def test_a_cache_holding_another_version_is_not_a_hit():
    verdict = _call(f"m.cacheVerdict({{cachedVersion: '15.6', wantedVersion: {WANTED!r}}})")

    assert verdict["action"] == "download"
    assert "15.6" in verdict["message"], "a reader must be able to tell this from a first run"


def test_the_summary_cannot_claim_a_step_that_was_skipped():
    """Assembled from what happened rather than written once at the end.

    A run that adopted a server and reused a cache started no database and downloaded nothing,
    and the line a reader takes away has to say so.
    """
    summary = _call(
        "m.summarise({postgres: {action: m.ADOPT}, cache: {action: m.REUSE}})"
    )

    assert "reused the Postgres already running" in summary
    assert "no download" in summary
    assert "started Postgres" not in summary

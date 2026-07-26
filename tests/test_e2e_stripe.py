"""M0 acceptance. Makes network and model calls; deselected by default.

Run with: uv run pytest tests/test_e2e_stripe.py -m e2e -v -s
"""

import os
import subprocess
import sys

import pytest

FROM_VERSION = os.environ.get("SYNC_E2E_FROM", "v2320")
TO_VERSION = os.environ.get("SYNC_E2E_TO", "v2330")


def _subprocess_env() -> dict[str, str]:
    """PYTHONIOENCODING=utf-8, set for the child, on top of the inherited environment.

    The parent decodes the child's stdout/stderr with `encoding="utf-8"` below.
    Without this, a Python child on a pipe on this machine defaults its own
    stdout encoding to the locale codepage (cp1252) -- a character cp1252
    cannot encode crashes the child outright, and a Latin-1 accent it can
    encode produces bytes that fail the parent's strict UTF-8 decode on the
    reader thread, which comes back as `stdout=None` rather than raising
    anywhere the caller can see it (CLAUDE.md's encoding section documents
    this exact failure shape). Extending `os.environ` rather than replacing
    it keeps PATH intact, so the child can still find git, gh, and node.
    """
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def test_subprocess_env_sets_encoding_without_discarding_the_inherited_environment():
    env = _subprocess_env()
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PATH"] == os.environ["PATH"]


@pytest.mark.e2e
def test_one_command_produces_one_green_pull_request():
    # Read inside the test, not at import. pytest collects every test module
    # before it applies `-m 'not e2e'`, so a missing variable at module scope
    # would fail collection of the whole suite rather than skipping this one
    # test.
    fork_url = os.environ.get("SYNC_E2E_REPO")
    if not fork_url:
        pytest.skip("set SYNC_E2E_REPO to the fork created in Step 1")

    result = subprocess.run(
        [sys.executable, "-m", "sync.cli", "run",
         "--vendor", "stripe",
         "--from-version", FROM_VERSION,
         "--to-version", TO_VERSION,
         "--repo", fork_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=7200,
        env=_subprocess_env(),
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    assert result.returncode == 0, result.stderr
    assert "finding(s)" in result.stdout
    assert "opened: https://github.com/" in result.stdout, (
        "no pull request was opened; check whether the run abandoned and why"
    )

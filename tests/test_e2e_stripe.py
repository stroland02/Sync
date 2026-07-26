"""M0 acceptance. Makes network and model calls; deselected by default.

Run with: uv run pytest tests/test_e2e_stripe.py -m e2e -v -s
"""

import os
import subprocess
import sys

import pytest

# Read inside the test, not at import. pytest collects every test module before
# it applies `-m 'not e2e'`, so a missing variable at module scope would fail
# collection of the whole suite rather than skipping this one test.
FROM_VERSION = os.environ.get("SYNC_E2E_FROM", "v2320")
TO_VERSION = os.environ.get("SYNC_E2E_TO", "v2330")


@pytest.mark.e2e
def test_one_command_produces_one_green_pull_request():
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
        timeout=3600,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    assert result.returncode == 0, result.stderr
    assert "finding(s)" in result.stdout
    assert "opened: https://github.com/" in result.stdout, (
        "no pull request was opened; check whether the run abandoned and why"
    )

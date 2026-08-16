"""B97: the patch agent's execution context, and the container boundary around it.

`sync.remediate.tool_gate` narrows what the agent may *ask for*. It is not an
operating-system boundary and says so in its own module docstring. This file
proves the gap concretely, on this host, rather than asserting it from a
configuration file:

- `test_patch_agent_execution_context_reaches_arbitrary_host_today` and
  `test_patch_agent_execution_context_inherits_the_full_parent_environment_today`
  reproduce the shape of the subprocess `ClaudeAgentOptions` puts the CLI in
  today -- `cwd` inside a throwaway clone, no `env=`, no `sandbox` -- and show
  it can open a socket to a host Sync never named, carrying whatever secret the
  parent process holds. Both are RED: they demonstrate a real, present gap.

- `test_container_network_cutoff_blocks_arbitrary_egress` proves the mechanism
  this entry needs is real on this host's actual Docker Desktop/WSL2 backend: a
  running Linux container loses its route the moment `docker network
  disconnect` returns, with a positive control so the test cannot pass because
  the harness itself has no route. `sync.remediate.sandbox` is the module this
  test is proving.

Requires a working Docker Desktop with Linux containers -- the same local
toolchain dependency this suite already has on the Postgres container.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys

import pytest

# A public resolver, not a vendor Sync integrates with -- this proves a raw
# socket can leave the process, not that any vendor API answered.
_ARBITRARY_HOST = ("1.1.1.1", 443)
_FAKE_SECRET = "sk-not-a-real-credential-b97-red-test"


def test_patch_agent_execution_context_reaches_arbitrary_host_today(tmp_path):
    """RED for B97: today's execution context has no network boundary.

    Reproduces the shape of the subprocess the patch agent's CLI runs in --
    same cwd-inside-clone, same inherited `os.environ`, no container, no
    network cutoff -- and shows it can open a socket to an arbitrary host.
    Run against a real external address so it demonstrates an actual open
    socket rather than an assumption about the platform.
    """
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import socket; socket.create_connection(('1.1.1.1', 443), timeout=5); "
            "print('CONNECTED')",
        ],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert "CONNECTED" in result.stdout


def test_patch_agent_execution_context_inherits_the_full_parent_environment_today(tmp_path):
    """RED for B97: today's execution context carries every credential the
    control plane holds, not only the ones the patch needs.

    `AgentRemediator._drive_agent` builds `ClaudeAgentOptions` with no `env=`
    argument, so the CLI subprocess it spawns inherits `os.environ` in full --
    `SYNC_GRAPH_DSN`, a webhook secret, a feed-signing key, all reachable from
    inside the clone's `Bash` today. This reproduces that inheritance directly
    rather than asserting it from reading the constructor call.
    """
    env = {**os.environ, "SYNC_GRAPH_DSN": _FAKE_SECRET}
    result = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ.get('SYNC_GRAPH_DSN', ''))"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.stdout.strip() == _FAKE_SECRET


@pytest.mark.docker
def test_container_network_cutoff_blocks_arbitrary_egress():
    """GREEN for B97's close condition, against a real running container.

    Not a mocked Docker client and not an assertion about `--network` flags in
    a compose file -- this is evidence about what this machine's Docker
    Desktop/WSL2 backend actually enforces, which is exactly what the backlog
    entry demands and exactly what a configuration file cannot provide.

    Positive control first: the harness itself proves it can reach the
    network before the cutoff, so a later failure means the cutoff worked,
    not that Docker Desktop lacks a route to begin with -- the same anti-
    pattern CLAUDE.md calls out for the import-boundary test.

    Imported lazily: this test's own existence must not block collection of
    the two RED tests above on a host where `sync.remediate.sandbox` does
    not exist yet.
    """
    from sync.remediate import sandbox

    with sandbox.ephemeral_container(image="python:3.12-slim") as container:
        before = sandbox.probe_connect(container, "1.1.1.1", 443)
        assert before.reachable, f"positive control failed: {before.detail}"

        sandbox.disconnect_network(container)

        after = sandbox.probe_connect(container, "1.1.1.1", 443)
        assert not after.reachable, "expected the disconnect to block egress, but it did not"

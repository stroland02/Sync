"""The container-level network boundary the patch run does not have yet.

B97: `sync.remediate.tool_gate` narrows what the agent may *ask* a tool to do. Its
own docstring says what it is not -- "not an OS boundary, and a command on the
permitted list still runs the customer's own toolchain." This module is a step
toward the boundary that docstring points at: a real Docker container, created for
one patch attempt, whose network can be cut off from underneath it while it runs.

**What this module proves, verified against this host's actual Docker Desktop
(4.81.0, Linux containers over the WSL2 backend -- `docker version` read before
writing a line of this file, rather than assumed): a running container loses its
route the moment `docker network disconnect` returns.** That was an open question
in the design this module implements -- "whether Docker Desktop's WSL2 network
driver severs [a connection] instantly on interface removal ... is a real question
I have not measured on this host" -- and `tests/test_patch_sandbox.py` is that
measurement, with a positive control so a pass cannot be mistaken for a harness
that never had a route to begin with.

**A follow-up adversarial review (2026-08-16) measured the question this module
had left open on purpose: whether a socket already open before `disconnect_network`
is called can keep delivering.** It can, for the better part of a second (0.92-1.5s
measured, sustained real transport, not a few buffered bytes) -- because `docker
network disconnect` blocks on the engine tearing the interface down, and nothing
stops the process on the other end of an already-open socket from calling
`sendall()` again while that teardown is in flight.
`tests/test_patch_sandbox.py::test_disconnect_network_does_not_stop_an_already_open_socket`
characterizes this directly against a real container and a real listener, and stays
green permanently -- it is not a RED test awaiting a fix inside `disconnect_network`.

**Two in-place fixes were tried against this host's real Docker Desktop/WSL2
kernel before choosing the structural one, and neither closed the window:**

- `ss -K` (kill a specific socket via the kernel's `sock_diag` netlink interface),
  run inside the container via `docker exec`, with `--cap-add=NET_ADMIN` added to
  the container: fails outright. `RTNETLINK answers: Invalid argument` on every
  attempt, loopback and real bridge traffic alike, capability present or not. This
  WSL2 kernel build (6.18.33.1-microsoft-standard-WSL2) does not support the
  `sock_diag` destroy operation `ss -K` depends on.
- `conntrack -F` (flush the netfilter connection-tracking table): the command
  itself succeeds, but has no effect on an already-established connection over a
  user-defined bridge network -- flushing conntrack clears NAT/tracking state, not
  the socket, and this traffic was not going through NAT to begin with. Measured
  directly: a listener kept counting incoming chunks across the flush with no
  interruption.

**What does close the window, also measured rather than assumed: destroying the
container outright.** `docker kill` on a container mid-stream stops the listener's
byte count from advancing within about a second and the listener sees a clean EOF
-- because the *process* is gone, not because its socket was individually reset.
`tests/test_patch_sandbox.py::test_networked_container_receives_nothing_after_it_is_torn_down`
proves it end to end.

**This module originally sketched a risky/safe container *pair* as the shape a live patch run
would use this destroy-based close through**: a networked install phase, destroyed once its
output was copied out (`copy_between_containers`), handing off to a `network="none"` safe phase
that never had a route to leak from. `DockerSdkRunner` (`sync.runner.docker_sdk`, B97 Decision 1)
hosts the live patch run a different way -- two containers alive together on an
`isolated_network.isolated_network` `--internal` network, with a forward proxy on one of them and
never a destroy-and-copy handoff between them -- because the sandboxed container never holds an
open route to anywhere but the proxy in the first place, so there is no already-open socket to
close by destroying anything. `copy_between_containers` is deleted (`M14-W411`) rather than kept
beside a design that does not call it: nothing else in this tree does a networked-install-then-
safe-verify split, and CLAUDE.md's "wait for the caller" rule is explicit that an unreached
primitive is debt with no asset behind it, not a hedge.

**What this module does not yet do, on purpose, rather than by oversight:**

- Grant the rest of mitigation 5. `ephemeral_container` runs a container non-root only because
  the image's own `USER` directive says so -- it passes no `--read-only` and enforces no
  per-container wall-clock kill, so a caller wanting either still has to ask for it and
  `ephemeral_container` still cannot grant it.
- Solve the credential passlist by itself. `build_container_env` below only
  achieves exclusion where it is used at a boundary that starts a process with no
  inherited environment -- a `docker exec` call against a freshly created
  container. It is not a general-purpose filter: passing a similarly-named `env=`
  to `ClaudeAgentOptions` does **not** exclude anything, a verified finding
  recorded in this module's tests rather than asserted here. See
  `claude_agent_sdk/_internal/transport/subprocess_cli.py:689-695`: `options.env`
  is merged on top of `dict(os.environ)`, not substituted for it, so every
  variable the parent process holds reaches the CLI regardless of what a caller
  names in `env=`. The container boundary is not a nicer way to do the same
  filtering the SDK could already do -- it is the only place the filtering is
  real.
"""

from __future__ import annotations

import os
import posixpath
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

_DOCKER_TIMEOUT_SECONDS = 30
_PROBE_TIMEOUT_SECONDS = 15

# Platform plumbing only, named the way `sync.verify.replay._ENVIRONMENT_ALLOWLIST`
# is: start from nothing and say what reaches the boundary, rather than copying the
# parent process wholesale and trying to subtract what looks sensitive afterward.
# `PYTHONIOENCODING` carries CLAUDE.md's own rule about a child choosing its own
# encoding -- the container's Python tooling needs it exactly as any other child
# subprocess in this repository does.
ENVIRONMENT_ALLOWLIST = ("PATH", "PYTHONIOENCODING")


@dataclass(frozen=True)
class Container:
    """One running sandbox container. `id` is the full ID `docker create` returned."""

    id: str


@dataclass(frozen=True)
class ProbeResult:
    """Whether a connect attempt made *inside* the container succeeded, and the
    raw output that says why -- diagnostic, not data, hence not required to be
    stable across Docker/Python versions.
    """

    reachable: bool
    detail: str


def _docker(*args: str, timeout: float = _DOCKER_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def build_container_env(auth_env: dict[str, str] | None = None) -> dict[str, str]:
    """The environment a sandboxed process should start with, built from an empty
    dict rather than from `os.environ`.

    The direction is the security property, the same one `sync.verify.replay
    ._environment` already established for the replay harness: copying the
    parent's environment and removing what looks sensitive is a denylist, and a
    denylist is one unanticipated variable name away from handing a control-plane
    credential to code running on a customer's behalf. Starting empty means
    `SYNC_GRAPH_DSN`, `SYNC_WEBHOOK_SECRET` and `SYNC_FEED_SIGNING_KEY` are absent
    because nothing named them, not because something excluded them.

    `auth_env` is the caller's problem to populate, not this function's: what
    credential the Claude Agent SDK's own CLI needs to reach Anthropic's API is
    unverified in this tree (`CLAUDE.md`'s model-configuration section documents
    `ClaudeAgentOptions` in full and it is not `env`-backed auth; no
    `ANTHROPIC_API_KEY` reference exists anywhere in `src/`, and the one
    environment snapshot taken while writing this module carried no `ANTHROPIC_*`
    variable at all -- only `CLAUDE_CODE_EXECPATH`, pointing at an already-
    authenticated `claude` binary, the same shape `CLAUDE.md` describes for `gh`).
    Naming that credential here would assert a fact nobody has confirmed.
    """
    environment = {name: os.environ[name] for name in ENVIRONMENT_ALLOWLIST if name in os.environ}
    if auth_env:
        environment.update(auth_env)
    return environment


@contextmanager
def ephemeral_container(
    image: str, network: str = "bridge", *, add_host: str | None = None,
) -> Iterator[Container]:
    """A running container for one phase of one patch attempt, always removed on
    exit.

    Created attached to `network` -- Docker's own default `bridge` unless a
    caller names something else. `DockerSdkRunner` names an
    `isolated_network.isolated_network` `--internal` network for both of its
    containers instead of either extreme: unlike `bridge`, it has no route out to
    the internet, and unlike `"none"`, the proxy and the sandboxed container can
    still reach each other on it. `"none"` and `disconnect_network` remain useful
    on their own terms -- a container created with `network="none"` gets
    `[Errno 101] Network is unreachable` on its first connect attempt, proven
    directly against this host, and `disconnect_network` removes a *running*
    container's route to block future connection attempts (see this module's
    docstring for what it does not stop). The container's only process is
    `sleep infinity`; nothing customer-facing is its entrypoint, and everything
    this module does to it happens through `docker exec`.

    `add_host`, passed straight to `docker create --add-host`, exists for one
    caller: a container on `isolated_network.isolated_network`'s `--internal`
    network carries no default gateway and no `host.docker.internal` resolution
    at all -- measured, not assumed, in `tests/test_isolated_network.py`.
    `--add-host=host.docker.internal:host-gateway` restores reachability to the
    host specifically, without opening a route to anything else
    (`tests/test_patch_sandbox.py::
    test_add_host_reaches_the_docker_desktop_gateway_without_opening_the_internet`
    proves both halves). `None` by default because every other caller of this
    function has no host to reach and no reason to widen what the container can
    resolve.

    Removal is unconditional (`finally`), so a probe or an assertion raising
    inside the `with` block still leaves no container behind for the next test
    or the next patch attempt to collide with. That same unconditional removal
    is what closes B97's cutover race for a risky-phase container: destroying it
    ends every process running inside, not merely its route.
    """
    name = f"sync-patch-sandbox-{uuid.uuid4().hex[:12]}"
    args = ["create", "--name", name, "--network", network]
    if add_host is not None:
        args += ["--add-host", add_host]
    args += [image, "sleep", "infinity"]
    create = _docker(*args)
    if create.returncode != 0:
        raise RuntimeError(f"docker create failed: {create.stderr.strip()}")
    container_id = create.stdout.strip()
    start = _docker("start", container_id)
    if start.returncode != 0:
        _docker("rm", "-f", container_id)
        raise RuntimeError(f"docker start failed: {start.stderr.strip()}")
    try:
        yield Container(id=container_id)
    finally:
        _docker("rm", "-f", container_id)


def _attach_network_args(network: str, container_id: str) -> list[str]:
    return ["network", "connect", network, container_id]


def attach_network(container: Container, network: str) -> None:
    """Give an already-running container a second network, alongside whatever it was created
    with -- B97 Decision 1's proxy container: the isolated network it shares with the sandboxed
    container is named at `ephemeral_container` time, and its own egress leg out to Anthropic is
    attached after, since `docker create --network` takes exactly one name.
    """
    result = _docker(*_attach_network_args(network, container.id))
    if result.returncode != 0:
        raise RuntimeError(f"docker network connect failed: {result.stderr.strip()}")


def disconnect_network(container: Container, network: str = "bridge") -> None:
    """Detach `container` from `network`, and do not return until the engine
    confirms it. Blocks *new* connection attempts from `container`; does **not**
    stop one already open when it is called -- see below and this module's
    docstring for the measurement and why this function is not the mechanism
    that closes B97's exfiltration boundary on its own.

    `docker network disconnect` is a synchronous Docker Engine API call: the CLI
    blocks until the engine reports the container's interface pulled off the
    bridge. A caller that waits for this to return before starting the risky
    phase is not racing the disconnect against anything -- this is the only
    writer of "when does the risky phase start," and it sequences that phase
    strictly after the state change is confirmed rather than assumed to have
    happened.

    What this does not establish -- and an earlier version of this docstring
    underestimated, calling it "a few buffered bytes": a connection already open
    before this call keeps delivering real, sustained data for the better part
    of a second while the engine call is in flight (0.92-1.5s measured; see this
    module's docstring). `tests/test_patch_sandbox.py::
    test_disconnect_network_does_not_stop_an_already_open_socket` proves it
    directly. A caller that needs the exfiltration boundary -- not merely "no
    new sockets" -- does not call this function on a container it plans to keep
    running; it destroys the container outright
    (`test_networked_container_receives_nothing_after_it_is_torn_down`), or, as
    `DockerSdkRunner` does, never gives the container a route to lose in the
    first place.
    """
    result = _docker("network", "disconnect", network, container.id)
    if result.returncode != 0:
        raise RuntimeError(f"docker network disconnect failed: {result.stderr.strip()}")


# Run inside the container via `docker exec`, so the connect attempt is made from
# the container's own network namespace and not from the host's. Exit code is the
# whole of the signal a caller needs; the printed line is diagnostic only.
_PROBE_SCRIPT = (
    "import socket, sys\n"
    "try:\n"
    "    socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5).close()\n"
    "except Exception as exc:\n"
    "    print(f'UNREACHABLE: {exc}')\n"
    "    sys.exit(1)\n"
    "print('REACHABLE')\n"
)


def _parse_probe_output(returncode: int, stdout: str, stderr: str) -> ProbeResult:
    """The pure parsing step `probe_connect` defers to, split out so a test can
    pin the exact input/output contract without spawning Docker.

    `reachable` requires the success marker to be the *whole* trimmed stdout, not
    merely present as a substring: `"REACHABLE" in stdout` is true on both the
    success line and the failure line `_PROBE_SCRIPT` prints
    (`"UNREACHABLE: ..."` contains `"REACHABLE"`), so that check did no work --
    correctness rested entirely on `returncode`, coincidentally, because
    `_PROBE_SCRIPT` always exits non-zero on its failure path. An exact match
    makes the stdout check mean what its presence implies, instead of relying on
    a coincidence between two independent signals.
    """
    detail = (stdout + stderr).strip()
    return ProbeResult(reachable=returncode == 0 and stdout.strip() == "REACHABLE", detail=detail)


def probe_connect(container: Container, host: str, port: int) -> ProbeResult:
    """Whether `container` can open a socket to `host:port` right now.

    A real connect attempt made inside the container's own network namespace via
    `docker exec` -- evidence about what this container can actually reach, not
    an assertion derived from which `--network` flag created it.
    """
    try:
        result = _docker(
            "exec", container.id, "python3", "-c", _PROBE_SCRIPT, host, str(port),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # A hung connect reads the same as a refused one for this caller's
        # purposes: no route reached `host:port` within the time this is willing
        # to wait, which `docker exec`'s own timeout can outlast when a dropped
        # packet is retried rather than immediately rejected.
        return ProbeResult(reachable=False, detail=f"docker exec timed out after {_PROBE_TIMEOUT_SECONDS}s")
    return _parse_probe_output(result.returncode, result.stdout, result.stderr)


def copy_into_container(container: Container, host_path: str, container_path: str) -> None:
    """Move `host_path` (a file or a directory) from the host straight into `container` at
    `container_path` -- B97 Decision 1's own need: the driver, the gate and the fence files, and
    the finding's clone, all have to reach the sandboxed container from the host that cloned the
    repository, not from another container.

    No staging directory: `docker cp` already reaches the host filesystem directly on this side.
    A container-to-container copy would need one, since neither endpoint is the host -- this
    module no longer has that shape (`copy_between_containers`, deleted at `M14-W411`; see this
    module's own docstring for why).
    """
    parent = posixpath.dirname(container_path) or "/"
    mkdir = _docker("exec", container.id, "mkdir", "-p", parent)
    if mkdir.returncode != 0:
        raise RuntimeError(f"mkdir -p {parent} in {container.id} failed: {mkdir.stderr.strip()}")
    copy_in = _docker("cp", host_path, f"{container.id}:{container_path}")
    if copy_in.returncode != 0:
        raise RuntimeError(f"docker cp into {container.id}:{container_path} failed: {copy_in.stderr.strip()}")


def copy_out_of_container(container: Container, container_path: str, host_path: str) -> None:
    """Move `container_path` out of `container` to `host_path` on the host -- the return half of
    `copy_into_container`: a patch attempt's clone goes back to the host path `AgentRemediator`
    already holds, so `static_verify` and everything after it read the same tree they always did.
    """
    copy_out = _docker("cp", f"{container.id}:{container_path}", host_path)
    if copy_out.returncode != 0:
        raise RuntimeError(f"docker cp out of {container.id}:{container_path} failed: {copy_out.stderr.strip()}")


def exec_in_container(
    container: Container,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    workdir: str | None = None,
    detach: bool = False,
) -> subprocess.CompletedProcess[str]:
    """`docker exec` with the flags a caller outside this module cannot reach otherwise --
    B97 Decision 1's `sync.runner.docker_sdk` needs `-e`, `-w` and `-d`, and reaching into
    this module's own `_docker` for them would couple a caller to a private helper rather
    than to a stated contract.
    """
    flags: list[str] = []
    if detach:
        flags.append("-d")
    for key, value in (env or {}).items():
        flags += ["-e", f"{key}={value}"]
    if workdir is not None:
        flags += ["-w", workdir]
    return _docker("exec", *flags, container.id, *args)

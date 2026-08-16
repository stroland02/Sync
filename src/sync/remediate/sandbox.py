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

**What this module does not yet do, on purpose, rather than by oversight:**

- Host a live patch run. `ephemeral_container` and `disconnect_network` are the
  two primitives the design calls for, proven independently. Routing the agent's
  own model traffic through a narrower allowlist after the cutoff -- a local
  forward proxy reachable only to Anthropic's API, so the container is never on
  literally zero network while an agent turn is in flight -- is unbuilt. A
  container disconnected with today's code has no route for anything, including
  the SDK's own traffic, and cannot yet host a live agent turn. `docker/patch-
  sandbox/Dockerfile` describes the image this would run; nothing in this tree
  yet builds an agent session inside it.
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
def ephemeral_container(image: str, network: str = "bridge") -> Iterator[Container]:
    """A running container for one patch attempt, always removed on exit.

    Created attached to `network` -- Docker's own default `bridge` unless a
    caller names an install-specific network -- because the install phase this
    design describes needs outbound internet and `disconnect_network` is the
    mechanism that takes it away afterward, not the absence of a network at
    creation time. The container's only process is `sleep infinity`; nothing
    customer-facing is its entrypoint, and everything this module does to it
    happens through `docker exec`.

    Removal is unconditional (`finally`), so a probe or an assertion raising
    inside the `with` block still leaves no container behind for the next test
    or the next patch attempt to collide with.
    """
    name = f"sync-patch-sandbox-{uuid.uuid4().hex[:12]}"
    create = _docker("create", "--name", name, "--network", network, image, "sleep", "infinity")
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


def disconnect_network(container: Container, network: str = "bridge") -> None:
    """Detach `container` from `network`, and do not return until the engine
    confirms it.

    `docker network disconnect` is a synchronous Docker Engine API call: the CLI
    blocks until the engine reports the container's interface pulled off the
    bridge. A caller that waits for this to return before starting the risky
    phase is not racing the disconnect against anything -- this is the only
    writer of "when does the risky phase start," and it sequences that phase
    strictly after the state change is confirmed rather than assumed to have
    happened.

    What this does not establish, and `tests/test_patch_sandbox.py`'s docstring
    says so rather than leaving it implicit: whether a connection that was
    already open before this call can still deliver a few buffered bytes during
    the transition. The probe here measures a *new* connect attempt made after
    this returns, which is the property the close condition asks for -- "a patch
    run cannot open a socket to a host Sync did not name" is about opening one,
    not about a byte in flight on one already open.
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
    output = (result.stdout + result.stderr).strip()
    return ProbeResult(reachable=result.returncode == 0 and "REACHABLE" in result.stdout, detail=output)

"""A Docker network with no route out at all -- the third primitive B97's forward proxy
design calls for, alongside `sandbox.ephemeral_container` and `forward_proxy_server.running_proxy`.

`docker network create --internal` removes the network's own gateway to the internet at the
Docker Engine level, not by convention: a container attached to one has no route anywhere except
another container on the same network, structurally, the same way `ephemeral_container`'s
`network="none"` has no route at all. What makes this usable rather than merely isolated is a
fact `tests/test_patch_sandbox.py` already established for a different reason:
`host.docker.internal` is Docker Desktop's own bridge to the host process, not internet routing,
so a container here can still reach `forward_proxy_server.running_proxy` even though `--internal`
gives it nowhere else to go. `tests/test_isolated_network.py` proves both halves against a real
Docker daemon rather than asserting either from this docstring.
"""

from __future__ import annotations

import subprocess
import uuid
from contextlib import contextmanager
from typing import Iterator

_DOCKER_TIMEOUT_SECONDS = 30


def _docker(*args: str, timeout: float = _DOCKER_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _create_args(name: str) -> list[str]:
    """The `docker network create` invocation, split out so `--internal` is pinned by a test
    that needs no daemon rather than only by one that does.
    """
    return ["network", "create", "--internal", name]


@contextmanager
def isolated_network(name: str | None = None) -> Iterator[str]:
    """A Docker network with `--internal`, yields its name, removed on exit.

    `name` defaults to a fresh one per call, the same reason `ephemeral_container` generates its
    own container name rather than taking one from a caller: a fixed name is one concurrent test
    or one concurrent patch attempt away from colliding with another network that has not been
    torn down yet. Removal is unconditional (`finally`), matching `ephemeral_container`'s own
    unconditional `docker rm -f` -- a network left behind by a raised assertion is one more thing
    the next run has to notice and clean up by hand.
    """
    network_name = name or f"sync-patch-sandbox-{uuid.uuid4().hex[:12]}"
    create = _docker(*_create_args(network_name))
    if create.returncode != 0:
        raise RuntimeError(f"docker network create failed: {create.stderr.strip()}")
    try:
        yield network_name
    finally:
        _docker("network", "rm", network_name)

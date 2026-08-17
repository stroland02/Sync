"""B97's third slice: a Docker network with no route out at all.

The design (`docs/superpowers/specs/2026-08-17-sync-b97-forward-proxy-design.md`) calls for the
sandboxed container to reach `forward_proxy_server.running_proxy` and nothing else. `--internal`
on a Docker network structurally removes the network's own gateway to the internet -- proven
below the same way `test_patch_sandbox.py` proves `disconnect_network`, against a real running
container rather than a configuration file.

**What this file does not yet prove, and why -- a corrected assumption rather than a gap left
quiet.** The working design going in was that `--add-host=host.docker.internal:host-gateway` on
the sandboxed container would let it reach `running_proxy` bound on the host, over the same
`--internal` network that blocks everything else. Measured directly and it does not:
`--add-host` writes an `/etc/hosts` entry, which is name resolution only, and `--internal`'s
routing restriction sits a layer below that. `host.docker.internal` resolves to a real address
(`tests/test_patch_sandbox.py::
test_add_host_reaches_the_docker_desktop_gateway_without_opening_the_internet` proves the
resolution and the still-blocked internet both), but a container on this network has no route to
that address or to anything else outside its own local subnet -- its own `/proc/net/route`
carries no gateway at all. Resolving a name and being able to reach it are two different facts,
and this repository's design nearly shipped having conflated them.

So the proxy cannot be a bare host process reached from an `--internal` network. It has to be a
container on the *same* isolated network as the sandboxed container -- reachable there by
construction, the way any two containers sharing one Docker network reach each other -- with a
second network attachment of its own into something that can actually leave. That composition,
and the test proving it, is the next unit, not this one.

Requires a working Docker daemon serving Linux containers, the same dependency
`test_patch_sandbox.py` already has.
"""

from __future__ import annotations

import pytest

from sync.remediate import sandbox
from sync.remediate.isolated_network import isolated_network

_TEST_IMAGE = "python:3.12-slim"


def test_isolated_network_names_it_internal():
    """The pure part: the Docker CLI invocation this module builds carries `--internal`, without
    needing a daemon to check it against.
    """
    from sync.remediate.isolated_network import _create_args

    args = _create_args("sync-b97-test-network")
    assert "--internal" in args


@pytest.mark.docker
def test_a_container_on_an_isolated_network_cannot_reach_the_internet():
    """Positive control first, same discipline `test_container_network_cutoff_blocks_arbitrary_
    egress` holds `disconnect_network` to: prove this host's Docker can reach the internet before
    trusting a later failure to mean the isolation worked rather than a harness with no route to
    begin with.
    """
    with sandbox.ephemeral_container(image=_TEST_IMAGE) as control:
        baseline = sandbox.probe_connect(control, "1.1.1.1", 443)
        assert baseline.reachable, f"positive control failed: {baseline.detail}"

    with isolated_network() as network_name:
        with sandbox.ephemeral_container(image=_TEST_IMAGE, network=network_name) as container:
            result = sandbox.probe_connect(container, "1.1.1.1", 443)
            assert not result.reachable, f"expected no route out, got: {result.detail}"


@pytest.mark.docker
def test_isolated_network_is_removed_on_exit():
    with isolated_network() as network_name:
        listing = subprocess_run_docker("network", "inspect", network_name)
        assert listing.returncode == 0, "expected the network to exist while the context is open"

    listing_after = subprocess_run_docker("network", "inspect", network_name)
    assert listing_after.returncode != 0, "expected the network to be gone once the context exited"


def subprocess_run_docker(*args: str):
    import subprocess

    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=15,
    )

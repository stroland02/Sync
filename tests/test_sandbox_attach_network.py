"""`sandbox.attach_network`: a second network on an already-running container -- B97 Decision 1's
proxy container needs the isolated network (shared with the sandboxed container) and its own
egress leg, and `docker create --network` only accepts one name at creation time.

Own file rather than added to `test_patch_sandbox.py`: Lane C owns that file for B183.
"""

from __future__ import annotations

import subprocess

import pytest

from sync.remediate import sandbox
from sync.remediate.isolated_network import isolated_network

_TEST_IMAGE = "python:3.12-slim"


def test_attach_network_names_the_second_call():
    args = sandbox._attach_network_args("sync-b97-test-network", "some-container-id")
    assert args[:2] == ["network", "connect"]
    assert "sync-b97-test-network" in args
    assert "some-container-id" in args


@pytest.mark.docker
def test_a_dual_homed_container_keeps_its_route_out_after_joining_the_isolated_network():
    """The proxy's own egress leg, proven to survive the isolated attachment."""
    with isolated_network() as network_name:
        with sandbox.ephemeral_container(image=_TEST_IMAGE) as proxy:
            sandbox.attach_network(proxy, network_name)
            result = sandbox.probe_connect(proxy, "1.1.1.1", 443)
            assert result.reachable, (
                f"expected the container's original bridge route to survive joining an "
                f"isolated network as a second attachment, got: {result.detail}"
            )


@pytest.mark.docker
def test_an_isolated_only_container_reaches_the_dual_homed_one_over_that_network():
    """The sandboxed side's whole reason to exist: a real route to a real listener, over the
    isolated network only.
    """
    with isolated_network() as network_name:
        with sandbox.ephemeral_container(image=_TEST_IMAGE, network=network_name) as proxy:
            sandbox.attach_network(proxy, "bridge")
            inspect = subprocess.run(
                ["docker", "inspect", "-f",
                 f'{{{{(index .NetworkSettings.Networks "{network_name}").IPAddress}}}}', proxy.id],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            proxy_ip = inspect.stdout.strip()
            assert proxy_ip, f"proxy carried no address on {network_name}: {inspect.stderr}"

            listener = subprocess.run(
                ["docker", "exec", "-d", proxy.id, "python3", "-m", "http.server", "8080"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            assert listener.returncode == 0, f"failed to start the listener: {listener.stderr.strip()}"
            import time
            time.sleep(0.5)

            with sandbox.ephemeral_container(image=_TEST_IMAGE, network=network_name) as sandboxed:
                result = sandbox.probe_connect(sandboxed, proxy_ip, 8080)
                assert result.reachable, (
                    f"expected the isolated-only container to reach the dual-homed one over "
                    f"their shared network, got: {result.detail}"
                )

                internet = sandbox.probe_connect(sandboxed, "1.1.1.1", 443)
                assert not internet.reachable, (
                    "the sandboxed side must still have no route to the internet even once a "
                    f"peer on its network does, got: {internet.detail}"
                )

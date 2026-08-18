"""`DockerSdkRunner` (B97 Decision 1), the orchestration logic verified against mocked `sandbox`
and `isolated_network` calls rather than real Docker or a real model call.

**Scope, deliberately narrow.** This proves the sequence and the arguments -- the proxy gets the
credential, the sandboxed container never does, the repo copies in and back out, a failed result
raises. It does not prove containers actually isolate network traffic (`test_sandbox_
attach_network.py` and `test_isolated_network.py` already do, against real Docker) and it does
not make a real call to `claude_agent_sdk.query` (no vendor or model API in tests,
`.claude/rules/test-discipline.md`). A real end-to-end run needs a real credential and a real
spend decision that is not this test file's to make.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sync.remediate import sandbox
from sync.runner.docker_sdk import DockerSdkRunner


class _FakeContainer:
    def __init__(self, id_: str) -> None:
        self.id = id_


@pytest.fixture
def mocked(monkeypatch):
    calls: list = []

    def fake_isolated_network(name=None):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            calls.append(("isolated_network",))
            yield "sync-b97-net-abc123"

        return cm()

    def fake_ephemeral_container(image, network="bridge", *, add_host=None):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            container = _FakeContainer(f"container-for-{network}")
            calls.append(("ephemeral_container", image, network))
            yield container

        return cm()

    def fake_attach_network(container, network):
        calls.append(("attach_network", container.id, network))

    def fake_exec_in_container(container, args, *, env=None, workdir=None, detach=False):
        calls.append(("exec_in_container", container.id, tuple(args), env, workdir, detach))
        return MagicMock(returncode=0, stderr="")

    def fake_copy_into_container(container, host_path, container_path):
        calls.append(("copy_into_container", container.id, host_path, container_path))

    def fake_copy_out_of_container(container, container_path, host_path):
        calls.append(("copy_out_of_container", container.id, container_path, host_path))
        if container_path.endswith("result.json"):
            Path(host_path).write_text(json.dumps({"ok": True, "error": None}), encoding="utf-8")

    def fake_container_address(self, container, network):
        calls.append(("container_address", container.id, network))
        return "10.10.0.2"

    monkeypatch.setattr("sync.runner.docker_sdk.isolated_network", fake_isolated_network)
    monkeypatch.setattr(sandbox, "ephemeral_container", fake_ephemeral_container)
    monkeypatch.setattr(sandbox, "attach_network", fake_attach_network)
    monkeypatch.setattr(sandbox, "exec_in_container", fake_exec_in_container)
    monkeypatch.setattr(sandbox, "copy_into_container", fake_copy_into_container)
    monkeypatch.setattr(sandbox, "copy_out_of_container", fake_copy_out_of_container)
    monkeypatch.setattr(DockerSdkRunner, "_container_address", fake_container_address)

    return calls


def test_the_proxy_gets_the_credential_and_the_sandbox_never_does(mocked, tmp_path):
    runner = DockerSdkRunner(image="sync-patch-sandbox:test", credential="sk-real-secret")
    runner.run("do the patch", tmp_path, "finding=f-1 repo=acme")

    exec_calls = [c for c in mocked if c[0] == "exec_in_container"]
    proxy_start = next(c for c in exec_calls if "run_proxy.py" in c[2])
    driver_start = next(c for c in exec_calls if "driver.py" in c[2])

    assert proxy_start[3]["SYNC_PROXY_CREDENTIAL"] == "sk-real-secret"
    # The sandboxed container's own exec call carries no credential anywhere in its env --
    # only ANTHROPIC_BASE_URL, pointing it at the proxy rather than handing it a key.
    assert "SYNC_PROXY_CREDENTIAL" not in (driver_start[3] or {})
    assert "sk-real-secret" not in json.dumps(driver_start[3])


def test_the_sandboxed_container_is_pointed_at_the_proxys_own_address(mocked, tmp_path):
    runner = DockerSdkRunner(image="sync-patch-sandbox:test", credential="sk-real-secret")
    runner.run("do the patch", tmp_path, "finding=f-1 repo=acme")

    exec_calls = [c for c in mocked if c[0] == "exec_in_container"]
    driver_start = next(c for c in exec_calls if "driver.py" in c[2])
    assert driver_start[3]["ANTHROPIC_BASE_URL"] == "http://10.10.0.2:8080"


def test_the_proxy_container_is_attached_to_the_isolated_network_and_bridge(mocked, tmp_path):
    runner = DockerSdkRunner(image="sync-patch-sandbox:test", credential="sk-real-secret")
    runner.run("do the patch", tmp_path, "finding=f-1 repo=acme")

    ephemeral_calls = [c for c in mocked if c[0] == "ephemeral_container"]
    # The proxy is created on the default network (bridge) first, per ephemeral_container's own
    # default, then attach_network adds the isolated one -- the sandboxed container is created
    # directly on the isolated network, needing no second attachment.
    assert ("ephemeral_container", "sync-patch-sandbox:test", "bridge") in ephemeral_calls
    assert (
        "ephemeral_container", "sync-patch-sandbox:test", "sync-b97-net-abc123"
    ) in ephemeral_calls
    attach_calls = [c for c in mocked if c[0] == "attach_network"]
    assert any(c[2] == "sync-b97-net-abc123" for c in attach_calls)


def test_the_repo_clone_is_copied_in_and_the_result_copied_back_out(mocked, tmp_path):
    runner = DockerSdkRunner(image="sync-patch-sandbox:test", credential="sk-real-secret")
    runner.run("do the patch", tmp_path, "finding=f-1 repo=acme")

    copy_in = [c for c in mocked if c[0] == "copy_into_container"]
    copy_out = [c for c in mocked if c[0] == "copy_out_of_container"]

    assert any(c[2] == str(tmp_path) and c[3] == "/workspace/repo" for c in copy_in)
    assert any(c[2] == "/workspace/repo" and c[3] == str(tmp_path) for c in copy_out)


def test_a_failed_result_raises_with_the_drivers_own_error(mocked, monkeypatch, tmp_path):
    def fake_copy_out_of_container(container, container_path, host_path):
        if container_path.endswith("result.json"):
            Path(host_path).write_text(
                json.dumps({"ok": False, "error": "this call is refused: not on the permitted list"}),
                encoding="utf-8",
            )

    monkeypatch.setattr(sandbox, "copy_out_of_container", fake_copy_out_of_container)

    runner = DockerSdkRunner(image="sync-patch-sandbox:test", credential="sk-real-secret")
    with pytest.raises(RuntimeError, match="refused"):
        runner.run("do the patch", tmp_path, "finding=f-1 repo=acme")

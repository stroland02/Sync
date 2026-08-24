"""B97 Decision 1: a `PatchRunner` that drives the agent turn inside the sandbox instead of the
operator's own process.

`sync.core.protocols.PatchRunner` is the whole seam this needs: `AgentRemediator.propose` calls
`self._runner.run(prompt, repo_path, identity)` and reads the clone afterwards, never the return
value, so a runner that edits the clone by a different mechanism is a complete substitute without
touching `AgentRemediator` at all. `AgentRemediator.__init__` now selects this class over
`ClaudeSdkRunner` when `SANDBOX_ENV` ("SYNC_PATCH_SANDBOX") is `"1"`, through
`runner_from_environment` below -- unset, which is every deployment today, construction is
unchanged. **Selecting this class is not the same claim as running it in production.**
`runner_from_environment` refuses to build one at all when `_CREDENTIAL_ENV` is unset, because
sourcing the sandbox's own Anthropic credential is still the open piece: no live patch run has
gone through this class, opting a real deployment in needs that credential question answered
first, and answering it is an owner decision this module takes as given rather than invents.

**What this closes, checked against `docs/superpowers/specs/2026-07-25-sync-threat-model.md`'s
own ledger:** mitigation 1 (credential-free sandbox) and mitigation 3 (no network egress except
the one allowlisted upstream) both become real once this runner is the one `AgentRemediator`
calls -- the sandboxed container never holds `SYNC_PROXY_CREDENTIAL`, it is set only on the proxy
container's own `docker exec`, and the sandboxed container's only network is the `--internal` one
it shares with nothing but the proxy.

**What this does not close, named rather than left implicit.** Mitigation 5 (non-root, read-only
root, wall-clock kill): `ephemeral_container` still passes no `--read-only` and no per-run
wall-clock kill of the container itself -- the image runs as `sandbox` (non-root) by its own
`USER` directive, which is the one third of mitigation 5 this runner inherits for free, not one
it adds. A caller that wants read-only and a hard timeout still has to ask `ephemeral_container`
for them, and `ephemeral_container` still cannot grant either. **Do not read
`CLAUDE.md`'s qualified sentence about executing customer code as upgraded because this class
exists** -- it narrows the credential and network exposure the threat model ranks first and
second; it does not touch the third.
"""

from __future__ import annotations

import json
import logging
import os
import posixpath
import tempfile
from pathlib import Path

from sync.remediate import sandbox
from sync.remediate.isolated_network import isolated_network
from sync.remediate.sandbox_image import ensure_image_built

log = logging.getLogger(__name__)

# `AgentRemediator.__init__` reads this; "1" opts a deployment into `DockerSdkRunner` in place
# of `ClaudeSdkRunner`. Unset (the default everywhere today), behaviour is unchanged.
SANDBOX_ENV = "SYNC_PATCH_SANDBOX"

# Names the credential `runner_from_environment` forwards to the proxy container, which is what
# the proxy attaches to every request it forwards to Anthropic (`forward_proxy.build_forward_request`)
# -- the same credential a non-sandboxed run authenticates with, sourced here rather than assumed,
# because Ruling 7 makes which one that is an owner decision.
_CREDENTIAL_ENV = "SYNC_PATCH_SANDBOX_CREDENTIAL"

# Overrides the image tag `ensure_image_built` would otherwise compute and build/inspect for.
# Unset is the normal path: `runner_from_environment` calls `ensure_image_built()` itself, so a
# pre-warmed image costs one `docker image inspect` and a cold one is built on the spot.
_IMAGE_ENV = "SYNC_PATCH_SANDBOX_IMAGE"


def runner_from_environment() -> "DockerSdkRunner":
    """The production `DockerSdkRunner`, configured from the environment rather than from a
    caller who would otherwise have to source the same two values themselves.

    Refuses outright when `_CREDENTIAL_ENV` is unset, rather than falling back to nothing or to
    a guess -- `ClaudeSdkRunner`'s own production path authenticates through an already-signed-in
    CLI binary (`CLAUDE_CODE_EXECPATH`), not a portable credential string, so there is no existing
    value this factory could read instead. Sourcing the sandbox's own credential is the
    still-open piece of B97 named in this module's own docstring and in the threat model's
    Ruling 7; this factory names the gap rather than papering over it with an invented default.
    """
    credential = os.environ.get(_CREDENTIAL_ENV)
    if not credential:
        raise RuntimeError(
            f"{_CREDENTIAL_ENV} is not set. DockerSdkRunner forwards this value to the proxy "
            f"container, which attaches it to every request it forwards to Anthropic in place "
            f"of whatever the sandboxed container sent -- it is the sandboxed run's real "
            f"upstream credential, not a lesser one, and which credential that should be is an "
            f"owner decision (docs/superpowers/specs/2026-07-25-sync-threat-model.md's Ruling 7) "
            f"this factory takes as given rather than invents."
        )
    image = os.environ.get(_IMAGE_ENV) or ensure_image_built()
    return DockerSdkRunner(image=image, credential=credential)

_REMEDIATE_DIR = Path(__file__).resolve().parents[1] / "remediate"
_DRIVER_DIR = Path(__file__).resolve().parents[3] / "docker" / "patch-sandbox"

_SANDBOX_WORKSPACE = "/workspace"
_SANDBOX_REPO_PATH = posixpath.join(_SANDBOX_WORKSPACE, "repo")
_SANDBOX_JOB_DIR = posixpath.join(_SANDBOX_WORKSPACE, ".sync-job")

_PROXY_PORT = 8080
_PROXY_CREDENTIAL_HEADER = "x-api-key"

# The three files a sandboxed process may run, per `driver.py`'s own docstring -- nothing that
# imports `sync.core`, `sync.graph`, or reads a database credential.
_SANDBOX_MODULES = ("tool_gate.py", "tool_output.py", "untrusted.py")
_PROXY_MODULES = ("forward_proxy.py", "forward_proxy_server.py")


class DockerSdkRunner:
    """Drives the agent turn inside two ephemeral containers -- a proxy holding the real
    credential, and a sandboxed container that never does -- and raises the same vocabulary
    `ClaudeSdkRunner` does on a failed run, so `AgentRemediator` cannot tell the two apart from
    the outside.
    """

    def __init__(self, image: str, credential: str) -> None:
        # `credential` is read once, at construction, from wherever the caller's own account
        # policy names -- Ruling 7's boundary, restated rather than re-litigated here: which
        # Anthropic credential Sync authenticates with is an owner decision this class takes as
        # given, not one it makes.
        self._image = image
        self._credential = credential

    def run(
        self, prompt: str, repo_path: Path, identity: str,
        *, on_event=None, on_note=None,
    ) -> None:
        # Accepted so a recording caller does not fail construction of a sandboxed run, and
        # deliberately unused: the hooks execute inside the container, where no host recorder
        # can be invoked. The run's own log line says the feed is off rather than letting an
        # empty feed read as an idle agent -- the console's empty state names both nothings.
        if on_event is not None or on_note is not None:
            log.info("activity recording does not cross the container boundary; no feed for [%s]", identity)
        with isolated_network() as network_name:
            with sandbox.ephemeral_container(image=self._image) as proxy:
                sandbox.attach_network(proxy, network_name)
                self._start_proxy(proxy)
                proxy_ip = self._container_address(proxy, network_name)

                with sandbox.ephemeral_container(image=self._image, network=network_name) as sandboxed:
                    self._run_in_sandbox(sandboxed, proxy_ip, prompt, repo_path, identity)

    def _start_proxy(self, proxy: sandbox.Container) -> None:
        for name in _PROXY_MODULES:
            sandbox.copy_into_container(proxy, str(_REMEDIATE_DIR / name), f"{_SANDBOX_WORKSPACE}/{name}")
        sandbox.copy_into_container(
            proxy, str(_DRIVER_DIR / "run_proxy.py"), f"{_SANDBOX_WORKSPACE}/run_proxy.py"
        )
        start = sandbox.exec_in_container(
            proxy, ["python3", "run_proxy.py"],
            env={
                "SYNC_PROXY_CREDENTIAL": self._credential,
                "SYNC_PROXY_CREDENTIAL_HEADER": _PROXY_CREDENTIAL_HEADER,
                "SYNC_PROXY_PORT": str(_PROXY_PORT),
            },
            workdir=_SANDBOX_WORKSPACE,
            detach=True,
        )
        if start.returncode != 0:
            raise RuntimeError(f"failed to start the forward proxy: {start.stderr.strip()}")

    def _run_in_sandbox(
        self,
        sandboxed: sandbox.Container,
        proxy_ip: str,
        prompt: str,
        repo_path: Path,
        identity: str,
    ) -> None:
        for name in _SANDBOX_MODULES:
            sandbox.copy_into_container(sandboxed, str(_REMEDIATE_DIR / name), f"{_SANDBOX_WORKSPACE}/{name}")
        sandbox.copy_into_container(
            sandboxed, str(_DRIVER_DIR / "driver.py"), f"{_SANDBOX_WORKSPACE}/driver.py"
        )
        sandbox.copy_into_container(sandboxed, str(repo_path), _SANDBOX_REPO_PATH)

        with tempfile.TemporaryDirectory() as staging:
            job_path = os.path.join(staging, "job.json")
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"prompt": prompt, "identity": identity, "repo_path": _SANDBOX_REPO_PATH}, f
                )
            sandbox.copy_into_container(sandboxed, job_path, f"{_SANDBOX_JOB_DIR}/job.json")

        run = sandbox.exec_in_container(
            sandboxed, ["python3", "driver.py"],
            env={"ANTHROPIC_BASE_URL": f"http://{proxy_ip}:{_PROXY_PORT}"},
            workdir=_SANDBOX_WORKSPACE,
        )

        with tempfile.TemporaryDirectory() as staging:
            result_path = os.path.join(staging, "result.json")
            sandbox.copy_out_of_container(sandboxed, f"{_SANDBOX_JOB_DIR}/result.json", result_path)
            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)

        sandbox.copy_out_of_container(sandboxed, _SANDBOX_REPO_PATH, str(repo_path))

        if not result["ok"]:
            raise RuntimeError(result["error"])
        if run.returncode != 0:
            # The result file is the authority on why -- an exec that failed for a reason the
            # driver never got to report (an import error, a crash before it could write
            # result.json) still has to reach the caller as a failure, not a silent success.
            raise RuntimeError(f"driver exited {run.returncode} with no clean result: {run.stderr.strip()}")

    def _container_address(self, container: sandbox.Container, network: str) -> str:
        """The IP a container holds on one specific network, named rather than inferred --
        `docker inspect`'s `.NetworkSettings.Networks` is a map keyed by network name, and a
        dual-homed container carries a different address on each entry.
        """
        import subprocess

        inspect = subprocess.run(
            ["docker", "inspect", "-f",
             f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}', container.id],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        if inspect.returncode != 0:
            raise RuntimeError(f"docker inspect failed for {container.id} on {network}: {inspect.stderr.strip()}")
        address = inspect.stdout.strip()
        if not address:
            raise RuntimeError(f"{container.id} carries no address on {network}")
        return address

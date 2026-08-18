"""The one-command install, held against the files that implement it.

**The gap this closes was named directly: a Dockerfile and compose files existed and nothing
verified that one command brings the product up.** Two kinds of check are needed and only one of
them belongs here.

What is here is structural and fast: the compose file describes the product rather than a database,
the console is published on loopback rather than every interface, the entrypoint is reachable, and
the `npx` doorbell exists and points at something real. None of it needs Docker and none of it
takes measurable time, so every lane pays nothing for it.

**What is deliberately not here is the bring-up itself.** Actually running `docker compose up` and
asking the console for a page takes minutes, and `CI-W363` measured the whole suite at about three
minutes -- adding a container build to every lane's local gate would be the largest single tax in
the workspace, imposed on five lanes to protect one claim. That check runs in CI instead, as its
own job, where it is paid once per push rather than once per iteration. `.github/workflows/ci.yml`
carries it.

The division is the same one `.claude/rules/console-dev-loop.md` draws: where a rule is *tested* is
a separate question from where it *belongs*.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE = REPO_ROOT / "docker-compose.demo.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile"
ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"
PACKAGE_JSON = REPO_ROOT / "package.json"
DOORBELL = REPO_ROOT / "bin" / "sync-up.mjs"


def _compose() -> str:
    return COMPOSE.read_text(encoding="utf-8")


def _without_comments(text: str) -> str:
    """The file's instructions, without its prose.

    Both files here explain themselves at length, and the explanations name the very things
    these tests forbid -- the compose file says why it must not publish 5433, and says "5433"
    doing so. Asserting over the prose makes a test that fails on its own documentation.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_the_compose_file_brings_up_the_product_and_not_only_a_database():
    """The whole of the finding that prompted this: compose ran Postgres and nothing else.

    Asserted on the services rather than on a line count, because what matters is that something
    serves the product beside the database -- and that it is built from this repository rather
    than pulled, since no image is published yet.
    """
    text = _compose()

    assert re.search(r"^\s{2}postgres:", text, re.MULTILINE), "the database service is gone"
    assert re.search(r"^\s{2}sync:", text, re.MULTILINE), (
        "there is no service running the product itself, which is exactly the state this file "
        "exists to stop returning to"
    )
    assert "build:" in text, "the product service must be built from this repository"


def test_the_console_is_published_on_loopback_and_the_database_is_not_published_at_all():
    """Deployment is local-only by the owner's ruling, and a demo that quietly listens on every
    interface is a different product decision than the one that was made.

    The database publishing nothing is the second half: a host port here would collide with the
    development Postgres on 5433 that every working session uses.
    """
    text = _compose()

    code = _without_comments(text)

    assert '"127.0.0.1:4173:4173"' in code, (
        "the console must be published to loopback explicitly; a bare port mapping listens on "
        "every interface"
    )
    assert "5433" not in code, (
        "this stack must not publish a database port: 5433 is the development Postgres that "
        "other sessions are using"
    )


def test_the_entrypoint_starts_the_api_before_the_console_and_waits_for_it():
    """`dev_up.py`'s rule, carried into the container: half a stack is worse than no stack.

    A console pointed at an API that never came up presents as a console bug and sends whoever is
    watching to debug the wrong thing. Asserted on order rather than on the waiting code, because
    the order is the property and the mechanism may change.
    """
    code = _without_comments(ENTRYPOINT.read_text(encoding="utf-8"))
    text = ENTRYPOINT.read_text(encoding="utf-8")

    api = code.index("python -m sync.api")
    console = code.index("serve-console.mjs")
    assert api < console, "the console must not be served before the API is started"
    assert "never answered" in text, "the wait for the API must be bounded and say so when it fails"


def test_the_entrypoint_keeps_the_console_credential_away_from_the_api():
    """`B187`, pinned so the workaround cannot be removed without meeting the defect again.

    `sync.api.auth.configured_api_password` falls back to `SYNC_CONSOLE_PASSWORD`, and
    `serve-console.mjs` strips `authorization` before proxying. Together they serve a fully
    rendered console whose every panel is 401 -- measured, not theorised.
    """
    text = ENTRYPOINT.read_text(encoding="utf-8")

    assert "env -u SYNC_CONSOLE_PASSWORD python -m sync.api" in text, (
        "the API must start without the console's credential in its environment, or every panel "
        "behind the proxy returns 401 (B187)"
    )


def test_the_image_carries_the_console_build_and_the_python_toolchain():
    """One image, per the install decision. A runtime missing either half cannot serve the
    product: Node runs the console server, Python runs the API."""
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM node:" in text, "the console has to be built"
    assert "FROM python:3.12" in text, "the API needs the pinned interpreter"
    assert "--from=console" in text, "the built console must be carried into the runtime image"
    assert "nodesource" in text.lower(), (
        "the runtime needs Node for serve-console.mjs, which owns the /api proxy and the "
        "credential gate and is not reimplemented"
    )


def test_the_npx_doorbell_exists_and_points_at_a_real_file():
    """`M0-W312`'s doorbell, which the four-surfaces audit recorded as absent.

    The bin entry and the file are asserted together: a `package.json` naming a script that is not
    there installs cleanly and fails on the one command it exists to provide.
    """
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert "bin" in manifest, "there is no bin entry, so `npx` has nothing to run"
    for _name, relative in manifest["bin"].items():
        assert (REPO_ROOT / relative).is_file(), f"bin points at {relative}, which does not exist"

    assert DOORBELL.read_text(encoding="utf-8").startswith("#!/usr/bin/env node")


def test_the_doorbell_ships_everything_it_needs_to_run():
    """`files` decides what a published package contains, and the doorbell is useless without the
    compose file and the image definition it hands to Docker."""
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    shipped = set(manifest["files"])

    for required in ("bin/", "docker-compose.demo.yml", "Dockerfile", "docker/"):
        assert required in shipped, f"{required} is not shipped, so the published command cannot run"


def _node() -> str | None:
    return shutil.which("node")


@pytest.mark.parametrize(
    "cli_status, daemon_status, expected",
    [
        (1, 0, "was not found"),
        (0, 1, "daemon is not answering"),
        (0, 0, ""),
    ],
)
def test_a_missing_docker_and_a_stopped_docker_are_told_apart(cli_status, daemon_status, expected):
    """Two failures that read identically to a newcomer and want different answers.

    "Install Docker" shown to somebody who has Docker and has not started it is the kind of
    instruction that makes a person doubt the tool rather than the state of their machine. It is
    the same distinction `B184` drew for the suite's own daemon probe, moved to the front door.

    **Executed rather than grepped.** Asserting that a phrase appears in the file would pass on a
    source that never reaches the branch printing it, which is the shape
    `.claude/rules/test-discipline.md` calls a test that cannot fail. This imports the function
    and calls it with both probe results.
    """
    node = _node()
    if node is None:
        pytest.skip("node is absent from this machine, and this executes the doorbell's own JavaScript")

    script = (
        f"import {{ dockerDiagnosis }} from {DOORBELL.as_uri()!r};"
        f"const r = dockerDiagnosis({{status: {cli_status}}}, {{status: {daemon_status}}});"
        "console.log(JSON.stringify(r));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    if expected == "":
        assert verdict["ok"] is True, f"a working Docker must not be reported as broken: {verdict}"
    else:
        assert verdict["ok"] is False
        assert expected in verdict["message"], (
            f"a reader gets the wrong explanation for this failure: {verdict['message']!r}"
        )

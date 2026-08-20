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

import conftest

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
@conftest.requires_node
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


@pytest.mark.parametrize(
    "docker_ok, no_admin_ok, expected_route",
    [
        (True, True, "docker"),
        (True, False, "docker"),
        (False, True, "no-admin"),
        (False, False, "stop"),
    ],
)
@conftest.requires_node
def test_plain_start_routes_instead_of_refusing(docker_ok, no_admin_ok, expected_route):
    """The owner's ruling, 2026-08-18: everything is set from `npm start` -- the command
    decides, the person never runs Docker chores. A serving daemon keeps the container path,
    because the container is the artifact. An unusable Docker on a platform with the
    user-space route falls through to it automatically, stating the Docker reason so a
    reader who wanted the container knows what to start and try again. Only a platform with
    neither gets a refusal. Before this, the fresh-clone `npm start` printed a Docker chore
    on the one machine Docker can never run on.
    """
    node = _node()
    docker = '{ok: true}' if docker_ok else '{ok: false, message: "the docker reason"}'
    support = '{ok: true}' if no_admin_ok else '{ok: false, message: "windows only"}'
    script = (
        f"import {{ startRoute }} from {DOORBELL.as_uri()!r};"
        f"console.log(JSON.stringify(startRoute({docker}, {support})));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["route"] == expected_route
    if expected_route == "no-admin":
        assert "the docker reason" in verdict["message"], (
            "the fall-through must carry the Docker diagnosis, so a reader who wanted the "
            "container knows what to fix rather than wondering why the route changed"
        )
    if expected_route == "stop":
        assert "the docker reason" in verdict["message"], (
            "a refusal that hides the diagnosis strands the reader"
        )


@pytest.mark.parametrize(
    "call, expected_action",
    [
        ("consoleDependenciesVerdict(false, 'aa', 'aa')", "install"),
        ("consoleDependenciesVerdict(true, 'aa', 'aa')", "keep"),
        ("consoleDependenciesVerdict(true, 'aa', 'bb')", "install"),
        ("consoleDependenciesVerdict(true, 'aa', null)", "keep"),
        ("consoleDependenciesVerdict(true, null, 'bb')", "keep"),
    ],
)
@conftest.requires_node
def test_the_no_admin_path_installs_the_console_dependencies(call, expected_action):
    """The last assembly step a fresh clone still asked a person to do: `dev_up.py` refuses
    on an absent `web/node_modules` and names `npm install --prefix web` -- a correct
    refusal that is still a defect in the one command, by the owner's own bar (*after this
    one command, is there anything a person still has to figure out?*). The no-admin flow
    now decides it the same way it decides the venv and the cluster: a verdict on the
    lockfile digest, never an mtime -- absent installs, a changed lockfile reinstalls, and
    an unknown digest on either side keeps what is there rather than churning a tree that
    was just built (the record catches up at the end of the run).
    """
    node = _node()
    script = (
        f"import {{ consoleDependenciesVerdict }} from {DOORBELL.as_uri()!r};"
        f"console.log(JSON.stringify({call}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["action"] == expected_action
    assert verdict["message"], "every verdict says what it decided; silence reads as a hang"


@pytest.mark.parametrize(
    "state, expected_action, expected_phrase",
    [
        ("{fetched: false, behind: 0, ahead: 0, dirty: false}", "keep", "Could not reach"),
        ("{fetched: true, behind: 0, ahead: 0, dirty: false}", "keep", "current"),
        ("{fetched: true, behind: 3, ahead: 0, dirty: false}", "pull", "3"),
        ("{fetched: true, behind: 3, ahead: 0, dirty: true}", "hold", "local changes"),
        ("{fetched: true, behind: 3, ahead: 2, dirty: false}", "hold", "diverged"),
    ],
)
@conftest.requires_node
def test_the_bring_up_freshens_the_checkout_and_says_what_it_decided(
    state, expected_action, expected_phrase
):
    """Owner's ruling, 2026-08-18: the build commands always build the most recent code --
    the person never wonders whether the screen they are looking at is behind `main`. The
    verdict is automatic exactly where automation cannot lose work: a clean checkout that is
    only behind fast-forwards; local changes are never pulled over; a divergence is named
    and left for a person; an unreachable origin is stated and the bring-up continues,
    because offline is a place people run software. Every branch says what it decided --
    silence here is how five stale dev servers happened.
    """
    node = _node()
    script = (
        f"import {{ updateVerdict }} from {DOORBELL.as_uri()!r};"
        f"console.log(JSON.stringify(updateVerdict({state})));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["action"] == expected_action
    assert expected_phrase in verdict["message"], (
        f"the decision is not legible from the message: {verdict['message']!r}"
    )


@pytest.mark.parametrize("cli_status, daemon_status", [(1, 0), (0, 1)])
@conftest.requires_node
def test_every_docker_refusal_offers_the_no_admin_route(cli_status, daemon_status):
    """`CI-W453`'s rationale binds both refusals, not one: the reader most likely to meet a
    Docker refusal is exactly the reader without admin rights, and on such a machine "start
    Docker Desktop and wait" is an instruction that can never complete, not a fix. The
    stopped-daemon branch shipped without the offer, and the first fresh-clone `npm start`
    on this machine dead-ended on it -- told to start a Desktop that elevation forbids,
    never told the user-space route exists.
    """
    node = _node()
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
    assert verdict["ok"] is False
    assert "no-admin" in verdict["message"], (
        "a Docker refusal that does not name the no-admin route strands exactly the reader "
        f"it exists for: {verdict['message']!r}"
    )


# -- `--check`: what this machine needs, before anything is fetched -----------------------
#
# `CI-W445` and `CI-W446` decided both install lifecycles and nothing called either, which by
# the standing rule means neither shipped. This is their caller. It is also the only honest
# thing buildable before the download and the process spawn exist -- the decisions are real
# now, the actions are not, and the output has to keep that difference.


def _run_check() -> subprocess.CompletedProcess:
    node = _node()
    return subprocess.run(
        [node, str(DOORBELL), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


@conftest.requires_node
def test_the_check_reports_what_an_install_would_do_rather_than_what_it_did():
    """Every action is framed as a `would`, because none of it is implemented.

    A check that listed four confident lines would read as a readiness report, and the
    install it describes cannot yet download anything or start a process.
    """
    result = _run_check()

    assert result.returncode == 0, result.stderr
    assert "would:" in result.stdout


@conftest.requires_node
def test_the_check_states_what_is_not_built_every_time():
    """Stated unconditionally rather than only when something is missing.

    Decision 99 forbids reporting anything working that has not been run on a clean machine.
    A caveat that appeared only on failure would be absent exactly when the output looks
    most like success.
    """
    stdout = _run_check().stdout

    assert "has been done" in stdout
    assert "not written yet" in stdout
    assert "never had this repository" in stdout


@conftest.requires_node
def test_the_check_never_prints_an_absence_as_a_value():
    """`runs Python null` was real output from the first version of this command.

    A probe that fails leaves a hole, and a hole rendered where a version goes is the
    absence-as-a-value defect this console refuses on screen. It is no better in a terminal,
    and a terminal is where nobody is reviewing the wording.
    """
    stdout = _run_check().stdout

    assert "null" not in stdout
    assert "undefined" not in stdout


# -- `CI-W451`: the commands are ours to type ----------------------------------------------
#
# The package carries the command's name inside the owner's scope, so `npx @stroland02/sync-up`
# is the whole instruction and the command it installs is still `sync-up`. What these pin is
# the decision, so a future edit that quietly re-privatises the package or renames it away
# from the bin it installs fails a test rather than a demo.


def test_the_manifest_is_publishable_under_its_own_name():
    """`private: true` was the right guard while the manifest carried a name that was not ours
    to publish under. The unscoped name turned out not to be ours either: the first real PUT
    was refused 403, `sync-up` too similar to an existing `syncup` -- a rule no absent-name
    lookup reveals, so "verified free on the registry" was true and insufficient. The name is
    the account-scoped form; the bin keeps the command; and `publishConfig.access` is public
    because a scoped package defaults to restricted, and a manifest that still refuses
    `npm publish` turns the owner's publish into a debugging session."""
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert manifest["name"] == "@stroland02/sync-up", (
        "the registry refused the unscoped name (403: too similar to `syncup`), so the "
        "publishable identity is the owner-scoped one; renaming it silently splits the "
        "README's instruction from what npx can resolve"
    )
    bare = manifest["name"].rpartition("/")[2]
    assert bare in manifest["bin"], (
        "the scope is address, not identity: the command a reader types after install is "
        "still the bare name, so the bin must carry it"
    )
    assert len(manifest["bin"]) == 1, (
        "npx runs a scoped package's bin without guessing only while there is exactly one"
    )
    assert manifest.get("publishConfig", {}).get("access") == "public", (
        "a scoped package publishes restricted by default; without this, `npm publish` is "
        "a 402 in front of the owner"
    )
    assert not manifest.get("private", False), (
        "the manifest still refuses to publish; the name is ours and the guard is stale"
    )


def test_the_pnpm_commands_hand_over_to_things_that_exist():
    """The pnpm surface is scripts, not a reimplementation: `start`/`down`/`check` reach the
    doorbell and `dev` reaches the from-source bring-up. Asserted against the files rather
    than exact strings, because a script that names a missing file installs cleanly and fails
    on the one command it exists to provide -- the same defect the bin test above pins.

    `start` rather than `up`, and it is not taste: `pnpm up` is pnpm's own alias for `update`,
    so a script named `up` is unreachable from pnpm and the command mutates the lockfile
    instead. Measured, not read about. `up` staying absent is part of what this pins."""
    manifest = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    scripts = manifest.get("scripts", {})

    for name in ("start", "down", "check", "install-docker", "no-admin"):
        assert name in scripts, f"`pnpm {name}` does not exist"
        assert "sync-up.mjs" in scripts[name], (
            f"`pnpm {name}` must hand over to the doorbell rather than reimplement it"
        )
    assert "up" not in scripts, (
        "`pnpm up` is pnpm's `update` builtin; a script named `up` is a command that runs "
        "something different under each package manager"
    )
    assert "dev" in scripts, "`pnpm dev` does not exist"
    assert "dev_up.py" in scripts["dev"], (
        "`pnpm dev` must hand over to the from-source bring-up rather than reimplement it"
    )
    assert (REPO_ROOT / "scripts" / "dev_up.py").is_file()


@pytest.mark.parametrize(
    "platform, fragment, runnable",
    [
        ("win32", "winget", True),
        ("darwin", "brew", True),
        ("linux", "get.docker.com", False),
    ],
)
@conftest.requires_node
def test_each_platform_gets_its_own_docker_install_command(platform, fragment, runnable):
    """`CI-W452`, measured on the first fresh-clone run anybody did: the refusal said Docker
    was missing and left the reader to a browser. A terminal that can say `winget install`
    should say it.

    Linux is deliberately not runnable: the convenience script is remote code, and a doorbell
    that pipes it into `sh` unread is a different product decision than the one made here. It
    is printed for the reader to run themselves.
    """
    node = _node()
    script = (
        f"import {{ dockerInstallCommand }} from {DOORBELL.as_uri()!r};"
        f"console.log(JSON.stringify(dockerInstallCommand({platform!r})));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert fragment in verdict["command"]
    assert verdict["runnable"] is runnable


@conftest.requires_node
def test_the_missing_docker_refusal_prints_the_install_command_for_this_platform():
    """The refusal and the installer must agree, and the reader gets both: the URL for a
    person who wants to see what they are installing, the command for one who already knows."""
    node = _node()
    script = (
        f"import {{ dockerDiagnosis, dockerInstallCommand }} from {DOORBELL.as_uri()!r};"
        "const d = dockerDiagnosis({status: 1}, {status: 0}, 'win32');"
        "const i = dockerInstallCommand('win32');"
        "console.log(JSON.stringify({message: d.message, command: i.command}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["command"] in verdict["message"], (
        "the refusal names Docker as missing without printing the command that installs it"
    )
    assert "--install-docker" in verdict["message"], (
        "the refusal must name the flag that runs the install, or nobody discovers it"
    )


# -- `CI-W453`: the no-admin path ----------------------------------------------------------
#
# The owner's machine has no admin rights, so Docker, WSL2 and every VM-backed runtime are
# closed -- and the alternative was proven by hand before it was automated: portable Postgres
# binaries in user space, a cluster on 5433, `uv sync`, seed, `dev_up.py`. These pin the
# decision layer of turning that afternoon into one command.


@pytest.mark.parametrize(
    "platform, expected_ok",
    [("win32", True), ("darwin", False), ("linux", False)],
)
@conftest.requires_node
def test_no_admin_is_windows_first_and_says_so_elsewhere(platform, expected_ok):
    """Windows is where the no-admin wall is real: enabling any VM feature is elevated, so a
    user without admin has no container runtime at all. macOS and Linux have user-space routes
    of their own, and a half-tested path offered there would fail in front of exactly the
    person it claims to rescue -- refused with directions instead, `B191` carries building it.
    """
    node = _node()
    script = (
        f"import {{ noAdminSupport }} from {DOORBELL.as_uri()!r};"
        f"console.log(JSON.stringify(noAdminSupport({platform!r})));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["ok"] is expected_ok
    if not expected_ok:
        assert verdict["message"], "a refusal with no directions strands the reader"


@pytest.mark.parametrize(
    "data_dir_exists, serving, expected_action, fragment",
    [
        (True, True, "adopt", "started nothing"),
        (True, False, "start-existing", "not running"),
        (False, False, "fresh", ""),
    ],
)
@conftest.requires_node
def test_a_cluster_the_installer_never_recorded_is_adopted_rather_than_clobbered(
    data_dir_exists, serving, expected_action, fragment
):
    """The case Decision 97's four verdicts do not cover: a cluster at our path with no install
    record, because a person built it by hand -- which is exactly how this path was proven
    before it was automated. Running `initdb` onto that directory would destroy a working
    database to satisfy a bookkeeping gap. Adopt what serves, start what is stopped, and only
    a genuinely absent directory is a first run.
    """
    node = _node()
    script = (
        f"import {{ unrecordedClusterVerdict }} from {DOORBELL.as_uri()!r};"
        f"const r = unrecordedClusterVerdict({{dataDirExists: {str(data_dir_exists).lower()}, "
        f"serving: {str(serving).lower()}}});"
        "console.log(JSON.stringify(r));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["action"] == expected_action
    if fragment:
        assert fragment in verdict["message"]


@conftest.requires_node
def test_the_missing_docker_refusal_offers_the_no_admin_path():
    """The reader most likely to meet this refusal is the reader who cannot act on it: no
    admin rights means no Docker, no matter how clearly the install command is printed. The
    refusal names the path that needs none."""
    node = _node()
    script = (
        f"import {{ dockerDiagnosis }} from {DOORBELL.as_uri()!r};"
        "console.log(JSON.stringify(dockerDiagnosis({status: 1}, {status: 0}, 'win32')));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert "no-admin" in verdict["message"], (
        "the refusal offers only routes that need elevation; a reader without admin rights is "
        "left with nothing to type"
    )


@conftest.requires_node
def test_the_embedded_cluster_is_held_to_the_shipped_database_settings():
    """`CI-W454`, measured before it was written: a hand-built cluster inherited the machine's
    timezone from `initdb` and full durability, so five view tests failed on `-05:00` renderings
    of correct instants and the suite crawled on `DataFileImmediateSync`. The shipped database
    (`docker-compose.yml`, both files) runs UTC with `fsync=off` and `synchronous_commit=off`
    because everything in it is rebuilt by a seed. The no-admin cluster is held to the same
    settings, whether adopted or created -- parity is the contract, not a default."""
    node = _node()
    script = (
        f"import {{ parityStatements }} from {DOORBELL.as_uri()!r};"
        "console.log(JSON.stringify(parityStatements()));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    statements = json.loads(result.stdout.strip())
    text = " ".join(statements).lower()
    for setting, value in (("timezone", "utc"), ("fsync", "off"), ("synchronous_commit", "off")):
        assert setting in text and value in text, (
            f"the parity statements do not pin {setting}; the next hand-built cluster drifts "
            "exactly the way the first one did"
        )


@conftest.requires_node
def test_the_binaries_extractor_is_windows_own_tar_and_not_whatever_path_serves():
    """The first real no-admin install died at extraction with `tar: Cannot connect to C:
    resolve failed`: bare `tar` resolves through PATH, a Git Bash environment puts GNU tar
    first, and GNU tar parses a `C:\\` archive path as a remote hostname -- and cannot read
    zip at all. The no-admin path is Windows-only by design, so the extractor is System32's
    bsdtar named absolutely, with bare `tar` only for a machine that does not have it.
    """
    node = _node()
    script = (
        f"import {{ tarExecutable }} from {DOORBELL.as_uri()!r};"
        "console.log(JSON.stringify(["
        "tarExecutable('ROOT', () => true),"
        "tarExecutable('ROOT', () => false),"
        "tarExecutable(null, () => true),"
        "]));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    with_system, without_system, no_root = json.loads(result.stdout.strip())
    assert "System32" in with_system and with_system.endswith("tar.exe"), (
        "with a SystemRoot and the binary present, the extractor must be Windows' own tar, "
        "named absolutely rather than resolved from PATH"
    )
    assert without_system == "tar", "a machine missing System32 tar falls back to PATH"
    assert no_root == "tar", "no SystemRoot means nothing absolute to name; fall back to PATH"


@pytest.mark.parametrize("source_tree_present, expected_ok", [(True, True), (False, False)])
@conftest.requires_node
def test_a_registry_install_without_the_source_tree_is_refused_with_directions(
    source_tree_present, expected_ok
):
    """The published tarball carries the compose file but not the tree it builds from, so a
    registry `npx` used to die mid-`docker build` on a missing `src/` -- a Node traceback in
    front of exactly the person the doorbell exists to protect. Refused up front instead,
    naming the clone that works and the fact that no prebuilt image is published yet (`B190`
    is what retires this).

    **Executed rather than grepped**, for the same reason as the Docker diagnosis above: a
    phrase asserted against the source passes even when no branch prints it.
    """
    node = _node()
    script = (
        f"import {{ sourceTreeDiagnosis }} from {DOORBELL.as_uri()!r};"
        f"const r = sourceTreeDiagnosis({str(source_tree_present).lower()});"
        "console.log(JSON.stringify(r));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"the doorbell would not load: {result.stderr}"

    verdict = json.loads(result.stdout.strip())
    assert verdict["ok"] is expected_ok
    if not expected_ok:
        assert "git clone" in verdict["message"], (
            "the refusal must print the command that works, not only the one that does not"
        )
        assert "image" in verdict["message"], (
            "the refusal must say why: no prebuilt image is published yet"
        )
        # The hand-over must be typeable. Every `npm <x>` / `npm run <x>` the refusal prints
        # has to resolve against the scripts package.json actually defines -- `npm run up`
        # shipped here once, handed to exactly the reader with no checkout to debug it in.
        scripts = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]
        package_manager_builtins = {"install", "ci", "exec"}
        handed_over = re.findall(r"(?:npm|pnpm)(?: run)?\s+([a-z][a-z-]*)", verdict["message"])
        assert handed_over, "the refusal must hand over a runnable command, not only a URL"
        for target in handed_over:
            if target in package_manager_builtins:
                continue
            assert target in scripts, (
                f"the refusal recommends `{target}`, which package.json defines no script for; "
                "a hand-over the reader cannot type is a traceback with better manners"
            )


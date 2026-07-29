"""One file names the oasdiff release, and both installers read it.

`docs/superpowers/reports/2026-07-29-oasdiff-version-settled.md` measured what two mechanisms
cost. `.github/workflows/ci.yml` pinned 1.26.1 with a comment saying why it must not float;
`scripts/bootstrap_tools.sh` then downloaded whatever release was latest on the day a checkout
ran it, and short-circuited on *presence* rather than version, so eleven working copies on one
machine held two different builds under one path and the spread widened rather than converged.

Nothing here checks that a version string appears somewhere. That is the check that cannot fail:
a version read out of the same file it was written to agrees with itself no matter what either
installer does. Both installers are run instead, under the shell that runs them in production,
against a pin this file writes -- so a version hardcoded anywhere in either one shows up as a
disagreement with the pin rather than as a matching literal.

The download is the only thing stubbed. `gh` and `curl` are replaced on `PATH`, so no test here
reaches GitHub.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIN = REPO_ROOT / ".oasdiff-version"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap_tools.sh"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# Written into every temporary pin. The comment and the blank line are the point: both readers
# have to skip them, and a reader that takes the first line of the file passes without them.
PIN_TEMPLATE = "# a comment neither reader may mistake for a version\n\n{version}\n"

# The three shapes a hand-maintained pin arrives in, all resolving to 9.9.9. CRLF is what
# `core.autocrlf=true` hands a Windows working tree; the trailing space is what a person leaves.
# They are not redundant -- measured here, Windows `grep` drops the CR on its own and does not
# touch the space, so only the second reaches the scrub in either reader.
WRITTEN_PINS = [("9.9.9", "\n"), ("9.9.9", "\r\n"), ("9.9.9  ", "\n")]
PIN_IDS = ["lf", "crlf", "trailing-space"]


# --- running the two installers for real -----------------------------------------


def git_bash() -> str:
    """The shell `CLAUDE.md` commits to for this repository's POSIX snippets.

    `shutil.which("bash")` is not it on Windows: it resolves `C:\\Windows\\System32\\bash.exe`,
    the WSL launcher, which is a different machine with a different filesystem.
    """
    if sys.platform != "win32":
        found = shutil.which("bash")
        assert found is not None, "bash is not on PATH"
        return found

    candidates = []
    git = shutil.which("git")
    if git is not None:
        beside = Path(git).resolve().parent
        candidates += [beside / "bash.exe", beside.parent / "bin" / "bash.exe"]
    candidates.append(Path(r"C:\Program Files\Git\bin\bash.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise AssertionError(f"Git Bash not found; looked in {[str(c) for c in candidates]}")


def write_script(path: Path, body: str) -> Path:
    """A shell script Git Bash will exec by its shebang.

    `newline="\\n"` is load-bearing rather than tidy: this repository is checked out with
    `core.autocrlf=true`, and a shebang line ending in CR names an interpreter that does not
    exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(0o755)
    return path


def fake_oasdiff(path: Path, *, version: str, exit_code: int = 0) -> Path:
    body = "#!/bin/sh\n"
    if version:
        body += f"printf '%s\\n' 'oasdiff version {version}'\n"
    body += f"exit {exit_code}\n"
    return write_script(path, body)


def recorder(path: Path, *, log: Path, then: str = "", exit_code: int = 0) -> Path:
    """A stub that appends its own argv to `log` and then does whatever `then` says."""
    body = (
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {shlex.quote(log.as_posix())}\n'
        f"{then}"
        f"exit {exit_code}\n"
    )
    return write_script(path, body)


def run(command: str, *, cwd: Path, stubs: Path) -> subprocess.CompletedProcess[str]:
    """Run `command` in Git Bash with `stubs` ahead of every real tool.

    The PATH has to be set by a shell that is already running. `bash.exe` prepends its own
    `/mingw64/bin` and `/usr/bin` to whatever PATH it inherits, so a directory exported from
    Python lands *behind* the real `curl` and `tar` -- measured by watching a stubbed test reach
    GitHub and come back with a 404.
    """
    quoted = shlex.quote(str(stubs))
    ahead = f'"$(cygpath -u {quoted})"' if sys.platform == "win32" else quoted
    return subprocess.run(
        [git_bash(), "--noprofile", "--norc", "-c", f"PATH={ahead}:$PATH; export PATH; {command}"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ},
    )


# --- the workflow half -----------------------------------------------------------


def install_step() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["test"]["steps"]:
        if step.get("name") == "Install oasdiff":
            return step["run"]
    raise AssertionError("ci.yml has no step named 'Install oasdiff'")


def write_pin(path: Path, *, version: str, newline: str) -> None:
    """`core.autocrlf=true` means a fresh Windows checkout hands both readers a CR per line."""
    path.write_text(PIN_TEMPLATE.format(version=version), encoding="utf-8", newline=newline)


def workflow_workspace(tmp_path: Path, *, pin: str, newline: str) -> Path:
    """A checkout as CI sees it: the pin, and the install step ready to run."""
    work = tmp_path / "workspace"
    work.mkdir()
    write_pin(work / ".oasdiff-version", version=pin, newline=newline)
    # `bash --noprofile --norc -e <file>` is what GitHub runs a `run:` block with.
    write_script(work / "step.sh", install_step())
    return work


def run_install_step(
    tmp_path: Path, *, pin: str, installs: str | None, newline: str = "\n"
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    work = workflow_workspace(tmp_path, pin=pin, newline=newline)
    stubs = tmp_path / "bin"
    stubs.mkdir()
    log = tmp_path / "curl.log"

    recorder(stubs / "curl", log=log)
    if installs is None:
        write_script(stubs / "tar", "#!/bin/sh\nexit 0\n")
    else:
        payload = fake_oasdiff(tmp_path / "payload", version=installs)
        write_script(
            stubs / "tar",
            "#!/bin/sh\n"
            f"cp {shlex.quote(payload.as_posix())} tools/oasdiff\n"
            "chmod +x tools/oasdiff\n"
            "exit 0\n",
        )

    result = run("bash --noprofile --norc -e step.sh", cwd=work, stubs=stubs)
    fetched = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, fetched


@pytest.mark.parametrize("written,newline", WRITTEN_PINS, ids=PIN_IDS)
def test_the_workflow_fetches_the_release_the_pin_names(
    tmp_path: Path, written: str, newline: str
) -> None:
    """Reads the pin and the workflow, and asks the workflow which release it went for.

    The pin is deliberately not the one this repository holds. A version hardcoded in `ci.yml`
    would satisfy an assertion that only checked the two matched each other.
    """
    result, fetched = run_install_step(
        tmp_path, pin=written, installs="9.9.9", newline=newline
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(fetched) == 1, fetched
    assert "/v9.9.9/oasdiff_9.9.9_linux_amd64.tar.gz" in fetched[0]


def test_the_workflow_fails_when_it_installs_a_build_the_pin_does_not_name(
    tmp_path: Path,
) -> None:
    result, _ = run_install_step(tmp_path, pin="9.9.9", installs="1.26.0")

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1.26.0" in result.stdout + result.stderr


def test_the_workflow_fails_when_the_binary_never_arrives(tmp_path: Path) -> None:
    result, _ = run_install_step(tmp_path, pin="9.9.9", installs=None)

    assert result.returncode != 0, result.stdout + result.stderr


# --- the bootstrap half ----------------------------------------------------------


def executable(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Windows tracks only the read-only bit, so `chmod` does not survive into the archive.

    Set explicitly because the extracted file has to pass the script's own `[ -x ]`, and on
    Linux it would not.
    """
    info.mode = 0o755
    return info


def tarball(tmp_path: Path, *, version: str) -> Path:
    """A `*windows_amd64.tar.gz` the real `tar` can extract, so only `gh` is stubbed."""
    payload = fake_oasdiff(tmp_path / "payload.exe", version=version)
    archive = tmp_path / f"oasdiff_{version}_windows_amd64.tar.gz"
    with tarfile.open(archive, "w:gz", encoding="utf-8") as bundle:
        bundle.add(payload, arcname="oasdiff.exe", filter=executable)
    return archive


def checkout(
    tmp_path: Path, *, pin: str, holds: str | None = None, newline: str = "\n"
) -> Path:
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    write_pin(root / ".oasdiff-version", version=pin, newline=newline)
    shutil.copy(BOOTSTRAP, root / "scripts" / "bootstrap_tools.sh")
    if holds is not None:
        fake_oasdiff(root / "tools" / "oasdiff.exe", version=holds)
    return root


def run_bootstrap(
    root: Path, *, tmp_path: Path, release: Path | None, gh_exit: int = 0
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "gh.log"
    drop = f"cp {shlex.quote(release.as_posix())} ./{release.name}\n" if release else ""
    recorder(stubs / "gh", log=log, then=drop, exit_code=gh_exit)

    result = run("bash scripts/bootstrap_tools.sh", cwd=root, stubs=stubs)
    called = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, called


@pytest.mark.parametrize("written,newline", WRITTEN_PINS, ids=PIN_IDS)
def test_the_bootstrap_downloads_the_release_the_pin_names(
    tmp_path: Path, written: str, newline: str
) -> None:
    root = checkout(tmp_path, pin=written, newline=newline)
    result, called = run_bootstrap(
        root, tmp_path=tmp_path, release=tarball(tmp_path, version="9.9.9")
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(called) == 1, called
    assert "v9.9.9" in called[0]
    assert (root / "tools" / "oasdiff.exe").is_file()


def test_a_checkout_holding_an_unpinned_build_is_refused_and_left_untouched(
    tmp_path: Path,
) -> None:
    """The defect this task closes. The old script exited 0 here and changed nothing."""
    root = checkout(tmp_path, pin="9.9.9", holds="1.26.0")
    before = (root / "tools" / "oasdiff.exe").read_bytes()

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, release=tarball(tmp_path, version="9.9.9")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert called == [], "a refusal must not download anything"
    assert (root / "tools" / "oasdiff.exe").read_bytes() == before
    complaint = result.stdout + result.stderr
    assert "1.26.0" in complaint and "9.9.9" in complaint


def test_a_checkout_holding_the_pinned_build_succeeds_without_downloading(
    tmp_path: Path,
) -> None:
    root = checkout(tmp_path, pin="9.9.9", holds="9.9.9")

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, release=tarball(tmp_path, version="9.9.9")
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert called == []


def test_a_binary_that_cannot_run_is_refused_rather_than_treated_as_absent(
    tmp_path: Path,
) -> None:
    root = checkout(tmp_path, pin="9.9.9")
    fake_oasdiff(root / "tools" / "oasdiff.exe", version="", exit_code=3)

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, release=tarball(tmp_path, version="9.9.9")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert called == []
    # Named rather than folded into the version mismatch. Reading `--version` without its exit
    # code makes an unrunnable binary indistinguishable from one reporting an empty version,
    # which sends the operator looking for a version problem that is not there.
    assert "'--version' failed" in result.stderr, result.stderr


def test_the_bootstrap_fails_when_the_download_fails(tmp_path: Path) -> None:
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(root, tmp_path=tmp_path, release=None, gh_exit=1)

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / "oasdiff.exe").exists()


def test_the_bootstrap_fails_when_the_download_produces_nothing(tmp_path: Path) -> None:
    """`gh` exiting 0 without writing a tarball. `set -e` has to carry this one."""
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(root, tmp_path=tmp_path, release=None, gh_exit=0)

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / "oasdiff.exe").exists()


def test_the_bootstrap_refuses_a_download_that_is_not_the_release_it_asked_for(
    tmp_path: Path,
) -> None:
    """A tag and its contents can disagree, and printing the version does not notice."""
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(
        root, tmp_path=tmp_path, release=tarball(tmp_path, version="1.26.0")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / "oasdiff.exe").exists(), (
        "a wrong binary this run downloaded is this run's to remove"
    )


# --- the pin itself --------------------------------------------------------------


def test_the_pin_names_exactly_one_version() -> None:
    lines = [
        line.strip()
        for line in PIN.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert len(lines) == 1, lines
    assert SEMVER.match(lines[0]), lines[0]


@pytest.mark.parametrize("installer", ["workflow", "bootstrap"])
def test_neither_installer_names_a_version_of_its_own(installer: str) -> None:
    """Belt to the behavioural tests' braces, and the one that names the offending line.

    Those tests catch a hardcoded version by its effect; this catches it by sight, which is
    what a reviewer reading a diff gets. Scoped to the install step rather than to the whole
    workflow because `actions/checkout@v4` and `postgres:16` are versions too, and a check
    that has to keep a list of the versions it tolerates stops being read.
    """
    source = install_step() if installer == "workflow" else BOOTSTRAP.read_text(encoding="utf-8")
    offenders = [line for line in source.splitlines() if re.search(r"\d+\.\d+\.\d+", line)]

    assert offenders == [], offenders

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

import functools
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
ASSET_MAP = REPO_ROOT / "scripts" / "oasdiff_asset.sh"
"""Sourced by the bootstrap script, so a checkout without it cannot run one."""

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


# Every asset shape `scripts/oasdiff_asset.sh` can name. The release below publishes all of them,
# the way the real one does, so the pattern the script sends is the only thing deciding which
# archive arrives -- on whatever platform this run happens to be.
ASSET_SUFFIXES = (
    "windows_amd64", "windows_arm64", "linux_amd64", "linux_arm64", "darwin_all",
)


@functools.lru_cache(maxsize=1)
def platform_selection() -> tuple[str, str]:
    """This machine's asset pattern and extracted binary name, read from the mapping itself.

    Restating either one here would agree with `oasdiff_asset.sh` on the machine this file was
    written on and nowhere else, which is precisely the defect these tests exist to catch: a
    fixture hardcoded to one platform makes every assertion below a tautology on that platform
    and a false report everywhere else.
    """
    probe = subprocess.run(
        [
            git_bash(), "--noprofile", "--norc", "-c",
            f". '{ASSET_MAP.as_posix()}'; "
            'oasdiff_asset "$(uname -s)" "$(uname -m)"; oasdiff_binary "$(uname -s)"',
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ},
    )
    assert probe.returncode == 0, probe.stdout + probe.stderr
    asset, binary = probe.stdout.split()
    return asset, binary


def platform_asset() -> str:
    return platform_selection()[0]


def platform_binary() -> str:
    return platform_selection()[1]


def foreign_suffix() -> str:
    """One asset suffix this machine's pattern does not match, whichever machine that is."""
    ours = platform_asset().removeprefix("*_").removesuffix(".tar.gz")
    return next(suffix for suffix in ASSET_SUFFIXES if suffix != ours)


def release(tmp_path: Path, *, version: str, suffixes: tuple[str, ...] = ASSET_SUFFIXES) -> Path:
    """A directory of published assets, one per platform, that the real `tar` can extract.

    The archives are real and only `gh` is stubbed. Every one carries the binary name its own
    platform's release carries, so an archive delivered for the wrong platform unpacks to a name
    the script will not find -- which is what a stub answering every pattern with one Windows
    archive hid until a Linux runner met it.
    """
    assets = tmp_path / "release"
    assets.mkdir(exist_ok=True)
    for suffix in suffixes:
        member = "oasdiff.exe" if suffix.startswith("windows") else "oasdiff"
        payload = fake_oasdiff(tmp_path / f"payload-{suffix}", version=version)
        archive = assets / f"oasdiff_{version}_{suffix}.tar.gz"
        with tarfile.open(archive, "w:gz", encoding="utf-8") as bundle:
            bundle.add(payload, arcname=member, filter=executable)
    return assets


def fake_gh(path: Path, *, log: Path, assets: Path | None, exit_code: int = 0) -> Path:
    """`gh release download`, stubbed as far as the pattern.

    It reads `--pattern` out of its own argv and delivers exactly the assets matching it, and it
    fails when none match -- the two behaviours `bootstrap_tools.sh` depends on. A stub that
    copies whatever the test handed it regardless of the pattern asserts that the script asked
    for *something*, which passes on the one platform whose asset the fixture happens to be
    named for and fails everywhere else.

    `case "$name" in $pattern)` is deliberately unquoted: that is the shell's own glob match,
    and `gh`'s `--pattern` is a glob over asset names.
    """
    deliver = ""
    if assets is not None:
        deliver = (
            f"for asset in {shlex.quote(assets.as_posix())}/*; do\n"
            '  name="${asset##*/}"\n'
            "  case \"$name\" in\n"
            '    $pattern) cp "$asset" "./$name"; matched=1 ;;\n'
            "  esac\n"
            "done\n"
        )
    body = (
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> {shlex.quote(log.as_posix())}\n'
        f"[ {exit_code} -eq 0 ] || exit {exit_code}\n"
        "pattern=''\n"
        "while [ $# -gt 0 ]; do\n"
        '  if [ "$1" = --pattern ]; then pattern="$2"; shift 2; else shift; fi\n'
        "done\n"
        "if [ -z \"$pattern\" ]; then echo 'gh: no --pattern was given' >&2; exit 2; fi\n"
        "matched=0\n"
        f"{deliver}"
        'if [ "$matched" -eq 0 ]; then\n'
        '  echo "gh: no assets match the file pattern \\"$pattern\\"" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    return write_script(path, body)


def checkout(
    tmp_path: Path, *, pin: str, holds: str | None = None, newline: str = "\n"
) -> Path:
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    write_pin(root / ".oasdiff-version", version=pin, newline=newline)
    shutil.copy(BOOTSTRAP, root / "scripts" / "bootstrap_tools.sh")
    shutil.copy(ASSET_MAP, root / "scripts" / "oasdiff_asset.sh")
    if holds is not None:
        fake_oasdiff(root / "tools" / platform_binary(), version=holds)
    return root


def run_bootstrap(
    root: Path, *, tmp_path: Path, assets: Path | None, gh_exit: int = 0
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "gh.log"
    fake_gh(stubs / "gh", log=log, assets=assets, exit_code=gh_exit)

    result = run("bash scripts/bootstrap_tools.sh", cwd=root, stubs=stubs)
    called = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, called


def run_gh(stub: Path, *args: str, cwd: Path, stubs: Path) -> subprocess.CompletedProcess[str]:
    return run(f"{shlex.quote(stub.as_posix())} {shlex.join(args)}", cwd=cwd, stubs=stubs)


def test_the_gh_stub_delivers_only_what_the_pattern_names(tmp_path: Path) -> None:
    """The stub is the platform mapping's only witness, so its fidelity is the test.

    `gh release download --pattern` takes a glob over asset names. A stub ignoring that flag
    turns every assertion below into "the script asked for something", and the script's answer
    is right on exactly one platform -- the one whose archive the fixture was named for. That is
    how `M0-W230`'s per-platform selection shipped correct and its tests still passed only on
    Windows.
    """
    assets = release(tmp_path, version="9.9.9")
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    into = tmp_path / "downloads"
    into.mkdir()
    stub = fake_gh(stubs / "gh", log=tmp_path / "gh.log", assets=assets)

    result = run_gh(
        stub, "release", "download", "v9.9.9", "--pattern", "*_linux_arm64.tar.gz",
        cwd=into, stubs=stubs,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert [path.name for path in sorted(into.iterdir())] == ["oasdiff_9.9.9_linux_arm64.tar.gz"]


def test_the_gh_stub_fails_when_the_release_publishes_nothing_matching(tmp_path: Path) -> None:
    """Real `gh` exits non-zero and downloads nothing when no asset matches; so must this.

    Without it a release missing this machine's asset would look like a successful download of
    an empty directory, and the script's next failure would be `tar` complaining about a file
    nobody can find -- which is the message a Linux runner printed for a fortnight.
    """
    assets = release(tmp_path, version="9.9.9", suffixes=("darwin_all",))
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    into = tmp_path / "downloads"
    into.mkdir()
    stub = fake_gh(stubs / "gh", log=tmp_path / "gh.log", assets=assets)

    result = run_gh(
        stub, "release", "download", "v9.9.9", "--pattern", "*_linux_amd64.tar.gz",
        cwd=into, stubs=stubs,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert list(into.iterdir()) == []


@pytest.mark.parametrize("written,newline", WRITTEN_PINS, ids=PIN_IDS)
def test_the_bootstrap_downloads_the_release_the_pin_names(
    tmp_path: Path, written: str, newline: str
) -> None:
    """The release publishes every platform's asset and the script picks one, on any platform.

    Both halves of the selection are asserted: the pattern that reached `gh`, and the binary
    name that ended up in `tools/`. Neither is spelled out here -- both come from
    `oasdiff_asset.sh`, so a mapping that changed and a test that agreed with the old one cannot
    both stay green.
    """
    root = checkout(tmp_path, pin=written, newline=newline)
    result, called = run_bootstrap(
        root, tmp_path=tmp_path, assets=release(tmp_path, version="9.9.9")
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert len(called) == 1, called
    assert "v9.9.9" in called[0]
    assert platform_asset() in called[0], called[0]
    assert (root / "tools" / platform_binary()).is_file()


def test_the_bootstrap_refuses_a_release_that_publishes_nothing_for_this_platform(
    tmp_path: Path,
) -> None:
    """A tag whose assets do not include this machine's is a refusal, not a silent wrong build.

    This is the case a stub answering every pattern with one archive could never reach: it
    always had something to hand over, so the bootstrap always got a file and the mapping was
    never consulted for anything.
    """
    root = checkout(tmp_path, pin="9.9.9")

    result, called = run_bootstrap(
        root,
        tmp_path=tmp_path,
        assets=release(tmp_path, version="9.9.9", suffixes=(foreign_suffix(),)),
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert len(called) == 1, called
    assert not (root / "tools" / platform_binary()).exists()


def test_a_checkout_holding_an_unpinned_build_is_refused_and_left_untouched(
    tmp_path: Path,
) -> None:
    """The defect this task closes. The old script exited 0 here and changed nothing."""
    root = checkout(tmp_path, pin="9.9.9", holds="1.26.0")
    before = (root / "tools" / platform_binary()).read_bytes()

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, assets=release(tmp_path, version="9.9.9")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert called == [], "a refusal must not download anything"
    assert (root / "tools" / platform_binary()).read_bytes() == before
    complaint = result.stdout + result.stderr
    assert "1.26.0" in complaint and "9.9.9" in complaint


def test_a_checkout_holding_the_pinned_build_succeeds_without_downloading(
    tmp_path: Path,
) -> None:
    root = checkout(tmp_path, pin="9.9.9", holds="9.9.9")

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, assets=release(tmp_path, version="9.9.9")
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert called == []


def test_a_binary_that_cannot_run_is_refused_rather_than_treated_as_absent(
    tmp_path: Path,
) -> None:
    root = checkout(tmp_path, pin="9.9.9")
    fake_oasdiff(root / "tools" / platform_binary(), version="", exit_code=3)

    result, called = run_bootstrap(
        root, tmp_path=tmp_path, assets=release(tmp_path, version="9.9.9")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert called == []
    # Named rather than folded into the version mismatch. Reading `--version` without its exit
    # code makes an unrunnable binary indistinguishable from one reporting an empty version,
    # which sends the operator looking for a version problem that is not there.
    assert "'--version' failed" in result.stderr, result.stderr


def test_the_bootstrap_fails_when_the_download_fails(tmp_path: Path) -> None:
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(root, tmp_path=tmp_path, assets=None, gh_exit=1)

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / platform_binary()).exists()


def test_the_bootstrap_fails_when_the_download_produces_nothing(tmp_path: Path) -> None:
    """`gh` exiting 0 without writing a tarball. `set -e` has to carry this one."""
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(root, tmp_path=tmp_path, assets=None, gh_exit=0)

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / platform_binary()).exists()


def test_the_bootstrap_refuses_a_download_that_is_not_the_release_it_asked_for(
    tmp_path: Path,
) -> None:
    """A tag and its contents can disagree, and printing the version does not notice."""
    root = checkout(tmp_path, pin="9.9.9")

    result, _ = run_bootstrap(
        root, tmp_path=tmp_path, assets=release(tmp_path, version="1.26.0")
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert not (root / "tools" / platform_binary()).exists(), (
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

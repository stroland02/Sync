"""Which oasdiff release `scripts/bootstrap_tools.sh` fetches, per platform.

The selection used to be a literal `*windows_amd64.tar.gz` in the download line, followed by a
verification of `./oasdiff.exe`, so every macOS and Linux checkout was blocked at the third
command of the Quick start. This machine is Windows and cannot execute the other branches, so
the mapping is a shell function and these tests call it with a `uname` pair rather than
pretending to have run anywhere else. What is proved is the selection; that each asset exists
under the pinned tag is proved by `.oasdiff-version` and the release itself.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

MAPPING = Path(__file__).resolve().parents[1] / "scripts" / "oasdiff_asset.sh"

BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(
    BASH is None, reason="bash is absent from this platform's PATH, and scripts/ is written for it"
)


def _call(function: str, *args: str) -> subprocess.CompletedProcess[str]:
    quoted = " ".join(f"'{arg}'" for arg in args)
    return subprocess.run(
        [BASH, "-c", f". '{MAPPING.as_posix()}'; {function} {quoted}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "*_linux_amd64.tar.gz"),
        ("Linux", "aarch64", "*_linux_arm64.tar.gz"),
        ("Linux", "arm64", "*_linux_arm64.tar.gz"),
        ("Darwin", "arm64", "*_darwin_all.tar.gz"),
        ("Darwin", "x86_64", "*_darwin_all.tar.gz"),
        ("MINGW64_NT-10.0-26200", "x86_64", "*_windows_amd64.tar.gz"),
        ("MSYS_NT-10.0-26200", "x86_64", "*_windows_amd64.tar.gz"),
        ("CYGWIN_NT-10.0", "x86_64", "*_windows_amd64.tar.gz"),
        ("Windows_NT", "arm64", "*_windows_arm64.tar.gz"),
    ],
)
def test_the_asset_pattern_follows_the_platform(system, machine, expected):
    result = _call("oasdiff_asset", system, machine)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_every_pattern_ends_in_the_archive_the_script_untars():
    """oasdiff also publishes `.apk`, `.deb` and `.rpm` for Linux, and `gh release download`
    takes every asset its pattern matches. A pattern that stopped at the architecture would
    fetch four files and hand `tar` a Debian package."""
    for machine in ("x86_64", "aarch64"):
        assert _call("oasdiff_asset", "Linux", machine).stdout.strip().endswith(".tar.gz")


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Linux", "oasdiff"),
        ("Darwin", "oasdiff"),
        ("MINGW64_NT-10.0-26200", "oasdiff.exe"),
        ("Windows_NT", "oasdiff.exe"),
    ],
)
def test_the_extracted_binary_is_named_for_the_platform(system, expected):
    result = _call("oasdiff_binary", system)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_an_unknown_platform_is_refused_rather_than_guessed():
    """A wrong guess downloads an archive for another machine and fails at `--version` with
    nothing saying why. Naming the `uname` it could not place is the whole of the fix."""
    system = _call("oasdiff_asset", "Plan9", "x86_64")
    assert system.returncode != 0
    assert "Plan9" in system.stderr

    machine = _call("oasdiff_asset", "Linux", "s390x")
    assert machine.returncode != 0
    assert "s390x" in machine.stderr


def test_the_bootstrap_script_names_no_platform_of_its_own():
    """One mapping, read by the one script that downloads. A literal left behind in the
    download or the verification is the defect returning in the place it was."""
    script = (MAPPING.parent / "bootstrap_tools.sh").read_text(encoding="utf-8")

    assert "oasdiff_asset.sh" in script
    for literal in ("windows_amd64", "linux_amd64", "darwin_all"):
        assert literal not in script

"""A measurement records which differ produced it, and that record has to be true.

`tools/` is gitignored and populated per checkout by `scripts/bootstrap_tools.sh`, which downloads
whatever oasdiff release is latest on the day it runs rather than a pinned one. Two working copies
of this repository therefore hold different builds at the same time -- measured on 2026-07-29, four
held 1.26.0 and four held 1.26.1 -- so a report naming its differ only in prose cannot be checked
afterwards by anyone, including its author.
`docs/superpowers/reports/2026-07-29-oasdiff-version-settled.md` is what that cost.

Two properties make the recorded instrument worth committing, and neither is free:

The version string does not identify the binary. Both builds answer to `oasdiff`, and a reader
holding one of them cannot tell from the name whether it is the one that ran. The sha256 is what
makes a recorded number attributable to an exact file.

The record must not be able to come out empty. `--version` on a binary that exists but cannot run
returns an empty `stdout`, and an unchecked read of it writes `""` into the artifact -- a
measurement that looks recorded and identifies nothing, which is worse than one that refuses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.measure_generated_vendor_noise import InstrumentUnavailable, read_instrument


def stub_binary(directory: Path, *, prints: str = "", exit_code: int = 0) -> Path:
    """An executable answering `--version` however a case needs it to.

    Two spellings because this suite runs on Windows here and on Linux in CI, and a stub that only
    executes on one of them is a test that only runs on one of them.
    """
    directory.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        path = directory / "oasdiff.cmd"
        lines = ["@echo off"]
        if prints:
            lines.append(f"echo {prints}")
        lines.append(f"exit /b {exit_code}")
        body = "\r\n".join(lines) + "\r\n"
    else:
        path = directory / "oasdiff"
        lines = ["#!/bin/sh"]
        if prints:
            lines.append(f"printf '%s\\n' '{prints}'")
        lines.append(f"exit {exit_code}")
        body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


# --- the version recorded is the version reported -------------------------------


@pytest.mark.parametrize("reported", ["oasdiff version 1.26.0", "oasdiff version 1.26.1"])
def test_the_recorded_version_is_the_one_the_binary_reported(tmp_path: Path, reported: str) -> None:
    assert read_instrument(stub_binary(tmp_path, prints=reported)).version == reported


def test_two_binaries_reporting_one_version_are_told_apart_by_the_hash(tmp_path: Path) -> None:
    """The case this file exists for: the name agrees and the bytes do not."""
    reported = "oasdiff version 1.26.1"
    one = read_instrument(stub_binary(tmp_path / "one", prints=reported))
    two = read_instrument(stub_binary(tmp_path / "two", prints=reported + "  "))

    assert one.version == two.version == reported
    assert one.sha256 != two.sha256


# --- an unusable binary is an error, never an empty field ------------------------


def test_a_missing_binary_is_an_error_rather_than_an_empty_field(tmp_path: Path) -> None:
    missing = tmp_path / "tools" / "oasdiff.exe"

    with pytest.raises(InstrumentUnavailable) as caught:
        read_instrument(missing)

    assert str(missing) in str(caught.value)


def test_a_binary_that_fails_is_an_error_rather_than_an_empty_field(tmp_path: Path) -> None:
    with pytest.raises(InstrumentUnavailable):
        read_instrument(stub_binary(tmp_path, prints="wat", exit_code=3))


def test_a_binary_that_prints_nothing_is_an_error_rather_than_an_empty_field(
    tmp_path: Path,
) -> None:
    with pytest.raises(InstrumentUnavailable):
        read_instrument(stub_binary(tmp_path))

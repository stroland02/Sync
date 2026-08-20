"""B101: two typechecks on one host racing on a shared, cold npx cache.

`run_tsc`'s fallback (no local `tsc`) used to jump straight from "the cache
might be cold" to executing the compiler through it, with no coordination
between two processes that reach that fallback at the same time. This was
observed for real in CI on 2026-08-06 (run 31099640833): several
pytest-xdist workers hit the fallback together against a cold cache, and the
loser's verification came back as `abandon_reason='RuntimeError: could not
establish a typecheck baseline ... ETXTBSY'` -- which reads as a bad patch,
not as two processes fighting over one directory.

Reproducing that exact failure through the real `npx` on this machine did not
work. Up to sixteen concurrent `npx --yes --package=typescript@latest`
resolves, each against its own genuinely fresh cache directory (via
`npm_config_cache` pointed at a fresh `tempfile.mkdtemp()`, so this never
touched the real shared cache), completed cleanly every time on the npm here
(12.0.1) -- its cache writer appears to already serialize the extraction step
internally, closing the specific race the backlog entry describes. The
backlog's own escape hatch covers exactly this: force the same shape of
race -- check whether a shared cache target exists, and if not, write it and
use it, with nothing stopping a second caller from doing the same thing at
the same time -- through a substitute for `npx` this test controls, so the
race is forced deterministically instead of betting on network timing an npm
upgrade already closed. `fixtures/fake_npx/fake_npx.py` reproduces that
shape, with a real pause in the middle of the write so two concurrent callers
reliably interleave rather than occasionally.

The substitution is only `shutil.which("npx")` finding the fake script
instead of the real binary, through `PATH` -- the same lookup `run_tsc`
already documents needing because Windows resolves it as `npx.cmd`. Every
other line of `run_tsc` runs unmodified, so this is a real end-to-end
exercise of the code the fix changes, not a test of an isolated helper.
"""

from __future__ import annotations

import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sync.index.tsc import run_tsc

FAKE_NPX_SCRIPT = Path(__file__).parent / "fixtures" / "fake_npx" / "fake_npx.py"

_WINDOWS_LAUNCHER = (
    '@echo off\r\n"{python}" "{script}" %*\r\nexit /b %errorlevel%\r\n'
)
_POSIX_LAUNCHER = '#!/bin/sh\nexec "{python}" "{script}" "$@"\n'


@pytest.fixture()
def fake_npx_on_path(tmp_path: Path, monkeypatch) -> Path:
    """Put a fake `npx` ahead of the real one on `PATH`, pointed at a fresh,
    empty cache directory it will race on -- never the real `~/.npm/_npx`.
    """
    bin_dir = tmp_path / "fake_npx_bin"
    bin_dir.mkdir()
    on_windows = os.name == "nt"
    launcher = bin_dir / ("npx.cmd" if on_windows else "npx")
    template = _WINDOWS_LAUNCHER if on_windows else _POSIX_LAUNCHER
    launcher.write_text(
        template.format(python=sys.executable, script=FAKE_NPX_SCRIPT), encoding="utf-8"
    )
    if not on_windows:
        launcher.chmod(0o755)

    cache_dir = tmp_path / "cold_cache"
    cache_dir.mkdir()

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_NPX_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("FAKE_NPX_RACE_DELAY_SECONDS", "2.0")

    found = shutil.which("npx")
    assert found is not None and Path(found).resolve() == launcher.resolve(), (
        f"the fake npx did not shadow the real one on PATH: shutil.which found {found!r}"
    )
    return cache_dir


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    # No node_modules/.bin/tsc anywhere in this tree, so run_tsc must take
    # the npx fallback branch -- the one this test is about. A tsconfig has to
    # exist, because run_tsc now refuses a tree with no TypeScript project in
    # it before it ever resolves a compiler.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tsconfig.json").write_text("{}", encoding="utf-8")
    return repo


def test_two_concurrent_typechecks_against_a_cold_cache_do_not_race(
    fake_npx_on_path: Path, project: Path
):
    """Two callers reaching the npx fallback against a cold cache at the same
    time must both succeed. Run against the code as it stood before B101's
    fix, this reliably failed: one `run_tsc` call came back `ok=False` with
    an `EBUSY`-shaped diagnostic, `fake_npx.py`'s stand-in for the real
    `ETXTBSY`/corrupt-read a loser sees when it reads the other caller's
    half-written cache entry. That is the RED half of B101's close condition,
    watched directly rather than assumed -- confirmed by running this exact
    test against `tsc.py` before `_ensure_typescript_resolved` and
    `npx_lock.resolve_lock` existed. A test that merely ran two `run_tsc`
    calls one after another would never reach the fallback while the cache
    was still cold for both, and would prove nothing.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run_tsc, project, timeout=30)
        second = pool.submit(run_tsc, project, timeout=30)
        results = [first.result(), second.result()]

    assert [r.ok for r in results] == [True, True], (
        f"a concurrent cold-cache resolve failed: {results}"
    )
    assert all(r.diagnostics == "" for r in results)


def test_a_warm_cache_skips_the_resolve_lock(fake_npx_on_path: Path, project: Path):
    """Once the cache is warm, callers must not acquire the resolve lock.

    `resolve_lock` exists to guard the one-time resolve against ETXTBSY/EBUSY.
    If subsequent typechecks still acquired the lock, parallel runs would serialize
    and starve under test concurrency.
    """
    from sync.index.tsc import _lock_path

    # First run warms the cache and writes the marker
    result1 = run_tsc(project, timeout=30)
    assert result1.ok

    # Manually hold/block the lock directory
    lock = _lock_path()
    lock.mkdir(exist_ok=True)
    try:
        # Second run on a warm cache must succeed quickly without waiting on the blocked lock
        result2 = run_tsc(project, timeout=1.0)
        assert result2.ok
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


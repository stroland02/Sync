"""A host-wide lock around npx's cold-cache package resolve.

`npx --package=typescript@latest` writes into a directory under the user's
npm cache (`~/.npm/_npx/<hash>` on POSIX, `%LOCALAPPDATA%\\npm-cache\\_npx\\<hash>`
on Windows) that is shared by every process the user runs on this host. Two
callers reaching that directory at once while it is still cold race on it:
one is still writing the package while the other tries to use what it wrote,
which Linux answers with `ETXTBSY` and which, on any OS, can just as well
hand the second caller a file that is missing, truncated, or mid-rewrite.

The fix is not to lock the whole typecheck. Once the cache is warm, `npx`
only checks that the package is already there and runs it, which is safe to
enter from any number of processes at once -- a host-wide lock around every
compile would serialize every verification on the host long after the race
window had closed, which is exactly the latency cost this repository's
specification rules out an agent adding for no result. `resolve_lock` exists
to guard only the one-time resolve, not the compile that follows it.

A lock directory, not `threading.Lock`, because the callers this guards are
different OS processes -- often different `sync` runs entirely, verifying
different customers' patches -- not different threads of one interpreter.
`Path.mkdir()` is atomic on both Windows and POSIX (unlike a plain file
write, which can itself race), which is what makes it usable as a
cross-process mutex without a third-party dependency and without ever having
to open or write the lock itself -- the directory's existence is the whole
of the state.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path

_POLL_SECONDS = 0.05

# Deliberately not `timeout` below: staleness answers "could the process that
# created this lock still legitimately be running", which does not shrink
# just because one particular caller was handed a small wait budget. A
# caller forcing a near-zero `timeout` to test its own timeout handling must
# not be able to steal a lock a different, live process is genuinely
# holding -- conflating the two did exactly that the first time this was
# written: `test_timeout_is_caught_and_reported_as_a_failed_verification`
# passes `timeout=0.001`, another pytest-xdist worker held the real lock a
# few milliseconds old, `0.001` read that as ancient, and the test deleted a
# live worker's lock out from under it.
_STALE_LOCK_SECONDS = 300


class LockTimeout(RuntimeError):
    """A resolve lock could not be acquired before its deadline.

    Surfaced as a failure rather than left to hang indefinitely -- the same
    reasoning `run_tsc` already applies to a compiler that hangs.
    """


@contextmanager
def resolve_lock(lock_path: Path, timeout: float):
    """Hold an exclusive, cross-process lock at `lock_path` for the block.

    `lock_path` is a directory, created to acquire and removed to release;
    its content never matters, only its existence and its age. `timeout`
    bounds only how long this call waits before giving up; a lock older than
    `_STALE_LOCK_SECONDS` is treated as abandoned -- left behind by a
    process that was killed while holding it -- and is removed rather than
    left to block every future caller forever.
    """
    deadline = time.monotonic() + timeout
    acquired = False
    while not acquired:
        try:
            lock_path.mkdir()
            acquired = True
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue  # released between this attempt's mkdir() and stat()
            if age > _STALE_LOCK_SECONDS:
                try:
                    lock_path.rmdir()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise LockTimeout(
                    f"timed out after {timeout}s waiting for the resolve lock at {lock_path}"
                )
            time.sleep(_POLL_SECONDS)
    try:
        yield
    finally:
        lock_path.rmdir()

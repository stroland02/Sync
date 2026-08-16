"""Keep a failing run's output somewhere the next run cannot overwrite it.

A run came back `1 failed, 2897 passed, 4 skipped, 12 warnings, 6 errors`, the immediate rerun was
green, and the text was gone. A flake and an intermittent defect look identical from a summary, so
that run can no longer be diagnosed at all. Nobody forgot to save it; there was nothing that saved
it.

**Nothing pytest ships does this.** `--last-failed` persists node ids and no output, and a green run
empties `lastfailed`. `--junitxml` carries the failure text and writes it to the single path the
flag names, so the next run overwrites it. `--stepwise` and the rest of `.pytest_cache` are the same
shape. Every built-in that survives a process is keyed on a fixed location, which is exactly what
makes it not survive the next run.

So: the terminal writer's file is wrapped for the life of the session, and if the run ends non-zero
the copy is written under a name no other run can produce. What is kept is what the terminal
received, byte for byte -- a rendering built from the reports would be a summary, and a summary is
what everyone already had.

**Only red runs are written, and the outcome is known in time.** `pytest_sessionfinish` carries the
exit status and `pytest_unconfigure` runs after it, so the decision to write is made when the
verdict already exists. A green run therefore does no filesystem work at all: it wraps a file, joins
nothing, and drops the copy.

`KEEP` bounds the directory. Retention runs on the write, so pruning is also off the green path.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

KEEP = 10
"""How many red runs are kept, newest first.

Red runs only rather than the last N of everything: a green run's output answers no question, and
keeping it would push the red one out of the window exactly when somebody reruns to see whether it
reproduces. Ten because the failure this exists for was one red in a sequence of greens, and a
window of one would be emptied by the second red of an afternoon spent chasing it.
"""

DIR_VARIABLE = "SYNC_RED_RUN_DIR"
"""Where to write, for an operator who wants the captures somewhere else, and for the test.

`tests/test_red_run_capture.py` drives real child runs and points them at a temporary directory
with this, so watching the mechanism work does not fill the repository's own.
"""

class _Tee:
    """Writes through, and keeps what it wrote.

    Wrapping the file under `TerminalWriter` rather than re-rendering from the collected reports.
    The reports would give a second rendering of the same failures, and this exists because a
    rendering is what the lost run left behind.
    """

    def __init__(self, wrapped: TextIO) -> None:
        self._wrapped = wrapped
        self.chunks: list[str] = []

    def write(self, text: str) -> int:
        # The wrapped file first. `TerminalWriter.write_raw` catches `UnicodeEncodeError` from it
        # and retries the whole write escaped to ASCII, so a copy taken before that retry would
        # hold text the terminal never received.
        written = self._wrapped.write(text)
        self.chunks.append(text)
        return written

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)


_tee: _Tee | None = None
_exitstatus: int = 0


def output_dir(config) -> Path:
    """`.cache/red-runs/` under the root, which `.gitignore` already covers.

    Already ignored rather than newly ignored: an artifact that shows up in `git status` is one
    somebody commits by accident, and `.cache/` is where this repository already stages generated
    inputs nobody tracks.
    """
    override = os.environ.get(DIR_VARIABLE)
    if override:
        return Path(override)
    return Path(config.rootpath) / ".cache" / "red-runs"


def start(config) -> None:
    """Wrap the terminal writer for the rest of the session.

    Called from `pytest_sessionstart` and not from `pytest_configure`: the terminal reporter is
    registered by a plugin whose own `pytest_configure` runs after every conftest's, so at configure
    time there is nothing to wrap. Measured, not assumed.

    Under xdist only the controller renders anything, and a worker that wrote a file of its own
    would give one run a capture per process. The worker is identified two ways because either
    alone is someone else's implementation detail: the environment variable xdist sets, and the
    absence of a terminal reporter in a worker session.
    """
    global _tee, _exitstatus
    _tee, _exitstatus = None, 0
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    _tee = _Tee(reporter._tw._file)
    reporter._tw._file = _tee


def record(exitstatus: int) -> None:
    global _exitstatus
    _exitstatus = int(exitstatus)


def finish(config) -> Path | None:
    """Write the copy if the run was red, and unwrap either way.

    Called from `pytest_unconfigure`, which is the last thing `wrap_session` does. The counts line
    -- `1 failed, 2897 passed, ...` -- is written by the terminal reporter's `pytest_sessionfinish`
    wrapper, after every ordinary `pytest_sessionfinish` hook has returned, so a capture flushed
    from one of those keeps the tracebacks and loses the verdict.

    Any non-zero status, not only a failed test. A collection error, an internal error and a usage
    error all leave output somebody would want and all get discarded by the next run the same way.
    """
    global _tee, _exitstatus
    tee, status = _tee, _exitstatus
    _tee, _exitstatus = None, 0
    if tee is None:
        return None

    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None and reporter._tw._file is tee:
        reporter._tw._file = tee._wrapped

    if status == 0:
        return None
    return write_capture(
        output_dir(config), "".join(tee.chunks), now=datetime.now(timezone.utc), pid=os.getpid()
    )


def write_capture(
    directory: Path, text: str, *, now: datetime, pid: int, keep: int = KEEP
) -> Path:
    """One file per red run, named so that no other run can claim the name.

    The timestamp is UTC to microseconds and sorts as text, so the newest `keep` are the last
    `keep` by name. The pid rules out a second run in the same microsecond; it does not rule out
    a second *capture* in one run landing on the same microsecond, which happens on Windows more
    often than the resolution suggests -- two back-to-back `datetime.now()` calls in one process
    can read the same tick. `-1`, `-2`, ... is appended on an actual name collision so the second
    write never overwrites the first; the two share a moment, so which of them sorts fractionally
    earlier carries no meaning worth a more elaborate name for.
    """
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{now:%Y%m%dT%H%M%S.%f}Z-{pid}"
    path = directory / f"{base}.log"
    collision = 0
    while path.exists():
        collision += 1
        path = directory / f"{base}-{collision}.log"
    # `newline=""` so the file holds what the terminal received rather than a Windows translation
    # of it. `errors="replace"` because this is diagnostic output and the thing being recorded is a
    # failure: a capture that raised on the run it exists for would fail exactly when it is needed.
    path.write_text(text, encoding="utf-8", errors="replace", newline="")
    for stale in sorted(directory.glob("*.log"))[:-keep]:
        stale.unlink(missing_ok=True)
    return path

"""Install one handler on the root logger, driven by two values from the environment.

`configure` is the only entry point. It is idempotent -- a second call replaces the handler
the first call installed rather than adding a second one -- so it is safe to call from more
than one process entry point (today, `sync.api.__main__`; `sync.cli` is another session's
lane) without doubling every line.
"""

from __future__ import annotations

import io
import json
import logging
import sys
from typing import Any, TextIO

# Marks a handler this module installed, so a second `configure` call can find and remove it
# instead of stacking a duplicate on the root logger.
_HANDLER_MARKER = "_sync_obs_handler"

_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_FORMATS = frozenset({"text", "json"})

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class _JsonFormatter(logging.Formatter):
    """One JSON object per record, ASCII by construction.

    `json.dumps`'s default `ensure_ascii=True` turns every non-ASCII character into a
    `\\uXXXX` escape, which is valid JSON and always encodable regardless of the stream's own
    encoding. The alternative, `ensure_ascii=False`, would hand a raw non-ASCII character to a
    stream write that can still fail on a cp1252 console, with no way to re-escape text that
    has already been serialized as a JSON string.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _rewrapped_at_utf8(stream: TextIO) -> TextIO:
    """`stream`, rewrapped over its byte buffer at UTF-8 when one is available.

    A real console or file stream exposes `.buffer`; wrapping that buffer at UTF-8 means a
    customer file path with an accented character writes correctly instead of racing the
    console's codepage. A stream with no `.buffer` -- a test double, or a capture harness --
    is returned unchanged; `_SafeStreamHandler.emit` is the backstop for that case.
    """
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream
    return io.TextIOWrapper(buffer, encoding="utf-8", errors="backslashreplace", newline="")


class _SafeStreamHandler(logging.StreamHandler):
    """A `StreamHandler` that cannot raise on a character its stream cannot encode.

    Without this, a character the stream's encoding cannot represent reaches `stream.write`,
    raises `UnicodeEncodeError`, and `Handler.handleError` swallows it -- the record never
    appears, and nothing says why. The fallback re-encodes with `backslashreplace` against the
    stream's own reported encoding, which always succeeds because every character survives as
    an ASCII escape sequence.
    """

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        try:
            self.stream.write(msg + self.terminator)
        except UnicodeEncodeError:
            encoding = getattr(self.stream, "encoding", None) or "ascii"
            safe = msg.encode(encoding, errors="backslashreplace").decode(encoding)
            self.stream.write(safe + self.terminator)
        self.flush()


def configure(*, level: str, fmt: str) -> None:
    """Install one handler on the root logger, replacing any handler this module installed
    before.

    `level` and `fmt` come from the environment (`SYNC_LOG_LEVEL`, `SYNC_LOG_FORMAT`), which
    `CLAUDE.md` names as a system boundary -- an unrecognised value raises rather than falling
    back to a default the caller never asked for and would not see.
    """
    level_name = level.upper()
    if level_name not in _LEVELS:
        raise ValueError(f"unknown log level {level!r}; must be one of {sorted(_LEVELS)}")
    if fmt not in _FORMATS:
        raise ValueError(f"unknown log format {fmt!r}; must be one of {sorted(_FORMATS)}")

    formatter: logging.Formatter = (
        _JsonFormatter() if fmt == "json" else logging.Formatter(_TEXT_FORMAT)
    )

    handler = _SafeStreamHandler(_rewrapped_at_utf8(sys.stderr))
    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_MARKER, True)

    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, _HANDLER_MARKER, False):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level_name)

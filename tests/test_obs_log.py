"""`sync.obs.log.configure` actually gets a module logger's records onto a stream.

Nine `sync.*` modules already call `logging.getLogger(__name__)`; nothing in the process ever
installed a handler, so Python's last-resort handler dropped every INFO and DEBUG record. These
tests assert the fix at the only place that matters: a record a module logger emits after
`configure` runs actually lands on the stream, not that a handler object merely exists.
"""

from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from sync.obs.log import configure


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Undoes whatever `configure` did to the *real* root logger after each test.

    `configure` is deliberately global -- it installs on `logging.getLogger()` -- so a test
    that did not restore the prior handlers and level would leak into every test that runs
    after it in the same worker process.
    """
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in original_handlers:
            root.removeHandler(handler)
    root.handlers[:] = original_handlers
    root.setLevel(original_level)


class _CP1252Stream:
    """Stands in for the real Windows console stream: it encodes to cp1252 on write and
    raises `UnicodeEncodeError` exactly as the real console would for a codepoint cp1252
    cannot represent. It deliberately has no `.buffer`, so `configure`'s UTF-8-passthrough
    path is not available and the fallback path in `_SafeStreamHandler.emit` is what gets
    exercised.
    """

    def __init__(self) -> None:
        self.encoding = "cp1252"
        self.chunks: list[str] = []

    def write(self, s: str) -> int:
        s.encode(self.encoding)
        self.chunks.append(s)
        return len(s)

    def flush(self) -> None:
        pass


def test_configure_makes_log_info_reach_the_stream(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    configure(level="INFO", fmt="text")
    log = logging.getLogger("sync.obs.test.info")
    log.info("repair tier resolved to observed")

    assert "repair tier resolved to observed" in stream.getvalue()


def test_configure_twice_attaches_one_handler_not_two(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    configure(level="INFO", fmt="text")
    configure(level="INFO", fmt="text")
    log = logging.getLogger("sync.obs.test.idempotent")
    log.info("distinct migration outcome")

    lines = [line for line in stream.getvalue().splitlines() if "distinct migration outcome" in line]
    assert len(lines) == 1, f"expected exactly one emitted line, got {lines!r}"


def test_json_format_emits_one_parseable_object_per_line(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stream)

    configure(level="INFO", fmt="json")
    log = logging.getLogger("sync.remediate.corpus")
    log.info("no tier attempted a repair")

    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["level"] == "INFO"
    assert record["logger"] == "sync.remediate.corpus"
    assert record["message"] == "no tier attempted a repair"


def test_a_non_ascii_record_does_not_raise_and_is_not_dropped(monkeypatch):
    stream = _CP1252Stream()
    monkeypatch.setattr(sys, "stderr", stream)

    configure(level="INFO", fmt="text")
    log = logging.getLogger("sync.obs.test.nonascii")

    # A customer file path with an accented character (encodable in cp1252) plus a
    # character cp1252 cannot represent at all -- the realistic worst case.
    log.info("indexed src/café_\U0001f680.ts")

    output = "".join(stream.chunks)
    assert output, "the record must reach the stream, not be silently swallowed"
    assert "café" in output, "a cp1252-representable character must survive intact"
    assert "\\U0001f680" in output, (
        "a character cp1252 cannot represent must be escaped, recoverably, not dropped"
    )


def test_non_ascii_record_is_preserved_exactly_when_the_stream_has_a_real_buffer(monkeypatch):
    # A real console/file stream exposes `.buffer`; `configure` prefers to rewrap that buffer
    # at UTF-8 rather than fall back to an escape, so the character survives untouched.
    raw = io.BytesIO()
    wrapped = io.TextIOWrapper(raw, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stderr", wrapped)

    configure(level="INFO", fmt="text")
    log = logging.getLogger("sync.obs.test.buffer")
    log.info("indexed src/café_\U0001f680.ts")

    written = raw.getvalue().decode("utf-8")
    assert "café_\U0001f680.ts" in written


def test_unknown_level_raises_rather_than_silently_falling_back():
    with pytest.raises(ValueError):
        configure(level="TRACE", fmt="text")


def test_unknown_format_raises_rather_than_silently_falling_back():
    with pytest.raises(ValueError):
        configure(level="INFO", fmt="xml")

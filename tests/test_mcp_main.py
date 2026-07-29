"""`main()`, driven in this process, where a coverage run can see what it did.

`tests/test_mcp_entry_point.py` starts `sync-mcp` as a subprocess, which is the right way to
assert that a console script exists and that its stdout is clean -- and it is measured by
nothing, because coverage sees only the process it runs in.
`docs/superpowers/specs/2026-07-29-sync-coverage-baseline-2.md` names that gap directly: the
module reads as the least-covered file in the tree and is one of the better-tested ones.

So these drive the same function over streams this process owns. What that buys is not the
percentage: it is the three claims `main`'s docstring makes which the subprocess tests cannot
separate from the ambient environment -- that a missing `SYNC_DSN` is an exit status rather
than a server waiting on a stream, that both streams are UTF-8 whatever the locale declares,
and that the surface this entry point serves is read-only.

The streams are `TextIOWrapper`s over `BytesIO` rather than `StringIO` because `main` calls
`reconfigure` on both, which only a wrapper over a byte stream has -- and because declaring the
wrong encoding on the way in is the only way to show that the reconfigure is doing something.
"""

from __future__ import annotations

import io
import json
import runpy
import sys

import pytest

from sync.mcp.server import PROTOCOL_VERSION, main

# `main` builds a `GraphStore` from this and `GraphStore` connects lazily, so nothing here
# reaches Postgres. The name is deliberately one no server hosts: a test that later calls a
# tool which reads the graph must fail loudly rather than quietly using a database it shares
# with another run.
UNCONNECTED_DSN = "postgresql://sync:sync@localhost:5433/sync_main_never_connects"


def _drive(
    monkeypatch: pytest.MonkeyPatch,
    *requests: dict,
    stdin_declares: str = "utf-8",
    stdout_declares: str = "utf-8",
) -> tuple[int, bytes]:
    """Run `main` over streams this test owns, and hand back its status and the raw bytes.

    The request text is always encoded UTF-8, which is what an MCP client sends. What varies is
    the encoding the wrapper was *declared* with, standing in for the machine's locale -- so a
    test can tell a stream `main` reconfigured from one it left alone.
    """
    payload = "".join(json.dumps(request, ensure_ascii=False) + "\n" for request in requests)
    source = io.TextIOWrapper(io.BytesIO(payload.encode("utf-8")), encoding=stdin_declares)
    sink = io.BytesIO()
    # Held in a local for the duration of the call. `main` reassigns `sys.stdout`, so a wrapper
    # referenced only from there is collected mid-run and closes `sink` on the way out.
    protocol = io.TextIOWrapper(sink, encoding=stdout_declares)

    monkeypatch.setattr(sys, "stdin", source)
    monkeypatch.setattr(sys, "stdout", protocol)
    monkeypatch.setenv("SYNC_DSN", UNCONNECTED_DSN)

    status = main()
    return status, sink.getvalue()


def _frames(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def test_no_dsn_is_an_exit_status_rather_than_a_server_that_waits_on_a_stream(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """The one configuration failure this entry point can have, and the only wrong answer to it
    is silence. A stdio server that reads stdin before deciding it cannot serve is
    indistinguishable to its client from one doing slow work: the client waits, the launcher
    waits, and no log says why. So the check comes before either stream is touched, the reason
    goes to stderr where a launcher shows it, and the status is non-zero.
    """
    monkeypatch.delenv("SYNC_DSN", raising=False)

    status = main()

    captured = capsys.readouterr()
    assert status == 2
    assert "SYNC_DSN is not set" in captured.err
    assert captured.out == ""


def test_the_entry_point_reads_its_stream_as_utf_8_whatever_the_locale_declares(
    monkeypatch: pytest.MonkeyPatch
):
    """Python decodes stdin with the machine's codepage, which here is cp1252, and every MCP
    client sends UTF-8. Without the reconfigure a request naming a non-ASCII path or symbol is
    mangled before the server sees it, and `json.dumps` escapes the mangling on the way out --
    so the server answers confidently about a string nobody sent.

    The stream below is UTF-8 bytes behind a wrapper that declares cp1252, which is exactly the
    shape of the real failure. The tool name comes back in the error message, so the assertion
    reads the bytes the server actually decoded rather than a line number.
    """
    status, raw = _drive(
        monkeypatch,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "sync_café", "arguments": {}}},
        stdin_declares="cp1252",
    )

    assert status == 0
    assert _frames(raw)[0]["result"]["content"][0]["text"] == "unknown tool: sync_café"


def test_the_entry_point_serves_the_stream_it_captured_and_hands_stdout_to_stderr(
    monkeypatch: pytest.MonkeyPatch
):
    """Two halves of one decision, and a client sees the same symptom from either being wrong.

    `main` takes the real stdout for the protocol and then points `sys.stdout` at stderr, so a
    `print` left in a code path or a logging handler somebody adds later lands where it is
    readable instead of in the middle of a frame. The frames therefore have to arrive on the
    stream captured at entry, and `sys.stdout` afterwards has to be stderr.

    The wrapper declares UTF-16 rather than cp1252 because cp1252 cannot fail here: `json.dumps`
    escapes non-ASCII, so every frame this server writes is ASCII and cp1252 encodes it
    identically to UTF-8. UTF-16 does not, which is what makes the outbound reconfigure
    observable at all.
    """
    status, raw = _drive(
        monkeypatch,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        stdout_declares="utf-16",
    )

    assert status == 0
    assert sys.stdout is sys.stderr
    frames = _frames(raw)
    assert [frame["id"] for frame in frames] == [1, 2]
    assert frames[0]["result"]["protocolVersion"] == PROTOCOL_VERSION


# `run_module` executes a module that is already imported, which it warns about because a module
# with state would then have two copies of it. This one is imports and four constants.
@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_running_the_module_as_a_script_exits_with_the_status_main_returned(
    monkeypatch: pytest.MonkeyPatch
):
    """`sync-mcp` is one way in and `python -m sync.mcp.server` is the other, and a launcher
    that takes the second learns whether the server started only from the exit status. A module
    guard that swallowed it would report every misconfiguration as a clean shutdown.
    """
    monkeypatch.delenv("SYNC_DSN", raising=False)

    with pytest.raises(SystemExit) as exit_:
        runpy.run_module("sync.mcp.server", run_name="__main__")

    assert exit_.value.code == 2

"""`sync-mcp`: the last inch between a server that works and one something can start.

`docs/superpowers/specs/2026-07-26-sync-review-integration.md` describes how Sync attaches to a
code reviewer -- "Sync's server is stdio with a `sync-mcp` entry point and `sync_`-prefixed
tools, so it attaches with no adapter and no name collision" -- and Open Code Review starts each
MCP server as a subprocess *by command*. Without that command the transport is complete,
correct, and unreachable by the one mechanism designed to reach it.

So these tests run the command the way OCR runs it: a subprocess, a request on stdin, a response
on stdout. Nothing here imports `serve` and calls it with two buffers; `tests/test_mcp_server.py`
already does that, and it is exactly the thing that cannot catch a missing console script, a
banner printed at import, or a logging handler pointed at stdout.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sync.mcp import PROTOCOL_VERSION, TOOL_NAMES, schemas_as_data

REPO_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = REPO_ROOT / "docs" / "integrations" / "opencodereview"
GOLDEN = Path(__file__).parent / "golden" / "tool_schemas.json"

# What OCR registers, and the whole of it. The spec keeps the added surface to two tools rather
# than four on Open Code Review's own finding that each added tool perturbs the whole call chain.
WHITELIST = ["sync_explain_call_site", "sync_whats_at_risk"]


def _command() -> str:
    """The installed `sync-mcp`, resolved the way a subprocess launcher would find it.

    Looked up beside the running interpreter first because that is this environment's console
    script directory, and `PATH` is whatever the developer's shell happens to carry.
    """
    scripts = Path(sys.executable).parent
    for candidate in (scripts / "sync-mcp.exe", scripts / "sync-mcp"):
        if candidate.exists():
            return str(candidate)
    found = shutil.which("sync-mcp")
    if found is None:
        pytest.fail("sync-mcp is not installed; OCR starts this server by command")
    return found


def _speak(*requests: dict) -> subprocess.CompletedProcess[str]:
    """Run the console script over one stdin script, as OCR's stdio transport would.

    `encoding="utf-8"` explicitly. Without it `subprocess` decodes with the machine's locale
    codepage, and on this one a decode error is raised on the reader thread where it never
    propagates: the call returns with `stdout` set to `None`, and the failure surfaces somewhere
    unrelated. Here stdout *is* the substance of the test.
    """
    environment = {**os.environ, "SYNC_DSN": os.environ.get("SYNC_DSN", "")}
    return subprocess.run(
        [_command()],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=environment,
    )


def _frames(completed: subprocess.CompletedProcess[str]) -> list[dict]:
    return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]


# --- the process ------------------------------------------------------------------


def test_the_console_script_is_installed():
    """The failure this task exists to fix, asserted on its own so it is not diagnosed through
    a protocol test that cannot start the process."""
    assert Path(_command()).exists()


def test_the_console_script_answers_initialize_over_stdio():
    """One `initialize` in, one well-formed response out. This is precisely OCR's first frame,
    and a server that cannot answer it is never asked for its tools."""
    completed = _speak({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

    assert completed.returncode == 0, completed.stderr
    frame = _frames(completed)[0]
    assert frame["jsonrpc"] == "2.0"
    assert frame["id"] == 1
    assert frame["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert frame["result"]["serverInfo"]["name"] == "sync"


def test_stdout_carries_protocol_frames_and_nothing_else():
    """The failure that would be hardest to diagnose in the field.

    A banner, a `print` left in an import, or a logging handler pointed at stdout corrupts the
    JSON-RPC stream, and the client reports a protocol error -- so the search starts in the
    framing code, which is not where the bug is. Asserting the first byte and the frame count
    together catches a prologue, an epilogue and an interleaved line: two requests must produce
    exactly two lines, and every one of them must parse.
    """
    completed = _speak(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert completed.stdout.startswith('{"jsonrpc"')
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == [1, 2]


def test_a_stray_write_to_stdout_lands_on_stderr_rather_than_in_the_stream():
    """The test above proves today's stream is clean; this one proves it stays clean.

    A logging handler somebody points at stdout, a library banner on first use, a `print` left in
    a code path -- none of those exist today and any of them corrupts every frame after it. The
    driver below stands in for one: it wraps `serve` so the write happens after `main` has taken
    the stream, which is exactly when a real one would happen.
    """
    driver = (
        "import sync.mcp.server as server\n"
        "original = server.serve\n"
        "def noisy(*args, **kwargs):\n"
        "    print('a library banner')\n"
        "    return original(*args, **kwargs)\n"
        "server.serve = noisy\n"
        "raise SystemExit(server.main())\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", driver],
        input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n",
        capture_output=True, text=True, encoding="utf-8", timeout=120,
        env={**os.environ, "SYNC_DSN": os.environ.get("SYNC_DSN", "")},
    )

    assert completed.stdout.startswith('{"jsonrpc"')
    assert json.loads(completed.stdout.splitlines()[0])["id"] == 1
    assert "a library banner" in completed.stderr


def test_a_request_carrying_non_ascii_text_is_read_as_utf_8():
    """Python decodes stdin with the machine's locale codepage, which here is cp1252, and a
    client sending UTF-8 -- which every MCP client does -- then has its request mangled before
    the server sees it. `json.dumps` escapes non-ASCII on the way out, so the corruption is
    invisible in the response too: the server answers confidently about a string nobody sent.

    Every fixture in this repository is ASCII, which is why `scripts/lint_encoding.py` exists;
    this path is one a fixture can reach, so it is asserted rather than linted.
    """
    completed = _speak(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "sync_café", "arguments": {}}},
    )

    frame = _frames(completed)[0]
    assert frame["result"]["isError"] is True
    assert frame["result"]["content"][0]["text"] == "unknown tool: sync_café"


def test_a_notification_is_not_answered_on_stdout():
    """`initialized` carries no id and takes no reply. A server that answers it writes a frame
    the client never asked for, which desynchronises every response after it."""
    completed = _speak(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    )

    assert len(_frames(completed)) == 1


# --- what the whitelist names -----------------------------------------------------


def _registration() -> dict:
    return json.loads((INTEGRATION / "config.json").read_text(encoding="utf-8"))


def test_the_registration_starts_the_server_by_the_command_that_exists():
    """The artifact and the entry point are one fact written in two files. A registration naming
    a command nobody installed fails at OCR's subprocess launch, with no Sync log to read."""
    assert _registration()["mcp_servers"]["sync"]["command"] == "sync-mcp"


def test_the_whitelist_names_two_tools_rather_than_four():
    """Deliberate, not an omission: each added tool perturbs the whole call chain, so a review
    agent gets the minimum that answers its question."""
    assert _registration()["mcp_servers"]["sync"]["tools"] == WHITELIST


def test_every_whitelisted_tool_is_one_the_server_advertises():
    """A whitelist entry that matches nothing registers nothing, silently -- OCR skips names it
    cannot resolve, so a typo here costs the whole integration with no error anywhere."""
    completed = _speak({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    advertised = {tool["name"] for tool in _frames(completed)[0]["result"]["tools"]}

    assert set(WHITELIST) <= advertised
    assert set(WHITELIST) <= set(TOOL_NAMES)


def test_the_advertised_schemas_are_the_frozen_ones():
    """Read from the golden file, over the transport rather than from the registry. The schemas
    are published, so a change to one is a breaking change to every consumer -- and this
    integration is the first consumer that is not this repository.
    """
    completed = _speak({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert _frames(completed)[0]["result"]["tools"] == json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert schemas_as_data() == json.loads(GOLDEN.read_text(encoding="utf-8"))


# --- the rule fragment ------------------------------------------------------------


def _fragment() -> str:
    return (INTEGRATION / "rules" / "sync-api-surface.md").read_text(encoding="utf-8")


def test_the_rule_attachment_adds_to_the_system_rules_rather_than_replacing_them():
    """`merge_system_rule: true` is load-bearing: all 25 of OCR's language rule sets keep
    working and Sync's fragment sits on top. Replacing them would trade a reviewer's whole rule
    set for one paragraph about vendor APIs."""
    attachment = json.loads((INTEGRATION / "rule.json").read_text(encoding="utf-8"))
    rule = attachment["rules"][0]

    assert rule["merge_system_rule"] is True
    assert rule["rule"].endswith("sync-api-surface.md")


def test_the_rule_fragment_tells_the_reviewer_when_to_stay_silent():
    """The line most likely to be trimmed by someone shortening the fragment, and the one that
    decides whether this integration is worth installing. A rule that only ever adds comments is
    a rule that adds noise, and the reviewer skims the next ten findings."""
    assert (
        "Do not comment on a third-party call whose `known_changes` is empty. Silence is the "
        "correct output." in " ".join(_fragment().split())
    )


def test_the_rule_fragment_names_the_tools_the_whitelist_registers():
    """A fragment instructing the model to call a tool OCR was never told to register is an
    instruction that cannot be followed."""
    fragment = _fragment()

    assert "sync_explain_call_site" in fragment
    for name in set(TOOL_NAMES) - set(WHITELIST):
        assert name not in fragment


def test_the_integration_readme_says_the_falsification_count_has_not_been_taken():
    """The spec requires the count before the claim: run OCR against a fixture pull request
    touching a Stripe call site with a known change, and count whether the tools are called.
    That has not been done -- OCR is a third-party binary and no test here may call one -- so the
    artifact has to say so where an installer reads it, not only in a task report that is
    archived by the time anyone installs this.
    """
    readme = (INTEGRATION / "README.md").read_text(encoding="utf-8").lower()

    assert "not been taken" in readme or "not been run" in readme
    assert "unverified" in readme

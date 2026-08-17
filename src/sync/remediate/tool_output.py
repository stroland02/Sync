"""The boundary applied to the bytes the agent fetches rather than the ones Sync hands it.

`sync.remediate.untrusted` fences the prompt. The prompt is the smaller of the two channels.
The agent then `Read`s and `Grep`s a repository whose files can hold anything, and until this
module existed a comment in the very file it was sent to edit arrived as tool output, in the
same register as Sync's own instructions, with no frame around it at all. Everything Sync
chose to include was marked; the far larger set the agent goes and gets was not.

**What makes this buildable rather than a sandbox problem: `PostToolUse` can rewrite what the
model sees.** `PostToolUseHookSpecificOutput.updatedToolOutput` is declared in the installed
SDK as "Replaces the tool output before it is sent to the model", the bundled CLI applies it,
and the hook is handed the same structured object it replaces. So the fence is the same fence,
in the same vocabulary, one layer further out.

**The one thing that has to be right is the shape, and getting it wrong fails open.** The CLI
parses a replacement against the tool's own output schema and, on a mismatch, logs an error
and *keeps the original output* -- the unfenced bytes. A control assembled from scratch would
be one CLI upgrade away from silently doing nothing. So a replacement here is always the
response object this module was handed with individual string fields rewritten: the shape is
preserved by construction. Where the fields it knows are not there, it refuses rather than
finding nothing to frame, because a framing that quietly stops framing is precisely the
"check that cannot fail" this repository has shipped twice.

Three outcomes and nothing else:

- **Framed.** The untrusted spans are wrapped and the result goes on to the model.
- **Withheld.** A `Read` whose bytes cannot be framed at all -- an image, a notebook, a PDF --
  is answered with a note instead. The run continues. Nothing a patch needs is in those bytes,
  `tool_gate` already refuses `NotebookEdit`, and abandoning a finding over an idle read would
  cost more than it buys.
- **Refused.** Content carrying one of Sync's own markers, or a result shaped in a way this
  module cannot account for. The bytes are withheld, the run is stopped, and the reason
  reaches `abandon_reason` through `agent_patch`.

What this does not do is make the agent obey the frame, and it is not containment: the bytes
are still read off the disk, and only what the *model* sees is changed. See the threat model.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sync.remediate.untrusted import (
    REPOSITORY,
    TOOL_OUTPUT,
    UntrustedTextRefused,
    fence,
    fenced_block,
)

log = logging.getLogger(__name__)

# Everything that hands the model bytes it did not write. `Edit` and `Write` report on what the
# agent itself just did, and framing Sync's own side of the conversation would teach the agent
# the elements mean nothing in particular.
FENCED_TOOLS = frozenset({"Read", "Grep", "Glob", "Bash"})

# The `Read` result arms whose payload is not text and cannot be fenced. `file_unchanged` is
# not among them: it is the CLI's own fixed notice for a second read of a file it already
# holds, it carries none of the file's bytes, and refusing it would break the ordinary loop of
# an agent that reads, edits, and reads again.
_READ_TEXT = "text"
_READ_UNCHANGED = "file_unchanged"

WITHHELD = (
    "Sync's patch agent does not receive this file. Only text it can edit is available to it. "
    "Read the source file the task named."
)

_REFUSED = (
    "Sync stopped this run: content read out of the repository carried one of Sync's own "
    "prompt boundary markers, or arrived in a shape Sync cannot frame. Nothing further will "
    "be read."
)


class UnfenceableToolOutput(RuntimeError):
    """A tool result whose shape this module cannot account for.

    Not a defensive check against something that cannot happen. Every field name below is read
    off the bundled CLI's own output schemas, and a CLI upgrade may rename one. Were that to
    happen silently, the framing would find nothing to frame and report success while passing
    the repository's bytes through untouched -- and nothing downstream would ever contradict
    it, because a patch built on injected instructions still compiles.
    """


def _framed_read(tool_input: dict[str, Any], response: dict[str, Any]) -> Any | None:
    kind = response.get("type")
    if kind == _READ_UNCHANGED:
        return None
    if kind != _READ_TEXT:
        return _withheld_read(tool_input, WITHHELD)

    file = response.get("file")
    if not isinstance(file, dict) or not isinstance(file.get("content"), str):
        raise UnfenceableToolOutput(
            "a Read result declared as text carries no `file.content` string. Sync frames what "
            "the patch agent reads before the model sees it, and a result it cannot find the "
            "content of is one it cannot frame"
        )

    # Inline rather than on lines of their own, which is the whole reason `untrusted.fence`
    # exists beside `fenced_block`. The CLI numbers these lines from `startLine`, and the
    # prompt tells the agent the call site is at `path:line`: a marker on a line of its own
    # would shift every line after it and send the agent to the wrong one.
    return {**response, "file": {**file, "content": fence(REPOSITORY, file["content"])}}


def _withheld_read(tool_input: dict[str, Any], notice: str) -> dict[str, Any]:
    """A `Read` result the CLI's schema accepts, carrying a sentence instead of the file."""
    path = tool_input.get("file_path")
    return {
        "type": _READ_TEXT,
        "file": {
            "filePath": path if isinstance(path, str) else "",
            "content": notice,
            "numLines": 1,
            "startLine": 1,
            "totalLines": 1,
        },
    }


def _framed_search(response: dict[str, Any]) -> Any | None:
    """`Grep` and `Glob`, which share `filenames` and differ only in whether `content` is set."""
    filenames = response.get("filenames")
    if not isinstance(filenames, list) or not all(isinstance(name, str) for name in filenames):
        raise UnfenceableToolOutput(
            "a search result carries no `filenames` list of strings. Sync frames what the "
            "patch agent reads before the model sees it, and a result it cannot find the "
            "matches in is one it cannot frame"
        )
    content = response.get("content")
    if content is not None and not isinstance(content, str):
        raise UnfenceableToolOutput(
            "a search result's `content` is not text. Sync frames what the patch agent reads "
            "before the model sees it, and a result it cannot read is one it cannot frame"
        )

    updated: dict[str, Any] = {}
    if content:
        updated["content"] = fence(REPOSITORY, content)
    if filenames:
        # Markers as entries of their own, because a path is the one kind of untrusted string
        # the agent hands straight back to a tool. Wrapping the first and last path in place
        # would corrupt two real paths; two synthetic entries corrupt none.
        updated["filenames"] = fenced_block(REPOSITORY, filenames)
    return {**response, **updated} if updated else None


def _framed_shell(response: dict[str, Any]) -> Any | None:
    """`npx tsc` and `git status`, rendered out of the customer's files.

    Filed as tool output rather than repository text, on the distinction the preamble already
    draws: this is a tool's report *over* the repository, and `build_patch_prompt` files the
    same bytes the same way when they come back as `diagnostics`.
    """
    stdout, stderr = response.get("stdout"), response.get("stderr")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        raise UnfenceableToolOutput(
            "a shell result carries no `stdout` and `stderr` strings. Sync frames what the "
            "patch agent reads before the model sees it, and a result it cannot read is one "
            "it cannot frame"
        )

    updated: dict[str, Any] = {}
    if stdout:
        updated["stdout"] = fence(TOOL_OUTPUT, stdout)
    if stderr:
        updated["stderr"] = fence(TOOL_OUTPUT, stderr)
    return {**response, **updated} if updated else None


def framed(tool_name: str, tool_input: dict[str, Any], tool_response: Any) -> Any | None:
    """`tool_response` with its untrusted spans marked, or `None` to leave it as it is.

    `None` means there was nothing to frame -- a tool that reports on Sync's own writes, a
    search with no matches, a command that said nothing. It never means a shape went
    unrecognised; that raises.
    """
    if tool_name not in FENCED_TOOLS:
        return None
    if not isinstance(tool_response, dict):
        raise UnfenceableToolOutput(
            f"a {tool_name} result arrived as {type(tool_response).__name__} rather than a "
            f"structured result. Sync frames what the patch agent reads before the model sees "
            f"it, and a result it cannot take apart is one it cannot frame"
        )
    if tool_name == "Read":
        return _framed_read(tool_input, tool_response)
    if tool_name == "Bash":
        return _framed_shell(tool_response)
    return _framed_search(tool_response)


def _withheld(tool_name: str, tool_input: dict[str, Any]) -> Any:
    """An empty result of the shape the refused tool's own schema declares.

    Refusing without replacing would leave the bytes to reach the model on the strength of a
    `continue` the CLI honours; replacing without refusing would let the run carry on against
    a repository that has already tried once. Both, so neither is load-bearing alone.
    """
    if tool_name == "Read":
        return _withheld_read(tool_input, _REFUSED)
    if tool_name == "Bash":
        return {"stdout": _REFUSED, "stderr": "", "interrupted": False}
    if tool_name == "Grep":
        return {"mode": "content", "numFiles": 0, "filenames": [], "content": _REFUSED,
                "numLines": 1}
    return {"durationMs": 0, "numFiles": 0, "filenames": [], "truncated": False}


def _subject(tool_name: str, tool_input: dict[str, Any]) -> str:
    """What was read, for the operator. The content is the repository and is not logged."""
    if tool_name == "Bash":
        return f"command={tool_input.get('command')!r}"
    return f"input={ {key: tool_input.get(key) for key in ('file_path', 'pattern', 'path')} !r}"


def hooks(identity: str, refusals: list[str]) -> dict[str, list[Callable]]:
    """The fence, bound to the run it is fencing.

    `refusals` is the runner's list and is how a refusal leaves the hook. A hook cannot
    abandon a run: raising inside one is answered to the CLI rather than to `propose`. So the
    reason is recorded here and `sync.runner.claude_sdk.ClaudeSdkRunner` raises on it after
    the query ends, which is what puts it in `abandon_reason` where this project keeps its
    interesting failures.

    **Plain callables keyed by event, not the SDK's `HookMatcher`.** How a tool's output is
    framed as untrusted text is Sync's policy and belongs on this side of the runner seam;
    the runner does the wrapping. See `tool_gate.hooks`.
    """

    async def fence_result(
        hook_input: dict[str, Any], tool_use_id: str | None, context: dict[str, Any],
    ) -> dict[str, Any]:
        tool_name = hook_input["tool_name"]
        tool_input = hook_input["tool_input"]
        subject = _subject(tool_name, tool_input)

        try:
            updated = framed(tool_name, tool_input, hook_input["tool_response"])
        except (UntrustedTextRefused, UnfenceableToolOutput) as exc:
            refusals.append(f"{exc} [{identity}]")
            log.warning(
                "patch agent tool result refused [%s] tool=%s %s: %s",
                identity, tool_name, subject, exc,
            )
            return {
                "continue_": False,
                "stopReason": _REFUSED,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "updatedToolOutput": _withheld(tool_name, tool_input),
                },
            }

        if updated is None:
            log.debug("patch agent tool result [%s] tool=%s %s", identity, tool_name, subject)
            return {}

        log.debug(
            "patch agent tool result framed [%s] tool=%s %s", identity, tool_name, subject,
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": updated,
            }
        }

    return {"PostToolUse": [fence_result]}

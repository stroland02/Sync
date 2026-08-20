"""A predicate on the patch run, where every other gate is a predicate on the artifact.

`tsc`, `shipped_tree`, `dependency_edits` and the customer's own CI all ask what the branch
would contain. An attack that wants to *ship* something has to beat them. The attack ranked
first in `docs/superpowers/specs/2026-07-25-sync-threat-model.md` does not want to ship
anything: the patch agent holds a shell inside a clone that routinely carries `.env`, `.npmrc`
and fixture credentials, the taking happens while the run is in progress, and the diff
afterwards can be a correct migration. `WebSearch` and `WebFetch` are denied and that is real,
but `curl` is a program rather than a tool.

This module is where a run is asked what it is doing. It refuses by default: a tool outside
`PERMITTED_TOOLS`, a shell command that is not one of `PERMITTED_COMMANDS` run on its own, and
any write under `.git/`. Everything it permits, it records; everything it refuses, it records
with the command verbatim.

**Why a PreToolUse hook and not `can_use_tool`.** The SDK is explicit, in
`claude_agent_sdk.types._get_can_use_tool_shadowed_warning`: an `allowed_tools` entry that
allows a whole tool auto-approves it *before* the permission callback is consulted, and "to
gate every tool call, use a PreToolUse hook". `can_use_tool` would also force the prompt into
streaming mode. The hook sees every call under the options this pipeline actually passes.

**Refusing by default is what makes a reduction real here.** `CLAUDE.md` records that leaving a
tool out of `allowed_tools` is not a block -- in headless mode an out-of-list call has no
resolution path and hangs. A denial has to be stated. Enumerating every tool Sync does not want
would rot on the next SDK release, so the set is stated the other way round: what a patch needs,
and a refusal for everything else.

**A refusal names the rule and never quotes the call.** The reason is handed back to the agent,
and the agent composed that command -- possibly out of text a vendor page put in front of it.
`sync.remediate.untrusted` already refuses to echo what it rejected for the same reason. The log
line is operator-facing and carries the command in full, which is the point: detection was zero
before this, and an attempt nobody can read about is an attempt nobody learns from.

What this does not do is contain a shell that gets through. It narrows what the agent may ask
for; it is not an OS boundary, and a command on the permitted list still runs the customer's own
toolchain. The sandbox in the threat model's mitigation 1 is the containment, and this is not it.
"""

from __future__ import annotations

import logging
import os
import shlex
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

# What making a patch takes: read the repository, change it, and tell git which new files belong
# to the change. Nothing here needs to reach the network, start a server, or spawn a subagent.
PERMITTED_TOOLS = frozenset({"Read", "Grep", "Glob", "Edit", "Write", "Bash"})

# The first two tokens of a shell command, which is the whole of what may run. `git add` and
# `npx tsc` are the two the patch prompt asks for by name; `git status` is how an agent confirms
# the staging the prompt made load-bearing. A pair rather than a prefix match, so `git -c
# core.pager=... add` -- one of several ways a git option names a program git then executes --
# is not the allowed `git add`.
PERMITTED_COMMANDS = frozenset({
    ("git", "add"),
    ("git", "status"),
    ("npx", "tsc"),
})

_GIT_DIRECTORY = ".git"

# `shlex` in this configuration is a shell's own view of where one command ends: quotes are
# honoured, so a Next.js route group like `app/(marketing)/route.ts` survives when it is quoted
# the way bash requires, and `;`, `&&`, `|`, `>` and the `(` of a substitution each become a
# token of their own.
_OPERATOR_CHARACTERS = frozenset("();<>|&")

# Neither survives tokenisation as an operator: a backtick keeps its word together, and `$`
# leads a substitution or an expansion whose result is a command line nothing here has seen.
_SUBSTITUTION_CHARACTERS = frozenset("`$")

_TOOL_REFUSED = (
    "this call is refused. Sync's patch agent may call only these tools: "
    + ", ".join(sorted(PERMITTED_TOOLS))
    + ". Make the edit with those."
)
_COMPOUND_REFUSED = (
    "this Bash command is refused. Sync's patch agent may run one simple command at a time: no "
    "second command, no pipe, no redirection, no substitution and no line break. Run the single "
    "command you need on its own."
)
_COMMAND_REFUSED = (
    "this Bash command is refused. The only commands Sync's patch agent may run are "
    + ", ".join("`" + " ".join(pair) + "`" for pair in sorted(PERMITTED_COMMANDS))
    + ". Use Read, Grep and Glob for anything you were going to inspect with a shell."
)
_UNPARSEABLE_REFUSED = (
    "this Bash command is refused: it does not parse as a shell command, most likely an "
    "unbalanced quote. Rewrite it as one simple command."
)
_GIT_DIRECTORY_REFUSED = (
    "this write is refused: nothing under `.git/` is ever part of a patch, and a file placed "
    "there runs or is read by the git commands Sync itself issues afterwards."
)


def _bash_refusal(tool_input: dict[str, Any]) -> str | None:
    command = tool_input.get("command")
    if not isinstance(command, str):
        return _COMPOUND_REFUSED

    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return _UNPARSEABLE_REFUSED

    for token in tokens:
        if set(token) <= _OPERATOR_CHARACTERS or _SUBSTITUTION_CHARACTERS & set(token):
            return _COMPOUND_REFUSED

    # A line break separates two commands exactly as `;` does, and the lexer folds it into the
    # whitespace around it -- so the tokens above read `git add x\ncurl ...` as a permitted
    # `git add` followed by three more arguments.
    if any(character in command for character in "\r\n"):
        return _COMPOUND_REFUSED

    if tuple(tokens[:2]) not in PERMITTED_COMMANDS:
        return _COMMAND_REFUSED
    return None


def _write_refusal(tool_input: dict[str, Any], cwd: str) -> str | None:
    path = tool_input.get("file_path")
    if not isinstance(path, str):
        return None
    absolute = os.path.normpath(path if os.path.isabs(path) else os.path.join(cwd, path))
    if _GIT_DIRECTORY in Path(absolute).parts:
        return _GIT_DIRECTORY_REFUSED
    return None


def refusal(tool_name: str, tool_input: dict[str, Any], cwd: str) -> str | None:
    """Why this call is refused, or `None` to leave the existing rules to decide it."""
    if tool_name not in PERMITTED_TOOLS:
        return _TOOL_REFUSED
    if tool_name == "Bash":
        return _bash_refusal(tool_input)
    if tool_name in ("Write", "Edit"):
        return _write_refusal(tool_input, cwd)
    return None


def _summary(tool_name: str, tool_input: dict[str, Any]) -> str:
    """What the agent asked for, for the operator rather than for the model.

    A shell command is the whole evidence and is recorded whole. For the file tools the path is
    the fact worth having; the content is the patch, and the diff already carries it.
    """
    if tool_name == "Bash":
        return f"command={tool_input.get('command')!r}"
    return f"input={ {key: tool_input.get(key) for key in ('file_path', 'pattern')} !r}"


def hooks(
    identity: str,
    on_event: Callable[[str, str | None, str], None] | None = None,
) -> dict[str, list[Callable]]:
    """The gate, bound to the run it is gating.

    `identity` is `sync.remediate.agent_patch._identity` -- the finding and the repository -- so
    a refusal in the log says which run it belongs to. A trail that cannot be joined back to a
    finding is not evidence.

    `on_event(kind, tool, summary)` is the same trail, live: `"tool"` for a permitted call and
    `"refusal"` for one turned away, with the summary the log line already carries. It does not
    take the identity -- the recorder was constructed knowing its finding -- and `None`, the
    default, records nowhere and leaves the gate exactly as it was.

    Registered against every tool rather than against `Bash`. The shell is where the damage is,
    but a record of only the shell cannot answer what the agent did on a run where it never
    reached for one.

    **Plain callables keyed by event, not the SDK's `HookMatcher`.** What a patch may ask a
    tool to do is Sync's policy and belongs on this side of the runner seam; producing an SDK
    type here would put a model SDK back inside `sync.remediate` for one constructor call.
    `sync.runner.claude_sdk` wraps these, and matching every tool is the wrap's own default.
    """

    async def gate(
        hook_input: dict[str, Any], tool_use_id: str | None, context: dict[str, Any],
    ) -> dict[str, Any]:
        tool_name = hook_input["tool_name"]
        tool_input = hook_input["tool_input"]
        summary = _summary(tool_name, tool_input)

        reason = refusal(tool_name, tool_input, hook_input["cwd"])
        if reason is None:
            log.debug("patch agent tool call [%s] tool=%s %s", identity, tool_name, summary)
            if on_event is not None:
                on_event("tool", tool_name, summary)
            # Silence, not `"allow"`. Answering `"allow"` would auto-approve calls the CLI's own
            # rules would otherwise still weigh, which widens the surface this exists to narrow.
            return {}

        log.warning(
            "patch agent tool call refused [%s] tool=%s %s", identity, tool_name, summary,
        )
        if on_event is not None:
            on_event("refusal", tool_name, summary)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    return {"PreToolUse": [gate]}

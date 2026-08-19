"""The production runner: the Claude Agent SDK, driven against a clone.

Everything here was `AgentRemediator._drive_agent` and moved unchanged. What changed is who
may reach it -- `sync.remediate` no longer imports the SDK, so the pipeline's own tests drive
`StaticRunner` instead of replacing a symbol in a library nobody here owns.

**Hooks arrive as plain callables and are wrapped into `HookMatcher` here.** The gate that
narrows what the agent may ask a tool to do is remediation's policy, and it stays in
`sync.remediate`; making it produce an SDK type would put the SDK back on the other side of
the seam for the sake of one constructor call. Both hooks Sync ships match every tool, which
is why the wrap hard-codes `matcher=None`: a runner that had to route matchers would be
carrying a distinction no caller makes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

from sync.runner.provider import DEFAULT_MODEL, resolve_provider

# The default, and the only model spend in the product: this runner is the patch agent, and no
# other code path here calls a model. `SYNC_MODEL` overrides it so a deployment can point at a
# cheaper tier, or at whatever model its own session is already paying for, without a fork.
#
# Read at call time rather than at import, so a caller that sets the variable after importing
# this module still gets what it asked for -- an import-time read makes the override depend on
# module ordering, which is the kind of failure nobody debugs twice.


def configured_model() -> str:
    """The model this runner will drive.

    Kept as a function because callers and tests import it; `sync.runner.provider` is where the
    decision now lives, so the model and the endpoint cannot be resolved by two different rules.
    """
    return resolve_provider().model

# ClaudeAgentOptions has no raw max_tokens knob -- the SDK manages its own
# multi-turn budget -- so the project's max_tokens=64000 binding does not
# apply here; it governs direct Messages API calls elsewhere in the pipeline.
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
# Not merely omitted from ALLOWED_TOOLS: an unlisted tool still falls through
# to the permission mode instead of being blocked, so network tools have to be
# denied explicitly to guarantee none run.
DISALLOWED_TOOLS = ["WebSearch", "WebFetch"]

# No settings are read from any filesystem. `cwd` is a clone of a customer's repository, and
# `setting_sources` defaults to `None`, which the SDK documents as "all sources are loaded" --
# so a `.claude/settings.json` that repository ships is configuration Sync obeys. A
# `SessionStart` hook in it is a shell command that runs before the first tool call, which is
# where `tool_gate` sits, in a process holding every credential the control plane has (B97:
# `options.env` merges onto `os.environ` rather than replacing it). Measured against the real
# SDK on 2026-08-16: a settings file written into the working directory executed and its marker
# came back on a `hook_response`; with this set to `[]` the same experiment reported no fire.
#
# `[]` rather than `["user"]`, because the operator's own global settings are no more part of a
# patch run than the customer's are -- the same experiment showed this host's SessionStart
# hooks firing inside the patch agent, and its tool roster carrying the operator's whole
# installed set rather than the six names above.
#
# Sync's own hooks are unaffected: they are passed programmatically through `hooks=`, which is
# not a filesystem source.
SETTING_SOURCES: list[str] = []
# Every entry above allows a whole tool, which auto-approves it before any permission callback
# is consulted -- so what the agent may do inside those tools is decided by the hooks the
# caller supplies, which the SDK reaches through PreToolUse and PostToolUse events that
# nothing shadows.

# What a caller hands over: the run's identity, and the list a hook appends a refusal to.
# The list is the runner's, because only the runner knows when the run is over and the
# refusals are worth reading.
HookFactory = Callable[[str, list[str]], dict[str, list[Any]]]


class ClaudeSdkRunner:
    """Drives the Claude Agent SDK until it stops, and raises unless it stopped cleanly."""

    def __init__(self, hooks_for: HookFactory) -> None:
        # Required, and deliberately not defaulted to "no hooks". The gate is the only thing
        # between an agent holding `Bash` and `curl` in a clone that routinely carries `.env`
        # -- the threat model's first-ranked item. A default would make an ungated production
        # runner one forgotten argument away, and nothing downstream could tell the difference:
        # an ungated run reports as an ordinary success.
        self._hooks_for = hooks_for

    def run(self, prompt: str, repo_path: Path, identity: str) -> None:
        asyncio.run(self._drive(prompt, repo_path, identity))

    async def _drive(self, prompt: str, repo_path: Path, identity: str) -> None:
        # A hook cannot abandon a run -- an exception raised inside one is answered to the
        # CLI, not to this frame -- so the caller's hooks record their refusals here instead.
        refusals: list[str] = []
        provider = resolve_provider()
        options = ClaudeAgentOptions(
            cwd=repo_path,
            model=provider.model,
            thinking={"type": "adaptive"},
            effort="xhigh",
            allowed_tools=ALLOWED_TOOLS,
            disallowed_tools=DISALLOWED_TOOLS,
            setting_sources=SETTING_SOURCES,
            # A self-hosted endpoint reaches the SDK's CLI subprocess through the environment
            # rather than through an option field, because the SDK has none: `sandbox.py`
            # records `options.env` as the channel. An empty mapping when nothing is
            # configured, so a default deployment passes nothing rather than an empty base URL.
            env=({"ANTHROPIC_BASE_URL": provider.base_url} if provider.base_url else {}),
            hooks={
                event: [HookMatcher(matcher=None, hooks=callbacks)]
                for event, callbacks in self._hooks_for(identity, refusals).items()
            },
        )
        result: ResultMessage | None = None
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result = message
        except Exception as exc:
            # A refusal answers `continue_: False`, which stops the turn -- and the CLI then
            # exits non-zero, so this raises rather than completing. Reading `refusals` only
            # after the loop therefore discarded the reason in exactly the case the hook exists
            # to report, and left the SDK's own text in `abandon_reason` instead: measured on a
            # full-depth rehearsal on 2026-08-16, three attempts abandoned with
            # `Claude Code returned an error result: success`, which names neither the run nor
            # what was refused.
            if refusals:
                raise RuntimeError(refusals[0]) from exc
            raise

        # Ahead of the two checks below, which describe how the run ended rather than why it
        # was stopped. A refusal reports as an ordinary completion with an empty diff, and
        # `route_after_patch` reads that as a remediator that found nothing to change.
        if refusals:
            raise RuntimeError(refusals[0])

        # A run that failed or never reported must not be mistaken for one that
        # completed and correctly found nothing to change: both would otherwise
        # leave behind the same empty git diff.
        if result is None:
            raise RuntimeError(f"agent run produced no result message [{identity}]")
        if result.is_error:
            raise RuntimeError(f"agent run failed ({result.subtype}) [{identity}]: {result.errors}")


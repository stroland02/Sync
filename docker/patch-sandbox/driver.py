"""The agent turn, run from inside the sandbox container. B97 Decision 1.

This is not `sync.runner.claude_sdk.ClaudeSdkRunner` imported -- it is that module's own
`_drive` logic, copied rather than imported, because importing it would import `sync.runner`
and everything `sync.runner.__init__` re-exports alongside it. The container gets exactly
three files from this repository (`tool_gate.py`, `tool_output.py`, `untrusted.py`, copied
beside this one at image-build or attempt-start time) plus this driver -- nothing that touches
`sync.core`, `sync.graph`, or a database credential ever reaches the sandboxed filesystem.
`tests/test_docker_driver.py` on the host side pins this file and the copied three against
their originals so the two cannot drift silently.

Protocol with the host, deliberately a filesystem rather than stdin/stdout: `ClaudeAgentOptions`
and the SDK's own subprocess management already own stdio, so a second use of the same channel
for job/result data would race it. `/workspace/.sync-job/job.json` in, `/workspace/.sync-job/
result.json` out, both plain JSON, both host-readable via `docker cp` after this process exits --
`sync.remediate.sandbox.copy_between_containers`'s own mechanism, not a new one.

The credential is never here. `ANTHROPIC_BASE_URL` (set by the host as this container's own
environment, not read from a file this driver opens) points the bundled `claude` CLI at the
forward proxy on the isolated network; the proxy holds the real key and this process never sees
it, the same way `build_container_env` already starts every sandboxed process from an empty
environment rather than the operator's own.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query

import tool_gate
import tool_output

JOB_DIR = Path("/workspace/.sync-job")
JOB_PATH = JOB_DIR / "job.json"
RESULT_PATH = JOB_DIR / "result.json"

MODEL = "claude-opus-5"
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
DISALLOWED_TOOLS = ["WebSearch", "WebFetch"]
SETTING_SOURCES: list[str] = []


def patch_hooks(identity: str, refusals: list[str]) -> dict[str, list[Any]]:
    """`sync.remediate.agent_patch.patch_hooks`, copied for the reason this file's own
    docstring gives -- the two are pinned together by `tests/test_docker_driver.py`.
    """
    return {**tool_gate.hooks(identity), **tool_output.hooks(identity, refusals)}


async def drive(prompt: str, repo_path: Path, identity: str) -> None:
    """`ClaudeSdkRunner._drive`, copied. See this module's own docstring for why."""
    refusals: list[str] = []
    options = ClaudeAgentOptions(
        cwd=repo_path,
        model=MODEL,
        thinking={"type": "adaptive"},
        effort="xhigh",
        allowed_tools=ALLOWED_TOOLS,
        disallowed_tools=DISALLOWED_TOOLS,
        setting_sources=SETTING_SOURCES,
        hooks={
            event: [HookMatcher(matcher=None, hooks=callbacks)]
            for event, callbacks in patch_hooks(identity, refusals).items()
        },
    )
    result: ResultMessage | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message
    except Exception as exc:
        if refusals:
            raise RuntimeError(refusals[0]) from exc
        raise

    if refusals:
        raise RuntimeError(refusals[0])
    if result is None:
        raise RuntimeError(f"agent run produced no result message [{identity}]")
    if result.is_error:
        raise RuntimeError(f"agent run failed ({result.subtype}) [{identity}]: {result.errors}")


def main() -> int:
    job = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    prompt = job["prompt"]
    identity = job["identity"]
    repo_path = Path(job["repo_path"])

    try:
        asyncio.run(drive(prompt, repo_path, identity))
    except Exception as exc:
        RESULT_PATH.write_text(
            json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8"
        )
        return 1

    RESULT_PATH.write_text(json.dumps({"ok": True, "error": None}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

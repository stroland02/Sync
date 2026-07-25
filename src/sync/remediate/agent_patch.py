"""Patch generation delegated to the Claude Agent SDK.

The Agent SDK runs against a throwaway clone, never a customer's working tree.
Nothing it produces is trusted: the graph typechecks the result and then waits
for the repository's own CI before anything becomes a pull request.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange

MODEL = "claude-opus-5"

# ClaudeAgentOptions has no raw max_tokens knob -- the SDK manages its own
# multi-turn budget -- so the project's max_tokens=64000 binding does not
# apply here; it governs direct Messages API calls elsewhere in the pipeline.
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
# Not merely omitted from ALLOWED_TOOLS: an unlisted tool still falls through
# to the permission mode instead of being blocked, so network tools have to be
# denied explicitly to guarantee none run.
DISALLOWED_TOOLS = ["WebSearch", "WebFetch"]

_SCOPE_RULES = """
Rules:
- Change only what this specific API change requires. Do not refactor surrounding code.
- Do not add error handling, abstractions, or helpers that were not there before.
- Do not reformat lines you did not otherwise need to touch.
- If the removed value is still needed, derive it from what the API does return; if it
  cannot be derived, remove the usage rather than inventing a placeholder.
- Run `npx tsc --noEmit` yourself and keep editing until it is clean.
""".strip()


def build_patch_prompt(
    finding: Finding,
    change: VendorChange,
    site: CallSite,
    diagnostics: str = "",
) -> str:
    """Everything the agent needs, and nothing it does not."""
    field = change.raw.get("field") or change.path_ptr.rsplit("/", 1)[-1]

    sections = [
        "A third-party API changed and this repository's code no longer matches it.",
        "",
        f"Vendor: {change.vendor_id}",
        f"Change: {change.kind}",
        f"Operation: {change.operation_id}  ({change.from_version} -> {change.to_version})",
        f"Affected field: {field}",
        "",
        f"Call site: {site.path}, line {site.line}",
        f"SDK call: {site.symbol}",
        f"Arguments passed: {', '.join(site.args_keys) or 'none'}",
        f"Response fields read: {', '.join(site.response_fields_read) or 'none'}",
        "",
        f"Why this matters: {finding.rationale}",
        "",
        _SCOPE_RULES,
    ]

    if diagnostics:
        sections += [
            "",
            "A previous attempt failed typechecking with:",
            "",
            diagnostics,
            "",
            "Fix the cause rather than suppressing the error.",
        ]

    return "\n".join(sections)


def _git_diff(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "diff"], cwd=repo_path, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return result.stdout


class AgentRemediator:
    """Remediator backed by the Claude Agent SDK."""

    strategy = "agent"

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return finding.severity in ("breaking", "deprecation")

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        prompt = build_patch_prompt(finding, change, site, diagnostics)
        repo_path = Path(repo.local_path)

        self._run_agent(prompt, repo_path)

        return Patch(
            diff=_git_diff(repo_path),
            strategy=self.strategy,
            rationale=finding.rationale,
        )

    def _run_agent(self, prompt: str, repo_path: Path) -> None:
        """Isolated so tests can substitute it without touching `propose`."""
        asyncio.run(self._drive_agent(prompt, repo_path))

    async def _drive_agent(self, prompt: str, repo_path: Path) -> None:
        options = ClaudeAgentOptions(
            cwd=repo_path,
            model=MODEL,
            thinking={"type": "adaptive"},
            effort="xhigh",
            allowed_tools=ALLOWED_TOOLS,
            disallowed_tools=DISALLOWED_TOOLS,
        )
        result: ResultMessage | None = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message

        # A run that failed or never reported must not be mistaken for one that
        # completed and correctly found nothing to change: both would otherwise
        # leave behind the same empty git diff.
        if result is None:
            raise RuntimeError("agent run produced no result message")
        if result.is_error:
            raise RuntimeError(f"agent run failed ({result.subtype}): {result.errors}")

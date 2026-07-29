"""Patch generation delegated to the Claude Agent SDK.

The Agent SDK runs against a throwaway clone, never a customer's working tree.
Nothing it produces is trusted: the graph typechecks the result and then waits
for the repository's own CI before anything becomes a pull request.

**The completion criterion is the edit, not a clean typecheck.** The prompt names the edit
the call site requires and tells the agent it is finished when that edit is made. It used to
say "run `npx tsc --noEmit` and keep editing until it is clean", and the M0 acceptance run
died on exactly that. Stripe removed `receipt_email` from the *specification*; the installed
SDK was stripe 22.4.0-beta.1, whose TypeScript declarations still carried the property, so
the code typechecked identically before and after the correct fix. The agent ran the command
it was told to run, found the tree as clean as it can get, and correctly concluded there was
nothing to do -- three times, for an empty diff each time, and ten and a half minutes of
model time for nothing.

That failure is not one field's bad luck. Anything request-side, and anything the SDK's
generated types lag, is invisible to the typechecker until the vendor ships a regenerated
SDK -- which is the moment the customer stops needing us. The typecheck keeps the role it
can actually perform: catching a patch that breaks compilation. It was never capable of
confirming that a spec-only change had been applied.

The required edit is derived from what the graph resolved -- the affected field, and whether
this call site passes it as an argument or reads it from the response -- and never from the
change kind. `VendorChange.kind` is one of over five hundred oasdiff rule identifiers, and a
second classifier here would rot on every oasdiff release while `sync.route.matrix` already
keys tier decisions on the catalogue's own `direction`/`action` axes. When the field resolves
to neither position, the prompt says so rather than asserting a location the index never
recorded.

**A new file is part of the patch only if the agent stages it.** Some correct fixes need a
module that is not there yet, and nothing downstream can tell one from the build output,
logs and stray installs the agent's `Bash` calls leave in the same clone. Classifying by
name or extension would be wrong on somebody's repository and wrong silently, so the
question is not answered here at all: it is put to the only party that knows, and `git add`
is how the answer is recorded. Everything the repository's own ignore rules cover stays
untracked and unremarked, which is what `push_branch` and `sync.index.shipped_tree` both
already exclude. An untracked path those rules do not cover is the case nobody answered,
and it refuses the patch rather than being guessed at -- the diff cannot arbitrate, since
an agent that edits a tracked call site and leaves the new module unstaged produces one
that looks complete and compiles to `TS2307: Cannot find module`.

Section order is load-bearing. Everything stable sits ahead of the diagnostics block, the
only part that changes between retries, so the prefix stays byte-identical and cacheable
across attempts; anything appended after diagnostics is invalidated every round. See the
prompt-cache boundary in `docs/superpowers/specs/2026-07-25-sync-latency-architecture.md`.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.signals.oasdiff import changed_field

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
- If the edit genuinely needs a file that does not exist yet, create it and then stage it
  with `git add <path>`. Only what git already tracks and what you have staged is
  typechecked and pushed; a new file left unstaged is in neither, and the branch would
  carry an import of a module that is not there. Stage the files you added for this change
  by path and nothing else -- never `git add -A` or `git add .`, which would sweep in
  whatever your commands happened to leave in this clone. Staging a file is you asserting
  the patch needs it, and it is the only thing that distinguishes a file the fix requires
  from a build artifact or a log.
- Run `npx tsc --noEmit` once you have made the edit -- after staging anything you added,
  so that it measures the same tree the branch will carry -- and confirm you introduced no
  new errors. That is the whole of what it establishes. It cannot tell you whether the edit
  was needed: the installed SDK's type declarations are generated from an older version
  of this specification and still describe the old shape, so a change like this one
  typechecks identically before and after the correct fix. A clean run is never a reason
  to leave the call site as it is.
""".strip()


def _required_edit(field: str | None, site: CallSite) -> str:
    """Where at this call site the edit has to land.

    Positional, not directional. What happened to the field is already stated two lines
    above as the oasdiff rule id; what the agent lacks is which expression to change.
    """
    if field is None:
        return (
            "the vendor change does not name a field, so read the call site and the change"
            " above and determine the affected expression yourself"
        )
    if field in site.args_keys:
        return (
            f"`{field}` is passed as an argument at this call site, so that argument is what"
            f" your edit must change to agree with the change above"
        )
    if field in site.response_fields_read:
        return (
            f"`{field}` is read from this call's response at this call site, so that read is"
            f" what your edit must change to agree with the change above"
        )
    return (
        f"the change affects `{field}`, which the index did not record among this call site's"
        f" arguments or the response fields it reads -- locate it in the surrounding code"
        f" rather than assuming either position"
    )


def build_patch_prompt(
    finding: Finding,
    change: VendorChange,
    site: CallSite,
    diagnostics: str = "",
) -> str:
    """Everything the agent needs, and nothing it does not."""
    field = changed_field(change)
    field_line = field if field is not None else "could not be determined from the vendor change"

    sections = [
        "A third-party API changed and this repository's code no longer matches it.",
        "",
        f"Vendor: {change.vendor_id}",
        f"Change: {change.kind}",
        f"Operation: {change.operation_id}  ({change.from_version} -> {change.to_version})",
        f"Affected field: {field_line}",
        "",
        f"Call site: {site.path}, line {site.line}",
        f"SDK call: {site.symbol}",
        f"Arguments passed: {', '.join(site.args_keys) or 'none'}",
        f"Response fields read: {', '.join(site.response_fields_read) or 'none'}",
        "",
        f"Required edit: {_required_edit(field, site)}.",
        "Done when: that edit is made and the call site agrees with the change above.",
        "",
        f"Why this matters: {finding.rationale}",
        "",
        _SCOPE_RULES,
    ]

    if diagnostics:
        # The graph feeds a CI rejection and a failed agent run through this
        # same argument, so the heading cannot name a stage: only the caller
        # knows which one produced the text.
        sections += [
            "",
            "A previous attempt failed. What went wrong:",
            "",
            diagnostics,
            "",
            "Fix the cause rather than suppressing the error.",
        ]

    return "\n".join(sections)


def _identity(finding: Finding, repo: RepoRef) -> str:
    """A `--limit 0` run raises through the same two lines for every finding it
    processes, and the operator aggregating those failures has the message and
    no stack trace. `Finding.id` is None until the store assigns one, which
    would otherwise read as "finding=None" -- a bug in Sync rather than a
    finding that was never persisted.
    """
    return f"finding={finding.id or 'unsaved'} repo={repo.repo_id}"


def _git_diff(repo_path: Path) -> str:
    """Everything the working tree and the index hold over HEAD.

    Against HEAD rather than the bare `git diff`, which compares the working tree
    to the index and so cannot see a file the agent staged. A fix that needs a
    module which does not exist yet is exactly such a file, and read the narrow
    way its patch is either missing that module or -- where the new module is the
    whole of the fix -- empty, which `route_after_patch` treats as a remediator
    that changed nothing.

    This does not widen what a branch can carry. An untracked path is invisible
    to `git diff HEAD` for the same reason it is invisible to `push_branch`'s
    `git add -u`: neither reads the working tree for paths the index does not
    know. Staging remains a deliberate act, and it is still the only way in.
    """
    result = subprocess.run(
        ["git", "diff", "HEAD"], cwd=repo_path, capture_output=True, text=True,
        encoding="utf-8", check=True,
    )
    return result.stdout


def _unstaged_additions(repo_path: Path) -> list[str]:
    """Files the agent created and did not stage, ignored ones excluded.

    `--exclude-standard` because a path the repository's own `.gitignore` covers
    is a byproduct by the customer's declaration, and naming it would send the
    next attempt after something no patch was ever going to carry.
    """
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo_path,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout.split()


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

        identity = _identity(finding, repo)
        self._run_agent(prompt, repo_path, identity)

        # Asked of the tree rather than of the diff. An unstaged addition is in
        # neither the tree `static_verify` compiles nor the commit `push_branch`
        # builds, and that holds whether or not the agent also edited a tracked
        # file -- where it did, the edit fills the diff and the missing module
        # reaches the gate as `TS2307: Cannot find module`, which names an import
        # rather than the `git add` that was never run. Conditioning this on an
        # empty diff sees only the half of the case where the new file is the
        # whole patch. The graph hands the message to the next attempt as
        # feedback, so this is also the run's chance to correct itself.
        unstaged = _unstaged_additions(repo_path)
        if unstaged:
            raise RuntimeError(
                f"the agent created {', '.join(unstaged)} and staged none of them; a new file "
                f"has to be staged with `git add <path>` to be typechecked or pushed "
                f"[{identity}]"
            )

        diff = _git_diff(repo_path)

        return Patch(
            diff=diff,
            strategy=self.strategy,
            rationale=finding.rationale,
        )

    def _run_agent(self, prompt: str, repo_path: Path, identity: str) -> None:
        """Isolated so tests can substitute it without touching `propose`."""
        asyncio.run(self._drive_agent(prompt, repo_path, identity))

    async def _drive_agent(self, prompt: str, repo_path: Path, identity: str) -> None:
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
            raise RuntimeError(f"agent run produced no result message [{identity}]")
        if result.is_error:
            raise RuntimeError(f"agent run failed ({result.subtype}) [{identity}]: {result.errors}")

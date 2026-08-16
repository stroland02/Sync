"""Tier 0: a remediator that produces a patch without a model call.

The routing matrix names four tiers and nothing sat below the agent until now. This fills the
cheapest one. The vendor names the replacement, `ast-grep` performs the edit against the AST,
and `difflib` renders the result -- so the whole path from "a model was retired" to "here is
the patch" costs nothing per finding.

`strategy="codemod"` is not decoration. `migration_outcome` splits merge rate by strategy and
tier so the claim that mechanical changes land more often than agent-written ones can be
checked rather than asserted.

The remediator declines rather than guesses. No replacement, no id to replace, a change that
is not a deprecation, an unreadable file, an unsupported language -- all of them return work
to the agent or produce nothing, because a confident wrong patch costs more than a missing one.

The first two are decided by `can_handle` rather than inside `propose`, and that placement is
the point. A codemod that accepts a change and then finds nothing to build has already spent
the attempt: the cascade returns its empty `Patch` and never reaches the next tier. Declining
at the predicate keeps the fall-through inside the same attempt, and it is the decline
`TieredRemediator._eligible` can measure -- a `CannotPatch` raised under a tier-0 route leaves
the narrowed candidate list non-empty and strands the finding at `NoTierApplies`.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.route import apply_rules, model_literal_swap

_DEPRECATION_PREFIX = "deprecation/model-"

# Extension to ast-grep language. A file type absent here is declined rather than guessed: the
# parser choice decides what counts as a string literal, and the wrong grammar silently matches
# nothing, which would read as "already migrated".
_LANGUAGES = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def _language_for(path: str) -> str | None:
    return _LANGUAGES.get(Path(path).suffix.lower())


# The keys `model_literal_swap` requires, in the form it requires them: a non-empty string.
# `can_handle` tests exactly this set and nothing narrower. A record the predicate claims and
# the builder refuses yields no rule, and `apply_rules` with no rules returns the source
# unchanged -- which is the same answer as an already-migrated file by the time `make_patch`
# reads it, so the run reports no change rather than reporting that no rule could be built.
_REQUIRED = ("model_id", "replacement")


def _named(change: VendorChange, key: str) -> str | None:
    value = change.raw.get(key)
    return value if isinstance(value, str) and value else None


class LiteralSwapRemediator:
    """Rewrites a retired operation literal to the replacement the vendor named."""

    strategy = "codemod"

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return change.kind.startswith(_DEPRECATION_PREFIX) and all(
            _named(change, key) is not None for key in _REQUIRED
        )

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        """A unified diff for one file, or an empty diff when there is nothing to do.

        Empty is a real answer. The remediation graph already routes an empty diff to
        `abandon`, which is correct here -- a patch that changes nothing would push a branch
        with no commit and open an empty pull request.
        """
        language = _language_for(site.path)
        target = Path(repo.local_path) / site.path

        if language is None:
            return self._patch("", change, site)

        try:
            # Bytes, decoded here rather than `read_text`, so no newline translation
            # happens in either direction: `read_text` folds CRLF to LF and `write_text`
            # expands LF to `os.linesep`, so on Windows a round trip rewrites every line.
            original = target.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            # The index can outlive the file: a deleted or moved path is a stale binding, and a
            # file that is not valid UTF-8 is not source this remediator can reason about.
            return self._patch("", change, site)

        rules = model_literal_swap(change, language=language)
        updated = apply_rules(rules, original, language)

        if updated == original:
            return self._patch("", change, site)

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{site.path}",
                tofile=f"b/{site.path}",
            )
        )
        # The edit has to land in the clone, not only in the rendered diff. Nothing
        # downstream applies `patch.diff`: `static_verify` typechecks the working tree and
        # `push_branch` stages it with `git add -u`, so a diff alone pushes an empty commit.
        target.write_bytes(updated.encode("utf-8"))
        return self._patch(diff, change, site)

    def _patch(self, diff: str, change: VendorChange, site: CallSite) -> Patch:
        return Patch(diff=diff, strategy=self.strategy, rationale=self._rationale(change, site))

    def _rationale(self, change: VendorChange, site: CallSite) -> str:
        """What a reviewer reads before approving a machine-written change.

        The vendor's own word and date, not "updated model" -- this is where a pull request
        opened by a machine either earns trust or spends it.
        """
        state = change.raw.get("state", "deprecated")
        old = change.raw.get("model_id", change.operation_id)
        new = _named(change, "replacement")
        retirement = change.raw.get("retirement_date")

        when = f" Retirement date: {retirement}." if retirement else ""
        return (
            f"{change.vendor_id} has {state} `{old}`, used at {site.path}:{site.line}."
            f"{when} The vendor names `{new}` as the replacement."
            " Requests to a retired model fail, and the SDK accepts any string, so a type"
            " checker cannot catch this."
        )

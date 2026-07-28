"""Tier 0 for parameters: removals and renames produced with no model call.

Two remedies, because vendors give two kinds of guidance. Anthropic tells you to stop passing
`temperature` and offers nothing in its place; where a successor exists the fix is a rename.
They share everything except the edit itself, so the difference is one method.

Both are scoped by the model at the call site rather than by the parameter alone. A
`temperature` nested elsewhere in the file is not this call's argument, and a diff that touched
it would claim something the finding never said.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.route.templates import omit_parameter, rename_parameter

_PARAMETER_KIND = "deprecation/parameter"

# A file type absent here is declined rather than parsed with a guessed grammar: the wrong
# grammar finds nothing, and nothing reads as "already clean".
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

_WHY_THE_COMPILER_IS_SILENT = (
    "Deprecated parameters stay in the SDK request types, so this type-checks today and fails "
    "at the vendor instead. Whether this model falls inside the stated scope is not resolved "
    "automatically."
)


class _ParameterRemediator:
    """Shared plumbing: read the file, apply one edit, render a diff."""

    strategy = "codemod"
    remedy = ""

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return change.kind == _PARAMETER_KIND and change.raw.get("remedy") == self.remedy

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        """A unified diff for one file, or an empty diff when there is nothing to do.

        Empty is a real answer -- the graph routes it to `abandon` -- and it covers the honest
        cases: the file is already correct, the call site names a different model, the path no
        longer exists because the index outlived the tree, or the edit was declined as unsafe.
        """
        language = _LANGUAGES.get(Path(site.path).suffix.lower())
        target = Path(repo.local_path) / site.path

        if language is None:
            return self._patch("", change, site)

        try:
            original = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return self._patch("", change, site)

        updated = self._edit(original, change, site, language)
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
        return self._patch(diff, change, site)

    def _edit(self, source: str, change: VendorChange, site: CallSite, language: str) -> str:
        raise NotImplementedError

    def _patch(self, diff: str, change: VendorChange, site: CallSite) -> Patch:
        return Patch(diff=diff, strategy=self.strategy, rationale=self._rationale(change, site))

    def _preamble(self, change: VendorChange, site: CallSite) -> str:
        parameter = _parameter_of(change)
        behavior = str(change.raw.get("behavior", "")).rstrip(".")
        scope = change.raw.get("applies_from")
        when = f" from {scope}" if scope else ""
        return (
            f"`{parameter}` is passed at {site.path}:{site.line} on model "
            f"`{site.operation_id}`, and {change.vendor_id} deprecated it{when}: {behavior}. "
        )

    def _rationale(self, change: VendorChange, site: CallSite) -> str:
        raise NotImplementedError


def _parameter_of(change: VendorChange) -> str:
    return str(change.raw.get("parameter") or change.operation_id)


class ParameterOmitRemediator(_ParameterRemediator):
    """Removes a request parameter the vendor no longer honours and did not replace."""

    remedy = "omit"

    def _edit(self, source: str, change: VendorChange, site: CallSite, language: str) -> str:
        return omit_parameter(
            source, _parameter_of(change), language=language,
            within_object_naming=site.operation_id,
        )

    def _rationale(self, change: VendorChange, site: CallSite) -> str:
        # A deletion is harder to approve than a substitution, because nothing replaces what is
        # gone. The vendor's own wording is what makes it approvable.
        return (
            self._preamble(change, site)
            + "The vendor's guidance is to omit it rather than replace it, so it is removed "
            "here. " + _WHY_THE_COMPILER_IS_SILENT
        )


class ParameterRenameRemediator(_ParameterRemediator):
    """Renames a request parameter to the successor the vendor named."""

    remedy = "rename"

    def _edit(self, source: str, change: VendorChange, site: CallSite, language: str) -> str:
        replacement = change.raw.get("replacement")
        if not isinstance(replacement, str) or not replacement:
            return source

        return rename_parameter(
            source, _parameter_of(change), replacement, language=language,
            within_object_naming=site.operation_id,
        )

    def _rationale(self, change: VendorChange, site: CallSite) -> str:
        replacement = change.raw.get("replacement")
        return (
            self._preamble(change, site)
            + f"The vendor names `{replacement}` as its replacement, so the key is renamed and "
            "the value left as it was. " + _WHY_THE_COMPILER_IS_SILENT
        )

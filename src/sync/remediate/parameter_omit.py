"""Tier 0 for parameters: a removal produced with no model call.

`LiteralSwapRemediator` covers the swap case, where a vendor named a successor. This covers the
omit case, where the guidance is to stop passing the argument at all -- which is what
Anthropic's `temperature`, `top_p` and `top_k` deprecation asks for.

The edit needs two facts rather than one. Removal is scoped to the object that also names the
model, so the remediator reads `site.operation_id` instead of guessing which object to touch. A
`temperature` nested elsewhere in the file is not this call's argument, and a diff that removed
it would claim something the finding never said.

`rename` is declined. Renaming an object key is a different edit from removing one, and a
remediator that half-implements a remedy is worse than one that hands it to something which can
do it properly.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.route.templates import omit_parameter

_PARAMETER_KIND = "deprecation/parameter"

# Shared with `literal_swap`: a file type absent here is declined rather than parsed with a
# guessed grammar, because the wrong grammar finds nothing and that reads as "already clean".
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


class ParameterOmitRemediator:
    """Removes a request parameter the vendor no longer honours."""

    strategy = "codemod"

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        return change.kind == _PARAMETER_KIND and change.raw.get("remedy") == "omit"

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        """A unified diff for one file, or an empty diff when there is nothing to remove.

        Empty is a real answer -- the graph routes it to `abandon` -- and it covers the honest
        cases: the file is already clean, the call site names a different model, or the path no
        longer exists because the index outlived the tree.
        """
        parameter = change.raw.get("parameter") or change.operation_id
        language = _LANGUAGES.get(Path(site.path).suffix.lower())
        target = Path(repo.local_path) / site.path

        if language is None:
            return self._patch("", change, site)

        try:
            original = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return self._patch("", change, site)

        updated = omit_parameter(
            original, parameter, language=language, within_object_naming=site.operation_id
        )
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

    def _patch(self, diff: str, change: VendorChange, site: CallSite) -> Patch:
        return Patch(diff=diff, strategy=self.strategy, rationale=self._rationale(change, site))

    def _rationale(self, change: VendorChange, site: CallSite) -> str:
        """What a reviewer reads before approving a removal.

        A deletion is harder to approve than a substitution -- nothing replaces what is gone --
        so this states the vendor's own wording, the model scope, and why the compiler was
        silent, and it says plainly that the scope was not evaluated here.
        """
        parameter = change.raw.get("parameter") or change.operation_id
        behavior = str(change.raw.get("behavior", "")).rstrip(".")
        scope = change.raw.get("applies_from")
        when = f" from {scope}" if scope else ""

        return (
            f"`{parameter}` is passed at {site.path}:{site.line} on model "
            f"`{site.operation_id}`, and {change.vendor_id} deprecated it{when}: {behavior}. "
            "The vendor's guidance is to omit it rather than replace it, so it is removed here. "
            "Deprecated parameters stay in the SDK request types, so this type-checks today and "
            "fails at the vendor instead. Whether this model falls inside the stated scope is "
            "not resolved automatically."
        )

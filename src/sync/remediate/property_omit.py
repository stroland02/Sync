"""Tier 0 for the change class the acceptance run actually hit.

`literal_swap` covers a retired model id. This covers the other mechanical shape, and the
commoner one: a vendor removed a request property, and a call site passes it. Deleting one
named key from one object literal needs no reasoning, and the M0 acceptance run spent roughly
ten minutes of `xhigh` model time doing exactly that to two lines.

The location is the whole difficulty. `stripe-connect-furever-demo` passes `receipt_email` at
two `stripe.paymentIntents.create` calls in one file, and a finding names one of them. So the
edit is scoped by the call site's own line and column rather than by anything in the source
that could match twice -- `sync.route.templates.omit_argument_at` carries that scoping, over
the same deletion span `omit_parameter` uses. Two entry points share one implementation
because the scoping differs and the deletion does not; the dangling-comma fix lives in one
place, which is the point.

**An empty diff means "this remediator declines", and `TieredRemediator` reads it as
ownership rather than a fall-through.** That is the tension worth naming. Its docstring is
explicit: a remediator that claimed the change owns the outcome, because empty almost always
means the file is already migrated and falling through would spend an agent run proving that
on every already-correct repository. That reasoning holds for `literal_swap`, whose
`can_handle` is a complete test of whether it can act -- a deprecation with a replacement is
always actionable.

It does not hold here. `can_handle` sees the change and never the call site, so this
remediator cannot know until `propose` whether the property is even at that location, whether
the argument is an object literal, or whether a spread makes the property set unknowable.
Those are declines, not "already migrated", and they must reach the agent.

So the two are separated deliberately: this returns an empty diff only for the one case that
genuinely means nothing to do -- the property is already gone from that call -- and every
case it cannot establish is a `CannotPatch`, which the tier catches and falls through on. An
empty diff that means "already correct" keeps abandoning the run, which is right; a decline
that means "not mechanical" reaches the agent, which is also right. Collapsing them would
either abandon findings the agent could fix, or spend an agent run on every repository that
was already correct.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from sync.core import CallSite, Finding, Patch, RepoRef, VendorChange
from sync.remediate.tiered import CannotPatch
from sync.route.templates import omit_argument_at
from sync.signals.oasdiff import changed_field

_KIND = "request-property-removed"

# Extension to ast-grep language. A file type absent here is declined rather than guessed:
# the parser choice decides what counts as an object literal, and the wrong grammar matches
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


class PropertyOmitRemediator:
    """Removes a removed request property from the one call site a finding names."""

    strategy = "codemod"

    def can_handle(self, finding: Finding, change: VendorChange) -> bool:
        """Only a request-side removal, and only when the vendor named the property.

        Response-side removals are excluded on purpose. Deleting a read means supplying
        what the code did with the value, which is reasoning rather than an edit.
        """
        return change.kind == _KIND and changed_field(change) is not None

    def propose(
        self,
        finding: Finding,
        change: VendorChange,
        site: CallSite,
        repo: RepoRef,
        diagnostics: str = "",
    ) -> Patch:
        """A unified diff for one file, or `CannotPatch` when this is not mechanical.

        An empty diff is returned only when the property is already absent from that call.
        Everything else this cannot establish raises, so the tier falls through to the
        agent rather than abandoning the finding -- see the module docstring.
        """
        field = changed_field(change)
        language = _language_for(site.path)
        if language is None:
            raise CannotPatch(f"{site.path} is not a language this codemod parses")

        target = Path(repo.local_path) / site.path
        try:
            # Bytes, decoded here rather than `read_text`, so no newline translation
            # happens in either direction. `read_text` folds CRLF to LF and `write_text`
            # expands LF to `os.linesep`, so on Windows a round trip rewrites every line
            # of an LF file. The diff would claim one line while `git add -u` staged the
            # whole file, and the pull request would ask for approval of a rewrite.
            original = target.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # The index can outlive the file: a deleted or moved path is a stale binding,
            # and a file that is not valid UTF-8 is not source this can reason about.
            raise CannotPatch(f"cannot read {site.path}: {type(exc).__name__}") from exc

        # `CallSite.line` is 1-based off tree-sitter's `start_point`; ast-grep counts from
        # zero. The column is already 0-based on both.
        updated = omit_argument_at(
            original, field, language=language, line=site.line - 1, col=site.col,
        )

        if updated is None:
            raise CannotPatch(
                f"could not locate an object-literal argument for `{field}` at "
                f"{site.path}:{site.line}"
            )
        if updated == original:
            # The call and its argument object were found and the property is not among
            # its keys: the code already agrees with the vendor. That is the one case
            # where an empty diff is the honest answer rather than a decline.
            return self._patch("", change, site, field)

        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{site.path}",
                tofile=f"b/{site.path}",
            )
        )
        target.write_bytes(updated.encode("utf-8"))
        return self._patch(diff, change, site, field)

    def _patch(self, diff: str, change: VendorChange, site: CallSite, field: str) -> Patch:
        return Patch(
            diff=diff, strategy=self.strategy, rationale=self._rationale(change, site, field)
        )

    def _rationale(self, change: VendorChange, site: CallSite, field: str) -> str:
        """What a reviewer reads before approving a machine-written change.

        It names the one call site the diff touches, because a file can hold several that
        pass the same property and the diff is a claim about which one was edited.
        """
        return (
            f"{change.vendor_id} removed the request property `{field}` from"
            f" {change.operation_id} between {change.from_version} and {change.to_version}."
            f" It is passed at {site.path}:{site.line}, and that call site alone is edited"
            f" here. The SDK's types still declare the property, so a type checker cannot"
            f" catch this."
        )

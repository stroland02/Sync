"""Indexing string literals that name a vendor operation.

`typescript.py` finds call sites by walking member chains -- `stripe.charges.create` -- which
is the right shape for an SDK method and the wrong shape for a model id. A model id is a string
in an options object; no member chain leads to it, and no type names it. That is exactly why a
type checker cannot catch a retired model and why the vendor's own audit tooling can only
report usage by API key rather than by line.

Output is `CallSite` with `operation_id` set to the literal's value, which is the same key
`to_vendor_changes` writes for a deprecation. `call_sites_for_operation` therefore joins the
two with no change to the DETECT stage.

This module uses `ast-grep` where `typescript.py` uses `tree-sitter` directly. They are the
same parser -- ast-grep is built on tree-sitter -- and the higher-level API keeps this file
short enough to read in one sitting. It is also the tool the project already adopted for
emitting migration rules, so the structural-matching surface stays one library rather than two.
"""

from __future__ import annotations

import hashlib

from ast_grep_py import SgRoot

from sync.core import CallSite

# Node kinds tree-sitter uses for a quoted string in the JS/TS grammars. `template_string` is
# deliberately absent: an interpolated model id is not a literal anyone can rewrite safely, and
# a rule that edited one could change the meaning of the interpolation.
_STRING_KINDS = ("string",)

_QUOTES = "\"'"


def _line_of(source: str, line_number: int) -> str:
    lines = source.splitlines()
    index = line_number - 1
    return lines[index] if 0 <= index < len(lines) else ""


def _enclosing_key(node) -> str | None:
    """The object key this literal is the value of, when it is one.

    A reviewer wants "the `model` field", not "a string on line 12", so this fills `symbol`
    the way the member chain fills it for a call site.
    """
    parent = node.parent()
    if parent is None:
        return None
    if parent.kind() not in ("pair", "property_signature"):
        return None
    key = parent.child(0)
    return key.text().strip(_QUOTES) if key is not None else None


def index_operation_literals(
    source: str,
    *,
    path: str,
    repo_id: str,
    vendor_id: str,
    sdk_version: str,
    prefixes: tuple[str, ...],
    language: str = "typescript",
) -> list[CallSite]:
    """Call sites for every string literal whose value starts with one of `prefixes`.

    The prefix filter is the precision decision. Indexing every string in a repository would
    make the graph mostly noise, slow every join, and bury the findings that matter. Which
    matched literals are actually affected is DETECT's question, not this stage's -- which is
    also why a new deprecation does not require a re-index.

    Vendor knowledge stays out of this module: `prefixes` is supplied by the caller that knows
    the vendor, keeping `sync.index` free of any vendor's naming scheme.
    """
    if not source.strip() or not prefixes:
        return []

    try:
        root = SgRoot(source, language).root()
    except Exception:
        # Customer repositories contain files that do not parse: generated output, partial
        # checkouts, syntax a newer compiler accepts. One bad file must not abort the index.
        return []

    sites: list[CallSite] = []

    for kind in _STRING_KINDS:
        for node in root.find_all(kind=kind):
            value = node.text().strip(_QUOTES)
            if not value.startswith(prefixes):
                continue

            start = node.range().start
            line = start.line + 1
            col = start.column

            # Hashing the whole line rather than the literal: the value alone is identical at
            # every site, so it could not distinguish one from another, and context changing
            # is what a re-index needs to notice.
            digest = hashlib.sha256(_line_of(source, line).encode("utf-8")).hexdigest()

            sites.append(
                CallSite(
                    repo_id=repo_id,
                    path=path,
                    line=line,
                    col=col,
                    vendor_id=vendor_id,
                    operation_id=value,
                    symbol=_enclosing_key(node) or value,
                    sdk_version=sdk_version,
                    content_hash=digest,
                )
            )

    return sites

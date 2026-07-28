"""Migration rules: what a finding produces instead of a diff.

`docs/superpowers/specs/2026-07-28-sync-domain-specific-thesis.md` argues Sync's missing piece
was a notation. Hennessy & Patterson's fifth domain-specific-architecture guideline is "use a
domain-specific language", and Coccinelle's SmPL is the same idea in the collateral-evolution
literature. `ast-grep` supplies the notation off the shelf -- declarative YAML, TypeScript
among its languages, built on the tree-sitter this project already indexes with -- so this
adopts rather than invents.

A rule beats a diff on four counts. It is reviewed once and trusted everywhere it applies,
rather than read per repository. It is reusable: the same vendor change at a thousand
customers is one rule, not a thousand agent runs. It gives `migration_outcome.edit_script` an
actual type, which its spec asks for and could not name. And it is what the public feed can
publish as the migration recipe alongside the change.

A deprecated model id is the first migration mechanical enough to need no model at all: one
string literal becomes another, and the vendor names the replacement.
"""

from __future__ import annotations

from typing import Any

from ast_grep_py import SgRoot

from sync.core import VendorChange

_DEPRECATION_PREFIX = "deprecation/model-"

# Quote styles a rule is emitted for, one rule each. A single rule matching both would have to
# pick one style for its fix and would rewrite the other, adding diff noise to every review and
# risking a fight with whatever formatter the customer's CI runs -- the CI this patch must pass.
_QUOTES = ('"', "'")


def model_literal_swap(change: VendorChange, language: str) -> list[dict[str, Any]]:
    """`ast-grep` rules rewriting a retired model id to its replacement.

    Returns an empty list when the change is not a model deprecation, or when the vendor named
    no replacement. A migration with no target is not a migration: emitting a rule that deletes
    the id, or guesses a successor, is worse than reporting the finding and stopping.
    """
    if not change.kind.startswith(_DEPRECATION_PREFIX):
        return []

    old = change.raw.get("model_id")
    new = change.raw.get("replacement")
    if not isinstance(old, str) or not isinstance(new, str) or not old or not new:
        return []

    return [
        {
            "id": f"sync-{change.vendor_id}-model-{old}-{style_name}",
            "language": language,
            # The pattern is a whole string literal, so matching is exact by construction. A
            # textual search would rewrite `claude-x` inside `claude-x-preview` and inside an
            # identifier, and the result would still compile -- failing only at the vendor.
            "rule": {"pattern": f"{quote}{old}{quote}"},
            "fix": f"{quote}{new}{quote}",
        }
        for quote, style_name in zip(_QUOTES, ("double", "single"), strict=True)
    ]


def apply_rules(rules: list[dict[str, Any]], source: str, language: str) -> str:
    """`source` with every rule applied, or `source` unchanged when none match.

    Applying is deterministic and needs no model, which is the whole point of tier 0. The
    operation is idempotent: a second application finds nothing, because the pattern names the
    old id and the fix writes the new one.
    """
    if not rules:
        return source

    result = source
    for rule in rules:
        pattern = rule["rule"]["pattern"]
        fix = rule["fix"]

        root = SgRoot(result, language).root()
        edits = [node.replace(fix) for node in root.find_all(pattern=pattern)]
        if edits:
            result = root.commit_edits(edits)

    return result

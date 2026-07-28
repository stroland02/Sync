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


def _pair_part(pair, field: str, position: int) -> str | None:
    """A pair's key or value text, by grammar field with a positional fallback.

    `field()` is the robust accessor -- it survives a grammar reordering that positional
    indices would silently misread -- but the fallback keeps this working if a grammar omits
    the field name.
    """
    node = pair.field(field) or pair.child(position)
    return node.text().strip("\"'") if node is not None else None


def _deletion_span(source: str, container, pair) -> tuple[int, int]:
    """The byte span covering a pair and the separator that binds it to its neighbours.

    Deleting the pair alone leaves `{ model: "x", , max_tokens: 16 }`. That is the whole
    difficulty, and re-parsing does not catch it -- tree-sitter recovers silently and reports
    no error for a dangling comma -- so the separator is removed with the pair rather than
    cleaned up afterwards.

    A following comma is preferred over a preceding one so the remaining entries keep the
    separators they already had.
    """
    children = list(container.children())
    target = pair.range().start.index
    index = next(i for i, child in enumerate(children) if child.range().start.index == target)

    start = pair.range().start.index
    end = pair.range().end.index

    following = children[index + 1] if index + 1 < len(children) else None
    if following is not None and following.kind() == ",":
        end = following.range().end.index
        # The space that separated this entry from the next one goes too. Left behind it
        # becomes a double space in an inline object -- a formatting change inside a diff whose
        # only claimed purpose is removing an argument.
        while end < len(source) and source[end] in " \t":
            end += 1
    else:
        preceding = children[index - 1] if index > 0 else None
        if preceding is not None and preceding.kind() == ",":
            start = preceding.range().start.index

    return _widen_to_whole_line(source, start, end)


def _widen_to_whole_line(source: str, start: int, end: int) -> tuple[int, int]:
    """Take the surrounding line too, when the span is all that is on it.

    Leaving an empty indented line behind would put a whitespace-only change in a diff a human
    has to approve, for no reason.
    """
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end == -1:
        return start, end

    if source[line_start:start].strip() or source[end:line_end].strip():
        return start, end
    return line_start, line_end + 1


def omit_parameter(
    source: str, parameter: str, language: str, within_object_naming: str
) -> str:
    """`source` with `parameter` removed from objects that also name `within_object_naming`.

    The scope matters. A `temperature` nested elsewhere in the file is not this call's
    argument, and removing it would edit code the finding never described -- worse than leaving
    a real one in place, because the diff would claim something untrue.

    Returns `source` unchanged when there is nothing to remove, which the caller reads as
    "no edit" rather than as failure.
    """
    root = SgRoot(source, language).root()

    spans: list[tuple[int, int]] = []
    for container in root.find_all(kind="object"):
        pairs = [child for child in container.children() if child.kind() == "pair"]
        names_the_model = any(
            _pair_part(pair, "value", 2) == within_object_naming
            for pair in pairs
        )
        if not names_the_model:
            continue

        for pair in pairs:
            if _pair_part(pair, "key", 0) == parameter:
                spans.append(_deletion_span(source, container, pair))

    if not spans:
        return source

    # Right to left, so an earlier span's offsets are still valid after a later one is cut.
    result = source
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    return result


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

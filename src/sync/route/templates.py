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

# Upper bound on removal passes. A pathological object cannot spin the loop.
_MAX_REMOVALS = 200


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


def _to_character_column(source: str, line: int, byte_col: int) -> int:
    """A tree-sitter byte column, as the character column ast-grep reports.

    The two are not the same unit and an earlier version of this module claimed they were.
    `sync/index/typescript.py` parses `read_bytes()`, so `start_point[1]` counts bytes; ast-grep
    reports characters. On a line holding one multi-byte character they differ by one, and on a
    line holding many they differ by enough to land inside a different call -- which the exact
    match below would then accept as the right one.

    Every fixture in this repository is ASCII, so no existing test could have caught this.
    """
    lines = source.splitlines()
    if not (1 <= line <= len(lines)):
        return byte_col

    encoded = lines[line - 1].encode("utf-8")
    if byte_col >= len(encoded):
        return len(lines[line - 1])
    # Truncating mid-character is possible when a caller passes a column this line never had;
    # decoding leniently keeps that a wrong answer rather than an exception.
    return len(encoded[:byte_col].decode("utf-8", errors="ignore"))


def _contains(node, line: int, col: int) -> bool:
    """Whether a node's range covers a 1-based line and a 0-based *character* column.

    Ranges are half-open at the end, so a column equal to `end.column` is one past the node and
    is not inside it.
    """
    span = node.range()
    start, end = span.start, span.end
    if not (start.line + 1 <= line <= end.line + 1):
        return False
    if line == start.line + 1 and col < start.column:
        return False
    if line == end.line + 1 and col >= end.column:
        return False
    return True


def _call_at(root, line: int, col: int):
    """The call expression a finding's position names.

    An exact start match is preferred, because that is what the indexer recorded. A position
    merely inside the call is accepted as a fallback: an off-by-one between a 0-based and a
    1-based column would otherwise turn a correct patch into a silent no-op, and a no-op reads
    as "nothing to fix" rather than as a miss.

    Where several calls contain the position -- a call inside a call's arguments -- the
    innermost wins, since that is the one the position most specifically identifies.
    """
    exact = None
    containing = []

    for call in root.find_all(kind="call_expression"):
        span = call.range().start
        if span.line + 1 == line and span.column == col:
            exact = call
        if _contains(call, line, col):
            containing.append(call)

    if exact is not None:
        return exact
    if not containing:
        return None
    return min(containing, key=lambda c: c.range().end.index - c.range().start.index)


def omit_property_at(source: str, prop: str, language: str, line: int, col: int) -> str:
    """`source` with `prop` removed from the object argument of the call at that position.

    `omit_parameter` scopes by a value in the same object, which is the wrong scope for a
    finding that names a location: a file can hold two identical calls, and removing the
    property from both is wrong even when both pass it, because the finding named one and the
    reviewer was told it named one.

    Only the call's own argument object is searched. A property nested deeper is not an
    argument of this call, and removing it would produce a diff the finding does not justify.

    Returns `source` unchanged whenever the target cannot be identified exactly -- no call at
    that position, no object argument, or the property absent. Producing nothing lets the tier
    fall through; producing the wrong edit does not.
    """
    root = SgRoot(source, language).root()

    # The caller passes what `CallSite` recorded, which tree-sitter measured in bytes.
    call = _call_at(root, line, _to_character_column(source, line, col))
    if call is None:
        return source

    arguments = call.field("arguments")
    if arguments is None:
        return source

    for container in arguments.children():
        if container.kind() != "object":
            continue
        for pair in [child for child in container.children() if child.kind() == "pair"]:
            if _pair_part(pair, "key", 0) != prop:
                continue
            start, end = _deletion_span(source, container, pair)
            return source[:start] + source[end:]

    return source


def _objects_naming(root, model: str):
    """Object literals that carry `model` as one of their values.

    The scope every parameter edit shares. A parameter nested elsewhere in the file is not this
    call's argument, and editing it would make the diff claim something the finding never said.
    """
    for container in root.find_all(kind="object"):
        pairs = [child for child in container.children() if child.kind() == "pair"]
        if any(_pair_part(pair, "value", 2) == model for pair in pairs):
            yield container, pairs


def _key_node(pair):
    return pair.field("key") or pair.child(0)


def _declared_keys(container) -> set[str]:
    """Every key an object literal declares, in whatever form it declares it.

    A duplicate key does not fail -- JavaScript takes the last one -- so a guard that misses a
    form produces exactly the silent overwrite it exists to prevent. Three forms carry a name
    and the first version of this guard saw only one:

    - `max_tokens: 8` is a pair.
    - `{ max_tokens }` is shorthand for `max_tokens: max_tokens`, and is not a pair at all.
    - `{ ["max_tokens"]: 8 }` is a pair whose key is a computed name wrapping a literal.

    A computed key that is not a literal -- `{ [k]: 8 }` -- names nothing knowable here and is
    not collected. That direction is safe: an unknown key cannot be proven absent, so a rename
    that might collide with it is declined by the caller only when a known key matches.
    """
    keys: set[str] = set()

    for child in container.children():
        if child.kind() == "shorthand_property_identifier":
            keys.add(child.text())
            continue
        if child.kind() not in ("pair", "property_signature"):
            continue

        node = _key_node(child)
        if node is None:
            continue
        if node.kind() == "computed_property_name":
            inner = node.text().strip("[]").strip()
            if inner[:1] in ("\"", "'"):
                keys.add(inner.strip("\"'"))
            continue
        keys.add(node.text().strip("\"'"))

    return keys


def rename_parameter(
    source: str, old: str, new: str, language: str, within_object_naming: str
) -> str:
    """`source` with the `old` argument key renamed to `new`, where it is safe to do so.

    Declined per object when `new` is already a key there. A duplicate key does not fail:
    JavaScript takes the last one, so the object would quietly carry a different value than
    either the author or this patch intended, and it would type-check on the way through.
    Declining one object does not stop a clean one being fixed, or a single awkward call site
    would freeze the whole file.

    Quoting is preserved. A key written `"budget_tokens"` and one written `budget_tokens` are
    the same key, and rewriting one form as the other puts a style change in a diff whose only
    claimed purpose is a rename.
    """
    root = SgRoot(source, language).root()
    edits: list[tuple[int, int, str]] = []

    for container, pairs in _objects_naming(root, within_object_naming):
        if new in _declared_keys(container):
            continue

        for pair in pairs:
            if _pair_part(pair, "key", 0) != old:
                continue
            node = _key_node(pair)
            if node is None:
                continue

            text = node.text()
            quote = text[0] if text[:1] in ("\"", "'") else ""
            span = node.range()
            edits.append((span.start.index, span.end.index, f"{quote}{new}{quote}"))

    if not edits:
        return source

    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def omit_parameter(
    source: str, parameter: str, language: str, within_object_naming: str
) -> str:
    """`source` with `parameter` removed from objects that also name `within_object_naming`.

    The scope matters. A `temperature` nested elsewhere in the file is not this call's
    argument, and removing it would edit code the finding never described -- worse than leaving
    a real one in place, because the diff would claim something untrue.

    One removal per pass, re-parsing between them. Batching spans computed against a single
    tree corrupts an object holding the key twice: the second pair takes the comma that the
    first pair's span already claimed, and applying both leaves output that does not parse.
    Re-parsing is the cheap way to make every span current rather than to reason about which
    overlaps are safe.

    Returns `source` unchanged when there is nothing to remove, which the caller reads as
    "no edit" rather than as failure.
    """
    result = source

    # Bounded by the number of pairs that could match, so a span that somehow fails to shrink
    # the source ends the loop rather than spinning.
    for _ in range(_MAX_REMOVALS):
        root = SgRoot(result, language).root()
        span = None

        for container, pairs in _objects_naming(root, within_object_naming):
            for pair in pairs:
                if _pair_part(pair, "key", 0) == parameter:
                    span = _deletion_span(result, container, pair)
                    break
            if span is not None:
                break

        if span is None:
            return result

        start, end = span
        if end <= start:
            return result
        result = result[:start] + result[end:]

    return result


def _object_argument_at(root, line: int, col: int):
    """The object literal passed to the call starting at `line`/`col`, if there is one.

    Both coordinates are matched. A line alone is not an identity -- two calls can share
    one -- and falling back to the first call on the line would edit whichever the
    formatter happened to put first.

    `ast-grep` and the tree-sitter positions `CallSite` is built from agree on both
    values, which was checked rather than assumed. Where they could not, a mismatch
    declines, and declining costs an agent run rather than a wrong edit.
    """
    for call in root.find_all(kind="call_expression"):
        start = call.range().start
        if start.line != line or start.column != col:
            continue
        arguments = call.field("arguments")
        if arguments is None:
            return None
        return next(
            (child for child in arguments.children() if child.kind() == "object"), None
        )
    return None


def omit_argument_at(
    source: str, argument: str, language: str, line: int, col: int
) -> str | None:
    """`source` with `argument` removed from the object passed at one specific call.

    The deletion is `omit_parameter`'s -- same span, same separator handling, same
    whole-line rule -- and only the scoping differs. A deprecation finding carries no
    location, so `omit_parameter` scopes by an object that names the model; a spec-change
    finding carries a call site, and scoping it by a sibling value would edit a second
    call the finding never named. Two entry points over one span implementation is the
    shape that keeps the dangling-comma fix in one place.

    Three outcomes, and the caller needs all three kept apart:

    - the edited source, when the property was there and was removed;
    - `source` unchanged, when the call and its object literal were found and the property
      simply is not among its keys -- the code already agrees with the vendor;
    - `None`, when nothing could be established: no call at that position, an argument
      that is not an object literal, or an object carrying a spread.

    That last distinction is the load-bearing one. "Already correct" and "cannot tell" are
    different answers, and a caller that collapses them either abandons a finding another
    tier could repair or claims a repair it never made. A spread is in the third group
    rather than the second because `...defaults` may itself supply the property, so
    deleting the explicit pair would not establish that the request stops sending it.

    A shorthand property (`{ receipt_email }`) is not a `pair`, so it reads as absent
    rather than as a decline. That is a real shape this could remove and currently does
    not.
    """
    root = SgRoot(source, language).root()

    container = _object_argument_at(root, line, col)
    if container is None:
        return None

    children = list(container.children())
    if any(child.kind() == "spread_element" for child in children):
        return None

    for pair in (child for child in children if child.kind() == "pair"):
        if _pair_part(pair, "key", 0) == argument:
            start, end = _deletion_span(source, container, pair)
            return source[:start] + source[end:]
    return source


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

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

from pathlib import Path
from typing import Any

from ast_grep_py import SgRoot

from sync.core import VendorChange

_DEPRECATION_PREFIX = "deprecation/model-"

# Extension to ast-grep language. A suffix absent here is declined rather than guessed: the
# grammar decides what counts as an object literal, and the wrong one matches nothing, which
# reads as "the property is not there" rather than as "this was not parsed".
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

# Node kinds whose value is written out in full at the call site, so deleting the pair that
# holds one removes the whole of it. Everything else -- an identifier, a call, a member
# expression, a template with a substitution -- reaches somewhere this cannot see, and
# deleting it would be reasoning about the surrounding code rather than an edit. The set is
# deliberately tight: the conservative answer costs an agent run, the generous one corrupts.
_LITERAL_KINDS = frozenset({"string", "number", "true", "false", "null", "regex"})

# Quote styles a rule is emitted for, one rule each. A single rule matching both would have to
# pick one style for its fix and would rewrite the other, adding diff noise to every review and
# risking a fight with whatever formatter the customer's CI runs -- the CI this patch must pass.
_QUOTES = ('"', "'")

# Characters a key's name can be wrapped in. The backtick is here because a template with
# nothing interpolated is a literal spelled differently, which is the rule this module already
# applies to a value.
_KEY_QUOTES = "\"'`"

# Node kinds whose text carries a key's name wrapped in one of `_KEY_QUOTES`. Used to decide
# what a rename writes back, rather than reading the first character: a key node can have empty
# text -- `{ : 1 }` yields an empty `property_identifier` -- and an empty string is a substring
# of every string.
_QUOTED_KINDS = frozenset({"string", "template_string"})



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


def _value_text(pair) -> str | None:
    """A pair's value as it is written, by grammar field with a positional fallback.

    `field()` is the robust accessor -- it survives a grammar reordering that positional
    indices would silently misread -- but the fallback keeps this working if a grammar omits
    the field name.
    """
    node = pair.field("value") or pair.child(2)
    return node.text().strip("\"'") if node is not None else None


def _key_node(pair):
    return pair.field("key") or pair.child(0)


def _name_node(key):
    """The node whose text carries the name a key declares, or `None` where it declares none.

    A computed key wraps its name: `{ ['receipt_email']: 'x' }` declares `receipt_email`, and
    the brackets are not part of it. Returning the *node* rather than the name is what lets one
    rule serve both the readers and the rewriter -- a reader takes its text, `rename_parameter`
    replaces its span. Unwrapping inside a shared text accessor instead would make a rename
    write the name bare, turning `['budget_tokens']` into `max_tokens`: a change to the form of
    source the customer wrote, inside a diff whose only claimed purpose is a rename.

    `None` where the name is not written at the call site. `{ [k]: 1 }`, `{ [FIELDS.a]: 1 }`
    and `` { [`${p}_email`]: 1 } `` each name something only the running program knows, and
    reading one would be reasoning about the surrounding code rather than reading the call. A
    numeric computed key is `None` for the same reason it is not a name.

    This is where the read/rewrite split from M3-W110 landed, and it is neither a parameter
    on the old `_pair_part` nor two independently maintained functions: `_pair_part` read a
    key or a value at a fixed grammar position and had no notion of a computed name, which is
    what let one read as absent. One grammar reading lives here; the four call sites that
    compare a name go through `_key_name`'s `.text()` of what this returns, and the one call
    site that rewrites one -- `rename_parameter` -- replaces this node's span directly. A
    shared text accessor could not serve both: unwrapping the brackets before handing back
    text is correct for a comparison and wrong for a rewrite, which is exactly the defect this
    task exists to close.
    """
    if key is None or key.kind() != "computed_property_name":
        return key

    inner = key.child(1)
    if inner.kind() == "template_string":
        if any(child.kind() == "template_substitution" for child in inner.children()):
            return None
        return inner
    return inner if inner.kind() == "string" else None


def _key_name(pair) -> str | None:
    """The name a pair's key declares, or `None` where it declares nothing readable here.

    Quoting is not part of a name. `budget_tokens`, `"budget_tokens"` and `['budget_tokens']`
    are one key, and a caller asking whether an object carries it wants that answer.
    """
    node = _name_node(_key_node(pair))
    return node.text().strip(_KEY_QUOTES) if node is not None else None


def _names_a_key_this_cannot_read(children: list) -> bool:
    """Whether the object declares a key only the running program knows.

    The unknown a spread carries, in a different shape. `{ [k]: 'x' }` may itself be the
    property under discussion, so neither "the property is here" nor "the property is not
    here" is established, and removing an explicit pair anyway produces a patch that compiles,
    type-checks, and leaves the call sending what it claims to have stopped sending.
    """
    return any(_key_name(child) is None for child in children if child.kind() == "pair")


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

    sole = _sole_entry_span(source, children)
    if sole is not None:
        return _widen_to_whole_line(source, *sole)

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


def _sole_entry_span(source: str, children: list) -> tuple[int, int] | None:
    """The whole interior of the braces, when one entry is all they hold.

    Removing the pair alone leaves `create({  })`: both spaces that surrounded it stay, and
    a diff whose only claimed purpose was removing an argument carries a whitespace change
    as well. Taking the interior removes them, along with whichever commas a sole entry was
    written with -- `{ model: "x" }` and `{ model: "x", }` differ by one branch of the
    separator rule and left two spaces and one respectively.

    Only where the interior is on one line. Across lines the braces are the author's
    formatting rather than a separator, `_widen_to_whole_line` already removes the entry's
    own line, and closing them up would reflow code the finding said nothing about.

    Anything that is not a brace or a comma counts as an entry, so an object holding a
    comment beside its pair is left to the separator rule.
    """
    entries = [child for child in children if child.kind() not in ("{", "}", ",")]
    if len(entries) != 1:
        return None

    start, end = children[0].range().end.index, children[-1].range().start.index
    if "\n" in source[start:end]:
        return None
    return start, end


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


def _has_object_argument(call) -> bool:
    arguments = call.field("arguments")
    if arguments is None:
        return False
    return any(child.kind() == "object" for child in arguments.children())


def _preferred(calls: list):
    """Which of several calls starting at one position an object edit acts on.

    A position is not an identity. `wrap(cfg)({ receipt_email: 'x' })` starts where
    `wrap(cfg)` starts, and `stripe.p.create({ ... }).then(h)` starts where
    `stripe.p.create({ ... })` starts, so both shapes offer two calls at the recorded
    column. Traversal order used to decide, which meant the first shape resolved to
    `wrap(cfg)` -- no object argument, nothing removed, and the caller reading an unchanged
    source as "already correct" rather than as a miss.

    Nesting depth cannot be the rule, because the two shapes want opposite ends of the
    nest: the first wants the outer call and the second the inner. What separates them is
    whether a call's own argument list holds an object literal. That is not a guess about
    which call the finding meant; it is a statement of which call this edit can act on at
    all, since a call passing no object has no property to remove.

    A tie -- `f({ a: 1 })({ receipt_email: 'x' })`, where both qualify -- goes to the widest
    span: the complete expression beginning at that position rather than a fragment of it.
    """
    return max(
        calls,
        key=lambda call: (
            _has_object_argument(call),
            call.range().end.index - call.range().start.index,
        ),
    )


def _call_at(root, line: int, col: int):
    """The call expression a finding's position names.

    An exact start match is preferred, because that is what the indexer recorded. A position
    merely inside the call is accepted as a fallback: an off-by-one between a 0-based and a
    1-based column would otherwise turn a correct patch into a silent no-op, and a no-op reads
    as "nothing to fix" rather than as a miss.

    Several calls can share that start, and `_preferred` states which one is taken.

    Where several calls merely contain the position -- a call inside a call's arguments --
    the innermost wins, since that is the one the position most specifically identifies.
    """
    exact = []
    containing = []

    for call in root.find_all(kind="call_expression"):
        span = call.range().start
        if span.line + 1 == line and span.column == col:
            exact.append(call)
        if _contains(call, line, col):
            containing.append(call)

    if exact:
        return _preferred(exact)
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
            if _key_name(pair) != prop:
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
        if any(_value_text(pair) == model for pair in pairs):
            yield container, pairs


def _declared_keys(container) -> set[str]:
    """Every key an object literal declares, in whatever form it declares it.

    A duplicate key does not fail -- JavaScript takes the last one -- so a guard that misses a
    form produces exactly the silent overwrite it exists to prevent. Three forms carry a name
    and the first version of this guard saw only one:

    - `max_tokens: 8` is a pair.
    - `{ max_tokens }` is shorthand for `max_tokens: max_tokens`, and is not a pair at all.
    - `{ ["max_tokens"]: 8 }` is a pair whose key is a computed name wrapping a literal.

    The third comes from `_key_name`, which is the same rule every key comparison in this
    module reads. A guard that saw a form the comparison did not would decline a rename the
    comparison then made, and the reverse would make the rename it declines.

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

        name = _key_name(child)
        if name is not None:
            keys.add(name)

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

    The key's form is preserved, not only its quoting. `budget_tokens`, `"budget_tokens"` and
    `['budget_tokens']` are one key, and rewriting one form as another puts a style change in a
    diff whose only claimed purpose is a rename. For a computed key the difference is larger
    than style: what is replaced is the name inside the brackets, because writing the name
    bare there produces `[max_tokens]`, which is a reference to a binding.

    A key computed from anything but a literal is left alone. Its name is not written at the
    call site, so renaming it would be renaming whatever the brackets happen to hold.
    """
    root = SgRoot(source, language).root()
    edits: list[tuple[int, int, str]] = []

    for container, pairs in _objects_naming(root, within_object_naming):
        if new in _declared_keys(container):
            continue

        for pair in pairs:
            node = _name_node(_key_node(pair))
            if node is None or node.text().strip(_KEY_QUOTES) != old:
                continue

            quote = node.text()[0] if node.kind() in _QUOTED_KINDS else ""
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
    overlaps are safe. It costs one parse per removal, so a file passing the key at N call sites
    is parsed N times -- paid because the alternative is the overlap reasoning this module has
    already been wrong about once.

    The loop runs until a pass finds nothing, and is not bounded by a pass count. It used to be,
    and the count bounded passes over the whole source rather than over one object: a file
    holding more matching calls than the bound silently kept the remainder -- measured, 201 calls
    each passing the key left one behind and 250 left fifty, in output that parsed and
    type-checked. Raising the number moved the cliff rather than removing it.

    Removing it is safe because the loop already had a variant. A span is computed only where a
    pair matching `parameter` was found, and every branch of `_deletion_span` returns a range
    covering that pair -- the sole-entry branch takes the whole brace interior, which is that
    pair, and the separator branch starts no later and ends no earlier than the pair itself. So a
    pass that shrinks the source has removed a match, and the number of matches left is a
    non-negative integer that strictly decreases. Nor can a pass create one: the widening rule
    consumes a whole line including its own newline, and the separator rule consumes only spaces
    and tabs, so no deletion joins two lines into a token that was not there before.

    Returns `source` unchanged when there is nothing to remove, which the caller reads as
    "no edit" rather than as failure.
    """
    result = source

    while True:
        root = SgRoot(result, language).root()
        span = None

        for container, pairs in _objects_naming(root, within_object_naming):
            for pair in pairs:
                if _key_name(pair) == parameter:
                    span = _deletion_span(result, container, pair)
                    break
            if span is not None:
                break

        if span is None:
            return result

        start, end = span
        if end <= start:
            # A span that removes nothing would be recomputed identically forever. Nothing
            # reaches this today, per the variant argument above, and it stays because it is
            # what makes termination a property of the loop rather than a belief about
            # `_deletion_span` -- which is the guarantee the pass count was standing in for.
            return result
        result = result[:start] + result[end:]


def _object_argument_at(root, line: int, col: int):
    """The object literal passed to the call starting at `line`/`col`, if there is one.

    Both coordinates are matched. A line alone is not an identity -- two calls can share
    one -- and falling back to the first call on the line would edit whichever the
    formatter happened to put first.

    `ast-grep` and the tree-sitter positions `CallSite` is built from agree on both
    values, which was checked rather than assumed. Where they could not, a mismatch
    declines, and declining costs an agent run rather than a wrong edit.

    Several calls can still share one start, so `_preferred` chooses among them rather than
    traversal order. Taking the first produced the mirror image of `_call_at`'s defect: on
    `stripe.p.create({ ... }).then(h)` it took the outer call, found `(h)` where an object
    should be, and answered `None` -- "cannot establish" for a shape that is entirely
    establishable, which abandons a finding to a tier that costs an agent run.
    """
    matches = [
        call
        for call in root.find_all(kind="call_expression")
        if call.range().start.line == line and call.range().start.column == col
    ]
    if not matches:
        return None

    arguments = _preferred(matches).field("arguments")
    if arguments is None:
        return None
    return next(
        (child for child in arguments.children() if child.kind() == "object"), None
    )


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
      that is not an object literal, an object carrying a spread, or one carrying a key
      only the running program knows.

    That last distinction is the load-bearing one. "Already correct" and "cannot tell" are
    different answers, and a caller that collapses them either abandons a finding another
    tier could repair or claims a repair it never made. A spread is in the third group
    rather than the second because `...defaults` may itself supply the property, so
    deleting the explicit pair would not establish that the request stops sending it. A
    key this cannot read -- `{ [k]: 'x' }` -- is the same unknown in a different shape:
    `k` may itself hold `argument`, so a pass that only matches the pairs it can read would
    report the property absent from an object that may well carry it.

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
    if _names_a_key_this_cannot_read(children):
        return None

    for pair in (child for child in children if child.kind() == "pair"):
        if _key_name(pair) == argument:
            start, end = _deletion_span(source, container, pair)
            return source[:start] + source[end:]
    return source


def language_for(path: str) -> str | None:
    """The ast-grep grammar for a source path, or `None` for one this cannot parse.

    Here rather than beside a remediator because the routing decision and the edit have to
    agree on it: a path the router judged as TypeScript and the codemod declined to parse
    would route work to a tier that cannot take it.
    """
    return _LANGUAGES.get(Path(path).suffix.lower())


def argument_is_literal_at(
    source: str, argument: str, language: str, line: int, col: int
) -> bool | None:
    """Whether one named argument at one call is written out as a literal value.

    This is `RoutingFacts.field_passed_as_literal`, answered from the source rather than from
    the index. The index records which keys a call site passes and never how each was
    written, and the distinction is what row 4 of the decision table turns on: deleting
    `receipt_email: 'a@example.com'` removes the whole of what was sent, while deleting
    `receipt_email: userEmail` drops the only use of a variable and leaves the question of
    what that variable was for.

    Scoped exactly as `omit_argument_at` is, over the same `_object_argument_at`, because the
    router and the codemod must read the same call. Three answers, and the caller needs them
    apart:

    - `True`  -- the pair is there and its value is a literal;
    - `False` -- the pair is there and its value is not, or the pair is simply absent, which
      is equally not "passed as a literal";
    - `None`  -- nothing could be established: no call at that position, no object argument,
      a spread, which may supply the property itself and so settles nothing, or a key only
      the running program knows, which may itself be `argument` and so settles nothing
      either.

    A shorthand property (`{ receipt_email }`) is not a `pair` and so answers `False`. That is
    right for the wrong reason and right anyway: the value is an identifier, and
    `omit_argument_at` cannot remove a shorthand either.
    """
    root = SgRoot(source, language).root()

    container = _object_argument_at(root, line, col)
    if container is None:
        return None

    children = list(container.children())
    if any(child.kind() == "spread_element" for child in children):
        return None
    if _names_a_key_this_cannot_read(children):
        return None

    for pair in (child for child in children if child.kind() == "pair"):
        if _key_name(pair) != argument:
            continue
        value = pair.field("value")
        if value is None:
            return False
        kind = value.kind()
        if kind == "template_string":
            # A template with no substitution is a literal spelled differently. One with a
            # substitution reaches a variable, which is the case this whole function exists
            # to keep away from a codemod.
            return not any(
                child.kind() == "template_substitution" for child in value.children()
            )
        return kind in _LITERAL_KINDS

    return False


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

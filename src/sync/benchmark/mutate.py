"""Labelled pairs by synthetic mutation of a real repository.

Binding precision and recall are the two axes `2026-07-27-sync-benchmark-gates.md` calls the
ones that matter most, and both need a labelled reference that a solo founder with no users
does not have. The obvious source was mining: find repositories that pinned a Stripe API
version, find the commit that bumped it across a breaking release, and take the human's
migration as the correct answer. `2026-07-29-sync-ground-truth-quality.md` read 117 such
commits and returned No -- 58% carry a trailer naming a coding agent, the five plausible human
migrations were none of them migrations, and the pinned cohort does not migrate at all, which
is a population problem rather than a search problem. It named this as the fallback the
benchmark specification had already reserved: synthetic mutation of real repositories, at the
cost of realism.

How the label is derived, and why it cannot ask the binder
----------------------------------------------------------
The mutation is the inverse of a vendor change: it writes into a chosen call site the exact
dependency the change removes. So the generator knows which sites the change breaks because it
broke them, and the label is a record of the edits it made -- not a computation over the
result. Every other site is labelled unaffected, and a site the generator could not reach is
labelled unaffected and *named*, since a target it failed to break is not a site the change
breaks.

Deriving the label any other way is the failure this whole approach exists to avoid. A label
computed by asking Sync's own binder which call sites an operation change affects would score
the binder against its own opinion: precision and recall would both read 1.0 against any binder
whatsoever, including a broken one, and the number would move only when the binder and the
scorer disagreed about something neither was right about. This module therefore imports nothing
from `sync.index`, `sync.detect` or `sync.graph`, and a test asserts that structurally rather
than trusting the sentence.

A generator that mutated every call site would fail the other half. Precision needs findings
that were wrong, so it needs call sites the change genuinely does not touch; a corpus where
every site is affected cannot measure it at all and reports 1.0 for the same empty reason. The
caller names its targets and everything else is a negative.

Guarding the exactness
----------------------
The label is exact only while the mutation is the sole source of the dependency, so a call site
that already carries it -- already passes the removed property, already reads the removed
response field -- is refused by name rather than labelled. Labelling it unaffected would
manufacture a false positive for every binder that correctly found it; labelling it affected
would break the rule above, because that label would not come from an edit.

The realism cost, stated rather than argued away
------------------------------------------------
A synthetic mutation is a vendor change applied mechanically to code written against the old
contract. Real migrations are messier: a human restructures, renames variables, works around
the change, or migrates half the call sites and leaves the rest for a later commit. Nothing
here produces any of that.

Three consequences belong beside any number this generator's pairs produce:

- **The distribution is chosen by whoever writes the generator.** Precision and recall measured
  over these pairs describe performance against the mutations implemented here, in the
  proportions the caller requests -- not against Stripe's release history. That belongs in the
  same sentence as the score, the way sample size does.
- **The break is mechanical and local.** One property inserted into one call's argument object,
  or one guard reading one response field. A real break often lands in code that has drifted
  around the call over years, which is exactly where a binder's static reading is weakest, so
  these pairs are biased *towards* the binder.
- **The repository is real and the change is not.** The code is somebody's, written for their
  own reasons, which is the property mining was wanted for; the vendor change applied to it is
  a change nobody shipped.

What is deliberately not here: a scorer -- `binding.py` already takes labels and this module
produces them -- and a mining harness, which the verdict recommends against building even for
comparison.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from ast_grep_py import SgRoot
from pydantic import BaseModel

from sync.benchmark.binding import BindingLabel
from sync.core import CallSite, VendorChange
from sync.signals.oasdiff import changed_field

# oasdiff's own kind names, taken from its catalogue rather than invented, and narrowed to the
# ones this repository's decision table already routes -- a mutation nobody's vendor would
# publish scores Sync against a world that does not exist.
REQUEST_KINDS: frozenset[str] = frozenset({"request-property-removed", "request-parameter-removed"})
RESPONSE_KINDS: frozenset[str] = frozenset({"response-property-removed"})
SUPPORTED_KINDS: frozenset[str] = REQUEST_KINDS | RESPONSE_KINDS

# The value the inserted property carries. A literal rather than an expression so the mutation
# is one insertion with no free variables, and the same literal every time so two runs over one
# input are byte-identical.
MUTATION_LITERAL = "'sync-benchmark'"

_STATEMENT_KINDS = frozenset({
    "lexical_declaration", "variable_declaration", "expression_statement", "return_statement",
})

# Which suffixes this generator can parse and edit, and it is deliberately not the router's
# table. `sync.route.templates.language_for` answers a different question -- *can a codemod patch
# this file* -- and its own docstring says the routing decision and the edit have to agree on it.
# Teaching that table `.py` would tell `remediate.tiered` a Python finding can be codemodded and
# `remediate.property_omit` that it can patch one, and both match TypeScript's `object` literal
# where Python has `dictionary`: the finding routes to a tier that produces an empty diff and
# abandons as "the remediator produced no change", which is the exact failure that docstring
# exists to prevent, arriving through a fix for something else.
#
# One function cannot answer both, and a flag on it would be the same coupling spelled with an
# argument -- a caller who omits it gets the wrong answer silently. So the generator owns what
# the generator can do. The TypeScript half started as a copy of the router's, so nothing that
# was mutable before is mutable differently now; `.py` is what this file adds.
_MUTABLE_LANGUAGES = {
    ".ts": "typescript", ".tsx": "tsx", ".mts": "typescript", ".cts": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".py": "python",
}

# Node kinds per language, for the places where only the grammar differs. Where the *syntax* of
# an edit differs -- how a request field is written, what a guard looks like -- the functions
# below branch, because a table of format strings would hide which language a bug is in.
_CALL_KIND = {"python": "call"}
_MAPPING_KIND = {"python": "dictionary"}
# Binder kind -> the field holding the name, and the field holding the value.
_BINDING_FORMS = {
    "python": {"assignment": ("left", "right"), "named_expression": ("name", "value")},
}
_PYTHON_STATEMENTS = frozenset({"expression_statement", "return_statement"})

# How a field read off a name is spelled, as the node kind and the field holding the property.
# ast-grep refuses a kind the grammar does not have rather than matching nothing, so this cannot
# be one search over both spellings.
_READS = {"python": ("attribute", "attribute")}


class UnsupportedChangeKind(ValueError):
    """A change kind this generator cannot invert.

    Raised rather than answered with an unmutated tree. A tree nothing broke labels every site
    unaffected while the scorer's findings say otherwise, which reads as a pipeline that
    hallucinates rather than as a generator that declined.
    """


class MutationPair(BaseModel):
    """One mutated repository and the ground truth for it.

    `sources` is the whole tree, mutated where mutated: a caller handed only the edited files
    has a checkout that no longer builds. `unreachable` names targets the mutation could not
    attach to, which are labelled unaffected -- the honest answer, since nothing broke them.
    """

    sources: dict[str, str]
    labels: list[BindingLabel]
    unreachable: tuple[str, ...] = ()


def generate_pair(  # lint-dead-links: allow - the scorer that consumes these pairs is the next task; `binding.py` takes labels and nothing yet feeds it
    sources: Mapping[str, str],
    change: VendorChange,
    sites: Sequence[CallSite],
    targets: Sequence[str],
) -> MutationPair:
    """A repository the change genuinely breaks at `targets`, and the label that says so.

    Pure: sources in, sources out. Nothing here reads a file, opens a connection, or consults
    the pipeline. The caller decides which sites to break, because which mutations exist in a
    corpus is a property of the corpus and not a default this module should be choosing.
    """
    if change.kind not in SUPPORTED_KINDS:
        raise UnsupportedChangeKind(
            f"{change.kind} is not a kind this generator can invert; supported: "
            f"{', '.join(sorted(SUPPORTED_KINDS))}"
        )

    field = changed_field(change)
    if not field:
        raise ValueError(
            f"change {change.id} names no field, so there is nothing to write into a call site"
        )

    by_id = {site.id: site for site in sites}
    missing = [name for name in targets if name not in by_id]
    if missing:
        raise ValueError(f"no call site in this tree is named {', '.join(missing)}")

    mutated = dict(sources)
    broken: list[str] = []
    unreachable: list[str] = []

    for site in sites:
        language = _language_for(site.path)
        if language is None:
            continue
        if _already_depends(mutated[site.path], change, site, field, language):
            raise ValueError(
                f"call site {site.id} already depends on `{field}`, so a label for it would "
                f"not be derived from this mutation"
            )

    # Sorted, so two runs over one input apply the same edits in the same order and a file
    # holding two targets comes out byte-identical rather than merely equivalent.
    for site_id in sorted(set(targets)):
        site = by_id[site_id]
        language = _language_for(site.path)
        if language is None:
            unreachable.append(site_id)
            continue

        edited = _mutate(mutated[site.path], change, site, field, language)
        if edited is None:
            unreachable.append(site_id)
            continue

        mutated[site.path] = edited
        broken.append(site_id)

    return MutationPair(
        sources=mutated,
        labels=[
            BindingLabel(
                call_site_id=site.id or "",
                vendor_change_id=change.id or "",
                affected=site.id in broken,
                # Where the evidence for this dependency lives. A mutation writes it into the
                # source, so a binder that misses it missed something statically visible.
                rung="static" if site.id in broken else "unresolved",
            )
            for site in sites
        ],
        unreachable=tuple(sorted(unreachable)),
    )


def depends_on_change(  # lint-dead-links: allow - the audit half of the generator above, wired when its scorer is
    sources: Mapping[str, str], change: VendorChange, site: CallSite
) -> bool:
    """Whether one call site in one tree carries the dependency `change` removes.

    Read from the source rather than from the edit record, which is what makes it worth
    asserting a label against: `generate_pair` labels from what it edited, this answers what
    the tree now says, and a disagreement between them is a generator bug rather than a
    tautology. It is not a binder -- it answers about one named call site against one field,
    and cannot say which sites an operation change affects.
    """
    field = changed_field(change)
    language = _language_for(site.path)
    if not field or language is None:
        return False
    return _already_depends(sources[site.path], change, site, field, language)


def _already_depends(
    source: str, change: VendorChange, site: CallSite, field: str, language: str
) -> bool:
    root = SgRoot(source, language).root()
    call = _call_at(root, site.line, site.col, language)
    if call is None:
        return False

    if change.kind in REQUEST_KINDS:
        argument = _object_argument(call, language)
        if argument is not None and field in _declared_keys(argument):
            return True
        # Python's ordinary spelling. A keyword argument names a request field exactly as an
        # entry in a literal does, and the indexer records both, so both have to be checked or a
        # site already passing the field would be labelled from a mutation that did not make it.
        return language == "python" and field in _keyword_names(call)

    binding = _result_binding(call, language)
    if binding is None:
        return False
    name, statement = binding
    return _reads_field(statement.parent() or statement, name, field, language)


def _mutate(
    source: str, change: VendorChange, site: CallSite, field: str, language: str
) -> str | None:
    """The source with the call at `site` made to depend on `field`, or None if it cannot be.

    None rather than an exception: a call the mutation cannot attach to is ordinary in a real
    repository -- a response nobody binds, a call passing no object -- and the caller records it
    as a target it did not break rather than abandoning the whole tree.
    """
    root = SgRoot(source, language).root()
    call = _call_at(root, site.line, site.col, language)
    if call is None:
        return None

    if change.kind in REQUEST_KINDS:
        return _insert_property(source, call, field, language)
    return _insert_response_guard(source, call, field, language)


def _insert_property(source: str, call, field: str, language: str = "typescript") -> str | None:
    """`field` written into the call's object argument, as its first entry.

    First rather than last because a trailing entry has to reason about whether the object
    already ends with a comma, and the repair this inverts -- `omit_argument_at` -- takes the
    pair with its following separator, so a leading insertion is the one it removes exactly.
    """
    argument = _object_argument(call, language)
    if argument is None:
        return _insert_keyword_argument(source, call, field) if language == "python" else None

    span = argument.range()
    entries = [child for child in argument.children() if child.kind() == "pair"
               or child.kind() == "shorthand_property_identifier"]
    opening = span.start.index + 1
    key = f'"{field}"' if language == "python" else field
    if entries:
        return f"{source[:opening]} {key}: {MUTATION_LITERAL},{source[opening:]}"
    return f"{source[:opening]} {key}: {MUTATION_LITERAL} {source[opening:]}"


def _insert_keyword_argument(source: str, call, field: str) -> str | None:
    """`field` written into a Python call as its first keyword argument.

    Python has no object literal at most call sites: request fields are keyword arguments, which
    is what `sync.index.python_lang` records and therefore what a break has to be written as. A
    mutation into a dict literal would produce a dependency the indexer reads and the SDK does
    not accept, and one the repair primitives could not invert.

    First rather than last, for the reason the literal insertion gives: a trailing entry has to
    reason about the trailing comma, and a leading one does not.
    """
    arguments = call.field("arguments")
    if arguments is None:
        return None
    span = arguments.range()
    opening = span.start.index + 1
    existing = [child for child in arguments.children()
                if child.kind() not in ("(", ")", ",")]
    separator = ", " if existing else ""
    return f"{source[:opening]}{field}={MUTATION_LITERAL}{separator}{source[opening:]}"


def _insert_response_guard(source: str, call, field: str, language: str = "typescript") -> str | None:
    """A guard reading `field` off the call's result, appended to the statement binding it.

    A response property is depended upon by being read, and the shortest realistic read is the
    check a caller writes anyway. A call whose result is never bound has nothing to read it off,
    which is the `None` case.

    **On the statement's own line, never on a new one.** `upsert_call_site` keys a call site's
    identity on line and column, so a guard occupying a line renames every call below it in the
    file: the label then addresses a row the mutated tree does not hold, `score.py` refuses the
    pair as `displaced-label`, and a file with several calls can carry no response-side pair at
    all. Two of the twelve frozen-corpus specifications were refused for exactly that. Widening
    the binding forms below without this would have converted unreachable targets into refused
    pairs rather than into labelled positives.

    Keeping identity stable here rather than changing what identity is keyed on is deliberate.
    The key belongs to `sync.graph` and every stage depends on it; a benchmark that needed the
    production key changed in order to score itself would be measuring a pipeline nobody runs.
    """
    binding = _result_binding(call, language)
    if binding is None:
        return None
    name, statement = binding

    end = statement.range().end.index
    if language == "python":
        # `;` joins two simple statements on one line, and `assert` is a simple statement --
        # which is what keeps this off a new line without reasoning about indentation at all. A
        # Python guard written as an `if` would have to be indented to match the block it lands
        # in, and getting that wrong is a syntax error rather than a shorter diff.
        return f"{source[:end]}; assert {name}.{field} is not None{source[end:]}"
    # A statement the grammar ends without a semicolon was terminated by a newline, and appending
    # to that line would splice the guard onto the expression instead of following it.
    separator = "" if source[:end].rstrip().endswith(";") else ";"
    guard = f"{separator} if ({name}.{field} === undefined) throw new Error('{field} missing');"
    return source[:end] + guard + source[end:]


def _language_for(path: str) -> str | None:
    """The language this generator can build a pair in, or None.

    See `_MUTABLE_LANGUAGES`. This is not `sync.route.templates.language_for` and must not become
    it: that one is the router's answer to whether a codemod can patch a file, and the two
    questions have different answers for Python.
    """
    return _MUTABLE_LANGUAGES.get(Path(path).suffix)


def _call_at(root, line: int, col: int, language: str = "typescript"):
    """The call expression the indexer recorded at this position.

    An exact start match only. `sync.route.templates._call_at` accepts a merely-containing call
    as a fallback because a patch that no-ops reads as "nothing to fix"; here a position that
    does not name a call is a broken input to a benchmark, and guessing which call was meant
    would put the label on a site nobody chose.
    """
    matches = [
        call for call in root.find_all(kind=_CALL_KIND.get(language, "call_expression"))
        if call.range().start.line + 1 == line and call.range().start.column == col
    ]
    if not matches:
        return None
    return max(matches, key=lambda call: (
        _object_argument(call, language) is not None,
        call.range().end.index - call.range().start.index,
    ))


def _object_argument(call, language: str = "typescript"):
    """The literal carrying this call's request fields, if it passes one.

    `object` in TypeScript and `dictionary` in Python. Python usually passes keyword arguments
    instead and then there is no literal at all, which is why the request path below has a second
    branch rather than treating `None` here as "cannot mutate".
    """
    arguments = call.field("arguments")
    if arguments is None:
        return None
    wanted = _MAPPING_KIND.get(language, "object")
    for child in arguments.children():
        if child.kind() == wanted:
            return child
    return None


def _keyword_names(call) -> set[str]:
    """Every keyword argument a Python call names."""
    arguments = call.field("arguments")
    if arguments is None:
        return set()
    names: set[str] = set()
    for child in arguments.children():
        if child.kind() != "keyword_argument":
            continue
        name = child.field("name")
        if name is not None:
            names.add(name.text())
    return names


def _declared_keys(argument) -> set[str]:
    """Every key the mapping literal names, across both grammars.

    JavaScript spells an entry `pair` or `shorthand_property_identifier`; Python spells it `pair`
    with a string key. Only a literal key counts in either -- a computed one names no field
    anyone can compare against.
    """
    keys: set[str] = set()
    for child in argument.children():
        if child.kind() == "shorthand_property_identifier":
            keys.add(child.text())
        elif child.kind() == "pair":
            key = child.field("key")
            if key is not None:
                keys.add(key.text().strip("'\""))
    return keys


def _result_binding(call, language: str = "typescript"):
    """The identifier a call's result is bound to, with the statement doing the binding.

    Two forms, and a declaration is only the more obvious one. `intent = await stripe
    .paymentIntents.create(...)` binds the result to a name a guard can read exactly as `const`
    does; the frozen corpus meets it four times, in `furever` and in `turbo`, both writing into a
    variable declared further up.

    `None` when the result is not bound to a plain name, and the two shapes that reach it are
    findings rather than gaps. A call whose result is discarded -- `await stripe.paymentIntents
    .create({...});` -- reads no response field, so a removed response property does not break it
    and `unaffected` is the correct label. A call whose result is returned puts whatever reads
    the field outside this function, where an insertion cannot see it; binding it to a name first
    would be a restructuring, and the label would then describe that rather than a dependency the
    vendor's change breaks. Five of the corpus's eleven unreachable targets are the first, two are
    the second.
    """
    if language == "python":
        return _python_result_binding(call)

    node = call
    while node is not None and node.kind() not in _STATEMENT_KINDS:
        node = node.parent()
    if node is None:
        return None

    if node.kind() in ("lexical_declaration", "variable_declaration"):
        for child in node.children():
            if child.kind() != "variable_declarator":
                continue
            name = child.field("name")
            if name is not None and name.kind() == "identifier":
                return name.text(), node
        return None

    if node.kind() == "expression_statement":
        for child in node.children():
            if child.kind() != "assignment_expression":
                continue
            # A plain name only. `order.intent = await ...` binds a property, and a guard reading
            # it would depend on the object outliving the statement rather than on the call.
            target = child.field("left")
            if target is not None and target.kind() == "identifier":
                return target.text(), node
    return None


def _python_result_binding(call):
    """The name a Python call's result is bound to, with the statement holding the binding.

    Two binders and the walrus is the second. `sync.index.python_lang` records reads through
    both, so a shape the binder can find and this cannot break would be a labelled negative that
    is really a gap. The walk climbs to the binder and then to the statement, because the guard
    is appended to the statement rather than to the expression -- `charge := create(...)` sits
    inside a condition, and splicing after the expression would land inside it.
    """
    node = call
    while node is not None:
        form = _BINDING_FORMS["python"].get(node.kind())
        if form is not None:
            name_field, value_field = form
            target = node.field(name_field)
            if target is None or target.kind() != "identifier":
                return None
            statement = node
            while statement is not None and statement.kind() not in _PYTHON_STATEMENTS:
                statement = statement.parent()
            return (target.text(), statement) if statement is not None else None
        if node.kind() in _PYTHON_STATEMENTS:
            return None
        node = node.parent()
    return None


def _reads_field(scope, name: str, field: str, language: str = "typescript") -> bool:
    """Whether anything in `scope` reads `name.field`.

    Scoped to the statement's own parent -- the function body holding the call -- rather than to
    the file. A different function reading the same field off its own result is a different call
    site's dependency, and counting it here would refuse a tree that is perfectly usable.
    """
    kind, property_field = _READS.get(language, ("member_expression", "property"))
    for member in scope.find_all(kind=kind):
        target = member.field("object")
        property_node = member.field(property_field)
        if target is None or property_node is None:
            continue
        if target.text() == name and property_node.text() == field:
            return True
    return False

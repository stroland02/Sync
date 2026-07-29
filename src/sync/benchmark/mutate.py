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

from ast_grep_py import SgRoot
from pydantic import BaseModel

from sync.benchmark.binding import BindingLabel
from sync.core import CallSite, VendorChange
from sync.route.templates import language_for
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
        language = language_for(site.path)
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
        language = language_for(site.path)
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
    language = language_for(site.path)
    if not field or language is None:
        return False
    return _already_depends(sources[site.path], change, site, field, language)


def _already_depends(
    source: str, change: VendorChange, site: CallSite, field: str, language: str
) -> bool:
    root = SgRoot(source, language).root()
    call = _call_at(root, site.line, site.col)
    if call is None:
        return False

    if change.kind in REQUEST_KINDS:
        argument = _object_argument(call)
        return argument is not None and field in _declared_keys(argument)

    binding = _result_binding(call)
    if binding is None:
        return False
    name, statement = binding
    return _reads_field(statement.parent() or statement, name, field)


def _mutate(
    source: str, change: VendorChange, site: CallSite, field: str, language: str
) -> str | None:
    """The source with the call at `site` made to depend on `field`, or None if it cannot be.

    None rather than an exception: a call the mutation cannot attach to is ordinary in a real
    repository -- a response nobody binds, a call passing no object -- and the caller records it
    as a target it did not break rather than abandoning the whole tree.
    """
    root = SgRoot(source, language).root()
    call = _call_at(root, site.line, site.col)
    if call is None:
        return None

    if change.kind in REQUEST_KINDS:
        return _insert_property(source, call, field)
    return _insert_response_guard(source, call, field)


def _insert_property(source: str, call, field: str) -> str | None:
    """`field` written into the call's object argument, as its first entry.

    First rather than last because a trailing entry has to reason about whether the object
    already ends with a comma, and the repair this inverts -- `omit_argument_at` -- takes the
    pair with its following separator, so a leading insertion is the one it removes exactly.
    """
    argument = _object_argument(call)
    if argument is None:
        return None

    span = argument.range()
    entries = [child for child in argument.children() if child.kind() == "pair"
               or child.kind() == "shorthand_property_identifier"]
    opening = span.start.index + 1
    if entries:
        return f"{source[:opening]} {field}: {MUTATION_LITERAL},{source[opening:]}"
    return f"{source[:opening]} {field}: {MUTATION_LITERAL} {source[opening:]}"


def _insert_response_guard(source: str, call, field: str) -> str | None:
    """A guard reading `field` off the call's result, inserted after the statement binding it.

    A response property is depended upon by being read, and the shortest realistic read is the
    check a caller writes anyway. A call whose result is never bound has nothing to read it off,
    which is the `None` case.
    """
    binding = _result_binding(call)
    if binding is None:
        return None
    name, statement = binding

    span = statement.range()
    line_start = source.rfind("\n", 0, span.start.index) + 1
    indent = source[line_start:span.start.index]
    if indent.strip():
        indent = ""

    guard = (
        f"\n{indent}if ({name}.{field} === undefined) {{\n"
        f"{indent}  throw new Error('{field} missing');\n"
        f"{indent}}}"
    )
    return source[:span.end.index] + guard + source[span.end.index:]


def _call_at(root, line: int, col: int):
    """The call expression the indexer recorded at this position.

    An exact start match only. `sync.route.templates._call_at` accepts a merely-containing call
    as a fallback because a patch that no-ops reads as "nothing to fix"; here a position that
    does not name a call is a broken input to a benchmark, and guessing which call was meant
    would put the label on a site nobody chose.
    """
    matches = [
        call for call in root.find_all(kind="call_expression")
        if call.range().start.line + 1 == line and call.range().start.column == col
    ]
    if not matches:
        return None
    return max(matches, key=lambda call: (
        _object_argument(call) is not None,
        call.range().end.index - call.range().start.index,
    ))


def _object_argument(call):
    arguments = call.field("arguments")
    if arguments is None:
        return None
    for child in arguments.children():
        if child.kind() == "object":
            return child
    return None


def _declared_keys(argument) -> set[str]:
    """Every key the object literal names, in either of JavaScript's two spellings."""
    keys: set[str] = set()
    for child in argument.children():
        if child.kind() == "shorthand_property_identifier":
            keys.add(child.text())
        elif child.kind() == "pair":
            key = child.field("key")
            if key is not None:
                keys.add(key.text().strip("'\""))
    return keys


def _result_binding(call):
    """The identifier a call's result is assigned to, with the statement doing it.

    `None` when the result is not bound to a plain name: an awaited call thrown away, a result
    destructured into several names, a call used inline. Each is a site a response-side
    mutation cannot attach to, and none is an error.
    """
    node = call
    while node is not None and node.kind() not in _STATEMENT_KINDS:
        node = node.parent()
    if node is None or node.kind() not in ("lexical_declaration", "variable_declaration"):
        return None

    for child in node.children():
        if child.kind() != "variable_declarator":
            continue
        name = child.field("name")
        if name is not None and name.kind() == "identifier":
            return name.text(), node
    return None


def _reads_field(scope, name: str, field: str) -> bool:
    """Whether anything in `scope` reads `name.field`.

    Scoped to the statement's own parent -- the function body holding the call -- rather than to
    the file. A different function reading the same field off its own result is a different call
    site's dependency, and counting it here would refuse a tree that is perfectly usable.
    """
    for member in scope.find_all(kind="member_expression"):
        target = member.field("object")
        property_node = member.field("property")
        if target is None or property_node is None:
            continue
        if target.text() == name and property_node.text() == field:
            return True
    return False

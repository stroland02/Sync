"""What tree-sitter's TypeScript grammar says, stated once for every rule that reads it.

`symbols_typescript.py` and `symbols_speakeasy.py` are separate rules and stay separate. Their
docstrings price four differences -- what a class is, what a mount is, how a class is identified,
and whether an operation is readable from one file -- and every one of those is a fact about a
generator's emission. This module holds the facts that are **not**: the grammar is one object, it
answers both rules identically, and nothing here may know a generator's name.

Why the line is drawn at the grammar and not wider
--------------------------------------------------
A fact stated here takes a `Node`. `_module_key`, `_specifier_target` and `_source_files` are also
written identically in both rules, and they stay there: they take a `Path`, they state where a
checkout keeps its files rather than what the parser makes of one, and each embeds a rule's own
decision about what to follow. Their divergence costs a mount that is *missing* -- and for a
specifier naming a module inside the checkout, one the decline channel names. Divergence here costs
a route that is **wrong**, which resolves.

That is not a hypothetical ordering. `eb50e91` copied one rule's route reader into the other's with
its docstring's escape sentence intact; `80e2e08` made that sentence true nine hours later, on a
branch the copy is not descended from. A route written `"/v4/aliases\\/{idOrAlias}"` then read as
`/v4/aliases`, which is the route another method of the same resource sends -- so the truncation did
not lose a binding, it made a second one to an operation the specification declares, where the
cross-check cannot contradict it.

One more helper was checked against the same question and left out on purpose: `_comparable` is
byte-identical in both readers today -- `_route(http_method, path)` followed by the same
`_PARAMETER.sub("{}", route)` -- which makes it look like exactly the kind of copy this module
exists to end. It stays local anyway, for two reasons neither of which is "it happens to differ
right now". First, it takes no `Node`; it reduces a method and a path that have already left the
tree, so it is not a fact about what tree-sitter parsed, and the rule this module holds to -- stated
once, below -- is a rule about `Node` facts. Second, the two readers do not agree on what the
identical code is *for*, and each says so in its own docstring rather than here: one needs the
reduction to compare at all, the other keeps it measured inert and documents the case that would
make it load-bearing too. A change to one reader's reason is not a change to the other's, so
coupling the implementation would be coupling two answers that are only accidentally the same
sentence today. The duplication is made visible instead of extracted:
`tests/test_parameter_reduction.py::test_both_flavours_reduce_a_parameter_the_same_way` asserts the
two patterns and the two behaviours agree, and goes red the day a copy drifts without an extraction
being taken.

The escape split is the fact the rest rests on
----------------------------------------------
This grammar ends a `string_fragment` at every `escape_sequence`, in a plain string and in a
template alike. There is no fragment worth preferring: the first is a prefix of what the source
says and the joined ones are the literal with its escapes deleted. So a literal carrying one is
declined whole, and `tests/test_typescript_grammar.py` holds the split itself as a measurement --
a tree-sitter upgrade that changed it would make every decline downstream the wrong answer.

Decoding is strict, everywhere and on purpose. A real SDK carries identifiers and comments in any
language, and a lenient decode turns one of them into a route or a class name that silently differs
from what the file says. `tests/test_source_decoding.py` holds this level with the two readers over
a customer's own repository, which is where the asymmetry was found.
"""

from __future__ import annotations

from tree_sitter import Node


def walk(node: Node):
    """The node and every descendant, in source order."""
    yield node
    for child in node.children:
        yield from walk(child)


def node_text(node: Node, source: bytes) -> str:
    """A node's own bytes as text, decoded strictly."""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def carries_escape(node: Node) -> bool:
    """Whether a literal holds an escape this grammar split it at.

    Asked of a `string` and of a `template_string` both, which is why it is a fact of its own
    rather than a line inside `string_literal`: the tagged-template reader has the same problem
    and had the same defect.
    """
    return any(child.type == "escape_sequence" for child in node.children)


def string_literal(node: Node, source: bytes) -> str | None:
    """The text of a plain string literal, or `None` where the source states none readably.

    The fragment rather than the quoted text, so an empty string reads as absent rather than as a
    value -- both callers of this guard on truthiness, and a route of `""` would occupy the key the
    real operation takes.
    """
    if node.type != "string":
        return None
    if carries_escape(node):
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return node_text(child, source)
    return None


def extends_names(node: Node, source: bytes) -> set[str]:
    """The classes a declaration extends.

    The `extends` clause only. An `implements` clause names an interface, which cannot be the base
    either rule anchors on, and reading the whole heritage would let one be mistaken for it.
    """
    names: set[str] = set()
    for child in node.children:
        if child.type != "class_heritage":
            continue
        for inner in walk(child):
            if inner.type != "extends_clause":
                continue
            for named in walk(inner):
                if named.type in ("identifier", "property_identifier", "type_identifier"):
                    names.add(node_text(named, source))
    return names

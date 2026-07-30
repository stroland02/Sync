"""The facts about tree-sitter's TypeScript grammar, and that both readers state them once.

`symbols_typescript.py` and `symbols_speakeasy.py` split for four reasons their module docstrings
price: what a class is, what a mount is, how a class is identified, and whether an operation is
readable from one file. None of those is a fact about the grammar. The grammar is one object and
says one thing to both readers, and the two places it was written down twice are where a fix
landed on one and not the other.

That happened. `eb50e91` copied `_plain_route` into `_string_literal`, false docstring sentence
included; `80e2e08` fixed the original nine hours later on a branch the copy is not descended from.
The defect it left was not a missing route -- `pathToFunc("/v4/aliases\\/{idOrAlias}")` read as
`/v4/aliases`, which is the route a *different* method of the same resource sends, so the
cross-check could not contradict it.

Two kinds of test are here and they answer different questions:

- **What the grammar does**, measured rather than assumed. The escape split is the fact both
  readers' declines rest on, and a tree-sitter upgrade that changed it would make three docstrings
  false at once.
- **That one edit reaches both readers.** That is the property the extraction exists for, and it is
  the one a shared module can lose silently -- a reader that quietly grew its own copy again would
  keep every other test in this file green.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.signals.generated import symbols_speakeasy, symbols_typescript, typescript_grammar

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SPEAKEASY_SDK = FIXTURES / "vercel_typescript"

_TS_LANGUAGE = Language(tsts.language_typescript())

_ROUTE_LITERAL = '"/v4/aliases/{idOrAlias}"'
_REQUEST_MODULE = "funcs/aliasesGetAlias.ts"


# --- what the grammar does, measured -------------------------------------------------------


def test_this_grammar_splits_a_string_at_every_escape():
    """The measurement three docstrings rest on, held here so it stops being an assumption.

    `'/v1/a\\u0041b'` is one literal and parses as `string_fragment`, `escape_sequence`,
    `string_fragment`. So the first fragment is a *prefix* of what the source says, and a reader
    taking it answers a route the source does not state. The assertion is on the shape of the
    children rather than on any reader, because it is the grammar's behaviour that makes every
    decline below the right answer.
    """
    node = _first_string("const x = '/v1/a\\u0041b';")

    assert [child.type for child in node.children] == [
        "'", "string_fragment", "escape_sequence", "string_fragment", "'",
    ]
    assert typescript_grammar.node_text(node.children[1], b"const x = '/v1/a\\u0041b';") == "/v1/a"


def test_a_literal_carrying_an_escape_is_declined_rather_than_truncated():
    """The decline the split forces, and the one defect this module was extracted to end.

    Whole rather than partial. There is no fragment to prefer: reading the first answers a prefix
    and joining them answers the literal with the escape deleted, and both are routes the source
    does not state.
    """
    assert typescript_grammar.string_literal(_first_string("const x = '/v1/a\\u0041b';"), b"") is None


def test_a_plain_literal_reads_as_the_text_between_its_quotes():
    """The positive control. Without it every assertion here is satisfied by a reader that
    declines everything, which is the shape a decline test cannot tell from a working one."""
    source = b"const x = '/v1/models';"

    assert typescript_grammar.string_literal(_first_string(source), source) == "/v1/models"


def test_an_empty_literal_reads_as_absent_rather_than_as_a_value():
    """A `string` node with no `string_fragment` child at all.

    The alternative is a value of `""`, which both readers' callers would carry: a route of the
    empty path, or a verb of the empty string. Absent is the honest answer -- the source states no
    value -- and it is what lets both callers guard on truthiness.
    """
    source = b"const x = '';"

    assert typescript_grammar.string_literal(_first_string(source), source) is None


def test_a_node_that_is_not_a_string_is_not_read_as_one():
    """A template literal reaches this from both readers -- Stainless through the argument of a
    request method, Speakeasy through `pathToFunc`. Reading its fragments would answer the route
    with its parameter segments dropped rather than templated."""
    source = b"const x = `/v4/aliases/${idOrAlias}`;"
    template = next(
        node for node in typescript_grammar.walk(_parse(source)) if node.type == "template_string"
    )

    assert typescript_grammar.string_literal(template, source) is None


def test_the_extends_clause_is_read_and_the_implements_clause_is_not():
    """Both readers anchor on a base class name, and an `implements` clause names an interface.

    Reading the whole heritage would let an interface be mistaken for the base -- which for
    Speakeasy makes every class implementing an interface called `ClientSDK` a candidate root, and
    for Stainless makes one a resource.
    """
    source = b"class Models extends APIResource implements Listable {}"
    declaration = next(
        node for node in typescript_grammar.walk(_parse(source)) if node.type == "class_declaration"
    )

    assert typescript_grammar.extends_names(declaration, source) == {"APIResource"}


def test_walking_a_tree_yields_the_root_and_every_descendant():
    """Both readers find their anchors by sweeping the whole tree rather than by descending named
    fields, so a walk that skipped the root -- or an unnamed child -- would lose a class declared
    at the top of a file."""
    source = b"class Models extends APIResource {}"
    root = _parse(source)
    walked = list(typescript_grammar.walk(root))

    assert walked[0] is root
    assert {node.type for node in walked} >= {"class_declaration", "class_heritage", "{", "}"}


# --- that one edit reaches both readers ------------------------------------------------------


def test_one_edit_to_the_escape_rule_moves_both_readers(tmp_path, monkeypatch):
    """The property the extraction exists for, asserted where it can be lost.

    `carries_escape` is patched to the answer it gave before `80e2e08` -- that no literal carries
    an escape -- and both readers must go back to truncating. A reader that grew its own copy again
    would keep this green on its own side and red here, which is the only place the copy shows.

    What the truncation produces is why this is the defect rather than an inconvenience. Speakeasy
    reads `/v4/aliases`, which `aliases.listAliases` also sends, so the SDK yields two symbols
    claiming one declared operation and `unknown_to_spec` has nothing to report. Stainless reads
    `/v1/a` for a source that says `/v1/aAb`.
    """
    stainless = _stainless_sdk(
        tmp_path / "stainless", "  plain() { return this._client.get('/v1/a\\u0041b', {}); }"
    )
    speakeasy = _speakeasy_sdk(tmp_path / "speakeasy")

    assert "models.plain" not in _map(symbols_typescript, stainless)
    assert "aliases.getAlias" not in _map(symbols_speakeasy, speakeasy)

    monkeypatch.setattr(typescript_grammar, "carries_escape", lambda node: False)

    assert _map(symbols_typescript, stainless)["models.plain"] == ("GET", "/v1/a")
    assert _map(symbols_speakeasy, speakeasy)["aliases.getAlias"] == ("GET", "/v4/aliases")


def test_the_readers_are_otherwise_unmoved_by_that_edit(tmp_path, monkeypatch):
    """The control. Both trees must read the same map either way apart from the one literal under
    test, or the assertions above are satisfied by a patch that broke the readers outright."""
    stainless = _stainless_sdk(
        tmp_path / "stainless", "  plain() { return this._client.get('/v1/a\\u0041b', {}); }"
    )
    speakeasy = _speakeasy_sdk(tmp_path / "speakeasy")
    before = (_map(symbols_typescript, stainless), _map(symbols_speakeasy, speakeasy))

    monkeypatch.setattr(typescript_grammar, "carries_escape", lambda node: False)
    after = (_map(symbols_typescript, stainless), _map(symbols_speakeasy, speakeasy))

    assert before[0] == {"models.list": ("GET", "/v1/models")}
    assert set(after[0]) - set(before[0]) == {"models.plain"}
    assert set(after[1]) - set(before[1]) == {"aliases.getAlias"}
    assert len(before[1]) == 14


def test_the_shared_module_states_no_fact_about_any_generator():
    """What keeps this from becoming the framework the split exists to avoid.

    The four differences both reader docstrings price are generator shape, and a shared module that
    started naming one would be re-answering them in a place neither reader owns. Nothing here may
    know a generator's name, its base classes, or its helpers -- so the day a fifth fact is tempted
    in, this says whether it belongs.
    """
    source = Path(typescript_grammar.__file__).read_text(encoding="utf-8")

    assert not typescript_grammar.__name__.endswith("symbols")
    for named in (
        symbols_typescript.GENERATOR,
        symbols_speakeasy.GENERATOR,
        "APIResource",
        "ClientSDK",
        "pathToFunc",
        "_createRequest",
    ):
        assert named not in source, f"{named} is a generator's fact and does not belong here"


# --- helpers -----------------------------------------------------------------------------------


def _parse(source: bytes | str) -> Node:
    if isinstance(source, str):
        source = source.encode("utf-8")
    return Parser(_TS_LANGUAGE).parse(source).root_node


def _first_string(source: bytes | str) -> Node:
    return next(node for node in typescript_grammar.walk(_parse(source)) if node.type == "string")


def _map(reader, root: Path) -> dict[str, tuple[str, str]]:
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in reader.extract_symbols(root)[0]
    }


def _stainless_sdk(root: Path, *methods: str) -> Path:
    """Three files of the shape the Stainless TypeScript rule reads, `models.list` always readable.

    The same shape `test_extracted_symbols_typescript.py` builds, and hand-written for the reason
    it gives: Stainless does not emit an escaped route, so there is nothing in the committed tree
    to corrupt into one without making the corruption the fixture.
    """
    files = {
        "client.ts": (
            "import * as API from './resources/index';\n"
            "\n"
            "export class Anthropic extends BaseAnthropic {\n"
            "  models: API.Models = new API.Models(this);\n"
            "}\n"
        ),
        "resources/index.ts": "export { Models } from './models';\n",
        "resources/models.ts": (
            "import { APIResource } from '../core/resource';\n"
            "\n"
            "export class Models extends APIResource {\n"
            + "\n".join(["  list() { return this._client.get('/v1/models', {}); }", *methods])
            + "\n}\n"
        ),
    }
    for relative, body in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def _speakeasy_sdk(root: Path) -> Path:
    """The committed Vercel tree with one route literal carrying an escape.

    An edit to the vendor tree rather than a hand-built SDK, for the reason
    `test_speakeasy_reader_declines.py` states: the fourteen other symbols are the control that
    says the tree still parses, still roots and still reads.
    """
    shutil.copytree(SPEAKEASY_SDK, root)
    target = root / _REQUEST_MODULE
    text = target.read_text(encoding="utf-8")
    assert text.count(_ROUTE_LITERAL) == 1, "the route literal this edit needs is not unique"
    target.write_text(
        text.replace(_ROUTE_LITERAL, '"/v4/aliases\\/{idOrAlias}"'), encoding="utf-8"
    )
    return root

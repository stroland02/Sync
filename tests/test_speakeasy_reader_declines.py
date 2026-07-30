"""Every input the Speakeasy reader declines on, and what the decline costs its caller.

`test_extracted_symbols_speakeasy.py` covers what this rule *reads*. This file covers what it
refuses, which is the other half and the half a coverage number cannot describe: eleven statements
in `symbols_speakeasy.py` were unexecuted by the whole suite, every one of them a refusal.

Two costs, and they are not the same cost
-----------------------------------------
`_comparable` is called only from `report_extraction`, and `operation_for_symbol` builds its
`OperationRef` from the SDK's own route verbatim -- established by M3-W96. So a decline in the
comparison path costs a **measurement** and a decline in the extraction path costs a **binding**:
a symbol a customer writes that resolves to no operation, against which no finding can be raised
however breaking the vendor's change.

Every statement covered here is in the extraction path.

Why the inputs are edits to the committed tree rather than hand-built SDKs
-------------------------------------------------------------------------
Each test copies `sdk_sources/vercel_typescript` and substitutes one span of one file. The other
fourteen symbols are then the control: they say the tree still parses, still roots, and still
reads, so the one symbol that went missing went missing for the reason under test. A hand-built
two-file SDK would prove only that the builder knew what to write.

`_edit` asserts its target text occurs exactly once. A substitution that silently matched nothing
would leave the test asserting against the unmodified tree, which passes for every wrong reason.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from sync.signals.generated.symbols import read_spec_operations
from sync.signals.generated.symbols_speakeasy import extract_symbols, report_extraction

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "vercel_typescript"
SPEC_OPERATIONS = FIXTURES / "vercel_spec_operations.json"

_ROUTE_LITERAL = '"/v4/aliases/{idOrAlias}"'
_REQUEST_MODULE = "funcs/aliasesGetAlias.ts"
_CLASS_MODULE = "sdk/aliases.ts"
_CLIENT_MODULE = "sdk/sdk.ts"


def _copy(tmp_path: Path) -> Path:
    """The committed tree, copied byte for byte.

    Bytes rather than text: these are vendor source files, and a copy that decoded them would be
    asserting something about this machine's codepage.
    """
    root = tmp_path / "sdk"
    shutil.copytree(SDK, root)
    return root


def _edit(root: Path, module: str, old: str, new: str) -> None:
    target = root / module
    text = target.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{module}: {old!r} occurs {text.count(old)} times, not once"
    target.write_text(text.replace(old, new), encoding="utf-8")


def _symbols(root: Path) -> dict[str, tuple[str, str]]:
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in extract_symbols(root)[0]
    }


def _declines(root: Path) -> tuple[str, ...]:
    return extract_symbols(root)[1]


def _stage_the_wrapper_module(root: Path) -> None:
    """Stage the one module every request-module import reaches that this fixture leaves out.

    `unwrapAsync` comes from `../types/fp.js`, which the twenty committed files do not include, so
    every method of every resource has one absent delegation target whatever else is wrong with it.
    Several declines below are visible in the committed tree only because of that, which is a fact
    about the fixture and not about the rule. Staging a stub makes the checkout complete for the
    purpose of the delegation walk, and is what the silence tests are measured against.
    """
    (root / "types").mkdir(exist_ok=True)
    (root / "types" / "fp.ts").write_text(
        "export function unwrapAsync<T>(value: T): T {\n  return value;\n}\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------------------------
# The route literal, and the one defect in this module: an escape used to truncate it
# --------------------------------------------------------------------------------------------


def test_a_route_literal_carrying_an_escape_is_declined_whole(tmp_path):
    """This grammar splits a string at every escape, so reading a fragment reads a prefix.

    `"/v4/aliases\\/{idOrAlias}"` parses as fragment `/v4/aliases`, an `escape_sequence`, then
    fragment `{idOrAlias}`. Taking the first fragment answers `/v4/aliases` -- which is not a
    route this SDK sends, and is a route it sends *from somewhere else*: `aliases.listAliases`.
    So the truncation does not merely lose a binding, it produces a second symbol claiming a real
    declared operation, and `unknown_to_spec` cannot see it because the route is declared.

    `symbols_typescript.py:_plain_route` declines an escape-carrying literal whole for exactly
    this reason and states it in its docstring. This rule's `_string_literal` claimed the same
    protection and did not have it.
    """
    root = _copy(tmp_path)
    _edit(root, _REQUEST_MODULE, _ROUTE_LITERAL, '"/v4/aliases\\/{idOrAlias}"')

    extracted = _symbols(root)

    assert "aliases.getAlias" not in extracted
    assert extracted["aliases.listAliases"] == ("GET", "/v4/aliases")
    assert [
        symbol for symbol, route in extracted.items() if route == ("GET", "/v4/aliases")
    ] == ["aliases.listAliases"]


def test_a_verb_literal_carrying_an_escape_is_declined_whole(tmp_path):
    """The same reduction reads the verb, so the same truncation applies to it.

    `"\\u0047ET"` splits into an `escape_sequence` and the fragment `ET`, and a verb of `ET` is
    not a verb. Unlike the route case the cross-check would catch this one -- no specification
    declares an `ET` operation -- but the decline is the answer either way, because a verb the
    source states unreadably is not a verb this rule read.
    """
    root = _copy(tmp_path)
    _edit(root, _REQUEST_MODULE, 'method: "GET",', 'method: "\\u0047ET",')

    extracted = _symbols(root)

    assert "aliases.getAlias" not in extracted
    assert not any(verb == "ET" for verb, _ in extracted.values())


def test_the_fourteen_other_symbols_are_the_control_for_every_edit(tmp_path):
    """An edited tree that stopped rooting would make every assertion above vacuous."""
    root = _copy(tmp_path)
    _edit(root, _REQUEST_MODULE, _ROUTE_LITERAL, '"/v4/aliases\\/{idOrAlias}"')

    assert len(_symbols(_copy(tmp_path / "control"))) == 15
    assert len(_symbols(root)) == 14


# --------------------------------------------------------------------------------------------
# 287 and 293: the route argument is a string this rule does not read, or is empty
# --------------------------------------------------------------------------------------------


def test_a_route_built_by_interpolation_is_not_read_as_a_route(tmp_path):
    """287. `pathToFunc` handed a template literal rather than a plain string.

    Reading the fragments of a template would answer `/v4/aliases/`, a route with its parameter
    segment dropped rather than templated -- which is the wrong-route failure the module's own
    `_helper_path` docstring refuses. The decline costs the binding for `aliases.getAlias`.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _REQUEST_MODULE,
        f"pathToFunc({_ROUTE_LITERAL})",
        "pathToFunc(`/v4/aliases/${idOrAlias}`)",
    )

    extracted = _symbols(root)

    assert "aliases.getAlias" not in extracted
    assert not any(path.startswith("/v4/aliases/") for _, path in extracted.values())


def test_an_empty_route_literal_reads_as_absent_rather_than_as_a_route(tmp_path):
    """293. A `string` node with no `string_fragment` child at all.

    The alternative is a route of `""`, which `_route` would keep and `ExtractedOperation` would
    carry, giving a symbol bound to the empty path -- a binding to nothing that occupies the key
    the real operation would take.
    """
    root = _copy(tmp_path)
    _edit(root, _REQUEST_MODULE, f"pathToFunc({_ROUTE_LITERAL})", 'pathToFunc("")')

    extracted = _symbols(root)

    assert "aliases.getAlias" not in extracted
    assert "" not in {path for _, path in extracted.values()}


# --------------------------------------------------------------------------------------------
# 340: an object member that is not a key/value pair
# --------------------------------------------------------------------------------------------


def test_a_request_object_carrying_members_that_are_not_pairs_still_yields_its_verb(tmp_path):
    """340, and it is what makes the rest of the loop safe rather than a guard against nothing.

    Three of the four member kinds an object literal can hold are not `pair` nodes -- a spread
    element, a shorthand property, and a comment -- and none of them has a `key` field. Skipping
    them is what lets the loop keep looking for `method`; the verb is read and the symbol survives.

    Vercel's own emission holds none of these inside `_createRequest`'s object, so nothing in the
    committed tree reaches this statement. It holds one directly next door: the object handed to
    `client._do` carries a shorthand `context`, which the `_createRequest` anchor two loops up
    before this loop ever sees it.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _REQUEST_MODULE,
        "client._createRequest(context, {\n    security: requestSecurity,",
        "client._createRequest(context, {\n    ...overrides,\n    // written by the generator\n"
        "    security: requestSecurity,",
    )

    assert _symbols(root)["aliases.getAlias"] == ("GET", "/v4/aliases/{idOrAlias}")


# --------------------------------------------------------------------------------------------
# 208: an import form that states no module specifier
# --------------------------------------------------------------------------------------------


def test_a_delegation_imported_through_the_require_form_reaches_no_module(tmp_path):
    """208. `import name = require("...")` is valid TypeScript and states no `source` field.

    tree-sitter parses it cleanly as an `import_statement` whose only named child is an
    `import_require_clause`, so the specifier is not where this rule looks for it and the import
    is not recorded. The delegation then resolves to no module, and `Aliases.getAlias` contributes
    no symbol.

    Speakeasy does not emit this form -- the committed tree contains no `require(` at all -- so
    the cost today is nothing. It is covered because a generator that changed its module target
    would emit it, and the loss would be a symbol rather than an error.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _CLASS_MODULE,
        'import { aliasesGetAlias } from "../funcs/aliasesGetAlias.js";',
        'import aliasesGetAlias = require("../funcs/aliasesGetAlias.js");',
    )

    assert "aliases.getAlias" not in _symbols(root)
    assert len(_symbols(root)) == 14


# --------------------------------------------------------------------------------------------
# 214-215: the two ValueErrors inside one handler, and the decline neither of them records
# --------------------------------------------------------------------------------------------


def test_a_mount_imported_from_outside_the_checkout_is_dropped_without_a_record(tmp_path):
    """214-215 by way of `relative_to`, which is the case the handler was written for.

    A specifier resolving above the checkout root cannot be given a module key, so the import is
    not recorded, so the mount's class name is looked for in the mounting file itself, is not a
    candidate there, and the mount is not an edge. Six symbols go.

    **And nothing is recorded**, because the decline at 503 requires `imported is not None` --
    the source has to have named a module for the rule to say which file is missing. The control
    below is the same absent class named by an in-tree specifier: identical loss, and that one is
    reported. So the record is not about whether the resource was lost, it is about whether the
    specifier resolved.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _CLIENT_MODULE,
        'import { Aliases } from "./aliases.js";',
        'import { Aliases } from "../../../../outside/aliases.js";',
    )

    assert not [symbol for symbol in _symbols(root) if symbol.startswith("aliases.")]
    assert not [entry for entry in _declines(root) if "Aliases" in entry]


def test_the_same_loss_named_by_an_in_tree_specifier_is_reported(tmp_path):
    """The control for the test above, and what makes its silence a finding rather than a reading.

    `./absent-aliases.js` resolves to a module key inside the checkout that no file provides. The
    resource is lost exactly as it is above, and this time a decline names it.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _CLIENT_MODULE,
        'import { Aliases } from "./aliases.js";',
        'import { Aliases } from "./absent-aliases.js";',
    )

    assert not [symbol for symbol in _symbols(root) if symbol.startswith("aliases.")]
    assert [entry for entry in _declines(root) if "Aliases" in entry]


def test_a_specifier_resolving_to_the_checkout_root_declines_the_same_way(tmp_path):
    """214-215 by way of `with_suffix`, which is an internal fault and not a boundary condition.

    `sdk/sdk.ts` importing `".."` resolves to the checkout root itself. `relative_to` succeeds and
    answers `.`, whose name is empty, so `with_suffix("")` raises `ValueError` -- from path
    arithmetic inside `_module_key`, over a path that *is* in the checkout. The handler cannot
    tell that from the specifier above and answers `None` for both.

    Pinned because the two are different faults with one answer: one says the SDK named something
    outside the tree, the other says this rule could not name something inside it.
    """
    root = _copy(tmp_path)
    _edit(
        root,
        _CLIENT_MODULE,
        'import { Aliases } from "./aliases.js";',
        'import { Aliases } from "..";',
    )

    assert not [symbol for symbol in _symbols(root) if symbol.startswith("aliases.")]
    assert not [entry for entry in _declines(root) if "Aliases" in entry]


# --------------------------------------------------------------------------------------------
# Whether any of it reaches the channel M3-W100 added
# --------------------------------------------------------------------------------------------


def test_an_unreadable_route_in_a_staged_request_module_is_recorded_nowhere(tmp_path):
    """The finding this file exists for, and it is invisible in the committed tree.

    In the committed twenty files every method has one absent delegation target -- `unwrapAsync`,
    from `types/fp.js` -- so a method that loses its route still records a decline, and that
    decline names `types/fp` rather than the module whose route could not be read. Stage a stub for
    that module and the decline disappears entirely: the request module is present, so nothing is
    absent, so nothing is recorded.

    `_Module.route is None` is what "this module builds no request" and "this module builds a
    request whose route I could not read" both reduce to, and the rule cannot separate them at the
    point it walks. The Python and TypeScript flavours can, and do -- both record
    `... with no route this rule can read` -- because there the route is in the file that declares
    the method.
    """
    root = _copy(tmp_path)
    _stage_the_wrapper_module(root)
    _edit(
        root,
        _REQUEST_MODULE,
        f"pathToFunc({_ROUTE_LITERAL})",
        "pathToFunc(`/v4/aliases/${idOrAlias}`)",
    )

    clean = _copy(tmp_path / "clean")
    _stage_the_wrapper_module(clean)

    assert "aliases.getAlias" not in _symbols(root)
    assert "aliases.getAlias" in _symbols(clean)
    assert _declines(root) == _declines(clean)


def test_the_loss_moves_two_numbers_and_names_itself_in_neither(tmp_path):
    """What an operator can see of it: one fewer symbol, one more unreached operation.

    `unreached` does move -- M3-W100's complement counts the declared operations no symbol
    reaches, and the route this rule could not read is now one of them. But it is one of 345, is
    spelled as the specification spells it, and carries no reason. Nothing distinguishes it from
    the 344 the fixture's truncation already loses, and Speakeasy publishes no
    `configured_endpoints`, so there is no declared symbol count to check the total against.
    """
    root = _copy(tmp_path)
    _stage_the_wrapper_module(root)
    _edit(
        root,
        _REQUEST_MODULE,
        f"pathToFunc({_ROUTE_LITERAL})",
        "pathToFunc(`/v4/aliases/${idOrAlias}`)",
    )
    clean = _copy(tmp_path / "clean")
    _stage_the_wrapper_module(clean)

    spec = read_spec_operations(SPEC_OPERATIONS)
    lost = report_extraction(root, spec)
    kept = report_extraction(clean, spec)

    assert lost.extracted_count == kept.extracted_count - 1
    assert set(lost.unreached) - set(kept.unreached) == {("GET", "/v4/aliases/{idOrAlias}")}
    assert lost.unreadable == kept.unreadable


# --------------------------------------------------------------------------------------------
# The five statements no input reaches
# --------------------------------------------------------------------------------------------

_TS_LANGUAGE = Language(tsts.language_typescript())

_REQUIRED_FIELDS = {
    "call_expression": ("function", "arguments"),
    "pair": ("key", "value"),
    "class_declaration": ("body",),
    "method_definition": ("name",),
}


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_the_four_guards_against_an_absent_required_field_cannot_fire(tmp_path):
    """309, 344, 392 and 399 each test a grammar field that is never absent.

    tree-sitter's error recovery inserts a MISSING node for a required field rather than omitting
    it, so `child_by_field_name` answers a node even for source that does not parse. The
    measurement: every committed Speakeasy file truncated at every 64th byte, which is 1,568
    parses of real vendor source in every state of incompleteness, and the count of MISSING nodes
    is asserted non-zero so that a sweep which had stopped producing broken trees cannot pass.

    Held as a test rather than reported as reasoning because it is the evidence for four
    "unreachable" verdicts, and because it goes red the day a tree-sitter upgrade changes error
    recovery -- which is the day those four guards would start to matter.
    """
    parser = Parser(_TS_LANGUAGE)
    parses = 0
    missing = 0
    absent_fields: set[tuple[str, str]] = set()

    for path in sorted(SDK.rglob("*.ts")):
        raw = path.read_bytes()
        for cut in range(0, len(raw) + 1, 64):
            tree = parser.parse(raw[:cut])
            parses += 1
            for node in _walk(tree.root_node):
                if node.is_missing:
                    missing += 1
                for field in _REQUIRED_FIELDS.get(node.type, ()):
                    if node.child_by_field_name(field) is None:
                        absent_fields.add((node.type, field))

    assert parses > 1000
    assert missing > 0
    assert absent_fields == set()


def test_a_non_pair_member_has_no_key_which_is_why_the_pair_guard_is_unreachable(tmp_path):
    """344 specifically: it is unreachable *because* 340 is there, not because nothing has no key.

    Every member kind that is not a `pair` answers `None` for both `key` and `value`. So deleting
    340 does not make the loop wrong -- it makes 344 the statement that skips those members. The
    two are one guard written twice, and only the first can fire.
    """
    parser = Parser(_TS_LANGUAGE)
    source = b'f({ ...spread, shorthand, /* comment */ m() {}, key: "value" });'
    tree = parser.parse(source)

    members = {
        member.type: (
            member.child_by_field_name("key"),
            member.child_by_field_name("value"),
        )
        for node in _walk(tree.root_node)
        if node.type == "object"
        for member in node.named_children
    }

    assert set(members) == {
        "spread_element",
        "shorthand_property_identifier",
        "comment",
        "method_definition",
        "pair",
    }
    for kind, (key, value) in members.items():
        if kind == "pair":
            assert key is not None and value is not None
        else:
            assert key is None and value is None

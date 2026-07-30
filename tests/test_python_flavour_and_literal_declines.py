"""What the Python symbol reader and the literal indexer decline, and what a caller sees of it.

M3-W97. Two modules, thirteen unexecuted statements between them, and almost every one is a
place where an input arrives that the rule does not read. A reader that declines too much
produces a smaller symbol map, and a smaller map produces fewer findings -- which is
indistinguishable from a healthy vendor. A literal indexer that declines too much loses a
model id its call site was the only record of.

`symbols.py` is the original of the three generated-SDK flavours and the module the other two
import `ExtractionReport`, `ExtractedOperation`, `UnrecognisedSdkShape` and `_route` from, so a
decline recorded here is a decline all three share.

Two of the thirteen are argued unreachable rather than reached, and the argument is pinned by a
test on the parse tree rather than by calling a private function with a fabricated value:
`literals.py:79` below, and `symbols.py:307`, whose reasoning is in the task report because it
is a property of a dict comprehension rather than of any parse.

The `SDK` sources here are written inline rather than committed under `fixtures/`. Every one is
a shape a generator does not emit -- a dotted decorator, a mount with no annotation, a request
helper handed no route -- so the fixture *is* the claim being made, and putting it one directory
away would separate the claim from the assertion resting on it. The committed verbatim vendor
source stays where it is and is read here only where the real shape is the point.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from ast_grep_py import SgRoot

from sync.index.literals import index_operation_literals
from sync.signals.generated.symbols import extract_symbols, report_extraction

FIXTURES = Path(__file__).parent / "fixtures" / "sdk_sources"
SDK = FIXTURES / "anthropic_python"

CLAUDE = ("claude-",)


def _sdk(tmp_path: Path, source: str) -> Path:
    root = tmp_path / "sdk"
    root.mkdir()
    (root / "_client.py").write_text(dedent(source), encoding="utf-8")
    return root


def _symbols(root: Path) -> dict[str, tuple[str, str]]:
    """The resulting symbol map, which is what a decline is visible in or absent from."""
    return {
        operation.symbol: (operation.http_method, operation.path)
        for operation in extract_symbols(root)[0]
    }


def _index(source: str, prefixes=CLAUDE, language="typescript"):
    return index_operation_literals(
        source,
        path="src/client.ts",
        repo_id="repo-1",
        vendor_id="anthropic",
        sdk_version="0.70.0",
        prefixes=prefixes,
        language=language,
    )


# --- symbols.py: the dotted spellings, which are accepted rather than declined ----------


def test_a_mount_decorated_through_a_module_is_still_a_mount(tmp_path):
    """`@functools.cached_property` rather than the bare name Stainless emits.

    The dotted form is the same decorator, and reading only the bare name would drop every
    resource mounted under it -- a whole subtree of symbols absent from the map with no signal.
    """
    root = _sdk(
        tmp_path,
        """
        import functools

        class Models(SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/models")

        class Acme(SyncAPIClient):
            @functools.cached_property
            def models(self) -> Models:
                ...
        """,
    )

    assert _symbols(root) == {"models.list": ("GET", "/v1/models")}


def test_a_resource_deriving_a_dotted_base_is_recognised(tmp_path):
    """`class Models(resources.SyncAPIResource)`. The base-class rule is the whole of how a
    resource is told from `AsyncModels` and the `*WithRawResponse` wrappers, so a spelling it
    does not read is a vendor that appears to have no resources at all."""
    root = _sdk(
        tmp_path,
        """
        class Models(resources.SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/models")

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...
        """,
    )

    assert _symbols(root) == {"models.list": ("GET", "/v1/models")}


def test_a_mount_annotated_through_a_module_names_its_resource(tmp_path):
    """`-> resources.Messages`. The annotation is the only statement of what a mount mounts --
    the directory is deliberately not consulted -- so an unread spelling unroots the subtree."""
    root = _sdk(
        tmp_path,
        """
        class Messages(SyncAPIResource):
            def create(self):
                return self._post("/v1/messages")

        class Acme(SyncAPIClient):
            @cached_property
            def messages(self) -> resources.Messages:
                ...
        """,
    )

    assert _symbols(root) == {"messages.create": ("POST", "/v1/messages")}


# --- symbols.py: the declines ------------------------------------------------------------


def test_a_mount_whose_annotation_names_no_resource_class_mounts_nothing(tmp_path):
    """Two inputs, one statement: a `cached_property` with no return annotation at all, and one
    annotated with a subscript rather than a name.

    Declining is right and the alternative is worse than a loss. The annotation is what says
    which class is mounted; `Optional[Messages]` states a type, not a resource, and guessing the
    subscript's base would mount a resource under a name the customer may not be able to reach.
    A third mount that *is* plainly annotated is here so the decline is shown to be scoped to
    the two rather than to be the reader failing on the file.
    """
    root = _sdk(
        tmp_path,
        """
        class Messages(SyncAPIResource):
            def create(self):
                return self._post("/v1/messages")

        class Acme(SyncAPIClient):
            @cached_property
            def untyped(self):
                ...

            @cached_property
            def boxed(self) -> Optional[Messages]:
                ...

            @cached_property
            def messages(self) -> Messages:
                ...
        """,
    )

    assert _symbols(root) == {"messages.create": ("POST", "/v1/messages")}


def test_a_request_helper_handed_no_route_yields_no_operation(tmp_path):
    """`self._post(**kwargs)` -- the verb is stated and the path is not.

    Declining is right: the route is the first positional argument and there is nothing else to
    read it from. Recording the verb alone would put a symbol in the map with no route to match
    a vendor change against, which resolves every call site on it to nothing while counting
    towards the coverage figure as though it had been extracted.
    """
    root = _sdk(
        tmp_path,
        """
        class Models(SyncAPIResource):
            def list(self, **kwargs):
                return self._get_api_list(**kwargs)

            def retrieve(self):
                return self._get("/v1/models/x")

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...
        """,
    )

    assert _symbols(root) == {"models.retrieve": ("GET", "/v1/models/x")}


def test_a_helper_handed_no_route_does_not_stop_the_one_beside_it(tmp_path):
    """The decline is scoped to the call, not to the method. Stainless emits one request per
    method, but an overload or a retry wrapper can put two in one body, and abandoning the
    method on the first unreadable call would lose a route that is stated plainly."""
    root = _sdk(
        tmp_path,
        """
        class Models(SyncAPIResource):
            def list(self, **kwargs):
                self._get_api_list(**kwargs)
                return self._get_api_list("/v1/models", **kwargs)

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...
        """,
    )

    assert _symbols(root) == {"models.list": ("GET", "/v1/models")}


# --- symbols.py: the zero that is a sentinel rather than a measurement -------------------


def test_an_empty_specification_yields_a_zero_ratio_and_says_so_in_the_line():
    """`coverage_ratio`'s `0.0` guard, and whether the zero is distinguishable from a real one.

    As a float it is not: a specification with no operations and a specification none of whose
    operations were reached both answer `0.0`, and this asserts that they are equal rather than
    implying otherwise. What distinguishes them is the module's own rule that coverage travels
    with its denominator -- `render()` writes `0 of 0` against `0 of 1`, so the sentinel is
    legible in the only artifact that exposes the ratio at all. M3-W100 put a second denominator
    in that line and this is what holds the first one legible beside it.
    """
    empty = report_extraction(SDK, set())
    missed = report_extraction(SDK, {("GET", "/a/route/this/sdk/does/not/send")})

    assert empty.coverage_ratio == 0.0
    assert missed.coverage_ratio == 0.0
    assert empty.coverage_ratio == missed.coverage_ratio

    assert "0 of 0 comparable routes (0.0%)" in empty.render()
    assert "0 of 1 comparable routes (0.0%)" in missed.render()
    assert empty.render() != missed.render()


def test_an_empty_specification_reports_every_extracted_operation_as_unknown():
    """The loud half of the same input. A denominator of zero is a staged specification that
    declares nothing, and the reason it is not silent is that every extracted operation then
    fails the cross-check and is named."""
    empty = report_extraction(SDK, set())

    assert empty.extracted_count == 11
    assert len(empty.unknown_to_spec) == 11
    assert "11 extracted operations the specification does not declare" in empty.render()


# --- symbols.py against the TypeScript flavour, on an input both generators can emit -----


def test_a_route_literal_carrying_an_escape_is_read_decoded_rather_than_truncated(tmp_path):
    """The defect M3-W91 found in the TypeScript flavour cannot exist in this one.

    tree-sitter splits a string literal at every escape, so that reader saw `/v1/a` for
    `'/v1/a\\u0041b'` and W91's fix was to decline the literal whole. `ast.Constant.value` is
    the *decoded* string, so this flavour reads the route the SDK actually sends and neither
    truncates nor declines. Pinned rather than described, because the two flavours answering the
    same logical input differently is the kind of difference that is only visible if a test
    states it.
    """
    root = _sdk(
        tmp_path,
        r"""
        class Models(SyncAPIResource):
            def list(self):
                return self._get_api_list("/v1/mod\u0065ls")

        class Acme(SyncAPIClient):
            @cached_property
            def models(self) -> Models:
                ...
        """,
    )

    # The escape stands in the SDK file as six characters, so the decoding under test is the
    # parser's rather than this test file's.
    assert r"/v1/mod\u0065ls" in (root / "_client.py").read_text(encoding="utf-8")
    assert _symbols(root) == {"models.list": ("GET", "/v1/models")}


# --- literals.py: an object key that is not an argument ----------------------------------


def test_a_model_id_used_as_a_type_key_records_no_argument_keys():
    """A quoted key in an `interface` or a type literal, which is a real shape: a customer
    keying a rate-limit or pricing table by model id.

    The literal is still indexed -- it names a model, and a retirement has to be able to reach
    the line -- but the sibling keys are refused, because the members of an interface are not
    the arguments of a call. Claiming them would make the finding describe a call that was never
    made, which is the same failure `_sibling_argument_keys` refuses a nested object for.
    """
    source = 'interface ModelLimits {\n  "claude-opus-4-8": number;\n  "claude-3-7-sonnet-20250219": number;\n}\n'
    sites = _index(source)

    assert [site.operation_id for site in sites] == [
        "claude-opus-4-8",
        "claude-3-7-sonnet-20250219",
    ]
    assert [site.args_keys for site in sites] == [[], []]
    assert [site.symbol for site in sites] == [
        "claude-opus-4-8",
        "claude-3-7-sonnet-20250219",
    ]


def test_the_enclosing_object_is_still_read_when_it_really_is_a_call():
    """The control for the test above. A guard that refused every container would pass it while
    losing the two-fact finding the whole `args_keys` capture exists for."""
    source = 'client.messages.create({ model: "claude-opus-4-8", temperature: 0.7 });'
    site = _index(source)[0]

    assert set(site.args_keys) == {"model", "temperature"}


# --- literals.py: what actually reaches the parse guard ----------------------------------


def test_source_that_does_not_parse_never_reaches_the_parse_guard():
    """The guard's stated reason is a condition that does not raise.

    tree-sitter error-recovers rather than refusing, so a file of syntax nobody can parse still
    yields a `program` node and the `try` completes. `test_malformed_source_does_not_raise`
    passes because of this, not because of the handler -- which is why the handler is
    unexecuted while that test is green.
    """
    root = SgRoot("const = = = {{{", "typescript").root()

    assert root.kind() == "program"
    assert _index("const = = = {{{") == []


def test_the_parse_guard_swallows_an_encode_error_and_no_decode_can_reach_it():
    """The only exception type a realistic input gets to the guard, and it is the encode
    direction rather than the decode one.

    `source` is already a `str`, so the decode happened in the caller -- `sync.cli`'s reader
    raises `UnicodeDecodeError` on the file and skips it by name before this is called. What is
    left available at this boundary is the reverse: a `str` carrying a lone surrogate, which
    `ast-grep` cannot encode to UTF-8 for the parser. It is swallowed here, and the resulting
    empty list is indistinguishable from a file that legitimately names no model.
    """
    surrogate = 'const m = { model: "claude-\udcff" };'

    with pytest.raises(UnicodeEncodeError):
        SgRoot(surrogate, "typescript").root()

    assert _index(surrogate) == []


def test_an_unsupported_language_is_not_caught_by_the_parse_guard():
    """`except Exception` does not catch the one thing `SgRoot` construction reliably raises.

    `ast-grep` is a Rust extension and an unsupported language is a `pyo3` panic, which derives
    `BaseException` directly so that it cannot be swallowed by a broad handler. Propagating is
    the right answer -- `language` is chosen by this repository, never by a customer file -- and
    it is pinned because it bounds what the handler protects: not the parser, only the encode.
    """
    with pytest.raises(BaseException) as raised:
        _index('const m = "claude-opus-4-8";', language="not-a-language")

    assert type(raised.value).__name__ == "PanicException"
    assert not isinstance(raised.value, Exception)


def test_a_string_literal_is_never_the_root_so_the_parent_guard_cannot_fire():
    """`literals.py:79` argued unreachable, on the parse tree rather than by calling `_enclosing_key`.

    The only node whose parent is `None` is the root, the root of every JS/TS parse is a
    `program`, and `find_all(kind="string")` returns descendants of it. So the guard is dead in
    the forward direction for every input this module can be handed.
    """
    for source in (
        'const m = { model: "claude-opus-4-8" };',
        '"claude-opus-4-8";',
        'interface O { "claude-opus-4-8": number }',
        "const = = = {{{",
    ):
        root = SgRoot(source, "typescript").root()

        assert root.kind() == "program"
        assert root.parent() is None
        assert all(node.parent() is not None for node in root.find_all(kind="string"))

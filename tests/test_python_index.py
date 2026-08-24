"""A second `LanguageAdapter`, which is the first real test of whether that protocol is a
plugin boundary or a shape one implementation happens to fit.

`docs/superpowers/specs/2026-07-25-sync-competitive-position.md` rests the moat on coverage
produced without hand-authored adapters, and every language claim in this repository currently
rests on one implementation. Several of the tests below exist to pin what Python *cannot* do
with the same strength TypeScript does, because a limitation asserted in a test is a limitation
the next person cannot mistake for an oversight.
"""

from __future__ import annotations

from conftest import symbol_resolver

import json
from pathlib import Path

import pytest

from sync.core import LanguageAdapter, Patch, RepoRef
from sync.index.python_lang import PythonAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
PY = FIXTURES / "py"

SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
    }
}


def _adapter(tmp_path) -> PythonAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = symbol_resolver(map_path)
    return PythonAdapter(vendor_adapter=vendor)


def _repo(name: str) -> RepoRef:
    return RepoRef(
        repo_id=name, url=f"https://example.invalid/{name}",
        local_path=str(PY / name), head_sha="0" * 40,
    )


def _only(tmp_path, name):
    sites = list(_adapter(tmp_path).index(_repo(name)))
    assert len(sites) == 1, f"expected one call site in {name}, got {len(sites)}"
    return sites[0]


# A manifest that is not UTF-8, in the spelling found in the wild: `.encode("utf-16")` writes the
# byte-order mark, so these bytes begin `ff fe` exactly as `LilithB92/Online_training_DRF` does.
UTF16_REQUIREMENTS = "stripe==11.0.0\n".encode("utf-16")

BILLING_PY = """import stripe


def charge():
    result = stripe.charges.create(amount=100, currency="eur")
    return result.status
"""


def _utf16_requirements_repo(tmp_path, *, pyproject: str | None = None) -> RepoRef:
    """A project whose `requirements.txt` is UTF-16, built here rather than committed.

    Built for the reason `_broken_repo` is, one step further along: git decides text from binary
    by heuristic and CLAUDE.md rules out a `.gitattributes` to overrule it, so a committed
    non-UTF-8 fixture is one whose bytes a checkout may quietly change -- and a fixture that
    silently became valid UTF-8 would leave the test below passing over nothing. Written with
    `write_bytes`, because bytes that are not text are not decoded.
    """
    root = tmp_path / "utf16_requirements"
    (root / "src").mkdir(parents=True)
    (root / "requirements.txt").write_bytes(UTF16_REQUIREMENTS)
    if pyproject is not None:
        (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (root / "src" / "billing.py").write_text(BILLING_PY, encoding="utf-8")
    return RepoRef(
        repo_id="utf16", url="https://example.invalid/utf16",
        local_path=str(root), head_sha="0" * 40,
    )


def _broken_repo(tmp_path) -> RepoRef:
    """A project whose source does not parse, built here rather than committed.

    `scripts/lint_encoding.py` AST-parses every `.py` file under `tests/`, so a deliberately
    invalid one cannot live in `tests/fixtures/` -- the repository gate that keeps encoding bugs
    out would reject the fixture that proves the syntax gate works. The TypeScript adapter never
    met this, because its malformed fixture is a manifest rather than source.
    """
    root = tmp_path / "broken_syntax"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "broken"\ndependencies = ["stripe>=12.0.0"]\n', encoding="utf-8"
    )
    (root / "src" / "billing.py").write_text("def charge(:\n    return 1\n", encoding="utf-8")
    return RepoRef(
        repo_id="broken", url="https://example.invalid/broken",
        local_path=str(root), head_sha="0" * 40,
    )


# --- the protocol -----------------------------------------------------------------


def test_adapter_satisfies_the_language_protocol(tmp_path):
    """The point of the task. A protocol with one implementation is a shape that
    implementation fits; this is the assertion that makes it a boundary."""
    assert isinstance(_adapter(tmp_path), LanguageAdapter)


def test_the_language_id_names_the_language(tmp_path):
    assert _adapter(tmp_path).language_id == "python"


# --- matches: which manifest, and what an unreadable one means --------------------


def test_matches_a_project_declaring_stripe_in_pyproject(tmp_path):
    assert _adapter(tmp_path).matches(_repo("simple")) is True


def test_matches_a_project_declaring_stripe_in_requirements(tmp_path):
    """Python has no single manifest. A repository pinning its dependencies in
    `requirements.txt` depends on Stripe exactly as much as one using `pyproject.toml`, and
    reading only the modern file would report half the ecosystem as not using the SDK."""
    assert _adapter(tmp_path).matches(_repo("requirements")) is True


def test_does_not_match_a_project_without_stripe(tmp_path):
    assert _adapter(tmp_path).matches(_repo("no_stripe")) is False


def test_an_unreadable_manifest_answers_no_rather_than_raising(tmp_path):
    """A customer's manifest is untrusted input. The caller already has a path for a repository
    that does not demonstrably depend on the SDK, and a parse error out of `run()` is a
    traceback where that answer belongs."""
    assert _adapter(tmp_path).matches(_repo("malformed_manifest")) is False


# A manifest a Windows editor saved. `utf-8-sig` writes the byte-order mark that `utf-8` does
# not, and every byte after it is ordinary UTF-8 -- which is what makes this a decoding question
# rather than a decode failure, and why nothing raised.
def _bom_repo(tmp_path, name: str, **files: str) -> RepoRef:
    """A project whose manifests each begin with a UTF-8 byte-order mark.

    Built rather than committed for the reason `_utf16_requirements_repo` is, and here the reason
    is sharper: a BOM is invisible in every editor and most diffs, so a committed fixture would be
    stripped or added by anything that rewrites the file and nobody would see it happen.
    """
    root = tmp_path / name
    root.mkdir(parents=True)
    for filename, text in files.items():
        (root / filename.replace("_", ".")).write_bytes(text.encode("utf-8-sig"))
    return RepoRef(
        repo_id=name, url=f"https://example.invalid/{name}",
        local_path=str(root), head_sha="0" * 40,
    )


def test_a_byte_order_mark_on_pyproject_does_not_hide_the_dependency(tmp_path):
    """A BOM is valid UTF-8, so nothing fails to decode -- `tomllib` refuses the `\\ufeff` that
    arrives as the first character of the document instead, and the guard written for an
    unreadable manifest swallows it. The repository declares Stripe and was reported as not
    depending on it."""
    repo = _bom_repo(
        tmp_path, "bom_pyproject",
        pyproject_toml='[project]\nname = "billing"\ndependencies = ["stripe>=12.0.0"]\n',
    )
    adapter = _adapter(tmp_path)

    assert adapter.matches(repo) is True
    assert adapter._requirement_lines(repo) == ["stripe>=12.0.0"]


def test_a_byte_order_mark_on_requirements_does_not_mangle_the_first_name(tmp_path):
    """The one that answers wrongly with no error at all, anywhere.

    `requirements.txt` is split into lines rather than parsed, so a leading `\\ufeff` is not a
    syntax error -- it becomes part of the first requirement's name. `_requirement_name`
    normalises `\\ufeffstripe` and compares it against `stripe`, they differ, and the repository is
    reported as not depending on the SDK. No exception is raised, no guard is entered and nothing
    is logged: the only evidence is the answer being wrong.
    """
    repo = _bom_repo(tmp_path, "bom_requirements", requirements_txt="stripe==11.0.0\n")
    adapter = _adapter(tmp_path)

    assert adapter._requirement_lines(repo) == ["stripe==11.0.0"]
    assert adapter.matches(repo) is True


def test_a_byte_order_mark_does_not_hide_a_configured_typechecker(tmp_path):
    """`static_verify` reads the same manifest to say which gate a project configures and does not
    run. A BOM made it report "no typechecker is configured" for a project configuring mypy, which
    is a weaker diagnostic standing in for a stronger one -- the distinction
    `test_a_syntax_error_is_reported_as_such_rather_than_as_a_missing_gate` exists to protect.
    """
    repo = _bom_repo(
        tmp_path, "bom_typed",
        pyproject_toml='[project]\nname = "billing"\ndependencies = ["stripe>=12.0.0"]\n'
                       "\n[tool.mypy]\nstrict = true\n",
    )

    assert _adapter(tmp_path)._configured_typechecker(repo) == "mypy"


def test_a_requirements_file_that_is_not_utf8_answers_no_rather_than_raising(tmp_path):
    """The same promise, made once in the docstring and kept by only one of the two branches.

    This is asked at adapter selection, before any indexing, so a customer repository whose
    `requirements.txt` carries a byte-order mark took the whole run down rather than being
    reported as not demonstrably depending on the SDK.
    """
    assert _adapter(tmp_path).matches(_utf16_requirements_repo(tmp_path)) is False


def test_an_unreadable_requirements_file_does_not_hide_a_readable_pyproject(tmp_path):
    """Unreadable means that manifest declares nothing, never that the project declares nothing.

    A repository carrying both files still depends on Stripe by the one that parses, and the
    version recorded is the one that file pins -- so the answer here is narrowed by the
    unreadable manifest and not replaced by it.
    """
    repo = _utf16_requirements_repo(
        tmp_path, pyproject='[project]\nname = "billing"\ndependencies = ["stripe>=12.0.0"]\n'
    )
    adapter = _adapter(tmp_path)

    assert adapter.matches(repo) is True
    assert [site.sdk_version for site in adapter.index(repo)] == ["12.0.0"]


# --- index ------------------------------------------------------------------------


def test_finds_the_call_site_and_resolves_the_operation(tmp_path):
    site = _only(tmp_path, "simple")

    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.path == "src/billing.py"
    assert site.line == 7


def test_captures_the_keyword_arguments_passed(tmp_path):
    """`args_keys` is what the parameter-deprecation detector joins on, so populating it is
    what gets that detector a second language for free."""
    assert _only(tmp_path, "simple").args_keys == ["amount", "currency"]


def test_captures_nested_dictionary_argument_paths(tmp_path):
    """Vendor changes are overwhelmingly nested, so a request-side path that stopped at depth
    one could only ever meet a depth-one change. Every prefix is recorded because the
    detector's comparison asks whether a call site's path leads into a change's."""
    assert _only(tmp_path, "nested_args").args_keys == [
        "amount", "metadata", "metadata.internal_id", "metadata.nested", "metadata.nested.deep",
    ]


def test_captures_response_fields_read_by_attribute(tmp_path):
    assert _only(tmp_path, "simple").response_fields_read == ["id", "status"]


def test_captures_response_fields_read_by_subscript(tmp_path):
    """The place Python genuinely differs. A Stripe response is dict-like and
    `result["status"]` is as idiomatic as `result.status`; the TypeScript adapter stops at a
    subscript because there it is nearly always an array index, and reading that rule across
    unchanged would miss most of what Python code does with a response.
    """
    assert _only(tmp_path, "subscript").response_fields_read == [
        "data", "payment_method_details", "payment_method_details.card", "status",
    ]


def test_records_the_sdk_version_from_the_manifest(tmp_path):
    assert _only(tmp_path, "simple").sdk_version == "12.0.0"


def test_records_a_pinned_version_from_requirements(tmp_path):
    assert _only(tmp_path, "requirements").sdk_version == "11.4.0"


def test_the_imported_module_is_itself_a_client(tmp_path):
    """`import stripe` then `stripe.charges.create(...)` binds no client variable at all. The
    TypeScript rule -- an identifier assigned from `new Imported(...)` -- has nothing to match
    here, and a port of it verbatim indexes nothing in a repository written this way."""
    site = _only(tmp_path, "module_client")

    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"


def test_a_resource_class_call_is_not_indexed(tmp_path):
    """`stripe.Charge.create(...)` is the older Python SDK's idiom and it resolves to nothing:
    the symbol map is derived from Stripe's own generator input, which names
    `stripe.charges.create`. Binding the two needs an alias table that is knowledge about one
    vendor's Python SDK, and vendor knowledge lives in that vendor's adapter -- so this is
    recorded as a miss rather than papered over here.
    """
    assert list(_adapter(tmp_path).index(_repo("resource_class"))) == []


def test_a_repository_with_no_client_yields_nothing(tmp_path):
    assert list(_adapter(tmp_path).index(_repo("no_stripe"))) == []


def test_non_ascii_source_does_not_corrupt_the_call_site(tmp_path):
    """tree-sitter reports byte offsets and Python slices strings by character. Every other
    fixture in this repository is ASCII, so nothing here would otherwise catch the confusion --
    `sync/route/templates.py` carries a fix for exactly it. The accented text sits on lines
    before and beside the call, so a character-sliced extraction reads from the wrong offset and
    the symbol, the arguments and the fields read all come out wrong together.
    """
    site = _only(tmp_path, "unicode")

    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.args_keys == ["amount", "currency"]
    assert site.response_fields_read == ["status"]
    assert site.line == 10


# --- prepare: what there is to do, which is less than TypeScript ------------------


def test_prepare_installs_nothing(tmp_path):
    """TypeScript installs the customer's dependencies because `tsc` cannot resolve an import
    without them. Python's equivalent would run `pip install`, which executes arbitrary
    `setup.py` from every sdist in the tree -- pip has no `--ignore-scripts`, and CLAUDE.md's
    position is that Sync runs the customer's toolchain and never their application code.
    Buying nothing (there is no typechecker to feed) at that price is not a trade worth making,
    so this is honestly a no-op.
    """
    before = sorted(p.name for p in (PY / "simple").iterdir())

    _adapter(tmp_path).prepare(_repo("simple"))

    assert sorted(p.name for p in (PY / "simple").iterdir()) == before


# --- static_verify: the gate Python does not have --------------------------------


def test_static_verify_never_reports_success_without_a_typechecker(tmp_path):
    """The whole finding, asserted. Nothing reaches a pull request unverified, and Python has no
    gate present in every project the way `tsc` is -- mypy is optional, often unconfigured, and
    frequently failing on code that ships. Returning ok=True here would let an unverified patch
    through on the strength of a gate that never ran, so it fails closed and every Python
    finding abandons at this node.
    """
    result = _adapter(tmp_path).static_verify(_repo("simple"), Patch(diff="", strategy="agent", rationale="r"))

    assert result.ok is False


def test_static_verify_says_which_gate_is_missing(tmp_path):
    """A reviewer reading `abandon_reason` has to be able to tell "Python has no universal
    typechecker" from "the typechecker ran and failed", because those call for entirely
    different responses."""
    result = _adapter(tmp_path).static_verify(_repo("simple"), Patch(diff="", strategy="agent", rationale="r"))

    assert "typechecker" in result.diagnostics.lower()


def test_static_verify_fails_on_source_that_does_not_parse(tmp_path):
    """The one gate Python does have everywhere. It is far weaker than `tsc` -- a renamed field
    parses perfectly -- but a patch that does not compile is a patch no reviewer should see, and
    it costs nothing to catch here rather than in the customer's CI.
    """
    result = _adapter(tmp_path).static_verify(
        _broken_repo(tmp_path), Patch(diff="", strategy="agent", rationale="r")
    )

    assert result.ok is False
    assert "src/billing.py" in result.diagnostics


def test_a_syntax_error_is_reported_as_such_rather_than_as_a_missing_gate(tmp_path):
    """Two different failures must not arrive wearing the same message, or the weaker one hides
    the stronger: a patch that broke the file would be reported as Python merely lacking a
    typechecker, which reads as "nothing to see here"."""
    broken = _adapter(tmp_path).static_verify(
        _broken_repo(tmp_path), Patch(diff="", strategy="agent", rationale="r")
    ).diagnostics
    missing = _adapter(tmp_path).static_verify(
        _repo("simple"), Patch(diff="", strategy="agent", rationale="r")
    ).diagnostics

    assert broken != missing
    assert "syntax" in broken.lower()


# --- what the syntax gate must and must not call broken -----------------------------

VALID_SOURCE = "import stripe\n\n\ndef charge():\n    return stripe.charges.create(amount=1)\n"


def _source_repo(tmp_path, name: str, source: bytes) -> RepoRef:
    """A project declaring Stripe whose one source file is exactly these bytes.

    Bytes rather than text, because every case below is a question about how the file is
    encoded, and writing it through a str would answer that question before the gate saw it.
    """
    root = tmp_path / name
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "billing"\ndependencies = ["stripe>=12.0.0"]\n', encoding="utf-8"
    )
    (root / "src" / "billing.py").write_bytes(source)
    return RepoRef(
        repo_id=name, url=f"https://example.invalid/{name}",
        local_path=str(root), head_sha="0" * 40,
    )


def test_a_byte_order_mark_on_source_is_not_a_syntax_error(tmp_path):
    """The gate called a file broken that Python compiles.

    A `.py` file may begin with a UTF-8 byte-order mark -- the tokenizer strips it, and
    `py_compile` accepts the file. Reading it as text and handing `ast.parse` the resulting str
    leaves the `\\ufeff` in place, and `ast.parse` rejects it as `invalid non-printable character
    U+FEFF`. So `static_verify` reported a file the patch never touched as one the patch broke,
    which is the strongest verdict this gate can give and it was wrong.
    """
    repo = _source_repo(tmp_path, "bom_source", VALID_SOURCE.encode("utf-8-sig"))

    assert _adapter(tmp_path)._syntax_errors(repo) == []


def test_a_coding_declaration_is_honoured_rather_than_overruled(tmp_path):
    """The same defect with a second cause, and the one `utf-8-sig` alone does not fix.

    PEP 263 lets a file declare its own encoding, and the interpreter reads the declaration
    before it decodes the rest. A file declaring `latin-1` and written in it compiles; decoding
    it as UTF-8 first raises `UnicodeDecodeError` and the gate reported that as the file being
    broken.
    """
    source = ("# -*- coding: latin-1 -*-\n" + VALID_SOURCE + 'CAFE = "café"\n').encode("latin-1")
    repo = _source_repo(tmp_path, "declared_latin1", source)

    assert _adapter(tmp_path)._syntax_errors(repo) == []


def test_source_that_declares_nothing_and_is_not_utf8_is_still_broken(tmp_path):
    """The gate must not have been widened. These are the same bytes as the case above with the
    declaration removed, which is what makes the pair a discrimination rather than two
    assertions: CPython rejects this one, so the gate has to as well."""
    source = (VALID_SOURCE + 'CAFE = "café"\n').encode("latin-1")
    repo = _source_repo(tmp_path, "undeclared_latin1", source)

    broken = _adapter(tmp_path)._syntax_errors(repo)

    assert [entry.split(":")[0] for entry in broken] == ["src/billing.py"]


def test_a_utf16_source_file_is_reported_rather_than_raising(tmp_path):
    """`ast.parse` over bytes answers this one with `ValueError`, not `SyntaxError` -- "source
    code string cannot contain null bytes" -- so a chain catching only `SyntaxError` would let it
    out of the gate as a crash rather than a verdict. Asserted here because the reason the gate
    catches `ValueError` at all is invisible from the code.
    """
    repo = _source_repo(tmp_path, "utf16_source", VALID_SOURCE.encode("utf-16"))

    broken = _adapter(tmp_path)._syntax_errors(repo)

    assert len(broken) == 1
    assert broken[0].startswith("src/billing.py:")


def test_the_gate_agrees_with_py_compile_on_every_shape(tmp_path):
    """The property the three cases above are instances of, stated once against the authority.

    `_syntax_errors` exists to answer "is this valid Python", and its docstring says the
    interpreter's own parser is what decides. So the test is whether it agrees with the
    interpreter, file by file, rather than whether it produces any particular message.
    """
    import py_compile

    cases = {
        "plain": VALID_SOURCE.encode("utf-8"),
        "bom": VALID_SOURCE.encode("utf-8-sig"),
        # The accented line is what makes this case latin-1 at all: `VALID_SOURCE` is ASCII, and
        # latin-1 of ASCII is ASCII, so without it the declaration is never exercised.
        "declared_latin1": (
            "# -*- coding: latin-1 -*-\n" + VALID_SOURCE + 'CAFE = "café"\n'
        ).encode("latin-1"),
        "utf8_accented": (VALID_SOURCE + 'CAFE = "café"\n').encode("utf-8"),
        "broken": b"def charge(:\n    return 1\n",
        "undeclared_latin1": (VALID_SOURCE + 'CAFE = "café"\n').encode("latin-1"),
        "utf16": VALID_SOURCE.encode("utf-16"),
    }

    disagreements = []
    for name, source in cases.items():
        repo = _source_repo(tmp_path, f"agree_{name}", source)
        gate_says_broken = bool(_adapter(tmp_path)._syntax_errors(repo))
        try:
            py_compile.compile(
                str(Path(repo.local_path) / "src" / "billing.py"), cfile=None, doraise=True
            )
            cpython_says_broken = False
        except py_compile.PyCompileError:
            cpython_says_broken = True
        if gate_says_broken != cpython_says_broken:
            disagreements.append(
                f"{name}: gate broken={gate_says_broken}, CPython broken={cpython_says_broken}"
            )

    assert disagreements == []


def test_a_configured_typechecker_is_reported_as_unused_rather_than_claimed(tmp_path):
    """A project configuring mypy has a gate this adapter does not run. Saying so is the
    difference between a limitation someone can close and one they have to rediscover -- and
    claiming the gate ran would be the papering-over this task exists to avoid.
    """
    result = _adapter(tmp_path).static_verify(_repo("typed"), Patch(diff="", strategy="agent", rationale="r"))

    assert result.ok is False
    assert "mypy" in result.diagnostics.lower()


@pytest.mark.parametrize("fixture", ["simple", "typed", "nested_args", "module_client"])
def test_static_verify_is_never_ok_for_any_fixture(fixture, tmp_path):
    """Stated once as a property rather than trusted to the cases above: there is no input to
    this adapter that produces a passing verification, because there is no gate behind it."""
    assert _adapter(tmp_path).static_verify(
        _repo(fixture), Patch(diff="", strategy="agent", rationale="r")
    ).ok is False


def test_an_integer_subscript_ends_the_path(tmp_path):
    """`result["data"][0]` names a field and then an element of it. The index is not a field
    name, and continuing through it would invent a path segment no vendor change can carry --
    so the path stops at `data`, which is shorter but never wrong."""
    fields = _only(tmp_path, "subscript").response_fields_read

    assert "data" in fields
    assert not [field for field in fields if "0" in field]


def test_two_functions_sharing_a_result_name_do_not_merge(tmp_path):
    """Both functions call their result `result`, which is the most common name there is.
    Collecting reads across the whole module would give each call site the other's fields, and
    the detector would then report a call site as reading something it never touches.
    """
    sites = {site.symbol: site for site in _adapter(tmp_path).index(_repo("two_scopes"))}

    assert sites["stripe.charges.create"].response_fields_read == ["status"]
    assert sites["stripe.charges.retrieve"].response_fields_read == ["amount_refunded"]


def test_unbound_import_paths_reports_wrapper_files(tmp_path: Path):
    repo_dir = tmp_path / "py_wrapper_repo"
    repo_dir.mkdir()
    (repo_dir / "requirements.txt").write_text("stripe==12.0.0\n", encoding="utf-8")
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    # A wrapper file that imports stripe and exports a helper
    (src_dir / "wrapper.py").write_text(
        "import stripe\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    # An app file that calls the helper
    (src_dir / "app.py").write_text(
        "from src.wrapper import helper\n\ndef run():\n    return helper()\n",
        encoding="utf-8",
    )

    repo = RepoRef(repo_id="py_wrapper_repo", url="https://example.invalid/py_wrapper_repo", local_path=str(repo_dir), head_sha="0" * 40)
    adapter = _adapter(tmp_path)

    # index yields 0 call sites because calls happen on helper() rather than stripe.charges.create
    sites = list(adapter.index(repo))
    assert len(sites) == 0

    # unbound_import_paths explicitly identifies src/wrapper.py as importing the SDK without bound call sites
    unbound = adapter.unbound_import_paths(repo)
    assert unbound == ["src/wrapper.py"]


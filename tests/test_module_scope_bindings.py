"""What each indexer does with a call whose result is bound at module scope.

`_enclosing_scope` walks to the nearest function ancestor and falls back to the module root
when there is none. Both adapters carry that fallback -- `python_lang.py:628` and
`typescript.py:495` -- and until this file neither statement had ever run, because every
response-side fixture in this repository wrapped its call in a function. A customer script
that calls the SDK at the top of a file and reads a field off the result is ordinary, and
nothing here had shown either adapter handled it.

The measurement says it does. A module-scope call is indexed, resolves its operation, records
its argument keys, and records the fields read off its result -- in both languages, to the same
values. The response-side path is reachable at module scope; the statement was unexercised and
not wrong.

What the fallback costs is a scope wide enough to contain other scopes. `_response_fields`
walks the whole subtree of whatever scope it is handed, so a module-scope call collects reads
of its name from inside every function in the file, including functions that rebind the name to
something the vendor never returned. `merged` shows that absorbing another indexed call's
fields, which is the merge both docstrings say must not happen.

`class_body` says the fallback answers for more inputs than its docstrings name: a class body is
not a function either, so a call in one is scoped to the whole module rather than to the class.

`nested_function` is why that is not a defect in the fallback. It puts the same rebinding one
level inside a function, where `_enclosing_scope` returns the function and the fallback never
runs, and the leak is identical. The walk is not shadow-aware at any scope; module scope is
only its widest instance. Fixing it means teaching `_response_fields` which reads a rebinding
shadows, which is a different change to a different method, and it trades a false field for a
missed one in a direction nothing here has measured. It is recorded in
`docs/superpowers/reports/2026-07-31-module-scope-bindings.md` as the next task rather than
guessed at here.

So these tests pin behaviour rather than drive a fix, and every one of them is proven to fail
against a mutation of the code it covers -- the table is in that report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"

SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
    }
}

PYTHON = "python"
TYPESCRIPT = "typescript"
BOTH = [PYTHON, TYPESCRIPT]

# The fixture files written to the same shape in both languages. `class_body` is deliberately not
# among them: Python reads a class attribute inside the class body by its bare name and TypeScript
# reads it through `this.` or the class, so there is no matched source to compare and a pair here
# would be asserting agreement about two different programs.
MATCHED = ("script", "shadowed", "merged", "nested_function")


def _sites(tmp_path, language: str) -> list[CallSite]:
    """Every call site the named language's indexer finds in its `module_scope` fixture.

    The two fixture trees are written to the same shape file by file, so a claim asserted for
    one language and then for the other is a claim about the same source in two spellings.
    """
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)

    if language == PYTHON:
        kind, adapter = "py", PythonAdapter(vendor_adapter=vendor)
    else:
        kind, adapter = "ts", TypeScriptAdapter(vendor_adapter=vendor)

    repo = RepoRef(
        repo_id="module_scope",
        url="https://example.invalid/module_scope",
        local_path=str(FIXTURES / kind / "module_scope"),
        head_sha="0" * 40,
    )
    return list(adapter.index(repo))


def _in(sites: list[CallSite], stem: str) -> list[CallSite]:
    """The sites from one fixture file, by stem, so `.py` and `.ts` are named the same way."""
    return [site for site in sites if Path(site.path).stem == stem]


def _one(sites: list[CallSite], stem: str) -> CallSite:
    found = _in(sites, stem)
    assert len(found) == 1, f"expected one call site in {stem}, got {len(found)}"
    return found[0]


def _fields(sites: list[CallSite], stem: str) -> list[str]:
    return sorted(_one(sites, stem).response_fields_read)


# --- the call is not invisible -------------------------------------------------------


@pytest.mark.parametrize("language", BOTH)
def test_a_module_scope_call_is_indexed_and_resolves_its_operation(tmp_path, language) -> None:
    """The first of the three outcomes this fixture had to separate, and the one that would
    have been worst: a call at the top of a file producing no call site at all, so the customer
    who wrote the most ordinary script there is gets no findings and no explanation."""
    site = _one(_sites(tmp_path, language), "script")

    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.line == 5


@pytest.mark.parametrize("language", BOTH)
def test_a_module_scope_call_records_the_request_fields_it_passes(tmp_path, language) -> None:
    """The request side never consults the scope, so this would have held however the fallback
    answered. It is here to separate a request-side binding from a response-side one, which is
    the shape a half-working module-scope call would have taken."""
    site = _one(_sites(tmp_path, language), "script")

    assert sorted(site.args_keys) == ["amount", "currency"]


@pytest.mark.parametrize("language", BOTH)
def test_a_module_scope_call_records_the_fields_read_off_its_result(tmp_path, language) -> None:
    """The statement this file exists for. `_enclosing_scope` finds no function ancestor above
    a module-level call and returns the module, and the module is a scope the read walk can
    search -- so the response-side binding is produced, correctly, in both languages."""
    assert _fields(_sites(tmp_path, language), "script") == ["id", "status"]


def test_the_two_languages_agree_on_every_module_scope_call(tmp_path) -> None:
    """The pair share a shape here -- the same walk, the same fallback -- so a disagreement on
    matched source would be a larger finding than the coverage gap, and one that comparing the
    two adapters could not have surfaced, since the defect being looked for is symmetric.

    Compared on symbol and response fields rather than on everything: `col` is a byte offset
    into differently-indented source, and the TypeScript request side reads an object literal
    where Python reads keyword arguments, so `merged`'s positional `retrieve` argument is
    legitimately empty on one side and not the other.
    """

    def summarise(language: str) -> list[tuple[str, str, tuple[str, ...]]]:
        return sorted(
            (Path(s.path).stem, s.symbol, tuple(sorted(s.response_fields_read)))
            for s in _sites(tmp_path, language)
            if Path(s.path).stem in MATCHED
        )

    assert summarise(PYTHON) == summarise(TYPESCRIPT)


# --- what the module as a scope costs ------------------------------------------------


@pytest.mark.parametrize("language", BOTH)
def test_the_scope_of_a_module_scope_call_is_the_whole_module(tmp_path, language) -> None:
    """`total` is read off a function-local rebinding of `charge` that holds no vendor response
    at all. It is credited to the module-scope call because the module is the scope, and the
    scope walk descends into every function in it.

    Pinned rather than fixed: the same leak reproduces where this fallback never runs, which
    the control below establishes.
    """
    assert _fields(_sites(tmp_path, language), "shadowed") == ["status", "total"]


@pytest.mark.parametrize("language", BOTH)
def test_a_module_scope_call_absorbs_a_function_scope_call_and_not_the_reverse(
    tmp_path, language
) -> None:
    """The merge both docstrings forbid, and it runs one way only.

    `merged` binds two indexed calls to the same generic name, one at module scope and one
    inside a function. The module-scope `create` collects the function's `amount_refunded`,
    because the function is inside the module; the function-scope `retrieve` collects nothing
    of the module's, because the module is not inside the function. A detector reading the
    first would report it against a change to a field it never touches.
    """
    sites = {site.symbol: site for site in _in(_sites(tmp_path, language), "merged")}

    assert sorted(sites["stripe.charges.create"].response_fields_read) == [
        "amount_refunded",
        "status",
    ]
    assert sorted(sites["stripe.charges.retrieve"].response_fields_read) == ["amount_refunded"]


@pytest.mark.parametrize("language", BOTH)
def test_the_same_leak_reproduces_where_the_module_fallback_never_runs(tmp_path, language) -> None:
    """The control, and the whole argument for changing no production code here.

    `nested_function` moves the rebinding one level down: the indexed call sits inside `outer`,
    so `_enclosing_scope` returns `outer` and the fallback to the module is never reached. The
    fields recorded are the same ones `shadowed` records at module scope.

    That places the leak in `_response_fields` -- which walks a scope's whole subtree without
    asking which nested scope rebinds the name -- and not in the fallback. Returning the module
    for a module-level call is the right answer to the question `_enclosing_scope` is asked;
    there is no smaller node, and the plain case above proves the answer is usable.
    """
    sites = _sites(tmp_path, language)

    assert _fields(sites, "nested_function") == ["status", "total"]
    assert _fields(sites, "nested_function") == _fields(sites, "shadowed")


def test_a_class_body_call_reaches_the_same_fallback_and_is_scoped_to_the_module(tmp_path) -> None:
    """A module-level call is not the only input the fallback answers for.

    A class body is not a function, so a call in one has no ancestor in `_FUNCTION_TYPES` either
    and gets the module as its scope -- not the class. That is wider than the fallback's own
    docstrings describe, and in a file holding several classes it is the widest read this walk
    performs.

    Python only. TypeScript reads a class field through `this.` or through the class name, and
    neither spells a bare identifier the read walk can root a chain at, so the equivalent source
    is a different program rather than the same one in another language -- and its response
    binding is declined earlier, at `_result_target`, which never reaches the scope walk at all.
    """
    assert _fields(_sites(tmp_path, PYTHON), "class_body") == ["status"]

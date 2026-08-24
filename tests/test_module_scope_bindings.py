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

What the fallback costs is a scope wide enough to contain other scopes, and until
`docs/superpowers/reports/2026-08-03-the-rebinding-leak.md` that cost was paid.
`_response_fields` walked the whole subtree of whatever scope it was handed, so a module-scope
call collected reads of its name from inside every function in the file, including functions
that rebound the name to something the vendor never returned. `shadowed`, `merged` and
`nested_function` all pinned that leak here on purpose, and all three now assert the narrowed
result instead: the walk no longer descends into a scope that gives the name a binding of its
own. Why that is not a weakening is in §2 of the newer report -- the three assertions moved from
naming a field the call never returned to naming only fields it did, and the fixtures kept
their genuine reads so a fix that dropped everything would fail them rather than pass.

`class_body` and `script` did not move. A class body is not a function, so a call in one still
reaches the fallback and is still scoped to the whole module rather than to the class -- which
is wider than that fallback's own docstrings described, and is why the scope walk had to learn
about class bodies as well as functions.

`nested_function` is why the fault was never in the fallback. It puts the same rebinding one
level inside a function, where `_enclosing_scope` returns the function and the fallback never
runs, and before the fix the leak was identical. The walk was not shadow-aware at any scope;
module scope was only its widest instance, and `_enclosing_scope` is unchanged.

So these tests still pin behaviour rather than drive a fix, and every one of them is proven to
fail against a mutation of the code it covers -- the tables are in the two reports.
"""

from __future__ import annotations

from conftest import symbol_resolver

import json
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
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
    vendor = symbol_resolver(map_path)

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


# --- what the module as a scope costs, and what it no longer does --------------------


@pytest.mark.parametrize("language", BOTH)
def test_a_function_that_rebinds_the_name_donates_nothing_to_the_module(
    tmp_path, language
) -> None:
    """`total` is read off a function-local rebinding of `charge` that holds no vendor response
    at all. The module is still the scope and the walk still searches it, but it no longer
    descends into `summarise`, which gives `charge` a binding of its own.

    This assertion used to read `["status", "total"]`. It moved because `total` was a field the
    module-scope call never returned, not because the walk got shy: `status` is the read that
    belongs to it and the assertion still requires it.
    """
    assert _fields(_sites(tmp_path, language), "shadowed") == ["status"]


@pytest.mark.parametrize("language", BOTH)
def test_two_calls_sharing_a_name_in_different_scopes_no_longer_merge(
    tmp_path, language
) -> None:
    """The merge both docstrings forbid, and it no longer happens in either direction.

    `merged` binds two indexed calls to the same generic name, one at module scope and one
    inside a function. The module-scope `create` used to collect the function's
    `amount_refunded`, because the function is inside the module; a detector reading that row
    would have reported it against a change to a field it never touches. The function-scope
    `retrieve` never collected anything of the module's, because the module is not inside the
    function, and its expectation is unchanged -- which is what shows the fix narrowed the one
    row that was wrong rather than both.
    """
    sites = {site.symbol: site for site in _in(_sites(tmp_path, language), "merged")}

    assert sorted(sites["stripe.charges.create"].response_fields_read) == ["status"]
    assert sorted(sites["stripe.charges.retrieve"].response_fields_read) == ["amount_refunded"]


@pytest.mark.parametrize("language", BOTH)
def test_the_fix_reaches_the_scope_the_module_fallback_never_answers_for(
    tmp_path, language
) -> None:
    """The control W120 wrote to place the fault, kept because it still places it.

    `nested_function` moves the rebinding one level down: the indexed call sits inside `outer`,
    so `_enclosing_scope` returns `outer` and the fallback to the module is never reached. Its
    result tracked `shadowed` exactly while both leaked and tracks it exactly now that neither
    does, which is what says the repair was made in `_response_fields` and not in the fallback.

    `_enclosing_scope` is unchanged. Returning the module for a module-level call is the right
    answer to the question it is asked; there is no smaller node, and the plain case above
    proves the answer is usable.
    """
    sites = _sites(tmp_path, language)

    assert _fields(sites, "nested_function") == ["status"]
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

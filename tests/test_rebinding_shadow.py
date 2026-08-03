"""Which reads of a bound name belong to the call that bound it, and which belong elsewhere.

`_response_fields` finds the name a call's result is bound to and then collects every read
rooted at that name inside the call's enclosing scope. Until this file it collected them from
the scope's *whole* subtree, so any nested scope that gave the same name a binding of its own
donated its reads to the call --
`docs/superpowers/reports/2026-07-31-module-scope-bindings.md` §3 and §4 measured that at module
scope, at class-body scope and inside a function, in both languages, to the same values.

A recorded field the call never returned is a false `static` binding. `ObservedDriftDetector`
and the vendor-change detectors join findings to call sites through `response_fields_read`, so a
leaked field produces a finding against a site that does not read it. Dropping a field the call
*does* return is the opposite error and it is silent, so every fixture here keeps a genuine read
(`status`) alongside the leaked one and asserts that the genuine one survives.

Two fixtures decide the shape of the fix rather than measure a form. `read_before_rebind` reads
the name *above* the rebinding, which both languages make an error rather than a read of the
outer object -- Python by making the whole body local, TypeScript by the temporal dead zone. So
the walk stops at a rebinding scope rather than skipping only the reads that follow the
rebinding. `closure_read` is the control in the other direction: a nested scope that reads the
name without rebinding it reads *this* call's result, and dropping it would turn a false field
into a missed break.
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

SPEC = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}

PYTHON = "python"
TYPESCRIPT = "typescript"
BOTH = [PYTHON, TYPESCRIPT]

# Every fixture file binds one indexed call to `charge`, reads `charge.status` off it where the
# binding is in force, and reads `charge.leaked` from a nested scope that has given the name a
# binding of its own. `leaked` is the false field; `status` is the one that must survive.
GENUINE = "status"
LEAKED = "leaked"

# The forms each language can spell, named after the construct that rebinds. Python's list is
# the language's own scopes; TypeScript's adds three that are not functions at all, because
# `let` and `const` are block-scoped where nothing in Python is.
PYTHON_FORMS = (
    "parameter",
    "lambda_parameter",
    "for_target",
    "with_as",
    "except_as",
    "comprehension",
    "destructured",
    "augmented",
    "nested_def",
    "class_scope",
)
TYPESCRIPT_FORMS = (
    "parameter",
    "optional_parameter",
    "arrow_parameter",
    "for_of",
    "counted_loop",
    "catch_parameter",
    "switch_case",
    "destructured",
    "array_pattern",
    "bare_block",
    "var_in_function",
    "nested_function",
)

# The forms written to the same shape in both languages, so a claim asserted for one and then
# for the other is a claim about the same program in two spellings.
MATCHED = ("parameter", "destructured", "read_before_rebind", "closure_read")


def _sites(tmp_path, language: str) -> list[CallSite]:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    vendor = StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)

    if language == PYTHON:
        kind, adapter = "py", PythonAdapter(vendor_adapter=vendor)
    else:
        kind, adapter = "ts", TypeScriptAdapter(vendor_adapter=vendor)

    repo = RepoRef(
        repo_id="rebinding",
        url="https://example.invalid/rebinding",
        local_path=str(FIXTURES / kind / "rebinding"),
        head_sha="0" * 40,
    )
    return list(adapter.index(repo))


def _one(sites: list[CallSite], stem: str) -> CallSite:
    found = [site for site in sites if Path(site.path).stem == stem]
    assert len(found) == 1, f"expected one call site in {stem}, got {len(found)}"
    return found[0]


def _fields(tmp_path, language: str, stem: str) -> list[str]:
    return sorted(_one(_sites(tmp_path, language), stem).response_fields_read)


# --- the leak, one rebinding form at a time ------------------------------------------


@pytest.mark.parametrize("form", PYTHON_FORMS)
def test_a_python_rebinding_keeps_its_reads_to_itself(tmp_path, form) -> None:
    """Each of Python's own scopes, rebinding by the construct the fixture is named for.

    All ten recorded `leaked` before this task. Python has no block scope, so every one of them
    rebinds inside a function, a lambda, a comprehension or a class body -- there is no other
    kind of scope for a name to be rebound in.
    """
    assert _fields(tmp_path, PYTHON, form) == [GENUINE]


@pytest.mark.parametrize("form", TYPESCRIPT_FORMS)
def test_a_typescript_rebinding_keeps_its_reads_to_itself(tmp_path, form) -> None:
    """The same claim over TypeScript's scopes, which include blocks.

    `for_of`, `counted_loop`, `catch_parameter`, `switch_case`, `destructured`, `array_pattern`
    and `bare_block` rebind inside the *same function* as the indexed call, in a block. Nothing
    in Python can do that, and a fix ported across unchanged would leave all seven leaking.
    """
    assert _fields(tmp_path, TYPESCRIPT, form) == [GENUINE]


# --- the two decisions the fix rests on ----------------------------------------------


@pytest.mark.parametrize("language", BOTH)
def test_a_read_above_the_rebinding_is_dropped_with_the_rest(tmp_path, language) -> None:
    """Why the walk stops at a rebinding scope rather than skipping the rebound reads.

    `summarise` reads `charge` on the line above the one that rebinds it. Neither language lets
    that reach the outer object: Python makes the name local to the whole body, so the read
    raises `UnboundLocalError`, and TypeScript puts the body in the new binding's temporal dead
    zone, so it throws `ReferenceError`. Recording `leaked` would be a false field on a read
    that cannot be of this call's result, which is exactly the error being removed.

    Skipping only the reads that follow the rebinding would record it.
    """
    assert _fields(tmp_path, language, "read_before_rebind") == [GENUINE]


@pytest.mark.parametrize("language", BOTH)
def test_a_nested_scope_that_only_reads_still_donates(tmp_path, language) -> None:
    """The control, and the error the fix must not make.

    `describe` reads `charge.total` off the binding the indexed call produced -- through the
    closure it is -- and rebinds nothing. That is a genuine dependency on a response field, and
    a fix that skipped nested scopes wholesale would drop it: a missed break, which is silent,
    where the leak it replaced was at least visible as a wrong finding.
    """
    assert _fields(tmp_path, language, "closure_read") == [GENUINE, "total"]


# --- the shape around the change -----------------------------------------------------


@pytest.mark.parametrize("language", BOTH)
def test_the_call_site_and_its_request_fields_are_untouched(tmp_path, language) -> None:
    """A narrowed response side must narrow nothing else.

    The request side never consults a scope, so a fix that moved it would have moved it by
    accident -- and a call site that stopped being indexed at all would make every assertion
    above pass for the wrong reason.
    """
    site = _one(_sites(tmp_path, language), "parameter")

    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert sorted(site.args_keys) == ["amount", "currency"]


def test_no_fixture_here_still_records_the_leaked_field(tmp_path) -> None:
    """One assertion over every file in both trees, so a form added later cannot be added
    without an expectation.

    `leaked` is spelled in no fixture except by a scope that rebound the name, so it appears in
    no correct result at all -- which makes this the cheapest statement of the whole task and
    the one that survives someone rewriting the tables above.
    """
    for language in BOTH:
        for site in _sites(tmp_path, language):
            assert LEAKED not in site.response_fields_read, f"{language} {site.path}"


def test_the_two_languages_agree_on_the_forms_they_share(tmp_path) -> None:
    """Python and TypeScript rebind differently and the fix is not identical in the two, so the
    forms both can spell are where a divergence would show.

    Restricted to those forms on purpose: a comprehension variable and a `catch` parameter are
    each real in one language and unspellable in the other, and comparing them would be
    asserting agreement about two different programs.
    """

    def summarise(language: str) -> list[tuple[str, tuple[str, ...]]]:
        return sorted(
            (Path(site.path).stem, tuple(sorted(site.response_fields_read)))
            for site in _sites(tmp_path, language)
            if Path(site.path).stem in MATCHED
        )

    assert summarise(PYTHON) == summarise(TYPESCRIPT)

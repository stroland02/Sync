"""Alias handling in the Python indexer, which was written and never executed.

`docs/superpowers/specs/2026-07-29-sync-coverage-baseline.md` measured the suite and named this
module first, for a reason rather than a ranking: its uncovered lines are capability rather than
guards. The branches that read `import stripe as s` and `from stripe import StripeClient as C`,
and the one that reads a dictionary passed positionally, had never run -- while
`tests/fixtures/ts/aliased` exists so the TypeScript adapter's alias handling is exercised. The
asymmetry is the whole finding, and the repair is a fixture rather than a redesign.

It matters now rather than as tidying because `PythonAdapter` is wired into the pipeline: a call
site the indexer fails to match costs a finding, and aliasing an import is ordinary Python.

These cases live beside `tests/test_python_index.py` rather than inside it because that file is
another task's to edit; the fixture helpers below are its helpers, duplicated for that reason and
for no other.
"""

from __future__ import annotations

from conftest import symbol_resolver

import json
from pathlib import Path

from sync.core import CallSite, RepoRef
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


def _sites(tmp_path) -> dict[str, CallSite]:
    """Every call site the aliased fixture yields, keyed by the file it came from.

    Keyed rather than ordered because `_source_files` walks the tree with `rglob`, and a test
    that depended on that order would be asserting the filesystem rather than the indexer.
    """
    found = list(_adapter(tmp_path).index(_repo("aliased")))
    return {site.path: site for site in found}


def test_every_aliased_form_in_the_fixture_is_indexed(tmp_path):
    """One assertion for the fixture as a whole: three files, three call sites. A form that
    stops being recognised drops a site here even if the test naming it were deleted."""
    assert sorted(_sites(tmp_path)) == [
        "src/client_alias.py", "src/module_alias.py", "src/positional_dict.py",
    ]


def test_a_module_imported_under_an_alias_is_still_a_client(tmp_path):
    """`import stripe as billing` binds a name that stands for the SDK, and nothing else in the
    file mentions `stripe` again. The plain form has a fixture (`module_client`) and this one had
    none, so the branch reading the alias out of the import had never run against real source --
    in a repository written this way every call site is missed and every finding with it.
    """
    site = _sites(tmp_path)["src/module_alias.py"]

    # The symbol is the SDK's, not the local name: `billing.charges.create` resolves against a
    # map derived from Stripe's own generator input, which never heard of `billing`.
    assert site.symbol == "stripe.charges.create"
    assert site.operation_id == "PostCharges"
    assert site.line == 5
    assert site.args_keys == ["amount", "currency"]
    assert site.response_fields_read == ["status"]


def test_a_client_class_imported_under_an_alias_binds_a_client(tmp_path):
    """`from stripe import StripeClient as Client` then `gateway = Client(...)`: the alias has to
    survive the import to be recognised as the constructor a client variable is assigned from.
    Two steps, and the first is the uncovered one -- if the alias is dropped at the import,
    `gateway` looks like an assignment from an unrelated callable and binds nothing.
    """
    site = _sites(tmp_path)["src/client_alias.py"]

    assert site.symbol == "stripe.charges.retrieve"
    assert site.operation_id == "GetChargesCharge"
    assert site.line == 7
    assert site.args_keys == ["id"]
    assert site.response_fields_read == ["amount"]


def test_a_dictionary_passed_positionally_is_read_like_keyword_arguments(tmp_path):
    """`client.charges.create({"amount": 1, ...})` is how the current Stripe SDK's service
    methods are called, and it carries exactly what the keyword form carries. Read only in the
    keyword form, the request-side paths of a repository written this way are empty, and the
    parameter-deprecation detector joins on those paths -- an empty `args_keys` does not fail,
    it silently matches nothing.

    Every prefix is present for the same reason the keyword form records them: the detector asks
    whether a call site's path leads into a change's.
    """
    site = _sites(tmp_path)["src/positional_dict.py"]

    assert site.symbol == "stripe.charges.create"
    assert site.args_keys == ["amount", "metadata", "metadata.internal_id"]

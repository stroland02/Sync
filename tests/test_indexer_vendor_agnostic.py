"""The indexer finds a second vendor's call sites, or the adapters below it are unreachable.

`docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` names this as the
highest-value defect in the system and says why it was invisible: SIGNAL can discover a
specification for any vendor a generator serves, INDEX could only find call sites for Stripe, and
every indexer test used a Stripe fixture. Six registered vendors plus every watched MCP server
were unbindable -- a vendor whose specification we diff perfectly still produces zero findings,
because nothing in the customer's code is ever bound to it.

The closing condition the spec sets is the first test here: a Twilio call site in a fixture
repository resolves to a Twilio operation, end to end. The Stripe tests that already existed are
the regression that matters most, and `test_sync_index_names_no_vendor` is what stops the next
special case quietly undoing this.

Both languages are exercised against Twilio. The two needed different shapes and
`_sdk_binding` in each adapter says why.
"""

from __future__ import annotations

from conftest import symbol_resolver

from sync.signals.stripe.adapter import StripeAdapter

import ast
import json
from pathlib import Path

import pytest

from sync.core import RepoRef
from sync.index import python_lang, typescript
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.registry import available_vendors
from sync.signals.generated.symbols_stripe_openapi import build_symbol_map as build_stripe_symbols
from sync.signals.twilio.adapter import ProductDocument, TwilioAdapter
from sync.signals.twilio.symbols import build_symbol_map as build_twilio_symbols

FIXTURES = Path(__file__).parent / "fixtures"
TS = FIXTURES / "ts"
PY = FIXTURES / "py"
TWILIO_SHAPE = FIXTURES / "twilio" / "insights_v1_shape.json"

INSIGHTS_V1 = ProductDocument(filename="insights_v1.json", domain="insights", version="v1")

STRIPE_SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/charges/{charge}": {"get": {"operationId": "GetChargesCharge"}},
    }
}


def _repo(root: Path, name: str) -> RepoRef:
    return RepoRef(
        repo_id=name,
        url=f"https://example.invalid/{name}",
        local_path=str(root / name),
        head_sha="0" * 40,
    )


def _twilio_vendor(tmp_path) -> TwilioAdapter:
    """The real adapter over the real product document, not a stub.

    A stub answering `operation_for_symbol` would prove the indexer calls something. The point
    of the closing condition is that a symbol the indexer builds from a customer's source
    reaches an operation id the vendor's own specification declares, so the map is derived here
    the way `registry._prepare_twilio` derives it.
    """
    shape = json.loads(TWILIO_SHAPE.read_text(encoding="utf-8"))
    map_path = tmp_path / "twilio-symbols.json"
    map_path.write_text(
        json.dumps(build_twilio_symbols(shape, INSIGHTS_V1.domain, INSIGHTS_V1.version)),
        encoding="utf-8",
    )
    return TwilioAdapter(
        spec_dir=tmp_path, symbol_map_path=map_path, documents=[INSIGHTS_V1]
    )


def _stripe_vendor(tmp_path) -> object:
    map_path = tmp_path / "stripe-symbols.json"
    map_path.write_text(json.dumps(build_stripe_symbols(STRIPE_SPEC)), encoding="utf-8")
    return symbol_resolver(map_path)


# --- the closing condition ----------------------------------------------------------


def test_a_twilio_call_site_in_typescript_resolves_to_a_twilio_operation(tmp_path):
    """The spec's closing condition, in the language the indexer was written for.

    `ListConference` is ground truth from `twilio-python`'s own `insights/v1/__init__.py`, the
    same source `test_twilio_adapter.py` reads its expectations from -- so this fails if the
    binding stops naming the method a customer actually writes, not merely if it stops
    agreeing with itself.
    """
    adapter = TypeScriptAdapter(vendor_adapter=_twilio_vendor(tmp_path))
    sites = {site.symbol: site for site in adapter.index(_repo(TS, "twilio"))}

    site = sites["twilio.insights.v1.conferences.list"]
    assert site.vendor_id == "twilio"
    assert site.operation_id == "ListConference"
    assert site.path == "src/insights.ts"
    assert site.sdk_version == "5.3.0"
    assert site.args_keys == ["pageSize"]


def test_a_twilio_call_site_in_python_resolves_to_a_twilio_operation(tmp_path):
    """The same condition in the second language, because the two bind clients differently.

    `from twilio.rest import Client` then `Client(...)` is the constructed shape Python shares
    with TypeScript. The module-as-client shape Python also has -- `import stripe` binding no
    variable -- is exercised by the Stripe fixtures and needs the module name rather than the
    distribution name, which is why the Python binding carries both.
    """
    adapter = PythonAdapter(vendor_adapter=_twilio_vendor(tmp_path))
    sites = {site.symbol: site for site in adapter.index(_repo(PY, "twilio"))}

    site = sites["twilio.insights.v1.conferences.list"]
    assert site.vendor_id == "twilio"
    assert site.operation_id == "ListConference"
    assert site.path == "app.py"
    assert site.sdk_version == "9.3.0"
    assert site.args_keys == ["page_size"]


def test_a_camel_cased_mount_resolves_through_the_vendors_own_spelling_rule(tmp_path):
    """`callSummaries` in TypeScript is `call_summaries` in the map.

    The rewrite is `TwilioAdapter._spelled`'s and the indexer knows nothing about it -- it
    hands over the symbol the source spells and takes back an operation or None. Asserted
    because it is the case that proves the indexer is not quietly normalising on the vendor's
    behalf.
    """
    adapter = TypeScriptAdapter(vendor_adapter=_twilio_vendor(tmp_path))
    sites = {site.symbol: site for site in adapter.index(_repo(TS, "twilio"))}

    assert sites["twilio.insights.v1.callSummaries.list"].operation_id == "ListCallSummaries"


def test_a_client_built_by_calling_the_package_is_bound_too(tmp_path):
    """`twilio(sid, token)` is how `twilio-node` documents building a client.

    The rule inherited from Stripe was `new Imported(...)` and nothing else, so the idiomatic
    Twilio shape bound no identifier and every call site under it was invisible. Widening to
    the factory call is driven by a second vendor rather than guessed: the import already had
    to come from the vendor's package, so what is being called is the package's own export.
    """
    adapter = TypeScriptAdapter(vendor_adapter=_twilio_vendor(tmp_path))
    sites = {site.symbol: site for site in adapter.index(_repo(TS, "twilio"))}

    assert sites["twilio.insights.v1.rooms.list"].operation_id == "ListVideoRoomSummary"
    assert sites["twilio.insights.v1.rooms.list"].path == "src/factory.ts"


def test_both_languages_report_the_repository_depends_on_twilio(tmp_path):
    vendor = _twilio_vendor(tmp_path)
    assert TypeScriptAdapter(vendor_adapter=vendor).matches(_repo(TS, "twilio")) is True
    assert PythonAdapter(vendor_adapter=vendor).matches(_repo(PY, "twilio")) is True


# --- the regression that matters most -----------------------------------------------


def test_stripe_still_resolves_in_typescript(tmp_path):
    """Every indexer test in the suite uses a Stripe fixture, which is exactly why they were
    not enough -- and exactly why they must all still pass."""
    adapter = TypeScriptAdapter(vendor_adapter=_stripe_vendor(tmp_path))
    sites = list(adapter.index(_repo(TS, "simple")))

    assert [site.symbol for site in sites] == ["stripe.charges.create"]
    assert sites[0].operation_id == "PostCharges"


def test_stripe_still_resolves_in_python(tmp_path):
    """The module-as-client shape. `import stripe` binds no variable, so the module name is
    the client root -- the one place the two languages could not share a parameter."""
    adapter = PythonAdapter(vendor_adapter=_stripe_vendor(tmp_path))
    sites = list(adapter.index(_repo(PY, "simple")))

    assert [site.symbol for site in sites] == ["stripe.charges.create"]


# --- no fallback, in either direction -----------------------------------------------


def test_a_repository_depending_on_neither_vendor_yields_no_call_sites(tmp_path):
    """It must produce nothing rather than fall back to Stripe. A fallback would file another
    vendor's traffic under Stripe operations, which is a finding against an API the customer
    does not call."""
    for vendor in (_twilio_vendor(tmp_path), _stripe_vendor(tmp_path)):
        assert TypeScriptAdapter(vendor_adapter=vendor).matches(_repo(TS, "no_stripe")) is False
        assert list(TypeScriptAdapter(vendor_adapter=vendor).index(_repo(TS, "no_stripe"))) == []
        assert PythonAdapter(vendor_adapter=vendor).matches(_repo(PY, "no_stripe")) is False
        assert list(PythonAdapter(vendor_adapter=vendor).index(_repo(PY, "no_stripe"))) == []


def test_a_twilio_repository_is_not_indexed_by_the_stripe_adapter(tmp_path):
    """The other direction of the same rule. A Twilio repository handed the Stripe vendor must
    read as "not this vendor's", not as a repository with no call sites in it."""
    vendor = _stripe_vendor(tmp_path)
    assert TypeScriptAdapter(vendor_adapter=vendor).matches(_repo(TS, "twilio")) is False
    assert list(TypeScriptAdapter(vendor_adapter=vendor).index(_repo(TS, "twilio"))) == []
    assert PythonAdapter(vendor_adapter=vendor).matches(_repo(PY, "twilio")) is False
    assert list(PythonAdapter(vendor_adapter=vendor).index(_repo(PY, "twilio"))) == []


class _RenamedVendor:
    """A vendor whose id is nothing like the package a customer imports.

    Both registered vendors spell the two alike, which is a coincidence of this catalogue and
    not a rule -- `@anthropic-ai/sdk` is the counterexample already on the roster. Without a
    double that separates them, building the symbol from `vendor_id` instead of the declared
    package passes every other test in this file.
    """

    vendor_id = "acme-billing"
    sdk_bindings = {
        "typescript": {"package": "stripe"},
        "python": {"distribution": "stripe", "module": "stripe"},
    }

    def __init__(self) -> None:
        self.asked: list[str] = []

    def fetch_changes(self, from_version, to_version):
        return []

    def operation_for_symbol(self, symbol, *, language=None):
        self.asked.append(symbol)
        return None


@pytest.mark.parametrize("adapter_type, root", [(TypeScriptAdapter, TS), (PythonAdapter, PY)])
def test_the_symbol_is_rooted_at_the_package_not_at_the_vendor_id(adapter_type, root):
    """The symbol is what the customer wrote, so it is rooted at what they imported.

    A vendor id is an identity this system chose; a package name is a string in someone else's
    source. Rooting the symbol at the id would produce `acme-billing.charges.create`, which
    matches nothing in any symbol map and which no map could be keyed by without the vendor
    knowing what we decided to call them.
    """
    vendor = _RenamedVendor()
    list(adapter_type(vendor_adapter=vendor).index(_repo(root, "simple")))

    assert vendor.asked == ["stripe.charges.create"]


class _NoPackageVendor:
    """A vendor whose adapter declares no SDK package -- every generated and MCP vendor today."""

    vendor_id = "unbound"

    def fetch_changes(self, from_version, to_version):
        return []

    def operation_for_symbol(self, symbol, *, language=None):
        raise AssertionError("an unbound vendor must never be asked to resolve a symbol")


def test_an_adapter_declaring_no_package_indexes_nothing_rather_than_defaulting():
    """Four configured vendors and every watched MCP server are in this position right now.

    Declining is the honest answer and defaulting to Stripe is the defect this task removes,
    so the absence has to fail closed. Asserted against the *Stripe* fixtures deliberately:
    those are the repositories a lingering default would bind, so a fallback shows up here as
    a match and a resolved call site rather than as nothing happening.
    `operation_for_symbol` raises rather than returning None, because a test that let it be
    called could not tell "declined" from "resolved nothing".
    """
    vendor = _NoPackageVendor()
    for adapter, root in (
        (TypeScriptAdapter(vendor_adapter=vendor), TS),
        (PythonAdapter(vendor_adapter=vendor), PY),
    ):
        assert adapter.matches(_repo(root, "simple")) is False
        assert list(adapter.index(_repo(root, "simple"))) == []


# --- the property the next special case will undo ------------------------------------


def _code_strings_and_names(path: Path) -> set[str]:
    """Every string literal and identifier in a module, with prose removed.

    Docstrings are stripped rather than searched, because this package explains Stripe's and
    Twilio's binding shapes at length and must go on being allowed to: naming a vendor to
    describe why two languages differ is the documentation working. What must not survive is a
    name that *decides* anything -- a constant, a literal, an attribute.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose:
            found.add(node.value)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
    return found


@pytest.mark.parametrize(
    "module_path",
    sorted(Path(typescript.__file__).parent.glob("*.py")),
    ids=lambda p: p.name,
)
def test_sync_index_names_no_vendor(module_path: Path):
    """No vendor id decides anything in `sync.index`.

    Asserted rather than left to review, because this is precisely the property the next
    person adding a special case will undo without noticing. The vendor list comes from the
    registry rather than being written here, so a vendor registered tomorrow is covered
    without anyone remembering to add it.
    """
    registered = {vendor.split(":")[-1].lower() for vendor in available_vendors()}
    assert "stripe" in registered, "the registry stopped naming the vendor this defect was about"

    offending = {
        token: vendor
        for token in _code_strings_and_names(module_path)
        for vendor in registered
        if vendor in token.lower()
    }
    assert offending == {}, f"{module_path.name} decides behaviour on a vendor name: {offending}"


def test_the_binding_each_language_reads_is_declared_by_the_vendor():
    """Where the package name now comes from, asserted so it cannot drift back to a constant.

    Both hand-written adapters declare it and the two languages read different fields out of
    it, which is the finding this task produced: TypeScript needs one npm name that is both
    the manifest key and the import specifier, and Python needs a distribution name for the
    manifest and a module name for the import, because those are different strings in general.
    """
    stripe_binding = StripeAdapter.sdk_bindings
    twilio_binding = TwilioAdapter.sdk_bindings

    assert stripe_binding[typescript.TypeScriptAdapter.language_id]["package"] == "stripe"
    assert twilio_binding[typescript.TypeScriptAdapter.language_id]["package"] == "twilio"

    assert stripe_binding[python_lang.PythonAdapter.language_id]["distribution"] == "stripe"
    assert stripe_binding[python_lang.PythonAdapter.language_id]["module"] == "stripe"
    assert twilio_binding[python_lang.PythonAdapter.language_id]["distribution"] == "twilio"

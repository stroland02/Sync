"""An emitted symbol is rooted at the symbol root, not at the package name.

`typescript.py` built its symbol as `f"{self._package}.{...}"`, where `_package` is the npm
name a manifest declares. For `stripe` and `twilio` that is right, because their npm package,
PyPI distribution, module and symbol root are all the same string. For a scoped package it is
wrong: a customer calling `@anthropic-ai/sdk` emitted `@anthropic-ai/sdk.messages.create`, and
no symbol map holds that key.

The failure was silent in the worst way. The vendor resolves, the manifest matches, the call
site is found, and only the operation lookup fails -- so a repository that calls Anthropic
looks exactly like one that does not. It survived two independent implementations of the
indexer and a green suite because no fixture in this repository declared a scoped npm package;
`tests/fixtures/ts/scoped/` is named for a different kind of scoping and declares plain
`stripe`.

`docs/superpowers/reports/b17-multi-vendor-index.md` has the shape: four names that come apart
independently, and only Stripe collapses them.

    | vendor id | package (manifest) | module (source) | symbol root |
    | stripe    | stripe             | stripe          | stripe      |
    | slack     | @slack/web-api     | @slack/web-api  | slack       |
    | slack     | slack-sdk          | slack_sdk       | slack       |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.core import OperationRef, RepoRef
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.generated.adapter import bindings_for

TS = Path(__file__).parent / "fixtures" / "ts"
PY = Path(__file__).parent / "fixtures" / "py"


def _repo(root: Path, name: str) -> RepoRef:
    return RepoRef(
        repo_id=name, url=f"https://example.invalid/{name}",
        local_path=str(root / name), head_sha="0" * 40,
    )


class StubVendor:
    """A vendor adapter that declares bindings and resolves exactly one symbol.

    The symbol it resolves is supplied by the test, so a call site that emitted a differently
    rooted symbol resolves to nothing -- which is what makes the resolution assertions test the
    root rather than test the stub.
    """

    def __init__(self, vendor_id: str, sdk_bindings, resolves: str | None = None) -> None:
        self.vendor_id = vendor_id
        self.sdk_bindings = sdk_bindings
        self._resolves = resolves
        self.asked: list[str] = []

    def fetch_changes(self, from_version, to_version):
        return []

    def operation_for_symbol(self, symbol, *, language=None):
        self.asked.append(symbol)
        if self._resolves is not None and symbol == self._resolves:
            return OperationRef(
                operation_id="messages_create", http_method="POST", path="/v1/messages"
            )
        return None


ANTHROPIC_BINDING = {
    "typescript": {"package": "@anthropic-ai/sdk", "symbol_root": "anthropic"},
}


# --- the fixture that did not exist -------------------------------------------------


def test_a_scoped_package_emits_a_symbol_rooted_at_the_symbol_root():
    """The defect, at the level it is visible. Against the unfixed indexer this emits
    `@anthropic-ai/sdk.messages.create`, which is a string no symbol map can hold."""
    vendor = StubVendor("anthropic", ANTHROPIC_BINDING, resolves="anthropic.messages.create")
    list(TypeScriptAdapter(vendor).index(_repo(TS, "scoped_package")))

    assert vendor.asked == ["anthropic.messages.create"]


def test_the_scoped_package_name_never_reaches_a_symbol():
    """Stated separately, because the root being right and the package leaking in somewhere
    else are different failures and only one of them is caught by the assertion above."""
    vendor = StubVendor("anthropic", ANTHROPIC_BINDING, resolves="anthropic.messages.create")
    list(TypeScriptAdapter(vendor).index(_repo(TS, "scoped_package")))

    assert not any("@anthropic-ai" in symbol for symbol in vendor.asked)


def test_a_scoped_vendor_s_call_site_resolves_to_an_operation():
    """End to end, because a symbol that is correctly shaped and matches no map is the same
    failure wearing a better name."""
    vendor = StubVendor("anthropic", ANTHROPIC_BINDING, resolves="anthropic.messages.create")
    sites = list(TypeScriptAdapter(vendor).index(_repo(TS, "scoped_package")))

    assert len(sites) == 1
    assert sites[0].symbol == "anthropic.messages.create"
    assert sites[0].operation_id == "messages_create"
    assert sites[0].vendor_id == "anthropic"


def test_the_scoped_manifest_still_matches_on_the_package_name():
    """The root changes what a symbol is rooted at and nothing about what a manifest declares.
    A fix that rooted the manifest match at the symbol root too would stop matching the
    repository at all."""
    vendor = StubVendor("anthropic", ANTHROPIC_BINDING)

    assert TypeScriptAdapter(vendor).matches(_repo(TS, "scoped_package")) is True


# --- the default, which is what makes this additive ---------------------------------


def test_a_typescript_binding_declaring_no_symbol_root_gets_the_package_name():
    vendor = StubVendor("acme", {"typescript": {"package": "acme-sdk"}})

    assert TypeScriptAdapter(vendor)._symbol_root == "acme-sdk"


def test_a_declared_binding_omitting_the_symbol_root_does_not_acquire_a_guess():
    """The rule inherited from the fallback reconciliation, applied one field down: a vendor
    that declares a language and omits the symbol root gets the package-name default, not a
    value derived from its id or from another language."""
    vendor = StubVendor("anthropic", {"typescript": {"package": "@anthropic-ai/sdk"}})

    assert TypeScriptAdapter(vendor)._symbol_root == "@anthropic-ai/sdk"


def test_a_vendor_that_declared_nothing_gets_its_id_as_the_symbol_root():
    """The property that made the fallback acceptable at all: package, module and symbol root
    all equal the vendor id, which is right for an unscoped vendor and fails to resolve rather
    than resolving wrongly for a scoped one."""
    binding = bindings_for("acme", None)
    typescript = StubVendor("acme", binding)
    python = StubVendor("acme", binding)

    assert TypeScriptAdapter(typescript)._symbol_root == "acme"
    assert PythonAdapter(python)._symbol_root == "acme"


# --- Stripe and Twilio emit exactly what they emitted before -------------------------


def test_stripe_emits_the_symbol_it_has_always_emitted():
    """A default that silently altered these fails here rather than in an acceptance run."""
    from sync.signals.registry import vendor_sdk_bindings

    vendor = StubVendor("stripe", vendor_sdk_bindings()["stripe"])
    list(TypeScriptAdapter(vendor).index(_repo(TS, "simple")))

    assert vendor.asked == ["stripe.charges.create"]


def test_twilio_emits_the_symbol_it_has_always_emitted():
    from sync.signals.registry import vendor_sdk_bindings

    vendor = StubVendor("twilio", vendor_sdk_bindings()["twilio"])
    asked = []
    for language, root, fixture in (
        (TypeScriptAdapter, TS, "twilio"),
        (PythonAdapter, PY, "twilio"),
    ):
        probe = StubVendor("twilio", vendor_sdk_bindings()["twilio"])
        list(language(probe).index(_repo(root, fixture)))
        asked.append(probe.asked)

    assert all(symbol.startswith("twilio.") for group in asked for symbol in group)
    assert all(group for group in asked), "both fixtures should have produced a symbol"
    assert vendor is not None


@pytest.mark.parametrize("vendor_id,expected_root", [("stripe", "stripe"), ("twilio", "twilio")])
def test_the_two_original_vendors_root_where_they_always_did(vendor_id, expected_root):
    """Read from wherever each vendor declares it today rather than from a class.

    `CI-W586` moved stripe's declaration from `StripeAdapter.sdk_bindings` to its configuration
    row, and this asserts the root is unchanged by that move -- which is the only thing about it
    a call site can observe.
    """
    from sync.signals.registry import vendor_sdk_bindings

    bindings = vendor_sdk_bindings()[vendor_id]

    assert TypeScriptAdapter(StubVendor(vendor_id, bindings))._symbol_root == expected_root
    assert PythonAdapter(StubVendor(vendor_id, bindings))._symbol_root == expected_root


# --- Python: the same field, a different default, and the reason ---------------------


def test_python_roots_a_symbol_at_the_module_and_not_at_the_distribution():
    """Python's default is the module rather than the distribution, and that is the whole
    reason it did not carry TypeScript's defect.

    An npm package name *is* its import specifier, so rooting at the package put
    `@anthropic-ai/sdk` into a symbol. A Python distribution is not importable -- PEP 503 folds
    `_` to `-` in a requirement and never in an `import` -- so `python_lang` already rooted at
    the module, which is always a valid identifier. Defaulting this field to the distribution
    would have *introduced* the defect on the Python side rather than fixing it: `slack-sdk` is
    not a symbol root any map could hold.
    """
    slack = StubVendor(
        "slack", {"python": {"distribution": "slack-sdk", "module": "slack_sdk"}}
    )
    adapter = PythonAdapter(slack)

    assert adapter._symbol_root == "slack_sdk"
    assert adapter._distribution == "slack-sdk"


def test_python_honours_a_declared_symbol_root_over_the_module():
    """The residual defect Python did have, weaker than TypeScript's and real: a module name
    and a symbol root are still different strings in general, so a map keying on `slack` is not
    reachable from a module named `slack_sdk` without this field."""
    slack = StubVendor(
        "slack",
        {"python": {"distribution": "slack-sdk", "module": "slack_sdk", "symbol_root": "slack"}},
    )

    assert PythonAdapter(slack)._symbol_root == "slack"


def test_a_declared_python_symbol_root_reaches_the_emitted_symbol():
    """The assertion that would have caught the Python defect if the module were the wrong
    root, so the conclusion is checked rather than asserted in prose."""
    vendor = StubVendor(
        "stripe",
        {"python": {"distribution": "stripe", "module": "stripe", "symbol_root": "billing"}},
    )
    list(PythonAdapter(vendor).index(_repo(PY, "simple")))

    assert vendor.asked
    assert all(symbol.startswith("billing.") for symbol in vendor.asked)


# --- what the configured vendors now emit -------------------------------------------


def test_the_two_scoped_configured_vendors_declare_a_symbol_root():
    """`@anthropic-ai/sdk` and `@vercel/sdk` are the two configured packages a default cannot
    serve, and a scoped root is one no map can ever hold."""
    import yaml

    from sync.signals.registry import GENERATED_VENDORS_FILE

    entries = {
        entry["vendor_id"]: entry
        for entry in yaml.safe_load(GENERATED_VENDORS_FILE.read_text(encoding="utf-8"))
    }

    for vendor_id in ("anthropic", "vercel"):
        typescript = entries[vendor_id]["sdk_bindings"]["typescript"]
        assert typescript["package"].startswith("@")
        assert typescript["symbol_root"] == vendor_id


def test_the_unscoped_configured_vendors_need_no_symbol_root():
    """Declaring one where the default already answers correctly would be configuration that
    says nothing, and one more place to disagree with itself."""
    import yaml

    from sync.signals.registry import GENERATED_VENDORS_FILE

    entries = {
        entry["vendor_id"]: entry
        for entry in yaml.safe_load(GENERATED_VENDORS_FILE.read_text(encoding="utf-8"))
    }

    for vendor_id in ("openai", "cloudflare"):
        typescript = entries[vendor_id]["sdk_bindings"]["typescript"]
        assert "symbol_root" not in typescript
        assert typescript["package"] == vendor_id

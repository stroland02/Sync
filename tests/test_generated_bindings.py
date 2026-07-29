"""SDK bindings for the generated tier, so a configured vendor can be watched at all.

`sync.index` no longer holds a vendor name: it reads `sdk_bindings` off whatever adapter it is
given. Stripe and Twilio declare one. `GeneratedSpecAdapter` did not, so the four vendors
`generated-vendors.yaml` configures -- anthropic, openai, cloudflare, vercel -- resolved through
the registry and matched nothing in a customer's repository. Adding a vendor by configuration
was the coverage argument, and it bought a vendor that could be diffed and never matched.

The rule these tests pin, inherited rather than re-derived:

    The fallback applies only to a vendor that declared nothing, and a vendor that declared
    bindings has spoken completely. A declared mapping missing a language yields no binding for
    that language rather than falling back -- because the vendor with a `@scope/name` package is
    exactly the vendor for whom the guess is wrong.

Anthropic is the worked example and this repository now carries the evidence: on PyPI the
distribution is `anthropic` and a fallback resolves; on npm the package is `@anthropic-ai/sdk`
and a fallback fails, silently and safely. One vendor, two languages, and a `vendor_id`-derived
default is right for one and wrong for the other.

What a binding does and does not buy
------------------------------------
It makes a repository *match* the vendor and makes the indexer look for its client. It does not
make a call site resolve to an operation: `GeneratedSpecAdapter.operation_for_symbol` answers
`None` by design -- mapping `acme.charges.create` onto an operation needs one generator's naming
scheme for one vendor, which is the per-vendor knowledge that adapter exists to do without --
and both indexers skip a call whose symbol resolves to nothing. So `test_a_configured_vendor_s_
call_site_is_found` supplies that one missing piece locally and says so; everything else here
runs against the real adapter.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from sync.core import OperationRef, RepoRef
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.signals.generated.adapter import GeneratedSpecAdapter
from sync.signals.registry import GENERATED_VENDORS_FILE

REPOS = Path(__file__).parent / "fixtures" / "generated_repos"
PACKAGES = Path(__file__).parent / "fixtures" / "sdk_packages"


def _repo(name: str) -> RepoRef:
    return RepoRef(
        repo_id=name, url=f"https://example.invalid/{name}",
        local_path=str(REPOS / name), head_sha="0" * 40,
    )


def _generated(vendor_id: str, sdk_bindings=None) -> GeneratedSpecAdapter:
    """The real adapter, with nothing fetched. Only the binding is under test here."""
    return GeneratedSpecAdapter(
        vendor_id=vendor_id, sources={}, fetch=lambda url: "",
        cache_dir=REPOS, sdk_bindings=sdk_bindings,
    )


def _configured() -> dict[str, dict]:
    """What `generated-vendors.yaml` declares, keyed by vendor id."""
    import yaml

    entries = yaml.safe_load(GENERATED_VENDORS_FILE.read_text(encoding="utf-8"))
    return {entry["vendor_id"]: entry for entry in entries}


# --- a configured vendor is recognised at all --------------------------------------


def test_a_configured_vendor_is_recognised_as_a_dependency_of_a_repository():
    """The step that was missing. Until the adapter declared a package, `matches` answered
    False for every configured vendor, so no repository was ever indexed for one."""
    adapter = TypeScriptAdapter(_generated("openai"))

    assert adapter.matches(_repo("openai_ts")) is True


def test_a_configured_vendor_is_recognised_from_a_python_requirement():
    adapter = PythonAdapter(_generated("anthropic"))

    assert adapter.matches(_repo("anthropic_py")) is True


def test_a_configured_vendor_s_call_site_is_found():
    """End to end through the indexer, with the one piece the generated tier does not have.

    `GeneratedSpecAdapter.operation_for_symbol` answers `None` by design, and both indexers
    skip a call whose symbol resolves to nothing -- so a binding alone yields no call site and
    this subclass supplies the resolution locally rather than the test pretending the tier has
    it. What is being tested is that the binding reaches the indexer: against the unmodified
    adapter this fails at `matches`, before symbol resolution is ever reached.
    """

    class Resolving(GeneratedSpecAdapter):
        def operation_for_symbol(self, symbol, *, language=None):
            if symbol == "openai.chat.completions.create":
                return OperationRef(
                    operation_id="createChatCompletion",
                    http_method="POST", path="/chat/completions",
                )
            return None

    vendor = Resolving(
        vendor_id="openai", sources={}, fetch=lambda url: "", cache_dir=REPOS,
    )
    sites = list(TypeScriptAdapter(vendor).index(_repo("openai_ts")))

    assert [site.symbol for site in sites] == ["openai.chat.completions.create"]
    assert sites[0].operation_id == "createChatCompletion"
    assert sites[0].vendor_id == "openai"


# --- the fallback, and the exact edge of it ----------------------------------------


def test_a_vendor_that_declared_nothing_falls_back_to_its_own_id():
    """The economics the tier rests on: one configuration line adds a vendor. Without a
    fallback a vendor added tomorrow with no binding line binds nothing, which restores the
    defect quietly."""
    adapter = TypeScriptAdapter(_generated("openai", sdk_bindings=None))

    assert adapter.matches(_repo("openai_ts")) is True


def test_the_fallback_fails_to_resolve_rather_than_resolving_wrongly():
    """The whole answer to the objection that a fallback is a guess.

    `acme` publishes `@acme/sdk`. The guess is `acme`, the manifest declares no package by that
    name, the match returns False and nothing binds. It cannot bind to the wrong vendor,
    because a symbol rooted at the wrong name is in no vendor's map.
    """
    adapter = TypeScriptAdapter(_generated("acme", sdk_bindings=None))

    assert adapter.matches(_repo("acme_scoped_ts")) is False


def test_a_declared_mapping_missing_a_language_yields_no_binding_for_that_language():
    """The rule, asserted rather than trusted. `vercel/sdk` has no Python target at all -- a
    package.json and a tsconfig and no pyproject -- so vercel declares typescript only. A
    fallback to `vercel` for Python would be inventing a distribution that does not exist.
    """
    vercel = _generated("vercel", sdk_bindings={"typescript": {"package": "@vercel/sdk"}})

    assert PythonAdapter(vercel).matches(_repo("vercel_py")) is False


def test_a_vendor_that_declared_one_language_still_binds_that_one():
    """The other half of the same rule: declaring incompletely must not cost the language that
    was declared."""
    vercel = _generated("vercel", sdk_bindings={"typescript": {"package": "@vercel/sdk"}})

    assert TypeScriptAdapter(vercel)._package == "@vercel/sdk"


def test_a_declaration_is_never_topped_up_by_the_fallback():
    """A vendor that has spoken has spoken completely. Filling the gap would restore the guess
    one level above where it was removed."""
    anthropic = _generated(
        "anthropic", sdk_bindings={"python": {"distribution": "anthropic", "module": "anthropic"}}
    )

    assert "typescript" not in anthropic.sdk_bindings
    assert TypeScriptAdapter(anthropic)._package is None


# --- PEP 503 applies to the distribution and not to the module ---------------------


def test_a_distribution_is_matched_under_pep_503_normalisation():
    """`slack-sdk` is the distribution and the fixture declares `slack_sdk`, which PEP 503
    says is the same name. This fails if the distribution were compared literally."""
    slack = _generated(
        "slack", sdk_bindings={"python": {"distribution": "slack-sdk", "module": "slack_sdk"}}
    )

    assert PythonAdapter(slack).matches(_repo("slack_py")) is True


def test_a_module_is_not_normalised_the_way_a_distribution_is():
    """`import slack_sdk` is spelled exactly as it is imported. Normalising the module the way
    the distribution is normalised would look for `slack-sdk`, which is not importable and
    appears in no source file -- so this fails if either were normalised the other way.
    """
    slack = _generated(
        "slack", sdk_bindings={"python": {"distribution": "slack-sdk", "module": "slack_sdk"}}
    )
    adapter = PythonAdapter(slack)

    assert adapter._module == "slack_sdk"
    assert adapter._distribution == "slack-sdk"


def test_a_module_declared_with_a_hyphen_finds_nothing_because_nothing_imports_one():
    """The direction that proves the previous assertion is not vacuous."""
    wrong = _generated(
        "slack", sdk_bindings={"python": {"distribution": "slack-sdk", "module": "slack-sdk"}}
    )

    assert PythonAdapter(wrong)._module == "slack-sdk"
    assert not list(PythonAdapter(wrong).index(_repo("slack_py")))


# --- the hand-written adapters are unaffected --------------------------------------


def test_stripe_still_declares_both_languages():
    from sync.signals.stripe.adapter import StripeAdapter

    assert StripeAdapter.sdk_bindings["typescript"] == {"package": "stripe"}
    assert StripeAdapter.sdk_bindings["python"] == {
        "distribution": "stripe", "module": "stripe",
    }


def test_twilio_still_declares_both_languages():
    from sync.signals.twilio.adapter import TwilioAdapter

    assert TwilioAdapter.sdk_bindings["typescript"] == {"package": "twilio"}
    assert TwilioAdapter.sdk_bindings["python"] == {
        "distribution": "twilio", "module": "twilio",
    }


# --- every configured name was confirmed, and the evidence is checked in -----------


@pytest.mark.parametrize(
    "vendor_id,fixture,expected",
    [
        ("anthropic", "anthropic-sdk-typescript.package.json", "@anthropic-ai/sdk"),
        ("openai", "openai-node.package.json", "openai"),
        ("cloudflare", "cloudflare-typescript.package.json", "cloudflare"),
        ("vercel", "vercel-sdk.package.json", "@vercel/sdk"),
    ],
)
def test_each_declared_npm_package_matches_the_sdk_s_own_manifest(vendor_id, fixture, expected):
    """A binding nobody checked is worse than none, because it moves a vendor from
    honestly-unwatchable to apparently-watched.

    The evidence is each SDK repository's own `package.json`, fetched once and committed here,
    rather than a package registry's index of it -- the artifact the vendor publishes rather
    than a third party's copy. This test is what stops the YAML drifting away from it.
    """
    manifest = json.loads((PACKAGES / fixture).read_text(encoding="utf-8"))
    declared = _configured()[vendor_id]["sdk_bindings"]["typescript"]["package"]

    assert manifest["name"] == expected
    assert declared == expected


@pytest.mark.parametrize(
    "vendor_id,fixture,expected",
    [
        ("anthropic", "anthropic-sdk-python.pyproject.toml", "anthropic"),
        ("openai", "openai-python.pyproject.toml", "openai"),
        ("cloudflare", "cloudflare-python.pyproject.toml", "cloudflare"),
    ],
)
def test_each_declared_distribution_matches_the_sdk_s_own_pyproject(vendor_id, fixture, expected):
    project = tomllib.loads((PACKAGES / fixture).read_text(encoding="utf-8"))
    declared = _configured()[vendor_id]["sdk_bindings"]["python"]["distribution"]

    assert project["project"]["name"] == expected
    assert declared == expected


def test_vercel_declares_no_python_binding_because_its_sdk_has_no_python_target():
    """Recorded as a test rather than a comment: the reason vercel is typescript-only is a
    fact about the repository, and a later editor adding a python line would be inventing a
    distribution that does not exist."""
    assert "python" not in _configured()["vercel"]["sdk_bindings"]


def test_every_configured_vendor_declares_at_least_one_binding():
    """The count this task exists to move. A configured vendor with no binding is one that can
    be diffed and never matched."""
    for vendor_id, entry in _configured().items():
        assert entry.get("sdk_bindings"), f"{vendor_id} declares no sdk_bindings"


# --- the declaration reaches the adapter the registry builds -----------------------


def test_the_registry_hands_the_adapter_what_the_file_declares():
    """A declaration the adapter cannot read is inert, which is the built-but-unwired shape
    this task exists to remove rather than reproduce one level down."""
    from sync.signals.registry import _generated_vendors

    vendors = _generated_vendors()

    # Compared against the file rather than against a copy of it written here. Pinning one
    # vendor's mapping literally caught a dropped field and also broke on an added one -- the
    # property is that the declaration arrives intact, and a field this test had never heard of
    # going missing is exactly the failure it exists to catch.
    for vendor_id, entry in _configured().items():
        assert vendors[vendor_id].sdk_bindings == entry["sdk_bindings"]

    assert vendors["anthropic"].sdk_bindings["typescript"]["package"] == "@anthropic-ai/sdk"
    assert "python" not in vendors["vercel"].sdk_bindings

"""Which shapes count as a Stripe client, and which deliberately do not.

`2026-07-29-python-corpus-has-no-repository-to-pin.md` indexed seventeen candidate repositories
with the shipped adapter: **sixteen bound nothing at all** and the seventeenth bound one call. The
adapter recognised a client only when it was a bare imported name, and two rules account for most
of the gap.

`client = stripe.StripeClient(key)` is what Stripe's own Python documentation tells people to
write, and it bound nothing — the constructor is a module attribute rather than an imported name.
That rule alone moves eleven of the seventeen repositories from zero.

`self.client.customers.create(...)` is how production code is written, and it bound nothing —
the chain is rooted at `self`, which is not a client name. It is also the shape the corpus most
wants, because a repository worth pinning is one with a class around its Stripe usage.

The negative cases carry as much weight as the positive ones. A rule loose enough to match any
`x.Something(...)` would attribute unrelated calls to Stripe, which is the false attribution this
module was fixed for twice today at the field step; reintroducing it at the binding step would be
worse, because a wrongly bound call site produces findings against code that never called the
vendor at all.

Symbols here are `charges.create`, which the fixture's own specification resolves. Whether a
*real* symbol reaches an operation is a separate defect — 93 of 179 symbols are unreachable from
Python — and is not what these assertions are about.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core import RepoRef
from sync.index.python_lang import PythonAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "py" / "client_forms"

SPEC = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}


@pytest.fixture
def adapter(tmp_path) -> PythonAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    return PythonAdapter(
        vendor_adapter=StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)
    )


def _bound(adapter: PythonAdapter) -> dict[str, str]:
    """Every call the adapter binds in the fixture, as path -> symbol."""
    repo = RepoRef(
        repo_id="client_forms", url="https://example.invalid/client_forms",
        local_path=str(FIXTURE), head_sha="0" * 40,
    )
    return {site.path: site.symbol for site in adapter.index(repo)}


# --- the two shapes the measurement named -------------------------------------------


def test_a_client_constructed_from_a_module_attribute_binds(adapter) -> None:
    """`billing = stripe.StripeClient(key)` — the form Stripe's own documentation uses, and the
    one rule that moves eleven of seventeen repositories off zero."""
    assert _bound(adapter).get("src/module_attribute.py") == "stripe.charges.create"


def test_a_receiver_that_is_an_attribute_of_self_binds(adapter) -> None:
    """`self.payments.charges.create(...)` inside a class. The chain is rooted at `self`, so the
    client is two segments rather than one, and the symbol is built from what follows them."""
    assert _bound(adapter).get("src/self_attribute.py") == "stripe.charges.create"


def test_a_module_level_singleton_used_from_another_file_binds(adapter) -> None:
    """Constructed in one module and imported into another. Client names accumulate across the
    repository rather than per file, which is what makes this work — and is the same
    name-matching that makes a renamed re-export impossible."""
    assert _bound(adapter).get("src/singleton_use.py") == "stripe.charges.create"


# --- what must not bind --------------------------------------------------------------


def test_a_constructor_on_another_module_does_not_bind(adapter) -> None:
    """`bucket = boto3.client("s3")` is a module-attribute construction of something that is not
    Stripe. The rule keys on the object being the vendor's own module, so a call chain that
    happens to spell `charges.create` on it is not attributed to the vendor."""
    assert "src/foreign_module.py" not in _bound(adapter)


def test_the_vendor_class_name_on_a_foreign_module_does_not_bind(adapter) -> None:
    """The sharper version: the constructor is spelled `StripeClient` and the module is not
    Stripe's. Matching on the attribute name would bind it, which is why the object is what is
    checked."""
    assert "src/foreign_constructor.py" not in _bound(adapter)


def test_a_client_only_received_as_a_parameter_does_not_bind(adapter) -> None:
    """The adjacent form left unfixed, asserted so the boundary is read rather than discovered.

    `def __init__(self, given): self.given = given` stores something the constructor was handed,
    and nothing statically says it is a Stripe client — the right-hand side is a parameter name.
    Binding on it would mean any attribute assigned from any parameter counted, which is the
    loose rule this file must not acquire. Closing it needs the caller's type, which tree-sitter
    does not give us.
    """
    assert "src/injected.py" not in _bound(adapter)


# --- the shapes that already worked --------------------------------------------------


def test_the_imported_name_form_still_binds(adapter) -> None:
    """`from stripe import StripeClient` then `client = StripeClient(...)`, which is the one form
    the adapter recognised before and the seventeenth repository's single bound call."""
    repo = RepoRef(
        repo_id="simple", url="https://example.invalid/simple",
        local_path=str(FIXTURES / "py" / "simple"), head_sha="0" * 40,
    )
    assert [site.symbol for site in adapter.index(repo)] == ["stripe.charges.create"]

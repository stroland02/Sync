"""Generating a labelled pair from a Python call site, and the routing lie that must not be told.

The corpus has never measured Python. The binder side is finished -- B38 taught it the client
shapes Stripe documents and B39 gave the symbol map the Python spelling -- and a qualifying
repository is waiting. `sync.benchmark.mutate` was the last thing in the way: it asked
`sync.route.templates.language_for`, which answers `None` for `.py`, so every Python target
recorded unreachable and the tree came back unedited on both change kinds.

**Adding `.py` to that table would have been the wrong fix and the defect it introduces is
silent.** `language_for` belongs to the router, and its own docstring says why it lives there:
the routing decision and the edit have to agree, or work routes to a tier that cannot take it.
Its other two callers are `remediate.tiered`, deciding whether a codemod can patch a finding, and
`remediate.property_omit`, which does the patching -- and those codemods hard-code TypeScript's
`object` literal, where Python has `dictionary`. A Python finding admitted there produces an empty
diff and abandons as "the remediator produced no change".

So the two questions are separated rather than reconciled. The router asks *can a codemod patch
this file*; the generator asks *can I parse and edit this file to build a labelled pair*. The
generator now owns its own table and `sync.route.templates` is untouched, which is why the last
two tests here assert the router still declines Python -- that regression is the one most likely
to be introduced by this change and it would show up nowhere else.
"""

from __future__ import annotations

import pytest

from sync.benchmark.mutate import depends_on_change, generate_pair
from sync.core import CallSite, RepoRef, VendorChange
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import CannotPatch
from sync.route.templates import language_for

FIELD = "description"


def _change(kind: str, field: str = FIELD) -> VendorChange:
    text = (
        f"removed the request property `{field}` from POST /v1/customers"
        if kind.startswith("request")
        else f"removed the optional property `{field}` from the response"
    )
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="v1", to_version="v2", kind=kind,
        operation_id="PostCustomers", path_ptr="/v1/customers", severity="breaking",
        source="oasdiff", raw={"id": kind, "text": text},
    )


def _site(sources: dict[str, str], site_id: str, path: str, needle: str, occurrence: int = 0):
    """A call site addressed the way the indexer addresses one, computed from the source."""
    source = sources[path]
    offset = -1
    for _ in range(occurrence + 1):
        offset = source.index(needle, offset + 1)
    return CallSite(
        id=site_id, repo_id="fixture", path=path,
        line=source.count("\n", 0, offset) + 1,
        col=offset - (source.rfind("\n", 0, offset) + 1),
        vendor_id="stripe", operation_id="PostCustomers", symbol="stripe.customers.create",
        sdk_version="12.0.0", content_hash="h",
    )


def _labels(pair) -> dict[str, bool]:
    return {label.call_site_id: label.affected for label in pair.labels}


KEYWORDS = {
    "src/billing.py": (
        "import stripe\n"
        "\n"
        'client = stripe.StripeClient("sk_test")\n'
        "\n"
        "def charge(name):\n"
        '    result = client.customers.create(name=name, email="a@b.c")\n'
        "    return result.id\n"
    )
}

POSITIONAL = {
    "src/billing.py": (
        "import stripe\n"
        "\n"
        'client = stripe.StripeClient("sk_test")\n'
        "\n"
        "def charge(name):\n"
        '    result = client.customers.create({"name": name})\n'
        "    return result.id\n"
    )
}

UNBOUND = {
    "src/billing.py": (
        "import stripe\n"
        "\n"
        'client = stripe.StripeClient("sk_test")\n'
        "\n"
        "def charge(name):\n"
        "    client.customers.create(name=name)\n"
    )
}


# --- the request half ----------------------------------------------------------------


def test_a_keyword_argument_call_is_mutated_and_labelled_affected() -> None:
    """Python passes request fields as keyword arguments rather than in an object literal, so
    this is the shape nearly every real call takes and the one the qualifying repository uses."""
    sources = dict(KEYWORDS)
    change = _change("request-property-removed")
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.unreachable == ()
    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True


def test_a_dictionary_passed_positionally_is_mutated_too() -> None:
    """The indexer reads a positional dict literal as request fields, so the generator has to be
    able to break one; a shape the binder can find and the generator cannot break would be a
    labelled negative that is really a gap."""
    sources = dict(POSITIONAL)
    change = _change("request-property-removed")
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.unreachable == ()
    assert depends_on_change(pair.sources, change, site) is True


def test_a_call_already_passing_the_field_is_refused() -> None:
    """The label is exact only while the mutation is the sole source of the dependency."""
    sources = {"src/billing.py": KEYWORDS["src/billing.py"].replace(
        "name=name", f"name=name, {FIELD}='already'"
    )}
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    with pytest.raises(ValueError, match="cs1"):
        generate_pair(sources, _change("request-property-removed"), [site], targets=["cs1"])


# --- the response half ---------------------------------------------------------------


def test_a_bound_result_takes_a_response_guard() -> None:
    sources = dict(KEYWORDS)
    change = _change("response-property-removed", field="status")
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, change, [site], targets=["cs1"])

    assert pair.unreachable == ()
    assert _labels(pair) == {"cs1": True}
    assert depends_on_change(pair.sources, change, site) is True


def test_the_response_guard_occupies_no_new_line() -> None:
    """`upsert_call_site` keys identity on line and column, so a guard on a line of its own
    renames every call below it in the file and its label addresses a row the mutated tree does
    not hold. Python's indentation makes a new line sharper to get right, not softer -- a
    same-line guard sidesteps the question entirely."""
    sources = dict(KEYWORDS)
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, _change("response-property-removed", field="status"),
                         [site], targets=["cs1"])

    before = sources["src/billing.py"]
    after = pair.sources["src/billing.py"]
    assert after != before
    assert after.count("\n") == before.count("\n")


def test_the_mutated_python_still_parses() -> None:
    """A guard spliced onto a statement that ends in a newline rather than a separator would
    join two statements into one expression, and the tree would stop being Python."""
    import ast

    sources = dict(KEYWORDS)
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, _change("response-property-removed", field="status"),
                         [site], targets=["cs1"])

    ast.parse(pair.sources["src/billing.py"])


def test_a_result_nobody_binds_is_unreachable_rather_than_labelled() -> None:
    """A call whose response is never bound reads no field, so a removed response property does
    not break it. Unaffected is the correct answer and not a missed positive."""
    sources = dict(UNBOUND)
    site = _site(sources, "cs1", "src/billing.py", "client.customers.create")

    pair = generate_pair(sources, _change("response-property-removed", field="status"),
                         [site], targets=["cs1"])

    assert pair.unreachable == ("cs1",)
    assert _labels(pair) == {"cs1": False}
    assert pair.sources["src/billing.py"] == sources["src/billing.py"]


# --- the router must still decline Python --------------------------------------------


def test_the_router_still_reads_python_as_a_language_it_cannot_codemod() -> None:
    """The regression this change is most likely to introduce, and it would be silent.

    `language_for` is the router's table, not the generator's. Teaching it `.py` would tell
    `remediate.tiered` that a Python finding can be codemodded and `remediate.property_omit`
    that it can patch one — and those codemods match TypeScript's `object` literal, which Python
    does not have. The finding would route to a tier that produces an empty diff and abandon.
    """
    assert language_for("src/app.py") is None
    assert language_for("src/app.ts") == "typescript"


def test_the_codemod_declines_a_python_call_site_by_name() -> None:
    """The consequence of the line above, asserted where a reader can see it cost something.
    `CannotPatch` is the tier falling through to the agent rather than abandoning."""
    site = CallSite(
        id="cs1", repo_id="r", path="src/billing.py", line=6, col=13, vendor_id="stripe",
        operation_id="PostCustomers", symbol="stripe.customers.create",
        sdk_version="12.0.0", content_hash="h",
    )
    repo = RepoRef(repo_id="r", url="u", local_path=".", head_sha="0" * 40)

    with pytest.raises(CannotPatch, match="not a language this codemod parses"):
        PropertyOmitRemediator().propose(
            finding=None, change=_change("request-property-removed"), site=site, repo=repo,
        )

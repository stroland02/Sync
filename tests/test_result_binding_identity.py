"""A response guard may only be attached to a name that holds the call's own result.

`mutate._result_binding` climbed to an assignment whose value *contained* the call.
`sync.index.python_lang._result_target` and `sync.index.typescript._result_target` require the
value to *be* the call. One word apart, and the generator was the permissive one -- so it wrote a
guard onto a name that never held the response, and manufactured a labelled positive no correct
binder can find.

The shape came out of a real repository:

```python
customers = list(self.client.customers.list(params={...}).auto_paging_iter())
assert customers.has_more is not None      # what the generator wrote
```

`customers` is a list built from the pager. `customers.has_more` is an `AttributeError`, and
removing `has_more` from the response cannot break that code. **The binder is right twice** --
right to record no response field, and right to emit no finding. Left alone this would have forced
`RECALL_FLOOR` from 1.0000 down to 0.8889 to accommodate a mislabel, which is the act
`scripts/gate_corpus.py` exists to prevent.

The asymmetry was not Python's alone. The TypeScript path walked to the statement and took the
declarator's name without ever asking what the declarator's value was, so
`const customers = Array.from(client.customers.list(...))` had the same defect in the same
function. Both are fixed the same way and each has its own commit.

Identity is expressed the way both binders express it: the call must be the value the name
receives, reached through transparent wrappers only. The wrapper sets are the languages' own and
are duplicated here deliberately -- `mutate.py` imports nothing from `sync.index`, and a test on
its import closure enforces that, because a generator that consulted the binder would be scoring
the binder against its own opinion.
"""

from __future__ import annotations

from sync.benchmark.mutate import generate_pair
from sync.core import CallSite, VendorChange


def _change(field: str = "has_more") -> VendorChange:
    return VendorChange(
        id="vc-1", vendor_id="stripe", from_version="v1", to_version="v2",
        kind="response-property-removed", operation_id="GetCustomers",
        path_ptr="/v1/customers", severity="breaking", source="oasdiff",
        raw={"id": "response-property-removed",
             "text": f"removed the optional property `{field}` from the response"},
    )


def _site(sources: dict[str, str], path: str, needle: str) -> CallSite:
    source = sources[path]
    offset = source.index(needle)
    return CallSite(
        id="cs1", repo_id="fixture", path=path,
        line=source.count("\n", 0, offset) + 1,
        col=offset - (source.rfind("\n", 0, offset) + 1),
        vendor_id="stripe", operation_id="GetCustomers", symbol="stripe.customers.list",
        sdk_version="12.0.0", content_hash="h",
    )


def _pair(sources: dict[str, str], path: str, needle: str, field: str = "has_more"):
    return generate_pair(sources, _change(field), [_site(sources, path, needle)], targets=["cs1"])


def _unchanged(pair, sources: dict[str, str], path: str) -> bool:
    return pair.sources[path] == sources[path]


# --- Python -------------------------------------------------------------------------


def test_a_python_result_wrapped_in_another_call_is_unreachable() -> None:
    """The defect, in the shape a real repository wrote it. `customers` holds what `list()`
    returned; the response never reaches that name, so there is no honest guard to write."""
    sources = {"src/billing.py": (
        "import stripe\n\n"
        'client = stripe.StripeClient("sk_test")\n\n'
        "def page():\n"
        "    customers = list(client.customers.list().auto_paging_iter())\n"
        "    return customers\n"
    )}

    pair = _pair(sources, "src/billing.py", "client.customers.list")

    assert pair.unreachable == ("cs1",)
    assert [label.affected for label in pair.labels] == [False]
    assert _unchanged(pair, sources, "src/billing.py")


def test_a_python_result_bound_directly_is_still_reachable() -> None:
    """The regression this change is most likely to cause. Requiring identity must not refuse
    the form the corpus depends on."""
    sources = {"src/billing.py": (
        "import stripe\n\n"
        'client = stripe.StripeClient("sk_test")\n\n'
        "def page():\n"
        "    customers = client.customers.list()\n"
        "    return customers\n"
    )}

    pair = _pair(sources, "src/billing.py", "client.customers.list")

    assert pair.unreachable == ()
    assert [label.affected for label in pair.labels] == [True]


def test_a_python_result_reached_through_a_wrapper_is_still_reachable() -> None:
    """Parentheses and `await` are what the value passes through while still being the value the
    name receives, which is the same set `python_lang` calls transparent."""
    sources = {"src/billing.py": (
        "import stripe\n\n"
        'client = stripe.StripeClient("sk_test")\n\n'
        "async def page():\n"
        "    customers = await (client.customers.list())\n"
        "    return customers\n"
    )}

    pair = _pair(sources, "src/billing.py", "client.customers.list")

    assert pair.unreachable == ()
    assert [label.affected for label in pair.labels] == [True]


# --- TypeScript ---------------------------------------------------------------------


def test_a_typescript_result_wrapped_in_another_call_is_unreachable() -> None:
    """The same defect in the same function, found by checking rather than by assuming Python
    was alone. `Array.from(...)` returns an array and the response never reaches `customers`."""
    sources = {"src/billing.ts": (
        "import Stripe from 'stripe';\n\n"
        "const stripe = new Stripe(process.env.KEY!);\n\n"
        "export async function page() {\n"
        "  const customers = Array.from(stripe.customers.list({ limit: 3 }));\n"
        "  return customers;\n"
        "}\n"
    )}

    pair = _pair(sources, "src/billing.ts", "stripe.customers.list")

    assert pair.unreachable == ("cs1",)
    assert [label.affected for label in pair.labels] == [False]
    assert _unchanged(pair, sources, "src/billing.ts")


def test_a_typescript_result_bound_directly_is_still_reachable() -> None:
    """The twelve corpus pairs are built on this form, so it has to survive untouched."""
    sources = {"src/billing.ts": (
        "import Stripe from 'stripe';\n\n"
        "const stripe = new Stripe(process.env.KEY!);\n\n"
        "export async function page() {\n"
        "  const customers = await stripe.customers.list({ limit: 3 });\n"
        "  return customers.data;\n"
        "}\n"
    )}

    pair = _pair(sources, "src/billing.ts", "stripe.customers.list")

    assert pair.unreachable == ()
    assert [label.affected for label in pair.labels] == [True]


def test_a_typescript_assignment_wrapped_in_another_call_is_unreachable() -> None:
    """The assignment form of the same thing, which the declaration test would not catch."""
    sources = {"src/billing.ts": (
        "import Stripe from 'stripe';\n\n"
        "const stripe = new Stripe(process.env.KEY!);\n\n"
        "export async function page() {\n"
        "  let customers;\n"
        "  customers = Array.from(stripe.customers.list({ limit: 3 }));\n"
        "  return customers;\n"
        "}\n"
    )}

    pair = _pair(sources, "src/billing.ts", "stripe.customers.list")

    assert pair.unreachable == ("cs1",)
    assert _unchanged(pair, sources, "src/billing.ts")

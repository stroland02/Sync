"""Which binding forms let the indexer see what a call's result is read for.

`_response_fields` walked up to a `variable_declarator` and answered `[]` for anything else, so a
result assigned to a variable declared earlier recorded no response fields at all -- and
`VendorChangeDetector` matches a response change against exactly that list, so no response-side
break could ever be found on such a call. **That is a missed break**, which the design document
names as the expensive direction: a false finding spends a reviewer's patience, a missed one is
the incident the product exists to stop.

It stayed invisible because the corpus generator had the same blind spot on the other side of the
pipeline. `mutate.py` only attached a response guard to a `const`/`let` result, so it never
produced a case this would miss, and the benchmark agreed with the binder by construction. B29
fixed the generator; four labelled positives immediately went unfound, and they are all this.

What these tests fix is the asymmetry between the two halves. Each fixture file holds one binding
form and one call, because two calls in one function sharing a result name would merge their reads
and the assertion would stop being about the form.

The negative cases are as load-bearing as the positive ones. A result the code never binds, or
binds only through another call, has no statically visible reads, and answering `[]` there is
correct -- widening the list to fields the code does not touch would convert a missed break into a
false finding, which `2026-07-26-sync-review-integration.md` commits this project against.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core import RepoRef
from sync.index.typescript import TypeScriptAdapter
from sync.signals.stripe.adapter import StripeAdapter
from sync.signals.stripe.symbols import build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "ts" / "assigned_result"

SPEC = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}


@pytest.fixture
def adapter(tmp_path) -> TypeScriptAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    return TypeScriptAdapter(
        vendor_adapter=StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)
    )


def _fields(adapter: TypeScriptAdapter, filename: str) -> list[str]:
    """The response fields recorded for the one call in one fixture file."""
    repo = RepoRef(
        repo_id="assigned_result", url="https://example.invalid/assigned_result",
        local_path=str(FIXTURE), head_sha="0" * 40,
    )
    sites = [site for site in adapter.index(repo) if site.path == f"src/{filename}"]
    assert len(sites) == 1, f"{filename} should hold exactly one indexed call, got {len(sites)}"
    return sorted(sites[0].response_fields_read)


def test_a_result_assigned_to_a_variable_declared_earlier_records_its_reads(adapter) -> None:
    """The defect. `charge = await stripe.charges.create(...)` reads `charge.id` and
    `charge.status` exactly as the `const` form does, and recorded neither."""
    assert _fields(adapter, "assigned.ts") == ["id", "status"]


def test_the_declaration_form_that_already_worked_still_does(adapter) -> None:
    """The regression this change is most likely to cause, and the form every existing
    response-side result in the corpus takes."""
    assert _fields(adapter, "declared.ts") == ["id", "status"]


def test_a_destructuring_assignment_records_the_keys_it_binds(adapter) -> None:
    """`({ id, status } = await ...)` names the vendor's fields in the pattern, the same way the
    declaration form does. The parentheses are required by the grammar, not by us."""
    assert _fields(adapter, "destructured_assignment.ts") == ["id", "status"]


def test_a_returned_result_records_nothing(adapter) -> None:
    """`return stripe.charges.create({...})` puts whatever reads the fields in the caller, which
    is a different function and frequently a different file. Nothing here can see it, and
    inventing a field list would be the false-finding direction."""
    assert _fields(adapter, "forwarded.ts") == []


def test_a_result_handed_to_another_call_is_not_attributed_to_this_one(adapter) -> None:
    """`const charge = wrap(await stripe.charges.create(...))` binds `wrap`'s return value, not
    the SDK's. The fields read off `charge` describe whatever `wrap` produced, so crediting them
    to the Stripe call would claim a dependency on fields that call's response may not even
    carry."""
    assert _fields(adapter, "argument.ts") == []

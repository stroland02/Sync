"""What the Python indexer may credit a call's result with, and what it may not.

This is the precision half of the defect `2026-07-29-the-binder-can-see-an-assigned-result.md`
fixed in TypeScript, and it is the only half Python has. There is no
declaration-versus-assignment split here — `x = ...` is an `assignment` node and is the only form
— so the shape that was blind in TypeScript is the shape Python already handled, and nothing in
this module is looking for a missed break.

`_response_fields` walked to the nearest `assignment` without checking that the SDK call is what
the name receives. So `charge = dict(client.charges.create(...))` credited the Stripe call with
`id` and `status`, which are read off `dict`'s return value. A false attribution turns a call site
into a finding for a change it does not depend on, and
`2026-07-26-sync-review-integration.md` puts that cost above a missed one: a missed finding costs
an incident, a false one costs the reviewer's willingness to read the next.

The fix is the same shape as TypeScript's and a different set. The walk stops at anything that is
not a transparent wrapper, and Python's wrappers are **`await` and `parenthesized_expression`,
those two and no others**. TypeScript's `as`, `satisfies`, non-null and type assertion have no
Python equivalent; what Python has instead, and what is deliberately not a wrapper, is asserted
below rather than left for the next reader to wonder about.

Every assertion here is that the indexer records the same or fewer fields than before. This is a
precision task, so a case that starts recording *more* is a regression even where the new fields
look plausible.
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
FIXTURE = FIXTURES / "py" / "response_forms"

SPEC = {"paths": {"/v1/charges": {"post": {"operationId": "PostCharges"}}}}


@pytest.fixture
def adapter(tmp_path) -> PythonAdapter:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(build_symbol_map(SPEC)), encoding="utf-8")
    return PythonAdapter(
        vendor_adapter=StripeAdapter(spec_dir=FIXTURES / "specs", symbol_map_path=map_path)
    )


def _fields(adapter: PythonAdapter, filename: str) -> list[str]:
    """The response fields recorded for the one indexed call in one fixture file."""
    repo = RepoRef(
        repo_id="response_forms", url="https://example.invalid/response_forms",
        local_path=str(FIXTURE), head_sha="0" * 40,
    )
    sites = [site for site in adapter.index(repo) if site.path == f"src/{filename}"]
    assert len(sites) == 1, f"{filename} should hold exactly one indexed call, got {len(sites)}"
    return sorted(sites[0].response_fields_read)


# --- the defect --------------------------------------------------------------------


def test_a_result_passed_through_another_call_is_not_credited_to_this_one(adapter) -> None:
    """`charge = dict(client.charges.create(...))` binds what `dict` returned. The fields read
    off it describe that object, and crediting them to the Stripe call claims a dependency on
    response fields the vendor need not carry."""
    assert _fields(adapter, "wrapped.py") == []


def test_a_result_defaulted_away_is_not_credited_either(adapter) -> None:
    """`client.charges.create(...) or {}` may bind the empty dict, and nothing static says which.
    A boolean operator is not a wrapper: it is a choice between two values, only one of which is
    the call's."""
    assert _fields(adapter, "or_default.py") == []


# --- the forms that must keep working ----------------------------------------------


def test_a_plain_assignment_still_records_its_reads(adapter) -> None:
    """The only binding form Python has, and the one this task must not disturb. Python's
    equivalent of the TypeScript declaration gap does not exist, so this already worked."""
    assert _fields(adapter, "bare.py") == ["id", "status"]


def test_an_annotated_assignment_records_its_reads(adapter) -> None:
    """`charge: dict = client.charges.create(...)` is the same `assignment` node wearing a type,
    not a different one. Keying the walk on a narrower node kind would lose it, and losing it
    would be a missed break introduced by a precision fix."""
    assert _fields(adapter, "annotated.py") == ["id", "status"]


def test_an_awaited_result_records_its_reads(adapter) -> None:
    """`await` is the first of Python's two transparent wrappers: the awaited value is the call's
    own result and nothing else."""
    assert _fields(adapter, "awaited.py") == ["id", "status"]


def test_a_parenthesised_result_records_its_reads(adapter) -> None:
    """The second and last. Parentheses change precedence and nothing else."""
    assert _fields(adapter, "parenthesized.py") == ["id", "status"]


# --- the forms that must stay empty ------------------------------------------------


def test_an_augmented_assignment_records_nothing(adapter) -> None:
    """`charge += client.charges.create(...)` binds the concatenation, not the response, and is
    an `augmented_assignment` node rather than an `assignment`. It recorded nothing before and
    has to keep recording nothing — a precision fix that swept this up would be the defect."""
    assert _fields(adapter, "augmented.py") == []


def test_a_returned_result_records_nothing(adapter) -> None:
    """Whatever reads the fields is in the caller, frequently in another module. Producing a list
    for it would be the false-attribution direction from the other end."""
    assert _fields(adapter, "forwarded.py") == []

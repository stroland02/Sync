"""Steps 2 and 3 of the replay tier: run the patched call path, and check what it read.

`docs/superpowers/specs/2026-07-26-sync-observed-contract-drift.md` names the property that
decides whether any of this is worth having:

    The replay tier is proven able to fail: a patch that mishandles the new shape must fail
    replay before the tier is trusted to pass anything.

So the rejection test comes first in this file and came first in the writing, and the two
fixtures behind it differ by one line. `mishandles/billing.ts` reads a property off the null
the new specification now permits; `handles/billing.ts` coalesces it. Everything else about
them is identical, so a tier that passed both would be proving nothing about either, and a
tier that rejected both would be a delay rather than a gate.

The output of this tier goes into a pull request body as evidence a human reads. That is the
whole reason the sandbox assertions here are executable rather than documented: "no network"
and "no credential" are claims a reviewer is being asked to trust.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.verify.replay import (
    SYNTHETIC_CREDENTIAL,
    replay_call_path,
    replay_from_specification,
    replay_shapes,
    unsatisfied_fields,
)

FIXTURES = Path(__file__).parent / "fixtures" / "replay"
TARGET = "src/billing.ts"

# What `synthesize_mock_response` produces for a charge whose `status` the new specification
# marks nullable: the mock shows the null rather than the happy shape, because the null is the
# case the tier exists to catch.
MOCK = {"id": "<sync-mock /id>", "status": None, "amount": 0}


def _repo(tmp_path: Path, fixture: str) -> RepoRef:
    shutil.copytree(FIXTURES / fixture, tmp_path, dirs_exist_ok=True)
    return RepoRef(
        repo_id="repo-1", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="abc123",
    )


def _site(fields: list[str] | None = None) -> CallSite:
    return CallSite(
        repo_id="repo-1", path=TARGET, line=9, col=23, vendor_id="stripe",
        operation_id="PostCharges", symbol="stripe.charges.create",
        args_keys=["amount", "currency"],
        response_fields_read=["id", "status"] if fields is None else fields,
        sdk_version="18.0.0", content_hash="h",
    )


def _replay(repo: RepoRef, site: CallSite, mock=MOCK, **kwargs):
    return replay_call_path(
        repo, site, mock, export="charge", vendor_packages=("stripe",),
        arguments=(1000,), **kwargs,
    )


# --- proof it can fail ------------------------------------------------------------


def test_a_patch_that_mishandles_the_new_shape_fails_replay(tmp_path: Path) -> None:
    """The first test written, and the one the tier is worth nothing without.

    `tsc` passes this file -- the SDK's declared type still carries `status` -- and a suite
    with no test over the call stays green. Executing the call against the new shape is the
    only gate that sees it.
    """
    result = _replay(_repo(tmp_path, "mishandles"), _site())

    assert result.ok is False
    assert result.outcome == "threw"
    assert "toUpperCase" in result.reason


def test_a_patch_that_handles_the_new_shape_passes(tmp_path: Path) -> None:
    """Second, so the test above cannot be satisfied by a tier that rejects everything."""
    result = _replay(_repo(tmp_path, "handles"), _site())

    assert result.ok is True, result.reason
    assert result.outcome == "passed"


# --- step 3: what the code reads, against what the mock carries --------------------


def test_a_field_the_code_reads_that_the_mock_does_not_carry_is_named() -> None:
    """Distinct from "the code threw". Code can consume a response without error while
    reading a field that is now absent -- `result.status` on an object with no `status` is
    `undefined` in JavaScript and throws nothing at all."""
    assert unsatisfied_fields({"id": "x"}, ["id", "status"]) == ("status",)


def test_a_nested_field_is_addressed_the_way_the_indexer_records_it() -> None:
    """`response_fields_read` is dot-separated -- `sync.index.typescript._path` joins the
    member chain with `.` -- so the check walks that form rather than a JSON Pointer. Reading
    it as a pointer would find nothing and report every nested field as absent."""
    body = {"data": {"status": None}}
    assert unsatisfied_fields(body, ["data.status"]) == ()
    assert unsatisfied_fields(body, ["data.amount"]) == ("data.amount",)


def test_a_present_field_holding_null_is_satisfied() -> None:
    """Present-and-null is what the vendor now sends. The field is there; whether the code
    survives it is the execution step's question, not this one's."""
    assert unsatisfied_fields({"status": None}, ["status"]) == ()


def test_an_unsatisfied_field_fails_the_run_and_names_the_field(tmp_path: Path) -> None:
    """The two halves compose: the code consumes the body cleanly and replay still fails,
    because the field it was recorded as reading is not in the response any more."""
    mock = {"id": "<sync-mock /id>", "status": None}
    site = _site(fields=["id", "status", "receipt_url"])

    result = _replay(_repo(tmp_path, "handles"), site, mock=mock)

    assert result.ok is False
    assert result.outcome == "unsatisfied"
    assert result.missing_fields == ("receipt_url",)
    assert "receipt_url" in result.reason


# --- the sandbox, asserted rather than documented ---------------------------------


def test_the_call_path_cannot_reach_the_network(tmp_path: Path) -> None:
    """The mock is the only response. A call path that tries to reach the vendor is refused
    inside the sandbox, not permitted and then reported."""
    result = _replay(_repo(tmp_path, "reaches_network"), _site())

    assert result.ok is False
    assert result.outcome == "threw"
    assert "network" in result.reason.lower()


def test_no_real_credential_and_no_parent_environment_reaches_the_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both halves of the credential rule at once, asserted from inside the child.

    The fixture throws if it can see a variable this process holds, and throws if the one
    variable replay was asked to supply is anything but the synthetic value. Passing is the
    only outcome consistent with both, and no value crosses back into Python to be asserted
    on -- which is how a test like this leaks the thing it is checking for.
    """
    monkeypatch.setenv("SYNC_TEST_PARENT_SECRET", "sk_live_not_a_real_key_but_shaped_like_one")

    result = _replay(
        _repo(tmp_path, "reads_environment"), _site(fields=["id"]),
        mock={"id": "<sync-mock /id>"}, credential_env=("STRIPE_KEY",),
    )

    assert result.ok is True, result.reason
    assert os.environ["SYNC_TEST_PARENT_SECRET"].startswith("sk_live_")


def test_the_synthetic_credential_cannot_authenticate_anywhere() -> None:
    """It is not a key with the wrong value; it is not key-shaped at all.

    Angle-bracket delimited, which no vendor's key format uses, and carrying no run of
    alphanumerics long enough to read as an opaque token. A placeholder that looked like a
    credential would eventually be pasted into an issue as one, which is the same argument
    `mock_response.PLACEHOLDER_PREFIX` makes about synthetic strings.
    """
    assert SYNTHETIC_CREDENTIAL.startswith("<") and SYNTHETIC_CREDENTIAL.endswith(">")
    runs = re.findall(r"[A-Za-z0-9]+", SYNTHETIC_CREDENTIAL)
    assert max(len(run) for run in runs) < 16, runs


# --- declining is not passing -----------------------------------------------------


def test_a_missing_export_declines_rather_than_passing(tmp_path: Path) -> None:
    """A decline is not evidence. It must not read as a green replay, and it must not read as
    a defect in the patch either -- the caller needs those apart to decide whether to gate."""
    result = replay_call_path(
        _repo(tmp_path, "handles"), _site(), MOCK,
        export="noSuchExport", vendor_packages=("stripe",), arguments=(1000,),
    )

    assert result.ok is False
    assert result.outcome == "declined"


def test_a_missing_file_declines(tmp_path: Path) -> None:
    """The index can outlive the file it points at."""
    site = _site()
    result = _replay(_repo(tmp_path, "handles"), site.model_copy(update={"path": "src/gone.ts"}))

    assert result.outcome == "declined"


# --- what the caller writes to the shape store ------------------------------------


def test_the_shapes_are_offered_for_the_store_and_not_written(tmp_path: Path) -> None:
    """Every replay run is a shape-store writer with `source='replay'`, and the writing
    belongs to whoever owns the store. This returns the rows and touches no database."""
    result = _replay(_repo(tmp_path, "handles"), _site())

    by_path = {shape.field_path: shape for shape in result.shapes}
    assert by_path["/id"].source == "replay"
    assert by_path["/id"].json_type == "string"
    assert by_path["/status"].nullable_seen is True


def test_the_whole_tier_runs_from_a_schema_and_a_baseline(tmp_path: Path) -> None:
    """Steps 1 to 3 in one call, which is the shape a caller holds: a schema for the new
    operation and whatever the store observed for it, never a body someone already built.

    The schema marks `status` nullable, so step 1 emits the null, and the fixture that
    dereferences it fails -- the same rejection as the first test in this file, reached
    through the composition rather than through a hand-written mock.
    """
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "status": {"type": "string", "nullable": True},
        },
    }

    result = replay_from_specification(
        _repo(tmp_path, "mishandles"), _site(fields=["id", "status"]), schema,
        export="charge", vendor_packages=("stripe",), arguments=(1000,),
    )

    assert result.outcome == "threw"
    assert "toUpperCase" in result.reason


def test_replay_shapes_reduce_a_body_to_paths_and_types_only() -> None:
    """No value survives the reduction. The store's rule is the threat model's, and a mock
    carrying a placeholder is still a value nobody should retain."""
    shapes = replay_shapes("stripe", "PostCharges", {"id": "<sync-mock /id>", "n": [1]})

    dumped = " ".join(repr(shape.model_dump()) for shape in shapes)
    assert "<sync-mock" not in dumped
    assert {"/id", "/n", "/n/-"} <= {shape.field_path for shape in shapes}

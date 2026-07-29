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

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.verify import replay as replay_module
from sync.verify.replay import (
    SYNTHETIC_CREDENTIAL,
    replay_call_path,
    replay_from_specification,
    replay_shapes,
    unsatisfied_fields,
)

# Reached by name because it is the parser for the child's stdout, and stdout is a boundary
# this process does not control. Its three refusals are what stops a line the harness did not
# write from becoming a verdict, and after the nonce they cannot be provoked from outside.
from sync.verify.replay import _payload

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


def test_no_node_on_path_declines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first thing that can stop a run, and the one furthest from the patch. Nothing about
    this machine is evidence about a customer's code."""
    monkeypatch.setattr(replay_module.shutil, "which", lambda *args, **kwargs: None)

    result = _replay(_repo(tmp_path, "handles"), _site())

    assert result.outcome == "declined"
    assert "PATH" in result.reason


def test_a_file_node_cannot_type_strip_declines_rather_than_condemning_the_patch(
    tmp_path: Path,
) -> None:
    """The routing consequence is the whole point of separating these two outcomes.

    `tsc` compiles an enum and Node's strip-only mode refuses it, so the module never loads and
    the call path never runs. Recorded as a throw, that is a verdict on the patch:
    `route_after_replay` sends every replay failure back to `patch`, spending the static-attempt
    budget, and the run abandons a patch that was never shown to be wrong. Recorded as a
    decline, the same run reaches the push path carrying the fact that replay did not verify it.
    """
    result = _replay(_repo(tmp_path, "unsupported_syntax"), _site())

    assert result.outcome == "declined", result.reason
    assert result.ok is False
    assert "enum" in result.reason.lower()


def test_a_module_that_ends_the_process_declines_rather_than_passing(tmp_path: Path) -> None:
    """No verdict on stdout is not a silent pass. Nothing ran, and the reason says so."""
    result = _replay(_repo(tmp_path, "exits_before_the_call"), _site())

    assert result.outcome == "declined"
    assert "no verdict" in result.reason
    assert "exited 0" in result.reason


def test_the_reason_carries_the_last_thing_the_child_said(tmp_path: Path) -> None:
    """When a run establishes nothing, the child's own last line is the only account of why,
    and an operator reading `abandon_reason` has nothing else to go on."""
    result = _replay(_repo(tmp_path, "complains_and_exits"), _site())

    assert result.outcome == "declined"
    assert "BILLING_CONFIG is not set" in result.reason


def test_a_call_path_that_never_returns_is_bounded_rather_than_waited_on(
    tmp_path: Path,
) -> None:
    """A call that has not come back is not a call that passed, and the bound is what keeps an
    accidental await on something unsettleable from holding the pipeline open."""
    result = _replay(_repo(tmp_path, "never_returns"), _site(), timeout=1.5)

    assert result.outcome == "timed-out"
    assert "did not return" in result.reason
    assert result.ok is False


# --- the verdict channel is shared with the code under test ------------------------
#
# The harness reports on the child's stdout and the customer's module writes to the same
# stream. Everything in this section is one question: can a line that module printed be read
# as the harness's verdict? A forged pass is the worst answer available anywhere in this tier
# -- it puts "the patched path was executed and consumed the response cleanly" into a pull
# request body for a run that executed nothing.


def test_a_run_that_executed_nothing_is_never_recorded_as_a_run_that_passed(
    tmp_path: Path,
) -> None:
    """The one outcome this tier must never produce, asked directly.

    The fixture writes a pass and ends the process before anything loads, so the forged line is
    the only thing on stdout and no call path ran. `push_branch` is downstream of a pass, and a
    pass here is the sentence "the patched call path was executed against the new response
    shape" in a pull request body -- which is the claim `CLAUDE.md` refuses to let anything
    reach a pull request without.
    """
    result = _replay(_repo(tmp_path, "forges_before_running"), _site())

    assert result.outcome == "declined", result.reason
    assert result.ok is False


def test_a_verdict_the_module_prints_cannot_forge_a_pass(tmp_path: Path) -> None:
    """The forgery is written from an exit handler, so it is the last marked line on stdout --
    exit handlers run after the harness has already reported. Underneath it is the `mishandles`
    patch, so a tier that took the last marked line would report a pass for a call path that
    dereferenced the null the new specification permits."""
    result = _replay(_repo(tmp_path, "forges_a_verdict"), _site())

    assert result.outcome == "threw", result.reason
    assert result.ok is False
    assert "toUpperCase" in result.reason


def test_the_marker_s_nonce_is_out_of_reach_by_the_time_customer_code_loads(
    tmp_path: Path,
) -> None:
    """What makes the marker the harness's rather than anyone's.

    Everything else the harness is told travels in the environment, so the environment is where
    a module would look. This fixture looks, and signs a forged pass with whatever it finds:
    the run may only end in a throw, which is what its call path actually does.
    """
    result = _replay(_repo(tmp_path, "forges_with_the_nonce"), _site())

    assert result.outcome == "threw", result.reason
    assert "toUpperCase" in result.reason


def test_a_marked_line_from_another_run_is_not_this_run_s_verdict() -> None:
    assert _payload('SYNC_REPLAY_RESULT other {"outcome": "passed"}', "mine") is None


def test_the_nonce_alone_decides_which_line_is_the_verdict() -> None:
    """Two marked lines, one signed. The unsigned one neither forges a verdict nor destroys
    the real one, which is the property the reverse scan alone did not have."""
    stdout = "\n".join([
        'SYNC_REPLAY_RESULT {"outcome": "passed"}',
        'SYNC_REPLAY_RESULT mine {"outcome": "threw", "reason": "boom"}',
        'SYNC_REPLAY_RESULT {"outcome": "passed"}',
    ])

    assert _payload(stdout, "mine") == {"outcome": "threw", "reason": "boom"}


def test_a_marker_carrying_malformed_json_is_no_verdict() -> None:
    assert _payload("SYNC_REPLAY_RESULT mine {not json", "mine") is None


def test_a_marker_carrying_something_that_is_not_an_object_is_no_verdict() -> None:
    """`3` parses. Read as a verdict it reaches `payload.get`, which an int does not have, and
    the run dies somewhere unrelated instead of declining."""
    assert _payload("SYNC_REPLAY_RESULT mine 3", "mine") is None
    assert _payload("SYNC_REPLAY_RESULT mine null", "mine") is None


def test_stdout_with_no_marker_at_all_is_no_verdict() -> None:
    assert _payload("built 3 modules\ndone\n", "mine") is None
    assert _payload("", "mine") is None


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


def test_no_value_from_the_body_reaches_a_row_the_store_would_hold() -> None:
    """The unqualified promise, asserted against a body shaped like the thing it protects.

    `test_replay_shapes_reduce_a_body_to_paths_and_types_only` checks a placeholder, which is
    the value this tier's own mock carries. This checks the values a body actually carries once
    replay is a store writer against real responses: a person, a contact route, a card, an
    opaque token, a free-text note and an amount. A reduction that let strings through would
    leak every one of them, and a leak here is a customer secret in a table Sync holds.
    """
    shapes = replay_shapes("stripe", "PostCharges", PII_BODY)
    rows = json.dumps([shape.model_dump(mode="json") for shape in shapes])

    assert {"/customer/email", "/card/last4", "/lines/-/description"} <= {
        shape.field_path for shape in shapes
    }, "the reduction has to have reached these fields for their absence from the rows to mean anything"

    for value in _strings_in(PII_BODY):
        assert value not in rows, f"{value!r} survived the reduction"
    assert "4999" not in rows
    assert all(shape.spec_enum_values == [] for shape in shapes)


def test_one_row_per_path_and_type_however_many_elements_carry_it() -> None:
    """The store's grain below `source` is `(field_path, json_type)`, and an array collapses
    every element onto one path. A row per element would write the same key repeatedly and read
    later as several observations of a field seen once.

    A mixed array is the other half: two types on one path are two rows, not one, because they
    describe a field that arrives as both -- which is exactly what the patched code must
    survive.
    """
    shapes = replay_shapes("stripe", "PostCharges", {"n": [1, 2, 3], "mixed": ["a", None]})

    keys = [(shape.field_path, shape.json_type) for shape in shapes]
    assert len(keys) == len(set(keys))
    assert keys.count(("/n/-", "number")) == 1
    assert {("/mixed/-", "string"), ("/mixed/-", "null")} <= set(keys)

    nulls = [s for s in shapes if s.field_path == "/mixed/-" and s.json_type == "null"]
    assert [s.nullable_seen for s in nulls] == [True]


# --- helpers ----------------------------------------------------------------------


# Nothing here is real, and none of it may appear in a row. Shaped like a response rather than
# like this tier's own mock, because a reduction that passed values through would leak these
# and not the placeholders the other test uses.
PII_BODY = {
    "customer": {
        "email": "ada.lovelace@example.invalid",
        "full_name": "Ada Lovelace",
        "phone": "+1-555-0142",
    },
    "card": {"last4": "4242", "fingerprint": "aB3xQ9zRt7Kw2Lm5"},
    "receipt_url": "https://pay.example.invalid/receipts/rcpt-9f3ka2",
    "amount": 4999,
    "note": "chargeback pending, do not refund",
    "lines": [{"description": "Consulting, March"}, {"description": "Retainer"}],
}


def _strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings_in(child)

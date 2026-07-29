"""The checkpointer must give Sync's own types back, not dictionaries.

LangGraph already writes `sync.core` models into a checkpoint natively. What it
does not do by default is *read* them back under a permission it intends to
withdraw: every load logs "Deserializing unregistered type ... This will be
blocked in a future version". When that permission goes, the ext hook stops
reconstructing the model and returns the raw `model_dump()` dict instead --
quietly, with no exception at the load. A run resumed after that point reaches
`make_locate`, asks a dict for `.call_site_id`, and dies on the durability
guarantee that is the whole reason this pipeline is a graph rather than a loop.

These tests hold the registration in place. The load-bearing one is
`test_a_type_that_was_not_registered_is_returned_as_a_dict`: a registration
that quietly did nothing would still round-trip every model correctly today,
because the permissive default carries them. Only the allowlist's *mode* tells
the two apart.
"""

from __future__ import annotations

import logging
import typing
from datetime import datetime, timezone

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde import jsonplus
from pydantic import BaseModel

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange
from sync.remediate.serde import CHECKPOINTED_TYPES, with_sync_types
from sync.remediate.state import RunState

SERDE_LOGGER = "langgraph.checkpoint.serde.jsonplus"

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["status"],
    sdk_version="18.0.0", content_hash="h1",
    indexed_at=datetime(2026, 7, 25, 9, 30, tzinfo=timezone.utc),
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="2026-06-30", to_version="2026-07-28",
    kind="response-property-removed", operation_id="PostCharges", path_ptr="/x/status",
    severity="breaking", source="oasdiff",
    # Nested rather than flat on purpose: `raw` is the field a lossy encoding
    # would flatten or drop without the object comparing unequal at the top level.
    raw={"paths": {"/v1/charges": {"post": {"deprecated": True}}}, "removed": ["status"]},
    detected_at=datetime(2026, 7, 28, 11, 0, tzinfo=timezone.utc),
)
FINDING = Finding(
    id="f1", detector="vendor_change", claim="response-field", call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking", rationale="status removed",
    created_at=datetime(2026, 7, 28, 11, 5, tzinfo=timezone.utc),
)
REPO = RepoRef(
    repo_id="r1", url="https://example.invalid/r", local_path="/tmp/r", head_sha="0" * 40
)
PATCH = Patch(diff="--- a\n+++ b\n@@\n-old\n+new\n", strategy="agent", rationale="fix")
EVIDENCE = Evidence(
    spec_diff=CHANGE.raw, changelog_entry="status removed",
    call_sites=["src/billing.ts:6"], ci_run_url="https://github.com/o/r/actions/runs/1",
)


def _state() -> RunState:
    return {
        "finding": FINDING, "repo": REPO, "site": SITE, "change": CHANGE,
        "patch": PATCH, "evidence": EVIDENCE, "branch": "sync/fix-1",
        "static_attempts": 1, "ci_attempts": 0, "verify_ok": True, "outcome": "running",
    }


class NotRegistered(BaseModel):
    """A model this repository never checkpoints.

    Defined at module scope, not inside a test: the ext hook reconstructs a type
    by importing its module and taking the attribute off it, so a class nested in
    a function comes back as a dict whatever the allowlist says, and would make
    the assertion below pass for the wrong reason.
    """

    value: str
    count: int


def _registered_serde():
    return with_sync_types(InMemorySaver()).serde


def _round_trip(serde, value):
    return serde.loads_typed(serde.dumps_typed(value))


def test_a_checkpointed_run_state_comes_back_as_models():
    restored = _round_trip(_registered_serde(), _state())

    assert isinstance(restored["finding"], Finding)
    assert isinstance(restored["repo"], RepoRef)
    assert isinstance(restored["site"], CallSite)
    assert isinstance(restored["change"], VendorChange)
    assert isinstance(restored["patch"], Patch)
    assert isinstance(restored["evidence"], Evidence)


def test_every_value_a_checkpointed_run_state_carries_survives_it():
    """Reconstructing the right class is not the same as reconstructing the right
    object: the ext hook feeds `model_dump()` back through the constructor, so a
    field lost on the way out is re-derived from a default rather than raising.
    """
    restored = _round_trip(_registered_serde(), _state())

    assert restored["finding"] == FINDING
    assert restored["repo"] == REPO
    assert restored["site"] == SITE
    assert restored["change"] == CHANGE
    assert restored["patch"] == PATCH
    assert restored["evidence"] == EVIDENCE
    assert restored["branch"] == "sync/fix-1"
    assert restored["static_attempts"] == 1
    assert restored["verify_ok"] is True

    # The two shapes a msgpack round trip is most likely to flatten, asserted
    # directly rather than left to the top-level equality that covers them.
    assert restored["change"].raw == CHANGE.raw
    assert restored["site"].indexed_at == SITE.indexed_at
    assert restored["site"].indexed_at.tzinfo is not None


def test_a_type_that_was_not_registered_is_returned_as_a_dict():
    """What makes the registration real rather than decorative.

    LangGraph's default allowlist is the string `True`: every type is allowed and
    warned about, so the models round-trip whether or not anyone registered them,
    and a round-trip test alone proves nothing. Registering replaces `True` with
    an explicit set, which is the behaviour a future version will impose on
    everyone -- an unregistered type stops being reconstructed and arrives as its
    raw `model_dump()`. Asserting that a foreign type is refused is how this
    suite knows Sync is already running under those rules.
    """
    foreign = NotRegistered(value="x", count=2)

    assert _round_trip(_registered_serde(), foreign) == {"value": "x", "count": 2}
    # ...and langgraph's own default does reconstruct it, which is what makes the
    # assertion above a statement about the registration and not about the type.
    assert _round_trip(InMemorySaver().serde, foreign) == foreign


def test_loading_a_checkpoint_no_longer_warns_that_syncs_types_are_unregistered(caplog):
    # `_warn_once` dedups for the life of the interpreter, so a warning any
    # earlier test already emitted for these types would make both halves of this
    # test read the wrong thing.
    jsonplus._warned_unregistered_types.clear()

    with caplog.at_level(logging.WARNING, logger=SERDE_LOGGER):
        _round_trip(InMemorySaver().serde, _state())
    warned = [r.getMessage() for r in caplog.records if "unregistered type" in r.getMessage()]
    # The control. Without it the assertion below passes on any process where the
    # warning happened to be emitted already.
    assert any("sync.core.models.Finding" in message for message in warned)

    caplog.clear()
    jsonplus._warned_unregistered_types.clear()

    with caplog.at_level(logging.WARNING, logger=SERDE_LOGGER):
        _round_trip(_registered_serde(), _state())
    assert [r.getMessage() for r in caplog.records] == []


def _models_in(hint) -> set[type]:
    if isinstance(hint, type) and issubclass(hint, BaseModel):
        return {hint}
    return {m for arg in typing.get_args(hint) for m in _models_in(arg)}


def test_every_model_run_state_can_carry_is_registered():
    """The allowlist is written out by hand, so it goes stale the moment someone
    adds a model to `RunState` -- and goes stale silently, because the permissive
    default keeps carrying the new type until the version that stops.
    """
    carried = {m for hint in typing.get_type_hints(RunState).values() for m in _models_in(hint)}

    assert carried, "RunState carries no models; this test would pass vacuously"
    assert carried <= set(CHECKPOINTED_TYPES)
    # The other direction: an entry nobody exercises rots into a comment. Every
    # registered type is one `_state()` carries, and the round-trip tests above
    # assert on each of them.
    assert set(CHECKPOINTED_TYPES) <= carried

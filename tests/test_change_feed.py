"""The public change feed: render, sign, verify, parse.

`docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` is binding on the format, and
`2026-07-25-sync-positioning-and-open-core.md` says why it is given away: publishing the
normalised feed for free is what makes Sync's schema the one a competitor's tooling speaks. The
feed is the giveaway; the binding engine is not.

Four of the tests below are the properties that specification makes binding -- byte-identical
republication, no customer data, the bare array, and a hard failure on a bad signature. The rest
exist because a feed that drives code changes is a supply-chain surface, and the two gates it
passes through fail for different reasons.
"""

from __future__ import annotations

import json
import random

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sync.core import VendorChange
from sync.signals.feed import (
    FEED_FIELDS,
    FeedFormatError,
    FeedSignatureError,
    parse_feed,
    public_key_bytes,
    render_feed,
    sign_feed,
    verify_and_parse,
    verify_feed,
)


@pytest.fixture()
def keypair():
    """Generated per test. No key material is committed, and the private half never leaves
    this process."""
    private_key = Ed25519PrivateKey.generate()
    return private_key, public_key_bytes(private_key)


def _change(**over) -> VendorChange:
    fields = dict(
        vendor_id="stripe",
        from_version="2026-05-01",
        to_version="2026-11-01",
        kind="response-property-removed",
        operation_id="PostCharges",
        path_ptr="/v1/charges",
        severity="breaking",
        source="oasdiff",
        raw={"id": "response-property-removed", "text": "removed the `status` property"},
    )
    fields.update(over)
    return VendorChange(**fields)


def _entries(payload: bytes) -> list[dict]:
    return json.loads(payload.decode("utf-8"))


# --- the array is the whole contract ----------------------------------------------


def test_the_payload_is_a_bare_json_array():
    """No wrapper object, no pagination envelope, no version field. The format is versioned by
    never breaking it."""
    assert isinstance(_entries(render_feed([_change()], vendor_id="stripe")), list)


def test_an_entry_carries_exactly_the_frozen_field_set():
    """An allow-list, not a deny-list. Rendering whatever fields the model happens to hold is
    how a future column reaches a public file without anyone deciding it should."""
    entry = _entries(render_feed([_change()], vendor_id="stripe"))[0]

    assert tuple(sorted(entry)) == tuple(sorted(FEED_FIELDS))


def test_raw_is_carried_because_the_changed_field_lives_in_it():
    """The changed field is not a column. It is the first backticked token in oasdiff's free
    text, and `changed_field()` is the only supported way to get it -- so dropping `raw` as an
    implementation detail would leave a consumer unable to tell which field moved."""
    entry = _entries(render_feed([_change()], vendor_id="stripe"))[0]

    assert entry["raw"]["text"] == "removed the `status` property"


def test_a_vendor_with_no_changes_renders_an_empty_array():
    """A vendor that shipped nothing publishes an empty feed, not a 404 and not a null. A
    consumer that has to special-case absence will get it wrong."""
    assert render_feed([], vendor_id="stripe") == b"[]"


def test_only_the_named_vendor_reaches_the_feed():
    """One array per vendor, at one URL per vendor. A stray entry from another vendor would be
    served under a name that does not describe it."""
    payload = render_feed([_change(), _change(vendor_id="twilio")], vendor_id="stripe")

    assert {entry["vendor_id"] for entry in _entries(payload)} == {"stripe"}


# --- byte-identical republication -------------------------------------------------


def test_republishing_unchanged_changes_is_byte_identical():
    """The property most easily lost and the one nobody notices until every client redownloads
    daily. The two runs build their rows fresh, the way a real regeneration would, so anything
    the renderer picks up from construction time rather than from content shows up here.
    """
    first = render_feed([_change()], vendor_id="stripe")
    second = render_feed([_change()], vendor_id="stripe")

    assert first == second


def test_the_detection_time_is_not_embedded():
    """`detected_at` is when Sync noticed, not when the vendor changed. It differs on every run
    and belongs to the customer's own graph, not to a file served to everyone."""
    from datetime import datetime, timezone

    stamped = _change()
    stamped.detected_at = datetime(2026, 3, 3, 3, 3, tzinfo=timezone.utc)

    assert b"2026-03-03" not in render_feed([stamped], vendor_id="stripe")


def test_the_input_order_does_not_reach_the_output():
    """A regeneration reads rows in whatever order the database returned them. If that ordering
    leaked into the bytes, a no-op run would invalidate every cached copy."""
    changes = [_change(operation_id=f"Op{i}") for i in range(12)]
    shuffled = list(changes)
    random.Random(20260726).shuffle(shuffled)

    assert render_feed(changes, vendor_id="stripe") == render_feed(shuffled, vendor_id="stripe")


def test_two_entries_differing_only_in_raw_are_ordered_stably():
    """Sorting on the top-level columns alone leaves these two tied, and a tie is where a
    stable-looking order stops being stable: whichever the database returned first would win."""
    a = _change(raw={"text": "removed the `status` property"})
    b = _change(raw={"text": "removed the `amount` property"})

    assert render_feed([a, b], vendor_id="stripe") == render_feed([b, a], vendor_id="stripe")


def test_raw_key_order_does_not_reach_the_bytes():
    """`raw` is stored as JSONB, and Postgres does not preserve key order. The same row read
    back from the store therefore arrives with its keys in a different order than the run that
    wrote it, so a renderer trusting insertion order would republish different bytes for a
    change nobody touched -- and would fail to recognise the two as duplicates.
    """
    first = _change(raw={"id": "response-property-removed", "text": "removed `status`"})
    reordered = _change(raw={"text": "removed `status`", "id": "response-property-removed"})

    assert render_feed([first], vendor_id="stripe") == render_feed([reordered], vendor_id="stripe")
    assert len(_entries(render_feed([first, reordered], vendor_id="stripe"))) == 1


def test_the_same_change_twice_appears_once():
    """Two adapters over an overlapping version window produce the same row twice. A feed that
    carried it twice would make every consumer's count wrong."""
    assert len(_entries(render_feed([_change(), _change()], vendor_id="stripe"))) == 1


# --- no customer data, ever --------------------------------------------------------


class _LeakyChange(VendorChange):
    """What a future column looks like before anyone notices it is customer-specific."""

    call_site_id: str = "cs-0dcb41f2"
    observed_field_path: str = "/data/status"


def test_no_field_outside_the_contract_reaches_the_payload():
    """Asserted against the rendered bytes rather than the input, because the input is exactly
    what a future change would alter. The feed is vendor-side public information produced before
    any customer relationship exists; a call site is the customer's code and an observed shape is
    their traffic, and neither has any business in a file served to everyone.
    """
    payload = render_feed([_LeakyChange(**_change().model_dump())], vendor_id="stripe")

    assert b"cs-0dcb41f2" not in payload
    assert b"observed_field_path" not in payload
    assert tuple(sorted(_entries(payload)[0])) == tuple(sorted(FEED_FIELDS))


# --- signing, and the order of the two gates --------------------------------------


def test_a_signed_feed_round_trips(keypair):
    private_key, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")

    parsed = verify_and_parse(payload, sign_feed(payload, private_key), public)

    assert [c.operation_id for c in parsed] == ["PostCharges"]
    assert parsed[0].raw["text"] == "removed the `status` property"


def test_a_tampered_payload_is_rejected(keypair):
    """One flipped byte. The feed drives code changes, so a forged entry proposes a patch
    against real code."""
    private_key, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")
    signature = sign_feed(payload, private_key)
    tampered = payload.replace(b"PostCharges", b"PostRefunds")

    with pytest.raises(FeedSignatureError):
        verify_and_parse(tampered, signature, public)


def test_a_signature_from_another_key_is_rejected(keypair):
    _, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")
    impostor = Ed25519PrivateKey.generate()

    with pytest.raises(FeedSignatureError):
        verify_and_parse(payload, sign_feed(payload, impostor), public)


@pytest.mark.parametrize("signature", [b"", b"too-short", bytes(64)], ids=["empty", "short", "zeros"])
def test_a_missing_or_malformed_signature_is_a_hard_failure(keypair, signature):
    """Never a warning, never a degraded mode. An unsigned feed that drives code changes is a
    supply-chain surface, and "verify if you can" is the same as not verifying."""
    _, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")

    with pytest.raises(FeedSignatureError):
        verify_and_parse(payload, signature, public)


def test_verification_runs_before_any_row_is_constructed(keypair, monkeypatch):
    """The order is the point, not an implementation detail. Parsing first would build
    `VendorChange` rows out of bytes nothing has vouched for, and by the time the signature
    check failed the objects would already exist for something downstream to use.
    """
    import sync.signals.feed.consumer as consumer

    def _never(*args, **kwargs):
        raise AssertionError("a row was constructed before the signature was checked")

    monkeypatch.setattr(consumer, "VendorChange", _never)

    private_key, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")
    signature = sign_feed(payload, private_key)

    with pytest.raises(FeedSignatureError):
        verify_and_parse(payload.replace(b"stripe", b"stripey"), signature, public)


def test_a_validly_signed_payload_carrying_a_bad_change_is_still_rejected(keypair):
    """A signature proves origin, not correctness. Whoever holds the key can sign nonsense, and
    a compromised or simply buggy publisher is exactly the case where the second gate earns its
    keep."""
    private_key, public = keypair
    payload = json.dumps([{**_change().model_dump(mode="json"), "severity": "catastrophic"}]).encode("utf-8")

    with pytest.raises(FeedFormatError):
        verify_and_parse(payload, sign_feed(payload, private_key), public)


def test_a_validly_signed_top_level_object_is_rejected(keypair):
    """The array is the whole contract. An envelope is the shape a future maintainer reaches for
    when they want to add a field to the file rather than to an entry."""
    private_key, public = keypair
    payload = json.dumps({"changes": [_change().model_dump(mode="json")]}).encode("utf-8")

    with pytest.raises(FeedFormatError):
        verify_and_parse(payload, sign_feed(payload, private_key), public)


def test_a_validly_signed_payload_that_is_not_json_is_rejected(keypair):
    private_key, public = keypair
    payload = b"<!doctype html><title>404</title>"

    with pytest.raises(FeedFormatError):
        verify_and_parse(payload, sign_feed(payload, private_key), public)


def test_the_two_failures_are_different_types(keypair):
    """Two gates, two failure modes, and neither substitutes for the other. A caller that
    cannot tell a forgery from a malformed entry cannot report either one usefully."""
    assert not issubclass(FeedSignatureError, FeedFormatError)
    assert not issubclass(FeedFormatError, FeedSignatureError)
    assert issubclass(FeedSignatureError, ValueError) and issubclass(FeedFormatError, ValueError)


# --- the format is versioned by never breaking it ---------------------------------


def test_an_unrecognised_kind_is_tolerated():
    """`kind` is an oasdiff rule identifier and the set grows with each release. A consumer that
    rejected an unknown one would break on the vendor's schedule rather than on ours."""
    payload = render_feed([_change(kind="response-property-any-of-added")], vendor_id="stripe")

    assert parse_feed(payload)[0].kind == "response-property-any-of-added"


def test_an_added_optional_field_does_not_break_a_consumer():
    """New fields may be added as optional; nothing is renamed or removed. An older consumer
    reading a newer feed has to keep working, or the format is versioned after all."""
    entry = {**_change().model_dump(mode="json"), "confidence": 0.8}
    payload = json.dumps([entry]).encode("utf-8")

    assert parse_feed(payload)[0].operation_id == "PostCharges"


def test_verify_feed_raises_rather_than_returning_false(keypair):
    """A boolean return is a value a caller can forget to check, and this one decides whether
    unauthenticated bytes become a patch against real code."""
    private_key, public = keypair
    payload = render_feed([_change()], vendor_id="stripe")

    assert verify_feed(payload, sign_feed(payload, private_key), public) is None
    with pytest.raises(FeedSignatureError):
        verify_feed(b"other", sign_feed(payload, private_key), public)

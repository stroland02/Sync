"""Verifying and parsing the public change feed.

Two gates, in one order, and neither substitutes for the other.

`verify_feed` proves the bytes came from whoever holds the publishing key. `parse_feed` proves
they say something a consumer can act on. A signature is not a correctness proof -- whoever holds
the key can sign nonsense, and a compromised or simply buggy publisher is the case the second
gate exists for. So a validly signed payload carrying a malformed change still fails.

Verification runs first, and that ordering is the point rather than an implementation detail.
Parsing first would build `VendorChange` rows out of bytes nothing has vouched for, and by the
time the signature check failed those objects would already exist for something downstream to
use. The feed drives code changes: a forged entry proposes a patch against real code.

Neither failure is a warning. "Verify if you can" is the same as not verifying, so a missing or
unreadable signature raises exactly as a forged one does.

What a signature is not
-----------------------
It is not a reason to trust the change further than any other input. A signed, correctly parsed
`VendorChange` still produces a patch that must pass `tsc` and the customer's own CI before it
reaches a pull request. Signing raises the cost of poisoning the feed; the verification gate is
what makes poisoning it unprofitable even if it succeeds.
"""

from __future__ import annotations

import json

from cryptography.exceptions import InvalidSignature

from sync.core import VendorChange
from sync.signals.feed.publisher import load_public_key


class FeedSignatureError(ValueError):
    """The bytes are not vouched for by the publishing key."""


class FeedFormatError(ValueError):
    """The bytes are vouched for and still do not say anything usable."""


def verify_feed(payload: bytes, signature: bytes, public_key: bytes) -> None:
    """Raise unless `signature` is the publisher's over exactly these bytes.

    Raises rather than returning a boolean: a returned `False` is a value a caller can forget to
    check, and this one decides whether unauthenticated bytes become a patch against real code.

    Every way the check can fail collapses to one exception. A signature of the wrong length, a
    malformed key and a genuine forgery are the same event to a consumer -- these bytes are not
    trusted -- and offering three exceptions invites a caller to handle two of them.
    """
    try:
        load_public_key(public_key).verify(signature, payload)
    except (InvalidSignature, ValueError) as exc:
        raise FeedSignatureError("feed signature does not verify") from exc


def parse_feed(payload: bytes) -> list[VendorChange]:
    """The feed's entries, or `FeedFormatError`.

    A top-level object is rejected rather than unwrapped. The array is the whole contract, and an
    envelope is what a future maintainer reaches for when they want to add a field to the file
    rather than to an entry -- accepting one here is how the format acquires a version.

    Unknown keys inside an entry are ignored, which is the other half of the same promise: new
    fields may be added as optional, so an older consumer reading a newer feed keeps working.
    """
    try:
        entries = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FeedFormatError("feed payload is not JSON") from exc

    if not isinstance(entries, list):
        raise FeedFormatError(f"feed payload is a {type(entries).__name__}, not an array")

    try:
        return [VendorChange(**entry) for entry in entries]
    except (TypeError, ValueError) as exc:
        raise FeedFormatError("feed payload carries an entry that is not a VendorChange") from exc


def verify_and_parse(payload: bytes, signature: bytes, public_key: bytes) -> list[VendorChange]:
    """Both gates, in the only order that is safe."""
    verify_feed(payload, signature, public_key)
    return parse_feed(payload)

"""Holding fetched feeds per vendor, so a consumer answers without refetching.

`render_feed`, `sign_feed`, `public_key_bytes` and `verify_and_parse` were each reachable from
nothing. A signature nobody checks is a signature nobody has to forge, so what was missing was
not a feature but the security property the whole format was designed around. This is the caller
that supplies it.

Nothing here re-implements the gates. `verify_and_parse` already composes them in the only safe
order and already keeps their two failures apart, so this calls it once and stores what came
back. A second copy of that ordering is how the copy ends up wrong.

Why a cache at all
------------------
`2026-07-25-sync-graph-surface-design.md` serves `sync://feed/{vendor}` from a local copy, and
the hosting section of the feed specification rests on it: a customer already holding a snapshot
depends on nothing of Sync's being up. That only holds if a snapshot survives a failed refresh,
which is why `store` mutates nothing until both gates have passed -- otherwise anyone able to
answer a fetch could empty the cache by serving one bad payload, a denial of service reachable
without the signing key.

Two integrity checks, and neither stands in for the other
---------------------------------------------------------
The digest answers "are these the bytes I stored" and the signature answers "did the publisher
write them". Corruption and forgery are different failure modes: a truncated download has a
wrong digest and no valid signature, and a forged feed has a perfectly good digest of bytes the
publisher never saw. Keeping both is the specification's requirement and the reason is that one
of them is not a subset of the other.

Bytes, never text
-----------------
A payload is `bytes` from fetch to verification. The signature covers exact bytes, so a payload
that made a round trip through the platform's default codec is not the payload the publisher
signed -- and on Windows that decode is cp1252, which would pass every ASCII test in this
repository and fail on the first accented vendor description.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sync.core import VendorChange
from sync.signals.feed.consumer import verify_and_parse


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class FeedSnapshot:
    """One vendor's feed as it was fetched, and what can be said about it afterwards.

    Frozen because a snapshot describes a moment. A mutable one would let a caller alter what
    the digest and the signature were computed over, which is the one thing that must stay true
    of it.
    """

    vendor_id: str
    changes: tuple[VendorChange, ...]
    digest: str
    """SHA-256 of the payload, hex. The corruption check, kept alongside the signature."""
    signature: bytes
    """The detached signature these bytes verified against, kept rather than discarded.

    A snapshot that dropped it could not be re-verified against a rotated key, and could not
    show an operator asking why a feed was trusted what it was trusted on.
    """
    fetched_at: datetime
    """When this copy was taken. `sync_whats_changed` reports it as `feed_fetched_at`.

    A timestamp rather than an age, per the graph-surface design: an age computed at fetch time
    and stored would let a cached response report a freshness that expired while it sat here.
    """


class FeedCache:
    """Fetched feeds, per vendor, verified on the way in.

    The key is supplied rather than read from `sync.core` here, for the reason
    `sync.signals.registry` takes its inputs rather than naming them: a deployment verifying
    against a rotated key, and a test verifying against a throwaway one, are the same operation
    with a different anchor. What must not be configurable is *whether* verification happens,
    and there is no argument for that.
    """

    def __init__(self, public_key: bytes, now: Callable[[], datetime] = _now) -> None:
        self._public_key = public_key
        self._now = now
        self._snapshots: dict[str, FeedSnapshot] = {}

    def store(self, vendor_id: str, payload: bytes, signature: bytes) -> FeedSnapshot:
        """Verify, parse, and keep -- in that order, and only all three together.

        `verify_and_parse` raises `FeedSignatureError` for bytes the publisher did not sign and
        `FeedFormatError` for bytes it did sign that say nothing usable. Neither is caught here.
        A cache that swallowed either would turn "these bytes are not trusted" into "this vendor
        published nothing", which is the same answer a healthy vendor with no changes gives.

        Nothing is written until both gates pass, so a rejected refresh leaves the previous
        snapshot exactly as it was.
        """
        changes = verify_and_parse(payload, signature, self._public_key)

        snapshot = FeedSnapshot(
            vendor_id=vendor_id,
            changes=tuple(changes),
            digest=hashlib.sha256(payload).hexdigest(),
            signature=signature,
            fetched_at=self._now(),
        )
        self._snapshots[vendor_id] = snapshot
        return snapshot

    def snapshot(self, vendor_id: str) -> FeedSnapshot | None:
        """What is held for this vendor, or None if nothing has been stored for it.

        None rather than an empty snapshot. A vendor that published no changes renders `[]` and
        is a real fetch with a real timestamp; one never fetched has no timestamp to report, and
        answering the two the same way would present a feed nobody has as up to date.
        """
        return self._snapshots.get(vendor_id)

    def changes(self, vendor_id: str) -> tuple[VendorChange, ...]:
        """This vendor's changes, empty when nothing is held.

        The convenience the read tools want, and it is deliberately the one place the two cases
        do collapse: a caller iterating changes has the same work to do for a vendor that
        published none and one never fetched. A caller that needs to tell them apart asks
        `snapshot`, which is why that answers None.
        """
        held = self._snapshots.get(vendor_id)
        return held.changes if held is not None else ()

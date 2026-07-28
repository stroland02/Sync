"""Rendering and signing the public change feed.

`docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` is binding on this format. One
JSON array per vendor, served as a static file, no authentication, CC0. It exists to commoditise
a layer Sync does not own: several companies alert on consumed-API change and none binds it to a
call site, so giving the normalised feed away makes Sync's schema the one their tooling speaks.
The feed is the giveaway; the binding engine is not.

The array is the whole contract
-------------------------------
No wrapper object, no pagination envelope, no version field. The format is versioned by never
breaking it: new fields may be added as optional, nothing is renamed or removed. `FEED_FIELDS` is
an allow-list rather than a dump of whatever the model holds, because `VendorChange` lives in
`sync.core` where anyone may add a column, and a deny-list would publish it by default.

Two fields the model carries are deliberately not published. `id` is a digest of the row as this
deployment stored it, which says nothing to a consumer holding no such row. `detected_at` is when
Sync noticed, not when the vendor changed -- it moves on every run, and embedding it would break
republication below.

Byte-identical republication
----------------------------
Regenerating a feed whose changes have not moved produces the same bytes, so a cached copy is
never invalidated by a no-op run. Three things make that true and all three are load-bearing:
nothing derived from generation time is emitted, keys are sorted, and entries are ordered by
their own canonical bytes.

Ordering on the rendered bytes rather than on chosen columns is what removes the last tie. Two
changes can agree on every top-level field and differ only inside `raw` -- oasdiff reports many
per operation -- and a sort over columns would leave those two in whatever order the database
returned, which is stable until the day it is not. Two entries that tie on this ordering are
byte-identical, so no tie can exist that the ordering leaves unspecified. Duplicates collapse for
the same reason: a feed carrying one change twice makes every consumer's count wrong.
"""

from __future__ import annotations

import json
from typing import Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from sync.core import VendorChange

FEED_FIELDS = (
    "vendor_id",
    "from_version",
    "to_version",
    "kind",
    "operation_id",
    "path_ptr",
    "severity",
    "source",
    "raw",
)
"""Every field published, and nothing else. See the module docstring."""


def _canonical(change: VendorChange) -> bytes:
    """One entry as the exact bytes it will occupy in the feed.

    Separators are pinned because `json.dumps` defaults to a space after each `:` and `,`, and a
    default is a thing that can change under us; the signature covers exact bytes.
    """
    entry = {field: getattr(change, field) for field in FEED_FIELDS}
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def render_feed(changes: Iterable[VendorChange], vendor_id: str) -> bytes:
    """The published bytes for one vendor.

    Entries from another vendor are dropped rather than published under a filename that does not
    describe them. A vendor that shipped nothing renders `[]` -- a consumer that has to
    special-case absence will get it wrong, and an empty array is the honest answer.
    """
    entries = sorted({_canonical(change) for change in changes if change.vendor_id == vendor_id})
    return b"[" + b",".join(entries) + b"]"


def sign_feed(payload: bytes, private_key: Ed25519PrivateKey) -> bytes:
    """A detached Ed25519 signature over the exact payload bytes.

    Detached because the signature is served as its own file: signing a payload that embedded its
    own signature would require deciding what the signature covers, and every such format has had
    a vulnerability about it.
    """
    return private_key.sign(payload)


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    """The 32 raw bytes of the matching public key.

    Raw rather than PEM because this is what gets committed to `sync.core` as a literal, and a
    key rotatable only through a release should be readable in the diff that rotates it.
    """
    return private_key.public_key().public_bytes_raw()


def load_public_key(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)

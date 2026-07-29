"""The public key the change feed is verified against, as inert bytes.

`docs/superpowers/specs/2026-07-26-sync-public-change-feed.md` puts the key here and says why:
committed in `sync.core` and rotatable only through a release. A key fetched at runtime is a key
an attacker who can answer that fetch gets to choose, so the trust anchor ships with the code
that trusts it, and rotating it is a diff somebody reviews.

Bytes and nothing else
----------------------
`CLAUDE.md` makes `sync.core` import nothing from any sibling package, and
`tests/test_import_boundary.py` enforces it. That rule is what decides the shape of this module:
raw bytes, no `cryptography` import, no `Ed25519PublicKey`, no verification helper. Turning these
bytes into a key belongs to `sync.signals.feed`, which has `load_public_key` for exactly that,
and a third party writing a vendor adapter depends on `sync.core` alone -- one import here to
turn a literal into an object would drag a crypto backend into their dependency tree.

Raw rather than PEM for the same reason `public_key_bytes` returns raw: a key rotatable only
through a release should be readable in the diff that rotates it, and thirty-two bytes of hex is
readable where a base64 block with armour is not.

**This is a development key.** It verifies the signed feeds committed under
`tests/fixtures/feed/`, and nothing else. The private half was generated in a throwaway process
and never written to disk, so these fixtures cannot be re-signed -- which is correct: they are
captured artefacts, and a repository that could re-sign them would be a repository holding a
signing key.

The production key is generated operationally, is not in this repository, and never will be.
Publishing is out of scope for the feed specification by the same reasoning: the keypair and the
publish job are operational rather than architectural. When a real key exists, it replaces the
literal below in a release, and every consumer picks it up by upgrading.
"""

from __future__ import annotations

DEVELOPMENT_FEED_PUBLIC_KEY = bytes.fromhex(
    "6add8a8cdaffd6d984cbddc253fb272d86c1e1debacfc2ac64e0587a8480cca1"
)
"""Ed25519 public key, 32 raw bytes. Verifies the committed feed fixtures only.

Named for what it is. A constant called `FEED_PUBLIC_KEY` would be reached for by a caller who
assumed a production key was already here, and a development key silently trusted in production
verifies nothing an attacker cannot also produce -- they need only generate their own pair,
because this one's private half is not a secret anybody is keeping.
"""

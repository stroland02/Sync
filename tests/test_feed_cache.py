"""The consumer that makes the signed feed worth signing.

`render_feed`, `sign_feed`, `public_key_bytes` and `verify_and_parse` were all reachable from
nothing, which makes a signature cryptography with no security property: bytes nobody verifies
are bytes nobody has to forge. `FeedCache` is the caller that turns them into a path.

Every test here drives `FeedCache`. One that called `verify_and_parse` itself would prove the
consumer works, which was never in doubt, and say nothing about whether the gate is reached.

No private key is committed, so the fixtures under `tests/fixtures/feed/` cannot be re-signed.
Tests needing a fresh signature generate a throwaway pair in the process that uses it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sync.core import DEVELOPMENT_FEED_PUBLIC_KEY, VendorChange
from sync.signals.feed import (
    FeedCache,
    FeedFormatError,
    FeedSignatureError,
    public_key_bytes,
    render_feed,
    sign_feed,
)
from sync.signals.feed import consumer

FIXTURES = Path(__file__).parent / "fixtures" / "feed"

# Bytes, never text. The signature covers exact bytes, and a payload that made a round trip
# through the platform's default codec is a payload the publisher did not sign -- which on this
# machine would pass every ASCII test and fail on the first accented vendor description.
SIGNED_PAYLOAD = (FIXTURES / "stripe.json").read_bytes()
SIGNED_SIGNATURE = (FIXTURES / "stripe.json.sig").read_bytes()


@pytest.fixture()
def signer():
    """A keypair that exists only for the test that asks for it.

    Generated rather than committed. `CLAUDE.md` is unqualified that we hold no secrets, and the
    same discipline applies to our own: a private key in a fixture is a private key in every
    clone, every fork and every CI log that ever cats it.
    """
    private = Ed25519PrivateKey.generate()

    def sign(payload: bytes) -> tuple[bytes, bytes]:
        return sign_feed(payload, private), public_key_bytes(private)

    return sign


@pytest.fixture()
def constructions(monkeypatch):
    """Every `VendorChange` the parser builds, in order.

    The spec asks for proof that verification runs *before* parsing, and an assertion that
    `store()` raised cannot tell that from an implementation that parsed first and raised
    second. This records the parse actually happening, so an empty list is the ordering claim.
    """
    built: list[dict] = []
    real = consumer.VendorChange

    class Recording(real):  # type: ignore[misc, valid-type]
        def __init__(self, **fields):
            built.append(fields)
            super().__init__(**fields)

    monkeypatch.setattr(consumer, "VendorChange", Recording)
    return built


def _cache(**overrides) -> FeedCache:
    return FeedCache(public_key=DEVELOPMENT_FEED_PUBLIC_KEY, **overrides)


# --- both gates, in one order -----------------------------------------------------


def test_a_signed_feed_becomes_a_snapshot_of_its_changes():
    snapshot = _cache().store("stripe", SIGNED_PAYLOAD, SIGNED_SIGNATURE)

    assert snapshot.vendor_id == "stripe"
    assert {change.operation_id for change in snapshot.changes} == {"GetCharges", "PostRefunds"}
    assert all(isinstance(change, VendorChange) for change in snapshot.changes)


def test_a_flipped_byte_is_rejected_before_any_vendor_change_is_constructed(constructions):
    """The spec's first verification item, and the reason it says *before* rather than *and*.

    One byte is flipped inside a string value, so the payload is still valid JSON carrying two
    valid entries -- only the signature no longer covers it. An implementation that parsed first
    would build both changes and then raise, and would pass an assertion that only checked the
    exception. The empty construction list is what separates the two.
    """
    tampered = SIGNED_PAYLOAD.replace(b"GetCharges", b"GetCharqes")
    assert tampered != SIGNED_PAYLOAD

    with pytest.raises(FeedSignatureError):
        _cache().store("stripe", tampered, SIGNED_SIGNATURE)

    assert constructions == []


def test_unverifiable_bytes_fail_as_a_forgery_rather_than_as_a_bad_format():
    """The ordering again, asked the other way round. These bytes are both unsigned and
    unparseable, so the exception says which gate ran first -- `FeedFormatError` here would mean
    the parser saw bytes nothing had vouched for.
    """
    with pytest.raises(FeedSignatureError):
        _cache().store("stripe", b"not json at all", SIGNED_SIGNATURE)


def test_a_validly_signed_payload_that_is_not_a_feed_still_fails(signer):
    """A signature proves origin, not correctness. Whoever holds the key can sign nonsense, and
    a compromised or simply buggy publisher is the case the second gate exists for -- so this
    fails at parse, and says so with the other error type.
    """
    payload = b'[{"vendor_id": "stripe"}]'
    signature, public_key = signer(payload)

    with pytest.raises(FeedFormatError):
        FeedCache(public_key=public_key).store("stripe", payload, signature)


def test_a_top_level_object_is_rejected_and_a_bare_array_is_accepted(signer):
    """The array is the whole contract. An envelope is what a maintainer reaches for when they
    want to add a field to the file rather than to an entry, and accepting one is how the format
    acquires a version it promised never to have.
    """
    wrapped = b'{"changes": []}'
    signature, public_key = signer(wrapped)
    with pytest.raises(FeedFormatError):
        FeedCache(public_key=public_key).store("stripe", wrapped, signature)

    bare = (FIXTURES / "empty.json").read_bytes()
    empty = _cache().store("stripe", bare, (FIXTURES / "empty.json.sig").read_bytes())
    assert empty.changes == ()


# --- what the snapshot keeps ------------------------------------------------------


def test_the_snapshot_keeps_the_digest_and_the_signature(signer):
    """Both, because corruption and forgery are different failure modes and one check does not
    stand in for the other. The digest answers "are these the bytes I stored"; the signature
    answers "did the publisher write them", and a snapshot holding only one can answer only one.
    """
    import hashlib

    snapshot = _cache().store("stripe", SIGNED_PAYLOAD, SIGNED_SIGNATURE)

    assert snapshot.digest == hashlib.sha256(SIGNED_PAYLOAD).hexdigest()
    assert snapshot.signature == SIGNED_SIGNATURE


def test_the_snapshot_carries_when_it_was_fetched():
    """`sync_whats_changed` reports `feed_fetched_at` so a stale feed degrades legibly rather
    than silently. A timestamp rather than an age, because a cached response must not report a
    freshness that expired while it sat in the cache.
    """
    fetched = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

    snapshot = _cache(now=lambda: fetched).store("stripe", SIGNED_PAYLOAD, SIGNED_SIGNATURE)

    assert snapshot.fetched_at == fetched


def test_a_stored_feed_answers_without_being_refetched():
    """What a cache is for. The hosting section rests on it: a customer already holding a copy
    depends on nothing of Sync's being up.
    """
    cache = _cache()
    cache.store("stripe", SIGNED_PAYLOAD, SIGNED_SIGNATURE)

    assert cache.snapshot("stripe") is not None
    assert cache.changes("stripe") == cache.snapshot("stripe").changes


def test_a_vendor_never_stored_is_absent_rather_than_empty():
    """Absent and "published nothing" are different answers. A vendor that shipped no changes
    renders `[]` and is a real snapshot; one never fetched has no snapshot at all, and
    collapsing the two would report a feed nobody has as up to date.
    """
    cache = _cache()

    assert cache.snapshot("twilio") is None
    assert cache.changes("twilio") == ()


def test_a_rejected_feed_leaves_the_previous_snapshot_in_place():
    """A forged update must not evict a good copy. Otherwise anybody able to answer a fetch can
    empty the cache by serving one bad payload, which is a denial of service reachable without
    the signing key.
    """
    cache = _cache()
    good = cache.store("stripe", SIGNED_PAYLOAD, SIGNED_SIGNATURE)

    with pytest.raises(FeedSignatureError):
        cache.store("stripe", SIGNED_PAYLOAD.replace(b"GetCharges", b"GetCharqes"),
                    SIGNED_SIGNATURE)

    assert cache.snapshot("stripe") == good


# --- byte-identical republication -------------------------------------------------


def test_a_no_op_republication_is_byte_identical_and_keeps_the_cached_copy(signer):
    """The reason canonical ordering exists. A vendor whose changes have not moved renders the
    same bytes, so re-fetching produces the same digest and a cached copy is never invalidated
    by a run that found nothing.

    Rendered twice from differently-ordered inputs, because a sort over columns would leave two
    entries agreeing on every published field in whatever order the database returned -- stable
    until the day it is not.
    """
    changes = [
        VendorChange(
            vendor_id="stripe", from_version="v1", to_version="v2", kind="k",
            operation_id=f"Op{index}", path_ptr="/p", severity="breaking", source="oasdiff",
            raw={"id": "k", "text": f"entry {index}"},
        )
        for index in range(4)
    ]

    first = render_feed(changes, "stripe")
    second = render_feed(list(reversed(changes)), "stripe")
    assert first == second

    # One signature serves both, which is the property itself: a signature covers exact bytes,
    # so it verifying against the second render proves the two renders are the same bytes.
    signature, public_key = signer(first)
    cache = FeedCache(public_key=public_key)
    before = cache.store("stripe", first, signature)
    after = cache.store("stripe", second, signature)

    assert before.digest == after.digest


# --- what must never be in the repository -----------------------------------------


def test_no_private_key_is_committed_anywhere_in_the_repository():
    """The one failure that cannot be undone by a later commit.

    A private key in git is a private key in every clone, every fork, and every mirror, and
    rotating it does not remove it from history. `CLAUDE.md` is unqualified that we hold no
    customer secrets; the same discipline applies to ours, and this is what makes it a fact
    rather than an intention.

    Every tracked file is scanned, not only the ones this task created -- the point is the
    repository, and a check scoped to one author's files protects nothing.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=Path(__file__).parent.parent,
        capture_output=True, check=True,
    ).stdout.split(b"\0")

    # Key material, scanned everywhere. A committed PEM key carries both its header and its
    # footer -- that is the shape `ssh-keygen`, `openssl`, and every vendor console emit, body
    # lines of base64 in between. A note that quotes the header alone, to name the format a
    # secret would take, is not that shape: it is prose about a hazard, not the hazard. Requiring
    # the pair rather than the header alone is what tells them apart, and it does not cost
    # anything on the positive side -- a real key pasted into the same file still carries both
    # markers and is still caught.
    material = (
        (b"-----BEGIN PRIVATE KEY-----", b"-----END PRIVATE KEY-----"),
        (b"-----BEGIN OPENSSH PRIVATE KEY-----", b"-----END OPENSSH PRIVATE KEY-----"),
        (b"-----BEGIN RSA PRIVATE KEY-----", b"-----END RSA PRIVATE KEY-----"),
        (b"-----BEGIN EC PRIVATE KEY-----", b"-----END EC PRIVATE KEY-----"),
    )
    # A key built in source, scanned in source only. This one is a call, so prose naming it is
    # discussing the hazard rather than committing one -- the task archive quotes it inside the
    # brief that required this test. Scoping it keeps the check precise; widening `material`
    # instead would be the mistake, because that is the half that catches an actual key.
    in_source = (b"Ed25519PrivateKey.from_private_bytes",)
    root = Path(__file__).parent.parent

    offenders = []
    for name in tracked:
        if not name:
            continue
        path = root / name.decode("utf-8")
        if not path.is_file():
            continue
        body = path.read_bytes()
        has_pem_pair = any(begin in body and end in body for begin, end in material)
        has_in_source = path.suffix == ".py" and any(marker in body for marker in in_source)
        if (has_pem_pair or has_in_source) and path != Path(__file__):
            offenders.append(str(path.relative_to(root)))

    assert offenders == []


def test_the_key_scanner_still_catches_a_full_pem_pair_in_the_same_documentation_file():
    """The narrowing above must not have bought its silence on the reference note by going
    blind to a real key -- so this pins the positive case directly against the pairing rule,
    independent of what happens to be committed today.
    """
    header_only = b"...) says GITHUB_APP_PRIVATE_KEY | Contents of the .pem file " \
        b"(including -----BEGIN RSA PRIVATE KEY----- ...)"
    full_pair = (
        b"-----BEGIN RSA PRIVATE KEY-----\n"
        b"MIIEowIBAAKCAQEAsyntheticsyntheticsyntheticsyntheticsynthetic==\n"
        b"-----END RSA PRIVATE KEY-----\n"
    )

    def has_pem_pair(body: bytes) -> bool:
        pairs = (
            (b"-----BEGIN PRIVATE KEY-----", b"-----END PRIVATE KEY-----"),
            (b"-----BEGIN OPENSSH PRIVATE KEY-----", b"-----END OPENSSH PRIVATE KEY-----"),
            (b"-----BEGIN RSA PRIVATE KEY-----", b"-----END RSA PRIVATE KEY-----"),
            (b"-----BEGIN EC PRIVATE KEY-----", b"-----END EC PRIVATE KEY-----"),
        )
        return any(begin in body and end in body for begin, end in pairs)

    assert has_pem_pair(header_only) is False, "a quoted header alone must not read as a key"
    assert has_pem_pair(full_pair) is True, "a header paired with its footer must still be caught"

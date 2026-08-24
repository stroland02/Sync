"""Producing the signed feed files, which nothing in this tree did.

The consuming half has been finished and reachable for a while: `FeedCache` verifies before it
parses and `sync://feed/{vendor}` serves the result. The producing half was three functions in
`sync.signals.feed.publisher` that nothing called, which left the strategic move
`2026-07-25-sync-positioning-and-open-core.md` commits to -- publishing the normalised feed, as
the attack on the vendors whose whole product is a change feed -- rendered by nothing.

This is the command that writes the two files, and deliberately not the thing that serves them.
`2026-07-26-sync-public-change-feed.md` puts hosting outside the architecture: static files
behind a CDN, no server-side logic, and the keypair and publish job are operational. So the
command writes `{vendor}.json` and `{vendor}.json.sig` into a directory it is handed and stops,
which is the shape `ingest` and `merge-outcome` already take.

Every test here generates its own keypair in-process. Nothing under `tests/fixtures/` is a key,
and `test_feed_cache.py` scans every tracked file to keep it that way.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sync.cli import FEED_SIGNING_KEY_ENV, publish_feed
from sync.core import VendorChange
from sync.graph.store import GraphStore
from sync.signals.feed import public_key_bytes, verify_and_parse

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")

CHANGES = [
    VendorChange(
        vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind="response-property-removed", operation_id="PostCharges", path_ptr="/v1/charges",
        severity="breaking", source="oasdiff", raw={"text": "removed the `status` property"},
    ),
    VendorChange(
        vendor_id="stripe", from_version="2026-05-01", to_version="2026-11-01",
        kind="request-property-removed", operation_id="PostRefunds", path_ptr="/v1/refunds",
        severity="breaking", source="oasdiff", raw={"text": "removed the `reason` property"},
    ),
    # A second vendor, so a feed published under one name cannot quietly carry the other's rows.
    VendorChange(
        vendor_id="twilio", from_version="a", to_version="b",
        kind="response-property-removed", operation_id="ListMessages", path_ptr="/Messages",
        severity="breaking", source="oasdiff", raw={"text": "removed the `body` property"},
    ),
]


@pytest.fixture()
def store():
    graph = GraphStore(DSN)
    graph.apply_schema()
    graph.truncate_all()
    for change in CHANGES:
        graph.upsert_vendor_change(change)
    return graph


@pytest.fixture()
def signing_key(tmp_path, monkeypatch):
    """A throwaway pair, generated here and never written anywhere this repository tracks.

    PEM because that is what an operator's key management produces -- `openssl genpkey
    -algorithm ed25519` writes exactly this -- and because loading it needs no call that the
    committed-key scan forbids.
    """
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_file = tmp_path / "signing.pem"
    key_file.write_bytes(pem)
    monkeypatch.setenv(FEED_SIGNING_KEY_ENV, pem.decode("ascii"))
    return private, key_file


def _args(out_dir, vendor="stripe", key_file=None):
    return argparse.Namespace(
        vendor=vendor, out_dir=str(out_dir), key_file=key_file, dsn=DSN
    )


# --- the round trip, which is what proves the two halves agree --------------------


def test_a_published_feed_verifies_and_parses(tmp_path, store, signing_key):
    """Through the consuming half rather than by asserting on the bytes. Asserting the payload
    looks right would pass on a feed no `FeedCache` accepts, and the two halves agreeing is the
    entire reason for building this one."""
    private, _ = signing_key
    out = tmp_path / "out"

    assert publish_feed(_args(out)) == 0

    payload = (out / "stripe.json").read_bytes()
    signature = (out / "stripe.json.sig").read_bytes()
    changes = verify_and_parse(payload, signature, public_key_bytes(private))

    assert sorted(change.operation_id for change in changes) == ["PostCharges", "PostRefunds"]


def test_a_feed_carries_only_its_own_vendor(tmp_path, store, signing_key):
    """One array per vendor, at one filename per vendor. A stray entry would be served under a
    name that does not describe it."""
    private, _ = signing_key
    out = tmp_path / "out"
    publish_feed(_args(out))

    changes = verify_and_parse(
        (out / "stripe.json").read_bytes(),
        (out / "stripe.json.sig").read_bytes(),
        public_key_bytes(private),
    )

    assert {change.vendor_id for change in changes} == {"stripe"}


def test_a_vendor_with_no_changes_publishes_an_empty_array(tmp_path, store, signing_key):
    """The array is the whole contract, so a vendor that shipped nothing has a feed and it is
    empty. A 404, an error, or a missing file would each make a consumer special-case absence,
    and a consumer that has to special-case absence will get it wrong."""
    private, _ = signing_key
    out = tmp_path / "out"

    assert publish_feed(_args(out, vendor="anthropic")) == 0

    payload = (out / "anthropic.json").read_bytes()
    assert payload == b"[]"
    assert verify_and_parse(
        payload, (out / "anthropic.json.sig").read_bytes(), public_key_bytes(private)
    ) == []


# --- byte-identical republication -------------------------------------------------


def test_republishing_unchanged_input_is_byte_identical(tmp_path, store, signing_key):
    """The property the spec's Verification section requires, asserted over both files.

    Ed25519 is deterministic, so a signature that differed would mean the payload differed --
    which is exactly the failure this catches, and it is invisible if only the payload is
    compared. A no-op run that rewrote the bytes would invalidate every cached copy a consumer
    holds, which is the cost the canonical form exists to avoid.
    """
    first, second = tmp_path / "first", tmp_path / "second"

    publish_feed(_args(first))
    publish_feed(_args(second))

    assert (first / "stripe.json").read_bytes() == (second / "stripe.json").read_bytes()
    assert (first / "stripe.json.sig").read_bytes() == (second / "stripe.json.sig").read_bytes()


def test_republishing_into_the_same_directory_is_byte_identical(tmp_path, store, signing_key):
    """The way an operator would actually run it: the same output directory, twice."""
    out = tmp_path / "out"
    publish_feed(_args(out))
    before = ((out / "stripe.json").read_bytes(), (out / "stripe.json.sig").read_bytes())

    publish_feed(_args(out))

    assert ((out / "stripe.json").read_bytes(), (out / "stripe.json.sig").read_bytes()) == before


def test_the_payload_carries_nothing_that_moves_between_runs(tmp_path, store, signing_key):
    """Why republication can be byte-identical at all. `detected_at` is when Sync noticed and
    moves on every ingest; `id` is a digest of the row as this deployment stored it and means
    nothing to a consumer holding no such row."""
    out = tmp_path / "out"
    publish_feed(_args(out))

    entry = json.loads((out / "stripe.json").read_text(encoding="utf-8"))[0]

    assert "detected_at" not in entry
    assert "id" not in entry


# --- the key, which is the whole risk ---------------------------------------------


def test_a_missing_key_refuses_and_writes_nothing(tmp_path, store, monkeypatch):
    """The failure mode is a partial write, not an exception. A consumer fetching a payload
    whose signature does not exist yet has unverified bytes that drive code changes, so the
    assertion is on the directory rather than on the exit code alone.
    """
    monkeypatch.delenv(FEED_SIGNING_KEY_ENV, raising=False)
    out = tmp_path / "out"

    assert publish_feed(_args(out)) == 2
    assert not out.exists() or list(out.iterdir()) == []


def test_an_unreadable_key_refuses_and_writes_nothing(tmp_path, store, monkeypatch):
    """A key that is present and not a key is the same answer. Publishing unsigned because the
    PEM was truncated would be the supply-chain surface the whole design exists to close.

    The material is deliberately not PEM-shaped: `test_feed_cache.py` scans every tracked file
    for private-key armour, and a fixture carrying that header to look realistic would trip the
    check that exists to keep a real one out.
    """
    monkeypatch.setenv(FEED_SIGNING_KEY_ENV, "this is not a key")
    out = tmp_path / "out"

    assert publish_feed(_args(out)) == 2
    assert not out.exists() or list(out.iterdir()) == []


def test_a_key_of_the_wrong_algorithm_refuses_and_writes_nothing(tmp_path, store, monkeypatch):
    """A readable PEM that is not Ed25519. It would sign, and every consumer would reject the
    result as a forgery -- a failure that looks identical to a poisoned feed and would send
    somebody hunting an attacker rather than a configuration mistake.
    """
    from cryptography.hazmat.primitives.asymmetric import ec

    wrong = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv(FEED_SIGNING_KEY_ENV, wrong.decode("ascii"))
    out = tmp_path / "out"

    assert publish_feed(_args(out)) == 2
    assert not out.exists() or list(out.iterdir()) == []


def test_the_signature_is_written_before_the_payload(tmp_path, store, signing_key, monkeypatch):
    """Order, which the finished directory cannot show and which decides what a reader sees
    mid-publish.

    Either order leaves a window where one file exists and the other does not, and the two
    windows are not equally safe. A signature with no payload is a fetch that fails; a payload
    with no signature is unverified bytes a consumer may act on, which is the supply-chain
    surface the whole design exists to close.
    """
    written: list[str] = []
    real = Path.write_bytes

    def recording(self, data):
        written.append(self.name)
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", recording)
    publish_feed(_args(tmp_path / "out"))

    assert written == ["stripe.json.sig", "stripe.json"]


def test_a_key_file_is_accepted_as_well_as_the_environment(tmp_path, store, signing_key,
                                                           monkeypatch):
    """Two sources and no third. An environment variable is how a process holds a credential
    without it reaching a file; a file is how an operator holds one without it reaching a
    process listing. `--key VALUE` is deliberately not offered."""
    private, key_file = signing_key
    monkeypatch.delenv(FEED_SIGNING_KEY_ENV, raising=False)
    out = tmp_path / "out"

    assert publish_feed(_args(out, key_file=str(key_file))) == 0
    assert verify_and_parse(
        (out / "stripe.json").read_bytes(),
        (out / "stripe.json.sig").read_bytes(),
        public_key_bytes(private),
    )


def test_the_command_takes_no_key_value_argument():
    """Asserted against the parser rather than trusted. An argument holding the key would be
    visible in `ps` and land in shell history, and the reason it is absent has to survive
    somebody adding one for convenience."""
    import sync.cli as cli

    parser_source = Path(cli.__file__).read_text(encoding="utf-8")

    assert '"--key"' not in parser_source
    assert "'--key'" not in parser_source


def test_nothing_the_command_prints_narrows_the_key(tmp_path, store, signing_key, capsys):
    """The public half is publishable and the private half must not be derivable from anything
    said out loud. Asserted over both streams against the PEM, its body, and the raw private
    bytes."""
    private, _ = signing_key
    publish_feed(_args(tmp_path / "out"))

    printed = capsys.readouterr()
    said = printed.out + printed.err
    raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    assert raw.hex() not in said
    assert os.environ[FEED_SIGNING_KEY_ENV] not in said
    for line in os.environ[FEED_SIGNING_KEY_ENV].splitlines():
        if line and "-----" not in line:
            assert line not in said


# --- what it deliberately does not do ---------------------------------------------


def test_publishing_binds_no_port_and_uploads_nothing(tmp_path, store, signing_key):
    """Hosting is outside the architecture: static files behind a CDN, no server-side logic.
    The command writes two files and stops, so whoever runs it decides where the bytes go --
    the same boundary `ingest` and `merge-outcome` hold.
    """
    import inspect

    out = tmp_path / "out"
    publish_feed(_args(out))

    assert sorted(path.name for path in out.iterdir()) == ["stripe.json", "stripe.json.sig"]

    # Scoped to this command rather than to the whole module. It read every line of `cli.py`
    # until `CI-W589` added `vendors probe`, whose entire job is to reach the network -- and a
    # whole-file ban that a legitimate command trips is one somebody deletes rather than narrows,
    # which would lose the property this actually guards.
    source = inspect.getsource(publish_feed)
    for forbidden in ("socket", "bind(", "boto3", "upload", "requests.put", "urlopen"):
        assert forbidden not in source

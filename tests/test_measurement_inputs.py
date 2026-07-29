"""The pinning half of the measurement fetcher, driven from committed fixtures.

No test here invokes `gh` or touches the network, which is the same split
`tests/test_mine_stripe_migrations.py` is built around: fetching is impure and
untested, and everything that decides whether a fetched artifact is the right one
is pure and is all that is asserted on.

Two committed fixtures stand in for the network. `stripe-openapi-github.json` holds
GitHub's own answers about the seven tags, verbatim, so the pins in the script are
checked against the vendor's statement rather than against a copy of themselves.
`stripe-spec3-info.json` holds the `info` block lifted from each distinct
specification, which is the ~200 bytes the three dated versions are read out of and
the only part of a 7.8 MB document that any of the three measurements quotes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.fetch_measurement_inputs import (
    INPUTS,
    MEASUREMENTS,
    InputMismatch,
    PinnedArtifact,
    git_blob_sha,
    verify,
)

FIXTURES = Path(__file__).parent / "fixtures" / "measurement_inputs"


def _github() -> dict:
    return json.loads((FIXTURES / "stripe-openapi-github.json").read_text(encoding="utf-8"))


def _info() -> dict:
    return json.loads((FIXTURES / "stripe-spec3-info.json").read_text(encoding="utf-8"))


def _pinned(data: bytes, **overrides) -> PinnedArtifact:
    """An artifact pinned at exactly `data`, for asserting on what `verify` refuses."""
    fields = {
        "repo": "stripe/openapi",
        "path_in_repo": "openapi/spec3.json",
        "tag": "v9999",
        "commit": "0" * 40,
        "blob_sha": git_blob_sha(data),
        "size_bytes": len(data),
        "api_version": None,
    }
    return PinnedArtifact(**{**fields, **overrides})


# --- content addressing, against git's own answer ----------------------------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"", "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"),
        (b"hello\n", "ce013625030ba8dba906f756967f9e9ca394464a"),
    ],
)
def test_a_blob_hash_is_the_one_git_would_compute(data: bytes, expected: str):
    """The two hashes every git repository contains, used here as an outside reference.

    A blob's name is `sha1("blob <length>\\0" + bytes)` and not the sha1 of the bytes,
    so an implementation that hashed the content alone would agree with nothing GitHub
    reports. These two constants are what `git hash-object` answers for an empty file
    and for `hello\\n`, which makes them evidence this repository did not produce.
    """
    assert git_blob_sha(data) == expected


# --- the pins say what GitHub said -------------------------------------------------


def test_every_pinned_blob_matches_the_committed_github_response():
    """The pattern `tests/fixtures/sdk_packages/` already sets: the declaration is
    compared against the vendor's own artifact rather than against a restatement of
    itself. A pin nobody checked is worse than none, because it moves an input from
    honestly-unreproducible to apparently-pinned."""
    responses = _github()

    for artifact in INPUTS:
        key = f"repos/{artifact.repo}/contents/{artifact.path_in_repo}?ref={artifact.tag}"
        response = responses[key]

        assert response["sha"] == artifact.blob_sha
        assert response["size"] == artifact.size_bytes
        assert response["path"] == artifact.path_in_repo


def test_every_pinned_tag_resolves_to_the_commit_the_pin_names():
    """A tag is a pointer and a commit is not. Recording both is what lets a reader
    tell the two apart later: if Stripe ever moves `v2330`, the fetch fails on the blob
    hash and the commit here is what still names the tree the measurement read."""
    responses = _github()

    for artifact in {(a.repo, a.tag): a for a in INPUTS}.values():
        ref = responses[f"repos/{artifact.repo}/git/ref/tags/{artifact.tag}"]["object"]
        if ref["type"] == "tag":
            ref = responses[f"repos/{artifact.repo}/git/tags/{ref['sha']}"]["object"]

        assert ref["type"] == "commit"
        assert ref["sha"] == artifact.commit


def test_every_declared_api_version_matches_the_committed_info_block():
    """The third claim's whole content. Three dated Stripe versions were read out of
    `info.version`, and this is where the reading is checked against the excerpt rather
    than against the document that quotes it."""
    info = _info()

    for artifact in INPUTS:
        if artifact.api_version is None:
            continue
        assert info[artifact.blob_sha]["version"] == artifact.api_version


# --- a response that is not the pinned one is refused ------------------------------


def test_an_artifact_that_matches_its_pin_is_accepted():
    """The direction that proves the three refusals below are not vacuous."""
    data = b'{"info": {"version": "2026-06-24.dahlia"}}'

    verify(_pinned(data, api_version="2026-06-24.dahlia"), data)


def test_a_truncated_response_is_refused_rather_than_written():
    """The failure this gate exists for. A short read produces a document that still
    parses as JSON often enough to be dangerous, and a measurement taken over it is
    wrong by an amount nobody can see."""
    data = b'{"info": {"version": "2026-06-24.dahlia"}}'
    artifact = _pinned(data)

    with pytest.raises(InputMismatch) as raised:
        verify(artifact, data[:20])

    assert artifact.tag in str(raised.value)
    assert str(len(data)) in str(raised.value)


def test_a_response_of_the_right_length_with_the_wrong_bytes_is_refused():
    """Length alone is not identity. This is what a moved tag looks like: the artifact
    is the right shape and the wrong release."""
    data = b'{"info": {"version": "2026-06-24.dahlia"}}'
    swapped = data.replace(b"2026-06-24", b"2026-05-27")
    artifact = _pinned(data)

    assert len(swapped) == len(data)
    with pytest.raises(InputMismatch) as raised:
        verify(artifact, swapped)

    assert artifact.blob_sha in str(raised.value)


def test_a_specification_whose_api_version_moved_is_refused():
    """Belt and braces over the hash, and it earns its place by naming the thing a
    reader recognises: the dated version is what the measurement quotes, so a mismatch
    should say `2026-06-24.dahlia` rather than only a pair of hashes."""
    data = b'{"info": {"version": "2026-05-27.dahlia"}}'
    artifact = _pinned(data, api_version="2026-06-24.dahlia")

    with pytest.raises(InputMismatch) as raised:
        verify(artifact, data)

    assert "2026-06-24.dahlia" in str(raised.value)
    assert "2026-05-27.dahlia" in str(raised.value)


# --- the three measurements this exists for name inputs that are pinned ------------


def test_every_measurement_names_inputs_the_table_pins():
    """The link between a documented figure and a fetchable artifact. A measurement
    naming an input nobody pins is the state this script exists to leave behind."""
    keys = {artifact.key for artifact in INPUTS}

    for measurement, inputs in MEASUREMENTS.items():
        assert inputs, f"{measurement} names no input"
        for key in inputs:
            assert key in keys, f"{measurement} reads {key}, which nothing pins"


def test_each_artifact_lands_where_the_measurement_commands_look_for_it():
    """`sync run`, `sync ingest` and `sync shapes` all default `--cache` to
    `.cache/specs`, and `registry._prepare_stripe` writes `<tag>.json` and
    `<tag>.sdk.json` into it. Fetching to any other layout would leave a reader holding
    the right bytes in a place nothing reads."""
    for artifact in INPUTS:
        assert artifact.destination.parent == Path(".cache/specs")
        assert artifact.destination.name.startswith(artifact.tag + ".")
        assert artifact.destination.name.endswith(".json")

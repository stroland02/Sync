"""Fetch the pinned artifacts three documented measurements were taken over.

`docs/superpowers/specs/2026-07-29-sync-spec-audit-log-2.md` lists a class of claim it could not
verify: the 105-of-414 symbol coverage, the 327,124-record depth measurement and the three dated
Stripe versions all read `.cache/specs/`, which is gitignored. A figure nobody can re-run is a
figure nobody can challenge, and that is the standard this repository holds its own benchmark to.

This is the path from an empty checkout to those inputs. It fetches nothing that is not pinned and
writes nothing it has not verified.

What is pinned, and why a tag is not enough
-------------------------------------------
A tag is a pointer. `v2330` names a commit today and could name a different one tomorrow, and a
script that fetched by tag alone would look reproducible while quietly producing different bytes.
So each row below carries four things: the tag to fetch by, the commit that tag resolved to on
2026-07-29, the git blob hash of the file at that commit, and its length. The blob hash is the pin
that does the work -- it is computed from the bytes themselves, so a moved tag, a truncated
response and a proxy that rewrote the document all fail the same check, before anything is written.

`tests/fixtures/measurement_inputs/stripe-openapi-github.json` holds GitHub's own answers about
those tags, captured verbatim on 2026-07-29, and `tests/test_measurement_inputs.py` asserts this
table against them. The pins are therefore checked against the vendor's statement rather than
against a restatement of themselves, which is the standard `tests/fixtures/sdk_packages/` already
sets for `generated-vendors.yaml`.

What is committed and what is not
---------------------------------
The specifications are not. `spec3.json` is 7.8 MB and `spec3.sdk.json` is 10 MB; eight of them is
55 MB of vendor document that a fetch reproduces exactly and that `.gitignore` excludes for a
reason. What is committed is the evidence a fetch can be checked against: the GitHub responses
above, and the `info` block of each distinct specification under
`tests/fixtures/measurement_inputs/stripe-spec3-info.json` -- about 200 bytes apiece, and the only
part of the document any of the three measurements quotes.

Seven tags, three specifications
--------------------------------
`spec3.json` is byte-identical across `v2300`/`v2320` and across `v2330`/`v2331`/`v2340`/`v2345`;
Stripe tags every SDK release whether or not the specification moved. That is visible in the blob
hashes below before a single byte is downloaded, and it is the same duplication
`2026-07-25-sync-self-maintaining-apis-design.md` had to correct a measurement over. So a tag whose
blob is already on disk under another tag is copied rather than fetched again, which is 30 MB the
run does not spend and a demonstration of the duplication rather than an assertion about it.

This script does not take any measurement. It puts a reader in a position to take them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Where `sync run`, `sync ingest` and `sync shapes` all default `--cache`, and the layout
# `registry._prepare_stripe` writes into it. Fetching to any other layout would leave a reader
# holding the right bytes somewhere nothing reads.
CACHE = Path(".cache/specs")

DESTINATION_NAMES = {
    "openapi/spec3.json": "{tag}.json",
    "openapi/spec3.sdk.json": "{tag}.sdk.json",
}


class InputMismatch(RuntimeError):
    """A fetched artifact is not the one that was pinned.

    Raised rather than warned, and raised before anything is written. A partial or substituted
    input does not announce itself downstream: it parses, it measures, and it produces a number
    that differs from the documented one by an amount nobody can see.
    """


@dataclass(frozen=True)
class PinnedArtifact:
    """One vendor document, identified by content rather than by where it was found."""

    repo: str
    path_in_repo: str
    tag: str
    commit: str
    blob_sha: str
    size_bytes: int
    api_version: str | None
    """`info.version`, for the documents whose excerpt is committed. None where none is."""

    @property
    def key(self) -> str:
        return f"{self.tag}/{Path(self.path_in_repo).name}"

    @property
    def destination(self) -> Path:
        return CACHE / DESTINATION_NAMES[self.path_in_repo].format(tag=self.tag)


def _stripe(tag: str, commit: str, blob_sha: str, size_bytes: int, api_version: str) -> PinnedArtifact:
    return PinnedArtifact(
        repo="stripe/openapi", path_in_repo="openapi/spec3.json", tag=tag, commit=commit,
        blob_sha=blob_sha, size_bytes=size_bytes, api_version=api_version,
    )


INPUTS: tuple[PinnedArtifact, ...] = (
    _stripe("v2200", "a62576f6c21328289aec64935b6fd3cb81118ed6",
            "7546a97be72fbadc9bdb1bae3cd561286b8c5ecd", 7598844, "2026-02-25.clover"),
    _stripe("v2300", "a7e607228d9579adf9f0367128bb5539a793827d",
            "c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3", 7830636, "2026-05-27.dahlia"),
    _stripe("v2320", "c5dcebd5209b9d34974a4101a3de604998f88558",
            "c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3", 7830636, "2026-05-27.dahlia"),
    _stripe("v2330", "62d4d7c732ca9603130284866b00ba267bf93a10",
            "634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d", 7866866, "2026-06-24.dahlia"),
    _stripe("v2331", "b9e97324c782479a93798fbe7c0ce110439c051b",
            "634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d", 7866866, "2026-06-24.dahlia"),
    _stripe("v2340", "635a63d3abcfa7fef32c3788451e5a5c1caaaa03",
            "634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d", 7866866, "2026-06-24.dahlia"),
    _stripe("v2345", "86b6ae4db114ff06968dcc191ff4a898e9b5db7c",
            "634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d", 7866866, "2026-06-24.dahlia"),
    # The generator input, and the reason the symbol map's verbs come from the vendor rather than
    # from a rule we invented. Only the tag the coverage figure was measured against is pinned:
    # no documented measurement reads it at any other tag, and it is 10 MB.
    PinnedArtifact(
        repo="stripe/openapi", path_in_repo="openapi/spec3.sdk.json", tag="v2330",
        commit="62d4d7c732ca9603130284866b00ba267bf93a10",
        blob_sha="3e278ec902d488bf3aa41eb0294b8c1fd15ddc14", size_bytes=10059776,
        api_version=None,
    ),
)

# Which inputs each documented figure reads. Named so that a reader arriving from one of the three
# documents can fetch what that figure needs and nothing else, and so that a measurement citing an
# artifact nobody pins is a test failure rather than a discovery made months later.
MEASUREMENTS: dict[str, tuple[str, ...]] = {
    # `2026-07-25-sync-self-maintaining-apis-design.md`: 179 symbols over 105 of 414 `/v1/` paths,
    # measured against the cached v2330 with and without the SDK document's `x-stableId`.
    "symbol-coverage-105-of-414": ("v2330/spec3.json", "v2330/spec3.sdk.json"),
    # The same document: 672,286 breaking records and 327,124 after the noise filter, over the one
    # window the duplicate specifications collapse to. v2300 is the same bytes as v2320, so either
    # names the same window.
    "breaking-record-depth-327124": ("v2320/spec3.json", "v2330/spec3.json"),
    # `2026-07-28-sync-ground-truth-count.md` and `2026-07-29-sync-ground-truth-quality.md`: the
    # three dated versions, read from `info.version`. All seven tags, because the claim is about
    # which tag carries which version and four of the seven are only interesting once observed.
    "three-dated-stripe-versions": (
        "v2200/spec3.json", "v2300/spec3.json", "v2320/spec3.json", "v2330/spec3.json",
        "v2331/spec3.json", "v2340/spec3.json", "v2345/spec3.json",
    ),
}


def git_blob_sha(data: bytes) -> str:
    """The name git gives these bytes, which is what GitHub reports as a file's `sha`.

    A blob is hashed with its type and length prefixed, so this is deliberately not the sha1 of
    the content alone -- that would agree with nothing the API says.
    """
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def verify(artifact: PinnedArtifact, data: bytes) -> None:
    """Refuse anything that is not the pinned bytes, naming what differed.

    Length first because it is the failure with the most misleading downstream behaviour: a
    truncated JSON document usually raises somewhere far from here, and occasionally does not
    raise at all.
    """
    if len(data) != artifact.size_bytes:
        raise InputMismatch(
            f"{artifact.key} at {artifact.tag}: expected {artifact.size_bytes} bytes, got "
            f"{len(data)}"
        )
    actual = git_blob_sha(data)
    if actual != artifact.blob_sha:
        raise InputMismatch(
            f"{artifact.key} at {artifact.tag}: expected blob {artifact.blob_sha}, got {actual}"
        )
    if artifact.api_version is None:
        return
    declared = json.loads(data.decode("utf-8")).get("info", {}).get("version")
    if declared != artifact.api_version:
        raise InputMismatch(
            f"{artifact.key} at {artifact.tag}: expected info.version {artifact.api_version}, got "
            f"{declared}"
        )


def gh_raw(artifact: PinnedArtifact) -> bytes:
    """The file's bytes at the pinned tag, through the authenticated `gh` CLI.

    The raw Accept header rather than the default JSON envelope: both documents are larger than
    the 1 MB limit GitHub enforces on the base64 `.content` field, so the envelope form returns an
    empty string for exactly the files this script exists to fetch. Bytes are captured unchanged,
    with no `text=True` round trip, so a console's non-UTF-8 default cannot corrupt them.
    """
    result = subprocess.run(
        [
            "gh", "api", f"repos/{artifact.repo}/contents/{artifact.path_in_repo}?ref={artifact.tag}",
            "--header", "Accept: application/vnd.github.raw",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{artifact.key}: gh failed: {result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def resolve(artifacts: tuple[PinnedArtifact, ...], fetch=gh_raw) -> list[tuple[PinnedArtifact, str]]:
    """Put every artifact on disk at its destination, verified, and say how each got there.

    Three ways an artifact arrives, and each is reported rather than assumed: it was already
    there and still verifies, it was copied from another tag carrying the same blob, or it was
    fetched. A destination that exists and does not verify is a failure and not a cache miss --
    silently replacing it would hide whatever wrote the wrong bytes.
    """
    written: dict[str, Path] = {}
    outcomes: list[tuple[PinnedArtifact, str]] = []

    for artifact in artifacts:
        destination = artifact.destination
        if destination.exists():
            verify(artifact, destination.read_bytes())
            written.setdefault(artifact.blob_sha, destination)
            outcomes.append((artifact, "cached"))
            continue

        source = written.get(artifact.blob_sha)
        data = source.read_bytes() if source else fetch(artifact)
        verify(artifact, data)

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        # `setdefault`, so every copy names the tag the bytes were fetched under rather than
        # whichever copy happened to be written last.
        written.setdefault(artifact.blob_sha, destination)
        outcomes.append((artifact, f"copied from {source.name}" if source else "fetched"))

    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--measurement", choices=sorted(MEASUREMENTS),
        help="fetch only what one documented figure reads; default is all of them",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print what would be fetched, and fetch nothing",
    )
    args = parser.parse_args()

    wanted = INPUTS
    if args.measurement:
        keys = set(MEASUREMENTS[args.measurement])
        wanted = tuple(artifact for artifact in INPUTS if artifact.key in keys)

    if args.list:
        for artifact in wanted:
            print(f"{artifact.key}\t{artifact.commit}\t{artifact.blob_sha}\t"
                  f"{artifact.size_bytes}\t{artifact.destination}")
        return 0

    try:
        outcomes = resolve(wanted)
    except InputMismatch as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    for artifact, outcome in outcomes:
        print(f"{artifact.destination} {outcome} ({artifact.size_bytes} bytes, "
              f"blob {artifact.blob_sha[:12]})")
    print(f"\n{len(outcomes)} inputs verified against their pins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

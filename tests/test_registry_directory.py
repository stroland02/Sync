"""The registry tier, which discovers that a vendor exists rather than what it changed.

`api.apis.guru/v2/list.json` is one document describing every API the directory holds, and that
shape is what makes this tier cheap: one fetch yields every vendor's last-updated time, so a
specification is downloaded only when a timestamp moves. Tier 0 must poll one manifest per SDK
repository.

What it cannot do is speak for the vendor. `swaggerUrl` points at the registry's own storage,
not the vendor's host, and a large share of entries are Swagger 2.0 rather than OpenAPI 3. A
converted mirror is a third derivation from the vendor's truth, so these entries are evidence
that an API exists and roughly when it moved -- which is what dependency intake needs -- and not
a source a pull request may rest on.

No test here reaches the network. The fixture is an excerpt of the real document, kept to the
fields this module reads.
"""

from __future__ import annotations

import json
from pathlib import Path

from sync.signals.registry_tier.directory import RegistryEntry, parse_directory, versions_after

FIXTURE = Path(__file__).parent / "fixtures" / "registry" / "list_excerpt.json"


def _document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_every_entry_becomes_one_record_per_api():
    entries = parse_directory(_document())
    assert {e.api_id for e in entries} == {"1forge.com", "stripe.com"}


def test_an_entry_carries_every_version_it_declares():
    entries = {e.api_id: e for e in parse_directory(_document())}
    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_the_preferred_version_is_recorded_rather_than_guessed():
    """A directory that names its own preferred version has answered the question. Picking the
    highest-sorting key instead would be a guess, and version strings here are dates for some
    vendors and integers for others."""
    entries = {e.api_id: e for e in parse_directory(_document())}
    assert entries["stripe.com"].preferred == "2022-11-15"


def test_provenance_is_recorded_as_a_mirror_not_as_the_vendor():
    """The rung this tier carries. `swaggerUrl` points at the registry's storage, so a change
    derived from it is not the vendor's published word and must not be indistinguishable from
    one that is."""
    entries = {e.api_id: e for e in parse_directory(_document())}
    version = entries["stripe.com"].versions["2022-11-15"]
    assert version.provenance == "registry-mirror"
    assert version.spec_url.startswith("https://api.apis.guru/")


def test_the_openapi_dialect_is_recorded_because_two_point_oh_needs_conversion():
    """`oasdiff` takes OpenAPI 3. A Swagger 2.0 entry needs converting first, which is a further
    derivation, so the dialect has to survive parsing rather than be discovered later."""
    entries = {e.api_id: e for e in parse_directory(_document())}
    assert entries["1forge.com"].versions["0.0.1"].openapi_version == "2.0"
    assert entries["stripe.com"].versions["2022-11-15"].openapi_version == "3.0"


def test_only_versions_updated_since_the_watermark_are_returned():
    """The whole reason this tier is cheap. One fetch of the directory answers what moved, so a
    specification is downloaded only when its timestamp advances past what was last seen."""
    entries = parse_directory(_document())
    moved = versions_after(entries, "2021-01-01T00:00:00.000Z")
    assert [(e.api_id, v) for e, v in moved] == [("stripe.com", "2022-11-15")]


def test_a_watermark_ahead_of_everything_returns_nothing():
    """The ordinary poll: nothing moved, nothing downloaded."""
    assert versions_after(parse_directory(_document()), "2030-01-01T00:00:00.000Z") == []


def test_an_entry_missing_its_versions_map_is_skipped_rather_than_raising():
    """A public directory is untrusted input. One malformed entry must not cost the other
    thousands, and skipping is the honest answer -- an entry with no versions has nothing to
    say about what changed."""
    document = _document()
    document["broken.com"] = {"added": "2020-01-01T00:00:00.000Z"}
    assert {e.api_id for e in parse_directory(document)} == {"1forge.com", "stripe.com"}


# ---------------------------------------------------------------------------------------------
# The four skips, one test each, asserted on which entries and versions came back.
#
# Every one of them is a `continue`, and a `continue` is the easiest thing in this file to write
# an unfalsifiable test against: deleting one usually makes some distant assertion fail for an
# unrelated reason. So each of these asserts the surviving set exactly rather than checking that
# one id is absent, because an exact set is what changes when a skip stops skipping -- and it
# also fails if the skip starts eating a good entry.
# ---------------------------------------------------------------------------------------------

GOOD = {"1forge.com", "stripe.com"}


def test_an_entry_whose_body_is_not_an_object_is_skipped():
    """`directory.py:78`. The directory is one object keyed by api id, and a key whose value is
    not an object cannot be an entry -- `body.get` would raise on it."""
    document = _document()
    document["scalar.com"] = "2020-01-01T00:00:00.000Z"
    document["array.com"] = ["0.0.1"]

    assert {e.api_id for e in parse_directory(document)} == GOOD


def test_a_version_whose_detail_is_not_an_object_is_skipped_without_costing_the_entry():
    """`directory.py:86`. One bad version, and the entry keeps the rest.

    This is the finer grain of the same rule one level down: the skip is scoped to the version,
    so an API with one malformed version is still discovered through its good ones. Asserting the
    entry's surviving version list is what distinguishes that from skipping the whole entry.
    """
    document = _document()
    document["stripe.com"]["versions"]["2021-broken"] = "not an object"

    entries = {e.api_id: e for e in parse_directory(document)}

    assert set(entries) == GOOD
    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_a_version_with_no_spec_url_or_no_timestamp_is_skipped():
    """`directory.py:90`. Both halves of the condition, and both are load-bearing.

    Without `swaggerUrl` there is nothing to download, so the entry cannot serve the only purpose
    the tier has. Without a timestamp there is nothing to compare against a watermark, which is
    the tier's whole economy -- and `RegistryVersion.updated` has no empty value that
    `versions_after` could compare, so admitting one would move the failure to the scan.
    """
    document = _document()
    versions = document["stripe.com"]["versions"]
    versions["no-url"] = {"updated": "2024-01-01T00:00:00.000Z", "openapiVer": "3.0"}
    versions["no-timestamp"] = {"swaggerUrl": "https://api.apis.guru/x.json", "openapiVer": "3.0"}

    entries = {e.api_id: e for e in parse_directory(document)}

    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_a_timestamp_that_is_not_a_string_is_skipped_rather_than_falling_back_to_added():
    """The same statement, reached by the route the `or` does not cover.

    `detail.get("updated") or detail.get("added")` falls back when `updated` is *falsy*, not when
    it is unusable. A numeric `updated` is truthy, so it wins the `or` and then fails the string
    check, and the version is skipped even though `added` beside it is perfectly readable. The
    directory writes strings for both, so nothing exercises this in practice; it is pinned
    because the behaviour is not what the expression looks like it does.
    """
    document = _document()
    document["stripe.com"]["versions"]["numeric"] = {
        "updated": 1700000000,
        "added": "2023-11-14T00:00:00.000Z",
        "swaggerUrl": "https://api.apis.guru/v2/specs/stripe.com/numeric/openapi.json",
        "openapiVer": "3.0",
    }

    entries = {e.api_id: e for e in parse_directory(document)}

    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_an_entry_whose_every_version_was_skipped_is_skipped_in_turn():
    """`directory.py:99`. The entry survived its own check and lost all of its versions anyway.

    Distinct from the `versions` map being absent or empty, which line 81 catches before any
    version is read. This is the case where the map was a non-empty object and nothing in it
    parsed, so the entry reaches the end holding no versions -- and `RegistryEntry` with an empty
    map would be read downstream as an API with nothing to watch rather than as one we could not
    read.
    """
    document = _document()
    document["all-bad.com"] = {
        "preferred": "1.0",
        "versions": {"1.0": {"openapiVer": "3.0"}, "2.0": "not an object"},
    }

    assert {e.api_id for e in parse_directory(document)} == GOOD


def test_a_skipped_entry_leaves_no_trace_the_caller_could_count():
    """What the caller observes, and the answer is nothing at all.

    `parse_directory` returns a list of what parsed. There is no second channel -- no count, no
    reason, no collected list of what it declined -- so a document carrying four malformed
    entries parses to exactly the same value as a document that never held them. That is the
    assertion, written as an equality between the two parses rather than as prose, because it is
    the whole of what this module tells a caller about a skip.

    `sync.signals.intake` has the channel this lacks: `IntakeReport.unreadable`, printed to
    stderr by `sync intake`, exists because a manifest that would not parse is not a repository
    with no dependencies. The same argument applies to a directory entry -- a vendor skipped here
    is one Sync will never offer to watch, and it is reported as a clean scan -- but closing it
    means changing this function's signature and both of its callers, which this task does not
    own.
    """
    clean = _document()
    junk = _document()
    junk["scalar.com"] = "not an object"
    junk["no-versions.com"] = {"added": "2020-01-01T00:00:00.000Z"}
    junk["all-bad.com"] = {"versions": {"1.0": {"openapiVer": "3.0"}}}
    junk["bad-detail.com"] = {"versions": {"1.0": "not an object"}}

    def shape(document):
        return [
            (e.api_id, e.preferred, sorted(e.versions), [v.updated for v in e.versions.values()])
            for e in parse_directory(document)
        ]

    assert shape(junk) == shape(clean)
    assert versions_after(parse_directory(junk), "2021-01-01T00:00:00.000Z") == versions_after(
        parse_directory(clean), "2021-01-01T00:00:00.000Z"
    )

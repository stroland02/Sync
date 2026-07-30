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

`parse_directory` answers in two halves: what parsed, and what it declined. The second half is
asserted here one cause at a time, because a skipped entry is a vendor Sync will never offer to
watch and the four causes are four different repairs. The tests that only care about the first
half go through `_entries`.

No test here reaches the network. The fixture is an excerpt of the real document, kept to the
fields this module reads.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sync.signals.registry_tier.directory import RegistryEntry, parse_directory, versions_after

FIXTURE = Path(__file__).parent / "fixtures" / "registry" / "list_excerpt.json"

WATERMARK = "2021-01-01T00:00:00.000Z"


def _document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _entries(document: dict) -> list[RegistryEntry]:
    """The parsed half of the pair, for assertions that are about what came back."""
    return parse_directory(document)[0]


def _faults(document: dict) -> tuple[str, ...]:
    """The declined half, for assertions that are about what did not."""
    return parse_directory(document)[1]


def test_every_entry_becomes_one_record_per_api():
    entries = _entries(_document())
    assert {e.api_id for e in entries} == {"1forge.com", "stripe.com"}


def test_an_entry_carries_every_version_it_declares():
    entries = {e.api_id: e for e in _entries(_document())}
    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_the_preferred_version_is_recorded_rather_than_guessed():
    """A directory that names its own preferred version has answered the question. Picking the
    highest-sorting key instead would be a guess, and version strings here are dates for some
    vendors and integers for others."""
    entries = {e.api_id: e for e in _entries(_document())}
    assert entries["stripe.com"].preferred == "2022-11-15"


def test_provenance_is_recorded_as_a_mirror_not_as_the_vendor():
    """The rung this tier carries. `swaggerUrl` points at the registry's storage, so a change
    derived from it is not the vendor's published word and must not be indistinguishable from
    one that is."""
    entries = {e.api_id: e for e in _entries(_document())}
    version = entries["stripe.com"].versions["2022-11-15"]
    assert version.provenance == "registry-mirror"
    assert version.spec_url.startswith("https://api.apis.guru/")


def test_the_openapi_dialect_is_recorded_because_two_point_oh_needs_conversion():
    """`oasdiff` takes OpenAPI 3. A Swagger 2.0 entry needs converting first, which is a further
    derivation, so the dialect has to survive parsing rather than be discovered later."""
    entries = {e.api_id: e for e in _entries(_document())}
    assert entries["1forge.com"].versions["0.0.1"].openapi_version == "2.0"
    assert entries["stripe.com"].versions["2022-11-15"].openapi_version == "3.0"


def test_only_versions_updated_since_the_watermark_are_returned():
    """The whole reason this tier is cheap. One fetch of the directory answers what moved, so a
    specification is downloaded only when its timestamp advances past what was last seen."""
    entries = _entries(_document())
    moved = versions_after(entries, WATERMARK)
    assert [(e.api_id, v) for e, v in moved] == [("stripe.com", "2022-11-15")]


def test_a_watermark_ahead_of_everything_returns_nothing():
    """The ordinary poll: nothing moved, nothing downloaded."""
    assert versions_after(_entries(_document()), "2030-01-01T00:00:00.000Z") == []


def test_an_entry_missing_its_versions_map_is_skipped_rather_than_raising():
    """A public directory is untrusted input. One malformed entry must not cost the other
    thousands, and skipping is the honest answer -- an entry with no versions has nothing to
    say about what changed."""
    document = _document()
    document["broken.com"] = {"added": "2020-01-01T00:00:00.000Z"}
    assert {e.api_id for e in _entries(document)} == {"1forge.com", "stripe.com"}


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
    """`directory.py:112`. The directory is one object keyed by api id, and a key whose value is
    not an object cannot be an entry -- `body.get` would raise on it."""
    document = _document()
    document["scalar.com"] = "2020-01-01T00:00:00.000Z"
    document["array.com"] = ["0.0.1"]

    assert {e.api_id for e in _entries(document)} == GOOD


def test_a_version_whose_detail_is_not_an_object_is_skipped_without_costing_the_entry():
    """`directory.py:122`. One bad version, and the entry keeps the rest.

    This is the finer grain of the same rule one level down: the skip is scoped to the version,
    so an API with one malformed version is still discovered through its good ones. Asserting the
    entry's surviving version list is what distinguishes that from skipping the whole entry.
    """
    document = _document()
    document["stripe.com"]["versions"]["2021-broken"] = "not an object"

    entries = {e.api_id: e for e in _entries(document)}

    assert set(entries) == GOOD
    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_a_version_with_no_spec_url_or_no_timestamp_is_skipped():
    """`directory.py:126` and `directory.py:133`, which W93 read as one condition.

    Without `swaggerUrl` there is nothing to download, so the entry cannot serve the only purpose
    the tier has. Without a timestamp there is nothing to compare against a watermark, which is
    the tier's whole economy -- and `RegistryVersion.updated` has no empty value that
    `versions_after` could compare, so admitting one would move the failure to the scan.
    """
    document = _document()
    versions = document["stripe.com"]["versions"]
    versions["no-url"] = {"updated": "2024-01-01T00:00:00.000Z", "openapiVer": "3.0"}
    versions["no-timestamp"] = {"swaggerUrl": "https://api.apis.guru/x.json", "openapiVer": "3.0"}

    entries = {e.api_id: e for e in _entries(document)}

    assert sorted(entries["stripe.com"].versions) == ["2020-08-27", "2022-11-15"]


def test_a_numeric_timestamp_falls_back_to_a_readable_added_rather_than_skipping_the_version():
    """The fallback triggers on a timestamp this tier cannot use, not on a falsy one.

    W93 pinned the opposite, because `detail.get("updated") or detail.get("added")` did the
    opposite: a numeric `updated` is truthy, so it won the `or`, failed the string check, and the
    version was skipped while a perfectly readable `added` sat beside it unused. The directory
    writes strings for both, so nothing exercised it in practice -- which is what made it worth
    fixing rather than leaving, since a defect no data reaches is a defect no test will report.
    """
    document = _document()
    document["stripe.com"]["versions"]["numeric"] = {
        "updated": 1700000000,
        "added": "2023-11-14T00:00:00.000Z",
        "swaggerUrl": "https://api.apis.guru/v2/specs/stripe.com/numeric/openapi.json",
        "openapiVer": "3.0",
    }

    entries, faults = parse_directory(document)
    stripe = {e.api_id: e for e in entries}["stripe.com"]

    assert sorted(stripe.versions) == ["2020-08-27", "2022-11-15", "numeric"]
    assert stripe.versions["numeric"].updated == "2023-11-14T00:00:00.000Z"
    assert faults == ()


def test_a_timestamp_that_is_an_empty_string_is_unusable_rather_than_a_value_to_compare():
    """Unusable means no non-empty string in either field, which is why an empty `updated` still
    falls back the way it always did.

    `versions_after` compares strings and `""` compares less than every real timestamp, so a
    version admitted with an empty `updated` would be reported as one that never moves. The `or`
    happened to fall back for an empty `updated` because empty is falsy; it also *admitted* an
    empty `added` when `updated` was absent, since `isinstance("", str)` is true. Both routes now
    answer the same way.
    """
    document = _document()
    versions = document["stripe.com"]["versions"]
    versions["empty-updated"] = {
        "updated": "",
        "added": "2023-11-14T00:00:00.000Z",
        "swaggerUrl": "https://api.apis.guru/v2/specs/stripe.com/empty-updated/openapi.json",
        "openapiVer": "3.0",
    }
    versions["empty-added"] = {
        "added": "",
        "swaggerUrl": "https://api.apis.guru/v2/specs/stripe.com/empty-added/openapi.json",
        "openapiVer": "3.0",
    }

    entries, faults = parse_directory(document)
    stripe = {e.api_id: e for e in entries}["stripe.com"]

    assert stripe.versions["empty-updated"].updated == "2023-11-14T00:00:00.000Z"
    assert "empty-added" not in stripe.versions
    assert len(faults) == 1
    assert "empty-added" in faults[0]


def test_an_entry_whose_every_version_was_skipped_is_skipped_in_turn():
    """`directory.py:146`. The entry survived its own check and lost all of its versions anyway.

    Distinct from the `versions` map being absent or empty, which line 116 catches before any
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

    assert {e.api_id for e in _entries(document)} == GOOD


# ---------------------------------------------------------------------------------------------
# The second channel, one test per cause.
#
# `IntakeReport.unreadable`'s key and shape, which M3-W90 already carried into
# `ReachabilityRanking`: a tuple of strings, each naming its source and its cause, present and
# empty on a clean read. Each string here names the api id it belongs to, and the version too
# where the skip was scoped to one, because the four causes are four different repairs and a
# reader who cannot tell them apart cannot make any of them.
# ---------------------------------------------------------------------------------------------


def test_a_well_formed_document_records_no_faults_and_the_channel_is_still_present():
    """Empty rather than absent, for the reason `ReachabilityRanking.unreadable` is: an absent
    channel does not distinguish a document that read cleanly from one parsed by something that
    never recorded a fault."""
    entries, faults = parse_directory(_document())

    assert {e.api_id for e in entries} == GOOD
    assert faults == ()


def test_an_entry_whose_body_is_not_an_object_is_recorded_against_its_api_id():
    """Cause one. Nothing below the entry was read, so the record is about the whole entry."""
    document = _document()
    document["scalar.com"] = "2020-01-01T00:00:00.000Z"

    faults = _faults(document)

    assert len(faults) == 1
    assert "scalar.com" in faults[0]
    assert "not an object" in faults[0]


def test_an_entry_declaring_no_versions_object_is_recorded_against_its_api_id():
    """The cause W93's table left out because an older test already covered the skip. It is a
    separate repair from a body that is not an object -- the entry is shaped like an entry and
    says nothing about any version -- so it gets its own record."""
    document = _document()
    document["no-versions.com"] = {"added": "2020-01-01T00:00:00.000Z"}
    document["empty-versions.com"] = {"versions": {}}

    faults = _faults(document)

    assert len(faults) == 2
    assert {f.split("'")[1] for f in faults} == {"no-versions.com", "empty-versions.com"}
    assert all("no versions" in f for f in faults)


def test_a_version_whose_detail_is_not_an_object_is_recorded_against_that_version():
    """Cause two, and the record is scoped the way the skip is: the entry survived, so a reader
    is told which version of a discoverable vendor is missing rather than that the vendor is."""
    document = _document()
    document["stripe.com"]["versions"]["2021-broken"] = "not an object"

    faults = _faults(document)

    assert len(faults) == 1
    assert "stripe.com" in faults[0]
    assert "2021-broken" in faults[0]
    assert "not an object" in faults[0]


def test_a_missing_spec_url_and_an_unusable_timestamp_are_recorded_as_different_faults():
    """Causes three and four, which W93's table counted as one row and which are two repairs.

    Nothing to download and nothing to compare against a watermark are different absences in the
    vendor's entry, and a reader told only that the version was unreadable would have to fetch the
    document again to find out which.
    """
    document = _document()
    versions = document["stripe.com"]["versions"]
    versions["no-url"] = {"updated": "2024-01-01T00:00:00.000Z", "openapiVer": "3.0"}
    versions["no-timestamp"] = {"swaggerUrl": "https://api.apis.guru/x.json", "openapiVer": "3.0"}

    faults = _faults(document)

    assert len(faults) == 2
    url = next(f for f in faults if "no-url" in f)
    timestamp = next(f for f in faults if "no-timestamp" in f)

    assert "swaggerUrl" in url
    assert "swaggerUrl" not in timestamp
    assert "timestamp" in timestamp


def test_an_entry_that_kept_no_version_is_recorded_as_a_consequence_of_the_faults_beneath_it():
    """The fifth record, and it is deliberately not a fifth cause.

    An entry losing every version is downstream of the three version-scoped skips, so recording
    it as an independent malformation would count the same fault twice. It is recorded anyway,
    because it is the only record that says the *vendor* is gone -- an entry with three versions
    and one bad one produces a version record too, and survives. The wording is what keeps the
    two apart: it states the entry is not discoverable and names how many versions it declared,
    rather than naming a malformation of its own.
    """
    document = _document()
    document["all-bad.com"] = {
        "preferred": "1.0",
        "versions": {"1.0": {"openapiVer": "3.0"}, "2.0": "not an object"},
    }

    entries, faults = parse_directory(document)

    assert {e.api_id for e in entries} == GOOD
    assert len(faults) == 3

    consequence = [f for f in faults if "not discoverable" in f]
    assert len(consequence) == 1
    assert "all-bad.com" in consequence[0]
    assert "2 version" in consequence[0]
    # The other two are the version-scoped causes it follows from, one each.
    assert sum("'1.0'" in f for f in faults) == 1
    assert sum("'2.0'" in f for f in faults) == 1


def test_a_skipped_entry_leaves_a_trace_the_caller_can_count():
    """What the caller observes, and it is no longer nothing.

    This test asserted the opposite until this task. `parse_directory` returned a list of what
    parsed and nothing else, so a document carrying four malformed entries parsed to *exactly the
    same value* as a document that never held them -- and that was the assertion, written as an
    equality between the two parses because it was the whole of what the module told a caller
    about a skip.

    The equality still holds for the half it was ever true of, and that half is asserted first:
    this is an addition, and a malformed entry still costs nothing that parsed. What changed is
    that the second half is no longer equal. `sync.signals.intake` had the channel this lacked --
    `IntakeReport.unreadable`, on the grounds that a manifest which would not parse is not a
    repository with no dependencies -- and the same sentence holds one level up, because a
    directory entry skipped is a vendor Sync will never offer to watch.
    """
    clean = _document()
    junk = _document()
    junk["scalar.com"] = "not an object"
    junk["no-versions.com"] = {"added": "2020-01-01T00:00:00.000Z"}
    junk["all-bad.com"] = {"versions": {"1.0": {"openapiVer": "3.0"}}}
    junk["bad-detail.com"] = {"versions": {"1.0": "not an object"}}

    junk_entries, junk_faults = parse_directory(junk)
    clean_entries, clean_faults = parse_directory(clean)

    def shape(entries):
        return [
            (e.api_id, e.preferred, sorted(e.versions), [v.updated for v in e.versions.values()])
            for e in entries
        ]

    assert shape(junk_entries) == shape(clean_entries)
    assert versions_after(junk_entries, WATERMARK) == versions_after(clean_entries, WATERMARK)

    assert clean_faults == ()
    assert Counter(
        api
        for api in ("scalar.com", "no-versions.com", "all-bad.com", "bad-detail.com")
        for fault in junk_faults
        if api in fault
    ) == {"scalar.com": 1, "no-versions.com": 1, "all-bad.com": 2, "bad-detail.com": 2}
    assert len(junk_faults) == 6

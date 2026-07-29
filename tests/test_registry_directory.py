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

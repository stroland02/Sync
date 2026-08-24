"""The shipped `generated-vendors.yaml`, asserted against the code that has to serve it.

Every other test of this machinery points `SYNC_GENERATED_VENDORS` at a fixture, which tests the
loader and can never fail because of a defect in the configuration the product actually ships.
That gap has already produced one: `vercel` is configured against a Speakeasy manifest and
`sync.signals.generated` holds extraction rules for Stainless Python and Stainless TypeScript
only, so its specification can be discovered and diffed and its call sites can never be bound. It
was found by somebody reading code. This file is the gate that reports the next one.

**The real file, never the environment.** The configuration is read from
`sync.signals.registry.GENERATED_VENDORS_FILE` directly rather than through `_generated_vendors`,
which resolves `SYNC_GENERATED_VENDORS` first. Other modules in this suite monkeypatch that
variable, and a gate on the shipped configuration that a fixture elsewhere can redirect is a gate
on whatever ran last.

Each property is asserted against the mapping the code keeps rather than against a list restated
here, so the test tracks the code: manifests against `manifest._PARSERS`, languages against
`cli.language_adapters`, extraction rules against `adapter.EXTRACTORS`. A list written out here
would agree with the code on the day it was written and quietly stop meaning anything after.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from sync.cli import language_adapters
from sync.signals.generated.adapter import EXTRACTORS
from sync.signals.generated.manifest import _PARSERS, parse_manifest
from sync.signals.registry import GENERATED_VENDORS_FILE

CONFIGURATION = GENERATED_VENDORS_FILE
MANIFESTS = Path(__file__).parent / "fixtures" / "manifests"

# What the file's own header documents, and the whole of what the loader reads. Spelled out
# because the check is that a row carries exactly these: `_generated_vendors` reads `sdk_bindings`
# with `.get`, so a row misspelling it loses every binding it meant to declare and raises nothing.
DOCUMENTED_FIELDS = {"vendor_id", "repo", "manifest", "spec", "sdk_bindings"}

# Present on every row. `manifest` and `spec` are the alternation and are checked separately,
# because a row carries exactly one and equality against the documented set would demand both.
REQUIRED_FIELDS = {"vendor_id", "repo", "sdk_bindings"}

# Generator-times-language pairs a vendor is configured against and no extraction rule covers,
# accepted as of 2026-07-29.
#
# This is a list and never a count, for the reason `scripts/dead_links_baseline.txt` gives: a
# count absorbs both a repair and a new defect in silence, while a named entry has to be deleted
# by whoever writes the rule, in the commit that writes it. The test fails in both directions --
# a configured pair that is not declared here, and a declared pair that no longer describes
# anything -- so a stale exemption cannot sit here quietly exempting a later regression too.
#
# Format: (generator, language), where the generator is what the vendor's manifest convention
# yields and the language is what a binding names. An extraction rule for the pair is
# `EXTRACTORS["<generator>-<language>"]`.
# Empty, and that is the state worth defending: every generator-times-language pair some vendor
# is configured against has a rule that can read symbols out of the SDK. The set held exactly one
# entry for the few minutes between this file landing and `symbols_speakeasy.py` landing, and the
# entry was deleted by the stale-exemption test firing rather than by anyone remembering to.
PENDING_EXTRACTORS: set[tuple[str, str]] = set()


def _rows() -> list:
    """The shipped configuration, parsed and otherwise untouched."""
    return yaml.safe_load(CONFIGURATION.read_text(encoding="utf-8"))


def _generator_of(manifest: str) -> str:
    """Which generator writes this manifest, read out of a committed example of one.

    Derived rather than named here. The generator string lives inside the parser that produces
    it, and `tests/fixtures/manifests/` holds a real capture of every convention this repository
    configures, so running the parser over one is what the code itself would answer. A manifest
    convention with no committed example fails rather than resolving to a default -- the shipped
    file's header states that every entry was confirmed by fetching it, and an entry whose
    convention nobody captured is one nobody confirmed.
    """
    suffix = Path(manifest).name
    for fixture in sorted(MANIFESTS.iterdir()):
        if fixture.suffix not in (".yml", ".yaml") or not fixture.name.endswith(suffix):
            continue
        source = parse_manifest(manifest, fixture.read_text(encoding="utf-8"))
        if source is not None:
            return source.generator
    raise AssertionError(
        f"no committed manifest under {MANIFESTS} parses as '{manifest}', so which generator "
        f"writes it cannot be established"
    )


def _indexed_languages() -> set[str]:
    return {adapter.language_id for adapter in language_adapters()}


def _configured_pairs() -> set[tuple[str, str]]:
    """Every (generator, language) the shipped configuration asks to be served."""
    # A row naming its specification directly has no generator convention to name, and asking
    # which extractor serves it is a question about the SDK checkout the deployment stages --
    # not about this file. Those rows are covered by the reachability probe instead.
    return {
        (_generator_of(row["manifest"]), language)
        for row in _rows()
        if row.get("manifest")
        for language in row.get("sdk_bindings") or {}
    }


# --- a row is what the file's own header says a row is -----------------------------


def test_every_row_carries_exactly_the_fields_the_header_documents():
    """Exactly, in both directions.

    A missing field is the obvious half. The half worth the test is a field the loader has never
    heard of: `_generated_vendors` reads `sdk_bindings` with `.get`, so a row spelling it
    `sdk_binding` declares its packages to nobody, loads without complaint and matches no
    repository -- a vendor that looks configured and binds nothing, which is the shape this whole
    file exists to report.
    """
    rows = _rows()
    assert isinstance(rows, list) and rows, f"{CONFIGURATION} holds no vendors"

    for row in rows:
        assert isinstance(row, dict), f"{row!r} is not a mapping"
        unknown = set(row) - DOCUMENTED_FIELDS
        assert not unknown, (
            f"{row.get('vendor_id', row)} declares {sorted(unknown)}, which the header of "
            f"{CONFIGURATION} does not document and the loader does not read"
        )
        assert REQUIRED_FIELDS <= set(row), (
            f"{row.get('vendor_id', row)} is missing {sorted(REQUIRED_FIELDS - set(row))}"
        )
        # Exactly one, which is the rule `_generated_vendors` enforces and this file states.
        assert bool(row.get("manifest")) != bool(row.get("spec")), (
            f"{row.get('vendor_id', row)} names "
            f"{'both manifest and spec' if row.get('manifest') else 'neither manifest nor spec'}"
        )
        for field in ("vendor_id", "repo"):
            assert isinstance(row[field], str) and row[field], (
                f"{row['vendor_id']}: {field} is {row[field]!r}"
            )
        assert isinstance(row["sdk_bindings"], dict) and row["sdk_bindings"], (
            f"{row['vendor_id']}: sdk_bindings is {row['sdk_bindings']!r}, and a vendor with no "
            f"binding is one nothing in a customer's code is ever bound to"
        )


# --- a configured manifest is one something can read -------------------------------


def test_every_configured_manifest_names_a_parser_that_exists():
    """A manifest nothing parses is a vendor that can never be discovered.

    `parse_manifest` returns None for a name it has no parser for, and the registry turns that
    into a runtime failure on the first scan of that vendor -- after the vendor has registered,
    been offered on the command line and been selected. Asserted against `_PARSERS` itself so a
    parser retired tomorrow takes the vendors configured against it down with it here.
    """
    for row in _rows():
        if not row.get("manifest"):
            continue
        assert row["manifest"] in _PARSERS, (
            f"{row['vendor_id']} is configured against manifest '{row['manifest']}' and "
            f"sync.signals.generated.manifest parses {sorted(_PARSERS)}"
        )


# --- a configured language is one an indexer reads ---------------------------------


def test_every_language_a_binding_names_is_one_an_indexer_supports():
    """A binding for a language with no adapter is a binding nothing will ever read.

    Both indexers select their binding by `language_id`, so a language spelled anything else --
    `ts`, `node`, a language Sync does not index at all -- is dropped silently at the point where
    the vendor would have been matched against a repository.
    """
    supported = _indexed_languages()

    for row in _rows():
        for language in row.get("sdk_bindings") or {}:
            assert language in supported, (
                f"{row['vendor_id']} declares a '{language}' binding and the indexers registered "
                f"in sync.cli.language_adapters read {sorted(supported)}"
            )


# --- a configured pair is one symbols can be extracted for, or is declared pending --


def test_every_configured_pair_has_an_extractor_or_is_declared_pending():
    """The property that would have caught Vercel.

    A vendor is served end to end only if something can read the symbols out of the SDK its
    generator emitted, and an extraction rule covers a generator *times* a language: Stainless
    writes the route as a positional literal in Python and as a tagged template in TypeScript, so
    one generator is two rules. A configured pair with neither a rule nor an entry in
    `PENDING_EXTRACTORS` is a vendor that can be discovered and diffed and never bound -- correct,
    tested, reachable from nothing, and silent about it.
    """
    for generator, language in sorted(_configured_pairs()):
        rule = f"{generator}-{language}"
        assert rule in EXTRACTORS or (generator, language) in PENDING_EXTRACTORS, (
            f"{CONFIGURATION} configures ({generator}, {language}) and no extraction rule covers "
            f"it; sync.signals.generated.adapter.EXTRACTORS holds {sorted(EXTRACTORS)}. Write the "
            f"rule, or accept the gap by naming the pair in PENDING_EXTRACTORS"
        )


# --- the pending list is a list, and a stale entry is a failure --------------------


def test_every_pending_pair_still_describes_something_missing():
    """The direction that is easy to leave out and is half the value.

    An exemption outlives what it exempted in one of two ways: the rule gets written and the
    entry stays, or the last vendor configured against that generator goes and the entry stays.
    Either leaves a line that exempts the next vendor configured against the same pair, silently,
    which is the defect this file exists to catch wearing the costume of a decision somebody made.
    """
    configured = _configured_pairs()

    for generator, language in sorted(PENDING_EXTRACTORS):
        rule = f"{generator}-{language}"
        assert rule not in EXTRACTORS, (
            f"({generator}, {language}) is declared pending and {rule} now exists; "
            f"delete the entry in the commit that wrote the rule"
        )
        assert (generator, language) in configured, (
            f"({generator}, {language}) is declared pending and no vendor in "
            f"{CONFIGURATION} is configured against it; delete the entry"
        )


# --- and the key the two tests above compose is the key the code registers ---------


def test_every_extraction_rule_is_named_for_a_generator_and_a_language():
    """What holds the two tests above together, and the only thing here that is a convention.

    `EXTRACTORS` is keyed by one string per generator-times-language pair, and both tests above
    compose that string as `<generator>-<language>`. Nothing enforces the spelling, so a rule
    registered as `speakeasy-ts` would leave the pending entry looking accurate and the gap
    looking open forever -- an exemption that never expires, which is the one failure mode a list
    is supposed to be immune to. Asserted here so that spelling breaks loudly at the source rather
    than quietly wherever it is composed.
    """
    generators = {_generator_of(manifest) for manifest in _PARSERS}
    languages = _indexed_languages()

    for rule in sorted(EXTRACTORS):
        generator, _, language = rule.rpartition("-")
        assert generator in generators, (
            f"extraction rule '{rule}' names generator '{generator}' and the manifest parsers "
            f"yield {sorted(generators)}"
        )
        assert language in languages, (
            f"extraction rule '{rule}' names language '{language}' and the indexers read "
            f"{sorted(languages)}"
        )

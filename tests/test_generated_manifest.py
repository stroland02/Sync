"""Reading the spec location out of a generated SDK's committed manifest.

`2026-07-27-sync-adapter-targets.md` argues this is the highest coverage-per-effort item on the
roadmap: a generated SDK names the spec it came from, in a public repository, for its own
reasons and without the generator having to cooperate. One adapter then covers every vendor a
generator serves, and adapter coverage stops scaling with vendor count.

Fixtures below are the real manifests, verbatim from `anthropics/anthropic-sdk-python` and
`vercel/sdk` on 2026-07-27 -- not tidied shapes that happen to parse.
"""

from __future__ import annotations

import pytest

from sync.signals.generated import SpecSource, parse_manifest

STAINLESS_STATS = """\
configured_endpoints: 131
openapi_spec_url: https://storage.googleapis.com/stainless-sdk-openapi-specs/anthropic/anthropic-f89e311096c42998ada5ab5580a2a3b0519265f1c005af625be7a0d11ad49d3c.yml
openapi_spec_hash: d2deb0fef6a15bf53cc6c53f07973a54
config_hash: 44bd45774e5a06742c1fb8f0e20e7864
"""

# Cloudflare's manifest carries no hash. The cheap change trigger is therefore not universal,
# which the adapter has to survive rather than assume away.
STAINLESS_NO_HASH = """\
configured_endpoints: 2521
openapi_spec_url: https://storage.googleapis.com/stainless-sdk-openapi-specs/cloudflare/cloudflare-abc123.yml
config_hash: 0f0e0d0c0b0a09080706050403020100
"""

SPEAKEASY_WORKFLOW = """\
workflowVersion: 1.0.0
speakeasyVersion: latest
sources:
    vercel-OAS:
        inputs:
            - location: https://openapi.vercel.sh/
        overlays:
            - location: overlay-title.yaml
        output: vercel-spec.json
        ruleset: vercelRestAPIRuleset
        registry:
            location: registry.speakeasyapi.dev/vercel/vercel-docs/vercel-oas
targets:
    vercel:
        target: typescript
        source: vercel-OAS
"""

SPEAKEASY_LOCAL = """\
workflowVersion: 1.0.0
sources:
    local-source:
        inputs:
            - location: ./openapi.yaml
"""


# --- Stainless -------------------------------------------------------------------


def test_stainless_manifest_yields_url_hash_and_endpoint_count():
    source = parse_manifest(".stats.yml", STAINLESS_STATS)

    assert source is not None
    assert source.generator == "stainless"
    assert source.spec_url.endswith(".yml")
    assert source.spec_hash == "d2deb0fef6a15bf53cc6c53f07973a54"
    assert source.endpoint_count == 131


def test_a_stainless_url_is_flagged_as_generator_hosted():
    """The spec lives on Stainless storage, not the vendor's host.

    That is fine for learning *when* something changed and wrong as the authoritative
    artifact, so callers have to be able to tell the difference. Recording it as a field beats
    leaving every caller to re-derive it from the hostname.
    """
    source = parse_manifest(".stats.yml", STAINLESS_STATS)
    assert source.generator_hosted is True


def test_a_missing_hash_is_absent_not_invented():
    """Cloudflare ships no hash. The adapter must fall back to fetching rather than
    fabricate a trigger, so the field is None and the caller can branch on it."""
    source = parse_manifest(".stats.yml", STAINLESS_NO_HASH)

    assert source is not None
    assert source.spec_hash is None
    assert source.endpoint_count == 2521
    assert source.has_cheap_change_trigger is False


def test_a_present_hash_advertises_the_cheap_trigger():
    assert parse_manifest(".stats.yml", STAINLESS_STATS).has_cheap_change_trigger is True


def test_a_manifest_with_only_an_endpoint_count_is_reported_not_discarded():
    """Found by running the parser against live manifests: Cloudflare and Orb publish
    `configured_endpoints` and nothing else -- no URL, no hash.

    An earlier version of this module returned None for those, which threw away a real
    coverage denominator and made two genuine vendors invisible. The source is not fetchable
    and it is not nothing.
    """
    source = parse_manifest(".stats.yml", "configured_endpoints: 2521\n")

    assert source is not None
    assert source.endpoint_count == 2521
    assert source.is_fetchable is False
    assert source.spec_url is None
    assert source.has_cheap_change_trigger is False


def test_a_fetchable_manifest_says_so():
    assert parse_manifest(".stats.yml", STAINLESS_STATS).is_fetchable is True


# --- Speakeasy -------------------------------------------------------------------


def test_speakeasy_workflow_yields_the_vendor_hosted_source():
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_WORKFLOW)

    assert source is not None
    assert source.generator == "speakeasy"
    assert source.spec_url == "https://openapi.vercel.sh/"
    assert source.generator_hosted is False


def test_speakeasy_overlays_are_reported():
    """Vercel applies overlay-title.yaml, so the fetched spec is not byte-identical to what
    the SDK was generated from. A diff across two fetches is still sound -- both sides get the
    same treatment -- but anything comparing spec to SDK must know an overlay intervened."""
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_WORKFLOW)
    assert source.has_overlays is True


def test_speakeasy_has_no_hash_or_endpoint_count():
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_WORKFLOW)
    assert source.spec_hash is None
    assert source.endpoint_count is None
    assert source.has_cheap_change_trigger is False


def test_a_relative_speakeasy_location_is_not_treated_as_a_url():
    """A local path is a real Speakeasy configuration and is not fetchable. Returning it as
    `spec_url` would hand the caller something it cannot resolve."""
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_LOCAL)
    assert source is None


# --- input the real world produces -----------------------------------------------


@pytest.mark.parametrize(
    "name,text",
    [
        (".stats.yml", ""),
        (".stats.yml", "config_hash: abc\n"),  # names neither a spec nor a count
        (".speakeasy/workflow.yaml", "workflowVersion: 1.0.0\n"),  # no sources
        (".speakeasy/workflow.yaml", "sources:\n  s:\n    inputs: []\n"),
        ("README.md", STAINLESS_STATS),  # right content, unrecognised filename
    ],
)
def test_unusable_manifests_return_none(name: str, text: str):
    assert parse_manifest(name, text) is None


def test_malformed_yaml_returns_none_rather_than_raising():
    """These files come from arbitrary public repositories. One vendor committing a broken
    manifest must not take down a scan across every other vendor."""
    assert parse_manifest(".stats.yml", "key: [unclosed\n  nested: :::") is None


def test_a_yaml_document_that_is_not_a_mapping_returns_none():
    assert parse_manifest(".stats.yml", "- just\n- a\n- list\n") is None


# --- change detection, which is the point ----------------------------------------


def test_two_manifests_differing_only_in_hash_compare_unequal():
    """The whole economic argument: detecting drift costs a string comparison against a file
    in a public repo -- no spec download, no oasdiff run, until something actually moved."""
    before = parse_manifest(".stats.yml", STAINLESS_STATS)
    after = parse_manifest(".stats.yml", STAINLESS_STATS.replace("d2deb0fe", "ffffffff"))

    assert before.spec_hash != after.spec_hash
    assert before.changed_from(after) is True


def test_an_identical_manifest_reports_no_change():
    a = parse_manifest(".stats.yml", STAINLESS_STATS)
    b = parse_manifest(".stats.yml", STAINLESS_STATS)
    assert a == b
    assert a.changed_from(b) is False


def test_without_a_hash_change_cannot_be_ruled_out():
    """Absent a trigger the honest answer is "unknown", and unknown must read as changed.

    Reporting "no change" from missing evidence would silently skip a vendor forever -- the
    expensive failure, because it is invisible.
    """
    a = parse_manifest(".stats.yml", STAINLESS_NO_HASH)
    b = parse_manifest(".stats.yml", STAINLESS_NO_HASH)
    assert a == b
    assert a.changed_from(b) is True


def test_sources_from_different_generators_are_never_equal():
    stainless = parse_manifest(".stats.yml", STAINLESS_STATS)
    speakeasy = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_WORKFLOW)
    assert stainless != speakeasy
    assert isinstance(stainless, SpecSource) and isinstance(speakeasy, SpecSource)


# Mistral's real manifest, reduced to one source. Every `location` is a Speakeasy *registry
# reference* rather than a URL -- verified live on 2026-08-23 at
# `mistralai/client-python/.speakeasy/workflow.yaml`, which returns 200 unauthenticated.
SPEAKEASY_REGISTRY_ONLY = """workflowVersion: 1.0.0
speakeasyVersion: 1.763.6
sources:
    mistral-openapi:
        inputs:
        -   location: registry.speakeasyapi.dev/mistral-dev/mistral-dev/mistral-openapi:v2
"""

MISTRAL_REFERENCE = "registry.speakeasyapi.dev/mistral-dev/mistral-dev/mistral-openapi:v2"


def test_a_registry_reference_is_recorded_rather_than_discarded():
    """A manifest naming a location we cannot resolve is not a manifest naming none.

    Returning None here put Mistral in Cloudflare's bucket, and the two are opposites: Cloudflare
    publishes no specification, while Mistral publishes three and gates them behind its own
    credential. `schema.sql` argues the rule -- absent and believed present is worse than absent.
    """
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_REGISTRY_ONLY)

    assert source is not None
    assert source.spec_reference == MISTRAL_REFERENCE
    assert source.spec_url is None
    # The reference is recorded, never resolved. Prefixing a scheme returns 200 and a 4,848-byte
    # HTML page, which `_spec` would cache as a specification and oasdiff would diff against its
    # identical twin and report clean.
    assert source.is_fetchable is False


def test_a_manifest_naming_a_real_url_records_no_reference():
    # The other side of the pair: a resolvable location must not be filed as unreachable.
    source = parse_manifest(".speakeasy/workflow.yaml", SPEAKEASY_WORKFLOW)

    assert source.spec_url == "https://openapi.vercel.sh/"
    assert source.spec_reference is None
    assert source.is_fetchable is True


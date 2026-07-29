"""Why the generated-SDK path drops nothing, and what would go missing if it did.

`2026-07-29-oasdiff-determinism.md` §4 measured 792,552 oasdiff records, found 93% of them were
`response-property-enum-value-added`, and observed that `sync.signals.generated.adapter` applies no
noise filter while both hand-written adapters drop that kind. The obvious repair is to copy
`sync.signals.stripe.adapter.NOISE_KINDS` across.

`2026-07-29-generated-vendor-noise.md` measured why that repair is wrong, and these tests are what
stops it being made by inspection. Over the four configured vendors' own specification pairs the
same rule id is the *sole route* to the affected operations rather than volume sitting on top of
them -- for `openai`'s 2026-07-23 to 2026-07-28 window it is every record and every operation, so a
vendor that filtered it would report that release as no change at all. That is the silent-vendor
failure the adapter's own `_spec` docstring refuses to allow from a fetch outage, arriving instead
from a filter.

So the generated path drops nothing, deliberately. These tests fail the moment somebody adds a
filter of any shape, and the two committed record sets are the evidence the decision rests on.
Nothing here reaches the network: the specification fetch is injected, and the vendor records were
captured by `scripts/measure_generated_vendor_noise.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated import STAINLESS_MANIFEST, parse_manifest
from sync.signals.generated.adapter import GeneratedSpecAdapter

RECORDS = Path(__file__).parent / "fixtures" / "generated_noise"

BINARY = Path(__file__).parents[1] / "tools" / "oasdiff.exe"
BINARY_POSIX = Path(__file__).parents[1] / "tools" / "oasdiff"

needs_binary = pytest.mark.skipif(
    not (BINARY.exists() or BINARY_POSIX.exists()),
    reason="needs tools/oasdiff; run scripts/bootstrap_tools.sh",
)

STRIPE_NOISE_KIND = "response-property-enum-value-added"
"""The single member of both hand-written adapters' `NOISE_KINDS`, named rather than imported.
Importing one vendor's judgement to assert that it does not apply to another would make the
comparison circular, and the duplication those two adapters carry is deliberate."""

# Every rule id observed across 72 oasdiff runs over the three fetchable vendors' pairs. The list
# is the measurement's output, so a filter of any kind-list shape turns at least one case red.
OBSERVED_KINDS = (
    "request-body-became-required",
    "request-body-one-of-removed",
    "request-parameter-list-of-types-narrowed",
    "request-parameter-removed",
    "request-property-all-of-added",
    "request-property-all-of-removed",
    "request-property-any-of-removed",
    "request-property-became-required",
    "request-property-list-of-types-narrowed",
    "response-body-one-of-added",
    "response-body-wrapped-in-one-of",
    "response-optional-property-removed",
    "response-property-became-optional",
    "response-property-const-removed",
    "response-property-enum-value-added",
    "response-property-list-of-types-widened",
    "response-property-max-length-unset",
    "response-property-one-of-added",
    "response-property-type-changed",
    "response-required-property-removed",
)

MIRROR_BASE = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/base.yml"
MIRROR_HEAD = "https://storage.googleapis.com/stainless-sdk-openapi-specs/acme/head.yml"


def _enum_spec(values: list[str]) -> str:
    """One operation whose response carries one enum, which is the smallest input that provokes
    `response-property-enum-value-added` out of the real differ."""
    return json.dumps(
        {
            "openapi": "3.0.3",
            "info": {"title": "acme", "version": "1"},
            "paths": {
                "/v1/thing": {
                    "get": {
                        "operationId": "getThing",
                        "responses": {
                            "200": {
                                "description": "ok",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "status": {"type": "string", "enum": values}
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
        }
    )


def _sources(spec_hash_from: str = "h-old", spec_hash_to: str = "h-new"):
    """Two manifests whose hash moved, built by the real parser so these ride the chain a run does."""
    def source(url: str, spec_hash: str):
        parsed = parse_manifest(
            STAINLESS_MANIFEST,
            f"configured_endpoints: 1\nopenapi_spec_url: {url}\nopenapi_spec_hash: {spec_hash}\n",
        )
        assert parsed is not None
        return parsed

    return {"v1": source(MIRROR_BASE, spec_hash_from), "v2": source(MIRROR_HEAD, spec_hash_to)}


def _adapter(tmp_path, bodies: dict[str, str] | None = None) -> GeneratedSpecAdapter:
    served = bodies or {MIRROR_BASE: _enum_spec(["open"]), MIRROR_HEAD: _enum_spec(["open", "shut"])}
    return GeneratedSpecAdapter(
        vendor_id="acme",
        sources=_sources(),
        fetch=served.__getitem__,
        cache_dir=tmp_path / "specs",
    )


def _record(rule_id: str, operation_id: str = "getThing", path: str = "/v1/thing") -> dict:
    return {
        "id": rule_id,
        "text": f"a {rule_id} record",
        "level": 2,
        "operation": "GET",
        "operationId": operation_id,
        "path": path,
    }


def _operations(records: list[dict]) -> set[tuple[str, str]]:
    return {
        (r.get("path", ""), r.get("operationId") or f"{r.get('operation', '')} {r.get('path', '')}")
        for r in records
    }


# --- the pin: nothing is dropped, whatever shape a filter would take ----------------------


@needs_binary
def test_the_kind_stripe_drops_survives_this_path_end_to_end(tmp_path):
    """The core assertion, through the real differ rather than a stub of it.

    A filter added anywhere between `run_oasdiff_breaking` and the returned rows fails here, and
    the input is the smallest specification pair that provokes the kind in question.
    """
    changes = list(_adapter(tmp_path).fetch_changes("v1", "v2"))

    assert [change.kind for change in changes] == [STRIPE_NOISE_KIND]


@needs_binary
def test_no_record_the_differ_reported_is_missing_from_the_rows(tmp_path, monkeypatch):
    """Shape-independent, which the kind-by-kind cases are not.

    A filter keyed on `level`, on the message text, or on anything else oasdiff reports would leave
    every named-kind assertion above green and still lose rows. This compares what the differ
    returned against what came back, so it only cares that the count and the kinds survived.
    """
    from sync.signals.generated import adapter as module

    reported: list[dict] = []
    real = module.run_oasdiff_breaking

    def spy(base, revision):
        records = real(base, revision)
        reported.extend(records)
        return records

    monkeypatch.setattr(module, "run_oasdiff_breaking", spy)
    changes = list(_adapter(tmp_path).fetch_changes("v1", "v2"))

    assert reported, "the fixture pair produced no records, so this test could not fail"
    assert len(changes) == len(reported)
    assert sorted(c.kind for c in changes) == sorted(r["id"] for r in reported)


@pytest.mark.parametrize("kind", OBSERVED_KINDS)
def test_every_kind_the_fetchable_vendors_produce_reaches_a_row(tmp_path, monkeypatch, kind):
    """Each rule id the measurement saw, one case each, so a partial filter names itself.

    The differ is stubbed here rather than provoked: constructing twenty specification pairs to
    make oasdiff emit twenty particular rule ids would test oasdiff, and what is in question is
    what this adapter does with a record once it has one.
    """
    from sync.signals.generated import adapter as module

    monkeypatch.setattr(module, "run_oasdiff_breaking", lambda base, revision: [_record(kind)])
    changes = list(_adapter(tmp_path).fetch_changes("v1", "v2"))

    assert [change.kind for change in changes] == [kind]


# --- the evidence the decision rests on ---------------------------------------------------


def test_the_enum_kind_is_the_only_route_to_every_operation_openai_changed():
    """Stripe's argument for the filter, inverted on real records from a different vendor.

    §4 of the determinism report found Stripe's volume and Stripe's coverage in different kinds:
    dropping this one removed 93% of records and none of the varying operations. Over OpenAI's
    2026-07-23 to 2026-07-28 window it is all of both, so the filter that costs Stripe nothing
    costs this vendor the entire release.
    """
    records = json.loads((RECORDS / "openai-2026-07-23-to-2026-07-28.json").read_text(encoding="utf-8"))
    kept = [r for r in records if r["id"] != STRIPE_NOISE_KIND]

    assert _operations(records), "the fixture holds no operations, so this test could not fail"
    assert _operations(kept) == set()
    assert len(_operations(records) - _operations(kept)) == len(_operations(records))


def test_the_enum_kind_is_a_minority_of_what_anthropic_produces():
    """The other end of the spread, and why one vendor's constant is not a fact about the corpus.

    93% of Stripe's records and 92% of Twilio's are this kind. 21% of Anthropic's 2026-06-30 to
    2026-07-28 window are, and the kind that dominates there is a level-3 request-side change no
    filter proposed for Stripe would have touched.
    """
    records = json.loads((RECORDS / "anthropic-2026-06-30-to-2026-07-28.json").read_text(encoding="utf-8"))
    enum_records = [r for r in records if r["id"] == STRIPE_NOISE_KIND]

    assert enum_records, "the fixture holds none of the kind under test, so this test could not fail"
    assert len(enum_records) / len(records) < 0.25
    assert max({r["id"] for r in records}, key=lambda k: sum(r["id"] == k for r in records)) == (
        "request-property-any-of-removed"
    )

"""What the two specification-reading symbol rules emit today, recorded before they move.

`docs/superpowers/plans/2026-08-23-uniform-vendor-tier-and-console-completion.md` Track A moves
the two hand-written symbol builders into the extraction-rule registry so that no vendor is
served by hand-written code. A move is only safe if it changes nothing, and
"changes nothing" is a claim somebody has to be able to check -- these digests are that check.

They are deliberately not the same artifact as `benchmark/corpus/symbol_map.yaml`. That pin
governs the *committed cache* `vendor-cache/stripe/symbols.json`, which was baked before these
builders gained `service_id` and carries four keys per entry where the builder now emits five --
so the cache must not be rebaked inside this sequence, and holding the builder to the cache would
demand exactly that. This file pins the builders; that file pins the artifact. Both have to hold,
and they hold different things.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.symbol_map_pin import symbol_map_digest
from sync.signals.generated.symbols_stripe_openapi import build_symbol_map as build_stripe_map
from sync.signals.twilio.symbols import build_symbol_map as build_twilio_map

FIXTURES = Path(__file__).parent / "fixtures"

STRIPE_SPEC = json.loads(
    (FIXTURES / "specs" / "stripe_v2330_shape.json").read_text(encoding="utf-8")
)
STRIPE_SDK_SPEC = json.loads(
    (FIXTURES / "specs" / "stripe_v2330_sdk_shape.json").read_text(encoding="utf-8")
)
TWILIO_SPEC = json.loads(
    (FIXTURES / "twilio" / "insights_v1_shape.json").read_text(encoding="utf-8")
)

# Measured by execution on 2026-08-23, not copied from a document.
STRIPE_WITHOUT_SDK = "cf8641cca4e454d6023556f066c18db0a1893d8b249b4c89143985426bfa5527"
STRIPE_WITH_SDK = "808500e370b7180645c5bd087deb20c4a391261d7c807b8b51d7d756feda5fcb"
TWILIO_INSIGHTS_V1 = "3aa3ba31c7fc7abfb0ed68fc35799f205c88ed34701590079c6ac4a690bf6267"


def test_the_stripe_rule_emits_what_it_emitted_before_the_move():
    mapping = build_stripe_map(STRIPE_SPEC)

    assert len(mapping) == 272
    assert symbol_map_digest(mapping) == STRIPE_WITHOUT_SDK


def test_the_stripe_rule_reads_the_sdk_document_and_answers_differently():
    """The two digests must differ, or this file would pass against a rule that ignored the
    SDK document entirely -- which is the one input whose loss would be silent."""
    with_sdk = build_stripe_map(STRIPE_SPEC, STRIPE_SDK_SPEC)

    assert len(with_sdk) == 272
    assert symbol_map_digest(with_sdk) == STRIPE_WITH_SDK
    assert STRIPE_WITH_SDK != STRIPE_WITHOUT_SDK


def test_the_twilio_rule_emits_what_it_emitted_before_the_move():
    mapping = build_twilio_map(TWILIO_SPEC, domain="insights", version="v1")

    assert len(mapping) == 17
    assert symbol_map_digest(mapping) == TWILIO_INSIGHTS_V1


@pytest.mark.parametrize(
    "mapping, expected",
    [
        (
            build_stripe_map(STRIPE_SPEC),
            {"http_method", "languages", "operation_id", "path", "service_id"},
        ),
        (
            build_twilio_map(TWILIO_SPEC, domain="insights", version="v1"),
            {"http_method", "operation_id", "path", "service_id"},
        ),
    ],
    ids=["stripe", "twilio"],
)
def test_each_rule_states_the_same_fields_for_every_symbol_it_emits(mapping, expected):
    """A digest changes when a value changes and equally when a field appears, so on its own it
    cannot say which happened. The field set is pinned separately because the move's most likely
    accident is a field quietly going missing for a subset of symbols -- the digests above would
    report that, and would not say what to look at.

    The two rules differ here, which is the point: Stripe derives per-language spellings and
    Twilio does not, so `languages` is present for one and absent for the other.
    """
    assert mapping, "an empty mapping would satisfy every assertion below vacuously"
    for symbol, entry in mapping.items():
        assert set(entry) == expected, symbol


def test_the_two_rules_agree_on_the_shape_of_what_they_share():
    """Whatever else differs, both emit the three fields the graph joins on."""
    shared = {"operation_id", "http_method", "path"}
    stripe = build_stripe_map(STRIPE_SPEC)
    twilio = build_twilio_map(TWILIO_SPEC, domain="insights", version="v1")

    for mapping in (stripe, twilio):
        for entry in mapping.values():
            assert shared <= set(entry)
            assert all(isinstance(entry[field], str) for field in shared)

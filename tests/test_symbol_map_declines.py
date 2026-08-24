"""Every input the two hand-written symbol maps refuse to resolve, and what the caller sees.

`sync.signals.generated.symbols_twilio_oai` and `sync.signals.generated.symbols_stripe_openapi` are the two maps written by
rule rather than read out of a generator, and between them they held eleven unexecuted
statements. Every one is a decline: an input that produces no symbol.

A map that declines too readily produces the worst-shaped false negative this system has. The
vendor change is real, the call site exists, and the two are never joined, so the pipeline
reports a clean scan. So each decline is asserted here against the *resulting symbol map* --
which symbols resolved and which did not -- rather than against an internal call, because a
decline that is right and a decline that is a bug look identical from the inside.

One file for two vendors, against the grain of `CLAUDE.md`'s rule that vendor knowledge lives in
adapters, and deliberately: three of the assertions below are *comparisons* between the two maps,
and they are the ones that found something. Neither vendor's own test file is the place for an
assertion about the other. Nothing here imports one vendor's derivation into the other's; it
imports both and states where they disagree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.signals.generated.symbols_stripe_openapi import build_symbol_map as build_stripe_map
from sync.signals.generated.symbols_twilio_oai import build_symbol_map as build_twilio_map

TWILIO_FIXTURES = Path(__file__).parent / "fixtures" / "twilio"


def _twilio(paths: dict) -> dict[str, dict[str, str]]:
    return build_twilio_map({"paths": paths}, domain="insights", version="v1")


def _stripe(paths: dict, sdk: dict | None = None) -> dict[str, dict[str, str]]:
    return build_stripe_map({"paths": paths}, sdk)


# --- twilio: the two `return None` in `_chain` -------------------------------------------


def test_a_parent_the_document_does_not_name_drops_the_child_rather_than_promoting_it():
    """`_chain`'s first refusal, and the one with a real caller.

    `x-twilio.parent` is spelled without the version prefix, so resolving it means putting the
    prefix back and looking the result up. A parent the document does not contain has to yield
    no symbol at all. The alternative -- keep the chain that resolved and mount the child at the
    top level -- is worse than a missing symbol: `twilio.insights.v1.events.list` is a name no
    customer can have written, it collides with nothing, and so nothing ever reports that the
    real `calls.events.list` went missing.

    This is not hypothetical for us. `scripts/build_twilio_fixtures.py` trims a document to one
    resource family, and a kept child whose parent falls outside the kept set arrives here.
    """
    mapping = _twilio(
        {
            "/v1/Voice/{CallSid}/Events": {
                "x-twilio": {"parent": "/Voice/{Sid}"},
                "get": {"operationId": "ListEvent"},
            }
        }
    )

    assert mapping == {}
    assert "twilio.insights.v1.events.list" not in mapping


def test_a_parent_cycle_yields_no_symbol_instead_of_recursing_until_the_interpreter_stops():
    """`seen` is the other half of the same statement, and it guards a crash rather than a name.

    No published document contains a cycle. Without the guard one is not a wrong symbol, it is a
    `RecursionError` from inside a map build -- which is why the guard is right even though the
    input is unpublished: the failure it prevents is undiagnosable, not merely wrong.

    Both shapes a cycle takes are here. A path naming itself as its own parent is the one-step
    case and the two-path ring is the general one; only the second needs `seen` to accumulate
    across frames.
    """
    self_parent = _twilio(
        {
            "/v1/Voice/{Sid}": {
                "x-twilio": {"parent": "/Voice/{Sid}"},
                "get": {"operationId": "FetchCall"},
            }
        }
    )
    ring = _twilio(
        {
            "/v1/Rooms": {"x-twilio": {"parent": "/Participants"}, "get": {"operationId": "ListRoom"}},
            "/v1/Participants": {
                "x-twilio": {"parent": "/Rooms"},
                "get": {"operationId": "ListParticipant"},
            },
        }
    )

    assert self_parent == {}
    assert ring == {}


def test_a_path_built_only_of_placeholders_yields_no_symbol_rather_than_an_empty_mount():
    """`_mount`'s `None`, and the reason it is `None` rather than `""`.

    `/v1/{Sid}` states no `mountName` and has no literal segment after the version to fall back
    on. An empty string here would mount the operation under the empty name --
    `twilio.insights.v1..fetch` -- which is a key the library cannot produce and a call site
    cannot spell, so it would sit in the map forever resolving nothing.

    No path in the five sampled product documents has this shape. It is asserted anyway because
    the cost of the wrong answer is a permanently unreachable operation and the cost of this one
    is a missing symbol that a coverage set would name.
    """
    mapping = _twilio({"/v1/{Sid}": {"get": {"operationId": "FetchThing"}}})

    assert mapping == {}
    assert "twilio.insights.v1..fetch" not in mapping


# --- twilio: the four `continue` in `build_symbol_map` -----------------------------------


def test_a_path_whose_body_is_not_an_object_leaves_its_siblings_resolving():
    """The skip is scoped to the one path, which is the whole content of the assertion.

    A malformed path item is a vendor-response shape, and the guard is at a boundary rather than
    inside trusted code. What matters is that it is a `continue` and not a `return`: the reading
    that abandoned the document would answer with a smaller map for one bad key.

    In the forward direction this statement is redundant -- `_chain` re-reads `paths[path]` and
    refuses a non-object itself, so removing the guard changes no answer. It is pinned in the
    direction that is load-bearing: the good path still resolves.
    """
    mapping = _twilio({"/v1/Rooms": {"get": {"operationId": "ListRoom"}}, "/v1/Broken": []})

    assert set(mapping) == {"twilio.insights.v1.rooms.list"}


def test_an_unresolvable_chain_costs_its_own_path_and_no_other():
    """`chain is None` is where the two `_chain` refusals become observable.

    Pinned on a document holding one resolvable path beside one unresolvable one, because a
    single-path fixture cannot tell "the chain was refused" from "the loop stopped".
    """
    mapping = _twilio(
        {
            "/v1/Conferences": {"get": {"operationId": "ListConference"}},
            "/v1/Voice/{CallSid}/Events": {
                "x-twilio": {"parent": "/Voice/{Sid}"},
                "get": {"operationId": "ListEvent"},
            },
        }
    )

    # `twilio-python`'s spelling. `CI-W588` records `twilio-node`'s beside it, and
    # `test_rule_twilio_oai.py` holds that each is the other's camel-cased twin.
    assert {s for s, e in mapping.items() if "python" in e["languages"]} == {
        "twilio.insights.v1.conferences.list"
    }


def test_the_real_vendor_document_carries_path_item_keys_that_are_not_operations():
    """Real vendor bytes, and the statement they cover is one the reduced fixture cannot reach.

    `servers` and `description` are legal Path Item fields and Twilio writes both on every path
    of this product. `scripts/build_twilio_fixtures.py:shape_only` keeps `x-twilio` and any
    object carrying an `operationId` and drops everything else, so the shape fixture the rest of
    the suite is built on holds neither -- which is the only reason this statement was never
    executed. It is not a defensive guard against an input nobody sends; it is the guard that
    makes the rest of the suite's fixture reduction safe.

    Asserted through the committed 2.3.0 document rather than a constructed one, so the input is
    the vendor's own and the four symbols are the four the trimmed document should still produce.
    """
    document = json.loads((TWILIO_FIXTURES / "2.3.0" / "insights_v1.json").read_text(encoding="utf-8"))
    path_item = document["paths"]["/v1/Conferences"]

    assert isinstance(path_item["servers"], list)
    assert isinstance(path_item["description"], str)

    mapping = build_twilio_map(document, domain="insights", version="v1")

    # `twilio-python`'s four. `CI-W588` records `twilio-node`'s spelling beside each, and
    # `test_rule_twilio_oai.py` holds that every camel-cased key is one of these camel-cased.
    assert {s for s, e in mapping.items() if "python" in e["languages"]} == {
        "twilio.insights.v1.conferences.list",
        "twilio.insights.v1.conferences.fetch",
        "twilio.insights.v1.conferences.conference_participants.list",
        "twilio.insights.v1.conferences.conference_participants.fetch",
    }


def test_an_operation_id_naming_no_known_verb_yields_no_symbol_rather_than_a_new_method():
    """The one Twilio decline with no second source behind it.

    Twilio states the verb in `operationId` and nothing else in the document states it, so an
    unrecognised leading word leaves nothing to fall back on. Accepting the word as its own
    method name is the tempting alternative and it is how a call site binds to an operation
    nobody called: `PurchaseThing` would mint `things.purchase`, and `twilio-python` exposes no
    such attribute.

    Both ways the read fails are here. `PurchaseThing` matches the leading-word pattern and is
    absent from the table; `fetchThing` does not match the pattern at all, because the pattern
    requires the PascalCase the vendor's generator writes. Declining the second is the same
    judgement as the first -- a case-insensitive read would be a rule about Twilio's punctuation
    that nobody checked against the library.
    """
    mapping = _twilio(
        {
            "/v1/Things": {
                "get": {"operationId": "FetchThing"},
                "post": {"operationId": "PurchaseThing"},
                "delete": {"operationId": "fetchThing"},
            }
        }
    )

    assert set(mapping) == {"twilio.insights.v1.things.fetch"}
    assert mapping["twilio.insights.v1.things.fetch"]["http_method"] == "get"


# --- stripe: `case _` and the three `continue` -------------------------------------------


def test_an_http_method_stripe_does_not_use_reaches_the_catch_all_and_yields_nothing():
    """What arrives at `_method_name`'s `case _`, and what it costs.

    Four kinds of input reach it, and only the first two are about HTTP at all: a verb Stripe
    does not use on a v1 resource (`PUT`, `PATCH`), a `DELETE` on a path this map reads as a
    collection, and any object-valued key of a path item that is not a method -- an `x-`
    extension being the realistic one, since Twilio's document proves a vendor writes those.

    Every one of them produces a smaller map and nothing else. Naming the method after the verb
    is the plausible wrong answer -- `stripe.charges.put` -- and it is exactly the invented
    method name `_SDK_VERBS`' own comment refuses.
    """
    mapping = _stripe(
        {
            "/v1/charges": {
                "get": {"operationId": "GetCharges"},
                "put": {"operationId": "PutCharges"},
                "patch": {"operationId": "PatchCharges"},
                "delete": {"operationId": "DeleteCharges"},
                "x-stripe": {"note": "an object-valued extension, not an operation"},
            }
        }
    )

    assert set(mapping) == {"stripe.charges.list"}


def test_a_stable_id_naming_no_verb_on_a_shape_the_http_rule_refuses_yields_nothing():
    """Both verb sources declining at once, which is the only way to reach the `continue`.

    The stable id is consulted first and the HTTP rule is the fallback, so a symbol is lost only
    when neither speaks. `search_charges` names a token the table does not carry and `PUT` is a
    pair `_method_name` does not handle, so this is the shape a future Stripe release would
    arrive in: a new operation whose `x-stableId` names a verb we have not checked against the
    SDK, on a method the map has never seen.
    """
    mapping = _stripe(
        {"/v1/charges": {"get": {"operationId": "GetCharges"}, "put": {"operationId": "PutCharges"}}},
        {"paths": {"/v1/charges": {"put": {"x-stableId": "search_charges"}}}},
    )

    assert set(mapping) == {"stripe.charges.list"}


def test_a_path_item_key_whose_value_is_not_an_object_is_skipped():
    """Two inputs, and only the second makes this statement load-bearing.

    `parameters`, `servers`, `description` and `summary` are legal Path Item fields carrying
    non-objects, and they are what a real document sends -- but `case _` already refuses all
    four one line later, so the guard changes no answer for them. The input that only this guard
    can answer is a *method* key holding something that is not an operation object, where the
    verb resolves and `operation.get` then has nothing to read.

    That second shape is malformed rather than merely unhandled, so it is stated plainly: this
    statement exists for a document no vendor publishes, and its sibling `post` resolving is
    what says the skip is scoped to the one key.
    """
    legal_fields = _stripe(
        {
            "/v1/charges": {
                "get": {"operationId": "GetCharges"},
                "parameters": [{"name": "expand", "in": "query"}],
                "servers": [{"url": "https://api.stripe.com/"}],
                "description": "prose",
                "summary": "prose",
            }
        }
    )
    method_key_holding_a_string = _stripe(
        {"/v1/charges": {"get": "prose", "post": {"operationId": "PostCharges"}}}
    )

    assert set(legal_fields) == {"stripe.charges.list"}
    assert set(method_key_holding_a_string) == {"stripe.charges.create"}


def test_a_stripe_path_whose_body_is_not_an_object_leaves_its_siblings_resolving():
    """The path-item level, which is a layer above the method-key guard just asserted.

    Stripe reached `.get` on whatever `paths` held, through `_addresses_one_resource`, before any
    method key was looked at -- so a single malformed path item cost the *entire* map with an
    `AttributeError` naming a builtin type. That is a far larger answer than the input deserves:
    every call site for the vendor goes unresolved, which this file's own preamble calls the
    worst-shaped false negative the system has, arriving by traceback instead of by silence.

    Twilio guarded the same layer from the start. This is the assertion that says both do now,
    and it is pinned in the load-bearing direction: the good path still resolves.
    """
    mapping = _stripe({"/v1/charges": {"get": {"operationId": "GetCharges"}}, "/v1/broken": []})

    assert set(mapping) == {"stripe.charges.list"}


def test_an_operation_with_no_operation_id_yields_no_symbol_however_the_verb_was_read():
    """A symbol with no operation behind it is unresolvable in the other direction.

    `operation_id` is what the graph joins a vendor change against, so an entry carrying `None`
    there is a call site bound to nothing -- and it occupies the key the real operation would
    have taken if the document were fixed.

    Asserted twice because the verb has two sources and this check sits after both. The second
    path reaches it with the method name supplied by Stripe's own generator input, which is the
    reading that has no `operationId` of its own to fall back on.
    """
    from_the_http_rule = _stripe(
        {"/v1/charges": {"get": {}, "post": {"operationId": "PostCharges"}}}
    )
    from_the_stable_id = _stripe(
        {"/v1/coupons/{coupon}": {"delete": {}, "get": {"operationId": "GetCoupon"}}},
        {"paths": {"/v1/coupons/{coupon}": {"delete": {"x-stableId": "delete_coupon"}}}},
    )

    assert set(from_the_http_rule) == {"stripe.charges.create"}
    assert set(from_the_stable_id) == {"stripe.coupons.retrieve"}


# --- what the caller sees of a decline, and where the two maps disagree ------------------


def test_a_declined_operation_leaves_no_trace_either_map_s_caller_could_count():
    """The finding this file exists to make countable, asserted rather than described.

    A document holding declined operations builds a map byte-identical to a document that never
    held them. Neither builder returns a count, a list or a second channel, so a decline and a
    vendor who published nothing are the same observation at every later stage -- which is the
    false negative the whole product exists to catch, arriving from our own side.

    Equality between the two builds is the assertion, not a count of what was dropped. A count
    is what does not exist.
    """
    twilio_with = _twilio(
        {
            "/v1/Conferences": {"get": {"operationId": "ListConference"}},
            "/v1/Things": {"post": {"operationId": "PurchaseThing"}},
            "/v1/{Sid}": {"get": {"operationId": "FetchThing"}},
        }
    )
    twilio_without = _twilio({"/v1/Conferences": {"get": {"operationId": "ListConference"}}})

    stripe_with = _stripe(
        {
            "/v1/charges": {"get": {"operationId": "GetCharges"}, "put": {"operationId": "PutCharges"}},
            "/v1/coupons/{coupon}": {"delete": {}},
        }
    )
    stripe_without = _stripe({"/v1/charges": {"get": {"operationId": "GetCharges"}}})

    assert twilio_with == twilio_without
    assert stripe_with == stripe_without


def test_the_two_maps_answer_a_malformed_path_item_the_same_way():
    """The drift this file recorded, closed, and pinned in the direction it was closed.

    Both builders iterate `spec["paths"]`. Twilio guarded the path body from the start; Stripe
    did not, and `_addresses_one_resource` reached `.get` on it, so the same malformed input at
    the same layer produced a skipped path from one vendor and an `AttributeError` naming a
    builtin type from the other. The earlier version of this test asserted that disagreement and
    said which answer was worse: the raise, because it costs the whole map for one bad key and
    names neither the vendor nor the path.

    Asserted as a comparison rather than twice in each vendor's own file, because agreement is
    the property -- the two can only drift apart again by one of these halves changing alone.
    """
    stripe = _stripe({"/v1/charges": {"get": {"operationId": "GetCharges"}}, "/v1/broken": []})
    twilio = _twilio({"/v1/Charges": {"get": {"operationId": "ListCharge"}}, "/v1/Broken": []})

    assert set(stripe) == {"stripe.charges.list"}
    assert set(twilio) == {"twilio.insights.v1.charges.list"}


def test_only_twilio_declines_an_unrecognised_verb_and_only_stripe_has_a_fallback():
    """The largest difference between the two maps, and a vendor fact rather than drift.

    Twilio writes the verb into `operationId` and the document states it nowhere else, so an
    unrecognised leading word ends the derivation. Stripe has two independent sources -- the
    generator input's `x-stableId` and the HTTP method with the path shape -- so an unrecognised
    token there falls back to a reading that is already the answer for every operation the
    generator input does not cover.

    Asserted on the same logical input to both, so the asymmetry is a measurement: an
    unrecognised verb token costs Twilio the symbol and costs Stripe nothing.
    """
    twilio = _twilio({"/v1/Things": {"get": {"operationId": "PurchaseThing"}}})
    stripe = _stripe(
        {"/v1/charges": {"get": {"operationId": "GetCharges"}}},
        {"paths": {"/v1/charges": {"get": {"x-stableId": "search_charges"}}}},
    )

    assert twilio == {}
    assert set(stripe) == {"stripe.charges.list"}

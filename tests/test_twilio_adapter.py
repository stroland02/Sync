"""Twilio as the second vendor, chosen because it is not shaped like Stripe.

Every expected symbol below is ground truth read out of the generated `twilio-python`
library, not out of our own derivation. That distinction is the whole value of this file:
a symbol map tested against itself proves only that it is self-consistent, where these
assertions fail if the derivation stops naming the method a customer actually imports.

The mounts and methods were read from `twilio/rest/insights/v1/__init__.py` (calls,
call_summaries, conferences, rooms, settings) and from the `call`, `conference` and `room`
modules beneath it (annotation, events, metrics, summary, conference_participants,
participants, fetch, list).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core import VendorAdapter
from sync.signals.stripe.symbols import build_symbol_map as build_stripe_symbol_map
from sync.signals.twilio.adapter import ProductDocument, TwilioAdapter
from sync.signals.twilio.symbols import SymbolCollision, build_symbol_map

FIXTURES = Path(__file__).parent / "fixtures" / "twilio"
SHAPE_FIXTURE = FIXTURES / "insights_v1_shape.json"

INSIGHTS_V1 = ProductDocument(filename="insights_v1.json", domain="insights", version="v1")


def _shape_spec() -> dict:
    return json.loads(SHAPE_FIXTURE.read_text(encoding="utf-8"))


# What `twilio-python` actually exposes for this product, symbol by symbol. Seventeen
# operations across fifteen paths; the two paths carrying no operations are absent by
# construction rather than by omission, and `test_a_path_with_no_operations_yields_nothing`
# is what holds that true.
SDK_GROUND_TRUTH = {
    "twilio.insights.v1.settings.fetch": ("FetchAccountSettings", "get", "/v1/Voice/Settings"),
    "twilio.insights.v1.settings.update": ("UpdateAccountSettings", "post", "/v1/Voice/Settings"),
    "twilio.insights.v1.calls.fetch": ("FetchCall", "get", "/v1/Voice/{Sid}"),
    "twilio.insights.v1.calls.annotation.fetch": ("FetchAnnotation", "get", "/v1/Voice/{CallSid}/Annotation"),
    "twilio.insights.v1.calls.annotation.update": ("UpdateAnnotation", "post", "/v1/Voice/{CallSid}/Annotation"),
    "twilio.insights.v1.calls.events.list": ("ListEvent", "get", "/v1/Voice/{CallSid}/Events"),
    "twilio.insights.v1.calls.metrics.list": ("ListMetric", "get", "/v1/Voice/{CallSid}/Metrics"),
    "twilio.insights.v1.calls.summary.fetch": ("FetchSummary", "get", "/v1/Voice/{CallSid}/Summary"),
    "twilio.insights.v1.call_summaries.list": ("ListCallSummaries", "get", "/v1/Voice/Summaries"),
    "twilio.insights.v1.conferences.fetch": ("FetchConference", "get", "/v1/Conferences/{ConferenceSid}"),
    "twilio.insights.v1.conferences.list": ("ListConference", "get", "/v1/Conferences"),
    "twilio.insights.v1.conferences.conference_participants.fetch": (
        "FetchConferenceParticipant", "get", "/v1/Conferences/{ConferenceSid}/Participants/{ParticipantSid}",
    ),
    "twilio.insights.v1.conferences.conference_participants.list": (
        "ListConferenceParticipant", "get", "/v1/Conferences/{ConferenceSid}/Participants",
    ),
    "twilio.insights.v1.rooms.fetch": ("FetchVideoRoomSummary", "get", "/v1/Video/Rooms/{RoomSid}"),
    "twilio.insights.v1.rooms.list": ("ListVideoRoomSummary", "get", "/v1/Video/Rooms"),
    "twilio.insights.v1.rooms.participants.fetch": (
        "FetchVideoParticipantSummary", "get", "/v1/Video/Rooms/{RoomSid}/Participants/{ParticipantSid}",
    ),
    "twilio.insights.v1.rooms.participants.list": (
        "ListVideoParticipantSummary", "get", "/v1/Video/Rooms/{RoomSid}/Participants",
    ),
}


def test_the_symbol_map_reproduces_the_generated_sdk_exactly():
    """Total coverage, asserted as a set rather than as a threshold.

    Every operation the document declares resolves, and resolves to the symbol the
    published library exposes. Equality both ways is deliberate: a subset assertion would
    pass while the map invented extra symbols nobody can call, and those are the ones that
    silently bind a call site to the wrong operation.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    assert set(mapping) == set(SDK_GROUND_TRUTH)
    for symbol, (operation_id, http_method, path) in SDK_GROUND_TRUTH.items():
        assert mapping[symbol] == {"operation_id": operation_id, "http_method": http_method, "path": path}


def test_a_mount_name_overrides_a_path_segment_naming_the_wrong_resource():
    """`/v1/Voice/{Sid}` is `client.insights.v1.calls`, not `.voice`.

    The single most important case in this file. Stripe's resource name falls out of the
    URL because Stripe's URLs are named after its resources; Twilio's are not, and here the
    path says `Voice` while the library says `calls`. A derivation that trusted the path
    would produce a symbol no customer can have written, so every call site on the busiest
    resource in the product would silently fail to bind.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    assert mapping["twilio.insights.v1.calls.fetch"]["path"] == "/v1/Voice/{Sid}"
    assert not any(symbol.startswith("twilio.insights.v1.voice") for symbol in mapping)


def test_a_path_segment_supplies_the_mount_the_specification_leaves_unstated():
    """`mountName` is a sparse hint, so it cannot be the only source.

    In `twilio_insights_v1` it covers 4 of the 15 paths that declare operations. That
    denominator is one product document and is stated because it is easy to quote as
    Twilio's coverage, which it is not -- measured across five documents at tag 2.6.9 the
    figure is 28 of 95 paths, 29%, ranging from 9% in `twilio_video_v1` to 47% in
    `twilio_messaging_v1`. Sparse everywhere, but sparse to different degrees.

    `/v1/Video/Rooms` states no mount and the library calls it `rooms`, which is the last
    literal segment of the path. Falling back to the response schema name instead would
    answer `video_room_summaries` -- the schema is `insights.v1.video_room_summary` -- and
    that is a name the library does not expose.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    assert mapping["twilio.insights.v1.rooms.list"]["path"] == "/v1/Video/Rooms"
    assert "twilio.insights.v1.video_room_summaries.list" not in mapping


def test_class_name_is_not_read_as_a_mount_however_much_it_looks_like_one():
    """`className` is the generated class, not the attribute the client exposes.

    It is the obvious way to make the sparse hint look denser: `mountName` covers 29% of
    paths across five documents, and accepting `className` too would raise that to 45%. It
    would also be wrong. `/v1/Voice/{CallSid}/Summary` states `className: call_summary` and
    the library exposes `.summary`, so the extra coverage is bought entirely with wrong
    answers -- and a wrong symbol is worse than a missing one, because it binds a call site
    to an operation the customer never called instead of leaving it visibly unresolved.

    Checked against `twilio-python` on three products rather than inferred from this one:
    `video.v1.rooms(sid)` exposes `recordings` where `className` says `room_recording`, and
    `studio.v2.flows(sid)` exposes `revisions` where it says `flow_revision`. Ten paths
    across the five documents disagree this way and the library sides with the path segment
    in every one.
    """
    spec = _shape_spec()

    assert spec["paths"]["/v1/Voice/{CallSid}/Summary"]["x-twilio"]["className"] == "call_summary"

    mapping = build_symbol_map(spec, domain="insights", version="v1")

    assert "twilio.insights.v1.calls.summary.fetch" in mapping
    assert "twilio.insights.v1.calls.call_summary.fetch" not in mapping


def test_a_parent_link_nests_a_sub_resource_under_its_owner():
    """`x-twilio.parent` is what makes `calls.annotation` rather than `annotation`.

    The parent is spelled without the version prefix -- `/Voice/{Sid}` for the path
    `/v1/Voice/{Sid}` -- so resolving it means putting the prefix back. A resolution that
    failed would leave the sub-resource mounted at the top level, where it collides with
    nothing and is therefore never noticed.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    assert mapping["twilio.insights.v1.calls.annotation.fetch"]["path"] == "/v1/Voice/{CallSid}/Annotation"
    assert "twilio.insights.v1.annotation.fetch" not in mapping


def test_a_parent_chain_resolves_through_a_link_that_states_no_mount_itself():
    """`conference_participants` hangs off `/Conferences/{ConferenceSid}`, which has no mount.

    So the chain has to resolve each link by the same rule rather than only its last one.
    Both halves of the answer come from different sources here: the parent's name from its
    path segment, the child's from its `mountName`.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    symbol = "twilio.insights.v1.conferences.conference_participants.list"
    assert mapping[symbol]["path"] == "/v1/Conferences/{ConferenceSid}/Participants"


def test_the_verb_comes_from_the_operation_id_and_not_from_the_http_method():
    """Twilio writes the verb into `operationId`; Stripe does not.

    `POST /v1/Voice/Settings` is `UpdateAccountSettings`, and Stripe's HTTP rule reads a
    POST on a path with no id segment as `create`. Reading the method would name a function
    that does not exist on the resource.
    """
    mapping = build_symbol_map(_shape_spec(), domain="insights", version="v1")

    assert mapping["twilio.insights.v1.settings.update"]["http_method"] == "post"
    assert "twilio.insights.v1.settings.create" not in mapping


def test_a_path_with_no_operations_yields_nothing():
    """Twilio publishes two paths holding a `servers` override and no operations at all.

    Stripe publishes none, so this is a shape the existing adapter was never asked to
    tolerate. It must produce no symbol rather than a symbol with no operation behind it.
    """
    spec = _shape_spec()
    mapping = build_symbol_map(spec, domain="insights", version="v1")

    assert spec["paths"]["/v1/InsightsDomains/Flex/Reports/Query"] == {}
    assert not any("insights_domains" in symbol for symbol in mapping)


def test_two_operations_deriving_one_symbol_raise_rather_than_overwrite():
    """Same reasoning as the Stripe map: an overwrite makes the loser unreachable.

    No call site can resolve to it afterwards, so a breaking change against it can never
    produce a finding, and nothing anywhere reports that it happened.
    """
    colliding = {
        "paths": {
            "/v1/Conferences": {"get": {"operationId": "ListConference"}},
            "/v1/Rooms": {"x-twilio": {"mountName": "conferences"}, "get": {"operationId": "ListRoom"}},
        }
    }

    with pytest.raises(SymbolCollision) as excinfo:
        build_symbol_map(colliding, domain="insights", version="v1")

    message = str(excinfo.value)
    assert "twilio.insights.v1.conferences.list" in message
    assert "ListConference" in message
    assert "ListRoom" in message


# The same product's mounts, read from `twilio/rest/messaging/v1/__init__.py`. A second
# product is what separates a derivation that generalises from one tuned to the fixture it
# was written against: Messaging shares no resource, no naming habit and no nesting depth
# with Insights, and half of these names are ones no path segment spells.
MESSAGING_V1_SDK_MOUNTS = {
    "brand_registrations",
    "deactivations",
    "domain_certs",
    "domain_config",
    "domain_config_messaging_service",
    "domain_validate_dns",
    "external_campaign",
    "linkshortening_messaging_service",
    "linkshortening_messaging_service_domain_association",
    "request_managed_cert",
    "services",
    "tollfree_verifications",
    "usecases",
}


def test_the_derivation_holds_on_a_second_product_it_was_not_written_against():
    """Every top-level mount Messaging exposes, and no mount it does not.

    Equality both ways again, and it is doing real work here: a rule that over-produces
    would invent attributes the library has never had, and every call site bound through one
    resolves to an operation the customer did not call.
    """
    spec = json.loads((FIXTURES / "messaging_v1_shape.json").read_text(encoding="utf-8"))

    mapping = build_symbol_map(spec, domain="messaging", version="v1")
    mounts = {symbol.split(".")[3] for symbol in mapping}

    assert mounts == MESSAGING_V1_SDK_MOUNTS


def test_stripes_derivation_reaches_no_twilio_path_at_all():
    """The cleanest available evidence that the derivation is vendor knowledge.

    Stripe's map is not merely tuned for Stripe, it is inapplicable: its path pattern
    requires lowercase segments and Twilio's are PascalCase, so the intersection is empty
    rather than partial. Run against the real fixture, so it is a measurement and not an
    argument about a regular expression.
    """
    assert build_stripe_symbol_map(_shape_spec()) == {}


def test_the_adapter_satisfies_the_vendor_protocol(tmp_path):
    adapter = TwilioAdapter(
        spec_dir=FIXTURES, symbol_map_path=_written_map(tmp_path), documents=(INSIGHTS_V1,)
    )
    assert isinstance(adapter, VendorAdapter)
    assert adapter.vendor_id == "twilio"


def _written_map(tmp_path: Path) -> Path:
    destination = tmp_path / "map.json"
    destination.write_text(
        json.dumps(build_symbol_map(_shape_spec(), domain="insights", version="v1")), encoding="utf-8"
    )
    return destination


def test_operation_for_symbol_resolves_a_call_a_customer_could_have_written(tmp_path):
    adapter = TwilioAdapter(
        spec_dir=FIXTURES, symbol_map_path=_written_map(tmp_path), documents=(INSIGHTS_V1,)
    )

    ref = adapter.operation_for_symbol("twilio.insights.v1.calls.annotation.fetch")

    assert ref is not None
    assert ref.operation_id == "FetchAnnotation"
    assert ref.http_method == "get"
    assert ref.path == "/v1/Voice/{CallSid}/Annotation"


def test_operation_for_symbol_returns_none_for_a_symbol_it_cannot_place(tmp_path):
    adapter = TwilioAdapter(
        spec_dir=FIXTURES, symbol_map_path=_written_map(tmp_path), documents=(INSIGHTS_V1,)
    )
    assert adapter.operation_for_symbol("twilio.insights.v1.nonexistent.fetch") is None


def test_fetch_changes_reads_two_tags_of_one_product_document(tmp_path):
    """Real vendor bytes, real records. 2.1.0 to 2.3.0 is a release that broke things.

    The pair is not adjacent on purpose: 2.5.0 to 2.6.9 produces zero breaking changes for
    this document, so a test built on the two newest tags would pass with an empty list and
    prove nothing.
    """
    adapter = TwilioAdapter(
        spec_dir=FIXTURES, symbol_map_path=_written_map(tmp_path), documents=(INSIGHTS_V1,)
    )

    changes = list(adapter.fetch_changes("2.1.0", "2.3.0"))

    assert changes
    assert all(change.vendor_id == "twilio" for change in changes)
    assert all(change.from_version == "2.1.0" and change.to_version == "2.3.0" for change in changes)
    assert all(change.source == "oasdiff" for change in changes)
    assert {change.kind for change in changes} == {"request-parameter-type-changed"}
    assert {change.operation_id for change in changes} == {"ListConference", "ListConferenceParticipant"}


def test_fetch_changes_keeps_the_raw_oasdiff_record():
    """`raw` is what lets a better extractor re-derive against stored history."""
    adapter = TwilioAdapter(spec_dir=FIXTURES, symbol_map_path=None, documents=(INSIGHTS_V1,))

    change = next(iter(adapter.fetch_changes("2.1.0", "2.3.0")))

    assert change.raw["id"] == "request-parameter-type-changed"
    assert "PageSize" in change.raw["text"]


def test_fetch_changes_records_which_product_document_a_change_came_from():
    """`VendorChange` has no product axis, so the adapter puts one in `raw`.

    A Twilio version spans 61 documents and `operation_id` is unique across the five
    sampled here, but nothing in the specification promises that and the graph keys on
    `(vendor_id, operation_id)`. Recording the document is what makes a collision
    diagnosable instead of silently merging two products' changes.
    """
    adapter = TwilioAdapter(spec_dir=FIXTURES, symbol_map_path=None, documents=(INSIGHTS_V1,))

    change = next(iter(adapter.fetch_changes("2.1.0", "2.3.0")))

    assert change.raw["sync_product_document"] == "insights_v1.json"


def test_fetch_changes_spans_every_document_a_version_names():
    """A Twilio version is a tag over 61 documents, not one file.

    This is where the protocol stops fitting: `fetch_changes(from_version, to_version)`
    takes two version strings, and for Stripe each names one file. Here each names a
    directory, and the adapter has to fan out across it. Registering the same document
    twice is the cheapest way to prove the fan-out is real rather than a loop that runs
    once -- a single-document adapter returns half these records.
    """
    one = TwilioAdapter(spec_dir=FIXTURES, symbol_map_path=None, documents=(INSIGHTS_V1,))
    two = TwilioAdapter(
        spec_dir=FIXTURES,
        symbol_map_path=None,
        documents=(INSIGHTS_V1, ProductDocument("insights_v1.json", "insights", "v1")),
    )

    assert len(list(two.fetch_changes("2.1.0", "2.3.0"))) == 2 * len(list(one.fetch_changes("2.1.0", "2.3.0")))


def test_a_missing_document_for_a_version_raises_rather_than_reporting_no_changes():
    """An absent file must never read as a vendor who changed nothing.

    That is the failure mode the whole product exists to catch, arriving from our own side.
    """
    adapter = TwilioAdapter(spec_dir=FIXTURES, symbol_map_path=None, documents=(INSIGHTS_V1,))

    with pytest.raises(FileNotFoundError):
        list(adapter.fetch_changes("2.1.0", "9.9.9"))


def test_the_enum_noise_filter_is_applied_to_twilio_too():
    """76 of 83 records in this real release are `response-property-enum-value-added`.

    Stripe's adapter carries that kind as `NOISE_KINDS` with a comment calling it a
    judgement about one vendor's release habits. Measured against Twilio it is 92% of the
    release, against Stripe's roughly 80% -- so it is not a Stripe habit, and the constant
    is duplicated knowledge rather than vendor knowledge. Asserted here so that the
    duplication is visible in the suite rather than only in a report.
    """
    adapter = TwilioAdapter(spec_dir=FIXTURES, symbol_map_path=None, documents=(INSIGHTS_V1,))

    kinds = {change.kind for change in adapter.fetch_changes("2.1.0", "2.3.0")}

    assert "response-property-enum-value-added" not in kinds

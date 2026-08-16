"""`sync://feed/{vendor}`, served over the real transport from a verified local cache.

The feed path existed except its last link: `render_feed` and `sign_feed` publish, the consumer
verifies before parsing, `FeedCache` holds -- and nothing served it. This is the caller
`2026-07-25-sync-graph-surface-design.md:79` specifies, and the reason `FeedCache` sat in the
dead-links baseline.

Every test drives `serve` with scripted frames. One that called a handler directly would prove
the handler works, which was never in doubt, and say nothing about whether a client can reach it
-- and the lint cannot settle that either, since it matches bare names without resolving them.

A resource is not a tool. `tests/golden/tool_schemas.json` stays byte-identical, and the
resource declaration is pinned as a literal below, which plays the same role for resources that
the golden file plays for tools: a contract change has to be typed out on purpose.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from sync.core import DEVELOPMENT_FEED_PUBLIC_KEY
from sync.mcp.registry import schemas_as_data
from sync.mcp.resources import FEED_URI_TEMPLATE, resource_templates_as_data
from sync.mcp.server import serve
from sync.mcp.tools import GraphSurface
from sync.signals.feed import FeedCache, FeedSignatureError
from sync.signals.registry import available_vendors

FIXTURES = Path(__file__).parent / "fixtures" / "feed"
GOLDEN = Path(__file__).parent / "golden" / "tool_schemas.json"

# Bytes, never text. The signature covers exact bytes, so a payload decoded and re-encoded on
# the way in is not the payload the publisher signed.
SIGNED = (FIXTURES / "stripe.json").read_bytes()
SIGNATURE = (FIXTURES / "stripe.json.sig").read_bytes()
EMPTY = (FIXTURES / "empty.json").read_bytes()
EMPTY_SIGNATURE = (FIXTURES / "empty.json.sig").read_bytes()

# A byte flipped inside a string value, so the payload stays valid JSON carrying valid entries
# and only the signature stops covering it. The marker is what a served response must never
# contain, which is a stronger claim than "the store call raised".
TAMPERED = SIGNED.replace(b"GetCharges", b"GetCharqes")
TAMPER_MARKER = "GetCharqes"

# What the server advertises for resources, typed out rather than derived. The tool half of this
# contract lives in a golden file for the reason the registry docstring gives -- a golden file
# can diff data and cannot diff a decorator -- and this is the same discipline in the place a
# resource declaration can be read beside the test that pins it.
EXPECTED_TEMPLATES = [
    {
        "uriTemplate": "sync://feed/{vendor}",
        "name": "vendor-change-feed",
        "description": (
            "The normalized change feed for one vendor, served from this server's verified "
            "local cache. Vendor-side public information only: no call sites, no findings and "
            "no telemetry, which stay in the customer's own graph."
        ),
        "mimeType": "application/json",
    },
    {
        "uriTemplate": "sync://context/{repo_id}",
        "name": "repository-context",
        "description": (
            "What stays true of one repository while its code changes underneath: "
            "conventions, generated directories, the package manager its lockfile names. "
            "Written by an operator or copied from a `.sync/context.md` the repository "
            "itself carries. Never a call site, a finding or telemetry."
        ),
        "mimeType": "text/markdown",
    },
]


class FakeGraph:
    """The private graph, present so the resource can be shown not to touch it.

    Every method raises. `sync://feed/{vendor}` serves vendor-side public information, and the
    separation between the public feed and the private graph is the whole reason the resource
    reads from a cache rather than from a store -- so a resource that reached for the graph
    fails here rather than quietly crossing the line.
    """

    def __getattr__(self, name):
        def refuse(*args, **kwargs):
            raise AssertionError(f"the feed resource reached the private graph: {name}")

        return refuse


def _cache(**stored) -> FeedCache:
    cache = FeedCache(public_key=DEVELOPMENT_FEED_PUBLIC_KEY)
    for vendor_id, (payload, signature) in stored.items():
        cache.store(vendor_id, payload, signature)
    return cache


def _talk(*requests: dict, feed: FeedCache | None = None) -> list[dict]:
    """Drive one server run over scripted frames, and parse what it wrote."""
    stdin = io.StringIO("".join(json.dumps(request) + "\n" for request in requests))
    stdout = io.StringIO()
    serve(GraphSurface(FakeGraph()), stdin=stdin, stdout=stdout, feed=feed)
    return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]


def _req(id_, method, params=None):
    body = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        body["params"] = params
    return body


def _read(uri: str, feed: FeedCache | None):
    (response,) = _talk(_req(1, "resources/read", {"uri": uri}), feed=feed)
    return response


def _contents(response) -> dict:
    """The one content block a feed read returns, parsed."""
    (block,) = response["result"]["contents"]
    return json.loads(block["text"])


# --- a client can read it -----------------------------------------------------------


def test_a_client_reads_a_verified_feed_over_the_transport():
    """The link that was missing. Driven through `serve` rather than through a handler, because
    a handler nothing routes to is exactly the defect this task exists to close.
    """
    response = _read("sync://feed/stripe", _cache(stripe=(SIGNED, SIGNATURE)))

    body = _contents(response)
    assert {change["operation_id"] for change in body["changes"]} == {"GetCharges", "PostRefunds"}
    assert body["vendor_id"] == "stripe"


def test_the_read_reports_when_the_copy_was_fetched():
    """`feed_fetched_at` is what makes a stale feed degrade legibly rather than silently, and
    the graph-surface design already reports it everywhere else."""
    response = _read("sync://feed/stripe", _cache(stripe=(SIGNED, SIGNATURE)))

    body = _contents(response)
    assert body["feed_fetched_at"]
    assert body["digest"]


def test_the_server_advertises_a_resources_capability():
    (response,) = _talk(_req(1, "initialize"))

    assert "resources" in response["result"]["capabilities"]
    # The tools capability is not displaced by the resources one arriving.
    assert "tools" in response["result"]["capabilities"]


def test_the_resource_template_is_published_exactly_as_declared():
    (response,) = _talk(_req(1, "resources/templates/list"))

    assert response["result"]["resourceTemplates"] == EXPECTED_TEMPLATES
    assert resource_templates_as_data() == EXPECTED_TEMPLATES
    assert FEED_URI_TEMPLATE == "sync://feed/{vendor}"


def test_resources_list_names_only_the_vendors_a_verified_snapshot_exists_for():
    """A concrete listing is what a client can actually read. Advertising a vendor with no
    snapshot would offer a URI whose read fails, which is worse than not offering it.
    """
    (response,) = _talk(_req(1, "resources/list"), feed=_cache(stripe=(SIGNED, SIGNATURE)))

    assert [entry["uri"] for entry in response["result"]["resources"]] == ["sync://feed/stripe"]


# --- three outcomes, three answers --------------------------------------------------


def test_a_fetched_empty_feed_is_a_real_answer():
    """A vendor that published nothing renders `[]` and is a real fetch with a real timestamp.
    This is the outcome the other two must not be confused with.
    """
    response = _read("sync://feed/stripe", _cache(stripe=(EMPTY, EMPTY_SIGNATURE)))

    body = _contents(response)
    assert body["changes"] == []
    assert body["feed_fetched_at"]


def test_a_vendor_with_no_snapshot_is_not_an_empty_feed():
    """The false negative this repository has rejected everywhere else. Serving `[]` for "we
    have never fetched this" reads as "this vendor changed nothing", and a consumer cannot tell
    a quiet vendor from a fetch that never happened.
    """
    response = _read("sync://feed/stripe", _cache())

    assert "result" not in response
    assert response["error"]["data"]["reason"] == "not_fetched"
    assert response["error"]["data"]["vendor"] == "stripe"


def test_an_unknown_vendor_is_not_a_vendor_that_has_not_been_fetched():
    """Two different repairs. An unregistered vendor is a typo or a vendor Sync does not serve;
    a registered one with no snapshot is a fetch that has not run, and telling an operator the
    wrong one sends them to the wrong place.
    """
    response = _read("sync://feed/nosuchvendor", _cache(stripe=(SIGNED, SIGNATURE)))

    assert response["error"]["data"]["reason"] == "unknown_vendor"
    assert "stripe" in response["error"]["data"]["available"]


def test_the_three_outcomes_are_distinguishable_without_reading_prose():
    """Structurally, not by message text. A caller branching on wording is a caller that breaks
    when the wording improves, so the difference is in `error.data.reason` and in whether the
    frame carries a result at all.
    """
    fetched = _read("sync://feed/stripe", _cache(stripe=(EMPTY, EMPTY_SIGNATURE)))
    unfetched = _read("sync://feed/stripe", _cache())
    unknown = _read("sync://feed/nosuchvendor", _cache())

    assert "result" in fetched and "error" not in fetched
    assert unfetched["error"]["data"]["reason"] != unknown["error"]["data"]["reason"]


# --- what must never be served ------------------------------------------------------


def test_unverified_bytes_are_never_served():
    """The gate the feed is signed for. `FeedCache.store` refuses to write anything the
    publisher did not sign, so a tampered payload cannot reach the cache and therefore cannot
    reach a client -- and the assertion is that nothing derived from those bytes appears in the
    response, not merely that the store call raised.

    Non-vacuous by construction: injecting the tampered snapshot into the cache makes
    `GetCharqes` appear in the served body and turns this red.
    """
    cache = _cache()
    with pytest.raises(FeedSignatureError):
        cache.store("stripe", TAMPERED, SIGNATURE)

    response = _read("sync://feed/stripe", cache)

    assert TAMPER_MARKER not in json.dumps(response)
    assert response["error"]["data"]["reason"] == "not_fetched"


def test_a_rejected_refresh_leaves_the_previous_feed_served():
    """A forged update must not evict a good copy, or anyone able to answer a fetch can empty
    the cache by serving one bad payload -- a denial of service reachable without the key.
    """
    cache = _cache(stripe=(SIGNED, SIGNATURE))
    with pytest.raises(FeedSignatureError):
        cache.store("stripe", TAMPERED, SIGNATURE)

    body = _contents(_read("sync://feed/stripe", cache))

    assert {change["operation_id"] for change in body["changes"]} == {"GetCharges", "PostRefunds"}
    assert TAMPER_MARKER not in json.dumps(body)


def test_the_resource_carries_vendor_side_fields_and_nothing_graph_derived():
    """The public/private separation, asserted on the payload rather than trusted to the call
    graph. `FakeGraph` raises on every attribute, so a resource that reached for the store would
    have failed before this -- and this catches the other direction, a field smuggled in.
    """
    body = _contents(_read("sync://feed/stripe", _cache(stripe=(SIGNED, SIGNATURE))))

    published = {
        "vendor_id", "from_version", "to_version", "kind",
        "operation_id", "path_ptr", "severity", "source", "raw",
    }
    for change in body["changes"]:
        assert set(change) <= published

    forbidden = ("call_site", "repo_id", "finding", "binding_rung", "observed", "local_path")
    rendered = json.dumps(body)
    for leak in forbidden:
        assert leak not in rendered


def test_no_read_path_serves_a_vendor_the_cache_does_not_hold():
    """There is no "serve what we have anyway" flag, and this is what would catch one being
    added: an unfetched vendor answers with an error whatever else is in the cache.
    """
    response = _read("sync://feed/twilio", _cache(stripe=(SIGNED, SIGNATURE)))

    assert "result" not in response
    assert "GetCharges" not in json.dumps(response)


# --- a server configured with no cache at all ---------------------------------------


def test_a_server_with_no_feed_cache_advertises_nothing():
    """`serve` takes the cache as an argument and defaults to none, so a graph surface with no
    feed configured is a deployment and not a broken state. It offers no resource rather than
    offering one whose read would fail.
    """
    (response,) = _talk(_req(1, "resources/list"))

    assert response["result"]["resources"] == []


def test_no_cache_and_an_empty_cache_advertise_the_same_nothing():
    """The one place this module conflates two states on purpose. `read`'s own comment settles
    it: a cache holding nothing for a vendor and a server with no cache are the same fact to a
    client, and the repair for both is a fetch. The listing says it the same way.
    """
    (absent,) = _talk(_req(1, "resources/list"))
    (empty,) = _talk(_req(1, "resources/list"), feed=_cache())

    assert absent["result"] == empty["result"] == {"resources": []}


def test_a_server_with_no_cache_advertises_nothing_and_serves_nothing():
    """Both halves of the listing's promise, on the configuration that holds no snapshot at
    all: nothing is offered, and every registered vendor refuses with the reason that names the
    repair. Advertising the registered vendors here would hand a client six URIs that all fail.
    """
    (listing,) = _talk(_req(1, "resources/list"))

    assert listing["result"]["resources"] == []
    for vendor_id in available_vendors():
        assert _read(f"sync://feed/{vendor_id}", None)["error"]["data"]["reason"] == "not_fetched"


def test_the_listing_and_the_read_agree_about_every_registered_vendor():
    """A client that trusts a listing has no reason to handle a listed resource being absent,
    so the listing has to be exactly the set that reads. Checked in both directions rather than
    asserted on the one vendor a snapshot happens to be held for.
    """
    feed = _cache(stripe=(SIGNED, SIGNATURE))
    (listing,) = _talk(_req(1, "resources/list"), feed=feed)
    advertised = {entry["uri"] for entry in listing["result"]["resources"]}

    for vendor_id in available_vendors():
        uri = f"sync://feed/{vendor_id}"
        assert ("result" in _read(uri, feed)) == (uri in advertised), uri


# --- a uri this server does not serve at all ----------------------------------------


def test_a_uri_outside_the_feed_scheme_is_refused_with_its_own_reason():
    """The fourth outcome, and the only refusal on this surface that says what it is. A client
    that asked for something this server does not serve gets `unknown_resource` and the uri
    back, which is a different repair from either feed refusal.
    """
    response = _read("file:///etc/passwd", _cache(stripe=(SIGNED, SIGNATURE)))

    assert "result" not in response
    assert response["error"]["data"]["reason"] == "unknown_resource"
    assert response["error"]["data"]["uri"] == "file:///etc/passwd"


def test_an_unknown_resource_is_not_an_unknown_vendor():
    """Three refusals, three repairs, told apart by `reason` rather than by wording. Asking
    this server for a resource it does not have is fixed by asking for a different resource;
    asking for a feed nothing registers is fixed by fixing the vendor id.
    """
    outside = _read("sync://graph/stripe", _cache(stripe=(SIGNED, SIGNATURE)))
    vendor = _read("sync://feed/nosuchvendor", _cache(stripe=(SIGNED, SIGNATURE)))

    assert outside["error"]["data"]["reason"] == "unknown_resource"
    assert vendor["error"]["data"]["reason"] == "unknown_vendor"


def test_a_read_with_no_uri_is_refused_rather_than_defaulted():
    """`resources/read` with no `uri` reaches this module as the empty string, because the
    transport passes `params.get("uri") or ""`. An empty string must not prefix-match its way
    to a vendor id of `""`, which would answer a question the client did not ask.
    """
    (response,) = _talk(_req(1, "resources/read", {}), feed=_cache(stripe=(SIGNED, SIGNATURE)))

    assert response["error"]["data"]["reason"] == "unknown_resource"
    assert response["error"]["data"]["uri"] == ""


@pytest.mark.parametrize(
    "uri", ["sync://feeds/stripe", "sync://feed", "SYNC://FEED/stripe", "sync:/feed/stripe", "stripe"]
)
def test_a_uri_that_only_resembles_the_feed_prefix_is_outside_it(uri: str):
    """A prefix match and nothing looser. Each of these is one character away from the real
    template, and answering any of them would mean guessing which resource was meant.
    """
    assert _read(uri, _cache(stripe=(SIGNED, SIGNATURE)))["error"]["data"]["reason"] == "unknown_resource"


def test_the_prefix_boundary_is_exact_in_the_other_direction_too():
    """`sync://feed/` is inside the scheme with an empty vendor id, which is an unknown vendor
    and not an unknown resource. The pair fixes where the boundary is: one character decides
    which of two repairs a client is told about.
    """
    assert _read("sync://feed", _cache())["error"]["data"]["reason"] == "unknown_resource"
    assert _read("sync://feed/", _cache())["error"]["data"]["reason"] == "unknown_vendor"


# --- the frozen tools -------------------------------------------------------------


def test_the_published_tool_contract_is_byte_stable():
    """The golden file pinned by digest as well as by equality.

    `schemas_as_data() == json.loads(...)` catches a schema that changed. This catches the
    golden file itself moving -- a regenerated expectation is the one edit that makes the other
    test pass while the published contract has in fact changed. Normalised before hashing so a
    checkout's line endings are not what is being pinned.
    """
    canonical = json.dumps(json.loads(GOLDEN.read_text(encoding="utf-8")), sort_keys=True).encode()

    assert hashlib.sha256(canonical).hexdigest() == (
        "b69c020883a894c2e4174b5a2c6a7bc68a93eb3fdfb3175950631acf26b36352"
    )


def test_adding_a_resource_leaves_all_four_tool_schemas_untouched():
    """A resource is not a tool. The golden file is the executable form of the freeze, and
    regenerating it to make a test pass converts the one artifact that would have caught a
    breaking change into a record of it.
    """
    assert schemas_as_data() == json.loads(GOLDEN.read_text(encoding="utf-8"))

    (response,) = _talk(_req(1, "tools/list"))
    assert [tool["name"] for tool in response["result"]["tools"]] == [
        "sync_whats_at_risk", "sync_explain_call_site", "sync_whats_changed", "sync_propose_patch",
    ]

"""`sync://feed/{vendor}`, the one resource, declared as data beside the four tools.

`2026-07-25-sync-graph-surface-design.md:79` specifies it as "the normalized change feed, served
from the server's local cache", and it is the caller `FeedCache` was built for: the feed path
had a publisher, a verifier and a cache, and nothing that served any of it.

A resource is not a tool
------------------------
The tool set is frozen and `tests/golden/tool_schemas.json` is the executable form of that
freeze. Nothing here appears in it, and nothing here changes it. Declaring resources in their
own module rather than as a fifth entry in `registry.TOOLS` is what makes that structural: there
is no arrangement of this file that can alter a tool's schema.

Served from the cache, never from the graph
-------------------------------------------
The separation between the public feed and the private graph is the design's, not a preference.
The feed is vendor-side public information -- what a vendor changed -- and carries no call site,
no finding and no telemetry-derived shape, because those are customer-specific and stay in the
customer's own graph. So this reads a `FeedCache` and is handed no store at all: a resource that
could reach the graph would be one code change away from publishing it.

What a published entry may contain is `FEED_FIELDS`, which the publisher already fixed as an
allow-list rather than a dump, for the same reason: `VendorChange` lives in `sync.core` where
anyone may add a column, and a deny-list would publish it by default.

Three outcomes, and the empty one is the trap
---------------------------------------------
- A verified snapshot, however few changes it holds, is a result.
- A vendor with no snapshot is an error, because serving `[]` for "never fetched" reads as "this
  vendor changed nothing" -- a consumer cannot tell a quiet vendor from a fetch that never ran,
  and that false negative is the shape this repository has rejected everywhere else.
- A vendor nothing registers is a different error, because it needs a different repair: one is a
  typo, the other is a fetch that has not happened.

They are told apart by `error.data.reason` rather than by wording. A caller branching on prose
is a caller that breaks when the prose improves.

Nothing unverified is reachable from here. `FeedCache.store` writes nothing until both gates
pass, so the cache holds only what the publishing key vouched for, and this module has no path
that takes bytes -- there is no "serve what we have anyway" to add a flag to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sync.signals.feed.cache import FeedCache
from sync.signals.feed.publisher import FEED_FIELDS

FEED_URI_PREFIX = "sync://feed/"
FEED_URI_TEMPLATE = f"{FEED_URI_PREFIX}{{vendor}}"
FEED_MIME_TYPE = "application/json"

UNKNOWN_VENDOR = "unknown_vendor"
NOT_FETCHED = "not_fetched"
UNKNOWN_RESOURCE = "unknown_resource"


class ResourceError(Exception):
    """A resource that cannot be read, and the machine-readable reason why.

    Carries `reason` and `data` because the transport turns this into a JSON-RPC error and a
    client has to branch on something stabler than a message. Raised rather than returned for
    the reason `verify_feed` raises: a returned sentinel is a value a caller can forget to
    check, and here forgetting it means serving an absence as an answer.
    """

    def __init__(self, message: str, reason: str, **data: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.data: dict[str, Any] = {"reason": reason, **data}


@dataclass(frozen=True)
class ResourceTemplateSpec:
    uri_template: str
    name: str
    description: str
    mime_type: str


RESOURCE_TEMPLATES: tuple[ResourceTemplateSpec, ...] = (
    ResourceTemplateSpec(
        uri_template=FEED_URI_TEMPLATE,
        name="vendor-change-feed",
        description=(
            "The normalized change feed for one vendor, served from this server's verified "
            "local cache. Vendor-side public information only: no call sites, no findings and "
            "no telemetry, which stay in the customer's own graph."
        ),
        mime_type=FEED_MIME_TYPE,
    ),
)


def resource_templates_as_data() -> list[dict[str, Any]]:
    """The templated resources, in the shape a client receives them."""
    return [
        {
            "uriTemplate": template.uri_template,
            "name": template.name,
            "description": template.description,
            "mimeType": template.mime_type,
        }
        for template in RESOURCE_TEMPLATES
    ]


def resources_as_data(feed: FeedCache | None, known_vendors: tuple[str, ...]) -> list[dict[str, Any]]:
    """The concrete URIs a client can read right now, which is what a listing is for.

    Only vendors a verified snapshot is held for. Advertising one with no snapshot would offer a
    URI whose read fails, which is worse than not offering it -- a client that trusts a listing
    has no reason to handle a listed resource being absent.

    Built by asking the cache about each registered vendor rather than by enumerating the cache.
    `FeedCache` publishes no enumeration, and reaching for its private mapping to get one would
    be a cross-package private access that breaks silently. Asking is also the better question:
    a snapshot held for a vendor nothing registers is not a resource this server offers.
    """
    if feed is None:
        return []
    return [
        {
            "uri": f"{FEED_URI_PREFIX}{vendor_id}",
            "name": f"{vendor_id} change feed",
            "description": f"Verified change feed for {vendor_id}.",
            "mimeType": FEED_MIME_TYPE,
        }
        for vendor_id in known_vendors
        if feed.snapshot(vendor_id) is not None
    ]


def read(uri: str, feed: FeedCache | None, known_vendors: tuple[str, ...]) -> dict[str, Any]:
    """One resource's contents, or `ResourceError` naming which of the three outcomes it is.

    `known_vendors` is supplied rather than read here, so this module holds no opinion about
    which vendors exist -- the registry answers that, and a second list would drift from it.
    """
    if not uri.startswith(FEED_URI_PREFIX):
        raise ResourceError(f"unknown resource: {uri}", UNKNOWN_RESOURCE, uri=uri)

    vendor_id = uri[len(FEED_URI_PREFIX):]
    if vendor_id not in known_vendors:
        raise ResourceError(
            f"no vendor is registered as '{vendor_id}'; available: {', '.join(known_vendors)}",
            UNKNOWN_VENDOR,
            vendor=vendor_id,
            available=list(known_vendors),
        )

    snapshot = feed.snapshot(vendor_id) if feed is not None else None
    if snapshot is None:
        # A cache holding nothing for this vendor and a server with no cache configured are the
        # same fact to a client: no verified snapshot is available to serve.
        raise ResourceError(
            f"no verified feed has been fetched for {vendor_id}",
            NOT_FETCHED,
            vendor=vendor_id,
        )

    return {
        "vendor_id": snapshot.vendor_id,
        "changes": [
            {field: getattr(change, field) for field in FEED_FIELDS}
            for change in snapshot.changes
        ],
        # Both integrity facts travel with the copy: the digest says these are the bytes that
        # were stored, and `feed_fetched_at` says when, so a stale feed degrades legibly.
        "digest": snapshot.digest,
        "feed_fetched_at": snapshot.fetched_at.isoformat(),
    }

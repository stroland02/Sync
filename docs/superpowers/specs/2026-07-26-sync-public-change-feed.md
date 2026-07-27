# Sync — The Public Change Feed

**Date:** 2026-07-26
**Status:** Specified. Fills the scope boundary left open by `2026-07-25-sync-graph-surface-design.md`.
**Scope:** What the free, public, cross-vendor API-change feed actually is — schema, hosting, integrity,
license, and how it is produced. Consumed by `FeedCache` (`2026-07-25-sync-mcp-graph-surface.md`, Task 4), by
`sync_whats_changed`, and mocked against by the replay tier in `2026-07-26-sync-observed-contract-drift.md`.

## Why this document exists

Three committed specs reference the feed and none defines it. `2026-07-25-sync-graph-surface-design.md`
explicitly flags this: *"The public change feed is consumed by this design and not specified by it... an
unsigned feed that drives code changes is a supply-chain surface, and it deserves the same scrutiny as the
threat model gives the verification sandbox."* `2026-07-25-sync-positioning-and-open-core.md` commits to
publishing it as the attack on FlareCanary, ShiftGraph, and Deprecatr AI's entire product. Neither says what it
looks like on disk or on the wire. This does.

## What it is

One JSON array per vendor, published to a static URL, requiring no authentication:

```
https://feed.sync.dev/{vendor_id}.json
https://feed.sync.dev/{vendor_id}.json.sig
```

Each entry is a `VendorChange`, the same contract already defined in `sync.core`:

```json
[
  {
    "vendor_id": "stripe",
    "from_version": "2026-05-01",
    "to_version": "2026-11-01",
    "kind": "response-property-removed",
    "operation_id": "PostCharges",
    "path_ptr": "/v1/charges",
    "severity": "breaking",
    "source": "oasdiff",
    "raw": {}
  }
]
```

**`path_ptr` is the operation's URL path, not a JSON Pointer into a response body.** An
earlier draft of this document showed `"/data/status"` there and was wrong about the field it
described. `sync/signals/oasdiff.py` sets `path_ptr=record.get("path", "")`, which is what
oasdiff reports as `path` — the URL. The name is misleading and predates the implementation;
it is not renamed here because `VendorChange` lives in `sync.core`, which every adapter and
the MCP graph surface already depend on, and a rename is a breaking change to that contract
for no gain the feed needs.

`kind` is oasdiff's checker rule identifier — `record["id"]`, drawn from the 200-plus rules
`oasdiff checks` enumerates for the pinned binary. Consumers must tolerate an identifier they
do not recognise; the set grows with each oasdiff release.

The **changed field** is not a top-level column at all. It is named inside `raw`, as the first
backticked token in oasdiff's free-text `text` message, and `sync.signals.oasdiff.changed_field()`
is the only supported way to extract it — it reduces oasdiff's schema path to its leaf property
name, stepping over the `anyOf`/`oneOf`/`allOf` segments oasdiff interposes. This is why `raw`
is carried in the feed rather than dropped as an implementation detail: without it, a consumer
cannot tell which field moved.

No wrapper object, no pagination envelope, no per-request negotiation. `FeedCache.store()`
(`2026-07-25-sync-mcp-graph-surface.md`, Task 4) already parses exactly this shape — a bare JSON array of
`VendorChange`-compatible entries — and this document does not add a layer above it. The array is the whole
contract, the same discipline the MCP tool schemas already follow: **the format is versioned by never breaking
it**, not by a version field inside it. New fields may be added as optional; nothing is renamed or removed.

## Production

The feed is not maintained by hand. It is the output of machinery M0 and M1 already build, published rather
than kept internal.

```
oasdiff (pinned spec pair)  ─┐
                             ├─► VendorChange rows  ─► one JSON array per vendor  ─► signed, published
changelog (LangChain chain) ─┘
```

This is the exact pipeline `2026-07-25-sync-self-maintaining-apis-design.md` specifies for M0's Stripe adapter:
`oasdiff` for the authoritative classification, a changelog chain for enrichment and prioritization, never the
reverse. The feed publishes the same rows a customer's own graph would compute — the only difference is that
it is computed once per vendor and served to everyone, which is the O(1)-per-vendor economics the latency
architecture already claims.

**Cadence tracks the vendor.** Stripe ships semiannual breaking releases, so its feed file changes rarely.
MCP servers, measured in `2026-07-25-sync-mcp-drift-measurement.md` at breaking changes in roughly half their
release transitions, need near-continuous republication. The feed is regenerated on every new pinned version
pair a `VendorAdapter` processes, not on a fixed schedule — a vendor that ships nothing produces no update, and
one that ships constantly is served as fast as its adapter runs.

## Integrity

The feed drives code changes, so a forged entry proposes a patch against real code — the supply-chain risk the
graph-surface design already names. The mitigation is signing, specified concretely here rather than deferred
again.

Each `{vendor_id}.json` is signed with a detached Ed25519 signature at `{vendor_id}.json.sig`, verified against
a public key committed in the `sync.core` package and rotatable only through a release. `FeedCache.store()`
gains a mandatory verification step before `_parse()` runs:

```python
def store(self, vendor_id: str, payload: bytes, signature: bytes) -> FeedSnapshot:
    if not verify(payload, signature, PUBLISHER_PUBLIC_KEY):
        raise ValueError(f"feed signature for {vendor_id} does not verify")
    changes = _parse(payload)
    ...
```

This extends the Task 4 interface from the graph-surface plan; it does not replace it. The existing SHA-256
digest stays as a corruption check; the signature is the authenticity check, and both are required —
corruption and forgery are different failure modes and one check does not stand in for the other.

**Verification does not stop at the feed.** Nothing a signature can vouch for is trusted further than any
other input: a signed, correctly-parsed `VendorChange` still produces a patch that must pass `tsc` and the
customer's own CI before it reaches a pull request. The signature raises the cost of poisoning the feed; the
verification gate is what makes poisoning it unprofitable even if it happens.

## Hosting

Static files behind a CDN, exactly as `2026-07-25-sync-graph-surface-design.md` specifies for the separation
between the public feed and the private graph: cacheable, byte-identical for every consumer, requiring no
account and reporting nothing about who fetched it. No server-side logic, no rate limit that could throttle a
legitimate customer's local `FeedCache`, no dependency on Sync's own uptime for a customer already holding a
cached copy — a stale feed degrades gracefully (`sync_whats_changed` already reports `feed_fetched_at`,
per the graph-surface design), it never breaks.

## Data license

CC0. No attribution requirement, no share-alike obligation, maximum reuse.

This resolves an item `2026-07-25-sync-positioning-and-open-core.md` left open, weighing CC0 against ODbL's
share-alike. CC0 wins for a reason specific to this feed's purpose: the feed exists to commoditize a layer
Sync does not own and to make Sync's schema the default one a competitor's tooling speaks. Share-alike would
constrain how a downstream consumer redistributes a derived feed, which cuts against exactly the adoption the
feed is for. The asset being protected is the binding engine, under FSL; the feed is not that asset and gains
nothing from restricting its reuse.

## What is never in the feed

No customer data, of any kind — the feed is vendor-side public information only, produced before any customer
relationship exists. No `observed` bindings, no telemetry-derived shapes from
`2026-07-26-sync-observed-contract-drift.md` — those are customer-specific and stay in the customer's own
graph. The feed carries exactly what a `VendorAdapter.fetch_changes()` call returns, nothing a customer's
traffic contributed.

## Package placement

Publishing is a `sync.signals` concern — the package already responsible for turning vendor artifacts into
`VendorChange` rows owns turning them into a published file. No new package. The signing keypair and the
publish job are operational, not architectural, and are out of scope for this document.

## Sequencing

| When | What |
|---|---|
| M0 (already building this) | The Stripe `VendorAdapter` producing `VendorChange` rows is the feed's entire content for one vendor. Nothing new to build; this document specifies what is done with output that already exists. |
| Before first publication | Ed25519 keypair generated, public key committed to `sync.core`, `FeedCache.store()` extended with the verification step above. |
| M1 | MCP as a second vendor in the feed, chosen because its measured drift rate makes it a real test of publication cadence rather than Stripe's near-static one. |
| Ongoing | Republish per adapter run, never on a fixed clock. |

## Verification

- **A tampered payload is rejected.** Flip one byte in a fixture feed, confirm `FeedCache.store()` raises
  before any `VendorChange` is constructed from it — signature verification must run before parsing, not after.
- **A validly signed but schema-invalid payload is still rejected** by the existing `_parse()` check — signing
  proves authenticity, not correctness, and both gates are required in that order.
- **The array format never gains a wrapper.** A test asserts `FeedCache.store()` accepts a bare JSON array and
  rejects an object at the top level, matching what Task 4 already specifies.
- **A regenerated feed for a vendor with zero new changes is byte-identical** to the previous publish, so a
  customer's cached copy is never invalidated by a no-op adapter run.

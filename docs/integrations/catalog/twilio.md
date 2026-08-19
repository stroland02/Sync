# Twilio

> Status: **supported** -- a registered `coded` adapter serves `twilio`.

## Quickstart

From nothing to this vendor's findings, on your own repository. The full journey, including what the remediation loop needs, is in [Getting started](../../getting-started.md).

```bash
npm start                                  # bring Sync up; it sets up everything
uv run sync index --repo <your-remote>     # read your call sites into the graph
uv run sync run --vendor twilio \
    --from-version <pinned> --to-version <target> --repo <your-remote>
```

The console then shows every call site bound to Twilio operations, each finding with the provenance rung it arrived at.

## What Sync watches

Sync stages this vendor's versioned OpenAPI specification and diffs two pinned versions with oasdiff. A hand-written adapter resolves the vendor's own symbol scheme, so a changed operation is matched to the SDK call your code actually makes.

Source: [`src/sync/signals/twilio/`](../../../src/sync/signals/twilio/)

## What Sync does not watch

Stated because absence claimed as coverage is the failure this product replaces:

- **Runtime behavior the specification does not carry.** A latency regression or a semantic change behind an unchanged schema is invisible to this adapter; attach telemetry to observe it, and Sync will keep the two kinds of evidence apart.
- **Anything requiring this vendor's credentials.** Sync holds no customer secrets, so nothing here calls the vendor's API on your behalf.
- **Versions outside the two you pin.** A diff is between the versions a run names; Sync does not interpolate what happened between them.

## What your lockfile declares

- **typescript**: `twilio`
Official documentation: [https://www.twilio.com/docs](https://www.twilio.com/docs)

# Browserbase

> Status: **supported** -- a registered `generated` adapter serves `browserbase`.

## Quickstart

From nothing to this vendor's findings, on your own repository. The full journey, including what the remediation loop needs, is in [Getting started](../../getting-started.md).

```bash
npm start                                  # bring Sync up; it sets up everything
uv run sync index --repo <your-remote>     # read your call sites into the graph
uv run sync run --vendor browserbase \
    --from-version <pinned> --to-version <target> --repo <your-remote>
```

The console then shows every call site bound to Browserbase operations, each finding with the provenance rung it arrived at.

## What Sync watches

Sync reads the manifest this vendor's SDK generator commits to `browserbase/sdk-python`, fetches the specification the manifest names when its hash moves, and diffs pinned versions with oasdiff. No agreement with the vendor is required and none can be withdrawn: the manifest is what the generator writes for its own reasons.

Source: [`src/sync/signals/generated/`](../../../src/sync/signals/generated/), configured by one entry in [`generated-vendors.yaml`](../../../generated-vendors.yaml)

## What Sync does not watch

Stated because absence claimed as coverage is the failure this product replaces:

- **Runtime behavior the specification does not carry.** A latency regression or a semantic change behind an unchanged schema is invisible to this adapter; attach telemetry to observe it, and Sync will keep the two kinds of evidence apart.
- **Anything requiring this vendor's credentials.** Sync holds no customer secrets, so nothing here calls the vendor's API on your behalf.
- **Versions outside the two you pin.** A diff is between the versions a run names; Sync does not interpolate what happened between them.

Official documentation: [https://docs.browserbase.com](https://docs.browserbase.com)

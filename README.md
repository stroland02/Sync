# Sync

Agentic Codebase Review built on the fundamental Pillars of creating Software

Self-maintaining API integrations.

---

**Self-maintaining API integrations.** Sync watches the third-party APIs your code calls, and when one of them changes, breaks, or starts costing you money, it opens a pull request that fixes your code — already verified green by your own CI.

Existing tools watch the API you *publish* and stop at an alert. Sync watches the APIs you *consume*, across every vendor, and repairs the calling code. Dependabot solved this shape for package versions; Sync does it for API surfaces.

## Status

Pre-alpha, and specific about it. Milestone M0 targeted one thing: a breaking change between two pinned Stripe OpenAPI versions producing a CI-green pull request against a real TypeScript repository, unattended. **That works.**

One `sync run` against a fork of `stripe/stripe-connect-furever-demo` produced [pull request #1](https://github.com/stroland02/stripe-connect-furever-demo/pull/1) — two deletions in one file, removing a withdrawn request argument at both call sites that passed it, typecheck green on the branch. No human between detection and pull request.

Two qualifications, because they change what the result means. The vendor change was constructed: a property removed from a real pinned specification rather than one Stripe withdrew, since no window of Stripe's own history examined here contains a top-level breaking change this application would notice. And matching is currently strongest where a call site reads shallow fields — a change twenty-five segments deep against a call site that records three emits a finding naming both ends rather than claiming the field was read.

Known limitations are enumerated in the design document rather than left implicit. The customer's CI remains the authoritative gate.

## How it works

Sync builds an **API Dependency Graph** for each customer — every third-party call site in the codebase, joined against vendor specifications and the customer's own production telemetry. Three detectors query that graph:

- **Vendor change** — a vendor shipped something that breaks you.
- **Efficiency** — you are paying for calls you do not need.
- **Production error** — an endpoint is failing in production.

All three emit the same finding into one remediation pipeline: locate, patch, verify, open. Nothing reaches a pull request without passing the customer's CI.

## Coverage

Vendor support is a plugin surface, not a hard-coded list. Each vendor — a REST API, an MCP server, or an internal service — is one implementation of the `VendorAdapter` protocol, which depends on `sync.core` and nothing else. Stripe is the first; the interface is the product.

## Design

Full specification: [`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`](docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md)

## License

Open core. The plugin SDK, adapter interfaces, and reference implementations are open source; the hosted multi-tenant runtime is commercial.

# Sync

Agentic Codebase Review built on the fundamental Pillars of creating Software

---

**Self-maintaining API integrations.** Sync watches the third-party APIs your code calls, and when one of them changes, breaks, or starts costing you money, it opens a pull request that fixes your code — already verified green by your own CI.

Existing tools watch the API you *publish* and stop at an alert. Sync watches the APIs you *consume*, across every vendor, and repairs the calling code. Dependabot solved this shape for package versions; Sync does it for API surfaces.

## Status

Pre-alpha. Milestone M0 is in progress: a real breaking change between two pinned Stripe OpenAPI versions producing a CI-green pull request against a real TypeScript repository, unattended.

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

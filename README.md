# Sync

Agentic Codebase Review built on the fundamental Pillars of creating Software

---

**Self-maintaining API integrations.** Sync watches the third-party APIs your code calls, and when one of them changes, breaks, or starts costing you money, it opens a pull request that fixes your code — already verified green by your own CI.

Existing tools watch the API you *publish* and stop at an alert. Sync watches the APIs you *consume*, across every vendor, and repairs the calling code. Dependabot solved this shape for package versions; Sync does it for API surfaces.

## Status

Pre-alpha, and specific about it. Milestone M0 targets one thing: a breaking change between two pinned Stripe OpenAPI versions producing a CI-green pull request against a real TypeScript repository, unattended.

Proven against a real fork and real vendor specifications: specification fetch, `oasdiff`, noise filtering, symbol mapping, clone, dependency installation, indexing, the graph store, detection, the patch agent, and `tsc` passing on the patched clone. Proven separately against real GitHub: branch push under Sync's own commit identity, and the CI gate correctly refusing to open a pull request on a red build.

Not yet proven: one invocation carrying a finding all the way to an opened pull request. The remediation half and the forge half have each run against production, but not yet in the same run.

Known limitations are enumerated in the design document rather than left implicit — including one case where the local typecheck can pass on an artifact that never reaches the branch. The customer's CI remains the authoritative gate.

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

# Security Policy

## Reporting a vulnerability

Report privately through [GitHub Security Advisories](https://github.com/stroland02/sync/security/advisories/new)
rather than opening an issue.

Include what you did, what happened, and what you expected. A reproduction is worth more than a
description. You will get an acknowledgement within three working days.

Do not open a public issue for anything with a security dimension, including a suspected one.

## What Sync touches, and what it does not

Sync reads a customer's source code and opens pull requests against their repository. That is a
large amount of trust, so the boundaries are stated rather than implied.

**We never hold customer secrets.** This one is unqualified.

**Verification runs the customer's toolchain, not their application.** `run_tsc` prefers the
clone's own `node_modules/.bin/tsc`, resolved through the customer's `.npmrc`, and the patch agent
holds `Bash` inside the clone. Dependency installs pass `--ignore-scripts`, so no lifecycle script
runs, and Sync never executes the customer's application — but it does execute their compiler. The
honest sentence is "we do not run your app", not "we never execute your code".

**Nothing reaches a pull request unverified.** Every patch passes `tsc` and then the customer's own
CI. There is no path that skips the gate.

**A signature proves origin, not correctness.** A validly signed vendor feed carrying a malformed
`VendorChange` fails at parse, before any row is built from it. See
[the threat model](docs/superpowers/specs/2026-07-25-sync-threat-model.md) for what a malicious or
compromised vendor feed can and cannot cause.

**Telemetry is stripped of identifiers at the boundary.** A `RequestCorrelator` receives an
observed path carrying real customer identifiers and must return the vendor's own published
template — `/v1/charges/{charge}` rather than `/v1/charges/ch_3PjkLm...`. That substitution is
where a customer's identifiers stop travelling, and `sync.core.conformance.check_request_correlator`
enforces it.

**The corpus stores shape, not source.** `migration_outcome` holds symbol shapes and salted
argument-key digests. Neither the diff nor the file path is stored — a path is customer structure
even when the code is not included.

## Supported versions

Pre-alpha. There is no released version and no backport branch; fixes land on `main`.

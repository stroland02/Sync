# Signals, Adapters & Indexing Beta Stock-Take

**Author**: Lane D (Signals, Adapters, Intake & Indexing)  
**Date**: 2026-08-17  
**Scope**: src/sync/signals/**, src/sync/index/**, src/sync/rehearse/**  
**Reference Precedent**: docs/superpowers/reports/2026-08-17-console-beta-stock-take.md

---

## 1. Executive Assessment

Lane D core subsystems -- static call site extraction for TypeScript and Python, vendor spec change diffing and extraction for Stripe and Twilio, generated spec adapters for Stainless manifests, intake attempt diagnostics, and zero-remote rehearsal harnesses -- are verified, stable, and ready for design-partner beta.

Walking all owned paths against what a partner experiences on **Day 1 (configuring repositories, scanning third-party SDKs, and running intake)** yields four concrete findings: two that are resolved or guarded by design, one that is an honest boundary to maintain, and one post-beta item to keep deferred.

---

## 2. Walk by Subsystem

### A. TypeScript & Python AST Indexers (src/sync/index/**)

- **What works**:
  - 	s_ast.py: Accurately discovers and binds common import forms (import Stripe from stripe, const stripe = require(stripe), import { Twilio } from twilio), chained invocations (stripe.charges.create), client construction, and records exact file locations, line/column, SDK version, and content hash.
  - py_ast.py: Discovers module and attribute imports (import stripe, rom stripe import Charge, rom twilio.rest import Client), client instantiation (Client(sid, token).messages.create()), positional and keyword arguments.
  - Performance: The 
px resolve lock (M5-W302 / B154) bypasses locks once the cache is warm, executing test suites in ~230s down from >1200s without worker starvation.
- **Day-1 Partner Edge Case -- Internal Client Wrappers**:
  - *Scenario*: A partner wraps the SDK in an internal module (e.g. lib/stripe.ts exports export const stripe = new Stripe(process.env.STRIPE_KEY);, and application files import { stripe } from @/lib/stripe).
  - *Status*: Single-file AST indexing extracts call sites within the file where the SDK import or direct identifier usage is present. Deep inter-file alias analysis across arbitrarily nested custom wrapper modules is deliberately bounded at the static rung.
  - *Verdict*: **Keep as designed.** The API Dependency Graph 3-rung architecture (static -> 
esolved -> observed) was designed specifically for this: what cannot be statically bound across custom abstraction layers is captured honestly by runtime telemetry (observed rung) rather than fabricating uncertain static links.

### B. Vendor Adapters & Intake (src/sync/signals/**)

- **What works**:
  - Stripe (stripe.py) & Twilio (	wilio.py): Exact OpenAPI spec diffing via oasdiff across versions, mapping changes to breaking/non-breaking categories with path pointers and operation IDs.
  - Generated Spec Adapters (generated/adapter.py): Stainless / OpenAPI generator support with declarative observability declarations (NO_MANIFEST, NO_SPECIFICATION, ONE_DOCUMENT).
  - Intake Attempt Diagnostics (intake_attempt.py): Closed vocabulary (IntakeReasonCode) separating *never-asked* from *nothing-new*, and *clean-decline* from *fetch-failure*.
  - Detail Sanitization (B168 / M5-W310): Capped at 500 characters and scrubbed of local filesystem paths ([path]), preventing host environment leaks.
- **Day-1 Partner Edge Case -- Network & Rate Limits on Vendor Spec Endpoints**:
  - *Scenario*: GitHub API rate limits or vendor downtime during hourly intake scans.
  - *Status*: Classifies HTTP 403, 404, 429, 5xx into closed reason codes without crashing the scan or aborting customer runs.

### C. Zero-Remote Rehearsal Harness (src/sync/rehearse/**)

- **What works**:
  - Pinned corpus fixtures (urever, 	urbo, 
emix, ireship-server, irtual-lab) cached with digest verification.
  - Rehearsal runs write is_rehearsal=True to migration_outcome, and GraphStore.migration_outcomes() explicitly filters them out (WHERE NOT is_rehearsal), guaranteeing that synthetic rehearsal runs never contaminate Beta Gate 2 quality metrics (M5-W308).

---

## 3. What We Would Refuse to Ship Beta Without vs. What Stays Post-Beta

### Refuse to Ship Without (Completed):
1. **Intake detail sanitization & bounds (B168 / M5-W310)**: Absolute paths and unbounded vendor error bodies scrubbed on ingestion.
2. **Rehearsal metric isolation (M5-W308)**: Proof that zero-remote rehearsal rows do not pollute production gate metrics.
3. **Warm-cache indexer concurrency (M5-W302)**: No worker starvation during typecheck verification.

### Deliberately Post-Beta:
1. **Catalog Expansion (M11 Fan-in)**: Expanding from 2 coded vendors + Stainless generator to 20+ third-party vendor adapters stays post-beta.
2. **Whole-program deep symbol alias propagation**: Cross-file custom wrapper inference remains deferred; runtime telemetry (observed rung) covers wrapper call sites.

---

## 4. Conclusion & State

Lane D has zero remaining blockers for beta. Owned paths (src/sync/signals/**, src/sync/index/**, src/sync/rehearse/**) are clean, fully tested, and ready. Standing by for B7 acceptance execution or cross-lane coordination.

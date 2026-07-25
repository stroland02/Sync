# Sync — Positioning and the Open-Core Boundary

**Date:** 2026-07-25
**Status:** Decided. Supersedes the positioning section of the design document and the one-line open-core
statement in the README.
**Scope:** What Sync sells, what the claim is allowed to say before it is measured, and which layers are given
away under which license.

Two decisions are recorded here. They were made together because the second follows from the first: once the
binding is the product rather than the repair, the crown jewel moves, and the open-core line has to move with
it.

## Decision 1 — the binding is the product

Sync sells a live binding between a codebase and the third-party operations it depends on. The API Dependency
Graph is not an implementation detail that makes remediation possible; it is the thing customers pay for.

Repair remains in the product. It is a feature, it is expected, and as of mid-2026 it is available from Datadog
and GitHub as well (`2026-07-25-sync-competitive-position.md`). Sync ships it because a binding that cannot act
is a report, and because the repair is what proves the binding was correct. It is not what makes Sync
different.

**What this changes.** The remediation graph is demoted from spine to feature. Signal-source integrations —
Sentry, Datadog, deploy events — are promoted, because composing multiple signals is exactly what a binding
makes possible and what nothing else can do. Integrations stop being a late milestone and become the
demonstration of the thesis.

## Decision 2 — open core, with the line drawn around the binding engine

Confirmed: open core. Sync is built solo and self-funded, so developer adoption is the only distribution
available, and the license structure has to serve adoption everywhere it is not protecting the one asset that
takes a competitor more than a year to rebuild.

## The claim

Every shipped competitor is reactive by construction rather than by neglect. Datadog's Bits Code fires on Error
Tracking and APM findings, GitHub's agentic autofix on a CodeQL alert or a published advisory, Sentry's Seer on
a thrown exception. Each sits causally downstream of a failure, and none can move upstream without building a
binding, because a stack trace cannot report what a vendor is about to ship.

Sync's trigger is a vendor artifact — a specification diff, a changelog entry, an SDK release — which exists
before the first failed call. That is a property of where the trigger sits in the causal chain, not a framing
choice, and it is the whole of the differentiation.

**State the mechanism before the adjective.** "Adaptive" is the most worn word in the category and carries no
information on its own. The mechanism is that the binding is computed ahead of the event, so the trigger can be
a vendor's release instead of a customer's outage. The adjective is earned by that sentence, never asserted
before it.

**Do not claim Sync is never reactive.** It is not true, and it fails on first contact with a sharp buyer: two
of the three detectors are reactive by design, and vendor knowledge cannot be synthesized from telemetry —
someone has to publish it. The honest form is stronger than the overclaim, because it turns a hole into a
completeness argument:

> Adaptive where the vendor publishes. Reactive where nobody could have known. One graph does both, and nobody
> else has the adaptive half at all.

**Do not demonstrate this on Stripe.** Stripe confines breaking changes to two semiannual releases. "Stay ahead
of vendor change" lands weakly against a vendor that changes twice a year. GitHub's MCP server shipped breaking
changes in 18 of 37 release transitions over the same window
(`2026-07-25-sync-mcp-drift-measurement.md`). Demonstrate on a vendor that actually moves; keep Stripe as the
correctness ground truth it is genuinely good for.

## The strongest available claim, and it is currently unused

Autonomous pull requests merge at roughly a third overall, and at three-quarters or better when the change is
maintenance-shaped. Sync's output is maintenance-shaped by construction and verified before it is offered.

> We do not send you a patch. We send you a patch your own CI has already run green — without ever holding a
> secret of yours or executing your code.

No competitor that runs customer code in its own environment can make the second half of that sentence. It
belongs near the front of the pitch, not in an appendix.

## The pitch

One line:

> Sync binds every third-party call site in your codebase to the vendor operation behind it, so when a vendor
> ships a change your code adapts at publication instead of at breakage.

Long form:

> Existing agents wait for damage: an error thrown, a CVE published, an alert raised. Sync watches the APIs your
> code consumes and maintains a live binding between each call site and the vendor operation it depends on. When
> a vendor publishes a change, the affected lines are already known — so the fix arrives ahead of the outage,
> verified green by your own CI, without Sync ever holding a secret or executing your code. The binding is
> computed once per vendor and shared across every codebase that calls it, which is why it gets cheaper as it
> gets broader.

The last sentence is the one a strategic buyer responds to, because it says the economics improve with scale.

## Claims discipline

The cost argument is real and is not yet sayable.

The mechanism is sound: a vendor diff is computed once and fanned out to every affected customer, so detection
is O(1) in customer count rather than O(customers), and gross margin improves as the base grows. This is
already specified in the latency architecture.

But "low cost" without a number is the one line in this pitch a technical buyer can puncture in a single
meeting. The number comes from the migration corpus — cost per verified pull request, cost per abandoned
finding — and the corpus does not exist until M0 writes its first rows
(`2026-07-25-sync-migration-corpus.md`). **Ship the efficiency claim after the corpus can source it, not
before.** Until then the claim is that the architecture is O(1) per vendor, which is defensible because it is
structural.

## The open-core boundary

Four layers, three answers.

| Layer | What | License | Why |
|---|---|---|---|
| Schema | `VendorChange` kinds, `CallSite`, `Finding` — the vocabulary | Apache 2.0 | A schema wins only by becoming the default |
| Interface | Adapter protocols, reference adapters (Stripe, MCP) | Apache 2.0 | Coverage requires third-party authors; an interface is copyable anyway |
| Binding engine | Static index correlated against telemetry; the detectors | FSL-1.1-Apache-2.0 | The only asset that takes over a year to rebuild |
| Corpus and runtime | Outcome corpus, multi-tenant control plane | Closed | Not code; and it is what is being sold |

**The schema is given away hardest.** If Datadog, Sentry, or GitHub ever emit "this call site depends on this
vendor operation," it should be in Sync's vocabulary. A binding company that does not own the interchange
format is a tool; one that does is a standard. This costs nothing that was being kept.

**The binding engine is source-available, never permissive.** Source-available rather than closed for three
reasons that compound for a solo operator: enterprises reading the code that touches their repositories is the
practical substitute for the SOC 2 that is not affordable in year one; a solo closed-source binary requesting
repository write access is a hard sell that readable source materially softens; and the non-compete term still
prevents a hyperscaler shipping it as a service. Sentry's FSL is the precedent, and it converts to Apache 2.0
after two years, which keeps the promise credible.

**Permissive licensing of the binding engine is the one irreversible mistake available here.** Future versions
can always be closed; past ones can never be un-licensed.

## The public API-change feed

Publish a free, normalized, cross-vendor feed of API changes — vendor, operation, change kind, date, source.
The normalization work is already required for M0 and M1, so the marginal cost is small.

This is not generosity, it is an attack. FlareCanary, ShiftGraph, and Deprecatr AI sell this signal and only
this signal. Published free, their entire product becomes Sync's free tier. It does nothing for Datadog or
GitHub, because neither holds the binding needed to act on it.

The principle: **commoditize the layer you do not own, keep the one you do.** The signal was never the moat.

**The risk, stated honestly.** The feed also arms anyone willing to build their own binding — Datadog could
consume it and add the static-index half. That is a two-to-three year exposure rather than a six-month one, and
they would be building on Sync's vocabulary, which is a position rather than a loss. The trade is accepted
deliberately.

The OSV precedent supports it. Google normalized vulnerability data, gave it away, and commoditized that layer;
Snyk's database stopped being a differentiator. Google did not lose by publishing — it captured the schema
position and made the ecosystem speak its format.

## Sequencing

Publishing an interface freezes it. The design document already argues this for M3: designing the adapter
protocol against Stripe alone would encode Stripe's tidiness as a permanent assumption.

1. **Schema and change feed** — earliest and cheapest, and the only distribution a solo founder can buy.
2. **Reference adapters** — after MCP has proven the protocol generalizes past Stripe.
3. **Binding engine under FSL** — once it exists and works.
4. **Corpus and hosted runtime** — never.

Nothing is published before M0 proves the spine end to end.

## Two audiences, two first slides

"Why invest" and "why acquire" are different pitches from the same product. Solo, self-funded, and open core is
not a conventional venture story, but it is a strong strategic-acquirer story and a strong adoption story. To a
strategic buyer, Sync is the layer that makes their agents' output land on the right lines. To a fund, Sync is
an adoption curve on a free feed. The product does not change; the first slide does.

## Open items

- The FSL non-compete term (two years is the Sentry default) is not yet chosen deliberately.
- The feed's data license — CC0 versus ODbL — is undecided. ODbL's share-alike would keep derived feeds open;
  CC0 maximizes adoption. Adoption is probably worth more, but this has not been argued out.
- Whether the graph itself is exposed as a queryable API surface, which is the natural product form once the
  binding rather than the repair is what is being sold.

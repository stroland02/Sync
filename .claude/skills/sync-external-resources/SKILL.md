---
name: sync-external-resources
description: Use when starting a Sync milestone, choosing a vendor to write an adapter for, deciding build-vs-buy on hosting or CI, or evaluating whether an external library is worth a dependency. Holds the milestone-attached verdict on nine reference repositories so they are consulted when relevant rather than all at once.
---

# External resources, attached to the milestone that needs them

Nine repositories were nominated as background reading. Loading all nine at every milestone is
the failure this file exists to prevent — most are irrelevant to an API-binding engine most of
the time, and a reference consulted at the wrong moment is a distraction wearing the costume of
diligence.

Each entry carries a **verdict**, the **milestone** that should consult it, and **the specific
question it answers**. Read only the row whose milestone is in hand.

Verdicts mean:

- **LOAD-BEARING** — a real input to a design decision. Read it before deciding.
- **REFERENCE** — consult when its specific question comes up. Do not read speculatively.
- **SKIP** — does not serve this project. Recorded with the reason so it is not re-litigated.

## Verified — read from the primary source on 2026-07-27

### `pbakaus/impeccable` — REFERENCE, M1

A design-guidance system for AI coding agents: a skill exposing 23 subcommands, roughly 60
deterministic detector rules, a browser extension for live visual iteration, and support for
13-plus agent tools. Apache 2.0.

**Its subject matter is irrelevant here.** Sync has no frontend. Do not read it for design
advice.

**Its architecture is the reason it stays on the list.** Deterministic detectors carry the load;
the model handles what detectors cannot express; the whole thing ships as one invocable skill
that many different agent tools can consume. That is the same split Sync adopted from Open Code
Review, and it is the shape the MCP graph surface is trying to be.

*The question it answers:* when packaging the graph surface, how does a tool present a
deterministic engine to many agent clients without becoming a chat interface?

*(Star count reported by the fetch looked like a misread of the page and is not recorded.)*

### `VectifyAI/PageIndex` — SKIP for specs, STEAL-THE-IDEA at M2

MIT. Builds an LLM-generated table-of-contents tree over a document, then resolves queries by
LLM tree search rather than vector similarity. PDF-oriented intake, multi-provider through
LiteLLM, default `gpt-4o-2024-11-20`. Claims 98.7% on FinanceBench — self-reported, no named
baseline, and the per-query model-call count is not disclosed.

**Wrong tool for OpenAPI specs, and the reason is worth keeping so this is not reopened.** An
OpenAPI document is already a machine-readable tree with exact addresses. Sync already diffs it
authoritatively with oasdiff and already stores JSON Pointers. Approximate, LLM-mediated
navigation over a document that supports exact addressing is strictly worse *and* costs model
calls per query.

**Right shape for vendor changelogs and migration guides.** Those are prose: unstructured, no
pointer, genuinely needing reasoning-based retrieval. That is an M2 concern, and the thing to
take is the tree schema and the node-summary prompt — not the package, whose PDF intake does not
match the input.

*The question it answers:* at M2, how should the changelog enrichment chain navigate a long
migration guide it cannot address exactly?

## Unverified — the research pass that would have settled these did not complete

A ten-agent fan-out was launched on 2026-07-27 and every agent died on the session limit. These
six were never fetched. **Each carries the exact question to answer, so whoever picks this up
resolves it rather than re-deriving what to ask.** Do not treat the guessed milestone as
settled — it is a placeholder until the repo is actually read.

### `public-apis/public-apis` — largely superseded, likely SKIP

The question this repo was on the list to answer — *which vendors should Sync write adapters
for?* — is now answered better elsewhere. `docs/superpowers/specs/2026-07-27-sync-adapter-targets.md`
carries a verified target list, and the criterion turned out not to be popularity at all but
**bindability**: a vendor is only a target if it publishes a machine-readable, versioned spec.
A catalogue ranked by popularity cannot answer that, and the spec's discovery mechanism —
reading `.stats.yml` from Stainless-generated SDKs — finds bindable vendors directly.

*Residual question, if anyone still wants it:* does it carry a machine-readable index rather
than a markdown table, and do entries link to OpenAPI specs? If not, mark SKIP outright.
**Check the license before deriving anything from it** — a share-alike list could contaminate a
derived artifact, and Sync is open-core with FSL on the engine.

### `ripienaar/free-for-dev` — provisionally M4, likely the most immediately useful of the six

*Question:* what are the **current** free-tier limits for Postgres 16 hosting (storage, row, and
connection caps, and which providers sleep or expire an idle database), CI minutes on public and
private repositories, static CDN hosting for the signed change feed, Sentry's free tier, and
scheduled jobs for adapter runs? Verify each against the provider's own pricing page — this list
goes stale fast, and a wrong number costs real money for a self-funded project.

### `awesome-selfhosted/awesome-selfhosted` — provisionally M4

*Question:* does anything here change the build-versus-buy calculus for the hosted control
plane? Name specific tools with their actual resource requirements, not categories. **Check the
license** — this list has historically been share-alike, which matters if any of it is
redistributed.

### `binhnguyennus/awesome-scalability` — provisionally M4, possibly SKIP

*Question:* is a scalability case-study list premature by two milestones for a single-tenant
system that has explicitly refused OTLP ingestion? Or is there a specific case study on API
versioning at scale, schema evolution, or large-scale codemod worth reading now? Name entries or
say plainly that it is premature.

### `trimstray/the-book-of-secret-knowledge` — provisionally M1, likely REFERENCE

*Question:* which single section applies to the credential-free, network-egress-free
verification sandbox — the one hard security surface in the architecture? If the answer is "none
specifically," mark it SKIP rather than keeping it as ambient reading.

### `iamgini/roadmap.sh` — provisionally SKIP

*Question:* what is this fork versus upstream `kamranahmedse/roadmap.sh`, and does it differ at
all? If it is an unmodified stale fork, record SKIP and point at upstream. Learning roadmaps are
not a design input for this project either way; the burden is on the entry to justify staying.

## How to close the gaps

The research script is saved and resumable, and unchanged agents replay from cache:

```
Workflow({scriptPath: "<session>/workflows/scripts/sync-knowledge-substrate-research-wf_1bd1627d-0a4.js",
          resumeFromRunId: "wf_1bd1627d-0a4"})
```

When a row is resolved, replace its question with the answer and move it into the verified
section. A row that stays a question for two milestones should become SKIP — a reference nobody
needed twice is not a reference.

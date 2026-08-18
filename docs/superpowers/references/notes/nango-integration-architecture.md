# Reference read: an integrations platform at catalog scale

**Read 2026-08-18 from a shallow clone at `..\nango-reference` (kept outside this repository).
License: Elastic License 2.0 — source-available, not open source, and incompatible with this
project's Apache-2.0. Nothing may be copied; everything below is architecture read for its
ideas, under `interface-originality.md`'s standing rule: conventions of the form are learnable,
the rendering is not.**

A 38-package TypeScript monorepo serving ~400+ API integrations. Five mechanisms carry the
scale, and each is summarised with what it would and would not buy Sync.

## 1. The declarative provider catalog — one YAML entry is one integration

A single 26,006-line `providers.yaml`, schema-validated, one entry per provider:

- `auth_mode` from a closed set of ~12 (API_KEY, BASIC, OAUTH1, OAUTH2, OAUTH2_CC, JWT,
  TWO_STEP, TBA, APP, NONE …) — every mode's form is derived, not hand-built.
- `proxy.base_url` with `${connectionConfig.x}` / `${apiKey}` interpolation.
- **A credential verification probe per provider**: method + endpoint that proves a credential
  works before anything else is attempted.
- `connection_config` and `credentials` as *typed form schemas* — title, description, pattern,
  example, enum, order, secret flag, and a deep link into the provider's own docs per field.
  The connect UI converts these to zod resolvers and renders the form; nobody writes a form
  per provider.
- `categories` for the catalog grid; docs links per provider.

**What this maps to here.** `generated-vendors.yaml` is the same philosophy (config entry, not
code, per vendor) applied to spec *watching* rather than auth. What is adoptable on top:
a per-adapter `connection_config`-style schema (what does this vendor's staging need — Twilio's
product list is exactly such a field), rendered by one schema-driven field renderer in the
Adapters settings panel; a verification probe per vendor for the Setup checklist; categories on
vendor cards.

## 2. A Postgres task scheduler with heartbeats — the liveness answer

`packages/scheduler`: tasks in Postgres with a six-state closed lifecycle — CREATED, STARTED,
SUCCEEDED, FAILED, **EXPIRED**, CANCELLED — and three distinct timeout classes per task:
created→started, started→completed, and **heartbeat** (`lastHeartbeatAt`, refreshed by the
worker while it runs). Three daemons: scheduling (due tasks), expiring (missed heartbeats →
EXPIRED, a recorded transition), cleaning. Group concurrency by `groupKey` +
`groupMaxConcurrency`; retries carry a `retryKey` for dedup; uuidv7 ids for time-ordered keys.

**What this maps to here, and it is the single most valuable idea in the read.** Sync's runs
cannot distinguish parked-on-the-customer's-CI from dead — the console's protected staleness
sentence exists *because* the checkpointer holds no heartbeat. `CLAUDE.md`'s own dot rule says
a status dot requires "a stored state transition inside one closed lifecycle": a heartbeat
column written by the remediation runner plus an expiring sweep is exactly that mechanism.
Adopting the *concept* (never the code) turns EXPIRED into a recorded fact and makes a
liveness claim honest for the first time. B194 carries it.

## 3. The records store — synced data with a lifecycle

`packages/records`: cursor-based pagination over synced records, merge/unique-key dedup, a
`generation` column for windowed re-syncs, a counts cache table with `size_bytes`, `pruned_at`
lifecycle, and one migration file per schema change. Relevant to `observed_*` tables only when
telemetry volume becomes real; noted, not urgent.

## 4. UI patterns worth taking as conventions

- **Row → wide drawer, with the drawer state in the URL.** The operations table opens a
  right-side sheet (~1000px) whose deep link is copyable from inside the drawer — an operator
  can hand a colleague the exact drawer they are looking at. Sync already keeps filters and
  offsets in the URL; extending that discipline to drawers is the same reasoning.
- **A closed tag vocabulary as components** (level, operation kind, status, provider) rather
  than ad-hoc chips per screen.
- **Faceted search over operations** with a searchable multi-select per facet — the filter
  rail's counts idea, at their scale.
- **A standalone connect micro-app** (`connect-ui`) embeddable via a window-event bridge, with
  per-auth-mode base form schemas plus per-provider schema overlays. The schema-driven form is
  the part worth having; the embed bridge is a hosted-product concern Sync does not share.
- **A design-system package with a story per component.** Noted for post-beta; `DESIGN.md`
  already carries the token contract that matters more.

## 5. Separations that confirm Sync's own, and two deliberately not taken

Their `persist` (script output ingestion) beside `server` (API) mirrors Sync's read-only API
versus pipeline-writes split. Their `fleet`/`runner`/`sandbox` triple is the shape B97's
containment work already points at. **Not taken:** `keystore`/`kms` — Sync's "we never hold
customer secrets" is unqualified and holding credentials is their product's job, not ours; and
their OAuth broker generally — Sync authenticates through the operator's own `gh`, which is a
smaller and honest surface for a local-first product.

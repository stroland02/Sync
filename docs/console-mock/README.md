# The operator console, mocked ahead of the build — 2026-08-08

Ten full-page screens of the operator console, drawn in HTML/CSS/JS in
[Claude Design](https://claude.ai/design) and exported here so the implementation has something to
be measured against rather than argued about from memory.

**This is a prototype, not production code.** Nothing in it ships. It is the target the React
console is built toward, and the only thing in this repository that is allowed to show a screen
that does not exist yet.

| | |
|---|---|
| **Live** | https://claude.ai/code/artifact/f321ac84-32d5-4181-a680-8bf2df671247 |
| **Source** | `index.html` (the design tool's `Sync Console.dc.html`), `support.js` (its runtime) |
| **Stills** | `screens/` — twelve captures, conditions below |
| **Tour** | `demo.mp4`, and `demo.gif` for the README |
| **Plan that consumes it** | `../superpowers/plans/2026-08-08-console-mock-to-build.md` |

## Why this one, and not the other one

The export carried two mocks. This is the first.

`Sync Console v2.dc.html` was built on **Industry**, a light blueprint design system attached to the
design brief. It addresses every colour through `var(--color-bg)`-style indirection into that
system's own stylesheet. `.claude/rules/console-surface.md` records dark-only on the owner's
explicit instruction and names `DESIGN.md` as the authority for every visual value, so v2 would have
to be re-themed before a single value in it could be trusted.

This one resolves against **our** contract. Its literal OKLCH values are the ones
`web/src/index.css` already declares:

| Mock | `web/src/index.css` |
|---|---|
| `oklch(0.19 0.0025 159)` | `--color-background` |
| `oklch(0.215 0.0025 159)` | `--color-card` |
| `oklch(0.2275 0.0025 159)` | `--color-popover` |
| `oklch(0.24 0.0025 159)` | `--color-secondary` |
| `oklch(0.95 0.00275 159)` | `--color-foreground` |

So a value read off this mock is a value already in the token contract, and a value that is *not*
is a deliberate proposal. That distinction is the whole reason this file is worth committing, and
v2 cannot make it.

v2 is not in this directory. It is in the export bundle if a light theme is ever revisited.

## What it already gets right, and what that costs a reader

The mock was drawn against the repository rather than against a screenshot, so three things
transfer without a translation step:

- **The vocabulary is ours, verbatim** — the six `AREAS`, the nine graph levels, the five rungs
  (`static`, `resolved`, `observed`, `unresolved`, `unattributed`), the eight workflow nodes and
  their standings, and the run outcomes.
- **The honesty discipline is applied, not decorated.** No composite score, no health figure, no
  traffic light, no green dot, no liveness pulse. Every status colour ships with a glyph **and** a
  word, so the colour is never load-bearing. Absence, staleness and never-measured each get their
  own sentence.
- **A change unit is the fleet's grain** — findings sharing a vendor change against one repository
  set, expandable to call sites. That is a product decision the mock makes on screen, and
  `plans/2026-08-08-console-mock-to-build.md` Decision 1 is where it gets ruled on rather than
  absorbed silently.

What it does **not** carry is any claim to be right. It is one person's drawing of ten screens, and
several of its facts are invented fixtures — `acme/payments-api`, pull request `#4127`, the
1.2M-span OTel window. Read a number here as a layout weight, never as a measurement.

## Running it

It needs a server; `file://` will not do, and the runtime pulls React, ReactDOM and Babel from
`unpkg.com` on first paint.

```bash
cd docs/console-mock && python -m http.server 8901
# then open http://127.0.0.1:8901/
```

Offline, override the three CDN URLs before `support.js` runs — the runtime checks
`window.__resources[url]` and prefers a local path when it finds one. That is the hook the capture
harness below used; nothing in this directory is modified to make it work.

## Capture conditions, because a screenshot without them is not evidence

- **1440×900, `deviceScaleFactor: 1`**, the mock's own declared preview size (`$preview` in its
  props block). No device-metrics override was applied.
- **Viewport, not full page** — these are captures of a fixed-height application shell whose panes
  scroll internally, so a full-page capture would describe a layout the mock never renders.
- Served from `docs/console-mock/` over `http://127.0.0.1`, with React 18.3.1, ReactDOM 18.3.1 and
  Babel 7.29.0 pinned to local copies through `window.__resources` rather than fetched from
  `unpkg.com`, so the capture does not depend on a CDN that may serve something else later.
- Captured 2026-08-08 from the bundle as committed here.

| File | Screen | Level | Route it is drawn against |
|---|---|---|---|
| `01-fleet.png` | Fleet | Fleet | `/` |
| `02-codebase.png` | Codebase | Codebase | `/repositories/:repoId` |
| `03-vendor.png` | API service | API Services | `/vendors/:vendorId` |
| `04-signals.png` | Signals | Signals | `/repositories/:repoId/observed` |
| `05-binding-surface.png` | Binding surface | Binding surface | `/bindings/…/operations/:operationId` |
| `06-finding.png` | Finding | Finding | `/findings/:findingId` |
| `07-workflow.png` | Solution workflow | Solution Workflow | `/findings/:findingId/workflow` |
| `08-pull-request.png` | Pull request | Pull Request | `…/workflow/pull-request` |
| `09-detectors.png` | Detector attribution | Errors & Incidents | `/detectors` |
| `10-settings.png` | Settings & adapters | **Not a level** | `/settings` |
| `11-drawer.png` | The call-site drawer, over Fleet | — | — |
| `12-palette.png` | The command palette | — | — |

Two of these are not levels and must not be read as ones. **Settings & adapters** is a destination;
the mock's own sidebar says so in as many words. The **drawer** and the **palette** are surfaces
that open over a level rather than replacing it.

## What binds anyone implementing from this

The mock is a proposal. Three authorities outrank it, and where they disagree the mock loses:

1. **`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445`** for the
   hierarchy. The mock groups nine levels under six areas; an area is not a level, and if the mock
   ever reads as inventing one, the specification is what ships.
2. **`DESIGN.md`** for every colour, size, space and elevation, with the arithmetic that proves each
   contrast against a 5.05:1 floor. A mock value that is not in `DESIGN.md` gets added there with
   its arithmetic, or it does not get built.
3. **`.claude/rules/console-surface.md`** and the twenty-four honesty sentences. The mock restates
   several of them in its own words. Restyling one is allowed; deleting, shortening or collapsing
   one behind a disclosure is not, and the mock's wording is not a licence to shorten the
   shipped wording.

`.claude/rules/interface-originality.md` is satisfied by construction here — this is our own
drawing of our own product, not a reading of anybody's screenshot — but the rule still governs
everything built from it.

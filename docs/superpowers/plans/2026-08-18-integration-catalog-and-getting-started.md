# The integration catalog, and the getting-started journey that ends in a closed loop

**Owner directive, 2026-08-18 (evening).** Two work streams, both in the packaging/deployment
lane, both aimed at tomorrow's ship, with the console's UI work running in a parallel lane that
this plan deliberately does not touch:

1. **A getting-started workflow** that ties together everything the loop needs — better than the
   pieces that exist today.
2. **An integration catalog in the shape Nango uses** — per-integration pages, a machine-readable
   provider registry, an `llms.txt` docs index — so that when a platform is detected in a
   customer's codebase, Sync recognizes it instantly and the documentation reads as a product.
   Internal documentation now; website later builds from the same files.

## The licensing ruling, first, because it fences everything else

**Nango's repository is Elastic License 2.0.** Measured 2026-08-18 via `gh api`, not assumed —
the owner described it as open source, which is true in the colloquial sense and insufficient in
the legal one: ELv2 is source-available with a hosted-service restriction, and this repository is
Apache-2.0. Vendoring their `providers.yaml` or their markdown wholesale would embed ELv2
expression in an Apache-2.0 tree.

So the Supabase precedent does **not** extend to Nango. What transfers instead, under
`.claude/rules/interface-originality.md`:

- **The shape.** A provider registry as data; a per-integration page with quickstart, guides,
  official-docs link, and a capability table with source links; an `llms.txt` index for agents.
  Conventions of the documentation form, learnable from anything.
- **Facts about third parties.** `stripe` is Stripe's npm package; OpenAI's docs live at
  platform.openai.com. Facts are nobody's property. Every entry we write is verified against the
  vendor itself — the standard `generated-vendors.yaml` already holds ("every entry confirmed by
  fetching the path").
- **Nothing else.** No copied YAML, no copied prose, no copied step order. If an entry cannot be
  written without looking at Nango's file, it is not written.

## What exists that this builds on (measured against the tree)

- `sync.signals.registry.registered_adapters()` — every registered vendor with kind
  (`coded`/`generated`/`mcp`) and source. 15 generated vendors + stripe + twilio + MCP servers.
- `vendor_sdk_bindings()` — package→vendor mapping per language, the thing that lets INDEX say a
  repository depends on a vendor at all.
- `sync intake` — reports which of a repository's declared dependencies Sync can watch.
- `sync index --repo` — offline call-site indexing (landed today).
- The doorbell (`npm start`) — routes, freshens, converges schema, installs everything.
- The console's Setup panel — six prerequisites probed, remote stored (other lane's, cited only).
- `docs/writing-a-vendor-adapter.md` — the "missing an API? add it yourself" story.

## Deliverables

### D1 — the vendor knowledge base (`vendor-catalog.yaml`)

Our own schema, our own words. One entry per recognized platform, whether or not an adapter
exists yet:

```yaml
- vendor_id: openai            # joins registry ids where an adapter exists
  display_name: OpenAI
  categories: [ai]
  docs_url: https://platform.openai.com/docs
  packages:                    # what a customer's lockfile names
    npm: [openai]
    pypi: [openai]
  status: supported            # supported | recognized
```

`status: supported` is **derived, never declared**: an entry is supported iff its `vendor_id` is
in `registered_adapters()`. `recognized` means INDEX/intake can name the dependency and the
catalog can say "not watched yet, here is how to add it" — honest absence instead of silence.

### D2 — the generated catalog docs (`docs/integrations/catalog/`)

`scripts/build_integration_docs.py` reads the registry + knowledge base and writes:
- `docs/integrations/catalog/index.md` — the catalog table: vendor, kind, what is watched,
  status. Cannot list an integration the code does not serve, because it is generated from the
  same call the CLI resolves vendors with.
- `docs/integrations/catalog/<vendor>.md` — per-vendor page: quickstart (real commands),
  what Sync watches (by adapter kind), **what Sync does not watch** (the honesty section),
  package bindings, official docs link, and "add what's missing" pointing at
  `writing-a-vendor-adapter.md`.
- `docs/llms.txt` — the docs index, one line per page, for agents and the future website.

A drift gate in `tests/test_integration_catalog.py` regenerates and diffs against the committed
files — the API/type-contract pattern — so the catalog cannot silently lag the registry.

### D3 — the getting-started journey (`docs/getting-started.md`)

One page, the whole loop, in order: one command up → index your repository → pick a vendor →
first findings on the console → what the remediation loop needs (gh auth, model key) → what the
meter cannot tell yet and why that is stated rather than painted green. Links from README.

### D4 — intake recognition widening (follow-up, needs D1)

`sync intake` consults the knowledge base so a dependency with a catalog entry reports
`recognized` with its display name and docs link instead of unknown. Follow-up because intake has
its own tests and grain; not blocking tomorrow.

## What this plan does not do

- No copying from ELv2 sources (ruling above).
- No console/UI work — the parallel lane owns every screen.
- No 900-vendor sweep tonight. The knowledge base ships seeded with the vendors the registry
  already serves plus a hand-verified popular set; breadth is configuration lines from there,
  which is the same scaling argument `generated-vendors.yaml` records.

## Ledger

- **2026-08-18** Ruling: Nango material is shape-and-facts only; ELv2 forecloses vendoring.
  Reversible only by the owner accepting ELv2 terms explicitly, and even then attribution and
  license separation would be required.
- **2026-08-18** Ruling: `status` in the knowledge base is derived from the registry at
  generation time, never written by hand — two lists that can disagree is the defect
  `registry.py` already names.

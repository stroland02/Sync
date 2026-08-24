# Uniform vendor tier, the Precedent store, and finishing the console

Two bodies of work the owner has ruled on, plus the hygiene each has already surfaced. Written
down because the sequence lived only in a session transcript, which
`.claude/rules/autonomous-development.md` forbids: *a session that stops mid-plan should be
resumable without its transcript.*

Status is measured, not remembered. Every count below was taken on 2026-08-23 against
`chore/clear-the-ground` at `85bdae83`.

## Ledger of rulings already made

| # | Ruling | Against | Standing |
|---|---|---|---|
| 1 | Full refactor: no hand-written adapters. Direct-spec tier, and both symbol modules folded into `EXTRACTORS` | Keeping `StripeAdapter`/`TwilioAdapter` and documenting them as the exception | Owner, explicit |
| 2 | The proto-RAG is renamed **Precedent** | `corpus` | Owner, explicit |
| 3 | Vendor acquisition stays model-free and unauthenticated; only Remediate uses a model | Adding a research model to Signal | Owner, confirmed |
| 4 | shadcn is the single primitive substrate, retired phased with the chassis | Big-bang substitution | Owner, explicit |
| 5 | Thin core governs guard policy: honesty and accessibility stay machine-enforced; aesthetic and structural guards retire | Keeping every guard | Owner, explicit |
| 6 | Console is terminal density, dark-only, one page skeleton on every screen | Comfortable density | Owner, explicit |
| 7 | `RouteEntry.question` is deleted entirely; the palette shows label + path grouped by workflow stage | Keeping it for the palette | Owner, explicit |
| 8 | The API stays read-only, but configuration writes are not the graph | Read-only without qualification | Owner, explicit |

## Track A -- the vendor tier becomes uniform

The owner's instruction: *"lets make sure all api follow the vendor tier and remove the HAND
WRITTEN, WE WANT THIS UNIFORM ACROSS THE BOARD."*

Today there are three registration routes and two of them are hand-written. `_BUILDERS` and
`_CODED_ADAPTERS` in `src/sync/signals/registry.py:497-516` name exactly `stripe` and `twilio`;
`GeneratedSpecAdapter` serves the sixteen configured rows; `McpServerAdapter` serves watched
servers. The end state is that stripe and twilio are configuration rows like every other vendor,
and their symbol rules are extractor modules selected the way the four generator rules are.

### The sequence, and how it was chosen

Three independent designs were produced -- minimum-diff, extractor-spine, and risk-first -- and
all three converged on the same architecture, which is the strongest signal available that it is
the right one. The adversarial judge panel and the completeness critic never ran: they died on an
account limit. **The adjudication below was therefore done by hand against the three surviving
designs**, and that is worth stating rather than implying a panel confirmed it.

**Risk-first wins the sequence**, because it alone found the constraint that governs everything:
`vendor-cache/stripe/symbols.json` is digest-pinned at `5f71dcd3bec1302cf70cba56bc9ebf043b38a1727acb43cee9e20fa08ead6be7`
in `benchmark/corpus/symbol_map.yaml:48` and asserted in the default suite by
`test_the_repository_ships_a_baked_stripe_cache_that_matches_its_pin`. **The symbol-map JSON is
the contract, not the Python function** -- both rules may move only if not one number changes, and
the cache must not be rebaked inside this sequence.

Four live claims were verified independently before adopting them:

| Claim | Measured |
|---|---|
| Stripe's spec needs no `gh` subprocess | `raw.githubusercontent.com/stripe/openapi/v2330/openapi/spec3.json` -> **200, 7,866,866 bytes**, unauthenticated |
| OpenAI's spec moved rather than vanished | `openai-python/v3.3.1/api_reference/openapi.transformed.yml` -> **200, 2,868,834 bytes** |
| Mistral has a cheap trigger even unfetchable | `.speakeasy/workflow.lock` -> **200, 4,329 bytes**, unauthenticated |
| The digest pin is real | `benchmark/corpus/symbol_map.yaml:48` |

**Two traps the designs found that a careless fix would walk into.** Prefixing `https://` onto
Mistral's registry reference returns **200 with a 4,848-byte HTML page** -- `_spec` would cache
that as a specification and oasdiff would diff it against its identical twin and report clean.
And registering OpenAI's `.castiron.stats.yml` as a Stainless manifest would make
`SpecSource.generator == "stainless"` false for a repository whose own commit is titled *remove
Stainless attribution and infrastructure* -- and that string selects the extraction rule, so
symbols would dispatch to the wrong reader with every test still green.

| # | Commit | State |
|---|---|---|
| A1 | One operation resolves to one name through both entry points | **landed `a568afc1`** |
| A2 | A reference we cannot resolve is reported as that, not as absent (mistral) | **landed `f1eb6e91`** |
| A3 | Pin what both symbol rules produce, before anything moves | **landed `01b883c7`** |
| A4 | The packages are named for what they hold | **deferred to after A13** |
| A5 | The rule contract is checked where a rule registers | next |
| A6 | The tier resolves symbols from a staged map, not only a checkout | |
| A7 | Every registered vendor's bindings come from its row | |
| A8 | A row may name its specification instead of discovering one | |
| A9 | OpenAI's row names the specification it actually publishes | |
| A10 | A row may name several documents (twilio) | |
| A11 | A row declares which oasdiff kinds are noise | |
| A12 | Stripe is a row; the hand-written adapter is deleted | |
| A13 | Twilio is a row; the registry names no vendor at all | |
| A14 | A stale row is found by a check, not by a person | |

### Two rulings against the adjudicated sequence, 2026-08-23

**A4, the package rename, moves to the end.** Measured: 73 files reference `sync.signals.generated`,
and the rename delivers no capability. Two reasons to do it last rather than fourth. A package can
only be named correctly once you know what it holds -- today it holds four generator rules, and
after A12 and A13 it holds six rules of two kinds -- so renaming now names it for a state that does
not exist yet. And 73 files of churn ahead of the semantic work maximises the conflict surface with
the other sessions pushing to this repository. What the later commits actually need from A4 is not
the name but the contract, which is A5. Reversible: the rename is mechanical whenever it happens.

**A5 narrows to the structural check alone.** The original form had each rule declare `RULE`, `INPUT`
and `LANGUAGES`. `INPUT` and `LANGUAGES` have no reader until a specification-reading rule registers,
and `CLAUDE.md` is explicit that an abstraction for an anticipated second caller is debt with no
asset behind it -- so those two fields arrive with the commit that reads them, and `GENERATOR` keeps
its name until a rule that is not a generator's makes `RULE` the truer word. What is left is real
today: the contract is `GENERATOR`, `extract_symbols` and `report_extraction`, and `EXTRACTORS`
touches only the first, so a module missing either function registers successfully and fails much
later inside `_extracted_symbols`.

### Two live defects Track A must absorb

Found by running `scripts/demo_signal_chain.py --all` (`CI-W569`). End-to-end coverage is **6 of
16** configured vendors, not sixteen.

- **`openai` is a stale row.** `.stats.yml` is 404 at `openai/openai-python`, confirmed through
  `raw.githubusercontent.com` and authenticated `gh`. The most-called vendor in the corpus is
  watched by a row pointing at nothing.
- **`mistral` is a third state the model does not carry.** Its manifest is genuine and names
  `registry.speakeasyapi.dev/...` references rather than URLs. `parse_manifest` returns `None`,
  which the caller cannot tell apart from Cloudflare, a vendor that genuinely publishes no
  specification. `schema.sql` argues that absent and believed present is worse than absent; this
  is that shape exactly.

## Track B -- Precedent

The vendor knowledge base the patch agent consults when resolving a finding, under the owner's
constraint: *we must validate that what we reference is correct, because we will not cite false
information.*

- **B1. Rename `corpus` to Precedent.** 292 files carry the word, including `sync/core/corpus.py`
  and the routed address `/repositories/:repoId/corpus`. Mechanical but wide; it wants its own
  commit and no other change riding along.
- **B2. Operation-scoped slices pinned to a spec hash.** A finding names an operation; the agent
  should receive that operation's slice of the specification and not two megabytes of YAML.
  Anthropic's document is 2,015,896 bytes across 96 paths and 144 operations.
- **B3. The evidence rung.** Every fact handed to the agent carries where it came from and at which
  spec hash, so a citation is checkable rather than plausible. This is the part the owner's
  constraint actually names.
- **B4. Changelog acquisition.** Specifications say what changed structurally; changelogs say what
  the vendor *meant*. Same honesty rule applies -- unattributed prose is worse than none.

## Track C -- finishing the console

- **C1.** `/repositories/:repoId/vendors/:vendorId` is the last `PENDING` entry in
  `web/src/layouts/screen-skeleton.test.tsx`. Twenty of twenty-one screens are on `ScreenFrame`.
- **C2.** Delete `RouteEntry.question`: 22 route entries, three consumers (`App.tsx:66,77`,
  `workflow-grid.tsx:58`, `page-header.tsx`), two tests (`routes-question.test.ts`,
  `page-header.test.tsx`).
- **C3.** Delete `PageHeader` (10 files) and `UnknownRoute` (22 files), both superseded by the
  four-band skeleton.
- **C4.** shadcn catalogue migration. 24 primitives are in `web/src/components/ui/`; the remaining
  bespoke components move onto them, phased with the chassis per ruling 4.
- **C5.** Token re-derivation. 143 custom properties in `web/src/index.css`, to be re-derived once
  composition is settled -- the owner sequenced composition first, tokens second.
- **C6.** Deferred content restructuring: `WorkflowPage`'s disabled controls become prose;
  `BindingSurfacePage` gets no exemption.
- **C7.** Terminal maximum-density pass across the migrated screens.

The console typechecks green today (`npx tsc -b`, exit 0).

## Track D -- hygiene these two tracks surfaced

- **D1.** `CI-W569` landed: the acquisition chain is runnable.
- **D2.** `CI-W570` landed: the decode census described a method `CI-W565` renamed.
- **D3.** `CLAUDE.md` prescribes `uv run pytest tests/ -q -n0` as the gate. Measured, that is
  23m54s where the parallel form reaches an identical verdict in 3m56s. Either the prescription or
  the measurement should change; a gate nobody runs because it costs a coffee break is a gate that
  decays.
- **D4.** A fresh worktree fails four tests for environment rather than for code: `tools/oasdiff.exe`
  and `.cache/corpus/` are both gitignored and absent. Four failures that look like defects and are
  not is exactly the noise that trains a reader to skim a red suite. Wants a bootstrap check that
  says which is missing.

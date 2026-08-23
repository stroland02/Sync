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

The detailed commit sequence is being derived by a design run and lands in this file when it does.
The shape is fixed: a source tier that knows how to *acquire* a document, an extractor that knows
how to *read* one, and both halves selected by data.

**A1 is applied and green but uncommitted** -- `ExtractedOperation` widened with `operation_id`,
`service_id` and `languages`, all optional, plus the `adapter.py` changes that honour them and two
tests in `tests/test_extracted_symbols.py`.

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

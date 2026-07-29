# Sync — The Deprecation Signal

**Date:** 2026-07-28
**Status:** Built, and both halves run. `src/sync/cli.py` fetches both vendor pages
(`DEPRECATION_SOURCES`, line 82), parses the parameter table, indexes model literals via
`index_operation_literals`, and constructs `ParameterDeprecationDetector` in its detector suite
(line 698). The model-retirement half is now wired too: `_model_deprecations` (line 577)
constructs a `DeprecationAdapter` per source at line 614 and collects its `VendorChange` rows,
so a retired model becomes a change `LiteralSwapRemediator` can act on. One vendor failing costs
that vendor's changes and is printed rather than swallowed, because an empty answer is
indistinguishable from a healthy vendor with nothing deprecated.
**Scope:** Vendor deprecation tables as a signal source, and the tier-0 path that repairs them
without a model call. The first end-to-end feature Sync has that costs nothing per finding.

## Why this signal is different

Every other detector answers *is this broken?* This one answers *when does this break?* — and a
date can be scheduled, which a severity cannot.

Three properties make it the strongest unclaimed signal in the domain, and the vendors document
the gap themselves.

**Nobody binds it.** Anthropic's published audit procedure is to open the Console, export a CSV,
and read usage by API key and model. OpenAI publishes shutdown dates in tables. Both tell a team
*that* it uses a dying model. Neither can say *which line of code holds the string*, because
neither has an index of the customer's source. That is exactly the binding half Sync exists to
supply.

**A type checker is structurally blind to it.** Anthropic's own note on deprecated parameters:
they *"remain in the SDK request types so existing code continues to type-check, but their
behavior changes per model."* `tsc` passes; the vendor returns 400. This repository hit that bug
itself — `CLAUDE.md` records `temperature`, `top_p` and `budget_tokens` returning HTTP 400 — so
the argument for a binding graph is written in the project's own scar tissue rather than
asserted.

**The repair is the most mechanical migration that exists.** One string literal becomes another,
and the vendor names the replacement. No judgement, no model, no diff to review beyond one line.

## The path, end to end

Five stages, none of which spends a token.

| Stage | Module | What it does |
|---|---|---|
| SIGNAL | `sync.signals.deprecations.adapter` | Fetches the vendor page, caches it, parses it |
| — | `sync.signals.deprecations.catalogue` | Turns published tables into `ModelDeprecation` rows and `VendorChange` |
| INDEX | `sync.index.literals` | Finds string literals in customer source that look like operation ids |
| DETECT | *(unchanged)* | Joins on `operation_id` — no new code at all |
| PATCH | `sync.route.templates`, `sync.remediate.literal_swap` | Emits an `ast-grep` rule and renders it as a diff |
| — | `sync.remediate.tiered` | Picks the cheapest remediator that can do the job |

**DETECT needed no change**, which is the design working. `to_vendor_changes` writes the model id
into `operation_id`, and the literal indexer writes the same value into `CallSite.operation_id`,
so `call_sites_for_operation` already joins them. A new signal class arrived without the join
learning anything about it.

## Measured against the live pages

Fetched 2026-07-28 from the vendors' own documentation, which serves clean markdown when the
documented `.md` suffix is appended — no HTML parser, and none of the breakage one brings.

| Vendor | Rows | Changes | Auto-patchable | Report-only |
|---|---|---|---|---|
| Anthropic | 29 | 19 | 19 | 0 |
| OpenAI | 108 | 108 | 61 | 47 |

The report-only column is the honest half: deprecations for which the vendor named no successor.
Reporting them is correct. Inventing one is the failure mode guarded against below.

## Decisions, and the failure each prevents

**State is derived from the date, not read from a column.** The first parser required a state
column and returned *zero rows* for OpenAI, who publish only shutdown dates — silently, which is
the problem, because zero rows reads exactly like zero deprecations. A model past its shutdown
date is retired whatever any table says; the date is what the API enforces. Where a vendor does
publish state it still wins, since a column can mark a model deprecated long before a date
exists.

**A placeholder is not a replacement.** Five real OpenAI rows use `---`; `N/A` and an em dash
also appear. Read as a name, that becomes the target of a literal swap — the model string is
rewritten to `"---"`, which compiles, type-checks, survives a review nobody reads closely, and
fails at the vendor. Nothing in the hand-written fixtures contained one; only running against the
real page could have caught it.

**A model id is identifier-shaped.** Vendors deprecate *endpoints* in tables shaped exactly like
their model tables, and one replacement cell carried a markdown link. One rule excludes both: a
cell containing a path separator, brackets, or whitespace is naming something else. An endpoint
deprecation is real and belongs to the oasdiff path, not here — it cannot be repaired by
rewriting a literal, and the indexer would never match one.

**Prefixes are checked, not guessed.** Sixteen real deprecated models — the `code-`, `codex-` and
`ft-` families — were invisible to the first prefix list. The finding would have been raised with
no call site to attach it to.

**A failed fetch never returns an empty list.** Empty is indistinguishable from a healthy vendor
and hides an outage rather than reporting one. A stale cache is preferred to silence; silence
with nothing cached raises. A page that returns 200 and parses to nothing raises too, and
deliberately does *not* overwrite the cache — caching before validating would compound the
failure, leaving the next run with an unparseable page and nothing to fall back on.

**Matching is structural, not textual.** Demonstrated rather than argued: against a naive
`str.replace`, `"claude-3-7-sonnet-20250219-preview"` becomes `"claude-sonnet-4-6-preview"` — a
silent retarget to a model that may not exist, and it still compiles — while the identifier
`claude_3_7_sonnet_20250219` becomes a syntax error. The `ast-grep` rule leaves both alone.

**Quote style is preserved per site.** Rules are emitted once per quote style rather than as one
rule matching both, because a single rule must pick a style for its fix and would rewrite the
other — diff noise on every review, and a likely fight with whatever formatter runs in the
customer's CI, which this patch has to pass.

**A codemod gets one attempt.** `make_patch` feeds `diagnostics` back after a failed
verification, and a deterministic remediator ignores feedback by construction: re-running it
re-emits the byte-identical patch that just failed. `TieredRemediator` drops deterministic tiers
on retry, so the graph does not spend its whole attempt budget on one unchanging answer.

## What is deliberately not done

**Template literals are not indexed.** An interpolated model id is not a literal anyone can
rewrite safely, and a rule that edited one could change what the interpolation means.

**`operation_for_symbol` returns `None` for every symbol.** A model id is not an SDK symbol.
Fabricating an `OperationRef` would mean inventing an HTTP method and path a model does not have.
The binding comes from the literal indexer, which produces `operation_id` directly.

**Parameter deprecations are no longer among these.** They were named here as the
highest-value remaining item — the case that most clearly defeats a type checker — and they are
built. `sync.signals.deprecations.parameters` parses the vendor's parameter table and emits
`VendorChange` rows through `parameters_to_vendor_changes`, and
`ParameterDeprecationDetector` in `src/sync/detect/parameter_deprecation.py` joins them against
`CallSite.args_keys` rather than `operation_id`. It fires only where a call site both passes the
parameter and targets the vendor whose parameter it is. The model scope stays unresolved and
says so in the severity: vendors write it as prose, and ordering model families is a guess this
system refuses to make.

## Sequencing

| When | What |
|---|---|
| Done | Catalogue, adapter with cache, literal index, migration rules, tier-0 remediator, tiering, `TieredRemediator` in the CLI, parameter deprecations end to end, and `DeprecationAdapter` constructed in the CLI — which is what turns a retired model into a `VendorChange` the tier-0 swap can repair |
| Done | A third vendor. Cloudflare publishes Workers AI retirements as a bulleted list under a dated heading and names models `@cf/meta/llama-3.1-8b-instruct`, so two rules were facts about the first two pages rather than about deprecation pages: the pipe-table row shape, and "a model id has no path separator". Seven further rules the third page never exercises are recorded as untested rather than as confirmed. `docs/superpowers/reports/2026-07-29-third-deprecation-vendor.md` measures each one |
| Done | Wiring it. `DEPRECATION_SOURCES` has left `cli.py` for the adapter module, beside the constants it names, and each `DeprecationSource` now declares which signals its page carries. The four call sites that read one tuple ask three different questions: the parameter scan takes the sources publishing a parameter table, the model scan and the run report share one accessor over the sources publishing retirements, and the literal indexer takes every source unfiltered, because it indexes model ids in customer code and a finding of either kind needs a call site. Measured on the way: only Anthropic of the three publishes a parameter table — the word "parameter" appears nowhere on the OpenAI page — so the replaced comment was false for OpenAI before Cloudflare existed. `docs/superpowers/reports/2026-07-29-wiring-the-third-vendor.md` carries the design, the two rejected shapes and the mutation table |
| Next | A state that is published as prose. "Variants that remain active" is real lifecycle information the parser cannot read; nothing depends on it today because that heading carries no date, so the safety is incidental rather than designed. A fourth vendor should then be chosen for a shape none of these three use — an HTML-only page, a JSON or YAML feed, or a page with no dates at all |

## Verification

- **Both vendors parse from their live pages** with zero uncovered model ids and zero malformed
  replacements. The prefix lists are asserted against ids the vendors actually publish.
- **The end-to-end test runs vendor table to applied patch** with no model call: two dying models
  found in a realistic integration, one healthy model left alone, quote style preserved per site,
  comments and arguments untouched, line count unchanged, and idempotent on its own output.
- **The produced diff was checked with `git apply --check`**, not merely inspected.
- **The tier-0 path is proven not to narrow the pipeline**: an oasdiff `response-property-removed`
  still reaches the agent when the codemod declines.

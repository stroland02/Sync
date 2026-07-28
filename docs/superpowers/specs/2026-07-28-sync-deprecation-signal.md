# Sync — The Deprecation Signal

**Date:** 2026-07-28
**Status:** Built and passing, unwired. Every component below exists with tests; nothing calls
it from the CLI yet.
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

**Parameter deprecations are not detected**, only model ids. Anthropic's `temperature` / `top_p` /
`top_k` table is the highest-value remaining item here: it is the case that most clearly defeats
a type checker, and it needs argument-position matching rather than literal matching.

## Sequencing

| When | What |
|---|---|
| Done | Catalogue, adapter with cache, literal index, migration rules, tier-0 remediator, tiering |
| Next | Wire the adapter and `TieredRemediator` into the CLI. Blocked only by ownership while `cli.py` is another worker's file. |
| Then | Parameter deprecations, which need argument matching |
| Later | A third vendor, as the next test of whether the parser is still shaped by its first two |

## Verification

- **Both vendors parse from their live pages** with zero uncovered model ids and zero malformed
  replacements. The prefix lists are asserted against ids the vendors actually publish.
- **The end-to-end test runs vendor table to applied patch** with no model call: two dying models
  found in a realistic integration, one healthy model left alone, quote style preserved per site,
  comments and arguments untouched, line count unchanged, and idempotent on its own output.
- **The produced diff was checked with `git apply --check`**, not merely inspected.
- **The tier-0 path is proven not to narrow the pipeline**: an oasdiff `response-property-removed`
  still reaches the agent when the codemod declines.

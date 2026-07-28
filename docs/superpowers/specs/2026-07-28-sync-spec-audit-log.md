# Sync — The Spec Audit Log

**Date:** 2026-07-28
**Status:** A record of one sweep, not a specification. Nothing here is binding on anything.
**Scope:** Every claim the spec corpus makes about the state of this repository, checked against
the repository, with the evidence beside each verdict so the next reader can disagree with it.

## What was audited, and against what

Eighteen files in `docs/superpowers/specs/`, checked against the working tree at `19737f7`
(`Merge branch 'stroland02/m2-depth'`), which is `main`. That pin matters: the branch this sweep
was dispatched on sat five commits behind `main` and was missing `src/sync/forge/webhook.py`,
the routing wiring in `src/sync/remediate/tiered.py`, and the whole of `src/sync/telemetry/`. The
branch was fast-forwarded to `main` before anything was checked, because a spec corrected against
a stale tree is worse than one left alone — it would have marked as unbuilt three things that are
built. Four other workers are landing on `main` in parallel, so a claim verified here can go stale
again; the SHA is recorded so the next reader knows what was and was not covered.

Claims about the market, about hosting that does not exist, and about vendor pages fetched over
the network are not settleable from a checkout. They are listed under "Not verifiable" rather than
guessed at.

Eleven claims were false or half-true and were corrected, across eight files. The total checked is
roughly 150, counting one assertion carrying a file, line or symbol reference as one claim — that
figure is a tally of the entries below rather than a measurement, and it is given as an order of
magnitude on purpose. The eleven are exact.

## The corrections, in descending order of what they cost

### The merge webhook — `2026-07-27-sync-benchmark-gates.md`, `2026-07-25-sync-migration-corpus.md`

Both files said no webhook receiver is built and `GraphStore.set_merge_outcome` has no caller.
`src/sync/forge/webhook.py` exists. `record_merge_outcome` (line 142) verifies GitHub's
HMAC-SHA256 signature with `hmac.compare_digest` before parsing, acts only on
`pull_request.closed`, and calls `store.set_merge_outcome` at line 178.

The correction is not "this is built now", because the merge rate still has no numerator and the
reason has moved. `record_merge_outcome` finds its corpus row by `pr_number`, and `pr_number` has
no writer: `grep -rn pr_number src/` returns the webhook, the model field, the store's update
statement, and `src/sync/benchmark/axes.py` reading it — no producer on the open-pull-request
path. The receiver's own docstring says so. Nothing mounts it either; it is a function over bytes
with no HTTP framework, deliberately.

This is the most consequential correction in the sweep. The old sentence would have sent a worker
to build a webhook receiver that exists, complete with the signature verification, while the two
things actually missing — a `pr_number` write at open time, and a process to deliver to — went
unnamed by any document.

### The routing table — `2026-07-27-sync-routing-matrix.md`, `2026-07-27-sync-benchmark-gates.md`

The claim was that `sync.route.matrix.route()` is imported by nothing outside `src/sync/route/`.
False: `src/sync/remediate/tiered.py:42` imports it and line 282 calls it. A tier −1 route raises
`NoPatchWarranted` so no remediator is consulted, which is the behaviour the table's first row
exists to produce.

Replacing that with "the table drives the routing" would have destroyed more information than it
added, so the correction names three separate limits, each checked:

- `route()` keys on a catalogue record and `TieredRemediator` takes the catalogue as a
  constructor argument. `build_remediator` in `src/sync/cli.py:84` passes none, so `_catalogue` is
  empty, `_tier_for` returns `None` for every change, and the cascade falls back to `can_handle`
  ordering. `grep -rn "TieredRemediator("` over `src/` returns exactly one construction.
- `routing_facts` in `tiered.py` cannot establish `call_sites_reading_field` or
  `field_passed_as_literal` — one is a graph-wide count and the other is not indexed — so rows 3
  and 4, the entire tier-0 surface, decline rather than guess even with a catalogue present.
- The row that decided is offered through an `on_route` callback. `grep -rn on_route src/`
  returns only its definition and call inside `tiered.py`; the only caller anywhere is
  `tests/test_tiered_remediator.py:413`. `migration_outcome` has no column for it either
  (`src/sync/graph/schema.sql:54`), so the benchmark spec's "the decision-table row does not exist
  to record" survives with its reason replaced.

### The deprecation signal — `2026-07-28-sync-deprecation-signal.md`

Two errors in opposite directions in one document.

The Status line said "Built and wired". The parameter half is: `src/sync/cli.py:409` constructs
`ParameterDeprecationDetector`, fed by `parse_parameter_deprecations` at line 354 over pages
fetched from `DEPRECATION_SOURCES` (line 45), against call sites from `index_operation_literals`
(line 381). The model-retirement half is not. `DeprecationAdapter` is the only caller of
`parse_deprecation_table` and `to_vendor_changes`
(`src/sync/signals/deprecations/adapter.py:129,145`), and `grep -rn "DeprecationAdapter("` over
`src/` returns nothing. So no `ModelDeprecation` becomes a `VendorChange`, and
`LiteralSwapRemediator` sits in the cascade with nothing to act on — which is the document's
headline path, unreachable.

In the other direction, "What is deliberately not done" still said parameter deprecations are not
detected. `src/sync/detect/parameter_deprecation.py` and
`src/sync/signals/deprecations/parameters.py` both exist with tests. Corrected in place, and the
Sequencing table's "Next" row narrowed from "wire the adapter and `TieredRemediator`" —
`TieredRemediator` reaches `build_graph` at `cli.py:541` — to the one call site still missing.

### `main` carries source — `2026-07-26-sync-review-integration.md`

Its Sequencing preamble said `main` carries documentation only and the `src/` tree lives on
`worktree-sync-m0-vendor-change` until M0 merges. `git ls-tree --name-only main` lists `src` and
`tests`. Corrected, and the real remaining blocker named instead: `src/sync/mcp/tools.py` is tool
logic over a `GraphReader` with no transport, so there is no `sync-mcp` process for Open Code
Review to start as a subprocess.

### A second shape-store feeder — `2026-07-26-sync-observed-contract-drift.md`

The Status line named `src/sync/signals/sentry/` as the `error-payload` source. There are two:
`src/sync/signals/datadog/shapes.py:79` sets `SOURCE = "error-payload"`, the same value
`sentry/shapes.py:63` sets, deliberately — the module explains that both samples are drawn from
failures so merging them is correct and their combined `sample_count` is not corroboration. Both
are now named, along with the consequence.

"Nothing has fed Sentry payloads in" was true and too narrow. `record_observed_shape` has no
caller outside the two readers, and neither reader is constructed anywhere in `src/`, so the
baseline is empty for a reason that now covers both.

### OTLP — `2026-07-27-sync-pipeline-discipline.md`

"Raw OTLP ingestion, and anything downstream of it" was listed under what deliberately does not
apply, which would tell a reader Sync does not read OTLP at all. It does: `src/sync/telemetry/otlp.py`
decodes OTLP/JSON export payloads and `src/sync/telemetry/ingest.py` folds the client spans into
`observed_call` (`schema.sql:181`). The strategic refusal was of ingestion *infrastructure*, and
that still holds — `ingest.py`'s docstring is explicit that there is no server, no port and no
collector protocol, and `ingest_payload` has no caller in `src/` outside the package's own
`__init__`. Qualified rather than deleted, since the conclusion it supports is unchanged.

### The migration corpus schema — `2026-07-25-sync-migration-corpus.md`

The document's SQL block is presented as what is recorded, under a Status line saying "Built".
Four specified columns are absent from `src/sync/graph/schema.sql:54`: `call_site_depth` and
`is_wrapped` from the call-site block, `ci_wall_ms` and `pr_closed_unmerged` from the outcome
block. `finding_id` is `text` rather than `uuid`, `terminal_status` is nullable, and the second
specified index is absorbed by `UNIQUE (finding_id, attempt_index)`, which leads with the same
columns. None of the four is read by `src/sync/benchmark/axes.py`. Recorded in the document rather
than either schema being changed — a query written from that block will not run against the table,
and that is the fact worth having.

### The domain-specific language — `2026-07-28-sync-domain-specific-thesis.md`

Guideline 5's row read "**Sync has none**" with status **Gap**, and the section under it said
"Sync currently has no such object" — both resolved ninety lines later by the same document's
"It is now built and is what tier 0 runs on". `src/sync/route/templates.py` emits the `ast-grep`
rules and `literal_swap.py`, `property_omit.py` and `parameters.py` apply them. The table row and
the opening sentence were corrected; the argument between them was left standing, because it is an
argument and not a state claim.

## Every file, and what was checked

### `2026-07-25-sync-competitive-position.md` — unchanged

A research record with a `Last verified: 2026-07-25` line, and every claim in it is about the
market. Datadog's Bits Code GA, GitHub's autofix preview, the three acquisitions, the ARR and
price figures, the autonomous-PR merge rates, FlareCanary/ShiftGraph/Deprecatr — none is settleable
from a checkout, and the document already carries per-claim confidence markers and an expiry rule.
Its one repository-adjacent claim, that Sync's remediation graph is `locate, strategize, patch,
static verify, push, await CI, open PR`, matches the seven conditional edges in
`src/sync/remediate/graph.py:35-78`. Correct.

### `2026-07-25-sync-graph-surface-design.md` — unchanged

Status claim checked in full and correct in every part. `src/sync/mcp/tools.py` defines
`GraphSurface` with `whats_at_risk` (line 65), `explain_call_site` (111) and `whats_changed` (145),
and no fourth tool. `grep -rn "FeedCache\|sync://feed" src/ tests/` returns nothing, so the
resource and the cache are absent as claimed. There is no transport: the module takes a
`GraphReader` protocol and returns dicts. `_envelope` emits `context_savings` (line 232) and
`_page` paginates, which the response-shaping rules require. The correction recorded at the end of
the document — that `codebase-memory-mcp` makes the 9-to-18-engineer-month moat estimate wrong —
is about an external project and was not re-checked.

### `2026-07-25-sync-latency-architecture.md` — unchanged

The only state claims are in the M3 sequencing row, and both hold. `build_remediator` at
`src/sync/cli.py:69` returns the `TieredRemediator`, and `grep -n cache_control
src/sync/remediate/agent_patch.py` returns nothing, so the prompt-cache boundary is genuinely
unset. The reducer landmine, the Nielsen thresholds and the fast-mode pricing are design
statements and were not treated as repository claims.

### `2026-07-25-sync-mcp-drift-measurement.md` — unchanged

A measurement record over two external git repositories. The 18-versus-59 release counts, the 135
breaking changes, and the `get_commit`/`include_diff` instance cannot be re-derived without
cloning those repositories, which is outside this task. Its one repository claim — that
`extract.py`, `go_extract.py`, `drift.py` and `drift_go.py` are in a session scratchpad and not
committed — holds: none appears under `scripts/` or anywhere in the tree.

### `2026-07-25-sync-migration-corpus.md` — corrected

Beyond the two corrections above: the table is at `schema.sql:54` as claimed, `MigrationOutcome`
is in `src/sync/core/models.py`, and `src/sync/remediate/corpus.py` is installed by
`graph.py:13` via `make_recorder`. The abandoned-attempt write is real —
`src/sync/remediate/nodes.py:344` calls `record(state, terminal_status="abandoned",
abandon_reason=reason)` inside `make_abandon`. The privacy argument's claims about `symbol_shape`,
`arg_key_hashes` and `edit_script` describe intent for a table with no rows and were not treated as
state claims; `edit_script` in particular has no writer, which the domain-specific thesis already
records.

### `2026-07-25-sync-positioning-and-open-core.md` — unchanged

Positioning and licensing decisions, none of them about code. One inconsistency was found and
deliberately not corrected: its Open Items still lists the feed's data licence as undecided,
while `2026-07-26-sync-public-change-feed.md` decides CC0 and says it is resolving this item.
That is a decision record disagreeing with a later decision record, not a claim about the
repository, and reconciling two committed positions is outside a state audit. Flagged here so
whoever owns the positioning document can settle it.

### `2026-07-25-sync-self-maintaining-apis-design.md` — unchanged

The largest file and the one with the most measured claims. Every M0 limitation was checked and
every one holds:

- `sync.index.shipped_tree` and `sync.index.dependency_edits` both exist as modules.
- `git add -u` is at `src/sync/forge/github.py:163`, with the comment at 116 giving the `-A`
  argument, so "a patch that needs a new file abandons rather than shipping one" stands.
- `run_tsc` prefers `node_modules/.bin/tsc` at `src/sync/index/tsc.py:132`; every install command
  in `src/sync/index/deps.py:25-29` passes `--ignore-scripts`. Both halves of the toolchain
  qualification are accurate.
- "Nothing in the pipeline applies `patch.diff`" holds: `grep -rn "git apply\|apply_patch" src/`
  returns nothing.
- The push lease reads authorship: `COMMIT_AUTHOR_EMAIL` at `github.py:31`, the author check at
  220, `--force-with-lease` at 186 and 273.
- The `x-stableId` verb correction is in `src/sync/signals/stripe/symbols.py:149`.

Two claims could not be settled. The 105-of-414 coverage figure and the 327,124-record depth
measurement both derive from `.cache/specs/`, which is gitignored, so they cannot be recomputed
from a clone — `tests/test_stripe_adapter.py:262` asserts the 414 denominator and nothing pins the
105. And the M0 acceptance run's pull request is on GitHub, outside what a checkout can confirm.

One thing was noticed and left: the Packages table lists eight packages and `src/sync/` now holds
`route`, `benchmark`, `mcp` and `telemetry` as well. That table is a design decomposition rather
than an inventory, and the packages that joined it were each added by another spec, so widening it
here would be editing a design and not correcting a fact.

### `2026-07-25-sync-threat-model.md` — unchanged

Every line reference resolves. `tsc.py:132` is the `node_modules/.bin/tsc` preference, `tsc.py:150`
is `--package=typescript@latest`, `_TSC_TIMEOUT_SECONDS` is at `tsc.py:21`, and the
`--ignore-scripts` claim is verified above. The "how it was resolved" paragraph is accurate in all
four of its parts, including that the unpinned fallback is still there.

Its Required Mitigations are prescriptive and were not audited as state. Worth noting for whoever
picks them up: mitigation 4, pinning the fallback compiler, is listed as M0 work and is not done —
which the document's own Finding section already says. The "branch Sync did not create" guard
exists as the authorship lease described in the design document; there is no separate refusal to
push to a default branch, and `_default_branch` (`github.py:330`) serves the fetch exclusion rather
than a guard.

The Status line's "code already on the M0 branch" now reads oddly since M0 merged, but it describes
where the finding was made and misleads nobody about the code. Left alone.

### `2026-07-26-sync-observed-contract-drift.md` — corrected

Beyond the two corrections above, the rest of the document is accurate and unusually so. The
`observed_shape` table is at `schema.sql:118`. `MIN_SAMPLES = 30` is at
`src/sync/detect/observed_drift.py:66`. The join correction — that `path_ptr` is the URL path and
not a JSON pointer — is confirmed at `src/sync/signals/oasdiff.py:110`,
`path_ptr=record.get("path", "")`, and `changed_field()` is at line 149. The admission that the
unpublished-enum case cannot be built as specified is carried in the detector's own docstring, as
the spec says it is.

### `2026-07-26-sync-public-change-feed.md` — unchanged

Status correct in every part. `render_feed`, `sign_feed` and `public_key_bytes` are in
`src/sync/signals/feed/publisher.py`; `verify_feed` raises `FeedSignatureError` and `parse_feed`
raises `FeedFormatError`, and `verify_and_parse` (consumer, line 84) runs verification first. The
operational half is genuinely absent: `grep -rn "PUBLIC_KEY\|public_key" src/sync/core/` returns
nothing, so no key is committed, and there is no `FeedCache` anywhere. Hosting and the keypair are
not verifiable from a repository and are not claimed to exist.

Its references to `2026-07-25-sync-mcp-graph-surface.md` resolve — that file is under
`docs/superpowers/plans/`, not `specs/`, which is why a `specs/`-only search misses it.

### `2026-07-26-sync-review-integration.md` — corrected

Beyond the Sequencing correction: the five adopted mechanisms are read out of Alibaba's repository
and were not re-verified against it. One Sync-side claim was checked and is still accurate as
pending work — snippet-based positioning is not in the `locate` node, which reads the stored call
site by id (`src/sync/remediate/nodes.py`, `make_locate`).

### `2026-07-27-sync-adapter-targets.md` — unchanged

The generator-mechanism claim is built exactly as described. `src/sync/signals/generated/manifest.py`
carries `STAINLESS_MANIFEST = ".stats.yml"` and `SPEAKEASY_MANIFEST = ".speakeasy/workflow.yaml"`
with a parser for each; `src/sync/signals/generated/adapter.py:80` is `GeneratedSpecAdapter`, and
`operation_for_symbol` at line 101 returns `None` with the reasoning the spec gives.

Every spec URL, size and endpoint count in the target table was fetched on 2026-07-27 over the
network and cannot be re-checked here — no test may call a vendor API. The `.stats.yml` hashes,
the Cloudflare and Orb manifests missing a URL, and the startup-cohort probes are all in that
category.

One mismatch left in place: the Sequencing table still schedules "**The `GeneratedSdkAdapter`**"
at M1.5 as future work, while the body says it is built and the class is in fact named
`GeneratedSpecAdapter`. The body is a hundred lines above the table and states the truth
explicitly, so the table reads as milestone ordering rather than as a claim that nothing exists.
Recorded rather than edited.

### `2026-07-27-sync-benchmark-gates.md` — corrected

Everything outside the two corrected preconditions holds. Gate tier A matches
`.github/workflows/ci.yml` line for line: the encoding lint, then `lint-imports`, then `pytest`,
in that order, with `OASDIFF_VERSION: 1.26.1` pinned and the comment giving the same reason the
spec does. `tests/test_lint_encoding.py:111` asserts `result.returncode != 0` on a known-bad file,
so the "proven able to fail" claim is real. `src/sync/benchmark/axes.py` computes exactly the three
claimed axes — `merge_rate_by_change_kind`, `merge_rate_by_tier`, `routing_accuracy`, plus
`tokens_per_merged_patch` and `wall_ms_per_merged_patch` for cost — with a `Counts` block for the
denominators precision will need, and `Axis.value` is `None` rather than `0.0` at zero samples, as
the Verification section demands. Nothing in that module is referenced from the workflow.

The corpus being empty was not verified: it is a claim about a Postgres instance, not about the
tree. It is consistent with `pr_number` having no writer.

### `2026-07-27-sync-pipeline-discipline.md` — corrected

The two commits it cites both resolve: `efcc19d fix: include line and col in call_site identity to
stop same-file collisions` and `b29795a fix: resolve the patch prompt's affected field from oasdiff
text, not the URL path`. `VendorChange.raw` is carried and is published in `FEED_FIELDS`.

Its Verification section asks that every table's grain appear as a comment in `schema.sql`, and
three of six do not. `grep -n "^-- Grain:" src/sync/graph/schema.sql` returns exactly three hits —
`migration_outcome` at 46, `observed_shape` at 104, `observed_call` at 150. `call_site` (line 1),
`vendor_change` (19) and `finding` (33) carry none. All three predate the rule, which is the
likely explanation and not an excuse: `CLAUDE.md` states the requirement without a carve-out for
tables that already exist. The gap is in the schema rather than in this document, so nothing was
edited — the rule is right and the source has not caught up. Recorded here because it is a
one-line-per-table fix that nobody currently owns.

### `2026-07-27-sync-routing-matrix.md` — corrected

Every measured number in this document reproduces. Running `tools/oasdiff.exe checks --format json`
gives 506 rules, 212 `error` / 264 `info` / 30 `warning`, and across the 212 breaking rules
`direction` request 118 / response 81 / none 13, `kind` structure 54 / constraints 54 / type 25 /
existence 24 / lifecycle 21 / values 20 / requiredness 14, and `action` change 60 / remove 57 /
add 43 / decrease 25 / increase 22 / generalize 4 / specialize 1. Every figure in the two
distribution tables matches exactly.

One qualification on that: the binary in `tools/` reports `oasdiff version 1.26.0`, while CI pins
1.26.1. `tools/` is gitignored, so the local version is a property of this machine and not of the
repository, and the spec's claim that CI pins 1.26.1 is separately confirmed in `ci.yml`. The
counts are therefore corroborated at 1.26.0 and not re-verified at the pinned version.

Also checked and correct: `to_vendor_changes` sets `severity="breaking"` unconditionally
(`oasdiff.py:111`), so the severity-discarding claim stands and preserving oasdiff's level is
still undone. The `add_conditional_edges` block quoted from `graph.py` matches the source at lines
43-47 exactly, including the destination map. `route_after_static` branches on an explicit boolean
as described. The tier-0 codemod modules and `src/sync/route/templates.py` all exist.

### `2026-07-28-sync-deprecation-signal.md` — corrected

Beyond the two corrections: `DEPRECATION_SOURCES` is at `cli.py:45` and
`ParameterDeprecationDetector` at `cli.py:409`, both as claimed. The design decisions — the
placeholder replacement, the identifier-shaped rule, the prefix lists, the never-empty fetch, the
quote-style rule, the one-attempt codemod — are all argued from live vendor pages fetched on
2026-07-28 and are not re-checkable without network access. The measured table (Anthropic 29 rows,
OpenAI 108) is in that category. `operation_for_symbol` returning `None` for every symbol is
confirmed at `src/sync/signals/deprecations/adapter.py:118`.

### `2026-07-28-sync-domain-specific-thesis.md` — corrected

Beyond the guideline-5 correction: the two claims in "What this changes about priorities" that
qualify the build are both accurate and both worth keeping. `edit_script` is declared at
`src/sync/core/models.py:162` and `grep -rn edit_script src/` finds no writer, so the column the
notation was meant to give a type is uniformly null. `FEED_FIELDS` in
`src/sync/signals/feed/publisher.py:45` is nine fields and none is a migration recipe. The NVIDIA
history, the Coccinelle papers and the `ast-grep` package facts are external and were not
re-verified; the document already marks which of them were checked and which were not.

### `2026-07-28-sync-ground-truth-count.md` — unchanged

The newest file, and it audits itself more carefully than this sweep could. Every number is a
GitHub search `total_count` from 2026-07-28, none reproducible here, and the document says so
twice — including that one query returned two different totals minutes apart. Its two repository
claims both hold: `tests/fixtures/specs/charges_base.json` and `charges_revision.json` both declare
`"version": "base"`, and the three dated Stripe versions came from `.cache/specs/`, which is
gitignored and therefore not reproducible from a fresh clone, exactly as stated. Its instrument,
`scripts/mine_stripe_migrations.py`, is committed.

## What could not be verified, and why

Grouped by the reason, because the reasons differ in what would fix them.

**Nothing exists to check.** The feed's hosting, its CDN, its Ed25519 keypair and its published
public key; the hosted control plane, its dashboard and its per-repository policy; the SOC 2
observation window; the credential-free verification sandbox the threat model gates M1 on. No
query settles these because there is nothing yet to query. Every document that mentions them
already says they do not exist.

**It is a network fact.** Every vendor spec URL and size in the adapter-targets table; the
`.stats.yml` hashes and endpoint counts for eleven SDK repositories; the Anthropic and OpenAI
deprecation-page row counts; every GitHub search total in the ground-truth count. No test in this
repository may call a vendor API, so re-checking these would break a house rule to confirm a number
already recorded with its date.

**It is a market fact.** Everything in the competitive-position document, the acquisition record,
the pricing, the merge-rate studies, and the MCP drift measurement over two external repositories.
These carry confidence markers and an expiry rule of their own.

**It is a database fact.** That `migration_outcome` and `observed_shape` hold no rows is asserted
by four documents and was not confirmed against a running Postgres. It is consistent with what the
tree shows — no writer for `pr_number`, no constructed shape reader — but a checkout cannot settle
it.

**It derives from a gitignored cache.** The 105-of-414 symbol coverage, the 327,124-record depth
measurement, and the three dated Stripe versions all read `.cache/specs/`. They are honest numbers
that no fresh clone can reproduce, and the ground-truth count is the only document that says so
about its own.

## Gates

Run against the tree after the edits above, all of which are documentation:

- `uv run pytest -q` — **1085 passed** in 90.41s, matching the count this sweep was told to expect.
- `uv run python scripts/lint_encoding.py src scripts tests` — clean.
- `PYTHONIOENCODING=utf-8 uv run lint-imports` — contracts kept.

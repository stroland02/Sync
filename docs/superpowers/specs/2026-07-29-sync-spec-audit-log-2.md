# Sync — The Spec Audit Log, Second Sweep

**Date:** 2026-07-29
**Status:** A record of one sweep, not a specification. Nothing here is binding on anything.
**Scope:** Every claim the spec corpus makes about the state of this repository, checked against
the repository, with the evidence beside each verdict so the next reader can disagree with it.
Supersedes nothing: `2026-07-28-sync-spec-audit-log.md` is a dated record of what was true at
`19737f7` and is left exactly as it was written.

## What was audited, and against what

Twenty-one files in `docs/superpowers/specs/`, plus the previous log, checked against the working
tree at `0613da2` (`feat: generate labelled pairs by mutating a real repository`). That is **105
commits past `19737f7`**, the tree the first sweep measured, of which 67 are non-merge.

Three of the twenty-one did not exist when the first sweep ran:
`2026-07-29-sync-adaptive-vendor-substrate.md`, `2026-07-29-sync-coverage-baseline.md` and
`2026-07-29-sync-ground-truth-quality.md`.

The previous log's own caveat — *"Four other workers are landing on `main` in parallel, so a claim
verified here can go stale"* — is the reason this sweep exists, and it was right at a scale nobody
predicted. **Twenty-eight substantive claims across twelve files were false or half-true**, and a
further fourteen line references in six files no longer resolved. Fourteen files were changed in
all.

**Every one of the twenty-eight had become false in the direction of understating what is built.**
Not one thing the corpus said existed had disappeared; a great deal it said was missing had
shipped. That asymmetry is itself the finding, and it means the corpus's failure mode right now is
stopping work that is already done rather than sending someone after work that does not exist.

Roughly 170 claims were checked, counting one assertion carrying a file, line or symbol reference
as one claim. That figure is a tally of the entries below rather than a measurement and is given
as an order of magnitude on purpose. The twenty-eight and the fourteen are exact.

The same categories the first sweep could not settle remain unsettleable: market facts, network
facts, hosting that does not exist, and the contents of a Postgres instance. They are listed under
"What could not be verified" rather than guessed at.

## The corrections, in descending order of what they cost

### The merge rate has a numerator — `2026-07-27-sync-benchmark-gates.md`, `2026-07-25-sync-migration-corpus.md`

The previous sweep's headline correction was that the webhook receiver existed and the merge rate
still had no numerator, for two reasons it named precisely: nothing wrote `pr_number` when a pull
request opened, and no process mounted the receiver. **Both are closed.**

`src/sync/remediate/nodes.py:571` calls `record(state, terminal_status="opened",
pr_number=pull_request.number)` inside `make_open_pr`, and the number is passed as an argument
rather than read off `RunState` deliberately — the comment above it says why: every other `record`
call site omits it, so a retried attempt keeps a null by construction rather than by the order two
writes happen to run in. `src/sync/remediate/corpus.py:221` takes the argument and threads it to
the store.

`sync merge-outcome` (`src/sync/cli.py:1150`) is the caller `record_merge_outcome` never had. It
reads a delivery from a file or stdin as bytes, refuses outright when no secret is configured
rather than processing unverified bytes, and prints "nothing to record" on the no-match path
because humans open pull requests in the same repository and every one of them delivers here.

What is left is not a defect and is stated as such in both documents now: nothing listens. The
receiver is still a function over bytes with no HTTP framework, the same refusal `sync ingest` and
`sync shapes` make, so a delivery arrives when an operator hands one in. Replacing "does not hold"
with "holds" would have been wrong in the other direction; the correction names which half moved.

### The MCP server is a process — `2026-07-25-sync-graph-surface-design.md`, `2026-07-26-sync-review-integration.md`, `2026-07-26-sync-public-change-feed.md`

The graph-surface Status line said four things were not built: `sync_propose_patch`, the
`sync://feed/{vendor}` resource, `FeedCache`, and any server transport. All four exist.

- `GraphSurface.propose_patch` is at `src/sync/mcp/tools.py:193`, driving the shipped pipeline
  through `src/sync/mcp/propose.py` as far as static verification. That module's guarantee is
  structural rather than asserted: `push_branch`, `await_ci`, `open_pull_request` and
  `delete_branch` are all methods on `Forge`, and the driver never accepts a `Forge`.
- `src/sync/mcp/server.py` is newline-delimited JSON-RPC 2.0 over stdio, with `main()` as the
  entry point and `SYNC_DSN` as its only configuration.
- `src/sync/mcp/resources.py` serves the feed resource out of `FeedCache`
  (`src/sync/signals/feed/cache.py`), and is handed no store at all, so a resource cannot reach
  the private graph.
- `tests/golden/tool_schemas.json` holds all four tool names, so the frozen-schema rule the
  document specifies is executable rather than aspirational.

The previous sweep's own evidence for the negative — `grep -rn "FeedCache\|sync://feed" src/
tests/` returning nothing — is the cleanest illustration of how fast this corpus goes stale.

This propagates. `2026-07-26-sync-review-integration.md`'s Sequencing preamble said the blocker was
that "there is no `sync-mcp` process for OCR to start". `pyproject.toml` declares
`sync-mcp = "sync.mcp.server:main"`, and the two configuration artifacts and the rule fragment are
committed under `docs/integrations/opencodereview/` — `config.json` whitelisting exactly the two
tools the spec specifies, `rule.json` with `merge_system_rule: true`, and
`rules/sync-api-surface.md`. The correction names what genuinely has not happened, which that
directory's own README also says: the falsification count — run OCR against a fixture pull request
and count whether the tools are called — has not been taken. Installed and unproven.

`2026-07-26-sync-public-change-feed.md` said "no committed public key, no hosting, no `FeedCache`".
`FeedCache` exists and is what made the signature load-bearing at all — a signature nobody checks
is a signature nobody has to forge. The public key needed a qualification rather than a flat
reversal: `DEVELOPMENT_FEED_PUBLIC_KEY` is committed in `src/sync/core/keys.py` as thirty-two raw
hex bytes, and it verifies the fixtures under `tests/fixtures/feed/` and nothing else. Its own
docstring records that the private half was generated in a throwaway process and never written to
disk, which is why those fixtures cannot be re-signed. Writing "the public key is committed" would
have read as the trust anchor for a real publication existing. It does not.

### A patch that needs a new file now ships one — `2026-07-25-sync-self-maintaining-apis-design.md`

The design document's Known Limitations said a patch requiring a new module abandons rather than
shipping one, because `git add -u` never stages an untracked path. `CLAUDE.md` says the same thing
in its qualifications on the verification gate.

It is no longer true, and the mechanism that closed it is the one the old paragraph called the
unsolved part. Separating a new source file the patch needs from build debris is not a question
the pipeline can answer, so it is put to the party that knows: `_SCOPE_RULES` in
`src/sync/remediate/agent_patch.py:67` now instructs the agent to create the file and stage it by
path with `git add <path>`, never `git add -A` or `git add .`. Staging is the assertion.

Three things carry it from there, and none of them needed changing:

- Git reports a staged addition as `A `, and `_UNSHIPPED` in `src/sync/index/shipped_tree.py:79`
  is exactly `{"??", "!!"}`, so the gate keeps the file in the tree and compiles it.
- `git add -u` updates the index where it already has an entry, so `push_branch` commits it.
- `_git_diff` (`agent_patch.py:177`) runs `git diff HEAD` rather than `git diff`, so a patch whose
  whole content is a new module is no longer read as a remediator that changed nothing.

That `_UNSHIPPED` is exactly those two codes is now load-bearing rather than incidental, which the
correction states, because adding `"A "` would read as tightening and would silently push branches
missing the module they import.

Half of the abandon path is closed and half is not: where the diff is empty and unstaged additions
exist, `propose` raises naming the files and the remedy; where the agent also edits a tracked call
site, the diff is non-empty, the run proceeds, and the gate fails on `TS2307: Cannot find module`
— a downstream compile error standing in for the real cause. Both halves are now in the document.

**A disagreement this leaves standing.** `CLAUDE.md` still carries the old sentence, under a
heading marked non-negotiable. It is not a spec and this sweep does not own it, so it was not
edited; whoever owns that file should know the qualification is now understated.

### The indexer serves more than one vendor — `2026-07-29-sync-adaptive-vendor-substrate.md`

This document is one day old and its central section was already wrong. It named
`src/sync/index/typescript.py:29`, `_SDK_PACKAGE = "stripe"`, as "the highest-value defect in the
system", and step 1 of its sequence was to remove it.

The constant is gone. Watched packages come from the vendor adapters an indexer instance holds,
through `sync.index.sdk_bindings` — `bound_vendors` at line 113 and `collect` at 129 — and one
instance covers several vendors in a single traversal rather than parsing the tree once per
vendor. A vendor declaring no `sdk_bindings` falls back to a binding derived from its vendor id,
which is safe in the one direction that matters: a wrong derivation names a package the manifest
does not declare, `matches` answers False, and `cli.select_language_adapter` raises naming what it
tried. It cannot resolve *incorrectly*, because a symbol rooted at the wrong name is in no
vendor's map.

Step 1's stated closing condition is met and was checked rather than assumed:
`tests/test_multi_vendor_index.py:182` indexes `tests/fixtures/ts/twilio` and resolves
`twilio.messages.create` to a Twilio operation. The same file pins what still does not resolve —
`client.insights.v1.calls(callSid).fetch()`, a chain broken by a call in its middle, which is how
`twilio-node` addresses a single resource.

The section was rewritten in the past tense rather than deleted, and the hard half it identified
was left standing, because that half is still true: parameterising a package name does not reach a
call-site shape. **Steps 2 through 5 have not started**, and this was checked rather than inferred
from the sequence's order — `grep -rn "watchable" src/` returns nothing, so there is no dependency
intake artifact; `grep -rni "reachab" src/` returns only unrelated prose and
`benchmark/mutate.py`'s `unreachable` field, so there is no reachability ranking; and no module
under `src/sync/signals/` extracts a symbol map from an SDK's own source.

### Row 4 of the routing table fires — `2026-07-27-sync-routing-matrix.md`, `2026-07-27-sync-benchmark-gates.md`

The previous sweep's best entry replaced a clean verdict with three separately-checked limits.
Two of the three have moved and one has not, so the same treatment applies again.

**The catalogue is wired.** The previous log recorded that `build_remediator` was passed no
catalogue, so `_catalogue` was empty and `_tier_for` returned `None` for every change.
`src/sync/cli.py:865` now calls `load_catalogue()` and hands the same object to
`build_remediator` and to `build_graph`, so there is one table rather than two that could drift.

**Row 4 is reachable.** The old text said `field_passed_as_literal` "is not recorded by the
indexer at all", and both mechanical rows therefore declined. `routing_facts` in
`src/sync/remediate/tiered.py` now establishes it from the clone, by reading the call itself
through `sync.route.templates.argument_is_literal_at` — the same file the codemod is about to
edit, parsed by the same scoping, so router and codemod cannot disagree about which call they
mean. Every way that reading can fail answers `None` rather than `False`, so absent evidence still
never reads as permission. `call_sites_reading_field` genuinely cannot be established there: it is
a count across the whole graph and `propose` is handed one site. So the request side of tier 0 is
reachable and the response side is not, which is what the corrected text says.

**The row that decided is still not recorded, and now travels further before being dropped.**
`_decide_tier` at `src/sync/remediate/nodes.py:72` calls `route()` inside `locate`, stores the row
on `RunState` as `routing_row`, and the report node names it in the reason a tier −1 finding
carries (`nodes.py:631`). That is prose for a human, not a column. `grep -rn on_route src/` still
returns only the definition and call inside `tiered.py`; `migration_outcome` still has no column
for it (`src/sync/graph/schema.sql:60-105`); and `sync.remediate.corpus` takes no such argument.
So the benchmark spec's "holds in part" survives with its reason sharpened rather than replaced.

Every measured number in the routing document reproduces exactly. `tools/oasdiff.exe checks
--format json` gives 506 rules, 212 `error` / 264 `info` / 30 `warning`; across the 212 breaking
rules, `direction` request 118 / response 81 / none 13, `kind` structure 54 / constraints 54 /
type 25 / existence 24 / lifecycle 21 / values 20 / requiredness 14, and `action` change 60 /
remove 57 / add 43 / decrease 25 / increase 22 / generalize 4 / specialize 1. The previous sweep
could only corroborate these at 1.26.0 because the local binary lagged; it now reports `oasdiff
version 1.26.1`, which is the version CI pins, so the qualification that sweep recorded can be
dropped.

### The replay tier exists, and is not the shape-store feeder it was specified as — `2026-07-26-sync-observed-contract-drift.md`

The Status line said "the replay tier and the interceptor SDK do not exist" and the Sequencing
table marked replay "Not built". `src/sync/verify/replay.py` and `src/sync/verify/mock_response.py`
exist, and `src/sync/remediate/graph.py:37` installs `replay` as a node between `static_verify` and
`push_branch` — exactly where this document puts it. A replay failure re-enters the retry loop; a
replay that could not run reaches the push path carrying the fact that it was not replay-verified.

Marking it "Built" alone would have destroyed the more interesting fact. This document also says
"every replay run is also a shape-store writer (`source = 'replay'`), which is how the baseline
begins accumulating before any customer installs anything." That half has not happened.
`replay_shapes` at `src/sync/verify/replay.py:171` builds the rows, `make_replay` carries them out
on `RunState`, and `grep -rn replay_shapes src/` shows no call to `record_observed_shape` with
them. The run holds the rows and the store does not get them. Both the Status line and the
Sequencing row now say so.

The second correction in the same file runs the other way. "Neither reader is constructed anywhere
in `src/`, so nothing feeds the store" is false: `sync shapes` (`src/sync/cli.py:974`) constructs
both through `_fold_sentry` (927) and `_fold_datadog` (950). It is still not a listener — it reads
an export somebody handed it — so the corrected text says the baseline is empty until somebody
feeds it rather than that it has no writer, and names `MIN_SAMPLES = 30`
(`src/sync/detect/observed_drift.py:66`) as the reason one export is unlikely to lift a shape over
the floor.

### Binding precision and recall have arithmetic and no reference — `2026-07-27-sync-benchmark-gates.md`

"Binding precision and recall are still uncomputable... the corpus records what Sync did, not what
was correct" was true about the reason and false about the state.
`src/sync/benchmark/binding.py` computes both and splits each by the rung the binding came from —
precision on the rung the finding carries, recall on the rung the label names, keyed differently
on purpose because a miss has no finding and therefore no rung of its own. And
`src/sync/benchmark/mutate.py` produces the labelled pairs it takes, by inverting a vendor change
into a call site and recording the edits it made rather than computing a label from the result.

What is missing is a corpus of those pairs. `sync benchmark` (`src/sync/cli.py:1333`) calls
`render_report(store.migration_outcomes())` and passes no labels, and `render_report`'s `labels`
parameter defaults to empty because no label source is wired. So the score it prints is computed
over an empty reference, and the shape of the blockage is now identical to the other three axes:
the computation exists and there is nothing to run it over.

### The model-retirement half runs — `2026-07-28-sync-deprecation-signal.md`

The previous sweep corrected this document in two directions at once and left one gap named: no
`DeprecationAdapter` was constructed in `src/`, so no `ModelDeprecation` became a `VendorChange`
and `LiteralSwapRemediator` sat in the cascade with nothing to act on. That gap is closed.
`_model_deprecations` at `src/sync/cli.py:577` constructs one adapter per source at line 614 and
collects its rows, and one vendor failing costs that vendor's changes and is printed rather than
swallowed — because an empty answer is indistinguishable from a healthy vendor with nothing
deprecated, which is this document's own rule applied to its own wiring. The Sequencing table's
"Next" row was the wiring; it has been folded into "Done" and the third vendor promoted.

### The Python adapter's alias handling is exercised — `2026-07-29-sync-coverage-baseline.md`

This document, also one day old, named one module to harden and made the case concrete with an
asymmetry: `tests/fixtures/ts/aliased` exists and `tests/fixtures/py/` has no equivalent, so the
Python adapter's alias handling "is written and never read", and "the repair is a fixture, not a
redesign." The repair was made. `tests/fixtures/py/aliased` exists and
`tests/test_python_aliases.py:59` indexes it.

The coverage tables above that paragraph were left alone. They are a measurement pinned to commit
`58257f6` over a suite of 1,468 tests, the same way the ground-truth count is pinned to a date, and
renumbering a measurement this sweep did not re-run would produce something half-updated and
harder to trust than the dated original. See "What could not be verified" for the consequence.

### The remediation graph has a stage the corpus does not list — `2026-07-25-sync-competitive-position.md`

The one repository-adjacent claim in a market document: Sync's remediation graph is "locate,
strategize, patch, static verify, push, await CI, open PR". The previous sweep verified it against
seven conditional edges. There are now eight, and the added one is `replay`. Corrected by naming
it, because the sentence exists to argue that Bits Code's loop is the same loop — and `replay` is
the one stage in it that Bits Code does not have. Nothing else in the paragraph was touched.

### Line references that no longer resolve

Corrected in place, in five files, because the originals name lines and a reader who follows one
to the wrong place trusts the next one less:

| Document | Was | Is |
|---|---|---|
| `2026-07-25-sync-migration-corpus.md` (×2) | `schema.sql:54` | `schema.sql:60` |
| `2026-07-27-sync-benchmark-gates.md` (×2) | `schema.sql:54` | `schema.sql:60` |
| `2026-07-27-sync-benchmark-gates.md` | `nodes.py:340` | `nodes.py:653` |
| `2026-07-26-sync-observed-contract-drift.md` (×2) | `schema.sql:118`, `cli.py:18` | `schema.sql:124`, `cli.py:23` |
| `2026-07-25-sync-latency-architecture.md` | `cli.py:69` | `build_remediator`, `cli.py:119` |
| `2026-07-28-sync-domain-specific-thesis.md` | `cli.py:69` | `build_remediator`, `cli.py:119` |
| `2026-07-27-sync-routing-matrix.md` | `cli.py:69`, `cli.py:541`, `cli.py:557`, `tiered.py:42`, `tiered.py:282` | `cli.py:119`, `cli.py:867`, `cli.py:865`, `tiered.py:43`, `tiered.py:319` |

`schema.sql:54` is now the first line of `migration_outcome`'s grain comment rather than the
table, which is the failure mode worth naming: the reference still lands inside the right block
and points at the wrong thing.

## Every file, and what was checked

### `2026-07-25-sync-competitive-position.md` — corrected

One repository claim, corrected above. Everything else is market fact carrying its own confidence
markers, its own sources, and an expiry rule, and none of it is settleable from a checkout. The
document's `Last verified: 2026-07-25` line still governs.

### `2026-07-25-sync-graph-surface-design.md` — corrected

Beyond the Status line: the three read tools are at `src/sync/mcp/tools.py:88`, `134` and `168`,
`propose_patch` at `193`, and `_envelope` emits `context_savings` at `338`. The response-shaping
rules hold — `_page` paginates, and nothing returns file contents.

Two things in it are still genuinely unbuilt and are named in the new Status line rather than left
implicit. `grep -rn "sqlite" src/` returns nothing, so the Packages table's "add a SQLite
implementation" has not happened and local mode still means Postgres —
`src/sync/mcp/server.py:280` reads `SYNC_DSN` and constructs a `GraphStore`. And `observed`
bindings still require telemetry nobody sends. The `codebase-memory-mcp` moat correction at the
end of the document is about an external project and was not re-checked.

### `2026-07-25-sync-latency-architecture.md` — corrected

One line reference. The two state claims still hold: `build_remediator` returns the
`TieredRemediator`, and `grep -n cache_control src/sync/remediate/agent_patch.py` returns nothing,
so the prompt-cache boundary is genuinely unset. Lever 1 is still unbuilt — `grep -rn "Send("` over
`src/sync/remediate/` returns nothing, so the vendor and repository branches still run in sequence
and there is no fan-out across findings. The reducer landmine, the Nielsen thresholds and the
fast-mode pricing are design statements and were not treated as repository claims.

### `2026-07-25-sync-mcp-drift-measurement.md` — unchanged

A measurement over two external git repositories. The 18-versus-59 release counts, the 135 breaking
changes, and the `get_commit`/`include_diff` instance cannot be re-derived without cloning those
repositories. Its one repository claim still holds: `extract.py`, `go_extract.py`, `drift.py` and
`drift_go.py` are in a session scratchpad and not committed — none appears under `scripts/` or
anywhere in the tree.

One thing changed around it and did not make anything in it false. `src/sync/signals/mcp_server/`
now exists and `sync.signals.registry` will build an `McpServerAdapter` for a configured server.
The document's "Consequences for the plan" asks for a snapshot store holding one row per
`(server, observed_at)`; there is no such table, and the adapter reads captures from disk that
something else wrote. `mcp-servers.yaml` ships with no server configured and says why in its own
comment: watching a server means holding its captures, and nothing here takes one. That is
prescriptive text matching an unbuilt component, not a false claim.

### `2026-07-25-sync-migration-corpus.md` — corrected

Beyond the Status line and the two line references: `MigrationOutcome` is in
`src/sync/core/models.py`, `src/sync/remediate/corpus.py` is installed by `graph.py:22` via
`make_recorder`, and the abandoned-attempt write is real at `nodes.py:653`. The four specified and
unbuilt columns are still absent — `call_site_depth`, `is_wrapped`, `ci_wall_ms` and
`pr_closed_unmerged` — `finding_id` is still `text` rather than `uuid`, `terminal_status` is still
nullable, and the second specified index is still absorbed by `UNIQUE (finding_id,
attempt_index)`. That whole paragraph survives unchanged apart from its line number.

The privacy argument's claims about `symbol_shape`, `arg_key_hashes` and `edit_script` describe
intent for a table with no rows and were not treated as state claims.

### `2026-07-25-sync-positioning-and-open-core.md` — unchanged

Positioning and licensing decisions, none of them about code. The inconsistency the previous sweep
flagged and deliberately did not correct is still there: its Open Items lists the feed's data
licence as undecided while `2026-07-26-sync-public-change-feed.md` decides CC0 and says it is
resolving that item. Left standing for the same reason — reconciling two committed decision
records is outside a state audit — and flagged again so it is not mistaken for something nobody
noticed.

### `2026-07-25-sync-self-maintaining-apis-design.md` — corrected

Beyond the new-file limitation, every other M0 limitation was re-checked and every one holds:

- `sync.index.shipped_tree` and `sync.index.dependency_edits` both exist as modules.
- `run_tsc` prefers `node_modules/.bin/tsc` at `src/sync/index/tsc.py:132`; every install command
  in `src/sync/index/deps.py:25-29` passes `--ignore-scripts`.
- "Nothing in the pipeline applies `patch.diff`" holds: `grep -rn "git apply\|apply_patch" src/`
  returns nothing.
- The push lease reads authorship: `COMMIT_AUTHOR_EMAIL` at `github.py:32`, the range check
  `[remote_tip, "^HEAD"]` at `198`, `--force-with-lease` at `204` and `291`.
- The `x-stableId` verb correction is in `src/sync/signals/stripe/symbols.py`.
- The tree-sitter finding — that a dangling comma parses with zero `ERROR` nodes — is a
  measurement against `tree_sitter_typescript` and was not re-run.

Two things were noticed and left. The Packages table lists eight packages and `src/sync/` now holds
`route`, `benchmark`, `mcp`, `telemetry` and `verify` as well; that table is a design
decomposition rather than an inventory, and the same reasoning the previous sweep gave applies.
And the `sync.cli` row calls it "the only entry point at M0", which is now two console scripts —
but the sentence is scoped to M0 and misleads nobody about the code.

The 105-of-414 coverage figure and the 327,124-record depth measurement both still derive from
`.cache/specs/`, which is gitignored.

### `2026-07-25-sync-threat-model.md` — unchanged

Every line reference still resolves, which is unusual in this corpus and was checked rather than
assumed: `local_tsc` is at `tsc.py:132`, `--package=typescript@latest` at `tsc.py:150`, and
`_TSC_TIMEOUT_SECONDS` at `tsc.py:21`. The `--ignore-scripts` claim is verified above. Mitigation 4
— pinning the fallback compiler — is still not done, which the document's own Finding section
already says.

One new fact bears on it and does not make anything in it false. `src/sync/verify/replay.py`
executes a customer module, which is a second path on which Sync runs customer-adjacent code. Its
own docstring quotes this document's containment argument and enforces four sandbox rules rather
than documenting them — no network, TypeScript run by Node's own type stripping rather than a
transpiler fetched at verification time, and so on. That is the replay spec's boundary claim
("this adds no new execution surface, only new use of one that must exist anyway"), and whether it
holds is a security review rather than a state check. Recorded so that review has somewhere to
start.

### `2026-07-26-sync-observed-contract-drift.md` — corrected

Corrections above. The rest of the document re-checked and still accurate: `MIN_SAMPLES = 30` at
`src/sync/detect/observed_drift.py:66`, `path_ptr=record.get("path", "")` at
`src/sync/signals/oasdiff.py:110`, `changed_field()` at `oasdiff.py:149`, and the admission that
the unpublished-enum case cannot be built as specified still carried in the detector's own
docstring. Both readers still write `source = "error-payload"` deliberately
(`sentry/shapes.py:63`, `datadog/shapes.py:79`).

### `2026-07-26-sync-public-change-feed.md` — corrected

Beyond the Status line and the Sequencing row: `render_feed` (69), `sign_feed` (80) and
`public_key_bytes` (90) are in `src/sync/signals/feed/publisher.py`; `verify_feed` (44) and
`parse_feed` (60) keep the two failures apart in `consumer.py`, and `verify_and_parse` (84) runs
verification first. `FEED_FIELDS` at `publisher.py:45` is still the nine-field allow-list. Its
reference to `2026-07-25-sync-mcp-graph-surface.md` still resolves under
`docs/superpowers/plans/`, not `specs/`.

### `2026-07-26-sync-review-integration.md` — corrected

Beyond the Sequencing preamble: the five adopted mechanisms are read out of Alibaba's repository
and were not re-verified against it. The one Sync-side pending-work claim is still accurate as
pending work — snippet-based positioning is still not in the `locate` node, which reads the stored
call site by `finding.call_site_id` (`src/sync/remediate/nodes.py:103-124`). That is the first row
of the Sequencing table, and it is the only row still outstanding.

### `2026-07-27-sync-adapter-targets.md` — unchanged

The generator mechanism is built exactly as described: `STAINLESS_MANIFEST = ".stats.yml"` and
`SPEAKEASY_MANIFEST = ".speakeasy/workflow.yaml"` at `src/sync/signals/generated/manifest.py:24-25`,
`GeneratedSpecAdapter` at `adapter.py:80`, and `operation_for_symbol` at `101` returning `None` for
the reason the spec gives.

The mismatch the previous sweep recorded rather than edited has got sharper and is still recorded
rather than edited. The Sequencing table schedules "**The `GeneratedSdkAdapter`**" at M1.5 as
future work; not only is the class built and named `GeneratedSpecAdapter`, but four cohort A
vendors are now registered as configuration in `generated-vendors.yaml` — anthropic, openai,
cloudflare and vercel — each confirmed by fetching its manifest path on 2026-07-28, with the four
responses committed under `tests/fixtures/manifests/`. The body states the truth a hundred lines
above the table and the table reads as milestone ordering, so editing it would be reordering a
roadmap rather than correcting a fact. Cohort C's Twilio is likewise built.

Every spec URL, size and endpoint count in the target table was fetched on 2026-07-27 over the
network and cannot be re-checked here.

### `2026-07-27-sync-benchmark-gates.md` — corrected

Three claims corrected above, plus three line references. Everything else holds. Gate tier A still
matches `.github/workflows/ci.yml` line for line, with `OASDIFF_VERSION: 1.26.1` pinned;
`tests/test_lint_encoding.py` still asserts a non-zero exit on a known-bad file, so the
proven-able-to-fail claim is real; and `src/sync/benchmark/axes.py` still computes exactly the
three claimed axes plus the two cost axes, with `Axis.value` `None` rather than `0.0` at zero
samples.

The corpus being empty was not verified: it is a claim about a Postgres instance, not about the
tree.

### `2026-07-27-sync-pipeline-discipline.md` — unchanged

Both cited commits still resolve: `efcc19d fix: include line and col in call_site identity to stop
same-file collisions` and `b29795a fix: resolve the patch prompt's affected field from oasdiff
text, not the URL path`. `VendorChange.raw` is carried at `src/sync/core/models.py:77` and is
published in `FEED_FIELDS`.

The OTLP qualification the previous sweep added still holds in the form it was written. It says
`sync.telemetry.otlp` decodes an export payload, `sync.telemetry.ingest` folds client spans into
`observed_call`, and there is no server, no port and no collector protocol. All three still true —
and `ingest_payload` now has a caller in `sync ingest` (`src/sync/cli.py:1052`), which changes the
"nothing calls it" fact the previous log recorded in its own prose without changing anything this
document claims.

The Verification section's grain requirement is still met by three tables of six. `grep -n "^--
Grain:" src/sync/graph/schema.sql` returns lines 52, 110 and 156 — `migration_outcome`,
`observed_shape`, `observed_call`. `call_site` (1), `vendor_change` (25) and `finding` (39) still
carry none. The gap is in the schema rather than in this document, so nothing was edited, and it
is recorded again because a year of sweeps recording it will not fix it: it is one line per table
and nobody owns it.

### `2026-07-27-sync-routing-matrix.md` — corrected

The "What is built" section rewritten as described above, plus five line references. Everything
else reproduces, including both distribution tables at the pinned oasdiff version. Also re-checked
and still correct: `to_vendor_changes` sets `severity="breaking"` unconditionally
(`oasdiff.py:111`), so preserving oasdiff's level is still undone; the tier-0 codemod modules and
`src/sync/route/templates.py` all exist; `route_after_static` still branches on an explicit
boolean. The `add_conditional_edges` block quoted from `graph.py` is now at lines 69-73 and its
destination map has changed — `{"patch": "patch", "push_branch": "replay", "abandon": "abandon"}`,
where the router's decision and its destination differ deliberately, because `sync.mcp.propose`
reads the same string to establish that a patch is verified. The document quotes the `prepare`
block rather than this one, and that block is unchanged.

### `2026-07-28-sync-deprecation-signal.md` — corrected

Beyond the Status line and the Sequencing table: `operation_for_symbol` returning `None` for every
symbol is still confirmed at `src/sync/signals/deprecations/adapter.py:118`. The measured table
(Anthropic 29 rows, OpenAI 108) and every design decision argued from live vendor pages fetched on
2026-07-28 are not re-checkable without network access.

### `2026-07-28-sync-domain-specific-thesis.md` — corrected

One line reference. Both qualifications in "What this changes about priorities" are still accurate
and both still worth keeping: `edit_script` is declared at `src/sync/core/models.py:168` and `grep
-rn edit_script src/` finds no writer — only the declaration and a docstring mention in
`route/templates.py:12` — so the column the notation was meant to give a type is uniformly null.
`FEED_FIELDS` is still nine fields and none is a migration recipe. Guideline 1's mention of
`FeedCache` was aspirational when written and is now built, which makes the row more true rather
than less.

### `2026-07-28-sync-ground-truth-count.md` — unchanged

Every number is a GitHub search `total_count` from 2026-07-28 and the document says so. Its two
repository claims both still hold: `tests/fixtures/specs/charges_base.json` and
`charges_revision.json` both declare `"version": "base"`, `stripe_v2330_shape.json` has top-level
keys `openapi` and `paths` and no `info` block, and `scripts/mine_stripe_migrations.py` is
committed. The three dated Stripe versions still came from `.cache/specs/`, which is gitignored.

Note for a reader arriving at it fresh: `2026-07-29-sync-ground-truth-quality.md` supersedes its
verdict, and says so in its own scope line. Nothing in the count is wrong; the question moved.

### `2026-07-28-sync-spec-audit-log.md` — deliberately not edited

A dated record of what was true at `19737f7`. Correcting it would destroy the evidence of when each
thing was checked, which is the only thing that makes a sweep worth having. At least eight of its
entries have since gone stale — the `pr_number` gap, `build_remediator` being handed no catalogue,
`DeprecationAdapter` having no construction, the missing `sync-mcp` process, neither shape reader
being constructed, `GraphSurface` having no fourth tool and no `FeedCache` anywhere, `ingest_payload`
having no caller, and `git add -u` refusing a new file — every one of them in the same direction.
Each is corrected in the document it was about rather than in the log. Its qualification that the
local `oasdiff` binary lagged CI's pin at 1.26.0 has also expired; the binary now reports 1.26.1.

### `2026-07-29-sync-adaptive-vendor-substrate.md` — corrected

Corrections above. The four items under "What is already true" were re-checked and all four still
hold: generator-manifest discovery is built, `sync.signals.registry` maps a vendor id to an
adapter as data, the protocol has been tested against Twilio, and a conformance kit exists
(`src/sync/core/conformance.py`, `tests/test_adapter_conformance.py`). The tier table is still
accurate — tier 0 built, tier 1 not started, tier 2 built for Stripe and Twilio, tier 3 partial —
and tier 0 now carries four configured vendors, which makes "a vendor is a row" a demonstrated
claim rather than a design one.

Its arguments about where an agent belongs, the poisoned-symbol-map hole in the threat model, and
the fourth `proposed` rung are design positions and were not audited as state. The `proposed` rung
does not exist in `sync.core`, which is consistent with the document, since it proposes it.

### `2026-07-29-sync-coverage-baseline.md` — corrected

One correction above. The coverage figures themselves were not re-derived — see below. Its other
structural claims were checked and hold: `addopts` in `pyproject.toml` carries `-m 'not e2e'`;
`.claude/rules/test-discipline.md` is the file it names; `src/sync/mcp/server.py`'s `main()` is
the shape it describes, reading `SYNC_DSN` and constructing a real `GraphStore`; and the seven
components it lists as having shipped dead are correctly listed in the past tense — **all seven now
have callers**, checked one at a time: `GraphStore.set_merge_outcome` from `webhook.py:178`,
`sync.route.matrix.route()` from `nodes.py:16` and `tiered.py:43`, `DeprecationAdapter` from
`cli.py:614`, `ingest_payload` from `cli.py:1114`, `synthesize_mock_response` from
`replay.py:277`, `record_merge_outcome` from `cli.py:1192`, and `PythonAdapter` from `cli.py:180`.
That is what makes the sentence about line coverage true rather than false, and it is also the
measure of how much of this corpus's "not wired" language has expired.

Its closing argument — that `scripts/lint_dead_links.py` is the gate that catches this class, not
the coverage number — is confirmed below, and by a defect the lint is currently reporting.

### `2026-07-29-sync-ground-truth-quality.md` — unchanged

Every claim is about GitHub, read through `scripts/read_stripe_migrations.py`, which is committed.
The 117 commits, the authorship trailers, the five hand-read candidates and the ten-repository
path survey are all network facts recorded with their date, and none is re-derivable here without
breaking the house rule against calling a vendor API in a test.

Its recommendation was taken: `src/sync/benchmark/mutate.py` is the synthetic-mutation generator,
and its module docstring cites this document's verdict as the reason it exists. That is a
recommendation followed rather than a claim that changed.

## Where a spec and the dead-link baseline disagree

`scripts/dead_links_baseline.txt` accepts exactly one entry —
`src/sync/route/templates.py:omit_property_at` — with a paragraph explaining why wiring it would be
an off-by-one and a collapsed distinction. That entry still describes something real, and the file
is otherwise in agreement with the corpus everywhere the two overlap: it is silent on
`GraphStore.set_merge_outcome` and `sync.route.matrix.route()` because both were wired, and it is
silent on `DeprecationAdapter`, `ingest_payload`, `record_merge_outcome`, `synthesize_mock_response`
and `PythonAdapter` for the same reason.

**The lint is currently failing, on source this sweep did not touch and does not own:**

```
src\sync\benchmark\mutate.py:121: generate_pair (function) is reached from nowhere in the scanned tree
src\sync\benchmark\mutate.py:198: depends_on_change (function) is reached from nowhere in the scanned tree
2 public symbol(s) nothing reaches, or opting out without a reason.
```

Both are exported from `src/sync/benchmark/__init__.py` and called only by tests. That is the eighth
instance of the pattern `2026-07-29-sync-coverage-baseline.md` lists seven of — a component
finished, tested, and reachable from nothing — arriving in the commit at the head of this branch,
`0613da2`, which is the commit that added it.

It is also the disagreement the audit brief asked for. The benchmark spec now says binding
precision and recall lack a corpus of labelled pairs; the lint says the thing that would produce
those pairs is not reachable from anything that runs. Those are the same fact seen from two sides,
and the spec's version is the one this sweep wrote, so the corrected text and the lint agree. What
does not agree is the baseline file, which does not carry these two entries — correctly, because
adding a line to it "says a component is finished, tested, and reachable from nothing, and that
somebody accepted that on purpose", and nobody has. The right resolution is a caller, not a
baseline entry, and it is not this sweep's to make.

## What could not be verified, and why

Grouped by the reason, because the reasons differ in what would fix them.

**Nothing exists to check.** The feed's hosting and its CDN; the production Ed25519 keypair, of
which only a development public key is committed and by design; the hosted control plane, its
dashboard and its per-repository policy; the SOC 2 observation window; the credential-free
verification sandbox the threat model gates M1 on; a customer. No query settles these because
there is nothing yet to query, and every document that mentions them already says they do not
exist.

**It is a network fact.** Every vendor spec URL and size in the adapter-targets table; the
`.stats.yml` hashes and endpoint counts for eleven SDK repositories; the four manifest paths
confirmed on 2026-07-28 for `generated-vendors.yaml`; the Anthropic and OpenAI deprecation-page row
counts; every GitHub search total in the ground-truth count and every commit read in the
ground-truth quality reading.

**It is a market fact.** Everything in the competitive-position document, the acquisition record,
the pricing, the merge-rate studies, and the MCP drift measurement over two external repositories.

**It is a database fact.** That `migration_outcome` and `observed_shape` hold no rows is asserted
by five documents and was not confirmed against a running Postgres. It is consistent with what the
tree shows — no scheduled writer for either, and both fed only by commands an operator runs — but a
checkout cannot settle it.

**It derives from a gitignored cache.** The 105-of-414 symbol coverage, the 327,124-record depth
measurement, and the three dated Stripe versions all read `.cache/specs/`.

**It is a measurement this sweep declined to re-run.** The coverage baseline's figures — 95.71% of
4,916 statements, 211 missed across 84 files, at commit `58257f6` over 1,468 tests — describe a
tree 105 commits behind this one and a suite roughly 300 tests smaller. Its per-module line
citations have moved with the code: `src/sync/index/python_lang.py:206-210` is now a set
comprehension inside `_bindings_for` rather than the aliased-import handling the document
describes there. Renumbering those without re-running `pytest --cov` would produce a measurement
that is half from one tree and half from another, which is worse than a dated one. The document
already pins its commit and its test count; a reader should treat the line ranges as pinned to
`58257f6` too. Re-running the measurement is a task, not an audit correction.

**It is a security property rather than a state.** Whether `src/sync/verify/replay.py`'s four
sandbox rules actually contain what they claim to contain — no network, no lifecycle scripts, no
credential in the environment — is a review of enforcement, not a check of existence. The
enforcement exists and has tests; whether it is sufficient is not a question a grep answers.

## The caveat this document inherits, and why it is not boilerplate

The previous log recorded that a claim verified in it could go stale, and it went stale within one
commit: the audit said the routing table's catalogue was unwired, and the wiring landed one commit
later.

This sweep was measured against `0613da2`. Work is landing on `main` in parallel while it is being
written, and the `docs/superpowers/reports/` directory already holds a report describing a change
whose consequences reach two of the files corrected above. Twenty-eight substantive claims went
stale in 105 commits — roughly one every four commits, and every one of them in the direction of
understating what exists.

The practical form of that warning: **if you are about to build something a spec here says is not
built, grep for it first.** The corpus's failure mode is not making things up. It is falling behind.

## Gates

Run against the tree after the edits above, all of which are documentation. No file outside
`docs/superpowers/specs/` was modified.

- `uv run pytest -q` — **1 failed, 1557 passed** in 100.53s. The failure is
  `tests/test_lint_dead_links.py::test_the_repository_matches_its_baseline`, which is the suite's
  half of the dead-link gate described above and fails on the same two symbols. It is pre-existing
  at `0613da2`; nothing in this sweep touches `src/`, `tests/` or `scripts/`.
- `uv run python scripts/lint_encoding.py src scripts tests` — clean.
- `PYTHONIOENCODING=utf-8 uv run lint-imports` — `sync.core depends on nothing KEPT`. Contracts: 1
  kept, 0 broken.
- `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` —
  **fails**, on the two `src/sync/benchmark/mutate.py` symbols described above.

Two notes on the suite count, since a count is the cheapest thing to misread. It is 1,558 tests
rather than the 1,767 this sweep was told to expect, so either a branch measured a different tree
or work has since been rebased out; that is a fact about the dispatch rather than about this
corpus, and it was reported rather than investigated. And a red suite at the head of a branch is
itself the strongest possible evidence for the dead-link finding above: the defect is not merely
lint-visible, it fails the build.

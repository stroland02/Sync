# The rung a finding rests on, and the surface that reported a different one

M3-W109. `finding.binding_rung` became an enforced column in B65/B66 and the four tools an
agent talks to kept answering `binding_source: "static"` for every finding they returned.
M3-W107 found that and pinned it across four rungs without repairing it, because its brief did
not own the decision; `docs/superpowers/reports/2026-07-30-mcp-tool-surface-declines.md` is that
record. This is the repair, and the part worth reading is not the fix but where the field turned
out to belong.

## Which rungs reach each tool, measured rather than argued

All four tools read findings through exactly one method, `GraphStore.open_findings`, and its
query carries no rung predicate:

```sql
SELECT finding.* FROM finding
  JOIN call_site ON call_site.id = finding.call_site_id
 WHERE finding.status = 'open' AND call_site.retracted_at IS NULL
 ORDER BY finding.created_at
```

So whatever a detector writes, a tool reads. The measurement was taken by wrapping
`Finding.__init__` to record the constructing frame together with `binding_rung`, and running the
whole suite under it — `uv run pytest -q -p no:randomly` at the repository's own `-n auto`,
2580 passed and 4 skipped, the baseline unchanged by the probe. Every rung below is a value a
detector actually produced or the store actually read back, not one the types permit.

| Construction site | Detector | Rungs it produced |
|---|---|---|
| `vendor_change.py:156` | `vendor_change` | `static` |
| `parameter_deprecation.py:98` | `parameter-deprecation` | `static` |
| `observed_drift.py:180`, `:223` | `observed-drift` | `static` |
| `efficiency.py:187` | `efficiency` | `observed`, `unresolved` |
| `status_rate.py:249` | `status-rate` | `observed`, `unresolved` |
| `store.py:515` — `Finding(**row)` inside `open_findings` | — | `static`, `observed`, `unresolved`, `unattributed` |

The last row is the answer to the brief's question. `sync_whats_at_risk`,
`sync_explain_call_site` and `sync_propose_patch` all draw their findings from that statement, so
each of them can be handed `static`, `observed`, `unresolved` or `unattributed`.
`sync_whats_changed` reads no finding at all — it answers from `all_vendor_changes` — so no rung
reaches it and none can.

**`resolved` reaches nothing, and that is the only part of the old argument that survives
intact.** No binder emits it: there is no compiler pass in this repository, so
`resolved` appears at no construction site and in no row. The spec's rule that a response with no
compiler pass must not claim `resolved` is therefore still kept, and kept by the same mechanism
as everything else here — the surface reports what the graph recorded.

**So this was a live wrong answer, not a contract gap.** Two of the five detectors raise their
claims from watched traffic. An agent asking `sync_whats_at_risk` on a repository with telemetry
configured was told a span-to-operation correlation was a syntactic match, in the direction that
matters: `observed` is the rung the spec says an agent trusts most, and `static` is the one it
discounts.

## One response can carry several rungs, so the field was in the wrong place

This is the question that decided the shape, and the answer is yes for one tool and no for
another.

`sync_whats_at_risk` returns a page built from every open finding that passes the filters. A
repository with telemetry has vendor-change findings resting on a static read and status-rate
findings resting on a correlation, and both appear on the same page. No single envelope value is
true of both of them, so an envelope-level `binding_source` was not holding the wrong value — it
was in the wrong place. `sync_explain_call_site` has the same property one level down: two
detectors can name one call site, and the call site itself carries no rung, because `CallSite` has
no such field.

`sync_propose_patch` is the opposite case, and it is what makes the distinction sharp rather than
a blanket rule. It answers about exactly one finding, so its whole response rests on exactly one
binding and the envelope is the right place for the rung.

What landed:

- **Per row on `sync_whats_at_risk`.** Each item carries `binding_source`, the stored rung of the
  finding that produced it. This is a response-shape change; see below.
- **The envelope speaks only when the answer agrees.** `_shared_rung` returns the single rung when
  every finding behind the answer names the same one, and `None` otherwise. An agent that reads
  only the envelope gets a correct value in the common case and a null that means "ask the rows".
- **Not the weakest rung.** Reporting the lowest rung on a mixed page never over-claims, and it
  was rejected anyway: understating is still a wrong answer about the rows carrying a stronger
  one, and `CLAUDE.md`'s rule is attribution rather than caution. A false positive an agent was
  told rested on a static read cannot be attributed to the correlator that produced it.
- **The envelope describes the answer, not the window.** `indexed_at` was already folded over
  every matching finding rather than over the page, and the second provenance field follows it.
  Page one of a mixed result declines even where the rows it happens to carry agree, so the value
  does not depend on where an agent happened to page.
- **`sync_whats_changed` reports null unconditionally,** for the reason its `indexed_at` is
  already null: the payload holds no binding, and naming a rung would claim a mapping had been
  established for an answer in which no mapping appears.
- **`sync_explain_call_site` now reads every finding that names the line** instead of returning at
  the first match. The rung is a property of all of them, not of whichever the graph returned
  first.

## What an `unattributed` row surfaces as

`unattributed`, verbatim, at both levels.

`GraphStore.insert_finding` refuses it on the way in, and rows written before the column existed
carry it on the way out — the column is `NOT NULL DEFAULT 'unattributed'`, and `FindingRung` is
`BindingRung` plus that one member for exactly this reason. The measurement above shows
`open_findings` returning it, so this is a state the surface meets rather than a hypothetical.

Folding it into the same `None` that means "the rows disagree" was the alternative and it is the
flattening this repository keeps rejecting. Those are two different facts: one says the graph
holds a rung and the rows do not share it, the other says the row predates attribution entirely.
An agent that cannot tell them apart cannot tell which of them is repairable. Publishing the
stored value costs nothing and invents nothing — `unattributed` is not a fourth rung and nothing
here treats it as one; it is a value `sync.core` already defines and the graph already records.

`test_a_row_written_before_the_column_existed_surfaces_as_unattributed` drives it through a real
`GraphStore`: the row is written normally and then reset to the column's own `DEFAULT`, which is
how history produced the value in the first place, and the assertion is on the tool's row.

## What changed in the `binding_source` docstring

The docstring at `tools.py` argued:

> `binding_source` is `static` throughout, and honestly so: `resolved` requires a compiler pass
> and `observed` requires production telemetry. Neither runs here, and claiming either would
> assert a trustworthiness nothing supports.

**That argument was sound when it was written, and it is not being corrected.** When it was
written the only binder was the static one, and every clause of it was true. What the replacement
records is that a precondition changed, not that someone reasoned badly:

- two of the five detectors now raise findings from watched traffic, so "neither runs here" no
  longer holds for `observed`;
- `finding.binding_rung` is an enforced column rather than a hint, so the answer exists to be
  reported;
- `open_findings` returns four distinct values, measured.

The claim the old text was defending — never assert a rung nothing established — is preserved and
now rests on something stronger than a constant. The new text says where null comes from and why
absent provenance is preferred to a smoothed one. `_shared_rung` carries the argument against
reporting the weakest rung, next to the code that would otherwise be the obvious place to put it.

## The golden file could not have caught this, and that is the hazard

`tests/golden/tool_schemas.json` stores `name`, `description` and `inputSchema` for each of the
four tools and nothing else — `schemas_as_data()` emits exactly those three keys, and there is no
`outputSchema`. So the published freeze covers the **request** half of the contract only. Adding
`binding_source` to a row and turning an envelope value null left that file byte-identical, and
`test_every_response_carries_the_provenance_fields` asserts a subset with `<=`, so it passed
through the change as well. W107 measured this and called it a permission and a hazard at once;
using the permission is what makes the hazard live.

**So the shape is asserted directly.**
`test_the_response_shape_is_pinned_here_because_the_golden_file_cannot_see_it` compares the exact
key set of each of the three read tools' payloads, of a `sync_whats_at_risk` row and of a
`sync_whats_changed` row. An added, removed or renamed response field fails it. The mutation
table below includes the check that this is not decorative: adding a second provenance key to the
envelope is killed by that test and by nothing else.

**The golden file did not move.** sha256 of the raw bytes, unchanged from W107's figure and taken
by the mutation harness before its first run and after its last:

    7070b152ee3ddd24e23144022704495b05451865568505c1a71ff253e23997fe

`test_the_published_tool_contract_is_byte_stable` in `tests/test_mcp_resources.py` pins the
canonicalised digest, `b69c020883a894c2e4174b5a2c6a7bc68a93eb3fdfb3175950631acf26b36352`, and
`test_adding_a_resource_leaves_all_four_tool_schemas_untouched` pins the equality. Neither moved,
and nothing in this task touches `registry.TOOLS`.

## Mutation table

Harness at `%TEMP%\w109\w109_mutate.py`, not committed. Focused runs over the ten `tests/test_mcp_*`
files under `uv run pytest -q -p no:randomly --color=no -n0`; baseline 180 passed. The whole-suite
figures quoted elsewhere in this report used the repository's own `-n auto`.

| Statement | Mutation | Outcome | Killed by |
|---|---|---|---|
| — (control) | a word changed in `_envelope`'s docstring | **SURVIVED** at exactly 180 | — the harness is not blind |
| — (control) | `_TOKENS_PER_AVOIDED_READ` → `0` | **KILLED**, 2 failed | `…reports_context_savings`, `…provenance_and_context_savings_like_every_other_tool` |
| — (control) | unbalanced paren in `DEFAULT_LIMIT` | **DID-NOT-COMPILE** | `compile()`, before pytest ran |
| row field | `finding.binding_rung` → `"static"`, the old constant | **KILLED**, 9 failed | `…surfaced_provenance_is_the_rung_it_was_stored_with` (×4), `…page_holding_two_rungs…`, `…written_before_the_column_existed…`, `…one_flattening_in_this_file_that_was_repaired` (×3) |
| row field | the field deleted | **KILLED**, 14 failed | the nine above plus `…invents_a_rung_the_graph_did_not_record`, `…speaks_for_the_answer_and_not_for_the_window`, `…response_shape_is_pinned_here…`, and the `static` cases |
| row field | → `site.vendor_id`, a value that is not a rung | **KILLED**, 13 failed | as above, less the shape test — the key is still there |
| row field | `unattributed` folded into `None` | **KILLED**, 2 failed | `…is_the_rung_it_was_stored_with[unattributed]`, `…written_before_the_column_existed_surfaces_as_unattributed` |
| `_shared_rung` | → `return "static"` | **KILLED**, 16 failed | every envelope test across the three read tools, including `…never_claimed_higher_than_it_was_established` |
| `_shared_rung` | → pick one when they disagree | **KILLED**, 3 failed | `…page_holding_two_rungs…`, `…explain_call_site_declines_when_two_findings_disagree…`, `…speaks_for_the_answer_and_not_for_the_window` |
| `_shared_rung` | → the weakest rung when they disagree | **KILLED**, 3 failed | the same three — which is what makes the choice against understating a tested decision rather than a preference |
| `_shared_rung` | → `return None` always | **KILLED**, 17 failed | every unanimous-envelope case on all three read tools |
| `whats_changed` | `binding_source=None` → `"static"` | **KILLED**, 2 failed | `…reports_no_binding_source_because_it_reports_no_binding`, `…carries_the_provenance_fields[changed]` |
| `explain_call_site` | `_shared_rung(...)` → `matched[0][0].binding_rung` | **KILLED**, 1 failed | `…declines_when_two_findings_disagree_about_one_line` |
| `propose_patch` | read-only branch → `"static"` | **KILLED**, 4 failed | `…reports_the_rung_of_the_one_finding_it_answers_about` (×4) |
| `propose_patch` | wired branch → `"static"` | **KILLED**, 4 failed | `…a_verified_patch_reports_the_rung_the_finding_it_patches_rests_on` (×4) |
| `_envelope` | ignores its argument, reports `"static"` | **KILLED**, 26 failed | the whole set |
| `_envelope` | grows a second `binding_rung` key | **KILLED**, 1 failed | `…response_shape_is_pinned_here_because_the_golden_file_cannot_see_it` |

Seventeen mutations, no survivals other than the intended control, and the two `propose_patch`
rows are why both of its `_envelope` calls are separately covered — a single test would have left
one of them free. The golden digest was identical before the first run and after the last, and
the harness re-established the 180-pass baseline afterwards.

### False-verdict modes

All six the brief names are guarded, and two were exercised:

- **Colourised summaries.** `--color=no`, and the verdict is read from pytest's summary counts,
  never from a `FAILED ` line prefix. Line prefixes are used only to name which tests failed, and
  only after the count has already decided the verdict.
- **A flag collision reading as a clean run.** Any exit code other than 0 or 1 is UNREADABLE, not
  a survival.
- **A `SyntaxError` mutation arriving as `ERROR`.** `compile()` runs on the mutated source before
  pytest is invoked. **Exercised** by the third control, which reported DID-NOT-COMPILE and never
  reached pytest.
- **Decoding versus arriving bytes.** `PYTHONIOENCODING=utf-8` in the child environment decides
  which bytes arrive; `errors="replace"` decides only how the harness reads them.
- **`pytest -q; echo $?` reporting `echo`'s status.** `CompletedProcess.returncode` is read
  directly and no shell reports on pytest's behalf.
- **A skipped test exiting 0 from the child.** A pass count other than the baseline is
  BASELINE-DRIFTED rather than SURVIVED.

A seventh was added, because the brief's rule is to suspect the mutation first: a mutation whose
`old` text is absent or appears more than once is reported NOT-APPLIED rather than run. A typo
there is otherwise indistinguishable from a survival, and every mutation in the table above
applied exactly once.

## Verification

Four gates, all exit 0. `uv run pytest -q` unpiped at the repository's own `-n auto`: **2613
passed, 4 skipped**, against a 2580-pass baseline measured on the same tree before the change —
the 33 added tests are 28 in `tests/test_mcp_provenance.py` and the five parametrised cases of
`test_a_verified_patch_reports_the_rung_the_finding_it_patches_rests_on`. Then
`uv run python scripts/lint_encoding.py src scripts tests`, `PYTHONIOENCODING=utf-8 uv run
lint-imports` — one contract, `sync.core depends on nothing`, KEPT — and
`uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt`.

## Two follow-ups this task does not own

- **`docs/integrations/opencodereview/rules/sync-api-surface.md:6`** tells a reviewing agent "if
  `binding_source` is `static`, say that the mapping is derived rather than observed". That rule is
  still correct and is now incomplete: the field can be `observed`, `unresolved`, `unattributed` or
  null, and the null has two causes worth different wording. `2026-07-26-sync-review-integration.md`
  carries the same sentence. Outside this brief's file list.
- **`2026-07-25-sync-graph-surface-design.md`** describes `binding_source` as a three-rung ladder.
  The graph has had four rungs since `unresolved` shipped and five values since the column got a
  default, and the surface now publishes what the graph holds. The spec is under
  `docs/superpowers/specs/`, which this brief forbids.

Neither is a change to the graph query. `open_findings` already returns the column and needed no
edit, so this task has no handoff into `src/sync/graph/`.

# Console prose audit: API Services, Remediation, Settings

Read against the tree at the time of writing. Nothing here was edited — this is a read of what the
three screens assert, checked against the payloads behind them and against what each screen
actually renders now.

The defect class is `M14-W363`'s: **prose can be falsified without a word of it changing, by moving
what it points at.** Nine findings below. Four are locational referents that have gone stale; four
are claims the payload cannot support; one is a liveness word on a run nothing is polling.

## Scope

| Screen | Route | Files read |
|---|---|---|
| API Services (list) | `/repositories/:repoId/vendors` | `features/vendors/repository-vendors-page.tsx` |
| API Services (detail) | `/vendors/:vendorId` | `features/vendors/vendor-page.tsx`, `vendor-findings-table.tsx`, `vendor-changes-table.tsx` |
| Remediation | `/findings/:findingId`, `/workflow`, `/workflow/pull-request` | `features/findings/finding-page.tsx`, `remediation.ts`, `features/workflows/*`, `features/pullrequests/*` |
| Settings | `/settings` | `features/settings/settings-page.tsx`, `adapter-table.tsx` |

None of the nine sentences is one of the protected twenty-four
(`plans/2026-08-05-sync-console-architecture.md:102-207`). Three of them sit on an axis two
protected sentences hold, and that is named per finding. No repair below deletes, shortens,
collapses or tooltips any sentence.

---

## A. The superseded-generations cluster — three on-screen sentences point at a table no screen mounts

`GET /api/workflows/{finding_id}` gained a `generations` array. `sync/dashboard/queries.py:196-218`
builds it, `api/types.ts:340-346` declares `GenerationSummary`, and
`features/workflows/superseded-generations.tsx` renders it on the Solution Workflow at
`workflow-page.tsx:384-387`. Three sentences written before that still describe the old limit, and
each sends the reader to **the fleet's runs table, which is mounted nowhere.**

`RunsCard` is declared at `features/fleet/runs-table.tsx:87` and has zero non-test importers. The
Fleet screen at `/` mounts `FleetFacts`, `CodebasesPanel`, `RungUpgradeCard`, a `FactTile` and
`ScreenLimitsCard` (`fleet-page.tsx:105-142`) and no runs panel. The Codebase screen states its own
refusal to mount one (`codebase-page.tsx:50-57`, blocked on `B149`).

### A1 — `features/workflows/workflow-page.tsx:239-244` (on screen, rail, "Generations")

> This is the most recent of {n} runs the checkpointer holds for this finding. **The fleet screen**
> lists every one.

Protected: no. False twice — the fleet screen lists no runs, and *this* screen already lists the
earlier generations in its own content column.

**Minimal repair.** Point at the panel that is on the page:
`…the checkpointer holds for this finding. The earlier ones are listed under Superseded generations
below.` Drop the `<Link to="/">`.

### A2 — `features/pullrequests/pull-request-page.tsx:190-199` (on screen, rail, "Generations")

> …An earlier generation may have reached a pull request even where this one has not; **the codebase
> overview** lists every one.

Protected: no. False for the same reason. This page renders no generations panel, so the honest
target is the solution workflow, which does — the link already exists at `:256-262`.

**Minimal repair.** Repoint the link to `/findings/{id}/workflow` and change three words: `…the
solution workflow lists every one.` The qualification it carries ("An earlier generation may have
reached a pull request even where this one has not") is the load-bearing half and stays verbatim.

### A3 — `features/findings/finding-page.tsx:130-133` (on screen, rail, "Remediation")

> The newest of {n} runs on this finding. The others are rows on **the fleet's runs table**; **this
> level can see only that they exist.**

Protected: no. False twice, and the second clause is the interesting one: `useWorkflow` at
`finding-page.tsx:285` already hands this level `data.generations`, carrying each earlier run's
`outcome`, `abandon_reason` and `report_reason`. The sentence claims a blindness the payload
retired.

**Minimal repair.** `The newest of {n} runs on this finding. The solution workflow lists the earlier
ones.` The workflow link is already built at `:348-352`.

### A4-A6 — the same retired limit, in three docstrings

- `api/types.ts:335-337` — "`sync.dashboard.fleet.runs` is the query that lists every generation as
  its own row, which is why a reader who wants the others goes there rather than to a link this
  route cannot serve." This route now serves them. **Second defect in the same block:** it is the
  doc-comment for `WorkflowState`, but `GenerationSummary` was inserted between it and the interface
  (`types.ts:338-346`), so it now documents the wrong type.
- `features/findings/remediation.ts:5-9` — "the number is the only part of the other threads this
  route can see."
- `features/workflows/workflow-page.tsx:25-30` — "a superseded generation is not reachable from it
  (B124) — `GET /api/workflows/{finding_id}` answers with the newest thread only. The rail says how
  many generations there are and where the others are listed, which is what the payload supports."
  All three clauses are retired.

**Minimal repair.** Restate each to what the payload does: the route answers with the newest thread
in full and a summary row per generation beside it; `B124` is closed and should be marked so rather
than left as a standing limit three files repeat.

---

## B. A liveness word on a run nothing is polling — `features/workflows/superseded-generations.tsx:51`

```tsx
{gen.outcome ?? <Absent>in flight</Absent>}
```

Protected: no. It contradicts the axis two protected sentences hold — "staleness is not liveness"
(`runs-table.tsx:114-123`) and the four-kinds-of-nothing rule (`states.tsx:3-6`).

`sync/dashboard/queries.py:200` sets a generation's `outcome` to `None` in **two** different cases:

```python
t_outcome = t_values.get("outcome") if t_values.get("outcome") in _FINISHED else None
```

with `_FINISHED = ("opened", "abandoned", "reported")` (`queries.py:48`). So `null` means either *no
terminal outcome was recorded* or *an outcome outside the vocabulary was recorded* — `"running"`, or
anything the remediation graph has grown since. The screen renders both as the words **in flight**,
about a run that is by construction superseded, that nothing polls, and that no checkpoint can
distinguish from one that died. It is also the unknown-outcome fold that `run-outcome.tsx:169-172`
and `finding-page.tsx:144-146` each refuse by name.

**Minimal repair.** `<Absent>no terminal outcome was recorded for this generation</Absent>`. No
liveness word, and it is true of both cases the payload collapses.

---

## C. A caption falsified by the panels under it — `features/pullrequests/evidence-bundle.tsx:133`

> No pull request exists for this run. Routing decided no patch was warranted, so **nothing below was
> attempted** — the reason it decided that is in the panel above.

Protected: no.

`Framing` renders unconditionally for `reported` (`:128-141`). But `EvidenceBundle` only swaps in
`NothingAttempted` when `outcome === "reported" && !anyEvidence` (`:180-184`). On a `reported` run
that *does* carry evidence — precisely the state the `!anyEvidence` guard exists to separate — this
sentence sits directly above five stage panels rendering recorded evidence from the run. The screen
contradicts itself two elements apart.

**Minimal repair.** Pass `anyEvidence` into `Framing` and split the `reported` branch: keep the
current sentence for `!anyEvidence`, and for the other case say what is true — `No pull request
exists for this run: routing decided no patch was warranted. What is below is however far the run
got before that decision.`

The trailing clause "the reason it decided that is in the panel above" is **true and needs no
change**: `pull-request-page.tsx:312-319` renders `RunOutcome` above `EvidenceBundle`, and its
`reported` branch carries "Reason it reported" (`run-outcome.tsx:153-164`).

---

## D. The narrative is *in* the rail, not beside it — `features/workflows/workflow-page.tsx:193-194`

> The run's own facts, **in the rail beside the narrative.**

Protected: no. This is the exact `W362`/`W363` shape: correct words about a screen that moved under
them.

`workflow-page.tsx:294-335` puts `FactList`, the pull-request link **and** the "Node by node"
`MetricPanel` wrapping `NodeSequence` (`:316-331`) all inside `DetailGrid`'s `rail`. The content
column (`:337-390`) holds `FetchedAt`/`StaleBanner`, `ActivityTimeline` and `SupersededGenerations`.
`DetailGrid` defaults to `railSide="start"`, whose shape is
`lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]` (`detail-grid.tsx:18`, rail rendered first at
`:37-41`).

So the eight-node narrative — which `workflow-page.tsx:7` calls the thing "everything else in this
console exists to get a reviewer" to — renders in the 360px column, and the activity list gets the
wide one. Nothing is beside the narrative; the facts are above it inside the same column.

Both sibling detail levels do the opposite, and one of them says so truthfully:
`pull-request-page.tsx:109` ("in the rail beside the evidence") is correct because
`:251-322` keeps the bundle in the content column, and `finding-page.tsx:156` is correct for the same
reason (`:332-441`).

**Two repairs, and they are not equivalent.**

1. *Preferred.* Move the "Node by node" panel out of `rail` and into the content column, above
   `ActivityTimeline`. The sentence then becomes true again with no word changed, and the screen's
   subject gets the frame the other two detail levels give theirs. This also restores what
   `finding-page.tsx:17-22` records as the settled detail shape.
2. *If the placement is deliberate.* Change the sentence, not the layout: `The run's own facts,
   above the narrative in the rail.` Then also revisit `node-sequence.tsx:190` ("a marker in the rail
   on the left"), which is true of the entry's own `grid-cols-[auto_1fr]` (`:205`) but now collides
   with `DetailGrid`'s meaning of "rail" on the same screen.

Repair 1 is what `.claude/rules/console-surface.md`'s "restyling one is allowed, moving one is not"
posture points at: the sentence is the record of an intent, and the layout is what drifted.

---

## E. The API Services list states a grain its payload cannot answer

`repository-vendors-page.tsx:47` reads `useOverview(repoId)` → `GET /api/overview?repo_id=`. Its
`vendors` field is `store.open_findings_vendor_counts` (`graph_views.py:570-577`), which is a
`GROUP BY call_site.vendor_id` over `finding JOIN call_site` under the open-findings predicate
(`graph/store.py:1146-1158`). **A vendor INDEX bound with no open finding produces no row.**

Three renderings claim a wider grain:

| # | Where | Sentence | Protected |
|---|---|---|---|
| E1 | `repository-vendors-page.tsx:143-147` (under the table) | "This list is what INDEX bound in this repository." | no |
| E2 | `repository-vendors-page.tsx:104-107` (empty state) | "No vendor is attached to this repository. / A vendor appears here once INDEX finds a call site binding this repository to it." | no — but it is the *absence apart from zero* distinction, which is |
| E3 | `lib/routes.ts:149-150`, rendered by `PageHeader` | "Which API vendors does this repository call, and how much is open against each?" | no |

E2 is the sharpest: a repository with call sites bound to three vendors and nothing open renders
**"No vendor is attached to this repository"** — a confirmed zero of *findings* reported as an
absence of *vendors*. The docstring at `:2` carries the same overclaim.

**Corroboration from inside the file.** The zero branch at `:132-134`
(`open_finding_count === 0 ? "No open findings"`) is unreachable: a `GROUP BY` never emits a zero
row. So the comment at `:128-130` — "A confirmed zero is an answer about this vendor and renders as
words" — defends against a state the payload has already made impossible. That is the same grain
error read from the other end.

**And the console already says the true grain, on the other screen reading the same payload.**
`layouts/scope-switchers.tsx:16` ("the vendor list is *vendors with an open finding*, so a vendor
with none is a real address the list…"), `:296` ("Every vendor with an open finding"), `:297` ("A
vendor with none is still reachable at its own address"). Two screens disagreeing about one
payload's grain is what `CLAUDE.md` names as *a fact written twice will disagree with itself* and
`.claude/rules/console-dev-loop.md` names as *a rule the payload can answer belongs in the payload,
so two screens cannot disagree about one fact.*

**Minimal repair — no new route, no new level, nothing lengthened.**

- E3 question → `Which API vendors does this repository have open findings against, and how many?`
- E1 → `This list is every vendor with an open finding in this repository. A vendor INDEX bound with
  nothing open has no row, because this answer is grouped over findings rather than over call sites —
  that is a limit of this query, not a statement that the vendor is unused.`
- E2 headline → `No vendor has an open finding in this repository.` Detail → `That is not the same
  as no vendor being attached: this list is grouped over open findings, so a vendor INDEX bound with
  nothing open is not shown here.`

The wider list an "API services this repository calls" heading would need is
`/api/repositories/{repo_id}/coverage` (per-vendor call-site counts, `graph_views.py:249-257`), which
carries no operations and is blocked by `B147`. **Say that limit; do not close it here.**

---

## F. The scope echo is fetched on the vendor detail screen and never checked

`VendorFindingsPage` carries `repo_id` (`api/types.ts:186-187`). `graph_views.py:407-409` states why
it exists:

> `repo_id` is echoed back rather than left to the caller's memory. A payload that names the scope it
> was computed in cannot be rendered under the wrong heading silently, which is the failure mode this
> whole scoping exists to close.

`vendor-findings-table.tsx:22-25` repeats the claim on the console side. **No render site reads
it.** Every scope sentence on the screen is built from the URL:

- `vendor-findings-table.tsx:264` — chip `countScope`
- `:319` — the metric unit, `open findings in {repoId}`
- `:333` — the caption, `in {repoId}, and in no other repository`
- `:196-197` — the empty-state headline
- `:424` — the footer's filtered-total caveat
- `vendor-page.tsx:99-113` — the fact list's two scope rows; `:147` — the lead paragraph

Protected: no — it is the brief's own stated rule, and the sibling API Services route already obeys
it (`repository-vendors-page.tsx:86` computes `scopeMatches`, `:93-102` refuses).

**Minimal repair.** Derive `const scopeMatches = page.repo_id === repoId` once and refuse in the same
shape `repository-vendors-page.tsx:93-102` uses, rather than rendering rows under a heading the
answer does not name.

---

## G. `?repo_id=` renders a confirmed zero attributed to a repository the screen cannot name

`vendor-page.tsx:83` takes `searchParams.get("repo_id")`, which returns `""` — not `null` — for
`?repo_id=`. `client.ts:97-104` forwards any value that is not `undefined`, so `repo_id=` reaches
`app.py:229` as `""`. Every branch on the screen tests `repoId === null`, so `""` takes the
*narrowed* path throughout:

- `vendor-page.tsx:104` — an empty repository chip in the fact list
- `:147` — `Open findings for stripe in  alone.`
- `vendor-findings-table.tsx:319` — `0 open findings in `
- `:333` — `in , and in no other repository`
- `:196-197` — `No open findings for stripe in .`

Protected: no. Reachable only by a hand-edited URL today. But `finding-page.tsx:270-271` states the
governing rule — "A URL is user input, so the identifier is checked here rather than assumed" — and
`vendor-page.tsx:82` checks `vendorId` and not this.

**Minimal repair.** `const repoId = searchParams.get("repo_id") || null` at `vendor-page.tsx:83`. One
character of change closes every sentence above.

---

## H. Settings: a caption narrower than its own table's grain — `settings-page.tsx:74-78`

> **Every adapter this deployment registers**, beside what the graph has received from it.

Protected: no.

`sync/dashboard/adapters.py:adapter_inventory` is a **full outer join**, and its own module docstring
says so: registered adapters, *plus* one row per vendor id the graph holds history for that nobody
registers any more (`kind: "unregistered"`, `source: None`). The table's empty state names both
halves correctly (`adapter-table.tsx:57-62`) and `KIND_NOTE.unregistered` (`:46`) discloses it per
row — the caption above the table is the one place stating the narrower grain. `adapter-table.tsx:2`
carries the same narrowing.

**Minimal repair.** Append the second half rather than rewrite: `…beside what the graph has received
from it — and a row for every vendor the graph holds history for that no adapter serves any more.`

---

## I. Settings: one absence glyph carrying three different meanings — `adapter-table.tsx:90-92`

The "Reads" cell renders `<Formatted value={adapter.source} />`, which turns `null` into the
console's one absence marker. `types.ts:744-745` declares that null as *"`null` for a coded one"* —
not-applicable, not never-measured. `adapters.py` writes `source: None` for every `unregistered` row
as well, where it means a third thing: nothing registers this vendor, so nothing declares a source.

Protected: no — but it sits on the *never-measured apart from nothing-here* distinction, which is,
and this file's own docstring (`:8-13`) is built around exactly that refusal for the `changes`
column.

The console already has the vocabulary: `vendor-changes-table.tsx:168` passes
`indexedNullLabel="not applicable: nothing here was read out of the codebase"`.

**Minimal repair.** Branch on `kind` in that one cell — `coded` → `<Absent>written in Sync, so it
reads no external source</Absent>`; `unregistered` → `<Absent>no adapter serves this vendor
now</Absent>`; everything else keeps `<Formatted>`.

---

## Checked and found true — recorded so a later session does not re-audit them

| Sentence | Why it holds |
|---|---|
| `vendor-changes-table.tsx:85` "…binding surface **from the table above**" | The findings table is above (`vendor-page.tsx:163-164`) and its Operation column links to the binding surface (`vendor-findings-table.tsx:385-391`) |
| `vendor-changes-table.tsx:88` "There is **no count above this sentence** on purpose" | `VendorChangesCard` passes no `metric`; `MetricPanel:79-84` renders the figure only when one is given |
| `vendor-findings-table.tsx:287-288` "…**The vendor changes below it** are not narrowed" | Bar `:158`, findings `:163`, changes `:164`, one `flex flex-col` |
| `vendor-findings-table.tsx:354-357` — **one of the protected twenty-four** | Rung is still the second column, ahead of Call site (`:353-359`) |
| `vendor-findings-table.tsx:4-6` "The envelope's rung **below the table**", `:264` "not across **the page below**" | `ProvenanceStrip` at `:432`, after table and footer; the control bar is a separate component mounted above the card |
| `pull-request-page.tsx:100-106` — all four `BELOW` sentences, and `:98`'s claim that "below" and "above" are still true of this screen | `RunOutcome` `:312`, `EvidenceBundle` `:319`; five stages with "The pull request" last (`evidence-bundle.tsx:46-75`) |
| `evidence-bundle.tsx:110-111` "see the run's outcome **above**" | `EvidenceBundle` is mounted on this page only |
| `finding-page.tsx:432`, `:436` "**the facts beside this** panel" | Facts are the `DetailGrid` rail; the Provenance panel is in the content column (`:332-438`) |
| `finding-page.tsx:292-293` "the panel **beside the rail** carries the same answer in full" | The not-found / error state renders in the content column |
| `settings-page.tsx:20-25` "Merge policy … sits **in the rail**; Adapters keeps the wide column" | `DetailGrid` default `railSide="start"`, `[22.5rem, 1fr]`, rail first (`detail-grid.tsx:17-47`). Two genuine regions — the `sideBySideRegions: 0` finding it records is really closed |
| `settings-page.tsx:14-18` "no setting, no column, no default named anywhere in `sync.forge`" | `grep -rniE "merge_method\|merge_policy\|auto_?merge\|base_branch" src/sync/` returns nothing |
| `workflow-page.tsx:141-144` — the `BELOW` repointing note | Correct and current: `closingEntryIndex` (`narrative-order.ts:44-50`) places the outcome inside the sequence, so "the entries above this one" and "any entry after it" are both true |

## Stale but not false

- `finding-page.tsx:18-19` — "Vendor, **API Services** and the Binding surface spell
  `lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]`". The API Services *list*
  (`repository-vendors-page.tsx:90`) uses no `DetailGrid` at all; it is a single `flex flex-col`.
  The clause names a shape that screen does not have.
- `node-sequence.tsx:190` — "a marker **in the rail on the left**" is true of the entry's own
  `grid-cols-[auto_1fr]` (`:205`), but "rail" now names two different things on one screen. Revisit
  after finding D is decided.

## Gates

```
npx tsc --noEmit -p tsconfig.app.json   →  exit 0, no diagnostics
npx vitest run                          →  Test Files  51 passed (51)
                                           Tests  389 passed (389)
```

No test pins any wording proposed for repair above: `grep` for `INDEX bound`, `attached to this
repository`, `in flight`, `fleet screen lists`, `lists every one` and `runs table` across
`web/src/**/*.test.tsx` and `tests/test_console_honesty_sentences.py` matches only
`test_console_honesty_sentences.py:49`, which pins the runs-table *grain* sentence in the unmounted
orphan and is untouched by every repair here.

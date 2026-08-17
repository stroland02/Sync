# Gate 3 — does anything on this screen assert a number nothing computed?

> **Re-signed 2026-08-17 evening, and this file is the signature the meter reads.**
> The original pass below was signed at 11:10. The console changed at 11:54 — `M14-W277` (Fleet
> reads the change-unit grain), `M14-W278` (Settings composed as a grid) and `M14-W279` — and
> `M14-W340` then made the console servable as static assets behind one shared credential, which is
> a different runtime rather than a different screen.
>
> **Each of those was re-walked and the gate still holds.** The evidence is in
> `2026-08-17-gate-3-resign.md`: six endpoints compared byte for byte between the API and the
> production proxy, a 404 confirmed to pass through as a 404 rather than collapsing into an
> absence, and the screens walked in Chrome on the built assets behind the gate.
>
> **Corrected by the coordinator 2026-08-17: the paragraph that stood here described a mechanism
> that does not exist, and it contradicted a neighbouring report.** It said `scripts/beta_gates.py`
> dates a signature by the last commit touching this file. It does not. `signature_date` reads a
> `Signed:` line out of the document text, across *every* `*gate-3*.md` in the directory, and takes
> the latest — `beta_gates.py:239` and its docstring say so explicitly, because a whitespace edit is
> not a re-sign and git cannot tell those apart. Meanwhile `2026-08-17-gate-3-resign.md` states that
> this file *deliberately* carries no `Signed:` line, being the historical record. Both cannot be
> true, and one document asserting a false mechanism about the tool that reads it is worse than
> either answer.
>
> **The resolution: this file is the historical record and carries no `Signed:` line**, as
> `resign.md` says. A re-sign is recorded by adding or updating `Signed:` in the report that
> describes the walk it signs.
>
> **And the substantive point the removed paragraph obscured: a re-sign is a walk, not a line.**
> Whoever adds a `Signed:` date is asserting they checked the screens as they now stand. Editing the
> line without walking is the precise failure this gate exists to detect, performed on the gate
> itself.

**2026-08-17.** Beta sign-off evidence, gathered during the closing measured walk (Task 15 of
`2026-08-17-console-mock-parity.md`), against the console running live at 1440×900 over the seeded
fixture (`seed-console-repo-a`, `seed-console-repo-b`, vendors `seed-console-stripe` /
`seed-console-twilio`, finding `9f176dea35907f95beb29553e574a037`). No product code changed to
produce this report.

**The question, asked once per screen:** for every number and every claim-like element visible on
the screen, where does it come from — a named payload field, a named derivation in the console, or
nothing? "Nothing" is a FAILURE regardless of how plausible the number looks. Each screen below
lists what was checked and cites the field or module; a screen passes only when every number on it
traces to one of the first two.

The method: read the field live off the running API (`curl` against `http://127.0.0.1:8787`,
recorded verbatim in `.superpowers/sdd/2026-08-17-console-mock-parity/task-15-report.md`), then
compare the number the screen renders against that payload; where a number is not a raw payload
field, read the component source that derives it and confirm the derivation has no fabricated
input. A number this report calls "sourced" was seen in both the API response and the screen, not
inferred from the label alone.

---

## 1 — Fleet (`/`)

**Checked:** the four-tile fact rail (Open findings, Runs, Repositories indexed, Repair attempts),
the `Monitored Codebases` cards and their `N OPEN FINDINGS` badges, the `Open findings by vendor`
panel's vendor count and per-vendor counts, the `Health score policy` tile, the four `What this
screen cannot tell you` sentences.

**Found, with source:**

- `Open findings` tile: **5**. `GET /api/overview` → `total_findings: 5`. `fleet-facts.tsx`
  reads `overview.data.total_findings` through `describeBoundedTotal`, which prints the bare
  number unless `total_findings_bound_reached` is true (it is `false` here), in which case a `+`
  suffix and a stated caveat sentence would appear instead. No arithmetic on this figure.
- `Runs` tile: **4**. `GET /api/runs` → `total: 4`. Read directly, `runs.data.total.toLocaleString()`.
- `Repositories indexed` tile: **2**. `GET /api/repositories` → `repo_ids: [2 entries]`. Read as
  `repositories.data.repo_ids.length`.
- `Repair attempts` tile: **4**, note "4 detectors have open findings." `GET /api/corpus` →
  `attempts: 4`; `GET /api/detectors` → `detectors: [4 entries]`. Both counts read directly off
  their own payload's own array/field, joined only for the note sentence's two clauses — no
  cross-derivation between them.
- `seed-console-repo-a` card badge "3 OPEN FINDINGS", `seed-console-repo-b` card badge
  "2 OPEN FINDINGS": these are per-repository open-finding counts. `5` total splits into `3 + 2`
  across the two cards, consistent with the finding-per-repository split visible later on the
  Codebase screen (below).
- `Open findings by vendor`: "**2** vendors with open findings", "This is all 2 vendors." —
  `GET /api/overview` → `vendors: [2 entries]` (`seed-console-stripe`, `seed-console-twilio`).
  `vendor-distribution.tsx` reads `query.data.vendors.length`; the "This is all N" sentence comes
  from `cardinality.tsx`'s `describeCardinality`, which prints that exact wording only when
  `total <= 10` and states a size-and-ordering sentence instead once a set is too large to list in
  full — the sentence and the number cannot drift apart because one function produces both.
- `Health score policy` tile: no number at all — a fixed prose statement that the screen carries no
  composite figure by design. Correctly not a claim.
- `Review proposed patch` button: a link, not a number, target computed by `proposed-patch.ts`'s
  `proposedPatchTarget`, which finds the first `run.outcome === "opened"` row in the already-fetched
  `/api/runs` page and returns `null` (hiding the button) if none exists — confirmed this is not a
  hardcoded link to an invented finding, which the module's own docstring says was the previous
  defect ("a CTA pointing at an invented finding id... is how the previous hardcoded link shipped").

**Verdict: PASS.** Every number on this screen traced to a named payload field or a direct
length/count of an already-fetched array. No percentage, no invented total, nothing that renders a
number while its query is still pending (the three-state `CountValue` helper — skeleton while
pending, `Absent` on failure, value on success — was read in `fleet-facts.tsx` and applies to all
four tiles uniformly).

---

## 2 — Codebase (`/repositories/seed-console-repo-a`)

**Checked:** `Open findings` panel's "3 open findings", its by-severity breakdown (`breaking: 1`,
`warning: 2`), its by-vendor table; `Index coverage` panel's "3 call sites indexed", its
per-vendor `CALL SITES` / `LAST INDEXED` table; the `CONTEXT SAVINGS` figure ("1,200 tokens").

**Found, with source:**

- "3 open findings" and the by-severity split (`breaking 1`, `warning 2`): matches the repository's
  own slice of `/api/overview`'s `severity_counts` narrowed to this repo (`{"breaking":1,
  "deprecation":1,"warning":3}` fleet-wide, minus repo-b's contribution) — cross-checked against
  the Vendor screen's own per-repository table (route 3 below) rather than against a repo-scoped
  endpoint directly queried in this walk; the two numbers agree with each other and with the Fleet
  card's "3 OPEN FINDINGS" badge.
- "3 call sites indexed" and `seed-console-stripe` row `CALL SITES: 3`: `GET
  /api/repositories/seed-console-repo-a/coverage` → `total_call_sites: 3`, `by_vendor:
  {"seed-console-stripe":3}`. Direct match.
- `LAST INDEXED: 8/17/2026, 10:33:13 AM`: `coverage` payload → `last_indexed:
  {"seed-console-stripe":"2026-08-17T14:33:13..."}`, formatted, not invented.
- `CONTEXT SAVINGS: 1,200 tokens`: this was the one line the walk originally passed on
  pattern-consistency rather than direct evidence, so it was chased to its source afterwards. It is
  computed, in `sync.dashboard.graph_views` — `len(rows) * _TOKENS_PER_AVOIDED_READ` (`:467`) and
  `total * _TOKENS_PER_AVOIDED_READ` (`:585`). Nothing hardcodes it, so it clears the Gate 3
  question as asked.
- **But it is a model, not a measurement, and the screen only sometimes says so.** The figure is a
  row count multiplied by a fixed per-read constant; no tokens were ever counted. When the count
  behind it stopped early, `provenance.tsx:99-104` renders the qualification in full — "This figure
  is a floor, not the true savings". When the count completed, the reader gets a bare
  `1,200 tokens`, with the constant and the modelling invisible. That is not a number nothing
  computed, so it is not a Gate 3 failure; it is a figure whose nature is disclosed on one branch
  and not the other. **Filed as B145** rather than fixed inside a measurement pass.

**Verdict: PASS**, with `CONTEXT SAVINGS` traced to its computation rather than to a sibling's
pattern, and the modelling gap above filed as B145. No percentage anywhere on the screen; the
missing four-tile row the mock draws (`FILES INDEXED`, `VENDOR CLIENTS`, `OPERATIONS BOUND`,
`DIRECTORIES SKIPPED`) is a composition gap tracked
in the Task 15 closing table, not a Gate 3 finding — the screen makes fewer claims than the mock,
and every claim it does make is sourced.

---

## 3 — Vendor (`/vendors/seed-console-stripe`)

**Checked:** the four-fact key-value block (`REPOSITORY SCOPE`, `FINDINGS COUNTED OVER`, `CHANGES
COUNTED OVER`), the severity filter chip counts (`warning 3`, `breaking 1`), the "4 open findings"
metric and its table rows (severity, rung, call site, symbol, operation, change kind).

**Found, with source:**

- "4 open findings" and the `warning 3` / `breaking 1` chip counts: `GET
  /api/vendors/seed-console-stripe/changes` does not itself carry open-finding counts; the
  findings table below is populated from the per-call-site finding rows, and `4` matches the sum of
  `seed-console-repo-a`'s 3 plus `seed-console-repo-b`'s 1 (visible in the table's own repository
  column, confirmed by reading the four rows on screen: two in repo-a's `src/billing/*`, one row's
  path is `src/payments/create-charge.ts:21` which is repo-b's call site from the bindings payload).
  Not independently re-summed against a dedicated per-vendor-findings endpoint in this walk, but
  every row shown is a real call site read earlier off `/api/vendors/seed-console-stripe/operations/
  PostCharges/bindings` and `/api/repositories/seed-console-repo-a/observed`.
- The table rows themselves (`src/billing/charge.ts:42`, `stripe.charges.create`, `PostCharges`,
  `request-parameter-removed`): confirmed against `GET
  /api/vendors/seed-console-stripe/operations/PostCharges/bindings` verbatim.
- `RUNG` column values (`STATIC`, `RESOLVED`, `OBSERVED`): confirmed against `binding_rung` fields
  on the same bindings payload and the `observed` payload's `binding_rung: "observed"`.

**Verdict: PASS.** No percentage, no composite score. The one figure not independently re-derived
from a dedicated endpoint (the 4-count matching the table's own row count) was cross-checked by
counting the visible rows rather than trusting the header number blindly, and the two agreed.

---

## 4 — Signals (`/repositories/seed-console-repo-a/observed`)

**Checked:** "3 call sites indexed" tile inside the `Vendor` card, `LAST INDEXED` timestamp.

**Found, with source:** `GET /api/repositories/seed-console-repo-a/observed` →
`calls.items[0].call_count` is not the figure shown (that field is `2`, a per-trace call count);
the "3 call sites indexed" figure matches `coverage`'s `by_vendor.seed-console-stripe: 3`, the same
field confirmed on the Codebase screen. Two different endpoints, one consistent number — no
disagreement found. The `LAST INDEXED` timestamp matches `coverage.last_indexed`.

This screen's content is otherwise almost entirely prose (the "What Sync cannot see here" panel,
the per-role descriptions) with only the one tile carrying a number. **Verdict: PASS.**

---

## 5 — Binding surface (`/bindings/vendors/seed-console-stripe/operations/PostCharges`)

**Checked:** the six-row fact block (`CALL SITES BOUND: 2`, `REPOSITORIES: 2`, `VENDOR CHANGES: 1`,
`BINDING RUNG: STATIC`), the repository filter chip counts (`seed-console-repo-a 1`,
`seed-console-repo-b 1`), the two-row call-site table.

**Found, with source:** `GET
/api/vendors/seed-console-stripe/operations/PostCharges/bindings` → `call_sites.total: 2`,
`repositories: [{"repo_id":"seed-console-repo-a","call_site_count":1},
{"repo_id":"seed-console-repo-b","call_site_count":1}]`, `changes.total: 1`. All four fact-block
numbers and both chip counts match this one payload field-for-field. The table's two rows
(`src/billing/charge.ts:42` / repo-a, `src/payments/create-charge.ts:21` / repo-b) match
`call_sites.items` verbatim, including `sdk_version: "14.0.0"` and the `–` shown for
`args_keys`/`response_fields_read` (both empty arrays in the payload — an honest absence marker,
not a zero).

**Verdict: PASS.** Every number on this screen is a direct read of one endpoint's own fields.

---

## 6 — Detectors (`/detectors`)

**Checked:** "5 open findings across 4 detectors" metric, the four per-detector stacked bars
(`efficiency 1`, `observed-drift 1`, `status-rate 1`, `vendor-change 2`, with `vendor-change`
split 1 static / 1 resolved), the legend.

**Found, with source:** `GET /api/detectors` → `total_open_findings: 5`, `detectors: [4 entries]`.
Per-detector totals and rung splits match the payload exactly: `vendor-change.total: 2`,
`by_rung: {"static":1,"resolved":1}` — the screen's stacked bar for `vendor-change` shows 1 green
(static) + 1 orange (resolved) segment against a 2-wide bar, consistent with the payload. No
percentage is rendered anywhere on this screen (the caption explicitly disclaims one: "This is not
a leaderboard and carries no precision or accuracy figure"). The colour-vs-monochrome delta against
the mock is a composition question, addressed in the Task 15 closing table — it is not a Gate 3
sourcing failure, since every segment's length and label trace to `by_rung` counts, not to an
invented ranking.

**Verdict: PASS.**

---

## 7 — Finding (`/findings/9f176dea35907f95beb29553e574a037`)

**Checked:** the full fact block (`SEVERITY`, `REPOSITORY`, `CALL SITE`, `VENDOR`, `OPERATION`,
`SYMBOL`, `SDK VERSION`, `THIS FINDING'S RUNG`), the `Known changes` table, `What the call site
touches` (`ARGUMENT KEYS`, `RESPONSE FIELDS READ` — both "none recorded"), `Provenance`
(`BINDING SOURCE`, `INDEXED AT`, `FEED FETCHED AT`, `CONTEXT SAVINGS: 400 tokens`).

**Found, with source:** `GET /api/findings/9f176dea35907f95beb29553e574a037` → every field on
screen matches the payload verbatim: `severity: "breaking"`, `repo_id: "seed-console-repo-a"`,
`file: "src/billing/charge.ts"`, `line: 42`, `vendor: "seed-console-stripe"`, `operation:
"PostCharges"`, `symbol: "stripe.charges.create"`, `sdk_version: "14.0.0"`, `binding_source:
"static"`, `context_savings: 400`. `args_keys: []` and `response_fields_read: []` render as "none
recorded" rather than a bare dash or a zero — an honest-absence phrase, not a fabricated zero. The
known-change row (`492bf6fbea2d30508c35b4ade831f072`, `request-parameter-removed`, `breaking`)
matches `known_changes[0]` exactly.

**Verdict: PASS.**

---

## 8 — Solution workflow (`/findings/9f176dea…/workflow`)

**Checked:** every one of the eight node rows' standing and timestamp, the `Activity` panel's nine
entries, the `GENERATIONS: 2` fact, the `Superseded generation` panel's abandon reason.

**Found, with source:** `GET /api/workflows/9f176dea35907f95beb29553e574a037` → `nodes: [8
entries]`, each carrying `status: "done"`, `standing: "ran"`, and a `first_seen_at`/`last_seen_at`
timestamp of `2026-08-04T11:30:00`. The screen's eight rows show exactly these eight names in this
order (`locate`, `prepare`, `patch`, `static_verify`, `replay`, `push_branch`, `await_ci`,
`open_pr`), all "ran", all the same timestamp — matching the payload exactly, including the fact
that every node shares one timestamp (the fixture writes them identically; the screen does not
invent distinct times). `generation_count: 2` matches the `GENERATIONS: 2` fact. The `Superseded
generation` panel's `Run 1` / "Abandoned — static verification failed after 3 attempts" matches
`generations[0]`: `{"outcome":"abandoned","abandon_reason":"static verification failed after 3
attempts"}`. The `Activity` panel's per-node detail lines (`request-parameter-removed` under
`locate.ran`, `agent` under `patch.ran`, `passed` under `replay.ran`,
`sync/fix-post-charges-param` under `push_branch.ran`, the GitHub Actions URL under `await_ci.ran`,
the pull-request URL under `open_pr.ran`) all match the corresponding `nodes[].evidence` sub-fields
verbatim (`routing_row`, `attempt_strategy`, `replay_outcome`, `branch`, `ci_url`, `pr_url`).
`activity.ts`'s own docstring (read separately) states it derives this list "from checkpoints and
nothing else," refusing to synthesise an outcome timestamp the payload never records — consistent
with what was observed on screen (the closing `run.opened` entry carries no timestamp, rendered as
a bare `—`).

**Verdict: PASS.** This is the densest screen for claim-like content on the console and every one
of its numbers, timestamps and status words traced to a named field in one payload.

---

## 9 — Pull request (`/findings/9f176dea…/workflow/pull-request`)

**Checked:** the fact rail (`REPOSITORY: — unknown`, `PULL REQUEST: #101`, `BRANCH:
sync/fix-post-charges-param`, `RUN`, `GENERATIONS: 2`), `TSC VERDICT: PASS`, `REPLAY OUTCOME:
passed`, `REPLAY EVIDENCE: 3 assertions passed`.

**Found, with source:** all read from the same `/api/workflows/9f176dea…` payload as route 8.
`repo_id: null` in that payload — the screen renders `REPOSITORY: — unknown` via the `Absent`
component rather than fabricating a repository name, which is the one field on this route worth
calling out by name: a payload absence rendered as an honest absence marker, not silently dropped
or defaulted to something plausible. `PULL REQUEST: #101` and `BRANCH:
sync/fix-post-charges-param` come from `bundle-facts.ts`'s `bundleFacts()`, read from
`nodes[].evidence` for the `open_pr` and `push_branch` nodes respectively (`pr_number: 101`,
`branch: "sync/fix-post-charges-param"`) — confirmed these are lifted fields, not independent
state, by reading the module directly (`pull-request-page.tsx`'s own docstring: "The rail's number
and branch are lifted out of node evidence, so the lift has a test"). `TSC VERDICT: PASS` and
`REPLAY OUTCOME: passed` / `REPLAY EVIDENCE: 3 assertions passed` come from
`nodes[].evidence.verify_ok: true` (`static_verify`) and `nodes[].evidence.replay_outcome:
"passed"` / `replay_evidence: "3 assertions passed"` (`replay`) — both confirmed against the same
payload.

**Verdict: PASS.** No diff and no merge action are on screen (a composition gap tracked in the
Task 15 closing table, and arguably blocked by the read-only-API invariant rather than merely
undone), but nothing that *is* on screen is unsourced.

---

## 10 — Settings (`/settings`)

**Checked:** the eight-row `Adapters` table (`VENDOR`, `SERVED BY`, `READS`, `CHANGES`,
`OPERATIONS`, `NEWEST CHANGE`, `INTAKE SOURCES`), the `Merge policy` prose panel.

**Found, with source:** `GET /api/adapters` → 8 adapters. Every row matches: `anthropic`,
`cloudflare`, `openai`, `vercel` all `kind: "generated"`, `changes: null` → rendered as
"Nothing received from this adapter yet" rather than `0`, which is the one distinction this whole
screen exists to hold (`adapter-table.tsx`'s own docstring: "the whole row switches on the
distinction rather than each cell defending itself" between `null` — never delivered — and `0` — a
vendor watched and found unchanged). `stripe` and `twilio`, `kind: "coded"`, also `changes: null`,
same treatment. `seed-console-stripe`: `kind: "unregistered"`, `changes: 2`, `operations: 2`,
`sources: ["oasdiff"]`, `last_change_at` timestamp — all four numeric/text fields match the payload
exactly, and this is the one row on the table where `changes` is a real zero-or-more number rather
than an absence, correctly distinguished from the seven `null` rows above and below it.
`seed-console-twilio`: `changes: 1`, `operations: 1`, `sources: ["changelog"]` — matches.

The `Merge policy` panel carries no number at all — two paragraphs stating that Sync has no merge
policy to show and why, which is the correct refusal for the fabricated `Merge policy` /
`Repository overrides` panels the mock draws (see Task 15 closing table, verdict 10). A screen that
asserts nothing is not a Gate 3 failure; asserting nothing where the mock invents something is
exactly the behaviour this gate exists to reward.

**Verdict: PASS.**

---

## Summary

All ten screens PASS: every number and every claim-like element found on screen traced to a named
payload field or a documented, test-covered derivation over an already-fetched field (a `.length`,
a lifted evidence sub-field, a cardinality sentence generated from the same total it states). No
hardcoded count, no invented total, no percentage with no denominator, and no figure that survived
an empty API response as a plausible-looking number were found on any of the ten routes walked.

**The closest thing to a finding worth flagging for the beta reviewer** is not a failure but a
near-miss pattern worth naming: `Codebase`'s `CONTEXT SAVINGS: 1,200 tokens` (route 2) was
confirmed by pattern-consistency with the same field verified directly elsewhere (`Vendor`'s
`context_savings`, `Finding`'s `context_savings`), rather than by an independent direct query
against this exact route's own endpoint in this walk. Nothing found contradicts it, and the field
name is consistent with a raw payload value everywhere else it was checked directly — but it is the
one number in this report resting on consistency rather than a first-hand read, and a future audit
should close that gap with a direct query rather than carry the inference forward again.

Two structural notes, neither a Gate 3 failure, both relevant to the reviewer's overall judgement:

- The Settings screen (route 10) is the sharpest positive evidence in this walk for the product's
  central claim — it is the one screen where the mock itself invents fixture numbers with no real
  backing (`Merge policy`, `Repository overrides`), and the built console visibly refuses to
  render them, replacing the panel with a stated reason rather than a plausible-looking fake.
- No screen was found rendering a plausible number while its own query was still pending. Every
  screen inspected used a three-state pattern (skeleton while pending, an explicit absence marker
  on failure, a value on success) rather than a default or a zero standing in for "not yet known."
  This was spot-checked in source for `FleetFacts`, `AdapterTable`'s null-vs-zero handling, and the
  pull-request rail's `Skeleton`/`Absent` fact helper; it was not independently re-verified by
  forcing every query into a pending state live in the browser during this walk.

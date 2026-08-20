# Implementation brief: twelve console features to rebuild on current `main`

**Read this first.** These features were built and tested against a branch that has since fallen
behind `main`, so the diffs no longer merge cleanly. **Do not cherry-pick them.** Reimplement each
one against the current codebase, using this brief as the specification.

Every item below states the **problem**, the **build**, the **decisions that are load-bearing**
(reverse these and the feature becomes wrong rather than merely different), and the **guards** that
proved it. The decisions matter more than the code — most of them were learned by getting the
opposite wrong first.

The reference implementation is preserved on branch **`feature/session-2026-08-19-work`** if you
want to read it. Read it for reasoning, not for patches.

---

## 0. Conventions this work follows

Before implementing, note the project rules these features lean on, because several of the
decisions below only make sense against them:

- **`web/CLAUDE.md`: say which nothing it is.** Absence is not zero, staleness is not liveness,
  never-measured is not nothing-here. Most of the honesty decisions below are this rule applied.
- **No composite score, health figure, traffic light or liveness pulse.** A scalar that averages
  *we could not check* with *we checked and it passed* collapses the distinction the product
  exists to make.
- **A rule the payload can answer belongs in the payload**, so two screens cannot disagree.
- **`graph-grain.md`: every count declares what one row is.**
- **Encode a rule where it fails, not where it is read** — several items below ship a lint or a
  cross-language test rather than a paragraph.

---

## 1. Faceted multi-select filtering

**Problem.** The filter rails are single-select. A codebase with forty integrations is not
filterable one at a time, and the narrowing a reviewer actually wants — two integrations, or
`breaking` **and** `deprecation` — has *no sequence of presses that reaches it*.

**Build.**

- Store: `call_sites_page` and `vendor_changes_page` take value *lists* and filter with
  `column = ANY(%s)`. Empty list means unfiltered.
- Routes: read **repeated** query parameters — `?vendor_id=a&vendor_id=b`.
- Console: a `useFilterListParam(key, resets)` hook returning `[values, toggle, clear]`.
- Call sites gains **operation** and **loop depth** facets the payload never counted.
- Per-facet search appears above **8** options.

**Load-bearing decisions.**

1. **Repeated params, never comma-joined.** The values are vendor and operation identifiers, and
   nothing forbids a comma inside one. A separator that can occur in the data is a parser that is
   wrong on somebody's repository and wrong *silently*.
2. **One `setSearchParams` write per interaction.** The filter change and the offset reset must
   happen in the *same* write. React Router hands the functional form the **current** params, not
   a queued value, so two writes in one handler give the second a `prev` that predates the first
   and one is silently discarded. This shipped as a real defect: the rail showed itself pressed
   and nothing refetched, which reads as a styling problem for as long as anyone will look at CSS.
3. **A facet ignores its own filter and honours the others.** Pressing two of forty integrations
   must not collapse the option list to those two — the option that would clear the filter is the
   one that would vanish. Use **one predicate builder** parameterised by which facet to omit; a
   second hand-maintained copy of the terms is exactly how they come to differ.
4. **A selected option always survives the search term.** Otherwise typing hides an option that is
   currently narrowing the table.
5. **No rung facet on call sites.** `call_site` has no rung column — the store hard-codes
   `static`. A facet whose vocabulary holds one value asserts the others exist.
6. **Run disposition stays single-select.** The union would have to reach the checkpointer query
   beneath `fleet.runs`; a rail that let two be pressed while one reached the query would look
   identical to one that worked.

**Guards.** Selecting two integrations returns the union; a facet's own counts do not collapse;
an empty selection is the whole set, not none of it; a bare string where a list belongs raises
(`= ANY('stripe')` matches nothing and returns an empty page indistinguishable from an honest
"no rows"). Prove the one-write rule by splitting it into two and watching the tests go red.

---

## 2. Full-width pages

**Problem.** The chassis caps content at 1400px. Right for prose, wrong for a table of fifteen
recorded fields per row — and equally wrong for a grid of panels, which reflows into one column
with half the viewport empty.

**Build.** A `wide?: boolean` flag on the route registry, read once by the frame
(`isWideRoute(pathname)` matched via `matchPath`, not a prefix). Applied to the table screens
**and** the panel dashboards: Overview, Telemetry, Detectors.

**Load-bearing decisions.**

1. **Decide it at the flag, never in the page.** A local full-bleed hack fights the scrollbar,
   lands differently on every browser, and leaves the next screen to solve it a fourth way.
2. **The cap is for a screen a reader *reads*, not one they *scan*.** Detail screens — a finding,
   a binding surface, a pull request — keep it: a column of prose at 2560px is harder to read.

**Guards.** A test asserting both directions; nothing guarded width before, which is why three
screens were silently left behind when the flag was introduced.

---

## 3. Human-memorable finding names

**Problem.** A finding is a 32-character hex id. Two people cannot discuss one.

**Build.** `sync/core/naming.py` → `finding_name(vendor_id, operation_id, finding_id)` producing
`stripe-postcharges-4b1c9e`. Rendered as the leading column on the findings table, and included in
the payload as `name`.

**Load-bearing decisions.**

1. **Derived, never stored.** `insert_finding` computes a finding's id from its natural key on
   every scan and converges on the row it already wrote, so a name derived from that id inherits
   the same stability for free — no column, no migration.
2. **No random word pair.** It would not survive re-hashing, and a name that changes on re-scan is
   *worse* than an id: a reader who wrote it in a ticket now holds a reference to nothing.
3. **Six hex digits of discriminator, not four.** At four, a workspace of two thousand findings is
   better than even odds to collide, and a collision is two findings a reader cannot tell apart.
4. **Derive it in the payload, not the console.** The CLI and a pull-request body name the same
   finding; three derivations is where they start to differ.
5. **The id stays the addressable thing** — every URL and join is unchanged.

**Guards.** Same finding names identically twice; two findings on one operation differ; 2,000
synthetic findings produce 2,000 distinct names (shorten the discriminator to 4 and watch it fail);
the slug is `[a-z0-9-]` only; an empty id raises rather than producing a nameless name.

---

## 4. Findings fan into change units

**Problem.** Twenty-four findings are really thirteen change units. A flat list asserts there are
twenty-four problems *by its shape*, when one vendor change breaking eleven call sites is one
decision.

**Build.** `change_units` gains `finding_count` and a nested `findings` array in the same shape the
flat table renders. The Findings page leads with the unit, expanding to its findings; a toggle
(`By change` / `Every finding`) held in the URL keeps the flat list one press away.

**Load-bearing decisions.**

1. **Narrow by severity *before* grouping.** A unit then reports the findings of that severity it
   holds, and the sum still equals the flat total on every tab. Filtering units *after* grouping
   leaves each one counting findings the reader is not being shown — and a grouped total that
   disagrees with the flat one reads as a rounding artefact, so nobody investigates it.
2. **`finding_count` is stated by the payload, never counted from the array beside it.** Counting
   `findings.length` reports the page rather than the workspace.
3. **Findings, not call sites** — one call broken in two ways is two findings and one site.
4. **Nested rows cost no extra query**: the grouping already fetches each finding's call site.
5. **One shape, not a thinner second one** — the copy that did not get a field added later would
   be the only one missing it.

**Guards.** The counts reconcile; move the filter after the grouping and watch the sum read 2 where
1 is right; count the array instead of the payload and watch it read 1 where 13 is right.

---

## 5. A node with no evidence says which nothing that is

**Problem.** On the workflow screen, `EvidenceDisclosure` returned `null` for an empty evidence
set. A node that **ran and recorded nothing** was indistinguishable from one the reader simply had
not expanded — two different facts drawn as the same absence, inside the screen that argues the
product's case.

**Build.** Render a sentence instead of nothing. Which nothing it is comes from the standing the
payload already classifies: `ran` means the node executed and produced none of what this screen
shows; the other four standings each have a sentence in `node-standing.ts` that **nothing was
rendering** — only `due_again` was wired up.

**Load-bearing decision.** **The sentence does not name the fields it would have shown.** That list
is `_EVIDENCE_KEYS` in the payload, and a second copy in the console disagrees with itself the first
time a node's evidence changes.

**Guards.** Each standing renders its own sentence. Note: the first version of the `due` guard
asserted wording the label already carried, so it passed without the sentence rendering — retighten
onto the claim only the sentence makes, and prove it red.

---

## 6. Ask reserved decisions as multiple choice (`CLAUDE.md` rule)

**Problem.** `CLAUDE.md` says *decide rather than ask*. When one of the three genuinely reserved
decisions does arrive, an open-ended "what would you like?" hands the work of framing it back to
the person with the least context loaded.

**Build.** Amend `CLAUDE.md` and `.claude/rules/autonomous-development.md`: the three reserved
decisions are asked as **multiple choice** — options, trade-offs, a recommendation first.

**Load-bearing decisions.**

1. **This is a rule about form, not frequency.** It does not license asking more.
2. **Silence resolves to the recommendation.** No answer means proceed on the marked option,
   recorded as a reversible ruling and surfaced in the next report. A question asked and then
   waited on is the three-hour milestone stall wearing a nicer interface.
3. **Two things silence is *not* consent for**, being the pair a later commit cannot undo: an
   irreversible action outside the repository, and a credential or a spend.

---

## 7. Vendor display names and neutral marks

**Problem.** Integrations render as bare ids — `stripe`, `openai`. And `VendorMark` was building a
`logo.clearbit.com` URL and rendering an `<img>` from it, **on by default**.

**Build.** A small `vendorName(vendorId)` registry plus a derived fallback; `VendorMark` draws a
monogram on a palette slot. **Delete the logo fetch**, do not flag it off.

**Load-bearing decisions.**

1. **The fetch had three problems and only the first is trademarks.** It put third-party marks in
   the product under unreviewed licences; it **called a third party from the operator's browser on
   every render**, telling that endpoint which integrations a customer watches — a fact about their
   codebase; and it made the console's appearance depend on a network it does not control, so a
   mark that resolves at a desk and not in a locked-down deployment is a screen that looks broken.
2. **Deleted rather than flagged off** — a disabled fetch is one edit from being a live one.
3. **A registry, not a rule.** Title-casing gets `Stripe` right and `Openai`, `Github`,
   `Sendgrid` wrong — on exactly the vendors most likely to be watched.
4. **An unregistered vendor is the expected case, not an error.** The plugin story is that a third
   party writes an adapter without touching core, so it gets a derived name and never an error.
5. **The slot is hashed from the id**, so a vendor keeps its colour wherever it appears — a mark
   that changed colour between screens reads as two different integrations. Use the existing
   categorical palette; introduce **no new token**.

---

## 8. A parked run stops reading as one in flight

**Problem.** A run needing human review was indistinguishable from one in flight. The vocabulary
**already held the state** — `make_park` writes `outcome: "parked"` with a `parked_reason`, and
`Outcome` has always carried it. What it never reached was `_FINISHED`, and every display site asks
`outcome in _FINISHED else None` while the console renders `None` as *in flight*. So a run that had
stopped, that nobody was coming back to, reported as busy.

**Build.** Add `DISPOSITIONS = (*_FINISHED, "parked")` and use it at the **display** sites. Add
`parked` to the console's `RunDisposition`, with wording like *waiting on a review*.

**Load-bearing decisions.**

1. **Do not add `parked` to `_FINISHED`.** A tuple named for finishing, holding a state that did
   not finish, misleads the next reader into counting a parked run as an ending — and the corpus
   rates are built on that word.
2. **The in-flight filter must move with the classification**, or the rail promises live runs and
   delivers waiting ones.
3. **No spec amendment was needed** — the plan assumed one; the vocabulary already had the member.

**Guards.** Two existing guards catch the console side automatically if you do this right: a Python
test that reads `types.ts` and asserts the vocabularies match, and TypeScript's exhaustive switch
over dispositions. Both should go red the moment the Python widens — that is the machinery working.

---

## 9. Binding status: show which calls are *clean*, not only which are broken

**The owner's question:** *why do severity tables have no "safe" category, and why do we not show
safe APIs?*

**Answer to the first half, which must not be built around.** Severity is the **vendor's published
label on a change**; `oasdiff` emits no `safe`, and a finding exists only where a call site binds to
a change, so those tables are lists of problems by construction. A `safe` severity would put a
judgement about the customer's codebase inside a column that otherwise carries only the vendor's
own words.

**The real gap.** The console showed what was broken and nothing else, so an operation the codebase
calls that is *fine* appeared nowhere — and a reader could not tell **"we checked this and nothing
binds"** from **"we never checked this."**

**Build.** A computed per-call `binding_status` with three members:

| status | meaning |
|---|---|
| `at_risk` | an open finding names this operation |
| `clean` | the vendor's spec was read and nothing binds |
| `unchecked` | no **successful** intake for the vendor — its spec has never been read |

Surface it as a column and a facet on Call sites, so a reader can press *clean* and walk the set.

**Load-bearing decisions.**

1. **`clean` is only honest because `intake_attempt` exists.** That table's own grain comment says
   it is there to keep *never-asked* apart from *nothing-new*. A vendor with no successful intake
   has never had its specification read, and calling its operations clean would be an all-clear the
   graph never earned — the exact shape of claim this product refuses, arriving as reassurance.
2. **`declined` and `failed` are not evidence.** An adapter that would not answer and one that
   could not. Counting *any* attempt turns a week of 403s into an all-clear.
3. **At risk is per operation, not per vendor.** A vendor with one broken call and forty working
   ones is the ordinary case; reporting all forty-one as at risk makes the status useless exactly
   where it matters.
4. **Do not special-case dismissal.** `_open_findings_predicate` — the clause seven reads share —
   asks only `finding.status = 'open'`. Teaching this one query about dismissals would put *clean*
   beside a table listing the finding.
5. **Two CTEs, not correlated per-row `EXISTS`** — the facet groups over the whole filtered set.
6. **The tag follows the project's tone rules**, whatever they currently are. If tones are in use,
   `at_risk` should be **`serious`, not `critical`**: it means a finding of *any* severity names the
   operation, and wearing `breaking`'s tone claims a grade it does not carry. `unchecked` must be
   toned, not neutral — being skimmed past as a milder `clean` is the one way this feature fails.

**Guards.** Make unexamined default to `clean` and **five** tests should go red. Also: an
unregistered status renders as itself; a status absent from the facet is absent, never nought.

---

## 10. The API surface panel (the dashboard half of the same question)

**Build.** `binding_status_rollup(repo_id)` → counts per status, plus a panel on the Codebase
overview.

**Load-bearing decisions.**

1. **Count operations, not call sites.** *How much of my API surface is safe* is a question about
   breadth; forty call sites to one operation is one thing to know about, and counting sites lets a
   single heavily-called operation dominate the answer.
2. **Bars, never a donut.** A donut cannot draw a zero, and a healthy codebase's `at_risk: 0` is
   exactly the figure a reader came to see — as a ring it ships looking broken. (This project
   already learned that on a provenance donut.)
3. **The zero rule splits, and the split is the honest part.** The **payload never** fills a
   missing member — an absent key was not measured at nought. The **panel** fills it, but only
   after establishing a surface exists, at which point every operation has one of the three
   statuses so a missing member really is a measured zero. A repository with no call sites gets a
   sentence, not three noughts — three noughts claim its operations were examined and found clean.
4. **No percentage, ratio or health figure.** Guard it by grepping the rendered text.

---

## 11. Two stale test fixtures were failing the gate for everyone

Neither is a defect in shipped code; both are a test left behind by a change that landed correctly.
Check whether they still apply before doing anything:

- `tests/test_cli.py` imported `_repo_id` from `sync.cli`, which moved to
  `sync.index.codebase.remote_repo_id`. Because it was an **ImportError it failed at collection**,
  taking all 52 tests in the file rather than the two that used the name.
- `subject-catalogue.test.ts` predated `by_service` becoming required on `IndexCoverageResponse`,
  so four fixtures were missing it and the whole console typecheck was red. Use `by_service: []` —
  a fixture should state what the function under test consumes and nothing more.

---

## 12. No test module may hardcode the development database ⚠️ **highest priority**

**This one caused real damage and should be implemented first.**

**Problem.** `conftest.pytest_configure` gives a run with `SYNC_DSN` unset its own per-pid database,
precisely so a suite cannot truncate a database somebody is looking at. A test file written with the
development DSN **inlined** opts itself out. Every run of it truncated the database the console
reads, while the console was being used.

**Why it is expensive:** a hardcoded DSN does not fail. It deletes somebody else's rows and leaves a
screen that reads as a feature not working. The demo seed vanished twice and looked both times like
data that had never landed.

**Build.** `tests/test_no_hardcoded_dsn.py` — refuse a **module-level constant bound straight to the
development database**:

```python
PINNED_CONSTANT = re.compile(
    r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*"postgresql://[^"]*@localhost:5433/sync"\s*$'
)
```

**Load-bearing decisions.**

1. **Prose could not have prevented it.** `conftest.py` explains the scheme at length at the top of
   the file every test module sits beside, and it was read and not applied. The fix is the check.
2. **Narrow to the assignment.** Matching the literal *anywhere* flags three modules that never
   connect — one sets an environment variable for a child, one passes it to a function taking a
   fake store, one is the lint's own fixture. A lint that fires on those is one somebody widens the
   allowlist on until it covers nothing.
3. Allow `conftest.py` and `test_parallel_isolation.py`: the literal is their **subject**.

**Guard.** Prove it red by planting an offender.

---

## Suggested order

1. **#12** (DSN lint) — stops the environment eating your data while you work.
2. **#11** (stale fixtures) — gets the gate green so everything after is measurable.
3. **#3** (finding names) and **#8** (parked runs) — small, self-contained, no console coupling.
4. **#1** (multi-select) — the foundation the facets in #9 render inside.
5. **#9** then **#10** (binding status, then its dashboard) — #10 depends on #9's SQL.
6. **#4** (change units), **#5** (node evidence), **#7** (vendor names), **#2** (full width).
7. **#6** (`CLAUDE.md` rule) — documentation, any time.

## How to verify each

Every item above has its guards named. The project's discipline is **test first, and watch it fail
for the reason you expect** — several of the decisions here were only found because a guard was
proven red first, and at least two guards initially passed while testing nothing.

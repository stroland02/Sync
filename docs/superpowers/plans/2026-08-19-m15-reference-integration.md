# M15 — Reference integration: the shell, the table, and the unit of work

**Owner direction, 2026-08-19.** *"go through all the reference and demo data to implement similar
UI features … the reference include nango, supabase, superlog, which all have codebases and
screenshots and more plans that you need to read through to build out."* Selections were taken
through four rounds of multiple-choice and are recorded in *Rulings* below.

**This is a plan, not a build.** Nothing in it has been implemented. Task order, the ledger and the
open questions are the deliverable.

---

## 1. What this milestone is for

Three references were studied and each answers a different question Sync has:

| Reference | The question it answers | Licence position |
|---|---|---|
| **Supabase** | How a control plane's *shell and tables* are composed | Apache-2.0, **owner-authorised code-level carve-out** (`specs/2026-08-06-sync-console-supabase-substrate-design.md`) |
| **Nango** | How an *integration catalogue* is presented and filtered | Concepts only |
| **Superlog** | What the *unit of investigation* is, and how a run reports | Concepts only |

`.claude/rules/interface-originality.md` governs all three: concepts, workflows and negative
findings transfer; renderings do not. The screenshot fence (`scripts/hook_guard_reads.py`) blocks
the images deterministically, so this plan is built from the notes, which are the adoptable half.

**One claim is refused across every task and is worth stating once.** Supabase's rail carries an
`ActiveDot` — red for errors, amber for warnings, driven by lint results. Their version clears a bar
ours cannot: a lint result is a stored, closed lifecycle with a definite pass or fail. Sync's
equivalent would be *is something wrong under this level*, which collapses **we could not check**
onto **we checked and it passed**. Refused, and the reason is our data rather than their taste.

---

## 2. Rulings taken as given

1. **All three Superlog items build**: clickable workflow steps, human-memorable finding names,
   findings fanning into an incident-like unit, a run state for waiting-on-a-human.
2. **All four Nango items build**: row → drawer with URL state, a closed tag vocabulary as
   components, faceted search with searchable multi-select, schema-driven integration config —
   **plus integration logos and professional names**, which the owner added.
3. **Three Supabase items build**: the two-tier shell, the layout primitives, the logs explorer —
   **plus full-page tables that use the whole width**, which the owner added and named as the
   most wanted.
4. **Populate before decorating.** Data first, then reference UI, so a drawer or a clickable
   workflow can be seen working rather than assumed.

---

## 3. What already landed, so this plan does not rebuild it

| Already built | Where | Note |
|---|---|---|
| Row → drawer with URL state | `features/bindings/call-site-drawer.tsx` (`CI-W514`) | **Uses the modal `Sheet`.** §7 records why that is the wrong half of the pattern. |
| Empty-state actions | 21 files (`CI-W514`) | Supabase's empty-state component was read and its four non-scenarios respected. |
| KPI strip as one instrument | `components/kpi-strip.tsx` (`CI-W511`) | Supabase's metric-panel *value above evidence* already applied. |
| Vendored Supabase primitives | `web/src/vendor/supabase/` | Card, sheet, table, badge, tooltip. Attribution in `web/NOTICE`. |

---

## 4. Tasks

Ordered so each one's verification is possible when it runs.

### Task 1 — Full-page tables *(owner's most-wanted; Supabase)*

**Problem.** Every table sits inside a `MetricPanel` inside a page container capped at
`max-w-[1400px]`, with a 16rem filter rail beside it. On a wide display the call-sites table shows
five columns in half the available width while 15 recorded fields sit unread.

**Build.**
- A `FullWidthTable` layout that breaks out of the panel and the page cap for table-first screens.
- Column visibility, persisted per table in `localStorage`.
- A sticky header and a pinned footer bar (Supabase's `GridFooter` is a 10px strip under the data
  view carrying the record count and an assistive label).
- Applies to: Call sites, Changes, Findings, Logs → Runs, Connections.

**Refused.** Virtualised rows. The largest set here is 165 call sites; a virtualiser buys nothing
below a few thousand and costs a scroll container that breaks find-in-page.

**Verify.** At 1440 and 1920, every column readable without horizontal scroll; find-in-page reaches
a row below the fold; the record count still names the narrowed set.

### Task 2 — The inline detail panel replaces the modal drawer *(Supabase)*

**Problem.** `CI-W514` shipped the row detail as a modal `Sheet`. Supabase's own note says that is
the *other* pattern: a sheet is for a longer form where switching pages would be disruptive. The one
worth taking is `UserPanel` — **not modal**, a resizable panel beside the list, so the list stays
readable and a reader can move down rows without closing anything.

**Build.**
- Non-modal resizable panel beside the table.
- URL state with `history: "push"` so **Back closes it**, and the parameter cleared on default so a
  screen with nothing selected has one canonical URL.
- Keyboard: up/down moves the selected row with the panel open.

**Verify.** Back closes the panel rather than leaving the page; the URL with no selection carries no
empty parameter; arrow keys move the selection.

### Task 3 — The closed tag vocabulary *(Nango)*

**Problem.** Severity, rung, run outcome, change kind and adapter tier are each spelled per screen.
`RungBadge` is the only one that is a component.

**Build.** One `Tag` family with a member per vocabulary, each legible without its colour, drawn
from `DESIGN.md`. **No status hue outside the three the surface rules permit** — run outcome, error
state, absence.

**Verify.** A grep finds no ad-hoc chip in `features/`; every vocabulary renders from one place.

### Task 4 — Faceted search with searchable multi-select *(Nango)*

**Problem.** The filter rails are single-select lists. A codebase with 40 integrations is not
filterable, and operation and rung are not offered at all.

**Build.** Per-facet search, multi-select, counts computed with that facet's own filter ignored (the
rail's existing rule). Facets: integration, operation, path prefix, rung, loop depth.

**Verify.** Selecting two integrations returns the union; a facet's own counts do not collapse to
the selection.

### Task 5 — Integration logos and professional names *(Nango; owner addition)*

**Problem.** Integrations render as bare ids — `stripe`, `anthropic`. `VendorMark` exists and is
used in one table.

**Build.** A registry mapping vendor id to display name and mark, used everywhere a vendor is
named: Connections, Integrations, Settings, call sites, findings, the maps.

**Open question — Q1 below.** Where the marks come from is a licensing question, not a design one.

### Task 6 — Findings get a human-memorable name *(Superlog)*

**Problem.** A finding is a 32-character hex id. Two people cannot discuss one.

**Build.** A deterministic short name derived from the finding's own identity — vendor, operation
and change kind — so it is stable across re-derivation and needs no new column.

**Refused.** A random word pair. It would not survive `insert_finding` re-hashing, and a name that
changes on re-scan is worse than an id.

**Verify.** The same finding names identically across two scans; two findings do not collide within
one workspace.

### Task 7 — Findings fan into a change unit *(Superlog)*

**Problem.** 24 findings are really 13 change units. The console lists them flat, so a reader sees
24 problems where there are 13.

**Build.** `/api/change-units` already returns them and `ChangeUnitsTable` already renders them.
Make the unit the primary object on Findings, with its findings nested.

**Verify.** The counts reconcile — a unit's finding count sums to the flat total.

### Task 8 — A run state for waiting on a human *(Superlog)*

**Problem.** A run needing review is indistinguishable from one in flight.

**Build.** Extend the run vocabulary, which is a **spec amendment first**:
`specs/2026-08-04-sync-run-state-and-abandonment-vocabulary.md` is the authority and
`.claude/rules/console-hierarchy.md`'s ordering rule applies — the vocabulary changes there, then
in the graph, then in the console.

**Verify.** A run in the new state renders as a badge from the closed vocabulary, legible without
colour.

### Task 9 — Clickable workflow steps *(Devin, via Superlog note)*

**Problem.** `NodeSequence` lists what each node did. The note's line: *the node list is not a
static summary, it is an index into recorded state*. Clicking `static_verify` should show the
compiler output that node produced.

**Build.** Each node opens its recorded evidence — in the inline panel from Task 2. **The
checkpointer already holds all of it**, so this is exposing rather than capturing.

**Verify.** Every node with recorded evidence opens it; a node without says which nothing that is.

### Task 10 — The two-tier shell *(Supabase)*

**Problem.** One flat rail carries seven destinations; the levels are already declared in
`GRAPH_LEVELS` and unused as navigation.

**Build.** An icon rail of levels, with a contextual sidebar for what sits under the level you are
inside.

**Sequenced last deliberately.** It touches every screen, and doing it before Tasks 1–9 would mean
rebuilding each of them inside a moving shell. **`ActiveDot` is refused** — §1.

**Verify.** Every declared route reachable; `routes.test.tsx` and `hrefs.test.ts` green without
relaxation.

### Task 11 — The logs explorer *(Supabase)*

**Problem.** Logs is a table plus a filter rail. The explorer pattern is query-driven with saved
queries.

**Open question — Q2 below.** What the query language is over is not obvious, and the API is
read-only with no SQL surface.

---

## 5. Sequencing

```
Data first     → production run (populates Solutions/Sankey)   ← owner decision, Q3
Foundation     → Task 3 (tags) → Task 1 (full-page tables) → Task 2 (inline panel)
Content        → Task 4 (facets) → Task 5 (logos) → Task 6 (names) → Task 7 (units)
Pipeline       → Task 8 (run state, spec first) → Task 9 (clickable steps)
Shell          → Task 10 (two-tier) → Task 11 (logs explorer, pending Q2)
```

Tasks 3, 1 and 2 are the foundation because 4–9 all render inside them.

---

## 6. What this plan refuses

- **A status dot on a navigation item.** §1.
- **A confidence scalar**, in any borrowed component. Superlog's incident view is the best thing in
  the reference set and it carries `Root cause confidence: 9`. Take its structure, refuse its
  scalar.
- **Virtualised tables** at this cardinality. Task 1.
- **A random-word finding name.** Task 6.
- **Copy lifted from any reference interface.** Every label here is written for Sync.

---

## 7. A correction this plan carries

`CI-W514` shipped the Call sites row detail as a modal sheet, citing Nango's row → drawer pattern.
Nango's note does say drawer; **Supabase's note says which drawer**, and the modal is the wrong one
for a list a reader moves down. Task 2 corrects it. Recorded here rather than quietly fixed, because
the reasoning is the reusable part.

---

## 8. Open questions for the owner

**Q1 — Integration marks (Task 5).** A vendor's logo is their trademark.
`interface-originality.md` excludes identity elements from every reference, and that reasoning
extends to the vendors Sync watches. Options: (a) official marks from each vendor's own brand
assets, honouring each licence individually; (b) a neutral generated mark per vendor — initial and
a palette slot, no trademark; (c) text only.

**Q2 — Logs explorer (Task 11).** The API is read-only and exposes no query surface. Options: (a) a
structured filter builder over existing facets, not a language; (b) saved filter combinations with
shareable URLs; (c) drop the task.

**Q3 — Production run.** Solutions, the Sankey and the activity charts stay empty until a
**production** run exists — `sync rehearse` writes `is_rehearsal` rows, which every rate and
activity query filters out by the corpus's own rule. A production run opens a real pull request on
a real repository. That is one of the three things `autonomous-development.md` reserves for the
human.

---

## 9. Ledger

| # | Decision | Against | Why |
|---|---|---|---|
| 1 | Build from the notes, never the screenshots | Reading the captures | The fence hook blocks them; the notes restate what is adoptable as a problem rather than a picture |
| 2 | Two-tier shell sequenced last | Doing it first, as foundation | It touches every screen; earlier tasks would be rebuilt inside a moving shell |
| 3 | Inline panel replaces the modal sheet | Keeping `CI-W514`'s sheet | Supabase's own note: a sheet is for a longer form, an inline panel for a list a reader moves down |
| 4 | Derived finding names | Random word pairs | A name must survive `insert_finding` re-hashing |
| 5 | No virtualisation | Adding it with full-page tables | 165 rows; a virtualiser breaks find-in-page for no gain |
| 6 | Run-state change is a spec amendment first | Adding the state in the graph | `console-hierarchy.md`'s ordering rule: the authority changes before the code |

# Fleet on the substrate — the mapping table, and the rulings it forced

Task 5 of `docs/superpowers/plans/2026-08-06-console-supabase-substrate.md`. Work item M7-W172.

Fleet is the console's index route and the first level ported onto the vendored Supabase
components. It is deliberately the first, because the shape of this document is the shape every
remaining level copies: **the mapping table before the port, the recomposition, the completeness
walk against the same seed after.** A level that is ported without this file has skipped the gate
the specification's section 10 exists to hold — that every field the current screen renders lands
in a named slot, and that a field with no slot is resolved here as a written ruling rather than
dropped in passing.

The table below was built by reading `fleet-page.tsx` and each of its six children, not from
memory. Every rendered string, every count, every state branch is a row.

## The mapping table

### `fleet-page.tsx` — the page shell

| Field rendered today | Substrate slot |
|---|---|
| title "Fleet" | `PageHeader` title, unchanged — `layouts/` is the chassis and is not reopened here |
| the route's own question, read from `ROUTES` | `PageHeader` question, unchanged |
| breadcrumb trail "Fleet" | `PageHeader` trail, unchanged |
| control bar "Scope" label and "Every repository the index has seen." | `ControlBar` left slot, unchanged |
| control bar action "Detector attribution" → `/detectors` | `ControlBar` action slot, unchanged |
| the no-composite-health paragraph ("we could not check") | page body, beside the fact rail, unchanged in wording and position |

### `fleet-facts.tsx` — the fact rail

| Field rendered today | Substrate slot |
|---|---|
| tile OPEN FINDINGS, value `describeBoundedTotal(total_findings, bound_reached)` | fact tile, unchanged |
| its note — the bounded caveat, or "Across every vendor, every repository." | fact tile note, unchanged |
| tile RUNS, value `runs.total` | fact tile, unchanged |
| its note "One per checkpoint thread, not one per finding." | fact tile note, unchanged (protected) |
| tile REPOSITORIES INDEXED, value `repo_ids.length` | fact tile, unchanged |
| its note "Holding at least one call site. Never indexed has no row." | fact tile note, unchanged |
| tile REPAIR ATTEMPTS, value `corpus.attempts` | fact tile, unchanged |
| its note "One row per attempt." plus the detector count | fact tile note, unchanged |
| per tile: `Skeleton` while pending | unchanged — see the skeleton ruling below |
| per tile: `Absent`("the API did not answer") on failure | unchanged |

`fact-tile.tsx` is not restyled. See the ruling on why re-pointing it at the vendored `Card`
would change nothing on screen.

### `vendor-distribution.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "Open findings by vendor, across N vendors" | metric panel: label VENDORS WITH OPEN FINDINGS, value **N** at the figure register, above the evidence |
| description — the fleet roll-up versus the per-repository answer | metric panel caption, beneath the value |
| `boundedTotalCaveat` paragraph when the count stopped early | metric panel caption, second paragraph, rendered on the same condition |
| empty state "No vendor is at risk." with its detail | `EmptyState`, unchanged, inside the panel body |
| cardinality statement over vendors | panel body, above the table |
| column Vendor, as a link carrying the scope | table identifying column, link, Studio header register |
| column Open findings | table column, mono |
| `ProvenanceStrip` with both `bindingNullLabel` variants | panel body, beneath the table, unchanged |
| loading and error states | unchanged, outside the panel |

### `runs-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "Runs" | panel title — no figure, the run total is the fact rail's tile |
| description "One row per checkpoint thread, not one per finding…" | panel caption (protected) |
| empty state "No run has ever checkpointed." with its detail | `EmptyState`, unchanged |
| "By disposition, this page only" label | furniture label in the panel body |
| the tally line itself | mono line beneath it |
| "Counted across the N runs shown below, not the fleet…" | the sentence under the tally, unchanged |
| cardinality statement, below the threshold | panel body, above the table |
| column Finding, as a link to the workflow | table identifying column, link |
| column Node the graph owes | table column, `Formatted`/`orAbsent` |
| column Outcome, and `abandon_reason` beneath it when abandoned | table column, unchanged — the reason stays a second line in the same cell |
| column Last checkpoint, `formatElapsed` | table column |
| `FooterBar` with pagination and the cardinality sentence in `left` | unchanged, above the threshold only |
| the staleness-not-liveness paragraph | panel body, beneath the table, unchanged (protected) |
| loading and error states | unchanged |

### `screen-limits.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "What this screen cannot tell you" | panel title, no figure |
| description "Four standing limits of the data behind this page…" | panel caption |
| limit 1 — a repository the index never indexed is invisible | `dl` row, unchanged (protected: "nobody ever configured") |
| limit 2 — the repair record's denominator excludes the earliest failures | `dl` row, unchanged |
| limit 3 — "Last checkpoint" is staleness, not liveness | `dl` row, unchanged (protected) |
| limit 4 — findings cannot be ordered by severity across vendors yet | `dl` row, unchanged |

### `corpus-summary.tsx` and `corpus-chart.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "Repair record" | metric panel label REPAIR RECORD |
| stat tile "Attempts" (inside the chart component) | **removed from this panel** — the fact rail already carries it; see the ruling |
| stat tile "Distinct findings" | metric panel value at the figure register, above the chart |
| description "…counts once toward findings." | metric panel caption (protected) |
| the paragraph on `migration_outcome` holding no repository | metric panel caption, second paragraph |
| empty state "The graph holds no repair attempts." with its detail | `EmptyState`, unchanged |
| the "By disposition" stacked bar | chart component unchanged, placed in the panel body beneath the value |
| its legend | unchanged — echarts `roundRect` icon plus the disposition word, which is already dot-with-word |
| its figcaption on what the table holds nothing for | unchanged, beneath the chart |
| tally table By disposition (Value, Attempts) | table, Studio header register |
| tally table By strategy | table |
| tally table By tier | table |
| loading and error states | unchanged |

### `repositories-table.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "N repositories indexed" | panel title, count kept in the sentence — the fact rail carries the figure |
| description, carrying "never indexed has no row" and "cannot tell the two apart" | panel caption, unchanged (both protected) |
| empty state "The index has seen no repository." with its detail | `EmptyState`, unchanged |
| cardinality statement over repositories | panel body |
| column Repository, mono, as a link | table identifying column, link |
| loading and error states | unchanged |

### `detectors-summary.tsx`

| Field rendered today | Substrate slot |
|---|---|
| title "N detectors with open findings" | panel title, count kept in the sentence — the rail's fourth tile note carries it |
| description on open findings being the only findings the graph offers | panel caption |
| empty state "No detector has an open finding." with its detail | `EmptyState`, unchanged |
| cardinality statement over detectors | panel body |
| column Detector | table column, mono |
| column Open findings | table column |
| column By rung, `summariseTally` | table column — never hidden, never coloured |
| loading and error states | unchanged |

## The rulings

Eleven fields or components had no obvious slot. Each is resolved here rather than in a commit
message, because the next eight levels will meet the same questions.

**1. The metric panel's value takes the figure step, not the display step.** The brief for this
task says "value at display size". `tests/test_console_design_tokens.py`'s
`test_exactly_one_component_spends_the_display_step` makes `layouts/page-header.tsx` the only file
in the tree permitted to spell `text-display`, and the reason is written into that guard: two
consumers on one screen is two focal points, which is none. The console's figure step
(`--text-figure`, 28px) is what a headline count was added for. So "display size" here means the
largest step a panel may spend, and that is the figure step.

**2. A count the fact rail already carries is never re-rendered at the figure register.** M7-W163
established this and removed the open-findings total from the vendor panel for exactly this reason:
two renderings of one count is a fact written twice, and the one that stays is the one an operator
reaches first. So of the six panels, only two carry a metric value — the vendor count, which is the
vendor panel's own grain and appears nowhere else, and the corpus panel's distinct-findings figure.
The repository count, the detector count and the run total stay as sentences in their panel titles,
where they already are.

**3. The corpus panel loses its "Attempts" figure and leads with distinct findings.**
`corpus-chart.tsx` rendered both as stat tiles at the figure register, and the fact rail's fourth
tile has rendered `attempts` since M7-W163 — so the same number was on screen twice at the same
weight, which is the defect ruling 2 names. Distinct findings is the figure the rail cannot carry,
and it is the one whose difference from attempts is the grain rule this panel exists to state. The
attempts figure is still asserted on this screen, by the rail tile; the protected sentence that
relates the two ("counts once toward findings") is unchanged and now sits directly beneath the
figure it qualifies.

**4. No row on Fleet gets a `⋮` overflow menu.** The instruction is that the menu appears only
where a row has more than one action today. Every row on this screen has exactly one: a repository
row links to that repository, a run row links to that finding's workflow, a vendor row links to
that vendor. The API is read-only, so a second action would have to be invented. A menu whose only
entry duplicates the link the row already is, is furniture claiming a choice nobody has — the same
argument `layouts/footer-bar.tsx` already makes against a page-size selector with one option. The
vendored `dropdown-menu` is therefore not imported by this feature.

**5. `layouts/` is not reopened, so `FooterBar`, `PageHeader`, `ControlBar` and `Breadcrumbs` are
consumed unchanged.** Task 4 finished the chassis and this task's file list excludes it. The
runs table keeps `FooterBar` exactly as it is.

**6. `components/skeleton.tsx` stays; the vendored `skeleton` is not adopted.** The vendored
component is `animate-pulse rounded-md bg-muted`. The console runs zero animations at rest on all
nine routes, held by `test_no_keyframes_or_animation_shorthand_outside_the_component_catalog`, and
`components/skeleton.tsx`'s own docstring records that a bar plainly not a value is already legible
without motion. This is the case the task anticipated — a component that fights the substrate is
kept and noted rather than forced.

**7. `fact-tile.tsx` and `fact-list.tsx` are left alone, because the restyle is already done.**
Task 3 resolved `--color-surface` to `oklch(0.215 0.0025 159)`, which is the same literal as
`--background-color-surface-100`, and `--radius-surface` to `0.5rem`, which is `rounded-lg`. A tile
built from `rounded-surface border border-line bg-surface` therefore renders the vendored card's
plane already. Re-pointing it at the vendored `Card` would touch every level that renders a tile
and change one thing on screen: it would add `shadow-xs`. Not worth the churn in this task.

**8. `components/data-table.tsx` is new, and it is where the Studio table anatomy is declared
once.** The vendored `TableHead` asks for a `heading-meta` class that this tree does not define —
the console's equivalent is `.furniture`, defined in `index.css` since the design-system slice — and
the vendored cell padding does not resolve to the row heights `DESIGN.md` derives. Rather than
hand-spell the same three classes on every `TableHead` and `TableCell` across nine levels, the
anatomy is one file: the vendored primitive with the console's header register and the arithmetic
`DESIGN.md` publishes (header 40px at `row-lg`, single-line body row 36px at `row-md`). Task 6's
levels import from there.

**9. `--card-padding-x` is declared in `index.css`.** The vendored `Card` spells its horizontal
padding as `px-(--card-padding-x)` and Supabase declares that variable in their own globals, which
were not vendored. Undeclared, every card renders with no horizontal padding at all. It is wired to
`--spacing-section`, which is the 16px the vendored card's own `py-4` already uses, so the card is
square. It is not a new design token: it names no new value, it sits outside the eight theme
families `DESIGN.md`'s contract governs, and it exists to connect a vendored component to a
spacing token that was already argued.

**10. The `variant="grouping"` distinction collapses, and every panel now carries a hairline.**
`components/ui/card.tsx` declares two variants and argues the difference: `plain` draws no ring,
because a panel's own surface step already tells it apart from the page, and `grouping` draws the
hairline for the one case a step alone cannot cover — a card beside another card at the same depth
with nothing between them. `RepositoriesCard` and `DetectorsSummaryCard` were the two callers on
this screen. The vendored `Card` has no variants and draws `border` unconditionally, so on the
substrate every panel is ringed and the distinction has nothing left to express.

Accepted, as a consequence of the substrate rather than a decision taken on its merits. Studio's
own panels are ringed on every surface, the ring is the 7.5%-alpha hairline rather than a visible
frame, and the M7-W170 ruling is that the substrate's values win where they disagree with an
earlier local argument. What the older argument was protecting — that depth should carry the
grouping claim rather than an outline — is not lost so much as no longer expressible, because the
substrate does not offer an unringed panel.

Reversing it is small and local: give `MetricPanel` a `grouping` prop that adds `border-0` to the
vendored `Card` for the default case, and pass it everywhere except the two paired panels. Nothing
in `vendor/` needs editing either way. What it would cost is a console whose panel outlines differ
by position, which is the thing the substrate decided against.

**11. A panel title moves from `text-emphasis` to the furniture register.** The mapping table's
rows say "panel title" and imply the register came along unchanged; it did not. Every panel name
on Fleet is now uppercase, open-tracked `--text-meta` at the second ink level — Studio's card-title
treatment, and the same register `fact-tile.tsx` uses for a label. `--text-emphasis` was the old
panel-title role and no panel spends it any more.

The consequence to know before porting a level: **a panel name is now visually lighter than
emphasis text inside the panel it contains**, and that is the arrangement rather than a defect.
`DESIGN.md` assigns type by role, not by size — a panel name is scanned and a sentence inside it is
read — so the two are not two points on one weight scale. `screen-limits.tsx` is where this is most
visible, because its four `dt` headlines sit at `text-emphasis` under a furniture-register panel
name, and its comment states the constraint.

**The heading level does not follow the register.** `metric-panel.tsx` writes its own `h2` rather
than taking the vendored `CardTitle`, which is an `h3` and accepts no `asChild`. A panel is the
level directly under `PageHeader`'s `h1`, and `corpus-summary.tsx`'s tally headings are `h3` inside
a panel — a panel at `h3` would put a container and its contents on one outline level and leave the
document with no `h2` at all. Outline and visual weight are two decisions and the substrate only
settles the second.

One consequence worth stating rather than discovering: `VendorFindingsTable` is exported from
`features/fleet/vendor-distribution.tsx` and imported by `features/repositories/open-findings-card.tsx`.
Restyling it here restyles that screen's table too. That is the substrate migration working as
intended and not a scope leak — the Codebase level's own port will find its table already correct.

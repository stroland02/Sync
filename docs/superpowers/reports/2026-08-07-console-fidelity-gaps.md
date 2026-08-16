# Fidelity gap analysis — the owner's screenshots against Studio's source and the console today

**Work item:** M7-W181. **Scout only — nothing here was implemented.**

Three inputs, and each row below joins all three:

1. **The owner's screenshots**, now filed durably under `docs/superpowers/references/direction/`
   (twenty-four Supabase screens, four Superlog). The index is at the foot of that directory's
   `NOTES.md`.
2. **Supabase Studio's source at the pinned commit** `6ac031673869c67a7c446b1c8cac8ce43476200b`
   (`6ac0316`) — the same commit `web/NOTICE` pins for the vendored components. Read from a sparse
   clone outside the repository, since deleted.
3. **The console measured in Chrome at 1440x900** against this worktree on branch
   `console-identity`, walking Fleet, a repository, a vendor, `/detectors`, and the finding
   `9f176dea35907f95beb29553e574a037` with its workflow and pull-request screens.

## What this report found before any individual gap

**The console is much further along than the direction notes describe, and the notes are stale
rather than wrong.** Entries 1 through 6 of `NOTES.md` were written before the substrate work
landed. Since then the theme swap, the two-tier chassis, the vendored table, the page header, the
control bar, the footer bar, the fact tile, the metric panel, the skeleton and one drawer have all
shipped. Several properties those entries name as absent now exist.

So the gaps below are narrower and more specific than "the console lacks a chassis." The largest
one is a whole component that was never built rather than one built badly.

## Constraints that do not move, whatever a screenshot shows

Every proposal in this document is bounded by these. A row whose fix would breach one is marked
**refused** in place rather than left for an implementer to discover.

- **No composite score, health figure, traffic light, green dot, liveness pulse or count-up.**
  Refused four times on the record. Superlog's `confidence 9/10`
  (`superlog-02-incident-findings-tab.png`) and Supabase's `STATUS Healthy` tile
  (`supabase-02-project-overview-populated.png`) are both instances of exactly this, and both are
  refused. Where a vendored component has a slot for one, the slot renders the rung, a
  closed-vocabulary badge, or the absence sentence.
- **The twenty-four protected sentences.** Restyling one is allowed; deleting, shortening,
  collapsing behind a disclosure or moving into a tooltip is not.
  `tests/test_console_honesty_sentences.py` is the merge gate.
- **Absence is not zero. Staleness is not liveness. Never-measured is not nothing-here.**
- **The provenance rung travels on every binding and every artifact derived from one**, monochrome,
  at two levels, never a hideable column.
- **The API is read-only.** No proposal here introduces a write path.
  `test_no_route_reaches_past_the_read_surface` holds it.
- **Dark-only**, on the owner's instruction of 2026-08-05.
- **The six rail areas and `GRAPH_LEVELS` come from the specification**, not from a plan and not
  from a screenshot. Areas group levels; they never invent one.
  `docs/superpowers/specs/2026-08-06-sync-console-supabase-substrate-design.md` section 4 carries
  the grouping; `.claude/rules/console-hierarchy.md` carries why.

Two further boundaries are worth stating because a screenshot makes each tempting:

- **A time range is a control, and we have almost nothing to scope with it.** Supabase's
  `Last 60 minutes` selector scopes every count on its metrics strip. Ours would have exactly one
  honest subject — `observed_error_window`, which is stored per window already. Anything else on
  our screens is a graph state rather than a time series, and a range control over it would claim a
  window the number does not have.
- **A vendored component is consumed, never forked.** Restyling happens in `web/src/components/`
  and in composition. A fix that edits `web/src/vendor/supabase/` has left its scope.

## Four things Studio does that this report recommends against copying

Each was checked in source rather than inferred from a screenshot, and each is a defect in the
reference rather than a decision we are declining.

- **The rail's `ICON_SIZE = 32` constant is dead.** `Sidebar.tsx:47` declares it and every route
  passes it, but `sidebarMenuButtonVariants` ends `[&>svg]:size-5`
  (`packages/ui/src/components/shadcn/ui/sidebar.tsx:509`) and a CSS rule beats an SVG presentation
  attribute. Studio's icons render at 20px. Ours already do. **Do not port the 32.**
- **Studio's grid header height is undefined.** `grid.css:130-134` reads
  `height: var(--header-row-height)` and that variable is defined nowhere in the repository, so the
  declaration is invalid and react-data-grid's default wins. The house standard visible in every
  *other* Studio grid is `rowHeight={44}` / `headerRowHeight={36}`.
- **Studio's selected row and hovered row are the same colour.** `grid.css:190-192` sets
  `.rdg-row[aria-selected='true'] { @apply bg-200; }` against a `hover:bg-200` — the two are
  indistinguishable. Our table has the identical collapse and it is listed as a gap below; copying
  Studio would not fix it.
- **Studio's rail carries a status dot.** `Sidebar.tsx:227-247` renders `ActiveDot` beside Advisors,
  `bg-destructive-600` or `bg-warning-600`, colour-only and unlabelled. **Refused** — this is the
  green-dot prohibition exactly, and the honest version is a counted, worded badge.

Three further Studio facts are inconsistencies rather than defects, and a port must pick one
deliberately rather than average them: there are **three different small-caps recipes** in the
tree (`ProductMenu` at `uppercase font-mono text-sm` with no tracking; `InnerSideMenu` at
`text-sm font-mono uppercase tracking-wide`; and the canonical `heading-meta` at
`text-xs font-mono uppercase tracking-wider font-medium`, `packages/config/typography.css:22-24`),
**two page-scaffold families** with different paddings and different subtitle sizes, and **two list
tables** whose headers do not resemble each other.

---

## Surface 1 — the top bar

**This is the largest gap in the report, and it is a whole component rather than a badly built one.**
Studio's shell puts a banner slot, then a header, then the rail and the content beside each other.
The console's shell has no header row at all: `AppFrame` renders the rail, the contextual sidebar and
`<main>` as three flex children, and `<main>` begins at `y=0` on every route. `[role=banner]` count
is **0**.

What that costs is not decoration. The console has nine levels in one hierarchy and no persistent
statement of which subject you are inside. A breadcrumb exists, but it is *inside* the page header,
inside the scrolling column, and on the detail pages inside a 360px column — so it leaves the screen
on the first scroll.

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-01`, top strip: a 48px bar above everything with a hairline under it | `LayoutHeader.tsx:104` `<header className="hidden md:flex h-11 md:h-12 items-center shrink-0 border-b">`, mounted at `DefaultLayout.tsx:108` inside a `shrink-0` div above the rail-and-content row (`:101-111`). Inner bar `:116-119` `justify-between h-full pr-3 flex-1 overflow-x-auto gap-x-8 pl-4` | **Absent.** No `<header>` outside `main` | The entire bar | **M** | `layouts/app-frame.tsx` — a new sibling above the rail row |
| `supabase-01`, `stroland02's Org` `FREE` / `stroland02's Project` / `main` `PRODUCTION`, each with an up-down control, slanted-slash dividers between | Three switchers, `LayoutHeader.tsx:142-181`: `HomeIcon` then divider, `OrganizationDropdown`, divider, `ProjectDropdown`, divider, `BranchDropdown`. The divider is a hand-drawn SVG slash — `LayoutHeader.tsx:37-54`, `<span className="text-border-stronger pr-2">` around `<path d="M16 3.549L7.12 20.600" />` at 16x16. Shared trigger anatomy at `AppLayout/AppLayoutDropdown.tsx:59-67`: a `<Link>` that navigates sits *beside* a separate `ChevronsUpDown` button that opens the popover (`:27-34`). The popover is a cmdk command menu with its own search — `OrganizationDropdownCommandContent.tsx:100-131` | **Absent.** `layouts/breadcrumbs.tsx:23` renders a literal `→` between plain links, inside `PageHeader` | NOTES entry 3 maps these to fleet / repository / vendor. Nothing in the console changes scope in place; every level change is a navigation | **L** | new `layouts/scope-switchers.tsx`, over the already-vendored `popover.tsx` and `command.tsx`; reads `lib/routes.ts` |
| `supabase-01`, the `FREE` and `PRODUCTION` chips | `packages/ui/src/components/shadcn/ui/badge.tsx:7-12` — `rounded-full tracking-[0.07em] uppercase font-medium text-[9px] leading-none px-[5.5px] py-[3px]`; `default` is `bg-surface-75 text-foreground-light border border-strong`. `BranchBadge.tsx:13` uses `variant="warning"` for Production | `vendor/supabase/ui/badge.tsx` is vendored and `RungBadge` consumes it; nothing in the chrome does | **9px is below the console's 11px floor, so the chip is not portable as drawn.** The closed-vocabulary chip transfers; the size does not | **S** | `components/provenance.tsx`; `DESIGN.md` if a chip step is added |
| `supabase-01`, right side: `Feedback`, a rounded `Search... Ctrl K` field, five icon buttons, an avatar | `LayoutHeader.tsx:227-257` in order: `FeedbackDropdown`, `CommandMenuTriggerInput` (`hidden md:flex md:min-w-32 rounded-full`), `HelpButton`, `AdvisorButton`, `InlineEditorButton`, `AssistantButton`, `UserDropdown` | **Absent.** The palette is `Ctrl/Cmd-K` with no on-screen trigger (`layouts/command-palette.tsx`) | A keyboard-only affordance nobody can discover. **Only the search trigger transfers honestly** — we have no account, org, assistant or feedback channel, and inventing furniture for them is chrome with nothing behind it | **S** | `layouts/command-palette.tsx` exports a trigger; `layouts/app-frame.tsx` places it |
| No banner in the screenshots; Studio reserves the slot | `DefaultLayout.tsx:100` mounts `<AppBannerWrapper />` above the header div; `AppBannerWrapper.tsx:41-47` stacks four banner kinds | `components/error-surface.tsx` floats errors over content — the owner's own capture showed 92 stacked "API is unreachable" cards obscuring the page | No structural slot; the error surface overlays rather than displaces | **S** | `layouts/app-frame.tsx`, `components/error-surface.tsx` |

**One thing to refuse.** Studio's header is `overflow-x-auto`, so at narrow widths the scope trail
scrolls sideways and the current subject can leave the screen. Ours should truncate with the subject
held.

---

## Surface 2 — the rail and the contextual sidebar

The two-tier arrangement exists and matches. The gaps are in behaviour, and in how little the second
tier currently holds.

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-02` rail collapsed to icons; `supabase-01` the same rail expanded to labels | `sidebar.tsx:20-22` `SIDEBAR_WIDTH_ICON = '3rem'` (48px) / `SIDEBAR_WIDTH = '13rem'` (208px). `Sidebar.tsx:85-90` expands on `onMouseEnter` when the stored behaviour is `expandable`; three modes — Expanded / Collapsed / Expand on hover — from a `DropdownMenuRadioGroup` in the footer (`:104-115`), persisted under `LOCAL_STORAGE_KEYS.SIDEBAR_BEHAVIOR`, default at `:50` | **40px, fixed.** `[data-sidebar=trigger]` and `[data-sidebar=rail]` both count **0**; no `data-collapsible`. Labels exist only as `aria-label` | The rail never shows a label — six areas are six permanently unlabelled glyphs. Hover-expand is the cheapest legibility fix available and the vendored primitive already ships it | **M** | `layouts/app-frame.tsx` (`AreaRail`) |
| `supabase-01` rail: four clusters separated by rules, `Project Settings` last | `Sidebar.tsx:284-369` — four `SidebarGroup`s at `gap-0.5` separated by `<Separator className="w-[calc(100%-1rem)] mx-auto" />` (`:308, 321, 356`). **Nothing is `mt-auto`**; Settings is simply the last group in flow. The only pinned element is the behaviour control in `SidebarFooter` (`:150-152`) | One flat `<ul>`, no dividers, no grouping. Settings *is* pinned, by `flex-1` on the list, at `y=860` | Ours pins Settings where Studio does not; Studio groups where ours does not. Six items may not need grouping — **this row is a question for the owner rather than a defect** | **S** | `layouts/app-frame.tsx`, `lib/routes.ts` (`AREAS`) |
| `supabase-06`/`07` sidebar headings: `DATABASE MANAGEMENT`, `ACCESS CONTROL`, `CONFIGURATION`, `PLATFORM` | Three recipes in one tree. `ProductMenu/index.tsx:19-26` with `Menu.tsx:145-152` gives `uppercase font-mono text-sm text-foreground-lighter font-normal` — **no tracking**. `InnerSideMenu/index.tsx:36` gives `text-sm font-mono uppercase tracking-wide`. Canonical `heading-meta` is `text-xs font-mono uppercase tracking-wider font-medium` (`packages/config/typography.css:22-24`) | `[data-sidebar=group-label]` — 12px / 500 / uppercase / ls 0.3px in a 32px box; the labels are the specification's own level names | **Already right, and closer to Studio's canonical recipe than two of Studio's own menus.** No change | — | `layouts/app-frame.tsx:284` |
| `supabase-06` sidebar carries ten destinations under four headings | Rows: `ProductMenu` intrinsic-height `py-[3px] px-3 rounded-md`; `InnerSideMenu` fixes `h-7`. Active `bg-sidebar-accent` + `font-semibold` (`Menu.tsx:62-94`), computed from a `pages` array (`ProductMenu/index.tsx:33-35`) | 32px rows, active `bg-surface-emphasis` + `font-medium`, `isActiveMenuItem` in `lib/routes.ts` | **The mechanism matches; the content does not.** Fleet's sidebar is one group with one item. On the finding, workflow and PR routes **all three rows are `<span>`, not `<a>`** — the second tier stops being navigable exactly where the hierarchy is deepest | **M** | `lib/routes.ts`, `layouts/app-frame.tsx` (`DestinationRow`) |
| `supabase-01` rail active item: filled surface, brighter text | `sidebar.tsx:509` `data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground data-[active=true]:font-medium`, `rounded-md`, no border | Rail active `oklch(0.95 0.00275 159 / 4.93%)`; the sidebar's active fill is **the identical alpha** | Two tiers marked with one value; which tier you are reading is carried by position alone | **S** | `layouts/app-frame.tsx`, `DESIGN.md` surface ramp |
| `superlog-03` / `superlog-04`: every icon at the identical vertical position across the collapse | — | Not applicable while the rail cannot collapse | NOTES entry 6's mechanical test has nothing to test yet. **It becomes the acceptance criterion the moment hover-expand lands** | — | `layouts/app-frame.test.tsx` |

---

## Surface 3 — the page scaffold

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-07`: `Database Extensions` over `Manage what extensions are installed in your database` | `ui-patterns/PageHeader/index.tsx` — title `heading-title` = `text-2xl tracking-tight` (**24px**), description `heading-subSection text-foreground-light` (**16px**), pair at `flex flex-col gap-1`, container `gap-4 w-full`, `large → pt-12` | `h1.text-display` **46px / 600 / ls −2.07px**; subtitle 13px, 4px below | **The two-line header exists and is right in kind.** The title is nearly twice Studio's, which is defensible on its own — but see the next row | — | `layouts/page-header.tsx` |
| `supabase-08`, `supabase-18`: a detail's identifier is small, and the title stays a name | — | On `/findings/9f176dea…` the `title` is the **raw 32-character hex id at 46px inside a 360px column**. Measured `348x156px` — **it wraps to four lines**, and the header block is **253px tall** against 104px on Fleet | **The worst-looking single thing measured.** A display step is for a name; an opaque identifier is not one. It also spends the page's only focal point on a value nobody reads | **S** | `features/findings/finding-page.tsx`, `features/workflows/workflow-page.tsx`, `features/pullrequests/pull-request-page.tsx` |
| `supabase-06`: schema selector, search, two filters and one green `New function`, all in one bar under the title | Pages compose `PageHeaderAside` beside the summary (`pages/project/[ref]/database/indexes.tsx:22-57`), with scope and search in the section beneath | `ControlBar` exists (`layouts/control-bar.tsx`) and five screens use it — **but on `/` and `/detectors` it holds no controls at all.** Measured: `main input` 0, `main select` 0, `main button` 0. It is a 40px static strip reading `SCOPE` plus a sentence | The component is right and is being fed nothing. On the vendor page the real controls sit **inside a card body** at `y=469-585`, beneath a table heading, where Studio would put them in the bar above the table | **M** | `layouts/control-bar.tsx` and its consumers in `features/fleet/`, `features/detectors/`, `features/vendors/` |
| `supabase-07`, `supabase-17`: content inset from the chassis and capped, with the cap changing per page | `ui-patterns/PageContainer/index.tsx:9-21` `mx-auto w-full @container px-6 xl:px-10` with a ladder — `small 768 / default 1200 / large 1600 / full none`; data pages pass `size="large"`. The older `Scaffold.tsx:4-6` uses `px-4 @lg:px-6 @xl:px-10` at `max-w-[1200px]` | `p-frame` 40px on four sides; **`max-width: none` on `main` and every wrapper**. `main` is 1177px at 1440 and unbounded above | **No max-width ladder anywhere.** Meanwhile `max-w-prose` caps paragraphs at 560px, which is the composition finding NOTES already recorded and which is still open | **M** | `layouts/app-frame.tsx`, `DESIGN.md` *Space* |
| `supabase-01`: `Go to Project Overview  G then H` under the nav | `Sidebar.tsx:211-222` wraps shortcut-bearing items in `<Shortcut side="right">`; `Sidebar.tsx:181` sets `shortcutPopoverDelay = sidebarState === 'collapsed' ? 0 : 1000`; pills from `ShortcutTooltip.tsx:62-70` | Palette is `Ctrl/Cmd-K`, undiscoverable | See surface 7 | **S** | `layouts/command-palette.tsx` |

**The spacing rhythm is sound and is stated here so it is not re-litigated:** frame 40 : between-panel
32 : intra-panel 16 : row 8 : field 4, frame larger than the gap inside it, ratio 5.0 against the
in-component unit. `DESIGN.md` *Space* carries the arithmetic. Nothing in the screenshots argues
against it.

---

## Surface 4 — data tables

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-06`, `supabase-07`: `NAME` `VERSION` `SCHEMA` on a strip a shade above the body | `packages/ui/src/components/shadcn/ui/table.tsx:72` — `<th>` is `h-10 px-4 text-left align-middle heading-meta whitespace-nowrap text-foreground-lighter`; `heading-meta` resolves to `text-xs font-mono uppercase tracking-wider font-medium`. `thead` carries `[&>tr]:bg-200` (`:31`) | 40px, 12px, uppercase, ls 0.3px, `text-ink-muted` — but **`background: transparent`**, and **`font-weight: 700`, which is the UA default for `th` that no class sets** | Two small defects: the header does not read as a strip, and the furniture register disagrees with itself — 700 in a table head against 500 in a sidebar group label | **S** | `components/data-table.tsx:49-59`, `DESIGN.md` *Type* |
| `supabase-03`: `id uuid`, `metadata jsonb`, `embedding vector` — the type printed beside the column name | `grid.css:305-324` — name `text-foreground text-xs`, type suffix `text-xs font-normal text-foreground-light` | Absent; headings are prose labels only | We have a real equivalent: the rung a column's values rest on, and whether a count is bounded. **The highest-value row in this table**, because it is where Studio's anatomy has a slot our data already fills | **M** | `components/data-table.tsx`, `components/provenance.tsx` |
| `supabase-06`, `supabase-07`: a `⋮` at each row's end | Per-page dropdowns over the list table (`Indexes.tsx:221-231` for the shape) | **Absent.** `DropdownMenu` is vendored at `vendor/supabase/ui/dropdown-menu.tsx` and used **nowhere** in `features/` | No per-row affordance of any kind | **S** | `components/data-table.tsx` |
| `supabase-03`: row checkboxes and a selected row | `table.tsx:56` `<tr>` = `border-b group data-[state=selected]:bg-muted hover:bg-surface-200` | Hover works — verified with a real pointer, `rgba(0,0,0,0)` → `oklch(0.95 0.00275 159 / 3.29%)`, `transition 0.15s`. **Selected is declared and unreachable**: `[data-state=selected]` count **0** on every route, *including the binding page with its drawer open*. And `--color-muted` and `--background-color-surface-200` resolve to the **identical** value, so it would be invisible if it fired | A row that opens a drawer does not mark itself, so a reader loses their place on return. **Studio has the same token collapse — fixing this means diverging from the reference deliberately** | **S** | `components/data-table.tsx`, `features/bindings/binding-surface-page.tsx`, `DESIGN.md` surface ramp |
| `supabase-03` foot: pager, page size, `4 records`, Data/Definition toggle, flush to the bottom | `GridFooter.tsx:9` `flex min-h-10 h-10 … px-2 w-full border-t gap-x-8`; contents `Footer.tsx:29-45`; pager anatomy `Pagination.tsx:248-295`, all text `text-xs text-foreground-light`; the record count at `:317-319` renders `(estimated)` with a `HelpCircle` when it is | `FooterBar` exists and is right in kind (`layouts/footer-bar.tsx`) — measured `1063x45px`, `border-top`, range then Previous/Next. **But it is absent on the Fleet index and absent on `/detectors`**, the two longest pages at 3380px and 3014px, which put counts in `<h2>` text instead | The two screens that most need a record count and a pager have neither | **M** | `layouts/footer-bar.tsx` consumers in `features/fleet/`, `features/detectors/` |
| `supabase-23` logs: extreme density | The house grid standard is `rowHeight={44}` / `headerRowHeight={36}` (Users, Query Performance, Linter, Queues, Cron). The list table has no height class — `p-4` on the `<td>` derives it | 40px header / 36-37px body, derived from `DESIGN.md`'s arithmetic and held by `tests/test_console_design_tokens.py` | **Ours is denser than Studio's own standard and its derivation is tested. No change.** Rows measured at 49/57/81px where cells wrap are a column-width problem, not a density one | — | `components/data-table.tsx` |

---

## Surface 5 — detail pages against the drawer and panel patterns

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-08`: the list dims and a right panel shows `CREATE UNIQUE INDEX …` with `Cancel` at its foot. `supabase-18`: a selected query row with the pattern as code above a nine-row metadata definition list | The contextual panel is a `ResizablePanel` at `ProjectLayout/index.tsx:279-287` (`minSize={256}`, hard-pinned at 256 for Database since `resizableSidebar` defaults false at `:131`); sheet-style details use the vendored `sheet` | **The pattern exists, on exactly one surface.** `/bindings/.../operations/:operationId` opens a `Sheet`: `[role=dialog]` **720x900**, right-anchored, `z-50`, over `div.fixed.inset-0.bg-alternative/90.backdrop-blur-xs` with `backdrop-filter: blur(4px)`. **Selection is in the URL** (`?binding=…`), so the address is shareable | The mechanism is built and proven, and used once. Every other detail navigates away | **M** per additional surface | `features/bindings/binding-drawer.tsx` is the model; `vendor/supabase/ui/sheet.tsx` |
| `superlog-01`: a ~360px fact rail beside the content, nine facts as a definition list | — (Superlog) | **Built.** `finding-page.tsx:34` `lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]` — measured 360 left / 720 right, `gap: 32px`. `FactList` renders a ruled `<dl>` with a `w-2/5` furniture-register `<dt>`. Workflow and PR use the same split | **NOTES entry 1's central finding is closed.** No gap | — | `components/fact-list.tsx` |
| `superlog-01`: the breadcrumb and title sit above *both* columns | Studio's page header spans the content column | **`PageHeader` renders inside the left 360px column** on all three detail routes | The title is constrained to 360px, which is what makes the hex id wrap to four lines. The header should span both columns | **S** | `features/findings/finding-page.tsx`, `features/workflows/workflow-page.tsx`, `features/pullrequests/pull-request-page.tsx` |
| `superlog-01`: `Activity` / `Findings` tabs. `supabase-14`: tabs carrying their own counts (`Errors 0 errors`, `Warnings 8 warnings`) | Studio composes the vendored `tabs` | **`Tabs` is vendored at `vendor/supabase/ui/tabs.tsx` and used nowhere.** The workflow page stacks a 1701px `<ol>` of nine nodes | Nothing anywhere is behind a disclosure; every screen is one scroll. `/` is 3380px, `/detectors` 3014px | **M** | `features/workflows/workflow-page.tsx`, `features/detectors/detectors-page.tsx` |
| `supabase-16`, `supabase-20`: a headline value directly above the evidence table that justifies it | — | **Built.** `MetricPanel` — furniture label, `--text-figure` value with a type-required `unit`, caption, then the evidence as children | No gap; `unit` being required is stricter than Studio | — | `components/metric-panel.tsx` |

**Refused, and recorded because `superlog-01` makes it tempting.** The composer pinned to the foot of
Superlog's incident detail implies a write path. Every route is a GET held by
`test_no_route_reaches_past_the_read_surface`. That is a product decision with an authorization story
attached, not a component, and it does not enter through a text box.

---

## Surface 6 — empty states and skeletons

| Screenshot | Studio | Console today | Gap | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-04`: *"No shared queries — share queries with your team by right-clicking on the query."* `supabase-12`: three routes in, each with its own action | `ui-patterns/EmptyStatePresentational/index.tsx:74-79` — an `<aside>`, `border border-dashed bg-surface-100 rounded-lg px-4 py-10 flex flex-col items-center gap-y-3`; Lucide icon `size={24} strokeWidth={1.5} text-foreground-muted` (`:61`); a bare `<h3>` (`:67`, picking up `text-base font-semibold` from the base layer); description `text-foreground-light text-sm max-w-[640px]`; the action slot is bare `{children}` at `:104` | **Better than the reference on content, weaker on form.** Measured at `/vendors/…?path=zzz-nothing-matches`: *"No open finding for seed-console-stripe in any repository the index has seen matches this filter."* then a second sentence separating what the filter excluded from what the codebase is missing, **and a `Clear` control**. Container `561x146`, `max-w-prose`, padding 16, **`border-radius: 4px`**, transparent, no icon | The sentence already says what would fill the space and how — NOTES entry 5 called this absent and it is not. Two real defects: **the 4px radius disagrees with every card's 8px**, and with no icon or centring an empty state reads as a paragraph rather than as a state | **S** | `components/states.tsx:25-52` |
| `supabase-21`, `supabase-22`: a dashed region, an icon, *"No data to show / It may take up to 24 hours for data to refresh"* — **with the value still printed above it** (`0`, `0ms`) | The same empty-state pattern | `MetricPanel` renders `<Absent>` rather than `0`, deliberately | **Agreement rather than a gap, and ours is the sharper version.** `supabase-22` prints `0` where the truth is "not measured", which is exactly the absence-is-not-zero failure. Our marker is correct and must not be replaced by a zero to match the reference | — | `components/status.tsx:65` |
| `supabase-01`: a grey bar the width `LAST MIGRATION`'s value will be | `ui-patterns/ShimmeringLoader/index.tsx:16` `shimmering-loader rounded-sm py-3` — a **gradient sweep**, not `animate-pulse`: `animation: shimmer 2s infinite linear` over a 1000px background, staggered by `delayIndex * 150ms`. Used for the top-bar switchers' own widths (`OrganizationDropdown.tsx:56`, `BranchDropdown.tsx:89`) and for a page title (`database/tables/[id].tsx:35`) | **Built.** `components/skeleton.tsx` — `h-4 rounded-control bg-surface-subtle` with a **required** `width`, used in five features. **Deliberately does not animate**, and the docstring records that merely naming the pulse utility once compiled the keyframe into the bundle | NOTES entry 3's "no skeleton anywhere" is closed. The remaining gap is coverage: it is always one fact's value, never a table, a card or a page title | **S** | `components/skeleton.tsx` |
| `supabase-10`, `supabase-11`: the headers stay and the empty state sits in the table body | The empty-state pattern inside a `<td colSpan>` | Ours replaces the whole table with a panel | Column identity is lost while empty, so a reader cannot see what would have been there | **S** | `components/data-table.tsx`, `components/states.tsx` |

---

## Surface 7 — what the screenshots show, our data can honestly fill, and the console lacks entirely

Each row states the honesty constraint that bounds it. Two candidates are **refused** in place, so a
later reader does not propose them again.

| Screenshot | Studio's mechanism | Console today | Can our data fill it honestly? | Scope | Owner |
|---|---|---|---|---|---|
| `supabase-01`: `Go to Project Overview  G then H` on the surface it applies to; `supabase-04`: `Hit CTRL+SHIFT+K to generate query`; `supabase-05`: `Go to Database  G then D` | `Sidebar.tsx:211-222` with `ShortcutTooltip.tsx:62-70` | `Ctrl/Cmd-K`, with **no on-screen trigger and no hint anywhere** | **Yes, unconditionally.** A keybind is a fact about the console, not a claim about the graph. The palette already reads `ROUTES`, so a per-destination hint has a source | **S** | `layouts/command-palette.tsx`, `layouts/app-frame.tsx` |
| `supabase-23`: a faceted filter sidebar where **every facet carries its own count** (`Postgres 95`, `Auth 54`, `Error 5xx 32`) | Studio's logs explorer | `FacetChips` (`components/filters.tsx:53`) carries counts, but only inside a card on the vendor page | **Yes, with one condition.** A facet count must say what it is counted over, and a facet at zero must render as zero rather than vanish — `supabase-23` gets this right, showing `Edge Function 0`. Absence and zero stay distinct | **M** | `components/filters.tsx`, `layouts/control-bar.tsx` |
| `supabase-01`, `supabase-16`: `Last 60 minutes`, with every count on the strip scoped by it | Studio's report time-range control | Nothing is time-scoped, and nothing says what window it covers | **Partly, and the boundary is the point.** `observed_error_window` is stored per window and can carry a range control honestly. **Nothing else can** — a count of open findings is a graph state, not a series, and a range over it would claim a window the number does not have. Scope it to observed telemetry, and say so on the control | **M** | `features/telemetry/`, `api/queries.ts` |
| `supabase-24`: status chips from a closed vocabulary (`INSTALLED`, `OFFICIAL`, `BETA`, `COMMUNITY`, `PARTNER`) | `badge.tsx:7-12` | `RungBadge` only | **Yes.** `CLAUDE.md` explicitly permits a badge that is a recorded value from a closed vocabulary and legible without its colour. Run outcome, error state and absence qualify. **An open vocabulary does not** | **S** | `components/provenance.tsx`, `components/status.tsx` |
| `supabase-05`: a node card whose header is the entity and whose rows are its fields, with the relationship drawn | Studio's schema visualizer | `binding-drawer.tsx` already does this at cardinality one, in composed cards with ruled edges, each edge stating its rung | **Already built, at the only cardinality where it is honest.** Task 11's refusal of a fleet-wide bipartite diagram rests on cardinality — thousands of call sites against hundreds of operations — and `supabase-05` draws three tables and fifteen columns | — | `features/bindings/binding-drawer.tsx` |
| `supabase-02`: a dimmed world map with one bright dot — a region whose job is orientation, not measurement | Studio's project overview | Nothing | **REFUSED as drawn.** We have no geography and no infrastructure. The transferable property is that the most spatial fact gets its own region, and `binding-drawer.tsx` already spends it. A locator with nothing to locate is decoration | — | — |
| `superlog-02`: `Root cause confidence 9/10`, `Impact confidence 9/10`. `supabase-02`: `STATUS Healthy`. `supabase-14`: coloured tab dots | `Sidebar.tsx:227-247` `ActiveDot`, colour-only and unlabelled | Refused four times on the record | **REFUSED, and this is the constraint the reference set most pressures.** The honest field already exists: the rung says which class of evidence a claim rests on, it is attributable, and it lets a false positive be traced to the binder that produced it. Where their screen puts a number, ours puts the rung and the evidence behind it | — | `CLAUDE.md`, `.claude/rules/console-surface.md` |

---

## The type ramp, which cuts across every surface and is the report's second-largest finding

It belongs to no single surface, so it is stated once.

The measured range is **46 / 13 = 3.54**, clearing the 3.4 bar the flatness report set. But the
*distribution* is bimodal and the middle of the ramp is unused. Distinct rendered sizes across all
seven routes: **46, 28, 18, 15, 13, 12**.

- **18px appears exactly once in the whole application** — `/detectors`, the `By detector` heading.
- **Almost every `<h2>` and `<h3>` on every page is 12px uppercase furniture**: Fleet's
  `Open findings by vendor`, `Runs` and `Repair record`; the repository's `Index coverage` and
  `Observed telemetry`; the finding's `Known changes` and `Provenance`; the pull request's
  `What the compiler said`.
- So a section heading is the same size as a table column header, and a page is one 46px title above
  an undifferentiated field of 13px and 12px. Studio's equivalents are populated: `heading-title` at
  24px, `ScaffoldSectionTitle` at `text-xl`, the page description at `text-base`, `FormHeader.tsx:25`
  at `text-xl`.

`DESIGN.md` declares `--text-section` at 1.125rem/600 and `--text-emphasis` at 0.9375rem/600. Both
exist and neither is reaching the panel headings. **The fix is assignment, not new tokens** —
`MetricPanel`'s `label` is rendered `furniture text-meta text-ink-muted` at
`components/metric-panel.tsx:70`, which is one line and roughly forty consumers. **Scope: M.**
Owner: `components/metric-panel.tsx`, `DESIGN.md` *Type*.

One caution against over-correcting. The panel label is deliberately in the scanned register, and
`test_exactly_one_component_spends_the_display_step` holds the 46px step to `PageHeader` alone. A
second display-size element is two focal points, which is none. What is wanted is a **section** step
between the two, not a second display step.

---

## Method, and what a reader should distrust

- Studio's citations were read from a sparse clone at `6ac0316`, since deleted. The first checkout
  silently landed on the default-branch head because GitHub will not serve an abbreviated SHA over
  the fetch protocol; every line number here was re-verified against the pin after that was caught.
  Two packages — `packages/config` and `packages/ui-patterns` — had to be added to the sparse set
  before `heading-meta`, the colour system or the current scaffold family could be resolved at all.
- The console's numbers came from Chrome at 1440x900 through `getComputedStyle` and
  `getBoundingClientRect`, with a real pointer moved onto a row so `:hover` genuinely matched. The
  viewport override was cleared before the session ended, per `.claude/rules/console-dev-loop.md`.
- Fifteen console screenshots sit in the scratchpad, outside the repository, and are not durable.
  Nothing in this report depends on them.
- **Everything above describes appearance and composition. None of it was implemented.**

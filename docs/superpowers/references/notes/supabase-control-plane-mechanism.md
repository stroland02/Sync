# Supabase Studio, read as source — the mechanism behind a control plane

**M7-W159, 2026-08-06.** `github.com/supabase/supabase` at `6ac0316`, cloned shallow into ignored
scratch outside this repository (`--depth 1 --filter=blob:none --sparse`, sparse set to
`apps/studio`, `packages/ui`, `packages/ui-patterns`, `apps/design-system`, `.claude`). Every path
below is relative to that clone's root. Nothing here was measured in a browser and nothing was read
from their documentation site; the `.mdx` files cited under `apps/design-system/content/` are files
in the repository, and they are the authors' own written reasoning rather than marketing.

**Why this read is permitted, and what it is not.** `.claude/rules/interface-originality.md` was
amended on 2026-08-06 to separate the conventions of the form — a rail, a page header, a control
bar, a drawer — from identity, which is not learnable from anyone. This note takes mechanism and
stated reasoning. **No component was copied and no class string appears below.** Where their
mechanism rests on something we do not have, the section says so and stops rather than designing
around it.

The standard is section 20 of `docs/superpowers/plans/2026-08-05-sync-console-architecture.md`,
which read `getsentry/sentry` and `grafana/grafana` the same way. That section also names the
failure mode this one avoids: **a note describing what a component looks like is worthless.** What
transfers is how it is composed, what it requires of a caller, and what its authors wrote down.

The slot mapping is not re-derived here. `docs/superpowers/references/direction/NOTES.md` already
records what the owner asked for and what we hold for each slot; each section below closes by
naming what goes in that slot and points at that file rather than repeating it.

---

## Before the six items: they wrote their conventions down, and two of them confirm ours

`apps/studio/CLAUDE.md` and `.claude/skills/studio-ui-patterns/SKILL.md` are the authors' stated
rules for their own console. Two are worth carrying regardless of anything below.

**A fetch state is four states, resolved by early return, never by a nested ternary.**
`apps/studio/CLAUDE.md:48-65` gives the shape as a rule with a worked example: loading, error,
success-and-empty, success-with-data — "never a nested ternary", and the same four again as a flat
chain of mutually exclusive guards for the inline case. That is our *four kinds of nothing*
(`web/src/components/states.tsx`) arriving from a mature codebase's style guide rather than from our
own argument, which is the strongest form of confirmation available. **We already hold it. Do not
treat this as new.**

**A tab is a URL.** `.claude/skills/studio-ui-patterns/SKILL.md:98-99`: activating a navigation item
"must trigger a URL change — no local-only tab state". Our console holds this by accident of having
no tabs; it is worth holding on purpose the first time a screen grows one.

One more, which is a caution rather than a rule: `apps/studio/CLAUDE.md:55` and `:62` show the empty
branch as a bare component with no argument attached. Their own design-system doc is far stricter
about it (§3 below), and the gap between a style guide's example and the doc that governs it is
where a console loses its sentences.

---

## 1. The shell — an icon rail, a contextual sidebar, and how a route declares which one it is in

### What composes what

`apps/studio/components/layouts/DefaultLayout.tsx:32-41` carries the authors' own description of the
arrangement, and it is a three-layer nest rather than a shell with slots:

- `DefaultLayout` (`:42`) is "rendered as the first child on all page files within a project" and
  owns the banner, the mobile bar, the header and the **first-level** navigation.
- Its docstring at `:35` states the requirement plainly: **"A second layout as the child to this is
  required, and the layout depends on which section of the dashboard the page is on."**
- That second layout — `DatabaseLayout`, `AuthLayout`, and so on — is what supplies the contextual
  sidebar.

The rail itself is `apps/studio/components/interfaces/Sidebar.tsx:60`, rendered by `DefaultLayout` at
`:113` and **conditioned on the route**: it is skipped entirely for account pages
(`router.pathname.startsWith('/account')`). The contextual sidebar is not rendered by the shell at
all — the page's own layout passes it down as a node.

### How a route declares its sidebar

`apps/studio/components/layouts/DatabaseLayout/DatabaseLayout.tsx:22-38` is the whole mechanism, and
it is composition rather than registration: the layout builds a menu, then hands it to
`ProjectLayout` as a `productMenu` prop alongside a `product` string used as the sidebar's own
heading. `ProjectLayout` declares those props at `:105-118` and renders the sidebar only when the
prop is present (`:279`).

**There is no route table mapping paths to sidebars.** A page nests inside the layout it belongs to,
and nesting *is* the declaration. That is worth stating because our console does the opposite —
`web/src/lib/routes.ts` is a registry every route passes through, which is the right shape for us and
a different shape from theirs.

### Where the active state lives

Positional, off the path, in two places at two depths:

- Rail: `Sidebar.tsx:255` takes `router.pathname.split('/')[3]` as the active key, with the project
  home active when that segment is `undefined` (`:288`).
- Contextual sidebar: `DatabaseLayout.tsx:24` takes `split('/')[4]` — one segment deeper — and
  `ProductMenu` (`apps/studio/components/ui/ProductMenu/index.tsx:33-35`) compares it against either
  the item's `key` or its `pages` array, so an item can claim several routes.

**The `pages` array is the transferable part.** A menu item that owns more than one route says so in
data rather than through a regex over the path, which is how an active state quietly stops matching
after a route is added.

### Collapse, and what reflows

Three states, not two. `Sidebar.tsx:47-49` declares `expandable | open | closed` with `expandable`
the default, persisted to local storage (`:63-66`), where `expandable` means expand-on-hover
(`:82-88`). The rail is the shadcn sidebar primitive in its icon-collapse mode, so collapsed is a
narrow icon column rather than nothing.

The content beside it is a resizable panel group with an autosaved id
(`DefaultLayout.tsx:115-138`), min 50% and max 70%, and a second sidebar — their AI assistant — takes
the remainder. The mount is deferred behind an `isMounted` flag (`:88-90`) with the reason written
down at `:86-87`: resizable panels render at 50% first and then jump, so the whole layout renders
nothing until mounted rather than shifting.

**Two things we would inherit for free and should not.** The resizable panel group is machinery for
a second sidebar we do not have, and the deferred mount is a fix for a problem that machinery
causes. A fixed-width rail needs neither.

### What we would put in it

The levels are already specified: `GRAPH_LEVELS` in `web/src/lib/routes.ts`, from the design
document's authoritative block. The rail is those levels; the contextual sidebar is what sits under
the level you are inside — for `Codebase`, the repository's own screens; for `API Services`, the
vendor's. `direction/NOTES.md` §5 records the owner asking for exactly this two-tier shape.

**One decline, and it is prominent.** `Sidebar.tsx:227-246` declares `ActiveDot`, rendered on a rail item at `:336` — a coloured dot on a
rail icon, red for errors and amber for warnings, driven by their lint results. It is a status dot on
a navigation item, and `CLAUDE.md` refuses one. Their version clears the bar ours cannot: a lint
result is a stored, closed lifecycle with a definite pass or fail. Our equivalent would be "is
something wrong under this level", which collapses *we could not check* onto *we checked and it
passed* — the exact failure the refusal exists for. **Refused, and the reason is our data, not their
screen.**

---

## 2. Layout primitives — a page header, a control bar, a footer bar

### Two generations live side by side, and the newer one is the interesting one

The older primitive is `apps/studio/components/layouts/PageLayout/PageLayout.tsx:20-58`: one
component taking `title`, `subtitle`, `icon`, `breadcrumbs`, `primaryActions`, `secondaryActions`,
`navigationItems`, `size` and `isCompact`. Every one is optional. Its docstring at `:36-57` is
honest about the cost — two of the props are documented as `TBD`.

The newer one is a slot family: `packages/ui-patterns/src/PageHeader/index.tsx` exports a root plus
`PageHeaderBreadcrumb` (`:79`), `PageHeaderIcon` (`:105`), `PageHeaderSummary` (`:127`),
`PageHeaderTitle` (`:150`), `PageHeaderDescription` (`:168`) and `PageHeaderMeta` (`:192`). The root
puts its `size` in context (`:34-38`) so a child reads it without being passed it.

**The mechanism worth taking is the direction of that migration**, not either API. A header with nine
optional props cannot say which combinations are meaningful, and two of its props ended up
documented as unknown. A header made of named slots can: the page composes only what it has, and a
slot that does not appear is not a prop set to undefined.

### Width is chosen by content, and it is a fixed set

`packages/ui-patterns/src/PageContainer/index.tsx:9-20` declares four widths — 768, 1200, 1600 and
uncapped — and `apps/design-system/content/docs/ui-patterns/layout.mdx:23-29` states the rule for
choosing: **"Pick width by content, not page type"**, with settings at the narrowest, lists and
detail pages in the middle, and dense horizontal content uncapped. The same file notes a route may
mix widths across its own child pages.

This is the direct answer to the measurement in
`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md`: our console has no width
system at all, one 24px gutter and `max-w-prose` on every paragraph, so a 1875px viewport renders a
491px column of prose beside 1330px of nothing. **Their fix is not a wider cap. It is that the cap is
a property of the content and there are four of them.**

### The control bar, and where an action goes

`layout.mdx:38-47` is a table with five rows, and it answers a question we have never asked: where
does the primary action live? Their answer depends on what else is on the page — on the breadcrumb
row for a parent with sub-navigation, in the header aside for a child page with no filter row, and
**on the right of the filter row whenever one exists**, explicitly not in the header. The stated
reason is at `:38`: put actions where the user is already looking.

`.claude/skills/studio-ui-patterns/SKILL.md:24-25` repeats it as a rule for their own agents, which
is how much they care about it.

### The footer bar, and the honest count

`apps/studio/components/ui/GridFooter.tsx:4-16` is a 10px-tall strip pinned under a data view with a
label for assistive technology; `apps/studio/components/grid/components/footer/Footer.tsx:29-42`
fills it with pagination on the left and a view toggle pushed right, and that toggle's state is a URL
query param via `nuqs` (`:19`).

**The count in that footer is the finding.** `Pagination.tsx:103-107` reads a count that may be an
estimate; `:105` formats an estimated count differently from an exact one (thousands abbreviated
rather than grouped, `pagination/Pagination.utils.ts:1-13`); `:318-319` prints the word
`(estimated)` beside it when it is one; and `:335-348` makes retrieving the exact count a deliberate
action behind a confirmation whose text states the cost — over their threshold, an exact count may
hurt the user's database.

That is our `total_findings_bound_reached` and `describeBoundedTotal` — an approximate figure that
says it is approximate — arrived at independently by a team with a real database under them, plus a
mechanism we do not have: **the exact answer is available on request, and the request states its
price.** Our bounded scan has no such escape hatch, and a reader who genuinely needs the true number
today has no way to ask for it.

### What we would put in it

A page header per `direction/NOTES.md` §5 — a display title and one sentence saying what the screen
is for. A control bar on the screens that have filters, which after M4.5-W141 is the vendor and
binding-surface screens. A footer bar is where our `PageControls` belongs: it currently sits inside
whichever card a table happens to be in, which is why pagination has no fixed home.

---

## 3. The empty state — the component, and the four scenarios it is not for

### The component

`packages/ui-patterns/src/EmptyStatePresentational/index.tsx:6-15` — `title` is the only required
prop. `description` is optional, `children` is where a caller puts an action, and the icon defaults
if absent (`:59-60`).

The API is unremarkable. **The docstring above it is not.** `:17-48` states a precondition rather
than a usage: the component is "specifically designed for initial state scenarios where users are
learning about a feature for the first time. It emphasizes value propositions and provides clear
actions users can take." A component that names the situation it is for is a component that can be
used wrongly on purpose rather than by accident.

### The four scenarios, which is the real mechanism

`apps/design-system/content/docs/ui-patterns/empty-states.mdx` splits absence four ways, and the
splits are argued:

1. **Initial state, presentational** (`:21-27`) — nothing exists yet and the reader is meeting the
   feature. Emphasis on the action. Their copy rule at `:27` is that this state uses active language
   rather than a negative statement of absence.
2. **Initial state, informational** (`:29-35`) — same fact, different presentation, chosen when the
   list is data-heavy and education would be noise: render the empty list *in the same shape as the
   populated list*.
3. **Zero results from a search or filter** (`:37-50`) — deliberately looks like the data state. The
   stated reason at `:39-40` is that a matching layout makes the transition between the two
   seamless. A table with no rows renders one row rather than a different component (`:43`).
4. **Missing route** (`:60`, and `SKILL.md:89`) — a centred admonition, not an empty state at all.

`:36` adds the one nobody writes down: an empty state usually arrives *after* a loading state, so the
two have to be considered together or the page jumps.

**This is the sharpest thing in the whole read for us.** Our four kinds of nothing distinguish *why
the screen is empty* — no data, not found, request failed, still asking. Theirs distinguishes
something orthogonal that we have exactly one shape for: **whether the reader has ever seen data
here.** A binding surface nobody has indexed and a binding surface a filter has emptied are the same
component on our screens today, separated only by a sentence. M4.5-W141 added a filtered-to-empty
sentence on the binding surface, which is the right distinction reached one screen at a time; this
says it is a property of the component, not of the page.

### What we would put in it

Every absence the console already names — and there are many, because this is the console's own
argument. What changes is that the empty component would take *which kind of absence* as an
argument rather than each caller composing a sentence. The sentences themselves are ours and are
protected (`docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, *Establish 2*); nothing
here proposes rewriting one.

**One decline.** `Reports/renderers/ApiRenderers.tsx:178` returns nothing at all when its evidence
table has no rows — the block vanishes with no sentence. That is the failure our console exists to
avoid, in the same repository as the doctrine above. Worth recording precisely because it shows a
written rule does not reach every screen on its own.

---

## 4. The drawer — two different things, and only one of them is in the URL

### The modal sheet

`packages/ui/src/components/shadcn/ui/sheet.tsx` is Radix's dialog with a side variant: a portal
(`:42`), an overlay that can be turned off per instance (`:169`, `hasOverlay`), a content element
with side and size variants (`:29-36`, `:150-157`), and a close control that can be suppressed
(`:169`, `showClose`). Focus trapping, escape dismissal and inert background come from Radix and are
not re-implemented.

Open state is the caller's, and in the case I read
(`apps/studio/components/interfaces/Database/Indexes/CreateIndexSidePanel.tsx:188`) it is a plain
prop. **The URL does not carry it.**

`apps/design-system/content/docs/ui-patterns/modality.mdx:19` states when to reach for which:
dialogs for short focused tasks, sheets for longer forms and detailed views. `SKILL.md:118` adds the
precondition that matters — a sheet is for when *switching pages would be disruptive and the reader
needs to keep their context*.

### The inline detail panel, which is the one in the URL

`apps/studio/components/interfaces/Auth/Users/UserPanel.tsx:30-33` is a different pattern with the
same visual job and it is the one worth taking. The selected row's id is URL state through `nuqs`,
with two options set explicitly:

- `history: 'push'` — opening the panel is a history entry, so **Back closes it**.
- `clearOnDefault: true` — the parameter disappears when the selection is cleared, so a screen with
  nothing selected has one canonical URL rather than one with an empty parameter on it.

It is not modal. It is a resizable panel beside the list (`:62`), so the list stays readable and the
reader keeps their scroll position.

That second option is the same discipline section 21.3 of the console architecture plan found in
Sentry — the URL holds the difference from default, not the whole state — reached by a different
codebase with a different router. Two independent confirmations make it a rule rather than a habit.

### Dismissal when the form is dirty

`modality.mdx:80-100` gives a five-step decision flow and an implementation checklist: keep every
dismissal affordance enabled, intercept them all at one place, route the footer's cancel through the
*same* guard, and — the line that matters — **do not try to block route changes or arbitrary
unmounts**; a route-driven dismissal needs a navigation guard, not a bigger dialog guard.

`apps/studio/hooks/ui/useConfirmOnClose.tsx:16-58` is that guard in twenty lines: a predicate the
caller supplies, an intercepted open-change handler (`:31-38`), and a props object for the
confirmation dialog (`:48-56`). The predicate is held in a ref (`:19-20`) so the returned callbacks
are stable.

### What we would put in it

`direction/NOTES.md` §5 names the case: a detail opening beside a list rather than navigating away.
Ours would be a finding opened from the binding surface or a run opened from the fleet table, with
the id in the URL under the two options above so a shared link opens the same panel.

**Where this stops.** The dirty-dismissal machinery is for forms, and every route we serve is a GET
held by a behavioural test. There is nothing to be dirty. `direction/NOTES.md` §1 already rules that
a write path is a product decision with an authorization story, not a component — this note does not
reopen it, and the confirm-on-close hook is recorded as read and not adopted.

---

## 5. The settings card — one card per setting, and the cancel boundary is the card

### The mechanism

`SKILL.md:44-58` states the composition: react-hook-form plus zod, one `Card` per settings group with
a section per field and the actions in the card's footer, and — the operative line — **destructure
`isDirty` from the form state to show Cancel and disable Save**.

`apps/studio/components/interfaces/Auth/BasicAuthSettingsForm.tsx` is the reference the older
primitive's own deprecation notice points at
(`apps/studio/components/ui/Forms/FormPanel.tsx:14`). Four lines carry the whole pattern:

- `:84` takes `isDirty` off the form state.
- `:90-98` calls the form's reset with the server's values inside an effect — which does double duty:
  it populates the form *and* rebaselines what "dirty" means, so a value that arrives from the server
  does not read as an edit.
- `:337-341` renders Cancel **only when dirty**, and its action is a reset to that baseline.
- `:345` disables Save unless dirty.

The older `FormActions` (`apps/studio/components/ui/Forms/FormActions.tsx:22`) shows the same rule
written as an expression, and its treatment of an undefined `hasChanges` is a small piece of care
worth naming: a caller that does not know whether anything changed gets an enabled button rather than
a disabled one.

**The cancel boundary is the card.** Not the page, not a global save bar. A settings screen is
several independent cards, each with its own dirty state and its own pair of buttons, so saving one
setting neither commits nor discards another.

### What we would put in it

**Nothing yet, and this is the section where the brief's instruction applies.** The pattern requires
a write path; we have none. `direction/NOTES.md` §5 already records that the settings pattern "needs
one and therefore waits". Recorded as read, mapped, and stopped — the mechanism is here so that
whoever builds M4's hosted half does not re-derive it.

The one part that transfers with no write path is the rebaseline: a screen whose displayed value
arrives asynchronously has to distinguish *the server said this* from *the reader typed this*, and
that is a real problem for any future filter form.

---

## 6. The metric panel — value above evidence, and one state machine for all five states

### How the evidence is fetched and keyed, which was the question

`apps/studio/components/interfaces/Reports/ReportWidget.tsx:11-33` takes a `renderer` and an `append`
— both render props over the same props object, which itself extends the widget's props, so the
appended block sees everything the chart saw. `appendProps` (`:22`) lets a caller substitute the data
the appended block reads.

`apps/studio/components/interfaces/Reports/SharedAPIReport/SharedAPIReport.tsx:30-77` shows the
arrangement three times over: one widget per metric, the chart as `renderer`, the same evidence table
component as `append`, and `appendProps` pointing at a *different slice of the already-fetched
payload* each time — top routes under the request count, top error routes under the error count, top
slow routes under the response time.

**So the answer to "how are the expandable rows fetched and keyed" is: they are not fetched
separately and they are not keyed separately.** One query per screen returns both the series and its
evidence; the widget is a layout, not a data boundary. That is the cheapest possible version of
"value above its own evidence" and it is the right one for us, because our aggregate routes already
return the breakdown beside the total — `/api/detectors` returns `by_rung` per detector, `/api/corpus`
returns three tallies.

The expansion itself is local: `Reports/renderers/ApiRenderers.tsx:173` holds a boolean, and rows
past the third are hidden rather than dropped.

### The state machine underneath it

`packages/ui-patterns/src/Chart/index.tsx` is the newer pattern and carries the mechanism I would
most want. `ChartContent` (`:311-355`) resolves **five** states in a fixed precedence — disabled,
loading, errored, empty, then data — each with its own slot prop, and reads the first three from the
`Chart` root through context (`:44-56`, `:335`) rather than from its own props.

Two properties follow, and both are ones our console argues for and does not enforce. The precedence
is declared once, so two charts cannot disagree about whether loading outranks empty. And `isEmpty`
is a *caller's assertion* (`:312`), not an inference from an array's length — so "the query returned
nothing" and "there was nothing to query" stay separable at the call site.

`ChartMetric` (`:225-233`) is the value-above-evidence element: a required label, a value typed to
admit null and undefined, and an optional delta. `:237` and `:297` render a skeleton in place of the
value while the root says it is loading — the label stays, the value is replaced, so the panel does
not change size.

### What we would put in it

`direction/NOTES.md` §3 maps the tiles: last indexed, index coverage, open findings, watched vendors,
last run, corpus attempts. The evidence beneath each is what we already return beside it — the
per-vendor split under the finding count, the per-rung split under a detector's total, which
M4.5-W145 has now drawn.

**Two declines.**

`ChartMetric`'s `status` prop (`:229`) and the sign-to-variant mapping at `:246-252` colour a delta
positive or negative by its sign. In their domain more requests is up and more errors is down, and
even there the component has to be told which. In ours a delta has no such axis: more open findings
this week is not worse, it is more findings, and the console's own detectors screen already refuses
to sort by count for exactly that reason
(`web/src/features/detectors/detector-accountability.tsx:11-14`). **A delta may be shown; it may not
be coloured.**

The evidence table's key (`ApiRenderers.tsx:197`) concatenates the array index with the row's
identity. Including the index means a reordering reuses the wrong DOM node. Our `PageControls` and
tables should key on identity alone, and this is a concrete example of why.

---

## What was read and declined, in one place

A mechanism read and rejected is worth as much as one adopted, and this repository has re-derived
rejected ideas more than once.

| Read | Where | Declined because |
|---|---|---|
| Status dot on a navigation item | `Sidebar.tsx:221-244` | Their dot has a closed lint lifecycle behind it. Ours would collapse *could not check* onto *checked and passed* — `CLAUDE.md`'s standing refusal |
| Resizable panel group in the shell | `DefaultLayout.tsx:115-138` | Machinery for a second sidebar we do not have; it also causes the layout shift its own deferred mount exists to fix |
| Confirm-on-dirty-close | `useConfirmOnClose.tsx` | Needs a write path. Recorded for M4's hosted half, not adopted |
| Settings card with its own Save | `BasicAuthSettingsForm.tsx:336-350` | Same. The rebaseline-on-server-value half transfers today |
| Delta coloured by sign | `Chart/index.tsx:246-252` | Our counts have no good direction; colouring one invents a verdict |
| Row key including the array index | `ApiRenderers.tsx:197` | A reorder reuses the wrong node |
| Evidence block that vanishes when empty | `ApiRenderers.tsx:178` | Absence rendered as nothing at all, which is the defect this console exists to remove |
| An empty state's copy | `empty-states.mdx:27`, `SKILL.md` | Their wording is theirs. The *rule* — active language when the reader is meeting a feature, a plain statement of absence in a table — transfers; the strings do not |

## Where their mechanism rests on something we do not have

Stated and stopped, rather than designed around:

- **A user model.** Their permission gates (`useAsyncCheckPermissions`) and their platform/self-hosted
  split are everywhere in this tree. We have no users and no authorization story.
- **A write path.** The settings card, the dirty-dismissal guard and the confirmation dialogs all
  exist to protect an edit. Every route we serve is a GET, held behaviourally by
  `tests/test_api_routes.py`.
- **Live infrastructure metrics.** Their overview's spatial panel reports CPU, disk and connections.
  `direction/NOTES.md` §3 already records that this does not transfer and why.
- **A query the reader can open.** Their report widget hands you the SQL behind the number
  (`ReportWidget.tsx:66-88`), which is the most attractive idea in the read: a panel that can show
  the reasoning behind its own figure is precisely this console's argument. We cannot do it — the API
  is a read surface over a view model and issues no SQL a reader could be given
  (`.claude/rules/console-dev-loop.md`). What we *can* hand a reader is the rung and the evidence
  behind a claim, which we already do. Naming this as unavailable rather than nearly-available is the
  point.

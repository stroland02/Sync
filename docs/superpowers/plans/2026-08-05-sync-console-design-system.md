# M4 Slice 3 — The console's design system

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Also required before Task 7:** the `dataviz` skill. It is the authority on chart form and
> colour, and a chart specified without it will be specified wrong. This plan applies it once, at
> planning time; the implementing agent applies it again against real numbers.

**Goal:** Give the operator console a design system — a colour system that works in both light and
dark, a type scale, a spacing rhythm, an elevation rule, and motion defaults — so that a reader
can tell six levels of a graph apart at a glance, and so that the libraries already installed and
unused have a decided job rather than an open invitation.

**This slice builds no new screen and no new route.** Everything it touches already renders. The
work is that the console currently runs on Tailwind's stock defaults plus fourteen achromatic
colour tokens, which is not a design system; it is the absence of one, added deliberately in
slice 1 and deferred to here.

---

## What is already satisfied, read from the tree

The owner supplied a scaffold specification. **All of it exists.** Verified against
`web/package.json`, `web/vite.config.ts`, `web/tsconfig.app.json` and the `web/src/` tree on
2026-08-05. Nothing in this plan re-scaffolds anything.

| Specified | State | Evidence |
|---|---|---|
| Vite | Present, v8.2.0 | `web/package.json:42`, `web/vite.config.ts:1-16` |
| React 19 | Present, 19.2.8 | `web/package.json:23-24` |
| Tailwind | Present, v4.3.3, via the Vite plugin | `web/package.json:31,40`, `web/vite.config.ts:4,7` |
| shadcn/ui on Radix | Present. CLI 4.16.1; `radix-ui` 1.6.7 | `web/package.json:22,39`; `Slot` imported at `web/src/components/ui/button.tsx:3` |
| `lucide-react` | **Installed, zero imports** | `web/package.json:21`; no match in `web/src` |
| `framer-motion` | **Installed, zero imports**, 12.43.0 | `web/package.json:20`; no match in `web/src` |
| `@react-three/fiber` + `drei` + `three` | **Installed, zero imports** | `web/package.json:13-14,28,36`; `web/src/components/3d/` holds only a README |
| `react-grid-layout` | **Installed, zero imports**, 2.2.4 | `web/package.json:25,35`; its stylesheet at `node_modules/react-grid-layout/css/styles.css` is imported nowhere |
| `echarts` + `echarts-for-react` | **Installed, zero imports**, 6.1.0 | `web/package.json:18-19`; there is no `web/src/components/charts/` directory, though slice 1's file structure named one (`2026-07-30-sync-m4-dashboard.md:101`) |
| Path aliases | Present in both places | `web/vite.config.ts:8`, `web/tsconfig.app.json:4` |
| `components/ui`, `components/3d`, `layouts`, `features` | All present | `web/src/` tree |
| `@tanstack/react-query`, `react-router` | Present, 5.101.4 and 8.3.0 | `web/package.json:15,26` |

**So the work is not scaffolding.** It is using what is installed and unused, and deciding what
`index.css` refuses to decide.

### The three deltas between the specification and the tree

**1. `tailwind.config.js` — the specification asks for it; Tailwind v4 does not want it, and I
confirmed this rather than assuming it.**

Slice 1 declined to create one, on the argument that a config nothing reads is worse than none
(`2026-07-30-sync-m4-dashboard.md:121-123`). That argument still holds, and it is now checkable
against the installed compiler rather than against a memory of the v4 announcement. Grepping
`web/node_modules/tailwindcss/dist/lib.mjs` (4.3.3, minified) for `@config` finds the at-rule
handler, which throws on a body and on nesting, and pushes the named path onto a load list.
**There is no auto-discovery path: a JS config is loaded only when a stylesheet names it with
`@config "…"`.** A `tailwind.config.js` created and not referenced would be read by nothing and
would silently diverge from the tokens actually in force.

**Decision: no config file. `@theme` in `web/src/index.css` is the entire configuration surface,
and this slice makes it the design system.** If a third-party plugin ever demands the JS shape,
the correct move is one `@config` line, not a second source of truth.

**2. The `@react-three/fiber` and `react-grid-layout` deferrals are reinstated by the owner.**

`2026-08-04-sync-m4-slice-2.md:506,508` recommends **deleting** both deferral rows and removing
four packages, on the argument that their retiring conditions had been argued down to "never".
`2026-08-04-sync-m4-slice-2.md:576-579` raises that as owner question 4, which was the correct
place for it.

**The owner has answered, and the answer is no.** Both libraries stay installed and both
deferrals stay open. This is recorded here as **a decision by the plan's owner**, reversing a
recommendation this repository's own plan made. Nothing in this slice removes a package, and
`web/src/components/3d/README.md` is updated in Task 8 so a future reader finds the reversal
rather than the superseded argument.

What the reversal does **not** do is convert either library into a task. An installed library is a
capability, not a requirement. Sections *Where 3D earns its place* and *Where a draggable
dashboard earns its place* decide each on its merits, and both conclude "not in this slice, and
here is the condition".

**3. `web/src/index.css` holds a minimal neutral set and nothing else. That absence is the gap.**

`web/src/index.css:8-26` declares exactly **fourteen** colour tokens. Thirteen are achromatic
(`oklch(L 0 0)`); the fourteenth is `--color-destructive`, `oklch(0.51 0.19 27.5)`. Its own
comment says so: "The minimum the shadcn catalog needs to be legible, and no more"
(`index.css:9-11`).

Everything else is Tailwind's stock default theme, unmodified: `--spacing: 0.25rem`
(`node_modules/tailwindcss/theme.css:325`), `--text-xs` through `--text-base`
(`theme.css:347-352`), `--radius-md` and `--radius-lg` (`theme.css:399-400`). The console has
never made a typographic or spatial decision — it has inherited defaults and then chosen classes
one at a time.

Three consequences are already measured rather than asserted, all from
`docs/superpowers/references/notes/impeccable-interface-quality.md`:

- **The type hierarchy is flat at a measured 1.5:1** across the whole console — 12px, 12.8px,
  14px, 16px, 18px — against a 2.0 threshold, reproduced by running a detector over a fixture
  mirroring the finding page (`impeccable-interface-quality.md:279-287`, `384-390`). Every `h1`
  in the console is `text-lg`: `overview-page.tsx:32`, `finding-page.tsx:76`,
  `workflow-page.tsx:95`. A six-level graph hierarchy renders at nearly one size.
- **The spacing values are numerous rather than rhythmic.** `p-2`, `p-4`, `px-4`, `py-3`, `py-6`,
  `gap-1`, `gap-2`, `gap-3`, `gap-4`, `mt-1`, `mt-2`, `mt-3`, `mb-6` and more, enumerated at
  `impeccable-interface-quality.md:150-158`. That variety is diagnostic of choosing per component,
  not of a rhythm.
- **Colour tokens are already unreachable.** `--color-input` is referenced only under a `dark:`
  prefix (`button.tsx:14`) and there is no `.dark` element anywhere (`index.css:3-6`).
  `--color-secondary`, `--color-secondary-foreground` and the `link` variant's `--color-primary`
  are referenced only by `Button` variants no screen uses — every `Button` in the console is
  `variant="outline"` (`error-surface.tsx:84`, `page-controls.tsx:32,40`,
  `workflow-page.tsx:68,109`). `2026-08-04-sync-m4-slice-2.md:444-446` parks these for this slice
  by name.

What is **not** broken and must survive: every current text pairing clears WCAG AA, worst case
5.05:1, computed from the OKLCH values at `impeccable-interface-quality.md:317-326`. A design
system that ships colour and loses that is a regression, not a slice.

---

## The architectural spine, before any file

Five decisions. They are here rather than in a task because a task that gets them wrong produces a
console that looks better and says less.

### 1. The design system is decisions, and decisions are tokens

A design system is not a look. It is the set of questions a future agent is no longer allowed to
answer per component. Every one of them lands as a named custom property in `@theme`, so the
decision is a value a build reads rather than a paragraph a reviewer remembers.

The test of whether a decision belongs here: **if two agents building two different screens could
reasonably choose differently, and the difference would be visible, it is a token.** If it could
not, it is a class.

That means this slice's deliverable is mostly `web/src/index.css` plus a `DESIGN.md`, and only
secondarily the four views. A slice that edits twenty components and adds three tokens has done
the work in the wrong place.

### 2. Density is the constraint. Whitespace is the thing being spent, not the thing being bought

An operator reads this console all day, and the screens are tables of evidence. Every unit of
vertical space is a row that fell off the viewport. The standing failure mode of an AI-authored
design system is generous padding, big type and airy cards, which is exactly what makes a
data-dense console worse — and the 32 `slop` rules in Impeccable's registry are a catalogue of
those reflexes (`impeccable-interface-quality.md:132-141`).

**So the rule is: contrast carries hierarchy, and space is spent only where it separates two
things a reader must not confuse.** Body text stays at 14px. Table cell padding stays at
`TableCell`'s current `p-2` (`table.tsx:84`). What grows is the *range* — the page title and the
value-versus-label distinction — not the average.

The floor is 12px and it is a floor rather than a default. `undersized-ui-text` fires below 11px
on interactive text and on structural furniture including `td` and `th`, and its own docstring
records a build that shipped its entire furniture layer at 8px and was waved through because 8px
was on the design ramp (`impeccable-interface-quality.md:411-417`). **Being on this document's
ramp does not exempt a value from that floor.** No `text-[10px]`, ever, and that survives the next
time a table gets crowded.

### 3. Nothing on screen may assert what the data does not hold — and colour, motion and depth all assert

This is the console's existing position (`2026-07-30-sync-m4-dashboard.md:54-63`), and it is the
reason the design system is harder than a palette. Every expressive channel a design system adds
is a new way to make a claim:

- **Colour claims a judgement.** Painting `abandoned` red says the run went wrong. It did not: an
  abandoned run is data, and its reason is where routing learns which change kinds are not
  mechanically safe (`CLAUDE.md`, *Abandoned runs are data*; `run-outcome.tsx:73-94`). Disposition
  is *identity*, not *status*, and it gets categorical colour, never the status palette.
- **Motion claims a time.** Animating eight nodes in sequence asserts an order and a duration the
  checkpoint does not carry.
- **Depth claims a relationship.** A shadow says "this floats above that". Cards do not float
  above tables.

The channels that may carry a claim, because the data holds one, are: the **run outcome** (a
recorded terminal value), the **error state** (a real failure), and **absence** (a recorded null,
already rendered as `ABSENT` — `format.ts`, one glyph everywhere). Everything else is neutral ink.

**The provenance rung is the load-bearing case and it stays monochrome.** `RungBadge` today is a
bare bordered span with no colour (`provenance.tsx:20-29`), and that is correct.
`static`/`resolved`/`observed`/`unresolved`/`unattributed` is an *evidence-class* scale, not a
good/bad one — the whole argument for the rung over a numeric confidence score is that it states
how a binding was established rather than how much to trust it
(`2026-08-04-what-the-research-changed.md:49,84-85`;
`docs/superpowers/references/notes/competitor-interfaces.md` §3.2). A red `observed` badge would
smuggle back the scalar the project rejected twice. If the rung ever gets colour it gets a
single-hue *ordinal* ramp with no good/bad end, never the four status hues.

### 4. Licensed component libraries are tools. Competitor interfaces are not references. These are different rules and both apply

`.claude/rules/interface-originality.md` is binding, and it is misapplied in both directions by
default. Stated precisely so a future agent does neither:

- **shadcn/ui, Radix, Material-UI, and the copy-paste catalogues at 21st.dev are tools.** Using
  them is ordinary engineering. They are not products Sync competes with, and taking a component
  from them is no more a design decision than taking a sort function from a standard library. This
  console already sits on shadcn (`web/src/components/ui/`) and will take more from it.
- **The twenty-two screenshots under `docs/superpowers/references/screenshots/` are off limits as
  visual reference.** They are research into how six competitors *conceive* of a finding, a piece
  of evidence, and a run in progress — never into how they draw one. Reading them for a layout is
  the exact failure `interface-originality.md` was written to prevent, and the commercial argument
  is in `2026-08-04-what-the-research-changed.md:119-122`: a console assembled from screenshots of
  black-box tools inherits the assumptions that produced the problem.
- **Inspiration galleries — awwwards, Framer's marketplace — are for technique, not for layout.**
  "How is a shared-element transition implemented" is technique. "Copy this hero" is not. A
  console has no hero.

**The test, restated so it can be applied without judgement:** state the thing as a problem the
operator has, without naming where it came from. "A reviewer cannot tell a page title from a card
title" is a problem. "Their dashboard has bigger headings" is not. If the justification needs the
pointer, delete the pointer and make the argument from the graph and the operator — or drop the
change.

### 5. Dark mode ships with light or it does not ship

`index.css:3-6` pins the console to one palette on purpose: `@custom-variant dark (&:is(.dark *))`
with no `.dark` element anywhere, so shadcn's `dark:` rules cannot fire against tokens that have
no dark values. That was the right call for a fourteen-token neutral set.

It is the wrong call for a design system, because a half-shipped dark mode is how a token layer
rots: some tokens get dark values, some do not, and the ones that do not are invisible until
somebody flips the switch. The dataviz skill states the same rule from the chart side — the dark
column is "the same eight hues stepped for the dark surface, not a separate palette", **selected
and validated against the dark surface, never an automatic flip** (`dataviz/references/palette.md`,
*Categorical palette* and step 6 of the procedure).

**So Task 1 defines every token in both modes, and Task 2 ships the switch that makes the second
half reachable.** If the owner declines dark mode (owner question 1), Task 1 still defines both
columns and Task 2 is cut — the tokens cost nothing unreachable that the existing five unreachable
tokens do not already cost, and a later switch is then an hour rather than a re-derivation.

---

## Global Constraints

- **No new route, no new screen, no transport change, no Python.** This slice touches
  `web/src/**` and adds `DESIGN.md`. A screen that needs a field the API does not send is out of
  scope and belongs in slice 2's *Questions only the owner can settle*.
- **`.claude/rules/interface-originality.md` binds every visual decision.** Architectural
  decision 4 states how it applies. Every task's verification asks the operator-problem question.
- **WCAG AA is a floor that must not regress.** Every current pairing clears it, worst case 5.05:1
  (`impeccable-interface-quality.md:317-326`). Any new pairing is computed, not eyeballed.
- **The colour palette is validated by running the validator, not by reasoning about it.**
  `node <dataviz-skill>/scripts/validate_palette.js "<hex,…>" --mode light --surface <light>` and
  again `--mode dark --surface <dark>`. Its output is pasted into `DESIGN.md`. A FAIL is fixed
  before the task closes; a contrast WARN obligates a visible label or a table view and is not
  dismissable.
- **Every motion respects `prefers-reduced-motion: reduce`.** Not a task, a condition of the
  feature existing.
- **The absence marker stays one glyph everywhere** (`ABSENT`, `format.ts`). The design system
  gives it a token for its colour and changes nothing else about it.
- **`provenance` is rendered, not dropped**, and after this slice it must also be *visible*:
  `bindingNullLabel` stays required, and the Rung column stops sliding off a 1280px viewport (see
  Task 4).
- **The console still has no test runner** (`web/package.json:6-11`, four scripts, none of them
  `test`). Verification is `npm run build`, `npm run lint`, and a stated human observation — the
  same standard slice 2 works to (`2026-08-04-sync-m4-slice-2.md:90-99`). Do not add one for this;
  it is named in *What I am not proposing*.
- **No package is removed.** The owner's reversal (delta 2) governs.

---

## Where motion earns its place, and where it does not

`framer-motion` 12.43.0 is installed with zero imports. The question is not whether to use it. It
is which three things it is allowed to do.

**The rule: motion may express a change the reader would otherwise have to detect by diffing
against memory. It may not express state, and it may not express time the data does not carry.**

### Earns its place

1. **The error surface arriving and leaving.** `ErrorSurface` renders `fixed inset-x-0 top-16
   z-50` and appears with no transition (`error-surface.tsx:71-95`). An element that materialises
   at the top of the viewport is indistinguishable from a re-render; a ~120ms fade and 4px
   translate says *something arrived*. This is the clearest win in the console and it is not
   decoration — it is the difference between an event and a redraw.
2. **A row or node that changed under a poll.** The workflow view re-reads every
   `WORKFLOW_POLL_MS` (`run-outcome.tsx:17,66-68`) and slice 2's fleet runs table will poll too
   (`2026-08-04-sync-m4-slice-2.md:356-357`). When a node moves `current → done` while the reader
   is looking at it, nothing marks the change; when they looked away for ten seconds, nothing tells
   them. A one-shot ~600ms background wash on the changed element, decaying to nothing, is the one
   fully honest motion in this product: **it encodes a real event — a checkpoint was written —
   with a real timestamp behind it.**
3. **Height on a page swap.** `PageControls` replaces a table body and the page height jumps
   (`page-controls.tsx:28-47`, used at `vendor-findings-table.tsx:88-96`). A height transition on
   the container removes a jolt for one component. Genuinely marginal; ranked last and cut first.

Three usages. **If the implementation ends with more than five `motion.` call sites, that is the
signal to stop and re-read this section**, not a sign the section was too strict.

### Does not earn its place

- **Animating the node sequence as a play-through.** `NodeSequence` renders eight nodes with
  `done`/`current`/`pending` and a connecting rule (`node-sequence.tsx:95-124`). Staggering them
  in, drawing the connector as it "progresses", or pulsing the current node all narrate a run that
  has already finished, at a speed and in an order that are rendering choices. The checkpoint
  carries no per-node duration. The view's entire claim is *this is what happened*; an animation
  would add *and this is when*, which is a fabrication. **Explicitly forbidden**, and it is
  forbidden precisely because it is the most tempting thing in the console to animate.
- **A pulsing dot, ring or shimmer on a live run.** Slice 2 rules out a liveness dot on data
  grounds: there is no heartbeat and no process registry, and a run parked at `await_ci` writes no
  checkpoint for minutes *by design*, so silence has two meanings and nothing separates them
  (`2026-08-04-sync-m4-slice-2.md:72-88`, `540-542`). A pulse is that same false claim rendered at
  60fps. The competitor note reaches the same place independently and takes from Pentagon only the
  *absence* of decoration on idle nodes (`competitor-interfaces.md` §3.1).
- **Count-ups on numbers.** A value animating from zero displays a sequence of numbers that were
  never true. On a console whose position is that it does not render confident wrong values, this
  is disqualifying rather than merely tacky.
- **Route transitions and shared-element morphs between screens.** The routes are graph levels
  (`App.tsx:19-27`). An operator navigating from a vendor to a finding is going somewhere on
  purpose; a cross-fade delays the paint of the thing they asked for and buys a sense of continuity
  the breadcrumb already provides (`layouts/breadcrumbs.tsx`).
- **Skeleton shimmer in place of `LoadingState`.** `LoadingState` names what is being asked for
  (`states.tsx:43-49`), which is strictly more information than a grey rectangle pretending to be
  content that has not arrived.

---

## Where 3D earns its place, if anywhere

`@react-three/fiber` 9.7.0, `@react-three/drei` 10.7.7 and `three` 0.185.1 are installed with zero
imports, and the owner wants them available. The honest question is whether the API Dependency
Graph contains a spatial question, because the prior rejection was of a *competitor's* canvas
rather than of the idea (`competitor-interfaces.md` §3.1;
`2026-08-04-what-the-research-changed.md:86-87`).

**The case for.** Sync's graph is a genuine graph, unlike Pentagon's roster of agents. "This one
vendor operation changed — show me every call site bound to it, across every repository" is a real
question an operator has, it is relational rather than tabular, and a table answers it one row at
a time. As repositories multiply, a 2D force layout of hundreds of call sites bound to dozens of
operations does become a hairball, and a third axis is a real way to separate clusters. That is a
better argument than "a graph looks good in 3D", and it deserves to be stated before it is
rejected.

**The case against, and it wins on four counts.**

1. **The relation is shallow, not deep.** Call site → binding → vendor operation → vendor change
   is depth three, and it is bipartite at every hop. There is no long path to trace, no cycle to
   untangle, no community structure to discover. Three-layer relations render as layered 2D
   diagrams; they gain nothing from a camera.
2. **Occlusion is a correctness failure here, not an aesthetic one.** In any 3D scene, nodes hide
   behind nodes. A view whose purpose is "here is *every* call site this change will break" cannot
   adopt a primitive whose native failure mode is silently omitting some of them. **You cannot
   count what you cannot see**, and a console built to stop confident wrong verdicts must not
   render one by geometry.
3. **Position would be fabricated.** The data has no third axis — no depth, no elevation, no
   coordinate of any kind. Every pixel of a node's position would be layout-engine output, and
   architectural decision 3 forbids exactly that: nothing on screen may assert what the data does
   not hold. In 2D the same objection applies to *x* and *y*, but a 2D diagram can be honest by
   fixing the axes to something real (layer, vendor). A free camera cannot.
4. **A canvas has no DOM.** No keyboard navigation, no screen reader, no browser text search. The
   single most common thing an operator does with this console is look for a file path, and
   `Ctrl-F` on a table finds it. Add roughly 600 KB of `three` to every page load for the
   privilege.

**Conclusion: no 3D in the operator console, and this plan proposes none.** The libraries stay
installed per the owner's reversal, and `web/src/components/3d/README.md` is rewritten in Task 8 to
record *this* argument rather than slice 1's placeholder — so the next agent finds a decision
instead of an empty directory.

**The real question gets a real answer, in 2D.** "Which call sites does this one vendor change
touch" is worth a view. It is a **layered bipartite diagram in SVG** — DOM nodes, keyboard
navigable, text-searchable, with both axes bound to something real. It is not in this slice
because slice 2 has not yet shipped the fleet screen it would sit beside, and because the dataviz
skill's own default for more than about seven meaningful classes is a table
(`dataviz/references/choosing-a-form.md:14`) — which is what `vendor-findings-table.tsx` already
is. It is a deferred row with a stated condition, below.

The one condition that would genuinely reopen 3D: **a spatial fact enters the data.** Not more
rows — a coordinate. Nothing on the roadmap produces one.

---

## Where a draggable dashboard earns its place

`react-grid-layout` 2.2.4 is installed with zero imports, and its stylesheet
(`node_modules/react-grid-layout/css/styles.css`) is imported nowhere, so a panel dragged today
would render unstyled. Its deferral condition was "needs a user who knows what they want on
screen" (`2026-07-30-sync-m4-dashboard.md:254`).

**Is slice 2's fleet view that user? No.**

The fleet screen is three fixed panels answering three fixed questions: a runs table, a corpus
summary, a repositories roll-up (`2026-08-04-sync-m4-slice-2.md:230-235`, Task 3). That is a screen
that answers questions, not a canvas an operator composes. Two things have to be true before
draggability is a feature rather than a toy, and neither is:

1. **More panels than fit, so order carries information.** Three panels fit.
2. **A place to persist the layout that survives the browser.** There is no user model anywhere in
   the tree and no auth; the server binds 127.0.0.1 by default
   (`2026-08-04-sync-m4-slice-2.md:550-552`). A draggable grid would store its layout in
   `localStorage`, which means the layout is per-browser and silently lost on a new machine — **a
   feature that quietly forgets is worse than a fixed layout**, and this is the console that does
   not do quiet.

**Conclusion: not in this slice.** The package stays installed per the owner's reversal. The
retiring condition, stated so it is checkable rather than rhetorical: *the auth slice has shipped a
per-operator preference store, the fleet screen carries more panels than one viewport, and an
operator has asked to reorder them.* All three, not any one.

---

## The enterprise-grid fallback protocol

Material-UI as a **secondary** system for one specific heavy-duty grid.

**The cost, stated honestly, because it is the part people skip.** Two design systems is a cost
paid per component and per session, not once at install:

- Every future control is looked up twice and the answer is "it depends which screen".
- The two systems disagree about focus rings, density, radius and elevation, so either the MUI
  grid looks foreign on a Sync page or somebody spends a week theming it — and that theme is a
  third source of truth that drifts from `@theme` with nothing to catch it.
- MUI's emotion runtime and the grid itself are a real bundle cost on a console whose current
  dependency list is already carrying `three` and `react-grid-layout` unused.
- A future agent reads a codebase with two catalogues and reasonably picks the wrong one.

**Try this first, because it is strictly cheaper.** TanStack Table plus `@tanstack/react-virtual`
is *headless*: it supplies sorting, filtering, column pinning and virtualisation and renders
nothing, so the markup stays shadcn's and no second design system enters the tree. The vendor is
already in `package.json` (`@tanstack/react-query`, `web/package.json:15`).

**The exact condition that triggers reaching for MUI.** All of:

1. One named route needs a grid, and **shadcn's `Table` plus TanStack headless has been tried and
   recorded as failing** — not predicted to fail.
2. At least two of: more than ~2,000 rows on screen at once such that DOM node count is the
   measured bottleneck; column pinning is required and cannot be solved by column order; per-column
   filtering with multi-column sort over server-side pagination.
3. The bundle size is measured before and after and written into the commit.

**And the scope is one route.** MUI is imported by that route's files and nowhere else, with a
single theme file mapping Sync's `@theme` tokens onto MUI's palette so the two cannot drift
silently. A second route wanting it is a decision to migrate wholesale, taken by the owner — not a
second exception.

**Note what triggers this today: nothing.** The one grid complaint on record is that the Rung
column slides off a 1280px viewport on a seven-column table
(`impeccable-interface-quality.md:365-372`), and the cheap fix is column order, which is Task 4.
Reaching for a grid library to solve a column-order problem would be the most expensive possible
answer.

---

## Charts, applying the `dataviz` skill

The skill was invoked at planning time. Its procedure is *form → colour job → validate → marks →
hover → accessibility → look at it*, and colour comes last.

**Where the first chart goes.** Slice 2's corpus summary — attempts by disposition, by strategy,
by tier (`2026-08-04-sync-m4-slice-2.md:348-351`). Slice 2 deliberately specifies a table and names
charts under *not proposing*, on "functionality before polish" (`:545`). That constraint is what
this slice retires, and only for that panel.

**Form, decided before colour:**

- **`attempts` and `distinct_findings` are a KPI row of two stat tiles, not a chart.** They are
  single current values, and the skill's first rule is that a single value is a stat tile and not
  a one-bar bar chart (`choosing-a-form.md:10-11`). They are also the two numbers slice 2 insists
  must read as different things (`2026-08-04-sync-m4-slice-2.md:119-121`, `276-279`), which a
  two-bar chart would actively blur.
- **Disposition is part-to-whole over a small closed set → one horizontal stacked bar**
  (`choosing-a-form.md:27`; horizontal because the category names are long strings).
- **Strategy and tier: count the classes first.** More than about seven classes that all carry
  meaning is a table, not more colours (`choosing-a-form.md:14`). Measure against the real
  `migration_outcome` rows before choosing; if either exceeds seven, it stays the table slice 2
  specified and that is the correct outcome, not a failure of this task.
- **No sparkline and no trend line.** `migration_outcome.created_at` exists
  (`src/sync/graph/schema.sql:229`), so a time axis is *possible* — but slice 2's `corpus_summary`
  emits no timestamp (`2026-08-04-sync-m4-slice-2.md:253,348-351`), so a trend chart needs a view
  model change, which is a Python task in another slice.

**Colour job:** disposition is **identity**, so categorical, fixed slot order, never cycled — and
explicitly **not** the status palette, per architectural decision 3. `abandoned` is not "bad".

**Non-negotiables carried from the skill:** one axis, never dual; a legend whenever there are two
or more series, with direct labels at four or fewer; text in ink tokens rather than in the series
colour; recessive grid and axes; status colours reserved and always shipped with an icon and a
label, never colour alone (`dataviz/references/palette.md`, *Status palette*: on a light surface
`warning` and `serious` sit below 3:1 by design and the icon-plus-label pairing is the mitigation).

**And the caption is part of the chart.** Slice 2 requires the sentence that three abandonment
classes never reach `migration_outcome` at all, so the denominator excludes the earliest failures
(`2026-08-04-sync-m4-slice-2.md:209-214`). A chart hides an omitted denominator better than a table
does, so that sentence ships as the figure's caption, not as an aside somewhere on the page.

---

## File Structure

```
DESIGN.md                              new — the design system as a document, with the validator's output
web/src/index.css                      the whole token layer: @theme, light and dark
web/src/lib/theme.ts                   new — reads OS + stored preference, stamps `.dark` on <html>
web/src/lib/motion.ts                  new — the three sanctioned transitions + a reduced-motion hook
web/src/components/theme-toggle.tsx    new
web/src/components/status.tsx          new — status treatment: icon + label + colour, never colour alone
web/src/components/charts/echart.tsx   new — the one echarts wrapper, themed from the tokens
web/src/features/fleet/corpus-chart.tsx new — Task 7, gated on slice 2 Task 3 landing
web/src/components/{provenance,states,error-surface,page-controls}.tsx   re-themed
web/src/components/ui/{card,table,button}.tsx                            token fixes only
web/src/layouts/app-shell.tsx          the toggle, and the type scale on the header
web/src/features/**/*.tsx              heading levels and the type scale applied
web/src/components/3d/README.md        rewritten to record the reversal and the 3D argument
```

`DESIGN.md` at the repository root is deliberate. Impeccable's four `design-system-*` rules
validate against a `DESIGN.md` or `.impeccable/design.json` the project supplies, and there is no
`DESIGN.md` at this repository's root today, which is why those four rules are permanently silent
(`impeccable-interface-quality.md:143-148`). Writing one turns four dead rules into live ones, and
gives the console-improvement tick something to check that is not taste.

---

### Task 1: The token layer — colour, type, space, radius, elevation, in both modes

**Files:** Modify `web/src/index.css`. Create `DESIGN.md`. **~1 day.**

This is the highest-value task in the slice and everything else reads from it. It adds no
component and changes no markup.

**What gets decided, and what each decision is *for* in a console whose job is showing evidence:**

- **A neutral ramp, not five values.** Nine steps, light and dark, so surface, border, muted ink
  and primary ink are *positions on a scale* rather than independent guesses. Purpose: a console of
  tables needs three or four levels of recession (header, row, hovered row, muted metadata) that
  are reliably distinguishable and reliably *not* louder than the data.
- **One brand hue, used sparingly.** Purpose: links, focus, and the current node. It is the only
  chromatic thing on a normal screen. Owner question 2 settles which hue; the token structure does
  not depend on the answer.
- **A reserved status palette — good / warning / serious / critical.** Purpose: the run outcome and
  the error state, and nothing else. Never a series colour, always with a `lucide-react` icon and a
  word (`dataviz/references/palette.md`, *Status palette*). This is `lucide-react`'s first job in
  the console.
- **A categorical series palette, fixed order, never cycled.** Purpose: charts only, Task 7.
  Validated as a set in both modes.
- **A type scale of six steps, each with a stated job**, replacing the current 12/12.8/14/16/18
  range that measures 1.5:1 (`impeccable-interface-quality.md:279-287`):
  `meta` 12px (labels, timestamps, furniture — the floor, and it is a floor);
  `body` 14px (prose and table cells — 14 rather than 16 because rows-per-screen is the currency);
  `emphasis` 16px (card titles, panel headlines);
  `section` 18px;
  `page` 24px (the `h1` on every view — this step alone takes the range ratio to 2.0 and clears
  `flat-type-hierarchy`);
  `figure` 32px+ (stat-tile values, Task 7 only).
- **The mono/sans rule, written down because it already holds and must survive.** **Mono means
  "this is a value the system recorded verbatim"** — a file path, a finding id, a node name, an
  operation, compiler output. Sans is prose. That distinction already runs through
  `finding-page.tsx:122-155`, `vendor-findings-table.tsx:63-83`, `evidence.tsx:229`,
  `node-sequence.tsx:108`, and it is doing real work: it tells a reader which strings came from the
  graph. Mono also supplies column alignment for count columns
  (`overview-page.tsx:76-78`), so no `tabular-nums` is needed while numbers stay mono; a
  proportional-sans number column would need it (`dataviz/references/palette.md`, *Typeface &
  figures*).
- **Three spacing tokens, and adding a fourth is a decision.** `space-row` 8px (table cell padding —
  what `TableCell`'s `p-2` already is, `table.tsx:84`); `space-field` 4px (label to value inside a
  card); `space-section` 16px, with 24px between top-level sections. Purpose: it makes "how much
  space here" answerable without judgement, which is what the current thirteen-plus ad-hoc values
  (`impeccable-interface-quality.md:150-158`) prove is missing.
- **Two elevation levels, and the mechanism is a ring.** *Flat* — a card, a table, a panel: a
  hairline ring, which is what `Card` already uses (`ring-1 ring-foreground/10`, `card.tsx:15`).
  *Floating* — something that occludes content: ring plus shadow, which is what `ErrorSurface`
  already uses (`shadow-lg`, `error-surface.tsx:79`). Purpose: a console with no depth to
  communicate should not paint depth, and the one thing that genuinely floats should say so. Two
  levels, no third.
- **Radius, once.** The catalog currently mixes `rounded-xl` (`card.tsx:15`), `rounded-lg`
  (`button.tsx:7`), `rounded` (`provenance.tsx:23`, `states.tsx:32`, `run-outcome.tsx:34`) and
  `rounded-[min(var(--radius-md),10px)]` (`button.tsx:26`). Pick two — `radius-control` and
  `radius-surface` — and let everything else resolve to one of them.

- [ ] **Step 1:** Draft the ramps and the four palettes as hex, both modes. Derive the dark column
  by re-stepping the same hues against the dark surface, never by inverting the light column.
- [ ] **Step 2:** **Run the validator** — `node <dataviz-skill-dir>/scripts/validate_palette.js
  "<hex,…>" --mode light --surface <light surface>`, then again `--mode dark --surface <dark
  surface>`. Fix every FAIL. Record the full report.
- [ ] **Step 3:** Compute every text-on-surface pairing in both modes and confirm none is below
  the current worst case of 5.05:1 (`impeccable-interface-quality.md:317-326`). A pairing that
  regresses is a bug in the ramp, not an acceptable trade.
- [ ] **Step 4:** Write the tokens into `@theme` in `web/src/index.css`, light values at `:root`
  and dark values under `.dark`, so the existing `@custom-variant dark (&:is(.dark *))`
  (`index.css:6`) fires exactly as written with no change to it.
- [ ] **Step 5:** Write `DESIGN.md`: the tokens, what each is *for*, the mono/sans rule, the
  status-versus-identity rule, the 11px floor, and the validator's pasted output.
- [ ] **Step 6:** `npm run build` clean. Commit.

**Verification a reviewer can run:** re-run the validator against the hex list in `DESIGN.md` and
confirm it exits clean in both modes. Then break one step deliberately — move a categorical slot
to a near neighbour — and watch the CVD check FAIL. **A validator that has never rejected a
palette has not been shown to validate one.**

### Task 2: The theme switch, so half the token layer is reachable

**Files:** Create `web/src/lib/theme.ts`, `web/src/components/theme-toggle.tsx`. Modify
`web/src/layouts/app-shell.tsx`, `web/src/main.tsx`. **Hours.**

Without this, every dark token is exactly as dead as the five colour tokens slice 2 already parked
(`2026-08-04-sync-m4-slice-2.md:444-446`), and this slice would have added nine more.

- [ ] **Step 1:** `theme.ts` resolves in this order: an explicit stored choice, else
  `prefers-color-scheme`, else light. It stamps `class="dark"` on `<html>`.
- [ ] **Step 2:** Apply it before first paint, from an inline script in `index.html` or the top of
  `main.tsx` — a flash of the wrong theme is the classic defect here.
- [ ] **Step 3:** A three-state toggle in the app shell header (`app-shell.tsx:17-26`): light,
  dark, follow the system. Two states cannot express "follow the system", and an operator whose OS
  switches at dusk will notice.
- [ ] **Step 4:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** load each of the four views in both modes and confirm no
element is invisible, and that `ErrorSurface` (trigger it by stopping the API) is legible in dark.
Then set the OS to dark with the toggle on "system" and confirm the console follows without a
reload.

### Task 3: The type scale and the heading outline, applied

**Files:** Modify `web/src/features/**/*.tsx`, `web/src/layouts/app-shell.tsx`,
`web/src/components/ui/card.tsx`. **Hours.**

Two currently-failing, measured defects close here.

- [ ] **Step 1:** Raise every `h1` to the `page` step — `overview-page.tsx:32`,
  `finding-page.tsx:76`, `workflow-page.tsx:95`, and the vendor page. This alone takes the measured
  range ratio from 1.5:1 to 2.0:1 (`impeccable-interface-quality.md:384-390`).
- [ ] **Step 2:** Fix the skipped heading. The finding page has `<h1>` at `finding-page.tsx:76` and
  `<h3>` at `finding-page.tsx:33` with no `<h2>` between them, because shadcn's `CardTitle` renders
  a `<div>` and is not a heading at all (`card.tsx:36-47`); reproduced against a fixture at
  `impeccable-interface-quality.md:374-382`. Give `CardTitle` an `as`/`asChild` route to a real
  heading element and use `h2` on cards, so `FieldList`'s `h3` (`finding-page.tsx:33`) descends
  correctly. The workflow page is already correct (`workflow-page.tsx:95` h1,
  `run-outcome.tsx:38` h2, `node-sequence.tsx:108` h3) and is the shape to match.
- [ ] **Step 3:** Apply the scale's other steps: `meta` on the `<dt>` labels
  (`provenance.tsx:34`, `finding-page.tsx:119-152`), `body` on prose and cells, `emphasis` on card
  titles.
- [ ] **Step 4:** Confirm nothing renders below 12px anywhere. `undersized-ui-text`'s floor is 11px
  and covers `td`, `th` and anything classed `meta`, `label` or `badge`
  (`impeccable-interface-quality.md:411-417`).
- [ ] **Step 5:** `npm run build` clean. Commit.

**Verification a reviewer can run:** open each view and answer the checklist's own question — can
you tell a page title, a card title and a row label apart at a glance
(`impeccable-interface-quality.md:384-390`)? Then walk each page's heading outline in the
accessibility tree and confirm no level is skipped.

### Task 4: Density, elevation, the clipped focus ring, and the Rung column

**Files:** Modify `web/src/components/ui/{card,table,button}.tsx`,
`web/src/components/{states,error-surface,page-controls,provenance}.tsx`,
`web/src/features/vendors/vendor-findings-table.tsx`. **Hours.**

- [ ] **Step 1:** Reduce every spacing value to one of the three tokens. Where a value does not
  fit, that is a decision to record in `DESIGN.md`, not a fourth token added quietly.
- [ ] **Step 2:** Two elevation levels applied. `Card` and every hand-rolled panel
  (`states.tsx:27-39`, `run-outcome.tsx:30-37`) use the flat ring; only `ErrorSurface`
  (`error-surface.tsx:79`) floats.
- [ ] **Step 3:** **Fix the clipped focus ring.** `card.tsx:15` sets `overflow-hidden` on every
  Card and `button.tsx:8` draws focus with `focus-visible:ring-3`, a box-shadow, so `PageControls`
  at the bottom edge of a `CardContent` has its ring clipped
  (`impeccable-interface-quality.md:402-409`). Either drop `overflow-hidden` where nothing needs
  clipping, or give the focus ring an outline that is not clipped. Elevation and focus share a
  mechanism, which is why this sits in the elevation task.
- [ ] **Step 4:** **Make the Rung column reachable at 1280px.** `vendor-findings-table.tsx:47-87`
  renders seven columns with Rung sixth, and `table.tsx:71,84` puts `whitespace-nowrap` on every
  header and cell inside a `w-full overflow-x-auto` container. The widest cell is
  `{row.file}:{row.line}`, a path from a customer repository, and no fixture will be long enough to
  catch it (`impeccable-interface-quality.md:365-372`). Move Rung left of the call site, or let the
  call-site cell truncate from the left with the full value in `title`. **Provenance being rendered
  is not the same as provenance being visible**, and the console's whole claim rests on the second.
- [ ] **Step 5:** Give the prose panels a readable measure. `states.tsx` and `run-outcome.tsx`
  render the console's longest strings as bare `<p>` inside `max-w-7xl` — the workflow page's
  "no remediation run" explanation is over 300 characters
  (`workflow-page.tsx:105`; `impeccable-interface-quality.md:392-400`). Tables want the viewport and
  paragraphs do not. The `<pre>` blocks (`evidence.tsx:229`) are already correct and are not what
  this is about.
- [ ] **Step 6:** `npm run build` clean, `npm run lint` no new error-level violations. Commit.

**Verification a reviewer can run:** at a 1280px window, on the vendor findings table, confirm the
Rung column is on screen without scrolling the table sideways. Tab to the Next button inside a card
and confirm the whole focus ring is visible. At 1920px, confirm the workflow page's no-run
explanation wraps at a readable measure.

### Task 5: The three things the console decides repeatedly, as components

**Files:** Create `web/src/components/status.tsx`. Modify `web/src/components/provenance.tsx`,
`web/src/features/workflows/run-outcome.tsx`, `web/src/components/states.tsx`. **~half a day.**

Three vocabularies are currently re-decided at each call site. Each becomes one component, so the
next screen inherits the decision instead of re-making it.

- [ ] **Step 1:** **Status.** One component taking a status and a word, rendering a
  `lucide-react` icon plus the word plus the reserved colour. Colour never alone
  (`dataviz/references/palette.md`, *Status palette*). It replaces the two hand-rolled `Panel`
  components' tone props (`states.tsx:18-40`, `run-outcome.tsx:21-50`), which currently disagree —
  `states.tsx` uses `border-destructive bg-destructive/10 text-destructive`, `run-outcome.tsx` uses
  `border-2 border-destructive`.
- [ ] **Step 2:** **The rung stays monochrome, and the code says why.** `RungBadge`
  (`provenance.tsx:20-29`) keeps its bordered, uncoloured treatment. Add a comment stating the
  constraint the code cannot show: the rung is an evidence class, not a verdict, and colouring it
  reintroduces the scalar confidence score the project rejected twice
  (`2026-08-04-what-the-research-changed.md:49,84-85`). It gets the design system's *weight* and
  *spacing*, not its hue.
- [ ] **Step 3:** **Absence.** `ABSENT` (`format.ts`) gets the muted-ink token and one treatment
  everywhere. It is already one glyph; this makes it one appearance.
- [ ] **Step 4:** `npm run build` clean. Commit.

**Verification a reviewer can run:** grep for `destructive` in `web/src` and confirm every
remaining use is inside `status.tsx`. Confirm no status is distinguishable by colour alone by
loading a view with a colour-blindness simulator, or by disabling colour entirely and checking the
word is still there.

### Task 6: Motion, three usages

**Files:** Create `web/src/lib/motion.ts`. Modify `web/src/components/error-surface.tsx`,
`web/src/features/workflows/node-sequence.tsx`, `web/src/components/page-controls.tsx`.
**Hours.**

- [ ] **Step 1:** `motion.ts` exports the sanctioned durations and easings as constants, plus a
  `useReducedMotion` gate. Every transition in the console reads from it — a duration written
  inline is the beginning of a second motion system.
- [ ] **Step 2:** `ErrorSurface` enter and exit, ~120ms fade plus a small translate.
- [ ] **Step 3:** The changed-under-poll wash on a workflow node whose status changed between
  polls, ~600ms decaying to nothing. Keyed on the status value changing, not on a re-render.
- [ ] **Step 4:** Height transition on the paged table container. Cut this first if the slice runs
  long.
- [ ] **Step 5:** Confirm `prefers-reduced-motion: reduce` removes every one of them, not just
  shortens them.
- [ ] **Step 6:** `npm run build` clean. Commit.

**Verification a reviewer can run:** count `motion.` call sites — more than five means the *Where
motion earns its place* section was overridden without an argument. Set the OS to reduced motion
and confirm the console is entirely still. Confirm the node sequence does **not** animate on load.

### Task 7: The first chart — the fleet corpus summary

**Files:** Create `web/src/components/charts/echart.tsx`,
`web/src/features/fleet/corpus-chart.tsx`. Modify `web/src/features/fleet/corpus-summary.tsx`.
**~1 day. Gated on slice 2 Task 3 having landed.**

If the fleet screen does not exist yet, this task does not start — do not build a chart against a
payload shape that has not shipped.

- [ ] **Step 1:** **Re-read the `dataviz` skill.** This plan chose forms against the payload
  *shape*; the implementing agent chooses against real numbers, and the class-count rule
  (`choosing-a-form.md:14`) can send strategy or tier back to being a table. That is a correct
  outcome, not a failure.
- [ ] **Step 2:** One `echarts-for-react` wrapper reading its colours, ink and gridlines from the
  `@theme` tokens via `getComputedStyle`, so a theme switch repaints the chart. A chart with its
  own hardcoded palette is a second design system.
- [ ] **Step 3:** `attempts` and `distinct_findings` as two stat tiles, labelled as different
  things, per slice 2's grain rule (`2026-08-04-sync-m4-slice-2.md:119-121`).
- [ ] **Step 4:** Disposition as one horizontal stacked bar, categorical colour, direct labels,
  legend present. **Not the status palette.**
- [ ] **Step 5:** The denominator caption — three abandonment classes never reach
  `migration_outcome` (`2026-08-04-sync-m4-slice-2.md:209-214`) — as the figure's caption.
- [ ] **Step 6:** Hover tooltip on every mark; the table stays on the page beneath the chart as the
  accessible view. The table is not replaced by the chart.
- [ ] **Step 7:** Render it and look at it in both modes — the validator checks colour, not layout.
- [ ] **Step 8:** `npm run build` clean. Commit.

**Verification a reviewer can run:** switch theme with the chart on screen and confirm it repaints
rather than keeping light-mode colours. Confirm the numbers on the chart equal the numbers in the
table below it.

### Task 8: Record the decisions where the next agent will find them

**Files:** Modify `web/src/components/3d/README.md`, `web/src/index.css` (comments),
`docs/superpowers/loops/console-improvement-tick.md`. **Hours. This is the task to cut first.**

- [ ] **Step 1:** Rewrite `web/src/components/3d/README.md` with the owner's reversal and the
  occlusion argument from *Where 3D earns its place*, replacing the slice-1 placeholder that says
  only "not built yet".
- [ ] **Step 2:** Add the seven-item checklist from
  `impeccable-interface-quality.md:328-417` under step 2 of the console-improvement tick, marking
  which items this slice closed.
- [ ] **Step 3:** If — and only if — the detector is installed, wire the URL scan **with its
  precondition**: `node -e "require.resolve('puppeteer')"` must pass first, because a URL scan
  without puppeteer writes one line to stderr and **exits 0**, which reads as clean
  (`impeccable-interface-quality.md:207-223`). A tick that records a clean result without that
  check has recorded nothing.

**Verification a reviewer can run:** uninstall puppeteer, run the tick's scan command, and confirm
it refuses rather than reporting clean.

---

## Ranking, and what loses

Value over cost, for a solo and self-funded project.

| # | Task | Cost | Why it ranks here |
|---|---|---|---|
| 1 | Token layer | ~1 day | Everything else reads from it. Doing any other task first means doing it twice. |
| 3 | Type scale + heading outline | Hours | Closes two *measured, currently failing* defects for the least work in the slice. The single cheapest visible improvement. |
| 4 | Density, elevation, focus ring, Rung column | Hours | The Rung fix protects the console's central claim; the focus-ring clip is an accessibility defect with a one-line cause. |
| 2 | Theme switch | Hours | Cheap, but it only pays off if dark ships at all — owner question 1. |
| 5 | Status / rung / absence components | ~½ day | Prevents the next screen re-deciding. Value is in the future, which is why it is not higher. |
| 6 | Motion | Hours | Real but small. Two of the three usages are genuinely informative; the third is comfort. |
| 7 | The first chart | ~1 day | Highest cost, and **blocked** on slice 2. Also the least certain: the honest outcome may be "the table was right". |
| 8 | Recording the decisions | Hours | **Cut first.** Steps 1 and 2 are ten minutes each and worth keeping; step 3 is the detector wiring and it loses. |

**What loses, explicitly:**

- **Task 8 step 3, the detector wiring.** Five of the seven checklist items are answered by tasks
  3 and 4 anyway, and the URL path fails as a pass unless puppeteer is proven present
  (`impeccable-interface-quality.md:207-223`). Half a day for a gate that mostly restates work
  already done.
- **Task 6 step 4, the height transition.** Comfort, not information.
- **Task 7, if slice 2 has not landed.** Do not build a chart against an unshipped payload.
- **A 3D view and a draggable dashboard.** Neither is a task, for the reasons argued above.

---

## What I am not proposing, and what decided it

- **Any 3D in the console.** Argued above on four counts, the decisive one being that occlusion
  makes "here is every affected call site" unprovable. The libraries stay installed by the owner's
  decision; that is not the same as a use.
- **A draggable dashboard.** The fleet view is three fixed panels and there is nowhere to persist a
  layout that survives the browser.
- **`tailwind.config.js`.** Verified against the installed compiler: v4.3.3 loads a JS config only
  through an explicit `@config` at-rule, so an unreferenced file would be read by nothing.
- **MUI now.** Nothing has defeated shadcn. The protocol above states the exact condition, and
  TanStack headless is the cheaper thing to try first.
- **Removing any package.** The owner reversed slice 2's deletion recommendation
  (`2026-08-04-sync-m4-slice-2.md:506,508,576-579`).
- **A composite score, a health number, a traffic light, or a liveness dot.** Rejected on the
  merits twice by the research and once by the run-state specification
  (`2026-08-04-sync-m4-slice-2.md:63-71,540-542`). A design system is exactly the moment somebody
  reaches for a coloured badge, which is why it is named here.
- **Colouring the provenance rung.** Architectural decision 3.
- **Animating the node sequence, or any liveness pulse.** *Where motion earns its place*.
- **A custom typeface or a webfont.** The system sans is the correct choice
  (`dataviz/references/palette.md`, *Typeface & figures*), and a webfont buys a network request, a
  flash of unstyled text and a licence question for a console nobody outside the project has opened.
- **A frontend test runner.** Slice 2 defers it with a named condition — a console screen needing
  logic that cannot live in a Python view model
  (`2026-08-04-sync-m4-slice-2.md:520`) — and a design system is tokens and classes, which a test
  runner does not usefully assert.
- **Replacing shadcn, or adopting a second component catalogue.** shadcn is copy-in source in
  `web/src/components/ui/`; the design system re-themes it through tokens, which is the whole point
  of that distribution model.
- **Icons everywhere.** `lucide-react` gets exactly one job in this slice: the icon half of the
  icon-plus-label status rule. Decorative icons on every heading are the reflex the `slop` rule set
  catalogues (`impeccable-interface-quality.md:132-141`).
- **A bento grid or a hero section.** A console has neither.
- **Re-fixing anything slice 2 closed.** `e13abce`, `0f02fb3`, `1464612` landed after the ledger
  entries that named them.

---

## The five questions, and how each was settled

Ruled 2026-08-05 by the controlling session, under `.claude/rules/autonomous-development.md`.
None of the five is one of the three things that rule reserves for the human: none is an
irreversible action outside the repository, none invalidates the plan's architecture, and none
needs a credential or a spend. Each is recorded here rather than in a transcript so an agent
arriving cold reads a decision instead of a question. **Every one of them is reversible at the
cost of one fix round**, and the token layer is deliberately structured so that reversing the
biggest of them touches one declaration rather than every component.

**1. Dark mode ships, in Tasks 1 and 2 together.** An operator console is read all day beside a
terminal, and the argument for deferring was cost rather than doubt. The plan's own escape hatch
is the reason the cost is bearable: Task 1 defines both columns whatever the answer, because
deriving the dark ramp is the expensive part and typing it is not.

**2. Sync's hue is a blue-violet at roughly 265°**, and the ramp is generated from it rather than
approved by eye. The reasoning is a constraint rather than a taste:

- The reserved status palette occupies the warm and green arc — good, warning, serious, critical
  land between about 30° and 145°. A brand hue inside that arc collides with a verdict, and this
  console's whole position is that it does not paint verdicts it cannot support.
- Under both protanopia and deuteranopia, 265° stays separable from every one of those four. A
  teal or cyan brand would not; it collapses toward "good" for a substantial share of readers, and
  the brand hue marks the *current node*, which is a position and not a judgement.
- It is not the default blue of every developer tool, which matters for a product whose argument
  is that it is not the same thing as the tools it replaces.

The hue is the input. `--color-primary` and the focus ring derive from it, and nothing else in the
console is chromatic on a normal screen. Reversing this ruling means regenerating one ramp.

**3. The reversal is confirmed: the packages stay installed and unimported, and their retiring
conditions stand as written.** `@react-three/fiber`, `@react-three/drei`, `three` and
`react-grid-layout` are wanted in the sense the owner meant — the project is not committing to a
plain interface, and nothing is uninstalled. What does not follow is building either now. This
plan already declined 3D on the merits (occlusion makes "every affected call site is shown"
unprovable, which is the one claim a spatial view would exist to make) and declined the draggable
dashboard on the grounds that a first version is what teaches a user what they want on screen.
Slice 2's question 4 is closed by this paragraph: the two plans do not contradict each other, they
answer different questions. Keeping a package for a condition that has not yet been met is not the
same as declining the capability.

**4. Body text is 14px.** Rows per screen is this console's currency and the plan's own
recommendation is sound. The `meta` step at 12px is a floor and not a suggestion; nothing renders
below it.

**5. Assume yes — somebody other than the owner opens this console this quarter.** The dogfooding
milestone makes the console the instrument through which the backend is exercised, and the product
position makes it the thing anyone is shown first. So Tasks 5 through 7 are worth doing now rather
than deferred, and the slice runs to its full eight tasks.

---

## Verification

- **Web:** `npm run build` clean and `npm run lint` with no new error-level violations after every
  task. There is no frontend test runner (`web/package.json:6-11`), so every other claim below is a
  human observation, recorded in the report with what was seen — the standard slice 1 and slice 2
  both work to.
- **The palette is proven able to fail:** re-run the validator against `DESIGN.md`'s hex list,
  confirm it is clean, then move one categorical slot next to its neighbour and watch the CVD check
  FAIL. Revert.
- **Contrast did not regress:** every text-on-surface pairing computed in both modes, none below
  the current worst case of 5.05:1.
- **The two measured defects are closed:** the type range ratio is at least 2.0:1, and no page's
  heading outline skips a level.
- **The Rung column is visible at 1280px** on the vendor findings table without a sideways scroll.
- **Reduced motion is respected:** with `prefers-reduced-motion: reduce`, the console is entirely
  still.
- **No status is colour-alone:** with colour disabled, every status still reads.
- **A full walk of Codebase → API Services → Errors & Incidents → Finding → Solution Workflow, in
  both themes, leaves the browser console empty** (`impeccable-interface-quality.md:354-362`).

### Where I could not verify

- **`react-grid-layout` 2.2.4 and `@react-three/fiber` 9.7.0 against React 19.2.8 at runtime.**
  Both are installed and neither is imported, so nothing exercises them; `npm run build` does not
  typecheck an unimported package's peer requirements. If either is ever used, that is the first
  thing to check.
- **The real cardinality of `strategy` and `tier` in `migration_outcome`.** I read the schema
  (`src/sync/graph/schema.sql:176-235`) but did not query a database, so Task 7's chart-versus-table
  choice for those two dimensions is genuinely open until somebody counts.
- **Whether Impeccable is installed on this machine.** `impeccable-interface-quality.md` records
  running it during the audit, but I did not check for it in this worktree. Task 8 step 3 is
  conditional for that reason.
- **The 12.8px figure in the measured type range** is `text-[0.8rem]` on `Button`'s `sm` size
  (`button.tsx:29`), which is used at `page-controls.tsx:32,40`, `error-surface.tsx:84` and
  `workflow-page.tsx:68,109`. I did not re-run the detector to reproduce the 1.5:1 measurement
  myself; it is taken from `impeccable-interface-quality.md:279-287`, which states it was
  reproduced against a fixture.

# The rail behaves — what expands, which fill says which tier, and where the deep levels lead

Task 5 of `docs/superpowers/plans/2026-08-07-console-fidelity-pass.md`. Work item M7-W199.

`reports/2026-08-07-console-fidelity-gaps.md` Surface 2 measures three defects, all of them
behaviour rather than arrangement. The rail is 40px and fixed, so six areas are six permanently
unlabelled glyphs and `[data-collapsible]` counts zero. The rail's active fill and the contextual
sidebar's active fill both resolve to `oklch(0.95 0.00275 159 / 4.93%)`, so two tiers are marked
with one value and which tier you are reading is carried by position alone. And on the finding,
workflow and pull-request routes every second-tier row is a `<span>` rather than an `<a>` — the
sidebar stops being navigable exactly where the hierarchy is deepest.

The fourth row of that surface has nothing measured against it yet: NOTES entry 6's mechanical test,
that an icon must not move vertically across a collapse. It becomes live here, because until now
there was no collapse.

## What changes

| Piece | Before | After |
|---|---|---|
| Rail width | `w-10`, 40px, fixed | 48px at rest, 208px while hovered or focused — the vendored primitive's own `--sidebar-width-icon` and `--sidebar-width` |
| Rail labels | `aria-label` only; a tooltip on hover | the label renders beside the icon while expanded; the tooltip stays and the primitive hides it whenever the rail is not collapsed |
| Rail rows | a hand-rolled `<ul>`/`<li>` of `size-8` boxes | `SidebarMenu` / `SidebarMenuItem` / `SidebarMenuButton` from the vendored primitive |
| Rail expansion | none | our `onMouseEnter` / `onMouseLeave` / focus handlers call the primitive's `setOpen` |
| Rail active fill | `--color-surface-emphasis` | `--color-surface-scope`, a new declared value |
| Sidebar active fill | `--color-sidebar-accent`, the same alpha as above | unchanged |
| Second-tier rows | `<span>` whenever the route declares a parameter | `<a>` whenever the current address supplies every parameter that route needs |
| Settings | pinned last by `mt-auto` | unchanged — the gap report records our pinning as a deliberate divergence from Studio, and it stays |

## The two active values, and why the new one goes to the rail

The surface ramp's two state steps are foreground overlays at `--surface-overlay-unit × ratio`,
with ratios 1 (a row under the pointer, 3.2895%) and 1.5 (a row that is selected, 4.9342%). The
depth ramp beside it runs 1, 1.5 and 2. The third state step is therefore not an invented value: it
is ratio 2 of the arithmetic already published, `oklch(0.95 0.00275 159 / 6.579%)`, and it
composites to `#212322` over the page plane the rail sits on.

It goes to the **rail**, and the sidebar keeps the value it has, for three reasons.

**The two marks do not mean the same thing.** The rail marks the scope the address is *inside*; the
sidebar marks the page the address *is*. A scope contains a page, so it is the outer and
longer-lived mark, and it is the one that has to read at a glance from a 48px column. Giving the
outer mark the stronger fill puts the ramp in the same order as the containment.

**The sidebar row already has three other channels and the rail item has one.** A current sidebar
row carries `aria-current="page"`, a weight step to 500, and full-strength ink beside its icon and
its label. A collapsed rail item carries a fill and a glyph. Spending the extra contrast where the
other channels are absent is where it buys the most.

**One new value, one consumer, one meaning.** Every other selected row in the console — table rows,
menu items, the command palette — resolves `--color-accent` or `--color-surface-emphasis`, and
moving *that* would have restyled all of them to fix a defect in the rail. `--color-surface-scope`
has exactly one consumer and says exactly one thing.

The alternative considered and rejected: give the rail an opaque depth step such as
`--color-secondary`. `DESIGN.md`'s surface-ramp section already argues against it — an opaque state
step was the old ramp's defect, invisible on a card and correct only on the page — and the rail
would have been the one place in the console where state is not an overlay.

## The second-tier link audit, route by route

A destination becomes a link when the current address supplies every parameter its path declares.
The address is the only honest source: `/findings/f-1/workflow` binds `findingId`, and the three
Remediation destinations all need exactly that one parameter, which is why the deepest area is the
one this fixes most.

| Area | Destination | Parameters | Linked at | Still a `<span>` at |
|---|---|---|---|---|
| Fleet | `/` | — | every address | nowhere |
| Codebase | `/repositories/:repoId` | `repoId` | `/repositories/:repoId`, `/repositories/:repoId/observed` | every other address |
| API services | `/vendors/:vendorId` | `vendorId` | `/vendors/:vendorId`, `/bindings/vendors/:vendorId/operations/:operationId` | every other address |
| Signals | `/repositories/:repoId/observed` | `repoId` | `/repositories/:repoId`, `/repositories/:repoId/observed` | every other address |
| Observe | `/bindings/vendors/:vendorId/operations/:operationId` | `vendorId`, `operationId` | `/bindings/vendors/:vendorId/operations/:operationId` | every other address, **including `/detectors`** |
| Observe | `/detectors` | — | every address | nowhere |
| Remediation | `/findings/:findingId` | `findingId` | all three finding addresses | every other address |
| Remediation | `/findings/:findingId/workflow` | `findingId` | all three finding addresses | every other address |
| Remediation | `/findings/:findingId/workflow/pull-request` | `findingId` | all three finding addresses | every other address |

Two things that table settles rather than leaves to the next reader.

**The binding surface is the one destination that legitimately keeps its `<span>` on a sibling
address.** Standing on `/detectors`, the Observe sidebar holds two rows; `/detectors` links to
itself and the binding surface cannot, because no vendor and no operation are in the address and
there is no sibling destination at that depth to borrow them from. That is the plan's "record it as
a ruling rather than forcing a link" case, and forcing one would produce
`/bindings/vendors//operations/`.

**Where a row stays unlinkable it keeps `reachedFrom`, and where it becomes a link it drops it.**
`— reached from a call site on a vendor or binding surface` is a sentence about where to find a
subject. Rendering it beside a working link would be telling a reader to go and look up something
they are already standing on. Neither string is one of the twenty-four protected sentences; both
were added by M7-W171's own pass, and the sentence still renders on every row where it is true.

## Rulings

**1. The vendored primitive ships no `expandable` mode, and consuming what it does ship is not
forking it.** The gap report's citation is `Sidebar.tsx:85-90`, which is Studio's *application*
layer — an `onMouseEnter` calling the primitive's `setOpen`, with a three-way behaviour preference
stored in local storage. `web/src/vendor/supabase/ui/sidebar.tsx` carries the state machine that
sits underneath: the provider's open state, `--sidebar-width` and `--sidebar-width-icon`,
`data-state` and `data-collapsible`, and `SidebarMenuButton`'s collapsed geometry. We layer the
same `onMouseEnter` at our own layer, exactly as Studio does at its. **No byte of the vendored file
changes.** The behaviour preference and its storage key are not adopted: three modes and a
persisted default is a control we would have to build a home for, and hover-expand is the whole of
what the gap report asked for.

**2. The rail keeps its own positioned wrapper rather than rendering `<Sidebar collapsible="icon">`
directly.** The primitive's non-`none` branch positions its panel absolutely against a spacer that
takes its height from a stretched flex parent. Our chassis row is `items-start` and both tiers are
`sticky top-12` at a viewport-derived height, so that branch resolves to zero height here. The
contextual sidebar already takes `collapsible="none"` for the same reason and supplies its own
sticky box; the rail now does the same and carries the primitive's `data-state` and
`data-collapsible` on the box it supplies, which is what the primitive's own descendant classes read.

**3. The expanded rail overlays the sidebar; it does not displace it.** The primitive's
`overflowing` variant is this shape — the box stays at icon width in flow while the panel grows
over what is beside it. Displacing would push the contextual sidebar and the entire content column
160px sideways every time a pointer crossed the rail, which is a worse defect than the one being
fixed.

**4. The width change is not animated.** `tests/test_console_design_tokens.py`'s geometry guard
bans `transition`, `transition-all`, `transition-transform` and `transition-shadow`;
`transition-[width]` would slip past the pattern and still be the thing the guard exists to stop.
The rail snaps between the two widths.

**5. The icon-position property is tested structurally in vitest and measured in Chrome.** jsdom has
no layout — `getBoundingClientRect` returns zeroes, which is why `app-frame.test.tsx`'s own docstring
already refuses to assert on them. What the vitest holds is the structural cause: the rail's flow
sequence is element-for-element identical between the collapsed and expanded states, so nothing can
appear above an icon in one state and not the other. A `SidebarGroupLabel` is precisely that defect
— it is `h-8` expanded and `-mt-8 opacity-0` collapsed — and the test was shown red against a
variant that added one. The pixels are read in Chrome at 1440×900 and 1280×800.

**6. One prior assertion is rewritten rather than extended.** `app-frame.test.tsx`'s *carries where
a subject comes from on the routes that need one* asserted `href === null` for every route declaring
a parameter, rendered at that route's own address. That is the defect this task fixes stated as a
guarantee, so extending it was not available. The replacement keeps both halves of the claim and
splits them by the condition that actually governs: a row whose subject the address supplies is a
link with no `reachedFrom`, and a row whose subject it does not is unlinkable and says where to go.

**7. The rail's rest width moves 40px → 48px.** That is the primitive's `SIDEBAR_WIDTH_ICON`, and
nothing in `DESIGN.md` or the token tests declared 40 — the old value was spelled `w-10` inline.

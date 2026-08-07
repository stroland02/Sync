# M7-W164 — the Binding surface and Vendor levels onto the chassis, measured

Every number here came from Chrome against a running console on a free port, reading
`getComputedStyle` and `getBoundingClientRect` over the live document at `--scale 10000`. The seed
holds 2,500 call sites on `seed-console-scale-stripe/PostCharges` and 2,500 open findings on the
vendor. Nothing below is derived from markup, and nothing is estimated.

## How each figure was taken, because two of them are easy to take wrongly

**Content width** is `main`'s client width less its own padding — the same box B115 reads, so the
tables below compare directly with it. **Table width** is the width granted to the table's own
scroll container. Before this item the two differed by 32px, because a `Card` sat between them; they
are now the same number, and that is the single most consequential thing measured here.

One column in the tables below is arithmetic rather than a reading, and it is marked here rather than
left to be assumed: the **before** table widths are content width less 32px. `CardContent` is
`px-(--card-spacing)`, `--card-spacing` defaults to `--spacing-section`, and that token is 16px — so
the subtraction is read off the stylesheet, not guessed. Every **after** figure, and every content
width in either column, was read from the live document.

**Row height** is the modal height over the fifty body rows on the page. One row in each set
measures a pixel taller than the other forty-nine — a border that lands on a half pixel — so a mean
would report a height no row has.

**Whether the rung column is visible without a sideways scroll** is read from the table's *own*
scroll container, plus the document's. It is deliberately not read from an ancestor: an ancestor with
`overflow: visible` reports a sibling's overflow as its own `scrollWidth`, and the first version of
this check called the screen broken because the prefix-filter input group is inset by 4px three
regions above the table. That inset predates this item, is clipped, and the document does not scroll
at any measured width.

**Regions placed beside another** counts containers holding at least two children that overlap
vertically and are horizontally disjoint, each at least 120x60 — the floor is what separates a region
from a row of chips. The same definition was run before and after.

## The binding surface

Sidebar states are named the way B115 names them: both viewports load collapsed, because the
auto-collapse threshold is 1473px.

| | content | table | call site column | row |
|---|---|---|---|---|
| 1440, collapsed *(the default here)* | 1297 → **1297** | 1265 → **1297** | 281 → **292** | 57 → **57** |
| 1440, expanded | 1137 → **1137** | 1105 → **1137** | 231 → **241** | 77 → **77** |
| 1280, collapsed *(the default here)* | 1137 → **1137** | 1105 → **1137** | 231 → **241** | 77 → **77** |
| 1280, expanded | 977 → **977** | 945 → **977** | 181 → **191** | 77 → **77** |

**1280 is still 77px, and it will be until something other than width changes.** B115 said it would
be and explained why; this item did not set out to fix it and did not.

What did move is the threshold, and it moved because it was never a property of the frame. Stepping
the viewport in 1px increments with the sidebar collapsed:

| table width | row |
|---|---|
| 1137px *(1280 viewport, collapsed)* | 77px |
| **1138px** *(1281 viewport)* | **57px** |
| 1141px | 57px |
| 1157px | 57px |

So the row falls at 1,138px of table width, and 1280 grants 1,137px. **The screen is one pixel
short.** Before this item it was 33px short, because the card's padding was inside the budget.

That is a finding, not a fix, and B115 stays open on its original condition. A threshold cleared by a
single pixel against one fixture is a coincidence: the entry already requires a second fixture whose
repository ids and argument-key lists are visibly longer than this one's, and a one-pixel margin does
not survive that.

## The vendor level

| | content | table | call site column | row |
|---|---|---|---|---|
| 1440, collapsed | 1297 → **1297** | 1265 → **1297** | 722 → **752** | 57 → **57** |
| 1280, collapsed | 1137 → **1137** | 1105 → **1137** | 573 → **603** | 77 → **77** |

The findings table's row height is set by its path column rather than by nine columns competing, so
30px of extra width does not move it. It was not expected to.

## Type range, and the bar

| route | before | after | bar |
|---|---|---|---|
| Binding surface, 1440x900 | 24 ÷ 12 = **2.00** | 48 ÷ 12 = **4.00** | 3.4 |
| Binding surface, 1280x800 | **2.00** | **4.00** | 3.4 |
| Vendor, 1440x900 | **2.00** | **4.00** | 3.4 |
| Vendor, 1280x800 | **2.00** | **4.00** | 3.4 |

The widest text on both routes, before and after, is the page title — not a figure. That is the
condition the flat-console report attached to this bar, and it holds here because neither screen
gained a stat tile: the largest thing on screen is the thing the screen is about.

The middle of the ramp moved too. Section headings were `--text-emphasis` (16px, "card titles, panel
headlines") and are now `--text-section` (18px, which `DESIGN.md` assigns to "a section heading
inside a view"). No token was added and none was reached for outside its declared job.

## Rung visibility, and regions beside another

| | rung visible without a sideways scroll | regions beside another |
|---|---|---|
| Binding surface, 1440 collapsed | yes → **yes** | 1 → **2** |
| Binding surface, 1440 expanded | yes → **yes** | 1 → **2** |
| Binding surface, 1280 collapsed | yes → **yes** | 1 → **2** |
| Binding surface, 1280 expanded | yes → **yes** | 1 → **2** |
| Vendor, 1440 collapsed | yes → **yes** | 1 → **2** |
| Vendor, 1280 collapsed | yes → **yes** | 1 → **2** |

The rung column is a pass/fail rather than a number and it passes everywhere, at both widths and both
sidebar states. On the vendor findings table it stays ahead of the call site, which is the layout
constraint the protected `sideways scroll` comment holds and the reason it is written down: the call
site is the widest cell in that table and no fixture here is long enough to prove it.

The second beside-placement on each route is the header with the fact list beside it. The first, on
both routes before and after, is the control bar's scope selector beside its path filter.

## What was decided rather than asked, and can be reversed

**No stat-tile row on either screen.** The presence bar asks for a region beside another, which the
header-and-facts arrangement satisfies at zero vertical cost. A tile row would have cost roughly a
hundred pixels above the fold on the console's densest screen, and every count it would have carried
is already rendered — per repository in the facet chips, and against the total in the footer bar.

**The cards are gone from both screens.** They cost 32px of the scarcest resource on the binding
surface, which is the one table in the console where 32px changes a row's height. The regions are
separated by their headings and by the rule each footer bar draws under itself.

**The shared-directory note stays above the table** rather than moving into the footer bar's `left`
slot, which that component's docstring offers it. A reader meets that sentence to understand a column
they are about to read; under the table it would arrive after the reading it exists to make possible.
The footer bar's `left` carries the two-meanings sentence on the binding surface and the
filtered-total caveat on the vendor findings table, both of which qualify the count beside them.

**One `ControlBar` survives and it is `layouts/control-bar.tsx`.** The one in `components/filters.tsx`
carried no facet behaviour — the narrowing lives in `FacetChips` and `PrefixFilter`, which stay — and
the layout component is the same row plus a slot for one primary action. It is deleted rather than
deprecated. No backlog entry had been filed against the collision, so there was none to close.

**`routeQuestion` was added to `web/src/lib/routes.ts`**, which is outside the two feature directories
this item owns. A screen has to get its header sentence from the registry rather than restate it, and
the registry is where a lookup over the registry belongs. It is additive, at the end of the file, with
its guard in a new test file rather than in the shared `routes.test.tsx`.

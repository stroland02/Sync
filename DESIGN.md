# Sync console — design system

Every value here lives in `web/src/index.css`. This document says what each one is *for*, and
carries the arithmetic that proves the colour is safe. Read it before adding a token, before
choosing a colour, and before writing a size that is not on the scale.

The test of whether a decision belongs here: **if two agents building two different screens could
reasonably choose differently, and the difference would be visible, it is a token.** If they could
not, it is a class.

**Dark-only as of 2026-08-05.** The owner's instruction was explicit: "remove light and dark mode,
we only want dark mode." The light column that used to sit beside every value below is deleted, not
hidden — every table here now carries the one column that survives. Where a fact in this document
used to be argued from a light-mode measurement and that measurement has no dark-mode equivalent on
record, this document says so rather than inventing a replacement number. `web/src/lib/theme.ts`,
`theme-toggle.tsx`, the `sync-theme` `localStorage` key, and the `prefers-color-scheme` listener
that resolved a `"system"` preference are removed with it — see *How the theme is wired* below for
what replaced the mechanism.

---

## The rules that outrank taste

These are constraints, not preferences. A change that breaks one of them is wrong even if it looks
better.

**Nothing on screen may assert what the data does not hold.** Colour claims a judgement, motion
claims a time, depth claims a relationship. Three channels may carry a claim, because the data
holds one: the run outcome, the error state, and absence. Everything else is neutral ink.

**Status is not identity.** The four status colours mean good, warning, serious and critical. A
run's *disposition* — applied, abandoned, verified — is identity, and identity takes the series
palette. Painting `abandoned` red says the run went wrong; it did not, and its reason is where
routing learns which change kinds are not mechanically safe.

**A status colour never travels alone.** It ships with a `lucide-react` icon and a word, always —
colour alone is not a safe channel for a colour-blind reader, whatever its contrast measures. In
the surviving dark palette all four marks in fact clear 3:1 against the card (good 5.34, warning
9.77, serious 6.80, critical 3.73 — see *Non-text, against the 3:1 floor* below), so the pairing is
not optional because of contrast arithmetic here; it is not optional because colour is never the
only channel. (The retired light column had `--color-warning` and `--color-serious` below 3:1
against the card, which is the historical reason this rule was first written down. That number's
provenance is the deleted light column and is not restated.)

**The provenance rung stays monochrome.** `static` / `resolved` / `observed` / `unresolved` /
`unattributed` is an evidence-class scale, not a good-to-bad one. Colouring it smuggles back the
scalar confidence score this project rejected twice. If the rung ever takes colour it takes a
single-hue ordinal ramp with no good end, never the status hues.

**Mono means the system recorded this verbatim.** File paths, finding ids, node names, vendor
operations, compiler output, counts. Sans is prose. That distinction is doing real work: it tells a
reader which strings came from the graph and which came from us. Mono also supplies column
alignment for numeric columns, so no `tabular-nums` is needed while numbers stay mono — a
proportional-sans number column would need it.

**12px is a floor, not the small end of a range.** Nothing renders below `--text-meta`. Being on
this ramp does not exempt a value from Impeccable's `undersized-ui-text`, whose own 11px floor
covers `td`, `th`, and anything classed `meta`, `label` or `badge`, and whose docstring records a
build that shipped its whole furniture layer at 8px and was waved through because 8px was on the
project's ramp. No `text-[10px]`, ever, including the next time a table gets crowded.

**Whitespace is what is being spent, not what is being bought.** An operator reads this console all
day and the screens are tables of evidence; every unit of vertical space is a row that fell off the
viewport. Contrast carries hierarchy. Space separates only two things a reader must not confuse.
What grows is the *range* — the page title, the value-versus-label distinction — not the average.

---

## Colour

### The neutral ramp — nine steps

Achromatic on purpose. The brand hue is the only chromatic thing on a normal screen, and a tinted
neutral would make that sentence false by degrees.

The steps are ordered back to front: surface, then line, then ink. **A raised surface is lighter
than the plane behind it**, which is why `--color-surface` is lighter than `--color-surface-sunken`.

| # | Token | Job | Value |
|---|---|---|---|
| 1 | `--color-surface-sunken` | depth: the page plane, behind everything | `oklch(0.155 0 0)` `#0c0c0c` |
| 2 | `--color-surface` | depth: a card, a panel, a chart's plotting area | `oklch(0.205 0 0)` `#171717` |
| 3 | `--color-surface-subtle` | state: a row under the pointer; also a `<pre>` and a muted fill in the shadcn catalog — see *Surface ramp: depth and state* | `oklch(0.255 0 0)` `#232323` |
| 4 | `--color-surface-emphasis` | state: a row that is selected — see *Surface ramp: depth and state* | `oklch(0.305 0 0)` `#2f2f2f` |
| 5 | `--color-line` | the hairline: dividers, card rings, table rules | `oklch(0.345 0 0)` `#393939` |
| 6 | `--color-line-strong` | the boundary of a control, which must clear 3:1 | `oklch(0.578 0 0)` `#7a7a7a` |
| 7 | `--color-ink-muted` | metadata, `<dt>` labels, timestamps, the absence marker | `oklch(0.715 0 0)` `#a3a3a3` |
| 8 | `--color-ink-secondary` | prose that is not the headline value | `oklch(0.83 0 0)` `#c7c7c7` |
| 9 | `--color-ink` | the primary ink | `oklch(0.955 0 0)` `#f0f0f0` |

This ramp was **re-stepped against the dark surface**, not produced by inverting the light ramp the
console shipped before 2026-08-05. An inverted ramp puts the wrong lightness against the wrong
surface and the contrast arithmetic stops holding; the values above are the ones separately verified
to hold, not a mirror of the retired light-mode values.

`ABSENT` — the console's one absence marker — wears `--color-ink-muted`. One glyph, one appearance.

**Graphics is an allocation, not a tenth step.** Two ink levels hold for text — `ink` and
`ink-secondary` — but an icon rendered at either is optically louder than the prose it sits beside,
because a filled glyph carries more area than a stroke pattern at the same lightness. `getsentry/sentry`
keeps a separate `graphics` category for exactly this (`components/core/principles/tokens/tokens.mdx`,
"Categories": `content` is "text and icons which need to stand out the most", `graphics` is "icons and
other graphical elements which don't need to stand out as much"). `--color-graphics` names step 7 of
the ramp above — the same value as `--color-ink-muted`, `oklch(0.715 0 0)` — under its own job so an
icon reaches for it rather than for a text token. No new lightness, and the contrast already published
for `ink-muted` in *Contrast, computed* below applies unchanged: for an achromatic OKLCH colour,
relative luminance is exactly `L^3`, so contrast against a surface of lightness `L_surface` is
`(0.715³ + 0.05) / (L_surface³ + 0.05)`. Worst case is `--color-surface-emphasis` (`L` 0.305): `(0.3655
+ 0.05) / (0.02837 + 0.05) = 5.30`, above the 5.05 floor with room, and every step behind it in depth
scores higher still (surface-subtle 6.24, surface 7.09, surface-sunken 7.73). A pairing below 5.05
would be a bug in the ramp, not a trade — none is.

### Surface ramp: depth and state

The four surface steps carry two different jobs, and no step does both.

**Two steps carry depth, and a console needs no more than two.** `surface-sunken` is the page
plane; `surface` is a panel resting on it. Elevation above that is a separate mechanism — see
*Elevation* below — and it stops at two levels for the same reason.

**Two steps carry interaction state, not a third and fourth level of nesting.** `surface-subtle`
is a row under the pointer; `surface-emphasis` is a row that is selected. A row *at rest* takes its
panel's own depth step — there is no separate token for rest, because state should only spend
contrast when the pointer or a selection asks for it.

**The ban is on an ad-hoc alpha spelled at a call site, not on the alpha mechanism itself.** This
rule originally forbade an alpha overlay outright; that was broader than the evidence supports and
is narrowed here. The defect it was written against was never "alpha" as a technique — it was a
colour composited without a name, invented fresh at whichever call site needed one, so the same
declaration (`bg-foreground/10`) meant a different rendered colour depending on which depth step it
landed on, and eight feature screens held exactly one authored row interaction between them because
the ramp gave an agent no named step to reach for instead. That failure is what stays banned: no
`bg-x/10`, no `text-y/70`, spelled inline in a component.

What is not banned is a single primitive that owns every interaction state together and composites
through `currentcolor` rather than a fixed grey — `getsentry/sentry`'s `InteractionStateLayer`
(`components/core/interactionStateLayer/interactionStateLayer.tsx`) is the worked example: one
absolutely-positioned overlay, rest at `opacity: 0`, hover at 0.06, pressed at 0.09, inheriting
`border-radius` and `border` from whatever it sits inside. Because its fill is `currentcolor`, it is
always an alpha of *the ink already on the element*, not of an invented neutral — a step toward the
foreground on any surface, in any theme, at any nesting depth, one declaration with one meaning. A
sanctioned overlay of that shape must satisfy three things: it is one primitive owning every state
together, not one class per state scattered across call sites; its fill is `currentcolor`, never a
literal or a fixed neutral; and it inherits the shape of whatever it sits inside rather than assuming
a pill, a card corner or a square cell.

**This console keeps named surface steps for its own state anyway, and the reason survives the
narrower rule.** After Task 12's reallocation there are exactly two depth steps for state to land
on — few enough that a named step costs nothing extra, and a named value is greppable in a way an
overlay is not. The composition ambiguity the original ban was written against is nearly absent at
two steps. A future primitive built the `InteractionStateLayer` way remains a legitimate alternative
construction; it is simply not the one this tree has chosen.

**A panel header takes the panel's own depth step, not a background of its own.** It separates from
the body by weight and the hairline rule (`--color-line`) already kept for table rules — cheaper
than a background, and a sticky header stays legible over a scrolled body at any depth without one.
This is also what frees `surface-subtle` for state above.

**The ring stops being the default.** `--shadow-flat` is kept for a surface that must be told apart
from a neighbour drawn at the *same* depth step and nothing else separates them; it no longer
decorates every surface that sits on the page. A step already tells a panel from the page and a row
from its neighbours — see *Contrast, computed* below, none of these pairings are new.

**The ring is a shadow, not a border, for one reason: it costs no layout.** A `border` changes an
element's box, so a row that gains one shifts by a pixel relative to its neighbours above and
below. A 1px inset box-shadow occupies no space, so a row can move between rest, hover and selected
without ever nudging the rows around it.

### The brand hue

265 degrees. It sits there because the reserved status palette occupies the warm and green arc from
about 30 to 145 degrees, and a brand hue inside that arc collides with a verdict. Under both
protanopia and deuteranopia 265 stays separable from all four status colours; a teal or cyan brand
would collapse toward *good* for a substantial share of readers, and the brand hue marks the
current node, which is a position rather than a judgement.

| Token | Job | Value |
|---|---|---|
| `--color-brand` | links, focus rings, the current node | `oklch(0.775 0.113 265)` `#92b4fe` |
| `--color-brand-surface` | the tint behind a current or selected thing | `oklch(0.285 0.055 265)` `#1d2945` |

Used sparingly is part of the decision, not a note on it. Links, focus, the current node. Nothing
else on a normal screen is chromatic.

### The status palette — reserved

Four roles, and they mean what they say. Never a series colour. Never without an icon and a word.

The **mark** carries one value regardless of surface — a status colour that shifted with the theme
would be a different claim on a different screen, and the four marks were selected as a set that
stays distinct from the series slots. The **ink** and the **surface** are selected against the
surface they land on.

| Role | Mark | Ink | Surface |
|---|---|---|---|
| good | `#0ca30c` | `oklch(0.72 0.17 145)` `#54bf5c` | `oklch(0.29 0.05 145)` `#1a321b` |
| warning | `#fab219` | `#fab219` | `oklch(0.3 0.05 78)` `#3c2a0d` |
| serious | `#ec835a` | `#ec835a` | `oklch(0.298 0.05 42)` `#422419` |
| critical | `#d03b3b` | `oklch(0.72 0.155 27.5)` `#f67a6d` | `oklch(0.29 0.055 27.5)` `#43201c` |

Tokens: `--color-good`, `--color-good-ink`, `--color-good-surface`, and the same three for
`warning`, `serious` and `critical`.

**Which of the three to reach for.** Text and icons take the `-ink` step — it is the only one
computed to clear 5.05:1. A panel's tint takes the `-surface` step. The bare mark is for a chart
fill or a filled dot large enough that area carries it — never a hairline rule; a 1px rule in
`--color-warning` reads as a rumour of colour, not a border, however it measures.

`--color-destructive` is kept for the shadcn catalog and holds the same value as
`--color-critical-ink`. New code should say `critical`.

### The series palette — categorical, fixed order, never cycled

Charts only. Assigned in sequence: one series takes slot 1, four series take slots 1 to 4. A ninth
series is never a generated hue — it folds into "Other", or the chart becomes small multiples, or
it becomes a table.

| Slot | Hue | Value |
|---|---|---|
| 1 | aqua | `#199e70` |
| 2 | orange | `#d95926` |
| 3 | blue | `#3987e5` |
| 4 | green | `#008300` |
| 5 | magenta | `#d55181` |
| 6 | yellow | `#c98500` |
| 7 | violet | `#9085e9` |
| 8 | red | `#e66767` |

Tokens `--color-series-1` … `--color-series-8`.

**The order is the colour-blindness mechanism, not a preference.** Adjacent slots touch in a stack,
a bar group and a line chart, so adjacent pairs are what the gate measures. All eight orderings of
these hues were enumerated and scored with the `dataviz` skill's validator in both modes, before
this slice retired one of them; 36 clear every hard gate with the brand constraint applied. This one
was chosen among the passing orders by the skill's own tie-break — maximise the minimum adjacent CVD
ΔE — and then, among the orders tied at that maximum, by two constraints this console has and the
skill does not:

- **Slot 1 is neither blue nor violet.** Those are the two families nearest the brand hue, and slot
  1 is the colour a single-series chart wears. Violet sits at slot 7, which the "more than about
  seven meaningful classes is a table" rule makes effectively unreachable.
- **Among the remaining candidates, slot 1 is the hue furthest from any status colour.** Aqua sits
  9.8 ΔE from the nearest status colour; orange sits 5.8.

**Known adjacencies, stated rather than hidden.** Series and status are different palettes measured
against different gates, and cross-palette pairs can sit close enough to matter. The light column
carried three such measurements, naming specific ΔE distances between light-mode series hues and
the status marks. That column and those numbers are retired as of 2026-08-05, and they were never
re-run against the dark series values above, so they are not restated here. The fix does not depend
on the distance regardless: a status colour always arrives with an icon and a word, a series colour
never does, and a chart carries direct labels and a legend.

**The series cap for scatter, bubble, choropleth and small multiples is three.** In those forms any
two marks can sit side by side, so the gate is all-pairs rather than adjacent, and it is strictly
harder. The first three slots clear it (see *The validator's report* below). A four-slot run before
this slice failed against the light hex values at ΔE 3.2 (protan); that run's inputs are retired
with the light column, and the dark palette has not been separately re-run at four slots. The cap of
three is kept regardless — adding a slot only makes the all-pairs gate harder, never easier, so the
absence of a fresh failing run is not read as permission. Past three in an all-pairs form, cut
series or facet. Do not change the palette.

### Chart chrome

| Token | Job | Value |
|---|---|---|
| `--color-chart-grid` | gridlines, recessive | `oklch(0.29 0 0)` `#2b2b2b` |
| `--color-chart-axis` | the baseline and axis rule | `oklch(0.42 0 0)` `#4d4d4d` |

The chart's plotting surface is `--color-surface`. Text on a chart — values, labels, legend entries
— wears the ink tokens, never the series colour; a coloured mark beside the text carries identity.
One axis, never two. A legend whenever there are two or more series; direct labels at four or
fewer.

### The names the shadcn catalog consumes

These are positions on the ramp above, kept under their existing names because renaming one breaks
components across the tree. Prefer the ramp names in new code.

| shadcn name | Is | Value |
|---|---|---|
| `--color-background` | `surface-sunken` | `oklch(0.155 0 0)` |
| `--color-foreground` | `ink` | `oklch(0.955 0 0)` |
| `--color-card` | `surface` | `oklch(0.205 0 0)` |
| `--color-card-foreground` | `ink` | `oklch(0.955 0 0)` |
| `--color-muted` | `surface-subtle` | `oklch(0.255 0 0)` |
| `--color-muted-foreground` | `ink-muted` | `oklch(0.715 0 0)` |
| `--color-border` | `line` | `oklch(0.345 0 0)` |
| `--color-input` | `line-strong` | `oklch(0.578 0 0)` |
| `--color-ring` | `brand` | `oklch(0.775 0.113 265)` |
| `--color-primary` | `brand` | `oklch(0.775 0.113 265)` |
| `--color-primary-foreground` | reads on `brand` | `oklch(0.155 0 0)` |
| `--color-secondary` | `surface-subtle` | `oklch(0.255 0 0)` |
| `--color-secondary-foreground` | `ink` | `oklch(0.955 0 0)` |
| `--color-destructive` | `critical-ink` | `oklch(0.72 0.155 27.5)` |
| `--color-destructive-foreground` | reads on `destructive` | `oklch(0.155 0 0)` |

Three of these are a visible design decision rather than a Tailwind default: `--color-background`
sits off pure black so a card separates from the page; `--color-input` is bright enough to clear
3:1 as a control boundary; `--color-primary` and `--color-ring` are the brand hue, which is what
makes focus visible and makes the `link` button variant a link.

---

## Type

Six steps. The console previously lived at 12 / 12.8 / 14 / 16 / 18px, a measured range ratio of
1.5:1 against a 2.0 threshold; the `page` step alone takes it to 2.0.

| Token | Size | Line height | Weight | Tracking | Job |
|---|---|---|---|---|---|
| `--text-meta` | 12px | 16px | inherit | normal | labels, timestamps, furniture. **The floor.** |
| `--text-body` | 14px | 20px | inherit | normal | prose and table cells. 14 rather than 16 because rows per screen is the currency. |
| `--text-emphasis` | 16px | 22px | 600 | −0.02em | card titles, panel headlines |
| `--text-section` | 18px | 24px | 600 | −0.02em | a section heading inside a view |
| `--text-page` | 24px | 30px | 600 | −0.04em | the `h1` on every view |
| `--text-figure` | 32px | 36px | 600 | −0.04em | stat-tile values only; carries `tabular-nums` — see below |

Utilities: `text-meta`, `text-body`, `text-emphasis`, `text-section`, `text-page`, `text-figure`.
Weight, line height and tracking travel with the step, so `text-page` is the whole decision rather
than three of them. Override with `font-normal` or `leading-*` where a specific case needs it.

**Tracking is two-tiered, and it belongs to the heading role, not to size alone.**
`--text-emphasis` and `--text-section` take −0.02em; `--text-page` and `--text-figure` take
−0.04em, deepened from the −0.01em/−0.02em this console shipped with, to keep the direction
consistent — larger heading, more negative tracking — across all four steps that carry it. **The
condition:** tracking travels with these four steps because each names a heading role — a panel
title, a section heading, a page title, a stat-tile figure. If `--text-emphasis` is ever reached
for as in-row emphasis rather than a panel title, that use takes `tracking-normal` alongside it;
the tracking belongs to the heading, not to the size.

**The furniture class.** `.furniture` (`web/src/index.css`, `@layer components`) is the uppercase,
open-tracked treatment `site-nav.tsx:65` already renders by hand for its graph-level labels,
defined once so nothing else in the tree hand-spells it again. It is a class, not a token — this
document's own test says so: two agents rendering a graph-level label would both reach for
uppercase and open tracking, so there is nothing for them to choose differently. It covers **one of
`--text-meta`'s two jobs**: a scanned label — a graph-level name, a column header, a rung label —
takes it; a read value — a timestamp, a count — does not. It sets `text-transform: uppercase` in
CSS rather than in copy, because a screen reader spells out letters that are already capitalised in
a string, and the transform is a rendering choice, not a fact about the data. It is deliberately
outside the `text-*` namespace: `web/src/lib/utils.ts` teaches `tailwind-merge` exactly six
font-size names under that prefix, and an unlisted `text-*` class merges as a text-*colour*
conflict instead — the defect that file's docstring already records once, for `text-emphasis`
against `text-critical-ink`.

**Tabular figures.** `--text-figure` carries `font-variant-numeric: tabular-nums`, because every
value on that step is a number an operator compares down a column or across a poll, and
proportional digits make that comparison a guess. Mono numbers do not also take it: mono already
aligns by construction — see *Mono means the system recorded this verbatim* above — and
`tabular-nums` on a mono run would be decoration on a mechanism that already works. A sans numeric
value outside `--text-figure` — a count rendered in prose rather than a stat tile — takes the same
Tailwind utility directly; it costs nothing in the stack already shipped and does not touch the
mono rule.

Tailwind's stock steps (`text-xs`, `text-sm`, `text-lg`) still resolve — they are not removed,
because removing them would break every component mid-migration. They are not the scale. New code
uses the six above.

**Faces.** `--font-sans` is `system-ui, -apple-system, "Segoe UI", sans-serif`; `--font-mono` is
`ui-monospace, "Cascadia Code", "Segoe UI Mono", Menlo, Consolas, "Liberation Mono", monospace`. No
webfont: a webfont buys a network request, a flash of unstyled text and a licence question, for a
console nobody outside the project has opened. Large standalone numbers use the default
proportional figures.

---

## Space

Three tokens. `p-row`, `gap-field`, `space-y-section` and the rest of the spacing utilities all
take them.

| Token | Value | Job |
|---|---|---|
| `--spacing-field` | 4px | a label to its value, inside a card |
| `--spacing-row` | 8px | table cell padding |
| `--spacing-section` | 16px | between blocks inside a panel |

**Recorded decision: the 24px gap between top-level sections of a page is not a fourth token.** It
is written `gap-6` or `space-y-6` on Tailwind's base 4px scale. It stays unnamed because it is a
page-layout value used once per view, not a component value; a component reaching for it is
misusing it. A genuinely new spacing value is a decision recorded here, not a token added quietly.

**Recorded decision: these three tokens are the only spacing spellings permitted inside
`features/`.** A raw Tailwind spacing utility in a feature screen (`gap-4`, `p-2`, …) duplicates
one of these three numbers under a different name — measured on this tree at 19 token spellings
against 128 raw ones, two of them landing on the same pixel value under a different name (`gap-1`
and `gap-field` both 4px; `p-4` and `p-section` both 16px). A raw value stays legitimate only for a
page-layout number used once per view, on the grounds already argued above for the 24px section
gap — never inside a component.

**Recorded decision: each spacing level is at least twice the one below it, and the requirement
binds the three *inner* levels, not the page frame.** `--spacing-section` (16px) is already 2× of
`--spacing-row` (8px), which is already 2× of `--spacing-field` (4px) — the token ramp holds this
without a change. The level above them — the gap between panels on a page — does not: it is
`gap-6` (24px) today, the same value as the page frame, which is the sharpest defect this slice
measured: the page had one spacing level where it needed three. The between-panel gap moves to
**32px** (`gap-8`, unnamed on the same grounds as the frame) so that `32 : 16 : 8 : 4` holds the 2×
floor at every inner step.

**Recorded decision, and it reverses earlier reasoning: the page frame is not required to exceed
the between-panel gap.** A console's edge is held by the navigation rail and the header, not by the
frame — the frame does no hierarchical work here the way it does on a page with no chrome around
it. The frame stays at **24px** (`px-6`, unnamed), set to the smallest value that keeps content off
the chrome, not to a multiple of anything below it. **The frame-to-section ratio this console
adopts is 24 : 32, or 0.75 : 1** — the frame is smaller than the gap it sits outside of, and that
only holds because the nav rail and header are already saying "this is a composition," so the frame
does not have to.

---

## Row height

Three named steps, not a fourth spacing token — a row height and a spacing gap answer different
questions. The row height is chosen first, from the same scale a control already renders at; the
cell padding is *derived* from it, not the other way round.

| Step | Value | Already rendered at | Governs |
|---|---|---|---|
| `row-sm` | 32px (`h-8`) | `Button`'s default size | a compact row — a dense table, a toolbar |
| `row-md` | 36px (`h-9`) | `Button`'s `lg` size, and `--text-body` (14/20) plus `--spacing-row` (8px) top and bottom | the default table row |
| `row-lg` | 40px (`h-10`) | `TableHead` today | a header row, or a form field needing a larger target |

None of these is a new value: each is a Tailwind stock height Sync's own components already
render, named here so a future row is chosen from the scale rather than invented. `row-md` is the
existing arithmetic made explicit — `TableCell` already renders a 36px row from `text-body` and
`p-row`; it was simply never named. A control dropped into a `row-md` cell (a default 32px button)
clears the row by 2px on each side without changing the row's height — that is the property the
scale exists to protect.

---

## Radius

Two values. Everything resolves to one of them.

| Token | Value | Job |
|---|---|---|
| `--radius-control` | 6px | buttons, inputs, badges, chips |
| `--radius-surface` | 10px | cards, panels, dialogs |

Tailwind's `--radius-md` (6px) is unchanged and still resolves, because `button.tsx` reads it
through `var(--radius-md)` in an arbitrary value.

---

## Elevation

Two levels, and the mechanism at both is a ring. A console with no depth to communicate should not
paint depth, and a surface with no neighbour to be told apart from should not draw a ring either.

| Token | Is | Use for |
|---|---|---|
| `--shadow-flat` | a hairline ring in `--color-line` | a surface that must be told apart from a neighbour at the same depth step — not applied by default; see *Surface ramp: depth and state* above |
| `--shadow-float` | the same ring, plus a soft drop shadow | only something that occludes content |

There is no third level. Cards do not float above tables. Today exactly one thing in this console
floats: `ErrorSurface`, which is `fixed` over the viewport.

**A shadow token must express its colour through a colour token, never as a literal.** Tailwind
resolves a `shadow-*` theme value at build time and bakes it into the class, so a literal colour
written into `--shadow-float` would be frozen forever, immune to any value `--color-shadow` is later
given. `--color-shadow` (`oklch(0 0 0 / 0.72)`) exists for exactly this reason and has no other use.
`ErrorSurface` reads `shadow-float`, and it is wired through this indirection correctly:
`--shadow-float`'s own colour components stay `var()` references rather than literals, so each
resolves against whichever value `--color-line` and `--color-shadow` are live on the element.

---

## Motion

Two mechanisms, because two different kinds of motion need two different gates.

**The gate a new transition is checked against is frequency, not duration.** A surface the operator
crosses repeatedly takes no transition at all; a surface they meet only occasionally may take one.
This console tried two other rules first and reversed both: "no motion anywhere," measured from three
landing pages with near-zero authored interactions, and "150ms because a dense screen has many
controls," reasoned from a component-count comparison. Neither is decidable by whoever is writing a
component, and a landing page's near-zero transition count and a dense table's forty is the same rule
producing opposite numbers at two different interaction densities — not a contradiction to arbitrate.
`getsentry/sentry` writes the actual variable down directly: "frequent interactions… should avoid
animation all together" (`components/core/principles/motion/motion.mdx:39`), while the same system
publishes a 120–240ms token set and spends it on overlays, modals and toasts — interactions an
operator meets occasionally, not on every pointer move. Its own row-hover primitive,
`InteractionStateLayer`, declares no transition at all, which is why `TableRow`'s hover fill carries
none either: a row hover is the most frequent interaction in this console, crossed on every pointer
move over every table, all day. `ErrorSurface` arriving is the opposite case — rare, and where a
transition earns its place. **When adding a transition, ask how often the operator crosses this
surface, not how large the page is or how long feels right.**

`web/src/lib/motion.ts` owns the three deliberate, framer-motion-driven usages: `ErrorSurface`
arriving and leaving, the changed-under-poll wash, and the paged table container settling into
its new height. Each reads `useReducedMotion()` from that file and, under reduced motion,
substitutes a duration of `0` for its animated prop set rather than shortening it — a fade or a
colour wash that merely sped up would still be motion. This is code, not a token, because the
branch is the token: there is no CSS value that expresses "skip this prop entirely."

Everything else — every Tailwind `transition-*` and `animate-*` utility the shadcn catalog and
the console's own components use — is gated by a `@media (prefers-reduced-motion: reduce)` block
in `web/src/index.css`, sitting unlayered on purpose: `@theme` and every Tailwind utility compile
into layers, and an unlayered rule beats every layered rule regardless of specificity, so the block
wins against `transition-all` and `transition-colors` without needing `!important`. It zeroes
`transition-duration`, `animation-duration` and `scroll-behavior` document-wide — zeroed, not
shortened, matching the framer half's rule.

`Button`'s `active:not-aria-[haspopup]:translate-y-px` is deliberately left alone. A `transform` is
not a transition: it moves the element on `:active` whether or not a transition is running. With
the transition gone under reduced motion, the 1px press lands in a single frame — an instant state
change indistinguishable from any other instant style swap this query already makes (a colour, a
border), not an animation. It stays.

---

## How the theme is wired

`web/src/index.css` declares every token once, inside `@theme static` at `:root` — there is no
second column left to switch to. `web/index.html` stamps `class="dark"` on `<html>` directly in the
markup, permanently, rather than resolving it at runtime: there is no preference to read and no
flash-of-wrong-theme to beat before first paint.

The class stays for a reason that has nothing to do with switching: the shadcn catalog's own
components — `button.tsx`, `input.tsx`, `textarea.tsx`, `input-group.tsx`, none of them owned by
this document — carry `dark:`-prefixed utility classes, and `@custom-variant dark (&:is(.dark *))`
in `index.css` is what makes those classes match anything. Removing the class, or the variant,
would silently drop those components' `dark:` rules rather than remove a toggle; keeping both is
what leaves them coherent. `:is(.dark *)` matches every descendant of `<html>`, so the one class
stamped once covers the whole document.

Every value is a literal, not a `var()` reference: the chart wrapper in `echart.tsx` reads these
through `getComputedStyle`, which returns declared text rather than a resolved colour, and a
`var()` reference would come back unresolved.

There used to be a `.dark` rule here, unlayered on purpose so it would beat `@theme`'s layered
declarations regardless of specificity, overriding `:root`'s light values for every token above.
That rule is deleted along with the light values it overrode: the values it held are now the only
ones declared, at `:root`, and nothing overrides them.

The three-state theme control (`light` / `dark` / `system`), `web/src/lib/theme.ts`,
`theme-toggle.tsx`, the `sync-theme` `localStorage` key, and the `prefers-color-scheme` listener
that resolved a `"system"` preference are all removed, not merely unused — a console that still
branched on `prefers-color-scheme` anywhere would not have honoured the owner's instruction that
the console has exactly one mode.

---

## Changing a colour

1. Change the value in `web/src/index.css`.
2. Recompute every text-on-surface pairing. Nothing may fall below **5.05:1**, the console's
   measured worst case before this slice. A pairing that regresses is a bug in the ramp, not an
   acceptable trade.
3. If a series slot moved, re-run the validator against the surfaces below and paste the new
   report here.
4. If you changed the slot *order*, re-run the enumeration: the order is a gate, not a preference.

---

## The validator's report

From the `dataviz` skill, `scripts/validate_palette.js`. Surface `#171717` — the console's own
`--color-surface`, which is what a chart renders on.

```
$ node <dataviz>/scripts/validate_palette.js \
    "#199e70,#d95926,#3987e5,#008300,#d55181,#c98500,#9085e9,#e66767" \
    --mode dark --surface "#171717"

Palette (dark, surface #171717, categorical): 8 slots
  [PASS] Lightness band         all 8 inside L 0.48–0.67
  [PASS] Chroma floor           all 8 >= 0.1
  [PASS] CVD separation         worst adjacent #d95926↔#199e70 ΔE 9.4 (deutan) · tritan 8.7
  [PASS] Normal-vision floor    worst adjacent #c98500↔#d55181 ΔE 19.3 (normal)
  [PASS] Contrast vs surface    all 8 >= 3:1

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

exit 0
```

The retired light-hex run reported a contrast WARN — three slots below 3:1 against a white card,
obligating a relief channel. That finding's provenance is the light column; against the dark card
above, contrast vs surface is a clean PASS at all 8 slots and there is nothing to relieve.

### The all-pairs cap

```
$ node <dataviz>/scripts/validate_palette.js "#199e70,#d95926,#3987e5" --mode dark --surface "#171717" --pairs all
  [PASS] CVD separation         worst all-pairs #d95926↔#199e70 ΔE 9.4 (deutan) · tritan 4.0
  [PASS] Normal-vision floor    worst all-pairs #3987e5↔#199e70 ΔE 20.9 (normal)
  → ALL CHECKS PASS                                                        exit 0
```

### The validator was shown to reject

A validator that has never rejected a palette has not been shown to validate one. Slot 4 (green)
was moved to slot 2, beside slot 1 (aqua), and the run was repeated against the dark hex values.
The run failed and exited 1.

```
$ node <dataviz>/scripts/validate_palette.js \
    "#199e70,#008300,#d95926,#3987e5,#d55181,#c98500,#9085e9,#e66767" \
    --mode dark --surface "#171717"

  [FAIL] CVD separation         worst adjacent #d95926↔#008300 ΔE 2.7 (protan) · tritan 8.7
  [FAIL] Normal-vision floor    worst adjacent #008300↔#199e70 ΔE 11.9 (normal) — below 15, hard to tell apart even with full color vision
  → FAILED — fix the marked checks
exit 1
```

The change was reverted.

---

## Contrast, computed

WCAG ratios for every text-on-surface pairing, against the floor of **5.05:1** — the console's
worst case before this slice, which must not regress. Ratios computed from the sRGB values above.

| Ink | on sunken | on surface | on subtle | on emphasis | on subtle/50 over card | on subtle/50 over page |
|---|---|---|---|---|---|---|
| `ink` | 17.17 | 15.73 | 13.79 | 11.75 | 14.79 | 15.58 |
| `ink-secondary` | 11.57 | 10.61 | 9.30 | 7.92 | 9.97 | 10.50 |
| `ink-muted` | 7.75 | 7.11 | 6.23 | **5.31** | 6.68 | 7.04 |
| `brand` | 9.48 | 8.69 | 7.62 | 6.49 | 8.17 | 8.61 |

| Status ink | on its own tint | on surface | on sunken | on a 10% wash of itself |
|---|---|---|---|---|
| `good-ink` | 5.93 | 7.67 | 8.37 | 6.54 |
| `warning-ink` | 7.49 | 9.77 | 10.66 | 8.07 |
| `serious-ink` | **5.31** | 6.80 | 7.42 | 5.88 |
| `critical-ink` | 5.42 | 6.76 | 7.38 | 5.87 |

`ink` on each tint: good 12.16, warning 12.05, serious 12.30, critical 12.60, brand 12.66.
`brand` on `brand-surface` 7.00. `primary-foreground` on `primary` 9.48.

**The two tables above enumerate declared tokens, not rendered pixels.** Most of the console
composes exactly what they say — a solid ink on a solid surface — and for those the tables are the
whole story. But a component that blends a token through an alpha modifier (`bg-x/10`, `text-y/70`)
or inherits an ink through a wrapper renders a colour no token table contains, and only checking the
class names would miss it. The pairings below were read from a running instance — `getComputedStyle`
on the actual element, not the source — and the alpha ones were confirmed against sampled rendered
pixels, because Chrome composites `background-color` alpha in gamma-encoded sRGB, not in linear
light; blending the same two colours in linear light and gamma space gives visibly different
answers, and only the gamma one matches what the screen shows.

### Composed pairings, rendered

| Composition | Value |
|---|---|
| `ink` on `surface-subtle/50` over the card (a hovered/selected table row) | 14.80 |
| `foreground` on `input/30` (outline button, resting) | 12.09 |
| `foreground` on `input/50` (outline button, hover) | 8.70 |
| `primary-foreground` on `bg-primary` mixed 15% toward `foreground` (default button, hover) | 10.37 |
| `secondary-foreground` on `bg-secondary` mixed 5% toward `foreground` (secondary button, hover) | 12.38 |
| `critical-ink` on `bg-critical-surface` (destructive button, resting) | 5.44 |
| `critical-ink` on `bg-critical-surface` mixed 25% toward the surface extreme (destructive button, hover) | 6.02 |

Every rendered composition found still clears the 5.05 floor, and the lowest of them (5.44) sits
above the declared-token worst case below — so "worst pairing anywhere" stays true once "anywhere"
is checked against what actually renders, not assumed from it.

**The `surface-subtle/50` row above is the alpha overlay *Surface ramp: depth and state* retires,**
kept here as the measurement of what the tree renders today rather than deleted for describing a
pattern that is going away. `TableRow` still composes it; the contract's named-step replacement is
`--color-surface-subtle` at full strength, applied where Task 13 lands it, not this alpha wash.

**Two of these rows document a fix, not a finding that stood.** `button.tsx`'s `default` variant
hover was `hover:bg-primary/80` — a wash toward whatever sits behind the button — which measured
**4.49:1 on a card and 4.61:1 on the page**, both below the floor, in a variant no screen used yet.
`destructive` was worse: `bg-destructive/10` and its `/20` hover measured as low as **4.18–4.97**
depending on mode and backdrop, back when there were two modes to measure. Both were rewritten to
compose against a fixed reference — `color-mix(…, var(--color-foreground) 15%)` for `default`, and
the already-verified `critical-surface`/`critical-ink` pair for `destructive` — so the result no
longer depends on whatever the button happens to sit on. The rows above are what those variants
render now.

**Worst pairing anywhere: 5.31:1** — `ink-muted` on `surface-emphasis`, and separately `serious-ink`
on its own tint, both land here. Above the 5.05 floor, and above WCAG AA for body text. Verified,
not merely declared: the lowest composed pairing found by rendering the tree is 5.44, so 5.31
remains the true minimum. (The light column's worst case, 5.21, is retired with it and is no longer
the number this floor is checked against.)

### Non-text, against the 3:1 floor

`--color-line-strong` clears 3:1 against every surface a control sits on: 3.12–4.56. The focus ring
(`--color-ring`, the brand hue) clears it comfortably: 8.69, against `--color-surface`.

The status **marks** against the card: good 5.34, warning 9.77, serious 6.80, critical 3.73 — all
four clear 3:1 in the surviving palette. (The retired light column had warning at 1.83 and serious
at 2.64, both below 3:1 by design, which is the origin of the icon-and-word-always rule above; the
rule is kept for colour-blind readers regardless of what the surviving palette measures.)

---

## Deliberately absent

- **A sequential ramp and a diverging pair.** No chart in the plan encodes continuous magnitude or
  polarity. Adding them before a chart needs them means guessing at steps nobody will check.
- **A texture fill.** The accessibility channel for the CVD, print and `forced-colors` cases. Not
  needed while every chart carries direct labels and a table beneath it; add it with the chart that
  needs it.
- **Motion tokens.** Durations and easings live in `web/src/lib/motion.ts`, not here — see
  "Motion" above for how the reduced-motion gate splits between that file's code and a media
  query in `index.css`.
- **A composite score, a health number, a traffic light, a liveness dot.** Rejected on the merits.
  A design system is exactly the moment somebody reaches for a coloured badge, which is why it is
  named here.
- **A third elevation level, a fourth spacing value, a seventh type step.** Each is a decision to
  be argued in this file, not a value to be added.
- **A light mode.** Retired 2026-08-05 on explicit instruction. Not a placeholder for a future
  toggle — the theme resolver, its storage key and its `prefers-color-scheme` listener are deleted,
  not disabled, and a component that branches on `prefers-color-scheme` again would be a regression
  against this decision, not a new feature.

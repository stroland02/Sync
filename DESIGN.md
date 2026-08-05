# Sync console — design system

Every value here lives in `web/src/index.css`. This document says what each one is *for*, and
carries the arithmetic that proves the colour is safe. Read it before adding a token, before
choosing a colour, and before writing a size that is not on the scale.

The test of whether a decision belongs here: **if two agents building two different screens could
reasonably choose differently, and the difference would be visible, it is a token.** If they could
not, it is a class.

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

**A status colour never travels alone.** It ships with a `lucide-react` icon and a word, always. On
a light surface `--color-warning` and `--color-serious` sit below 3:1 against the card by design;
the icon-and-word pairing is what makes that legal, and it is not optional.

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

### The neutral ramp — nine steps, both modes

Achromatic on purpose. The brand hue is the only chromatic thing on a normal screen, and a tinted
neutral would make that sentence false by degrees.

The steps are ordered back to front: surface, then line, then ink. **A raised surface is lighter
than the plane behind it in both modes**, which is why `--color-surface` is the lightest value in
light mode and `--color-surface-sunken` is the darkest in dark mode.

| # | Token | Job | Light | Dark |
|---|---|---|---|---|
| 1 | `--color-surface-sunken` | the page plane, behind everything | `oklch(0.972 0 0)` `#f6f6f6` | `oklch(0.155 0 0)` `#0c0c0c` |
| 2 | `--color-surface` | a card, a panel, a chart's plotting area | `oklch(1 0 0)` `#ffffff` | `oklch(0.205 0 0)` `#171717` |
| 3 | `--color-surface-subtle` | a table header, a `<pre>`, a muted fill | `oklch(0.962 0 0)` `#f2f2f2` | `oklch(0.255 0 0)` `#232323` |
| 4 | `--color-surface-emphasis` | a hovered or selected row | `oklch(0.93 0 0)` `#e8e8e8` | `oklch(0.305 0 0)` `#2f2f2f` |
| 5 | `--color-line` | the hairline: dividers, card rings, table rules | `oklch(0.885 0 0)` `#d9d9d9` | `oklch(0.345 0 0)` `#393939` |
| 6 | `--color-line-strong` | the boundary of a control, which must clear 3:1 | `oklch(0.615 0 0)` `#848484` | `oklch(0.578 0 0)` `#7a7a7a` |
| 7 | `--color-ink-muted` | metadata, `<dt>` labels, timestamps, the absence marker | `oklch(0.485 0 0)` `#5f5f5f` | `oklch(0.715 0 0)` `#a3a3a3` |
| 8 | `--color-ink-secondary` | prose that is not the headline value | `oklch(0.4 0 0)` `#484848` | `oklch(0.83 0 0)` `#c7c7c7` |
| 9 | `--color-ink` | the primary ink | `oklch(0.2 0 0)` `#161616` | `oklch(0.955 0 0)` `#f0f0f0` |

The dark column was **re-stepped against the dark surface, not inverted from the light column**. An
inverted ramp puts the wrong lightness against the wrong surface and the contrast arithmetic stops
holding — the light ink steps and the dark ink steps are not mirror images of each other, and the
table below is why.

`ABSENT` — the console's one absence marker — wears `--color-ink-muted`. One glyph, one appearance.

### The brand hue

265 degrees. It sits there because the reserved status palette occupies the warm and green arc from
about 30 to 145 degrees, and a brand hue inside that arc collides with a verdict. Under both
protanopia and deuteranopia 265 stays separable from all four status colours; a teal or cyan brand
would collapse toward *good* for a substantial share of readers, and the brand hue marks the
current node, which is a position rather than a judgement.

| Token | Job | Light | Dark |
|---|---|---|---|
| `--color-brand` | links, focus rings, the current node | `oklch(0.475 0.19 265)` `#254fc5` | `oklch(0.775 0.113 265)` `#92b4fe` |
| `--color-brand-surface` | the tint behind a current or selected thing | `oklch(0.955 0.017 265)` `#ebf0fc` | `oklch(0.285 0.055 265)` `#1d2945` |

Used sparingly is part of the decision, not a note on it. Links, focus, the current node. Nothing
else on a normal screen is chromatic.

### The status palette — reserved

Four roles, and they mean what they say. Never a series colour. Never without an icon and a word.

The **mark** carries one value in both modes. A status colour that shifts with the theme is a
different claim on a different screen, and the four marks were selected as a set that stays
distinct from the series slots. The **ink** and the **surface** are per-mode, because text and
tints have to be selected against the surface they land on.

| Role | Mark (both modes) | Ink light | Ink dark | Surface light | Surface dark |
|---|---|---|---|---|---|
| good | `#0ca30c` | `#006300` | `oklch(0.72 0.17 145)` `#54bf5c` | `oklch(0.958 0.033 145)` `#e4f7e4` | `oklch(0.29 0.05 145)` `#1a321b` |
| warning | `#fab219` | `oklch(0.5 0.105 72)` `#875806` | `#fab219` | `oklch(0.968 0.033 85)` `#fff3dc` | `oklch(0.3 0.05 78)` `#3c2a0d` |
| serious | `#ec835a` | `oklch(0.51 0.145 42)` `#a74210` | `#ec835a` | `oklch(0.962 0.02 45)` `#ffefe8` | `oklch(0.298 0.05 42)` `#422419` |
| critical | `#d03b3b` | `oklch(0.51 0.19 27.5)` `#ba1f1e` | `oklch(0.72 0.155 27.5)` `#f67a6d` | `oklch(0.958 0.02 27.5)` `#feecea` | `oklch(0.29 0.055 27.5)` `#43201c` |

Tokens: `--color-good`, `--color-good-ink`, `--color-good-surface`, and the same three for
`warning`, `serious` and `critical`.

**Which of the three to reach for.** Text and icons take the `-ink` step — it is the only one
computed to clear 5.05:1. A panel's tint takes the `-surface` step. The bare mark is for a chart
fill or a filled dot large enough that area carries it; a 1px rule in `--color-warning` on a light
card measures 1.83:1 and is not a border, it is a rumour.

`--color-destructive` is kept for the shadcn catalog and holds the same value as
`--color-critical-ink`. New code should say `critical`.

### The series palette — categorical, fixed order, never cycled

Charts only. Assigned in sequence: one series takes slot 1, four series take slots 1 to 4. A ninth
series is never a generated hue — it folds into "Other", or the chart becomes small multiples, or
it becomes a table.

| Slot | Hue | Light | Dark |
|---|---|---|---|
| 1 | aqua | `#1baf7a` | `#199e70` |
| 2 | orange | `#eb6834` | `#d95926` |
| 3 | blue | `#2a78d6` | `#3987e5` |
| 4 | green | `#008300` | `#008300` |
| 5 | magenta | `#e87ba4` | `#d55181` |
| 6 | yellow | `#eda100` | `#c98500` |
| 7 | violet | `#4a3aa7` | `#9085e9` |
| 8 | red | `#e34948` | `#e66767` |

Tokens `--color-series-1` … `--color-series-8`.

**The order is the colour-blindness mechanism, not a preference.** Adjacent slots touch in a stack,
a bar group and a line chart, so adjacent pairs are what the gate measures. All eight orderings of
these hues were enumerated and scored with the `dataviz` skill's validator in both modes; 36 clear
every hard gate with the brand constraint applied. This one was chosen among the passing orders by
the skill's own tie-break — maximise the minimum adjacent CVD ΔE — and then, among the orders tied
at that maximum, by two constraints this console has and the skill does not:

- **Slot 1 is neither blue nor violet.** Those are the two families nearest the brand hue, and slot
  1 is the colour a single-series chart wears. Violet sits at slot 7, which the "more than about
  seven meaningful classes is a table" rule makes effectively unreachable.
- **Among the remaining candidates, slot 1 is the hue furthest from any status colour.** Aqua sits
  9.8 ΔE from the nearest status colour; orange sits 5.8.

**Known adjacencies, stated rather than hidden.** Series and status are different palettes measured
against different gates, and several cross-palette pairs sit close: in light mode slot 2 orange is
5.8 from `--color-serious`, slot 8 red is 4.8 from `--color-critical`, and slot 6 yellow is 4.8
from `--color-warning`. This is not fixed by hue avoidance and is not meant to be. It is fixed by
the rule above: a status colour always arrives with an icon and a word, a series colour never does,
and a chart carries direct labels and a legend.

**The series cap for scatter, bubble, choropleth and small multiples is three.** In those forms any
two marks can sit side by side, so the gate is all-pairs rather than adjacent, and it is strictly
harder. The first three slots clear it in both modes; the fourth does not — adding green next to
orange fails at ΔE 3.2 in light. Past three in an all-pairs form, cut series or facet. Do not
change the palette.

### Chart chrome

| Token | Job | Light | Dark |
|---|---|---|---|
| `--color-chart-grid` | gridlines, recessive | `oklch(0.925 0 0)` `#e6e6e6` | `oklch(0.29 0 0)` `#2b2b2b` |
| `--color-chart-axis` | the baseline and axis rule | `oklch(0.8 0 0)` `#bebebe` | `oklch(0.42 0 0)` `#4d4d4d` |

The chart's plotting surface is `--color-surface`. Text on a chart — values, labels, legend entries
— wears the ink tokens, never the series colour; a coloured mark beside the text carries identity.
One axis, never two. A legend whenever there are two or more series; direct labels at four or
fewer.

### The names the shadcn catalog consumes

These are positions on the ramp above, kept under their existing names because renaming one breaks
components across the tree. Prefer the ramp names in new code.

| shadcn name | Is | Light | Dark |
|---|---|---|---|
| `--color-background` | `surface-sunken` | `oklch(0.972 0 0)` | `oklch(0.155 0 0)` |
| `--color-foreground` | `ink` | `oklch(0.2 0 0)` | `oklch(0.955 0 0)` |
| `--color-card` | `surface` | `oklch(1 0 0)` | `oklch(0.205 0 0)` |
| `--color-card-foreground` | `ink` | `oklch(0.2 0 0)` | `oklch(0.955 0 0)` |
| `--color-muted` | `surface-subtle` | `oklch(0.962 0 0)` | `oklch(0.255 0 0)` |
| `--color-muted-foreground` | `ink-muted` | `oklch(0.485 0 0)` | `oklch(0.715 0 0)` |
| `--color-border` | `line` | `oklch(0.885 0 0)` | `oklch(0.345 0 0)` |
| `--color-input` | `line-strong` | `oklch(0.615 0 0)` | `oklch(0.578 0 0)` |
| `--color-ring` | `brand` | `oklch(0.475 0.19 265)` | `oklch(0.775 0.113 265)` |
| `--color-primary` | `brand` | `oklch(0.475 0.19 265)` | `oklch(0.775 0.113 265)` |
| `--color-primary-foreground` | reads on `brand` | `oklch(1 0 0)` | `oklch(0.155 0 0)` |
| `--color-secondary` | `surface-subtle` | `oklch(0.962 0 0)` | `oklch(0.255 0 0)` |
| `--color-secondary-foreground` | `ink` | `oklch(0.2 0 0)` | `oklch(0.955 0 0)` |
| `--color-destructive` | `critical-ink` | `oklch(0.51 0.19 27.5)` | `oklch(0.72 0.155 27.5)` |
| `--color-destructive-foreground` | reads on `destructive` | `oklch(1 0 0)` | `oklch(0.155 0 0)` |

Three of these changed value rather than only gaining a dark column, and each is a visible change:
`--color-background` moved off pure white so a white card separates from the page; `--color-input`
darkened to clear 3:1 as a control boundary; `--color-primary` and `--color-ring` became the brand
hue, which is what makes focus visible and makes the `link` button variant a link.

---

## Type

Six steps. The console previously lived at 12 / 12.8 / 14 / 16 / 18px, a measured range ratio of
1.5:1 against a 2.0 threshold; the `page` step alone takes it to 2.0.

| Token | Size | Line height | Weight | Job |
|---|---|---|---|---|
| `--text-meta` | 12px | 16px | inherit | labels, timestamps, furniture. **The floor.** |
| `--text-body` | 14px | 20px | inherit | prose and table cells. 14 rather than 16 because rows per screen is the currency. |
| `--text-emphasis` | 16px | 22px | 600 | card titles, panel headlines |
| `--text-section` | 18px | 24px | 600 | a section heading inside a view |
| `--text-page` | 24px | 30px | 600 | the `h1` on every view |
| `--text-figure` | 32px | 36px | 600 | stat-tile values only |

Utilities: `text-meta`, `text-body`, `text-emphasis`, `text-section`, `text-page`, `text-figure`.
Weight, line height and tracking travel with the step, so `text-page` is the whole decision rather
than three of them. Override with `font-normal` or `leading-*` where a specific case needs it.

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
paint depth.

| Token | Is | Use for |
|---|---|---|
| `--shadow-flat` | a hairline ring in `--color-line` | cards, tables, panels — anything that sits *on* the page |
| `--shadow-float` | the same ring, plus a soft drop shadow | only something that occludes content |

There is no third level. Cards do not float above tables. Today exactly one thing in this console
floats: `ErrorSurface`, which is `fixed` over the viewport.

**A shadow token must express its colour through a colour token, never as a literal.** Tailwind
resolves a `shadow-*` theme value at build time and bakes it into the class, so a literal colour
written into `--shadow-float` is frozen at its light value and the dark column never reaches it —
silently. `--color-shadow` (light `oklch(0.2 0 0 / 0.3)`, dark `oklch(0 0 0 / 0.72)`) exists for
exactly this reason and has no other use.

---

## How the two modes are wired

`web/src/index.css` declares the light column inside `@theme` and the dark column in a `.dark` rule
at the top level of the file. Two facts make that work, and both are easy to break by tidying:

**The `.dark` rule is outside every layer on purpose.** `@theme` compiles into `@layer theme`, and
an unlayered rule beats a layered one whatever the specificity — `:root` and `.dark` have identical
specificity and both match `<html>`, so the layer is the only thing deciding it.

**Every value is a literal.** A custom property whose value is `var(--x)` is substituted where it
is *declared*, so a token declared at `:root` as `var(--x)` keeps the `:root` result even on an
element where `.dark` has redefined `--x`. The two columns therefore repeat their values rather
than aliasing each other. The chart wrapper also reads these through `getComputedStyle`, which
returns declared text rather than a resolved colour.

`@custom-variant dark (&:is(.dark *))` is unchanged from slice 1 and must stay as written; the
theme resolver stamps `.dark` on `<html>`, so `:is(.dark *)` covers the document.

---

## Changing a colour

1. Change the value in `web/src/index.css`, both columns.
2. Recompute every text-on-surface pairing in both modes. Nothing may fall below **5.05:1**, the
   console's measured worst case before this slice. A pairing that regresses is a bug in the ramp,
   not an acceptable trade.
3. If a series slot moved, re-run the validator in both modes against the surfaces below and paste
   the new report here.
4. If you changed the slot *order*, re-run the enumeration: the order is a gate, not a preference.

---

## The validator's report

From the `dataviz` skill, `scripts/validate_palette.js`. Light surface `#ffffff`, dark surface
`#171717` — the console's own `--color-surface` in each mode, which is what a chart renders on.

```
$ node <dataviz>/scripts/validate_palette.js \
    "#1baf7a,#eb6834,#2a78d6,#008300,#e87ba4,#eda100,#4a3aa7,#e34948" \
    --mode light --surface "#ffffff"

Palette (light, surface #ffffff, categorical): 8 slots
  [PASS] Lightness band         all 8 inside L 0.43–0.77
  [PASS] Chroma floor           all 8 >= 0.1
  [PASS] CVD separation         worst adjacent #eb6834↔#1baf7a ΔE 9.2 (deutan) · tritan 5.8
  [PASS] Normal-vision floor    worst adjacent #eda100↔#e87ba4 ΔE 19.6 (normal)
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#1baf7a",2.82],["#e87ba4",2.69],["#eda100",2.17]]

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

exit 0
```

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

**The light-mode contrast WARN is not dismissable.** Three slots sit below 3:1 against a white
card. It obligates a relief channel — visible direct labels, or the table view staying on the page
beneath the chart. Shipping the fill with neither is a failure, not a warning.

### The all-pairs cap

```
$ node <dataviz>/scripts/validate_palette.js "#1baf7a,#eb6834,#2a78d6" --mode light --surface "#ffffff" --pairs all
  [PASS] CVD separation         worst all-pairs #eb6834↔#1baf7a ΔE 9.2 (deutan) · tritan 9.6
  [PASS] Normal-vision floor    worst all-pairs #2a78d6↔#1baf7a ΔE 24.0 (normal)
  → ALL CHECKS PASS                                                        exit 0

$ node <dataviz>/scripts/validate_palette.js "#199e70,#d95926,#3987e5" --mode dark --surface "#171717" --pairs all
  [PASS] CVD separation         worst all-pairs #d95926↔#199e70 ΔE 9.4 (deutan) · tritan 4.0
  [PASS] Normal-vision floor    worst all-pairs #3987e5↔#199e70 ΔE 20.9 (normal)
  → ALL CHECKS PASS                                                        exit 0

$ node <dataviz>/scripts/validate_palette.js "#1baf7a,#eb6834,#2a78d6,#008300" --mode light --surface "#ffffff" --pairs all
  [FAIL] CVD separation         worst all-pairs #008300↔#eb6834 ΔE 3.2 (protan) · tritan 7.6
  → FAILED — fix the marked checks                                         exit 1
```

### The validator was shown to reject

A validator that has never rejected a palette has not been shown to validate one. Slot 4 (green)
was moved to slot 2, beside slot 1 (aqua), and the run was repeated. **Both modes failed and both
exited 1.** The change was reverted.

```
$ node <dataviz>/scripts/validate_palette.js \
    "#1baf7a,#008300,#eb6834,#2a78d6,#e87ba4,#eda100,#4a3aa7,#e34948" \
    --mode light --surface "#ffffff"

  [FAIL] CVD separation         worst adjacent #eb6834↔#008300 ΔE 3.2 (protan) · tritan 5.8
  → FAILED — fix the marked checks
exit 1

$ node <dataviz>/scripts/validate_palette.js \
    "#199e70,#008300,#d95926,#3987e5,#d55181,#c98500,#9085e9,#e66767" \
    --mode dark --surface "#171717"

  [FAIL] CVD separation         worst adjacent #d95926↔#008300 ΔE 2.7 (protan) · tritan 8.7
  [FAIL] Normal-vision floor    worst adjacent #008300↔#199e70 ΔE 11.9 (normal) — below 15, hard to tell apart even with full color vision
  → FAILED — fix the marked checks
exit 1
```

---

## Contrast, computed

WCAG ratios for every text-on-surface pairing, both modes, against the floor of **5.05:1** — the
console's worst case before this slice, which must not regress. Ratios computed from the sRGB
values above.

### Light

| Ink | on sunken | on surface | on subtle | on emphasis | on subtle/50 over card | on subtle/50 over page |
|---|---|---|---|---|---|---|
| `ink` | 16.74 | 18.10 | 16.16 | 14.77 | 17.19 | 16.45 |
| `ink-secondary` | 8.46 | 9.15 | 8.17 | 7.46 | 8.69 | 8.32 |
| `ink-muted` | 5.91 | 6.39 | 5.70 | **5.21** | 6.07 | 5.81 |
| `brand` | 6.47 | 6.99 | 6.25 | 5.71 | 6.64 | 6.36 |

| Status ink | on its own tint | on surface | on sunken | on a 10% wash of itself |
|---|---|---|---|---|
| `good-ink` | 6.72 | 7.54 | 6.98 | 6.41 |
| `warning-ink` | 5.57 | 6.12 | 5.67 | 5.30 |
| `serious-ink` | 5.47 | 6.12 | 5.67 | **5.27** |
| `critical-ink` | 5.57 | 6.36 | 5.88 | 5.40 |

`ink` on each tint: good 16.13, warning 16.46, serious 16.17, critical 15.86, brand 15.86.
`brand` on `brand-surface` 6.13. `primary-foreground` on `primary` 6.99.

### Dark

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

**Worst pairing anywhere: 5.21:1**, `ink-muted` on `surface-emphasis` in light mode. Above the
5.05 floor, and above WCAG AA for body text.

### Non-text, against the 3:1 floor

`--color-line-strong` clears 3:1 against every surface a control sits on, in both modes: light
3.05–3.74, dark 3.12–4.56. The focus ring (`--color-ring`, the brand hue) clears it comfortably:
6.99 light, 8.69 dark, against `--color-surface`.

The status **marks** against the light card: good 3.35, warning **1.83**, serious **2.64**,
critical 4.80. Warning and serious are below 3:1 by design, which is why the icon-and-word pairing
is mandatory and why the mark is not a border. Against the dark card all four clear it: 5.34, 9.77,
6.80, 3.73.

---

## Deliberately absent

- **A sequential ramp and a diverging pair.** No chart in the plan encodes continuous magnitude or
  polarity. Adding them before a chart needs them means guessing at steps nobody will check.
- **A texture fill.** The accessibility channel for the CVD, print and `forced-colors` cases. Not
  needed while every chart carries direct labels and a table beneath it; add it with the chart that
  needs it.
- **Motion tokens.** Durations and easings live in `web/src/lib/motion.ts`, not here, because the
  reduced-motion gate is code rather than a value.
- **A composite score, a health number, a traffic light, a liveness dot.** Rejected on the merits.
  A design system is exactly the moment somebody reaches for a coloured badge, which is why it is
  named here.
- **A third elevation level, a fourth spacing value, a seventh type step.** Each is a decision to
  be argued in this file, not a value to be added.

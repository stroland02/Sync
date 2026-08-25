# Sync console — design system

Every value here lives in `web/src/index.css`. This document says what each one is *for*, and
carries the arithmetic that proves the colour is safe. Read it before adding a token, before
choosing a colour, and before writing a size that is not on the scale.

The test of whether a decision belongs here: **if two agents building two different screens could
reasonably choose differently, and the difference would be visible, it is a token.** If they could
not, it is a class.

**The palette, the type ramp and the radii are Supabase's, as of 2026-08-06 (M7-W170).**
`docs/superpowers/specs/2026-08-06-sync-console-supabase-substrate-design.md` §3 is the ruling and
`.claude/rules/interface-originality.md` carries the carve-out that permits it. The source is
`github.com/supabase/supabase` at `6ac0316`, Apache-2.0, with the per-file provenance in
`web/NOTICE`. What that spec asks of this document is the whole of it: the values change, the
discipline does not — every token still arrives with the arithmetic that produced it, and every
text-bearing pairing is measured rather than assumed.

**Dark-only as of 2026-08-05, and the substrate does not reopen it.** Supabase ships both themes;
only the dark values were imported. `web/src/vendor/supabase/theme.css` declares one selector,
`[data-theme='dark'], .dark`, and carries no light block — a future owner instruction starts by
regenerating from `web/scripts/theme-contrast.mjs`, not from a block already sitting in the tree.

---

## How the substrate is resolved, and why this file carries numbers

Supabase's theme is generative. `theme.css` declares **eight parameters** for `.dark`, and upstream
`packages/ui/build/css/source/semantic.css` derives every semantic colour from them in OKLCH:

| Input | Value | What it drives |
|---|---|---|
| `--hue` | 159 | the neutral ramp and the brand, locked together |
| `--chroma` | 0.005 | how far the neutrals sit off achromatic |
| `--surface` | 0.19 | the lightness of the page plane |
| `--elevation-step` | 0.025 | one level of depth, in lightness |
| `--contrast` | 0.5 | the global knob borders and inks ramp against |
| `--foreground-lightness` | 0.95 | the primary ink |
| `--muted-foreground-level` | 0.8 | the second ink, as a fraction of the surface→foreground span |
| `--tertiary-foreground-level` | 0.65 | the third ink, the same way |

**This file records the resolved literals, not the chain, and `index.css` declares them the same
way.** Two independent reasons, and both are load-bearing:

- `getComputedStyle` on a custom property returns the *declared text*, not a resolved colour.
  `components/charts/echart.tsx` reads seven tokens through it and round-trips each through a
  canvas 2D context so zrender can parse it. A `var()` reference or a relative-colour
  `oklch(from …)` comes back unresolved and the chart paints nothing.
- A contrast figure is checkable only against a number. A generative chain would move this
  document's arithmetic into a CSS file nobody measures.

**`web/scripts/theme-contrast.mjs` is the resolver and the re-measurement tool.** It carries the
eight inputs above and the derivations transcribed from upstream, and it declares each token once,
as numbers. That single declaration produces both the CSS literal it prints under
`== declarations ==` and the sRGB bytes every ratio is computed over, **so a figure in this document
cannot describe a colour different from the one `index.css` ships.** The declarations block is meant
to be pasted into `index.css` verbatim; if the two ever differ, the script is right and the
stylesheet is stale.

**What that claim covers, precisely.** Every `--color-*`, `--background-color-*` and
`--border-color-*` declaration, and every contrast figure in this document, is printed by that
script and was pasted rather than typed. **Three things are not**, and each is a length or a
constant with no arithmetic to reproduce and no contrast to measure: the type ramp (carried from
`apps/studio/styles/globals.css`), the spacing and radius values, and the two `--shadow-*`
compositions. They are argued in their own sections below.

Three derived quantities are used repeatedly and are worth naming here, because every alpha in the
palette is one of them:

```
--tone-span            = 0.95 − 0.19                     = 0.76
--surface-overlay-unit = 0.025 / 0.76                    = 3.2895%
--contrast-border      = (0.05 + 0.95 × 0.5)²            = 0.275625
```

### What was taken, and what was not

| Adopted whole | Not imported, and why |
|---|---|
| the neutral surface and ink ramp | the light theme — dark-only stands |
| the border and overlay alphas | `--info` and `--info-foreground` — no consumer in this tree |
| `--primary`, the brand scale, `--warning` and `--destructive` families | `--tertiary` (`bg-surface-400`) — no consumer |
| the compat names the vendored catalog spells | the twelve-step Radix scales and the code-block colours — no consumer |
| Studio's type ramp and `--font-weight-normal` | the two `sidebar-primary` entries — no consumer, and one of them upstream resolves to the warning colour |
| Studio's sidebar aliasing (six of eight) | the faces — identity, and excluded by the carve-out |

Four values are **deviations**, each named where it appears with both measurements: the control
boundary, the focus ring, the `serious` status role, and the series palette. Nothing else departs
from upstream.

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
the adopted palette all four marks clear 3:1 against the card (good 8.76, warning 6.56, serious
5.27, critical 4.52 — see *Non-text, against the 3:1 floor*), so the pairing is not optional because
of contrast arithmetic; it is not optional because colour is never the only channel. **The
substrate makes this rule carry more weight than it did**, because the brand hue and the `good` hue
are now one hue — see *The brand hue* below.

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
project's ramp. No `text-[10px]`, ever, including the next time a table gets crowded. **The
vendored catalog is exempt by path, not by argument** — `badge.tsx` ships a 9px label upstream, and
`tests/test_console_design_tokens.py` excludes `vendor/supabase/` from this guard for the same
reason it excludes it from the others: restyling a vendored file happens in
`web/src/components/`, never inside the vendor directory.

**Whitespace is what is being spent, not what is being bought.** An operator reads this console all
day and the screens are tables of evidence; every unit of vertical space is a row that fell off the
viewport. Contrast carries hierarchy. Space separates only two things a reader must not confuse.
What grows is the *range* — the page title, the value-versus-label distinction — not the average.

---

## Colour

### The neutral ramp — two depths, two states, three inks

Nearly achromatic. `--chroma` is 0.005 and the surfaces take half of it, so the neutrals carry a
trace of the brand hue rather than none — enough that the ramp reads as one family, far too little
to claim anything.

**The four depth steps are `--surface` plus `--elevation-step × ratio`**, and the ratios are
upstream's: 1 for a card, 1.5 for a popover, 2 for the secondary fill. A raised surface is lighter
than the plane behind it.

| Job | Token | Value | Resolved |
|---|---|---|---|
| depth: the page plane, behind everything | `--color-background`, `--color-surface-sunken` | `oklch(0.19 0.0025 159)` | `#131413` |
| depth: a card, a panel, a chart's plotting area | `--color-card`, `--color-surface` | `oklch(0.215 0.0025 159)` | `#181a19` |
| depth: something that occludes — a popover, a dialog | `--color-popover` | `oklch(0.2275 0.0025 159)` | `#1b1d1c` |
| a filled control, and the vendored `bg-overlay` | `--color-secondary` | `oklch(0.24 0.0025 159)` | `#1e201f` |

**The three state steps are foreground overlays, not three more depth steps.** Their alpha is
`--surface-overlay-unit × ratio`, tuned upstream so each matches the lightness delta of the same
elevation ratio measured on the page plane. The ratios are the depth ramp's own — 1, 1.5, 2.

| Job | Token | Value |
|---|---|---|
| state: a row under the pointer | `--color-muted`, `--color-surface-subtle` | `oklch(0.95 0.00275 159 / 3.2895%)` |
| state: a row that is selected | `--color-accent`, `--color-surface-emphasis` | `oklch(0.95 0.00275 159 / 4.9342%)` |
| state: the scope an address is inside | `--color-surface-scope` | `oklch(0.95 0.00275 159 / 6.579%)` |

> **Amended 2026-08-17 (M14-W366): the two tiers this passage argues from no longer exist.** The
> area rail is deleted and there is one sidebar. The reasoning is kept rather than rewritten because
> the *ratio* it establishes survives its subject: `--color-surface-scope` still marks the scope an
> address is inside and still sits above the selected-row step, which is now the difference between
> a repository heading and the destination row under it rather than between two tiers. What is no
> longer true is the sentence about "a 48px column with no label in it" describing a shipped
> surface — that column returns as the minimised sidebar, at the 48px this passage always assumed
> and the shipped rail never used.

**The third step was added on 2026-08-07 (M7-W199), and what it fixes is two tiers marked with one
value.** The area rail and the contextual sidebar beside it both painted their current row at
4.9342% — measured identical in the fidelity report's Surface 2 — so which of the two tiers a
reader was looking at was carried by position alone. They do not mean the same thing: the rail
marks the scope an address is *inside*, the sidebar marks the page the address *is*. A scope
contains a page, so it is the outer and longer-lived mark, and it is the one that has to read from
a 48px column with no label in it. Ratio 2 puts the ramp in the same order as the containment.

It goes to the rail rather than to the sidebar for two further reasons. A current sidebar row
already carries `aria-current="page"`, a weight step to 500 and full-strength ink beside its icon
and its label; a collapsed rail item carries a fill and a glyph, so the extra contrast buys most
where the other channels are absent. And every other selected row in the console — table rows, menu
items, the palette — resolves `--color-accent` or `--color-surface-emphasis`; moving *that* would
have restyled all of them to correct a defect in one column. `--color-surface-scope` has one
consumer, `layouts/app-frame.tsx`, and says one thing.

**This reverses the shape of the old surface ramp, and the reversal is the substrate's argument
rather than ours.** The previous ramp gave state two opaque steps because an alpha spelled at a
call site composites differently against whichever depth sits under it — one declaration meaning
several colours. That defect is real and the ban on it stands: **no `bg-x/10`, no `text-y/70`,
spelled inline in a component.** What the substrate supplies is the sanctioned alternative this
document already carved out: *one* primitive owning the state, its fill an alpha of the foreground
rather than an invented neutral, declared once and meaning one step toward the ink at any nesting
depth. An opaque step cannot do that — the old `surface-subtle` was invisible on a card and correct
only on the page. All three composites are measured below, against every depth they can land on.

| Composite | over `background` | over `card` | over `popover` | over `secondary` |
|---|---|---|---|---|
| `surface-subtle` | `#1a1b1a` | `#1f2120` | `#222423` | `#252726` |
| `surface-emphasis` | `#1e1f1e` | `#232524` | `#252726` | `#282a29` |
| `surface-scope` | `#212322` | `#262827` | `#292a2a` | `#2c2d2c` |

`surface-scope` lands on `background` in practice — `--color-sidebar` resolves to the page plane —
and only that cell is measured in Chrome. The other three are computed the same way the two rows
above it were, and are published so a later consumer on a card is not guessing.

A row *at rest* takes its panel's own depth step. There is no token for rest, because state should
only spend contrast when the pointer or a selection asks for it.

**Three ink levels, at `--surface + --tone-span × level`.** Two of them are working DOM text steps;
the third is the chart legend's.

| # | Level | Token | Value | Resolved |
|---|---|---|---|---|
| 1 | 1.0 | `--color-foreground`, `--color-ink`, `--color-card-foreground`, `--color-popover-foreground`, `--color-secondary-foreground`, `--color-accent-foreground` | `oklch(0.95 0.00275 159)` | `#edefee` |
| 2 | 0.8 | `--color-foreground-light`, `--color-muted-foreground`, `--color-ink-muted`, `--color-graphics` | `oklch(0.798 0.00275 159)` | `#bcbdbc` |
| 3 | 0.65 | `--color-foreground-lighter`, `--color-foreground-muted`, `--color-ink-secondary` | `oklch(0.684 0.00275 159)` | `#989a99` |

**The two working text levels are `ink` and `ink-muted`, and level 3 is not a third one.** A
headline value takes `ink`; everything recessive beside it — a `<dt>` label, a timestamp, a panel's
explanatory prose, an absence marker — takes `ink-muted`. That is the pair the console renders, and
it is what makes "two ink levels plus one accent" true rather than aspirational. `ABSENT` — the
console's one absence marker — wears `--color-ink-muted`. One glyph, one appearance.

**`--color-ink-secondary` changed direction under the substrate, and the ban on it did not.** It
used to sit *between* the two working levels at `oklch(0.83)`; it is now the dimmest of the three,
because the substrate's three neutral inks descend and our three names map onto them in order of
role prominence. Its one consumer is unchanged: `corpus-chart.tsx` spends it on a chart legend's
`textStyle`, resolved through `getComputedStyle` in `echart.tsx`, painted inside a canvas, never
composing against DOM text on the same surface. **Reaching for it as a `text-` class is what a third
grey looks like when it arrives**, and it arrived twice — `run-outcome.tsx` on the two screens
carrying the densest evidence, and `filters.tsx` on the active-filter *value*, where at the old
value it also made the value barely brighter than the word naming it. Both were corrected on
2026-08-06 (`M4.5-W142`). `tests/test_console_design_tokens.py` holds the class ban rather than the
token, so a chart resolving level 3 keeps working and a component cannot spend it on DOM text.

**Graphics is an allocation, not a fourth level.** An icon rendered at a text ink is optically
louder than the prose it sits beside, because a filled glyph carries more area than a stroke
pattern at the same lightness. `getsentry/sentry` keeps a separate `graphics` category for exactly
this (`components/core/principles/tokens/tokens.mdx`). `--color-graphics` names level 2 under its
own job so an icon reaches for it rather than for a text token. **Declared ahead of its first
consumer**, deliberately: the console has shipped no icon for it to colour, and the allocation
exists so the first one reaches for `graphics` on day one instead of borrowing `ink-muted` and
leaving a second migration to do later. The retiring condition is that first icon.

### Boundaries

| Job | Token | Value | Against the four depths |
|---|---|---|---|
| the hairline: dividers, card rings, table rules | `--color-border`, `--color-line` | `oklch(0.95 0.001485 159 / 7.5125%)` | 1.19 – 1.23 |
| the boundary of a control | `--color-input`, `--color-line-strong`, `--color-border-control` | `oklch(0.578 0.00275 159)` `#787a79` | 3.79 – 4.27 |
| the edge of an occluding surface | `--color-border-overlay` | `oklch(0.95 0.001375 159 / 13.3713%)` | 1.41 – 1.47 |
| a boundary that must be seen against an overlay | `--color-border-stronger` | `oklch(0.95 0.001375 159 / 17.4031%)` | 1.62 – 1.67 |
| the focus ring | `--color-ring` | `oklch(0.76 0.15 159)` | 8.10 – 9.12 |

A hairline divider carries no 3:1 obligation and never has — WCAG 1.4.11 covers what is *required
to identify a component or its state*, and a rule between two table rows is neither. The previous
palette's `--color-line` measured 1.55 against the card and this document never claimed otherwise.

> **Deviation 1 — the control boundary.** Upstream derives `--input` as the foreground at
> `3% + 38% × --contrast-border` = 13.47% alpha, which composites to **1.43 – 1.47** against the
> four depth steps. This contract requires a control boundary to clear **3:1**, and that
> requirement is the older of the two. The declared value keeps the substrate's neutral hue and
> foreground chroma and takes the lightness that clears the floor: `oklch(0.578 0.00275 159)`,
> measuring **4.27 / 4.05 / 3.92 / 3.79**. Reversing this means accepting a control whose edge a
> low-vision reader cannot find, and it would be a change to the floor, not to a token.

> **Deviation 2 — the focus ring.** Upstream declares `--ring` as `--primary` at 55% alpha, which
> composites to **3.55 / 3.46 / 3.45 / 3.38**. That clears 3:1, and it is still refused. The ring is
> frequently the *only* focus channel this console renders: `outline-style` is `none` on every
> control, and on the `outline` button variant — the one pagination and filters use — the border
> does not change under `:focus-visible`, because `focus-visible:border-ring` and
> `dark:border-input` both resolve to specificity (0,2,0) and Tailwind emits `dark:` last. A ring
> at partial strength is also a contrast figure nobody can read off a class name, which is the
> argument the 2026-08-06 decision was recorded on when it removed `ring-ring/50` at 3.08. Declared
> at full strength: **9.12 / 8.64 / 8.37 / 8.10**.

### The brand hue

159 degrees — the substrate's green, and the console's most consequential inheritance.

| Token | Job | Value | Resolved |
|---|---|---|---|
| `--color-primary` | the derived accent: focus, the current node, a filled primary control | `oklch(0.76 0.15 159)` | `#45cd8e` |
| `--color-primary-foreground` | reads on `primary` | `oklch(0.19 0.00225 159)` | `#131413` |
| `--color-brand` | the brand's own literal, for a mark rather than a fill | `hsl(153.1 60.2% 52.7%)` | `#3ecf8e` |
| `--color-brand-link` | a link | `hsl(155 100% 38.6%)` | `#00c573` |
| `--color-brand-600` | the readable step | `hsl(154.9 59.5% 70%)` | `#85e0ba` |
| `--color-brand-500` | | `hsl(154.9 100% 19.2%)` | `#006239` |
| `--color-brand-400`, `--color-brand-surface` | the tint behind a current or selected thing | `hsl(155.5 100% 9.6%)` | `#00311d` |
| `--color-brand-300` | | `hsl(155.1 100% 8%)` | `#002918` |
| `--color-brand-200` | | `hsl(162 100% 2%)` | `#000a07` |

**This retires a recorded rule, and the retirement is the important part.** The previous brand sat
at 265 degrees on the explicit ground that *"the reserved status palette occupies the warm and green
arc from about 30 to 145 degrees, and a brand hue inside that arc collides with a verdict."* The
substrate's brand is green. The rule cannot survive the palette it described, and there are only two
honest ways to close it: refuse the substrate's brand — which is refusing the substrate — or accept
that the brand hue and the `good` hue are the same hue and say what still keeps them apart.

They are the same hue here. `good` *is* the brand family (see below), because two greens fourteen
degrees apart is strictly worse than one: a reader cannot tell them apart, and the pair would claim
a distinction the screen cannot render. What keeps a brand mark from reading as a verdict is what
always did, and it is now doing more work: **a status colour ships with an icon and a word, and the
brand never does.** A navigation highlight, a focus ring and a link carry no glyph and no verdict
noun; a status mark carries both. That is the whole of the separation, it is stated rather than
assumed, and it is why *A status colour never travels alone* is no longer merely an accessibility
rule in this console.

Used sparingly remains part of the decision. Links, focus, the current node, one primary action per
screen. Nothing else on a normal screen is chromatic.

### The status palette — reserved

Four roles, and they mean what they say. Never a series colour. Never without an icon and a word.

Three of the four take a substrate family whole: the **ink** is the step a reader reads, the
**surface** is the tint a panel takes, and the **mark** is the fill a chart segment or a filled dot
takes.

| Role | Ink | Surface | Mark | ink on its own tint | mark on the card |
|---|---|---|---|---|---|
| good | `--color-good-ink` `#85e0ba` (`brand-600`) | `--color-good-surface` `#00311d` (`brand-400`) | `--color-good` `#3ecf8e` (`brand-default`) | 9.18 | 8.76 |
| warning | `--color-warning-ink` `oklch(0.8 0.14 75)` `#f2af48` | `--color-warning-surface` `#4a2900` (`warning-400`) | `--color-warning-600` `#db8e00` | 6.84 | 6.56 |
| serious | `--color-serious-ink` `oklch(0.77 0.14 45)` `#fd9565` | `--color-serious-surface` `oklch(0.26 0.055 45)` `#391a0b` | `--color-serious` `oklch(0.66 0.16 45)` `#df6c32` | 7.28 | 5.27 |
| critical | `--color-critical-ink` `oklch(0.75 0.14 25)` `#fa8880` | `--color-critical-surface` `#541c15` (`destructive-400`) | `--color-critical` `#e54d2e` (`destructive-default`) | 5.73 | 4.52 |

`--color-warning` holds the same value as `--color-warning-ink`, because that is upstream's own
semantic `--warning` and three call sites spell the role bare. `--color-destructive` holds the same
value as `--color-critical-ink`, as it did before; new code should say `critical`.

Two ink steps exist for text sitting *on* a solid status fill, and both are upstream's flip
construction — dark ink on a light fill, resolved from the fill's own lightness rather than chosen:
`--color-warning-foreground` `oklch(0.12 0.0112 75)` measures **10.65** on the warning fill, and
`--color-destructive-foreground` `oklch(0.12 0.0112 25)` measures **8.60** on the destructive fill.

**The two stepped scales the roles draw from are declared whole**, as per-theme literals from
`theme.css`. The vendored catalog spells three of them directly (`text-brand-600`,
`text-warning-600`, `border-warning-500`); the rest complete the families, so a later screen
reaching for a tint takes a step rather than inventing one.

| Step | Warning | Destructive |
|---|---|---|
| 600 | `--color-warning-600` `#db8e00` | `--color-destructive-600` `#f16a50` |
| 500 | `--color-warning-500` `#693f05` | `--color-destructive-500` `#7f2315` |
| 400 | `--color-warning-400` `#4a2900` | `--color-destructive-400` `#541c15` |
| 300 | `--color-warning-300` `#341c00` | `--color-destructive-300` `#3b1813` |
| 200 | `--color-warning-200` `#291900` | `--color-destructive-200` `#1d1412` |

**Which of the three to reach for.** Text and icons take the `-ink` step. A panel's tint takes the
`-surface` step. The bare mark is for a chart fill or a filled dot large enough that area carries it
— never a hairline rule; a 1px rule in `--color-warning` reads as a rumour of colour, not a border,
however it measures.

> **Deviation 3 — `serious`.** The substrate has three expressive families (brand, warning,
> destructive) and this console has four roles. `serious` is built on the substrate's *own*
> expressive construction rather than invented beside it: a fixed lightness, the shared
> `--expressive-chroma` of 0.14, and a hue of 45 — between warning's 75 and destructive's 25, and
> inside neither's clamp, so it can never be mistaken for either by the same arithmetic that keeps
> those two apart. Its tint takes the construction the other tints take on their own hues. If the
> substrate ever ships a fourth expressive family, this is the entry to delete.

### The series palette — categorical, fixed order, never cycled

Charts only. Assigned in sequence: one series takes slot 1, four series take slots 1 to 4. A ninth
series is never a generated hue — it folds into "Other", or the chart becomes small multiples, or
it becomes a table.

| Slot | Token | Hue | Value | On the plotting surface |
|---|---|---|---|---|
| 1 | `--color-series-1` | aqua | `#199e70` | 5.14 |
| 2 | `--color-series-2` | orange | `#d95926` | 4.50 |
| 3 | `--color-series-3` | blue | `#3987e5` | 4.81 |
| 4 | `--color-series-4` | green | `#008300` | 3.54 |
| 5 | `--color-series-5` | magenta | `#d55181` | 4.43 |
| 6 | `--color-series-6` | yellow | `#c98500` | 5.70 |
| 7 | `--color-series-7` | violet | `#9085e9` | 5.59 |
| 8 | `--color-series-8` | red | `#e66767` | 5.41 |

> **Deviation 4 — the series palette is not the substrate's.** Not a choice between two candidates:
> **the substrate ships no categorical chart palette.** Its five code-block colours are a syntax
> palette, scored against nothing and ordered by token type. There was nothing here to swap, so the
> palette stands as enumerated and validated, and only the surface it is drawn on moved — from
> `#171717` to the substrate's card, `#181a19`. Contrast against that surface was re-measured for
> all eight slots (the column above): the minimum is 3.54 at slot 4, still clear of the 3:1 floor,
> and the lightness, chroma and CVD-separation checks in *The validator's report* do not depend on
> the surface at all.

**The order is the colour-blindness mechanism, not a preference.** Adjacent slots touch in a stack,
a bar group and a line chart, so adjacent pairs are what the gate measures. All eight orderings of
these hues were enumerated and scored with the `dataviz` skill's validator; 36 clear every hard
gate. This one was chosen among the passing orders by the skill's own tie-break — maximise the
minimum adjacent CVD ΔE — and then, among the orders tied at that maximum, by two constraints this
console has and the skill does not:

- **Slot 1 is neither blue nor violet.** Slot 1 is the colour a single-series chart wears, and
  violet sits at slot 7, which the "more than about seven meaningful classes is a table" rule makes
  effectively unreachable.
- **Among the remaining candidates, slot 1 is the hue furthest from any status colour.** That
  argument was made against the previous status palette and has not been re-run against this one;
  what does not change is that a status colour always arrives with an icon and a word, a series
  colour never does, and a chart carries direct labels and a legend.

**The series cap for scatter, bubble, choropleth and small multiples is three.** In those forms any
two marks can sit side by side, so the gate is all-pairs rather than adjacent, and it is strictly
harder. The first three slots clear it. Past three in an all-pairs form, cut series or facet. Do
not change the palette.

### Chart chrome

| Token | Job | Value |
|---|---|---|
| `--color-chart-grid` | gridlines, recessive | `oklch(0.29 0.0025 159)` |
| `--color-chart-axis` | the baseline and axis rule | `oklch(0.42 0.0025 159)` |
| `--color-chart-label-on-light` | the in-segment label ink `corpus-chart.tsx`'s `labelInkFor` picks per fill | `#000000` |

Both chrome steps moved onto the substrate's neutral hue and chroma, so a gridline belongs to the
same family as everything behind it. The chart's plotting surface is `--color-surface`. Axis
labels, legend entries and tooltip text wear the ink tokens, never the series colour; a coloured
mark beside the text carries identity. One axis, never two. A legend whenever there are two or more
series; direct labels at four or fewer.

**One exception to "text wears the ink tokens": a value label set *inside* a stacked segment**
(`corpus-chart.tsx`) reads against that segment's own fill, not against `--color-surface`, so it
needs a colour chosen for that fill rather than for the neutral ramp.

`--color-chart-label-on-light` is black, not white, and the arithmetic is why. Black's relative
luminance is exactly 0, so contrast against a fill of relative luminance `Lf` is `(Lf + 0.05) / 0.05`;
white's is `(1 + 0.05) / (Lf + 0.05)`. `Lf` below is the full sRGB computation on each series hex,
because these eight are chromatic:

| Series slot | Hue | Value | `Lf` | vs. black | vs. white |
|---|---|---|---|---|---|
| 1 | aqua | `#199e70` | 0.2583 | 6.17 | 3.41 |
| 2 | orange | `#d95926` | 0.2204 | 5.41 | 3.88 |
| 3 | blue | `#3987e5` | 0.2385 | 5.77 | 3.64 |
| 4 | green | `#008300` | 0.1623 | 4.25 | 4.95 |
| 5 | magenta | `#d55181` | 0.2162 | 5.32 | 3.94 |
| 6 | yellow | `#c98500` | 0.2919 | 6.84 | 3.07 |
| 7 | violet | `#9085e9` | 0.2859 | 6.72 | 3.13 |
| 8 | red | `#e66767` | 0.2750 | 6.50 | 3.23 |

Black clears the 5.05 floor against seven of the eight slots; white clears none of them, its worst
case being 3.07. That is the argument for the literal: not "black looks fine here" but "white fails
everywhere and black mostly doesn't."

**Named exception: slot 4 (`#008300`) cannot clear 5.05:1 against any ink, and no different literal
fixes it.** Its `Lf` (0.1623) sits inside the band `(0.158, 0.202)`: below 0.158 white clears 5.05,
above 0.202 black does, and a fill inside the band clears it with neither — that is what solving
both inequalities for the same floor produces, not a property of any one colour. The best available
is white at 4.95. The consequence is bounded rather than silent: `corpus-chart.tsx`'s
`INLINE_LABEL_SHARE_FLOOR` withholds an inline label from a segment too thin to hold one, the legend
restates every value, and the tooltip gives the exact count on hover.

### The compat names the vendored catalog spells

Upstream keeps these in `compat.css` as aliases onto the semantic tokens above, and the vendored
components still use them. They are positions on the ramp, not new colours.

| Utility a vendored file writes | Token declared | Is |
|---|---|---|
| `bg-overlay` | `--background-color-overlay` | `secondary` |
| `bg-overlay-hover`, `bg-selection` | `--background-color-overlay-hover`, `--background-color-selection` | `accent` |
| `bg-alternative` | `--background-color-alternative` | `background` |
| `bg-surface-100` | `--background-color-surface-100` | `card` |
| `bg-surface-200` | `--background-color-surface-200` | `muted` |
| `border-control`, `border-strong` | `--border-color-control`, `--border-color-strong` | `input` |
| `border-stronger` | `--border-color-stronger` | the stronger overlay edge |
| `border-overlay`, `bg-border-overlay` | `--border-color-overlay`, `--color-border-overlay` | the overlay edge |
| `text-background-overlay` | `--color-background-overlay` | `secondary` |
| `ring-border-control` | `--color-border-control` | `input` |

A `--color-*` entry generates `bg-border-overlay` but not `border-overlay`, which is why upstream
declares both namespaces and so does `index.css`.

The sidebar family the vendored rail reads is Studio's own aliasing, and every entry is a step
already argued above:

| Token | Is |
|---|---|
| `--color-sidebar` | `background` |
| `--color-sidebar-foreground`, `--color-sidebar-accent-foreground` | `foreground` |
| `--color-sidebar-accent` | `accent` |
| `--color-sidebar-border` | `border` |
| `--color-sidebar-ring` | `ring` |

---

### The outcome ramp

Five states one repair attempt can end in, ordered by how well it ended. Added 2026-08-24 on the
owner's ruling; the two endpoints are theirs unchanged.

| Step | Token | Value | Meaning |
|---|---|---|---|
| 1 | `--color-outcome-opened` | `#3ecf8e` | reached the forge |
| 2 | `--color-outcome-retried` | `#5bd6e0` | tried again |
| 3 | `--color-outcome-in-flight` | `#e8c15a` | still going |
| 4 | `--color-outcome-reported` | `#f78a4e` | no patch attempted |
| 5 | `--color-outcome-abandoned` | `#fa8880` | gave up |

**Why a ramp rather than the three status inks.** An outcome is a state, not a category, and a
state painted from a categorical slot lies: `abandoned` rendered in the good ink and read as a
success on the Solutions screen (`CI-W620`). There are five states and only three reserved status
inks, so the reserved set is extended rather than stretched.

**Why these five values and not the ones first proposed.** The ruling's middle steps were
`#45cd8e`, `#f2af48` and `#fd9565`. Measured, `opened` against `retried` came out at **CIE76 dE
2.1** — two colours no reader can tell apart, which is exactly the defect `CI-W619` had just fixed
in the traffic chart. `reported` against `abandoned` was **19.8**, also under the threshold. The
middles were searched for the arrangement maximising the worst pair while holding the contrast
floor and the semantic order.

**Measured, and both properties hold at once.** Worst pair **dE 26.3** (`reported` vs
`abandoned`); every other pair is 36.7 or higher. dE ≥ 20 is the threshold this file uses for
"clearly different at chart scale", where a band is a few hundred pixels of flat fill.

Contrast against the three surfaces, all clearing the 5.05:1 floor:

| Step | on `#131413` | on `#181a19` | on `#1e201f` |
|---|---|---|---|
| opened | 9.25 | 8.76 | 8.21 |
| retried | 10.68 | 10.12 | 9.49 |
| in-flight | 10.73 | 10.17 | 9.53 |
| reported | 7.65 | 7.25 | 6.80 |
| abandoned | 7.82 | 7.41 | 6.94 |

**The endpoints are load-bearing and the middles are not.** `opened` is the good ink and
`abandoned` is critical, so the two states a reader most needs to tell apart are the two furthest
apart on the ramp. A future sixth state takes a step between the middles, never at an end.

## Type

Seven steps, and the sizes are Studio's own ramp adopted whole. The console previously lived at
12 / 14 / 16 / 18 / 24 / 32 / 48px.

**The line box on each step is Tailwind's stock ratio for the step it takes, rounded up to the 4px
grid.** That is a rule rather than seven choices, it is checkable from this table alone, and it
lands `--text-body` on a 20px line box — the number *Row height* below derives `row-md` from.

| Token | Size | Line height | Weight | Tracking | Job |
|---|---|---|---|---|---|
| `--text-meta` | 12px | 16px | inherit | normal | labels, timestamps, furniture. **The floor.** |
| `--text-body` | 13px | 20px | inherit | normal | prose and table cells; rows per screen is the currency |
| `--text-emphasis` | 15px | 24px | 600 | −0.02em | a card's own title, inside a repeating grid of them |
| `--text-section` | 18px | 28px | 600 | −0.02em | a section heading — every `MetricPanel` title |
| `--text-page` | 22px | 32px | 600 | −0.04em | a heading that groups sections, above `--text-section` |
| `--text-figure` | 28px | 36px | 600 | −0.04em | stat-tile values only; carries `tabular-nums` |
| `--text-display` | 46px | 48px | 600 | −0.045em | **the page title, once per route.** Nothing else, ever |

Utilities: `text-meta`, `text-body`, `text-emphasis`, `text-section`, `text-page`, `text-figure`,
`text-display`. Weight, line height and tracking travel with the step, so `text-page` is the whole
decision rather than three of them. Override with `font-normal` or `leading-*` where a specific case
needs it.

**The range arithmetic, which is the reason a display step exists at all.** Measured across all nine
routes at 1440x900 before M7-W160, the type range was **2.00 on five routes and 2.67 on four**,
against a 3.4:1 bar, and the widest text on six of them was a stat-tile figure rather than anything
naming the screen — so the console had no focal point on any route, which
`docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md` measures the consequences of.
On this ramp the range is **46 / 12 = 3.83**, and the display step is **46 / 13 = 3.54×** body. Both
halves of the bar clear — at least 3.4:1 overall and a display step at least 3× body — and the step
costs no rows, because **exactly one element per route may take it**: the page title in
`layouts/page-header.tsx`. A second one on a screen is two focal points, which is none.

**The middle of that ramp was declared and never spent, and closing it is an assignment rather
than a step.** `docs/superpowers/reports/2026-08-07-console-fidelity-gaps.md` read the rendered
census across seven routes and found six distinct sizes — 46, 28, 18, 15, 13, 12 — with **18px on
exactly one heading in the whole application**. Almost every other `h2` and `h3` was 12px uppercase
furniture: Fleet's *Open findings by vendor*, *Runs* and *Repair record*; the repository's *Index
coverage* and *Observed telemetry*; the finding's *Known changes* and *Provenance*; the pull
request's *What the compiler said*. So a section's name and the name of a column inside that
section rendered at one size, in one register, and every route was a display-size title above an
undifferentiated field of 13 and 12.

**The boundary between the section step and the furniture register is what a heading does, not
whether it is scanned.** Both are scanned; that is why the distinction was missed. The test:

- **A section heading names a region a reader enters** — a panel with a figure, a caption and the
  evidence under it. It takes `--text-section`. Every `MetricPanel` title is one, which is where
  M7-W188 assigned the step: one class in `components/metric-panel.tsx`, roughly forty renderings
  across all nine routes. `tests/test_console_design_tokens.py` holds it there, and holds it
  against wearing both registers at once — `.furniture` beside `text-section` is 18px small-caps,
  which is neither.
- **A label names a value beside or beneath it** — a `dt`, a table column header, a rail group
  label, a fact tile's caption, a tally's axis. It stays furniture. Nothing in that list moved.

**`--text-page` is reassigned in the same breath, because the assignment above would otherwise
collide with it.** Its job read "the `h1` on every view" — untrue since M7-W160 gave the `h1`
`--text-display`, and 22px appears nowhere in the census above. It is now the step for a heading
that *groups* sections. There is one such heading in the console: `signals-page.tsx`'s role group,
which contains panels rather than tables, and whose own comment has always said that a container
and its contents may not render at one weight. Moving the panel heading to 18px without moving the
role name to 22px would have broken exactly that. The ordering is what is being held — 22 over 18
over 12 — not the individual numbers.

**This adds a section step, never a second display step.** A panel heading at 46px would be the
failure the display step's own rule exists to prevent, and
`test_exactly_one_component_spends_the_display_step` is deliberately untouched by the assignment
above.

### The substrate's own steps, under their own names

Twelve more steps are declared, and they are a decision rather than a convenience. The vendored
catalog spells `text-xs`, `text-sm`, `text-base` and `text-lg` directly, and nothing should resolve
those against Tailwind's defaults while the components around them come from Supabase — a vendored
dialog would sit at 14px body while the screen around it sat at 13px, which is two ramps on one
screen. So Studio's whole ramp is carried, from `apps/studio/styles/globals.css`, tuned there for
its body face.

**These are lengths carried across, not values derived from anything** — there is no arithmetic to
reproduce and no contrast to measure, which is why `web/scripts/theme-contrast.mjs` does not emit
them. The seven role steps above are the ones a screen this project writes reaches for.

| Token | Value | px | Role step on it | |
|---|---|---|---|---|
| `--text-sm` | 0.8125rem | 13 | `--text-body` | |
| `--text-base` | 0.9375rem | 15 | `--text-emphasis` | |
| `--text-lg` | 1rem | 16 | — | |
| `--text-xl` | 1.125rem | 18 | `--text-section` | |
| `--text-2xl` | 1.375rem | 22 | `--text-page` | |
| `--text-3xl` | 1.75rem | 28 | `--text-figure` | |
| `--text-4xl` | 2.125rem | 34 | — | display step |
| `--text-5xl` | 2.875rem | 46 | `--text-display` | display step |
| `--text-6xl` | 3.625rem | 58 | — | display step |
| `--text-7xl` | 4.375rem | 70 | — | display step |
| `--text-8xl` | 5.875rem | 94 | — | display step |
| `--text-9xl` | 7.875rem | 126 | — | display step |

**The six display steps are declared and none of them is licensed.** `--text-display` at 46px is
the only step above `--text-figure` a screen may take, and *exactly one element per route may take
it*. `--text-4xl` and everything above `--text-5xl` exist because the ramp is carried whole and a
vendored component may reach one; a screen in `features/` reaching for `text-6xl` is a second focal
point argued nowhere, and `tests/test_console_design_tokens.py` already fails on a second consumer
of the display tier. The steps above 46px have no consumer in this tree and are the first entries
to delete if the substrate's ramp is ever narrowed.

New code in `features/` and `components/` uses the seven role names.

**Tracking is two-tiered, and it belongs to the heading role, not to size alone.**
`--text-emphasis` and `--text-section` take −0.02em; `--text-page` and `--text-figure` take −0.04em;
`--text-display` takes −0.045em. **The condition:** tracking travels with these five steps because
each names a heading role. If `--text-emphasis` is ever reached for as in-row emphasis rather than a
panel title, that use takes `tracking-normal` alongside it; the tracking belongs to the heading, not
to the size.

**`--font-display` is Manrope; `--font-sans` leads with Inter.** The face split of `CI-W627`,
from the Stitch references: headers wear the display face (h1–h3 take it in the base layer) and
body, meta and furniture run in Inter, which restores the voice change between a title and its
data that one face for every run had flattened. No contrast arithmetic attaches — a face carries
no colour — but the split is a decision with a live alternative (one face everywhere, rejected
for reading monotone), so it is recorded here where the type system is argued.

**`--font-weight-normal` is 450, not 400.** Upstream's own adjustment, adopted with the ramp it
belongs to — its ramp was tuned against that weight, and taking the sizes without it would be taking
half a decision. The heaviest step this console declares is still 600, and
`tests/test_console_design_tokens.py` reads that ceiling out of the table above.

**The furniture class.** `.furniture` (`web/src/index.css`, `@layer components`) is the uppercase,
open-tracked treatment for graph-level labels, defined once so nothing in the tree hand-spells it
again. It is a class, not a token — this document's own test says so: two agents rendering a
graph-level label would both reach for uppercase and open tracking, so there is nothing for them to
choose differently. It covers **one of `--text-meta`'s two jobs**: a scanned label — a graph-level
name, a column header, a rung label — takes it; a read value — a timestamp, a count — does not.
**Being scanned is necessary and not sufficient**: a section heading is scanned too and takes
`--text-section` instead, on the boundary the *Type* argument above states. It
sets `text-transform: uppercase` in CSS rather than in copy, because a screen reader spells out
letters that are already capitalised in a string. It is deliberately outside the `text-*` namespace:
`web/src/lib/utils.ts` teaches `tailwind-merge` exactly the seven font-size names above, and an
unlisted `text-*` class merges as a text-*colour* conflict instead — the defect that file's
docstring already records once, for `text-emphasis` against `text-critical-ink`.

**Tabular figures.** `--text-figure` carries `font-variant-numeric: tabular-nums`, because every
value on that step is a number an operator compares down a column or across a poll, and
proportional digits make that comparison a guess. Mono numbers do not also take it: mono already
aligns by construction, and `tabular-nums` on a mono run would be decoration on a mechanism that
already works.

**Faces.** `--font-sans` is `system-ui, -apple-system, "Segoe UI", sans-serif`; `--font-mono` is
`ui-monospace, "Cascadia Code", "Segoe UI Mono", Menlo, Consolas, "Liberation Mono", monospace`.
**The substrate's faces are deliberately not taken.** Upstream's sans is a licensed brand typeface
and Studio's is a webfont; both are identity rather than mechanism, and
`.claude/rules/interface-originality.md`'s carve-out keeps identity excluded whatever else it
permits. A webfont also buys a network request, a flash of unstyled text and a licence question for
a console nobody outside this project has opened.

---

## Space

Four tokens. `p-row`, `gap-field`, `space-y-section`, `p-frame` and the rest of the spacing
utilities all take them.

| Token | Value | Job |
|---|---|---|
| `--spacing-field` | 4px | a label to its value, inside a card |
| `--spacing-row` | 8px | table cell padding |
| `--spacing-section` | 16px | between blocks inside a panel |
| `--spacing-frame` | 40px | the page frame: content to the chassis. One consumer, `app-frame.tsx` |

**The substrate did not move these, and that is a measurement rather than a decision to skip the
work.** Supabase's own spacing scale is `xs 4 / sm 8 / md 16 / lg 32 / xl 64`; the three inner
tokens above are its first three values exactly, and the vendored components spell Tailwind's base
4px scale throughout rather than any named spacing token. There was nothing to swap. The frame is
ours and is argued below.

**Recorded decision: the between-panel gap stays **32px** and stays unnamed.** It is written
`gap-8` on Tailwind's base scale — the substrate's `lg`, as it happens — and it stays unnamed
because it is a page-layout value used once per view, not a component value; a component reaching
for it is misusing it. A genuinely new spacing value is a decision recorded here, not a token added
quietly.

**Recorded decision: these four tokens are the only spacing spellings permitted inside
`features/`.** A raw Tailwind spacing utility in a feature screen (`gap-4`, `p-2`, `p-10`, …)
duplicates one of these numbers under a different name — measured on this tree at 19 token spellings
against 128 raw ones, two of them landing on the same pixel value under a different name (`gap-1`
and `gap-field` both 4px; `p-4` and `p-section` both 16px). A raw value stays legitimate only for a
page-layout number used once per view, on the grounds argued above for the 32px section gap — never
inside a component.

**Recorded decision (2026-08-17, M14-W367): the chassis has three page-layout numbers — an expanded
sidebar at 240px, a minimised sidebar at 48px, and a 48px top bar.** They are argued here before
being spent, and they are spelled in `layouts/` rather than as tokens, on exactly the grounds above:
each is used once per view and none is a component value. `layouts/` sits outside the raw-spacing
guard's scope (`tests/test_console_design_tokens.py:305-309`), so spelling them there is legitimate
rather than a hole.

**The 48px minimised width settles a contradiction this document has carried.** The passage on the
current-row ramp above argues from "a 48px column with no label in it", while the rail that actually
shipped was `w-10` — 40px. Two numbers, one of them never true. The rail is deleted as of `M14-W366`
and there is now one sidebar, so the number is settled at **48px**: it is what the ramp argument was
written against, it matches the top bar's `h-12` so the two edges meet, and it leaves 16px of
clearance around a 16px icon rather than 12px.

**240px expanded, not the vendored 13rem/208px.** `M14-W366` measured the shipped sidebar at 208px
against mock v1's 246px, and the mock is the appearance target. 240px is the nearest value on the
frame's own arithmetic (`6 × 40px`), lands within 6px of the drawing, and gives a destination label
room to render without truncation at the longest level name the specification declares.

**What minimising may and may not change.** It changes **density, not navigation** — the constraint
carried from `M7-W160`'s commit body and the reason `M7-W171`'s predecessor was deleted. Every
destination reachable expanded stays reachable minimised; no icon moves vertically across the state
change, which means a group heading's row keeps its height and only its text goes `sr-only`; and no
prose renders at one width and not the other, because that changes the height of every row beneath
it. **No transition on the width.** `DESIGN.md`'s motion test is frequency rather than duration, and
a surface the operator crosses repeatedly takes none — which is also why the vendored `Sidebar`'s
`collapsible="icon"` path is not adopted: it carries `transition-[width]`
(`web/src/vendor/supabase/ui/sidebar.tsx:226`) and is exempt from
`test_nothing_transitions_geometry_anywhere` by path, so it would animate for a default reader while
CI stayed green.

**Recorded decision: each spacing level is at least twice the one below it, and the requirement
binds the three *inner* levels, not the page frame.** `32 : 16 : 8 : 4` holds the 2× floor at every
inner step. Before M7-W160 the between-panel gap was 24px, the same value as the page frame, which
was the sharpest defect that slice measured: the page had one spacing level where it needed three.

**Reversed 2026-08-06 (M7-W160): the frame is 40px, and the argument that kept it at 24 rested on a
component that did not exist.** The refusal read: *"A console's edge is held by the navigation rail
and the header, not by the frame."* **There was no rail.** `layouts/site-nav.tsx` rendered a
horizontal strip with a bottom border, and `app-shell.tsx` put the whole page in a 24px gutter under
it — so the premise was false when it was written and stayed unexamined because it had been recorded
as a ruling. Against the 8px in-component unit, 40px gives a ratio of **5.0**, inside the 4.7–7.2
band three measured reference surfaces hold. It was **3.0 on all nine routes** before this.

**The frame is larger than the gap it sits outside of — 40 : 32 — and that ordering is the point.**
Four levels: `40 : 32 : 16 : 8 : 4`.

---


### Shell geometry

Three page-layout numbers the Stitch specification names, added 2026-08-24. They are not component
spacing and do not belong in the four-token scale above: each is used once per view, by the chassis.

| Token | Value | Job |
|---|---|---|
| `--spacing-sidebar` | `15rem` (240px) | the sidebar, expanded |
| `--spacing-sidebar-collapsed` | `3rem` (48px) | the sidebar as a rail |
| `--spacing-topbar` | `3rem` (48px) | the top bar |

**Both sidebar widths were already argued** under the *chassis widths* decision (`M14-W367`) and are
unchanged: 240px lands within 6px of mock v1's 246px and is 6× the 40px frame; 48px settles a
contradiction where the current-row colour ramp argued from "a 48px column with no label in it"
while the rail that shipped was 40px. What is new is that they are **tokens rather than two string
constants in `sidebar-collapse.ts`**, because the Stitch specification gives the top bar the same
48px and a third view choosing its own number is the drift a token exists to stop.

**The top bar's 48px is the specification's**, and it matches what the console already rendered —
`h-12` on the banner — so this token names a measured fact rather than changing one.

## Row height

Three named steps, not a fourth spacing token — a row height and a spacing gap answer different
questions. The row height is chosen first, from the same scale a control already renders at; the
cell padding is *derived* from it, not the other way round.

| Step | Value | Already rendered at | Governs |
|---|---|---|---|
| `row-sm` | 32px (`h-8`) | `Button`'s default size | a compact row — a dense table, a toolbar |
| `row-md` | 36px (`h-9`) | `Button`'s `lg` size, and `--text-body`'s 20px line box plus `--spacing-row` (8px) top and bottom | the default table row |
| `row-lg` | 40px (`h-10`) | `TableHead` today | a header row, or a form field needing a larger target |

None of these is a new value: each is a Tailwind stock height Sync's own components already render,
named here so a future row is chosen from the scale rather than invented. A control dropped into a
`row-md` cell (a default 32px button) clears the row by 2px on each side without changing the row's
height — that is the property the scale exists to protect.

**The substrate swap left these standing, and that is why `--text-body`'s line box is on the 4px
grid rather than scaled with its size.** Tailwind's stock ratio for the step `--text-body` takes
would give 18.57px, which makes a 34px row; the rounding rule stated in *Type* gives 20px and holds
`row-md` at 36. Changing the row scale is a different decision from swapping a type ramp, and this
work item did not make it.

**Corrected 2026-08-06, and the correction is the useful part.** This section used to say `row-md`
was "the existing arithmetic made explicit". It never rendered 36px: `table.tsx` spelled `py-2.5` —
10px, off the 4px base — and a comment in that file stated the opposite rule to this one. Measured
in Chrome at 1440×900 across seven tables on the Fleet screen: a single-line body row was **40.5px**
and a header row **36.5px**, the two heights this table assigns, in each other's slots. The classes
now derive from the numbers above (`h-10 px-row py-row` on the header, `px-row py-row` on the cell)
and measure **40.0px** and **36.0px**.

Two things follow. **A header cannot reach `row-lg` through padding**: 12px of `--text-meta` on a
16px line box plus `--spacing-row` twice is 32px, and the value that would make it 40 is a 12px
padding this document deliberately does not name — which is why the header declares `h-10` and pads
inside it. And **the sentence is checkable**: `tests/test_console_design_tokens.py` multiplies the
classes `table.tsx` sets against the Type, Space and Row height tables here and asserts they equal
these numbers, so this table and that file cannot disagree again without a test naming which one
moved.

---

## Radius

Two values, and both are the substrate's — `rounded-md` on every control the vendored catalog
ships, `rounded-lg` on every card and dialog.

| Token | Value | Job |
|---|---|---|
| `--radius-control` | 6px | buttons, inputs, badges, chips |
| `--radius-surface` | 8px | cards, panels, dialogs |

The surface radius was 10px before the swap. Tailwind's stock `--radius-md` is left alone and still resolves,
because `button.tsx` reads it through `var(--radius-md)` in an arbitrary value — see *Stock Tailwind
keys this contract leaves alone* below.

---

## Elevation

Two levels for surfaces this project draws, and the mechanism at both is a ring. A console with no
depth to communicate should not paint depth, and a surface with no neighbour to be told apart from
should not draw a ring either.

| Token | Is | Use for |
|---|---|---|
| `--shadow-flat` | a hairline ring in `--color-line` | a surface that must be told apart from a neighbour at the same depth step — not applied by default |
| `--shadow-float` | the same ring, plus a soft drop shadow | only something that occludes content |

There is no third level *of ours*. Cards do not float above tables. Today exactly one thing this
project draws floats: the command palette's dialog, which is modal and covers the console
deliberately.

**`ErrorSurface` used to be the example here and is no longer one, which is the clearest case this
section has of the rule working.** It was `fixed` over the viewport with `--shadow-float`, and the
owner's capture of a branch with no API behind it showed ninety-two stacked error cards covering the
page. A debugging log is not worth occluding for. M7-W183 moved it into a banner slot above the top
bar, in flow, where it displaces the chassis instead — and it took the float token off on the way
out, because the elevation was the claim that it deserved to be in front.

**The vendored catalog carries Tailwind's stock `shadow-xs / sm / md / lg` instead, and that is the
boundary rather than a fourth level.** A vendored dialog, popover and card arrive with the elevation
their own system gave them; restyling them happens in `web/src/components/`, never inside
`web/src/vendor/`. What this section governs is what the console's own surfaces reach for.

**The ring is a shadow, not a border, for one reason: it costs no layout.** A `border` changes an
element's box, so a row that gains one shifts by a pixel relative to its neighbours above and below.
A 1px inset box-shadow occupies no space, so a row can move between rest, hover and selected without
ever nudging the rows around it.

**A shadow token must express its colour through a colour token, never as a literal.** Tailwind
resolves a `shadow-*` theme value at build time and bakes it into the class, so a literal colour
written into `--shadow-float` would be frozen forever, immune to any value `--color-shadow` is later
given. `--color-shadow` (`oklch(0 0 0 / 0.72)`) exists for exactly this reason and has no other use.

---

## Motion

Two mechanisms, because two different kinds of motion need two different gates.

**The gate a new transition is checked against is frequency, not duration.** A surface the operator
crosses repeatedly takes no transition at all; a surface they meet only occasionally may take one.
This console tried two other rules first and reversed both: "no motion anywhere," measured from
three landing pages with near-zero authored interactions, and "150ms because a dense screen has many
controls," reasoned from a component-count comparison. Neither is decidable by whoever is writing a
component. `getsentry/sentry` writes the actual variable down directly: "frequent interactions…
should avoid animation all together" (`components/core/principles/motion/motion.mdx:39`), while the
same system publishes a 120–240ms token set and spends it on overlays, modals and toasts. Its own
row-hover primitive declares no transition at all, which is why `TableRow`'s hover fill carries none
either: a row hover is the most frequent interaction in this console. `ErrorSurface` arriving is the
opposite case — a genuine failure, and nothing else, puts it on screen. **When adding a transition,
ask how often the operator crosses this surface, not how large the page is or how long feels
right.**

`web/src/lib/motion.ts` owns the framer-motion-driven usages, and **it is a registry rather than a
list in prose**: `MOTION_USAGES` names every module permitted to import framer-motion, and
`tests/test_console_design_tokens.py` asserts that array and the tree name the same modules in both
directions. An unlisted importer fails; so does an entry that no longer imports anything, so a
deletion cannot leave a permission behind.

Each usage reads `useReducedMotion()` from that file and, under reduced motion, substitutes a
duration of `0` for its animated prop set rather than shortening it — a fade or a colour wash that
merely sped up would still be motion. This is code, not a token, because the branch is the token:
there is no CSS value that expresses "skip this prop entirely."

**Two usages, and the third was deleted on evidence rather than on taste.** `ErrorSurface` arriving
and leaving is the occasional surface this section already licensed; its animated property is
opacity alone, because a banner that displaces the chassis would otherwise be animating a layout
shift. The changed-under-poll wash tracks a checkpoint the checkpointer wrote at a moment, which is
a time the graph holds. The third was "the paged table container settling into its new height", and it had
never once run: every screen that paginates returns a loading state while `query.isPending`, so a
page change unmounts the subtree a layout animation would need to persist across. Sampled every 40ms
across a swap from 50 rows to 34: zero transforms, zero entries in `document.getAnimations()`.

Everything else — every Tailwind `transition-*` and `animate-*` utility the vendored catalog and the
console's own components use — is gated by a `@media (prefers-reduced-motion: reduce)` block in
`web/src/index.css`, sitting unlayered on purpose: `@theme` and every Tailwind utility compile into
layers, and an unlayered rule beats every layered rule regardless of specificity. It zeroes
`transition-duration`, `animation-duration` and `scroll-behavior` document-wide — zeroed, not
shortened.

`Button`'s `active:not-aria-[haspopup]:translate-y-px` is deliberately left alone. A `transform` is
not a transition: it moves the element on `:active` whether or not a transition is running. With the
transition gone under reduced motion, the 1px press lands in a single frame — an instant state
change indistinguishable from any other instant style swap this query already makes.

---

## How the theme is wired

`web/src/index.css` declares every token once, inside `@theme static` at `:root` — there is no
second column left to switch to. `web/index.html` stamps `class="dark"` on `<html>` directly in the
markup, permanently, rather than resolving it at runtime: there is no preference to read and no
flash-of-wrong-theme to beat before first paint.

The class stays for a reason that has nothing to do with switching: the shadcn catalog's own
components carry `dark:`-prefixed utility classes, and `@custom-variant dark (&:is(.dark *))` in
`index.css` is what makes those classes match anything. Removing the class, or the variant, would
silently drop those components' `dark:` rules rather than remove a toggle. `:is(.dark *)` matches
every descendant of `<html>`, so the one class stamped once covers the whole document. **The
vendored catalog keys off the same two selectors** — upstream's own theme block is
`[data-theme='dark'], .dark`, so a component copied from it resolves against the class this
document already stamps.

Every value is a literal, not a `var()` reference: `echart.tsx` reads seven of them through
`getComputedStyle`, which returns declared text rather than a resolved colour.

**One base rule sits alongside the tokens, and it is what makes the hairline above reach the
vendored components at all.** Tailwind v4's preflight resets every element to `border: 0 solid`,
leaving `border-color` at `currentColor`; a `border` utility that names no colour therefore draws
the *text* colour, which on this theme is the primary ink at full strength. Nothing in `src/`
outside `vendor/` hit that, because every class here names its colour — but the vendored catalog
spells bare `border` and `border-b`, since upstream ships this compat rule in the globals we did
not vendor. `index.css` declares it in `@layer base`:

```css
*, ::after, ::before, ::backdrop, ::file-selector-button {
  border-color: var(--color-border);
}
```

Measured on the Fleet screen at 1920×889 before it existed: every panel outline and every card
header rule computed `oklch(0.95 0.00275 159)` — identical to the element's own `color` — against
the `oklch(0.95 0.001485 159 / 7.5125%)` the Boundaries table declares. The icon rail beside them,
which spells `border-line` explicitly, was already correct, which is what made the two comparable.
**It is a default, not a token**: it declares no value of its own, `theme-contrast.mjs` does not
produce it, and any utility naming a colour still wins.

The three-state theme control (`light` / `dark` / `system`), `web/src/lib/theme.ts`,
`theme-toggle.tsx`, the `sync-theme` `localStorage` key, and the `prefers-color-scheme` listener
that resolved a `"system"` preference are all removed, not merely unused.

---

## Changing a colour

1. **Do not edit `web/src/index.css`.** Change the number in `web/scripts/theme-contrast.mjs` —
   a generator parameter for a substrate colour, the token's own `decl(…)` for one of ours — and
   paste its `== declarations ==` block back over the declarations in `index.css`. A literal
   hand-edited into the stylesheet is a colour the measurement below never saw.
2. Run `node web/scripts/theme-contrast.mjs`. Nothing may fall below **5.05:1**. A pairing that
   regresses is a bug in the ramp, not an acceptable trade.
3. Paste the new tables into *Contrast, computed* below. A figure whose run is not reproducible is
   the defect this section keeps having.
4. If a series slot moved, re-run the validator against the plotting surface and paste the report.
5. If you changed the slot *order*, re-run the enumeration: the order is a gate, not a preference.

---

## The validator's report

From the `dataviz` skill, `scripts/validate_palette.js`. The run below was made against the
console's previous plotting surface, `#171717`; the surface is now `#181a19` and the palette is
unchanged, so four of its five checks are unaffected — lightness, chroma and both CVD separations
are properties of the eight hues alone. **The fifth, contrast against the surface, was re-measured
and is published in the series table above** (minimum 3.54, all eight clear of 3:1) rather than
restated from this run.

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

exit 0
```

### The all-pairs cap

```
$ node <dataviz>/scripts/validate_palette.js "#199e70,#d95926,#3987e5" --mode dark --surface "#171717" --pairs all
  [PASS] CVD separation         worst all-pairs #d95926↔#199e70 ΔE 9.4 (deutan) · tritan 4.0
  [PASS] Normal-vision floor    worst all-pairs #3987e5↔#199e70 ΔE 20.9 (normal)
  → ALL CHECKS PASS                                                        exit 0
```

### The validator was shown to reject

A validator that has never rejected a palette has not been shown to validate one. Slot 4 (green) was
moved to slot 2, beside slot 1 (aqua), and the run was repeated. It failed and exited 1.

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

Every figure below is printed by `node web/scripts/theme-contrast.mjs`. WCAG 2.x relative luminance
over resolved sRGB bytes, against a floor of **5.05:1**. Alpha is composited in gamma-encoded sRGB
rather than in linear light or in OKLCH, because that is what a browser does to `background-color`
and the three disagree visibly; a ratio computed the other way would not describe the screen.

The four rightmost columns are composites, not declared tokens: a state overlay resolved over the
depth step beneath it. **A composed figure is meaningless without the backdrop it was composed over,
so every column names one.**

| Ink | on `background` | on `card` | on `popover` | on `secondary` | subtle/bg | subtle/card | emphasis/bg | emphasis/card |
|---|---|---|---|---|---|---|---|---|
| `ink` | 15.99 | 15.14 | 14.67 | 14.19 | 14.96 | 14.02 | 14.32 | 13.35 |
| `ink-muted` | 9.80 | 9.28 | 8.99 | 8.70 | 9.17 | 8.59 | 8.77 | 8.18 |
| `ink-secondary` | 6.52 | 6.18 | 5.99 | 5.79 | 6.10 | 5.72 | 5.84 | **5.45** |
| `primary` | 9.12 | 8.64 | 8.37 | 8.10 | 8.54 | 8.00 | 8.17 | 7.62 |
| `brand-link` | 8.12 | 7.69 | 7.45 | 7.21 | 7.60 | 7.12 | 7.27 | 6.78 |
| `good-ink` | 11.76 | 11.13 | 10.79 | 10.43 | 11.00 | 10.31 | 10.53 | 9.82 |
| `warning-ink` | 9.67 | 9.16 | 8.88 | 8.58 | 9.05 | 8.48 | 8.66 | 8.08 |
| `serious-ink` | 8.50 | 8.05 | 7.80 | 7.54 | 7.95 | 7.45 | 7.61 | 7.10 |
| `critical-ink` | 7.82 | 7.41 | 7.18 | 6.94 | 7.32 | 6.86 | 7.01 | 6.54 |

Status ink on its own tint: good 9.18, warning 6.84, serious 7.28, critical **5.73**. `ink` on each
tint: good 12.48, warning 11.30, serious 13.71, critical 11.70. `brand` on `brand-surface` 7.22.
`primary-foreground` on `primary` 9.12. `warning-foreground` on `warning` 10.65.
`destructive-foreground` on `destructive` 8.60.

**Worst pairing anywhere: 5.45:1** — `ink-secondary` composed over `surface-emphasis` on a card,
which is the chart legend's step under a selected row and is not a pairing the tree renders today.
The worst pairing the tree *does* render is `ink-muted` at 8.18. Both are above the 5.05 floor, and
the substrate improves the previous palette's worst case of **5.31**.

**Below the floor: none.** The four deviations named in this document exist so that this line reads
that way; each one is a place where the substrate would have produced a figure this contract
refuses, argued rather than accepted.

### Non-text, against the 3:1 floor

| | on `background` | on `card` | on `popover` | on `secondary` |
|---|---|---|---|---|
| `line-strong` / `input`, as declared | 4.27 | 4.05 | 3.92 | 3.79 |
| `line-strong`, as upstream derives it | 1.43 | 1.46 | 1.46 | 1.47 |
| `ring`, as declared | 9.12 | 8.64 | 8.37 | 8.10 |
| `ring`, as upstream derives it (55%) | 3.55 | 3.46 | 3.45 | 3.38 |
| `line` (a hairline, no 3:1 obligation) | 1.19 | 1.21 | 1.22 | 1.23 |
| `border-overlay` (a hairline) | 1.41 | 1.44 | 1.46 | 1.47 |
| `border-stronger` (a hairline) | 1.62 | 1.65 | 1.67 | 1.67 |

The status **marks** against the card: good 8.76, warning 6.56, serious 5.27, critical 4.52 — all
four clear 3:1. The `brand` mark measures 8.76, the same value as `good`, which is the collision
*The brand hue* names and the icon-and-word rule answers.

**A link takes the user agent's ring, not this one.** No console rule styles `a:focus-visible`;
Chrome renders `outline-style: auto`, its own two-tone ring, contrast-safe by construction.
Deliberately left alone — a ring the browser adapts is better than one this contract would have to
re-measure per surface.

---

## Stock Tailwind keys this contract leaves alone

Two theme keys are named in this document, are not declared in `index.css`, and are not an
oversight: the stock value is already the right one, and redeclaring it would put a second copy of a
number nobody chose into a file that has to be maintained. **This section exists so that "named but
not declared" is a category with two members rather than an untested gap** —
`tests/test_console_design_tokens.py` reads the table below and holds every other token in this
document to being declared.

| Key | Stock value | Why it stands |
|---|---|---|
| `--text-xs` | 0.75rem | Upstream leaves it alone too. It is the same 12px as `--text-meta`, so the floor is one number whichever spelling a component reaches for. |
| `--radius-md` | 0.375rem | Already equal to `--radius-control`, and `button.tsx` reads it through `var(--radius-md)` inside an arbitrary value. Redeclaring it would give the same 6px two names in one file. |

A third entry here is a claim that a stock Tailwind value is correct for this console, which is a
decision — argue it in this table or declare the token.

---

## Deliberately absent

- **A sequential ramp and a diverging pair.** No chart in the plan encodes continuous magnitude or
  polarity. Adding them before a chart needs them means guessing at steps nobody will check.
- **A texture fill.** The accessibility channel for the CVD, print and `forced-colors` cases. Not
  needed while every chart carries direct labels and a table beneath it.
- **Motion tokens.** Durations and easings live in `web/src/lib/motion.ts`, not here.
- **A composite score, a health number, a traffic light, a liveness dot.** Rejected on the merits.
  A design system is exactly the moment somebody reaches for a coloured badge, which is why it is
  named here.
- **A third elevation level of ours, a fifth spacing value, an eighth type step.** Each is a
  decision to be argued in this file, not a value to be added.
- **The substrate's `--info`, `--tertiary`, its twelve-step Radix scales, its code-block colours,
  and its two `sidebar-primary` entries.** Every one of them is declared upstream and none has a
  consumer in this tree. An abstraction added for an anticipated caller is debt with no asset behind
  it; the day a component needs one, it arrives with the component.
- **A light mode.** Retired 2026-08-05 on explicit instruction. Reversing it means regenerating from
  `web/scripts/theme-contrast.mjs` rather than importing a block already in the tree: `theme.css`
  declares one selector, `[data-theme='dark'], .dark`, and carries no light values at all. Not a placeholder for a toggle — the theme resolver, its storage key and its
  `prefers-color-scheme` listener are deleted, and a component that branches on
  `prefers-color-scheme` again would be a regression against a recorded decision.

---

## The four bands

Every screen renders through `layouts/screen-frame.tsx`: **identity → controls → content → status**.
Twenty screens carried eight different opening structures before it, so a reader re-learned the
layout on every navigation.

**They are a reading order across four elements, not one parent.** Identity is the chassis banner
and status is a `<footer>` beside `<main>`, because `app-frame.test.tsx` pins `banner.parentElement`
to the element that also holds `main` — the sidebar has to stay outside that column. A screen
therefore publishes its status through a portal rather than rendering it inline.

| Band | Owner | Absent when |
|---|---|---|
| identity | chassis | never — it derives from the address and renders before any query answers |
| controls | screen | **omitted entirely** when there is nothing to narrow: no element, no rule, no reserved height |
| content | screen | never |
| status | screen, via portal | never — a screen with nothing to count publishes `none` and says why |

**Status is a row of typed segments rather than one count.** Four screens make a single number false:
`RunsPage` counts runs at workspace scope beside corpus attempts at deployment scope, `MetricsPage`
has five independent fetches and no instant at which it is loaded, `SolutionsPage` holds three scopes
in one content region, `DetectorsPage` has four countable regions.

The segment vocabulary is closed — `records` · `listing` · `figure` · `note` · `none` — and `none`
carries a reason, because a blank band renders "nothing here pages" and "has not answered yet" as
the same nothing.

**`data-band`, never `data-slot`.** The shadcn primitives stamp `data-slot` on 26 files' worth of
elements, so a test helper querying it binds to a `CardHeader` before it binds to a band.

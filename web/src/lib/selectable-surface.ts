/**
 * Selected and unselected, as named surface steps.
 *
 * The catalog's own `outline`/`secondary` pairing renders this backwards here: `outline` fills
 * with `input/30`, a translucent light wash, while `secondary` is `0.255` — flat and *darker* than
 * the wash. Measured on the running screen, the unselected chips came back brighter than the
 * selected one, which is the state distinction inverted rather than merely subtle.
 *
 * So the steps are named instead, which is what `DESIGN.md`'s surface ramp reserves them for: a
 * control at rest takes its panel's own depth step, `surface-emphasis` is a selection, and
 * `surface-subtle` is the pointer. Rest, hover and selected then climb the ramp in that order. The
 * `dark:` spellings are the ones that land — the console is dark-only and the class is permanent —
 * but both are written so the override does not depend on which variant the catalog happens to use
 * for a background.
 *
 * It lives here rather than in `filters.tsx`, where it started, for two reasons. A filter and an
 * ordering both need it and they are deliberately not the same thing — one changes which rows
 * exist, the other changes nothing about the set — so neither file owns it. And exporting a
 * non-component from a component module trips `react(only-export-components)`: Fast Refresh stops
 * working for the whole file, which `npm run lint` reports and which was the immediate reason this
 * moved.
 */
export function chipSurface(selected: boolean): string {
  return selected
    ? "border-line-strong bg-surface-emphasis hover:bg-surface-emphasis dark:border-line-strong dark:bg-surface-emphasis dark:hover:bg-surface-emphasis"
    : "border-line bg-surface hover:bg-surface-subtle dark:border-line dark:bg-surface dark:hover:bg-surface-subtle"
}

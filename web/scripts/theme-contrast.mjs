/**
 * Resolves the Supabase dark theme to sRGB and measures every text-bearing pairing
 * `DESIGN.md` declares, against the console's 5.05:1 floor and the 3:1 non-text floor.
 *
 * The inputs are the eight generator parameters `web/src/vendor/supabase/theme.css`
 * carries for `.dark`; the derivations are transcribed from the same commit's
 * `packages/ui/build/css/source/semantic.css` and `compat.css`. Nothing here is a
 * measured number typed in by hand -- run it again after changing a token and paste
 * what it prints.
 *
 * Alpha is composited in gamma-encoded sRGB, not in linear light or in OKLCH,
 * because that is what a browser does to `background-color` and the two disagree
 * visibly. A ratio computed the other way would not describe the screen.
 *
 *   node web/scripts/theme-contrast.mjs
 */

// -- colour space -------------------------------------------------------------------

function srgbFromLinear(c) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055
}

function linearFromSrgb(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

/** OKLCH (L 0..1, C, H degrees) to linear sRGB, then to 0..255 with clipping. */
function oklch(l, c, h) {
  const hr = (h * Math.PI) / 180
  const a = c * Math.cos(hr)
  const b = c * Math.sin(hr)

  const l_ = l + 0.3963377774 * a + 0.2158037573 * b
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b
  const s_ = l - 0.0894841775 * a - 1.291485548 * b

  const L = l_ * l_ * l_
  const M = m_ * m_ * m_
  const S = s_ * s_ * s_

  const lr = +4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S
  const lg = -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S
  const lb = -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S

  return [lr, lg, lb].map((v) => clamp255(Math.round(srgbFromLinear(clamp01(v)) * 255)))
}

/** HSL (H degrees, S percent, L percent) to 0..255, the spelling the theme file uses. */
function hsl(h, s, l) {
  const sN = s / 100
  const lN = l / 100
  const k = (n) => (n + h / 30) % 12
  const a = sN * Math.min(lN, 1 - lN)
  const f = (n) => lN - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  return [f(0), f(8), f(4)].map((v) => clamp255(Math.round(v * 255)))
}

function clamp01(v) {
  return Math.max(0, Math.min(1, v))
}

function clamp255(v) {
  return Math.max(0, Math.min(255, v))
}

function hex(rgb) {
  return '#' + rgb.map((v) => v.toString(16).padStart(2, '0')).join('')
}

/** Source over backdrop at `alpha`, in gamma-encoded sRGB -- what a browser does. */
function over(source, backdrop, alpha) {
  return source.map((v, i) => Math.round(v * alpha + backdrop[i] * (1 - alpha)))
}

function relativeLuminance(rgb) {
  const [r, g, b] = rgb.map((v) => linearFromSrgb(v / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(a, b) {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  const hi = Math.max(la, lb)
  const lo = Math.min(la, lb)
  return (hi + 0.05) / (lo + 0.05)
}

function fmt(n) {
  return n.toFixed(2)
}

// -- the dark theme's generator inputs, verbatim from vendor/supabase/theme.css -------

const HUE = 159
const CHROMA = 0.005
const SURFACE = 0.19
const ELEVATION_STEP = 0.025
const CONTRAST = 0.5
const FOREGROUND_LIGHTNESS = 0.95
const MUTED_FOREGROUND_LEVEL = 0.8
const TERTIARY_FOREGROUND_LEVEL = 0.65

// -- the derivations, transcribed from semantic.css at the same commit ---------------

const TONE_SPAN = FOREGROUND_LIGHTNESS - SURFACE // 0.76
const ELEVATION = { e1: 1, e2: 1.5, e3: 2 }
const CONTRAST_BORDER_FLOOR = 0.05
const CONTRAST_BORDER_LINEAR = CONTRAST_BORDER_FLOOR + (1 - CONTRAST_BORDER_FLOOR) * CONTRAST
const CONTRAST_BORDER = CONTRAST_BORDER_LINEAR * CONTRAST_BORDER_LINEAR
const OVERLAY_UNIT = ELEVATION_STEP / Math.abs(TONE_SPAN)

const ALPHA = {
  muted: OVERLAY_UNIT * ELEVATION.e1,
  accent: OVERLAY_UNIT * ELEVATION.e2,
  tertiary: OVERLAY_UNIT * ELEVATION.e3,
  border: 0.02 + 0.2 * CONTRAST_BORDER,
  input: 0.03 + 0.38 * CONTRAST_BORDER,
  borderOverlay: 0.04 + 0.34 * CONTRAST_BORDER,
  borderStronger: 0.05 + 0.45 * CONTRAST_BORDER,
  ring: 0.55,
}

const FOREGROUND_CHROMA = CHROMA * 0.55
const EXPRESSIVE_CHROMA = 0.14

// Opaque depth steps.
const background = oklch(SURFACE, CHROMA * 0.5, HUE)
const card = oklch(SURFACE + ELEVATION_STEP * ELEVATION.e1, CHROMA * 0.5, HUE)
const popover = oklch(SURFACE + ELEVATION_STEP * ELEVATION.e2, CHROMA * 0.5, HUE)
const secondary = oklch(SURFACE + ELEVATION_STEP * ELEVATION.e3, CHROMA * 0.5, HUE)

// Ink steps.
const foreground = oklch(SURFACE + TONE_SPAN * 1, FOREGROUND_CHROMA, HUE)
const mutedForeground = oklch(
  SURFACE + TONE_SPAN * MUTED_FOREGROUND_LEVEL,
  FOREGROUND_CHROMA,
  HUE,
)
const tertiaryForeground = oklch(
  SURFACE + TONE_SPAN * TERTIARY_FOREGROUND_LEVEL,
  FOREGROUND_CHROMA,
  HUE,
)
const foregroundContrast = oklch(SURFACE, FOREGROUND_CHROMA, HUE)

// Brand and status.
const primary = oklch(0.76, 0.15, HUE)
const primaryForeground = oklch(Math.min(SURFACE, FOREGROUND_LIGHTNESS), CHROMA * 0.45, HUE)
const warning = oklch(0.8, EXPRESSIVE_CHROMA, 75)
const destructive = oklch(0.75, EXPRESSIVE_CHROMA, 25)
const onFill = (l, h) => oklch(0.12, EXPRESSIVE_CHROMA * 0.08, h)

// `serious` is the one status role the substrate has no family for. Built on the
// substrate's own expressive construction -- fixed lightness, the shared expressive
// chroma, a hue between warning's 75 and destructive's 25 and inside neither clamp.
const serious = oklch(0.77, EXPRESSIVE_CHROMA, 45)

// Per-theme literal scales, verbatim from theme.css.
const brandDefault = hsl(153.1, 60.2, 52.7)
const brandLink = hsl(155, 100, 38.6)
const brand600 = hsl(154.9, 59.5, 70)
const brand500 = hsl(154.9, 100, 19.2)
const brand400 = hsl(155.5, 100, 9.6)
const brand300 = hsl(155.1, 100, 8)
const brand200 = hsl(162, 100, 2)
const warning600 = hsl(38.9, 100, 42.9)
const warning500 = hsl(34.8, 90.9, 21.6)
const warning400 = hsl(33.2, 100, 14.5)
const warning300 = hsl(32.3, 100, 10.2)
const warning200 = hsl(36.6, 100, 8)
const destructiveDefault = hsl(10.2, 77.9, 53.9)
const destructive600 = hsl(9.7, 85.2, 62.9)
const destructive500 = hsl(7.9, 71.6, 29)
const destructive400 = hsl(6.7, 60, 20.6)
const destructive300 = hsl(7.5, 51.3, 15.3)
const destructive200 = hsl(10.9, 23.4, 9.2)

// The four status roles, mark / ink / surface. Three take a substrate family whole;
// `serious` takes the substrate's construction on a hue the substrate does not use.
const STATUS = [
  ['good', brandDefault, brand600, brand400],
  ['warning', warning600, warning, warning400],
  ['serious', oklch(0.66, 0.16, 45), serious, oklch(0.26, 0.055, 45)],
  ['critical', destructiveDefault, destructive, destructive400],
]

// The series palette is unchanged and stays ours; only its plotting surface moved.
const SERIES = [
  ['1 aqua', '#199e70'],
  ['2 orange', '#d95926'],
  ['3 blue', '#3987e5'],
  ['4 green', '#008300'],
  ['5 magenta', '#d55181'],
  ['6 yellow', '#c98500'],
  ['7 violet', '#9085e9'],
  ['8 red', '#e66767'],
]

function parseHex(s) {
  return [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))
}

// -- report -------------------------------------------------------------------------

const DEPTHS = [
  ['background', background],
  ['card', card],
  ['popover', popover],
  ['secondary', secondary],
]

const FLOOR = 5.05
const NON_TEXT_FLOOR = 3

function line(label, value) {
  console.log(`${label.padEnd(34)} ${value}`)
}

console.log('\n== declared values ==\n')
const DECLARED = [
  ['--background', background],
  ['--card', card],
  ['--popover', popover],
  ['--secondary', secondary],
  ['--foreground', foreground],
  ['--muted-foreground (foreground-light)', mutedForeground],
  ['--tertiary-foreground (lighter)', tertiaryForeground],
  ['--foreground-contrast', foregroundContrast],
  ['--primary', primary],
  ['--primary-foreground', primaryForeground],
  ['--warning', warning],
  ['--destructive', destructive],
  ['--warning-foreground', onFill(0.8, 75)],
  ['--destructive-foreground', onFill(0.75, 25)],
  ['serious mark (ours, their construction)', oklch(0.66, 0.16, 45)],
  ['serious-ink (ours, their construction)', serious],
  ['serious-surface (ours)', oklch(0.26, 0.055, 45)],
  ['--brand-default', brandDefault],
  ['--brand-link', brandLink],
  ['--brand-600', brand600],
  ['--brand-500', brand500],
  ['--brand-400', brand400],
  ['--brand-300', brand300],
  ['--brand-200', brand200],
  ['--warning-600', warning600],
  ['--warning-500', warning500],
  ['--warning-400', warning400],
  ['--warning-300', warning300],
  ['--warning-200', warning200],
  ['--destructive-default', destructiveDefault],
  ['--destructive-600', destructive600],
  ['--destructive-500', destructive500],
  ['--destructive-400', destructive400],
  ['--destructive-300', destructive300],
  ['--destructive-200', destructive200],
]
for (const [name, rgb] of DECLARED) line(name, hex(rgb))

console.log('\n== alpha tokens, as declared ==\n')
for (const [name, a] of Object.entries(ALPHA)) {
  line(`--${name} alpha`, `${(a * 100).toFixed(4)}%`)
}

console.log('\n== composited state fills, per backdrop ==\n')
for (const [name, alpha] of [
  ['muted / surface-subtle', ALPHA.muted],
  ['accent / surface-emphasis', ALPHA.accent],
  ['tertiary', ALPHA.tertiary],
]) {
  for (const [dname, d] of DEPTHS) {
    line(`${name} over ${dname}`, hex(over(foreground, d, alpha)))
  }
}

console.log('\n== ink on surface, WCAG (floor 5.05) ==\n')
const INKS = [
  ['ink / foreground', foreground],
  ['ink-secondary / foreground-light', mutedForeground],
  ['ink-muted / foreground-lighter', tertiaryForeground],
  ['brand / primary', primary],
  ['brand-600', brand600],
  ['brand-link', brandLink],
  ['warning-ink', warning],
  ['critical-ink / destructive', destructive],
  ['good-ink / brand-600', brand600],
  ['serious-ink', serious],
]
const SURFACES = [
  ...DEPTHS,
  ['subtle/bg', over(foreground, background, ALPHA.muted)],
  ['subtle/card', over(foreground, card, ALPHA.muted)],
  ['emph/bg', over(foreground, background, ALPHA.accent)],
  ['emph/card', over(foreground, card, ALPHA.accent)],
]
console.log(
  'ink'.padEnd(34) + SURFACES.map(([n]) => n.padStart(11)).join(''),
)
const belowFloor = []
for (const [iname, ink] of INKS) {
  const cells = SURFACES.map(([sname, s]) => {
    const r = ratio(ink, s)
    if (r < FLOOR) belowFloor.push(`${iname} on ${sname}: ${fmt(r)}`)
    return fmt(r).padStart(11)
  })
  console.log(iname.padEnd(34) + cells.join(''))
}

console.log('\n== status ink on its own tint ==\n')
for (const [name, mark, ink, tint] of STATUS) {
  const r = ratio(ink, tint)
  line(`${name}-ink on ${name}-surface`, fmt(r) + (r < FLOOR ? '   << below 5.05' : ''))
  line(`  ink on ${name}-surface`, fmt(ratio(foreground, tint)))
  line(`  ${name} mark / ink / surface`, `${hex(mark)}  ${hex(ink)}  ${hex(tint)}`)
}
line('brand on brand-surface (brand-400)', fmt(ratio(brandDefault, brand400)))
line('brand-link on background', fmt(ratio(brandLink, background)))

console.log('\n== on-fill inks (a solid status fill) ==\n')
line('warning-foreground on warning', fmt(ratio(onFill(0.8, 75), warning)))
line('destructive-foreground on destructive', fmt(ratio(onFill(0.75, 25), destructive)))
line('primary-foreground on primary', fmt(ratio(primaryForeground, primary)))
line('foreground-contrast on foreground', fmt(ratio(foregroundContrast, foreground)))

console.log('\n== non-text, against the 3:1 floor ==\n')
for (const [name, alpha] of [
  ['border / line', ALPHA.border],
  ['input / line-strong', ALPHA.input],
  ['border-overlay', ALPHA.borderOverlay],
  ['border-stronger', ALPHA.borderStronger],
]) {
  for (const [dname, d] of DEPTHS) {
    const r = ratio(over(foreground, d, alpha), d)
    line(`${name} on ${dname}`, `${hex(over(foreground, d, alpha))}  ${fmt(r)}` +
      (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
  }
}
for (const [dname, d] of DEPTHS) {
  const composed = over(primary, d, ALPHA.ring)
  const r = ratio(composed, d)
  line(`ring (primary @55%) on ${dname}`, `${hex(composed)}  ${fmt(r)}` +
    (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
}
for (const [dname, d] of DEPTHS) {
  const r = ratio(primary, d)
  line(`ring at full strength on ${dname}`, fmt(r))
}

console.log('\n== the status marks, 3:1 against the card ==\n')
for (const [name, mark] of STATUS.map((entry) => [entry[0], entry[1]])) {
  const r = ratio(mark, card)
  line(`${name} mark on card`, fmt(r) + (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
}
line('brand mark on card', fmt(ratio(brandDefault, card)))
line('line-strong, the deviation', hex(oklch(0.578, FOREGROUND_CHROMA, HUE)))
for (const [dname, d] of DEPTHS) {
  line(`  on ${dname}`, fmt(ratio(oklch(0.578, FOREGROUND_CHROMA, HUE), d)))
}

console.log('\n== the series palette against its new plotting surface ==\n')
for (const [name, value] of SERIES) {
  const rgb = parseHex(value)
  const r = ratio(rgb, card)
  line(`series-${name} on card`, fmt(r) + (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
}

console.log('\n== in-segment label ink, per series fill ==\n')
for (const [name, value] of SERIES) {
  const rgb = parseHex(value)
  line(
    `series-${name}`,
    `Lf ${relativeLuminance(rgb).toFixed(4)}  vs black ${fmt(ratio([0, 0, 0], rgb))}  vs white ${fmt(ratio([255, 255, 255], rgb))}`,
  )
}

console.log('\n== pairings below the 5.05 text floor ==\n')
if (belowFloor.length === 0) console.log('  none')
else for (const entry of belowFloor) console.log('  ' + entry)
console.log('')

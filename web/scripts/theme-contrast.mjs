/**
 * Resolves the Supabase dark theme and emits every colour `web/src/index.css` declares,
 * then measures every pairing `DESIGN.md` publishes against the console's 5.05:1 text
 * floor and its 3:1 non-text floor.
 *
 * The inputs are the eight generator parameters `web/src/vendor/supabase/theme.css`
 * carries for `.dark`; the derivations are transcribed from the same commit's
 * `packages/ui/build/css/source/semantic.css` and `compat.css`.
 *
 * **One source of truth, deliberately.** Each token is declared once below, as numbers.
 * The same declaration produces both the CSS literal printed under `== declarations ==`
 * and the sRGB bytes every ratio is computed over, so a figure in `DESIGN.md` can never
 * describe a colour different from the one `index.css` ships. The declarations block is
 * meant to be pasted into `index.css` verbatim; if the two ever differ, this file is
 * right and that one is stale.
 *
 * Alpha is composited in gamma-encoded sRGB, not in linear light or in OKLCH, because
 * that is what a browser does to `background-color` and the three disagree visibly. A
 * ratio computed the other way would not describe the screen.
 *
 * The type ramp is not here. It is `apps/studio/styles/globals.css` carried across as
 * lengths, with no arithmetic to reproduce and nothing to measure a contrast against;
 * `DESIGN.md`'s Type section names the source and the one rule that shapes the line
 * boxes.
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

function clamp01(v) {
  return Math.max(0, Math.min(1, v))
}

function clamp255(v) {
  return Math.max(0, Math.min(255, v))
}

/** OKLCH (L 0..1, C, H degrees) to sRGB bytes. */
function oklchBytes(l, c, h) {
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

/** HSL (H degrees, S percent, L percent) to sRGB bytes, the spelling theme.css uses. */
function hslBytes(h, s, l) {
  const sN = s / 100
  const lN = l / 100
  const k = (n) => (n + h / 30) % 12
  const a = sN * Math.min(lN, 1 - lN)
  const f = (n) => lN - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  return [f(0), f(8), f(4)].map((v) => clamp255(Math.round(v * 255)))
}

function hexBytes(s) {
  return [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16))
}

function hex(bytes) {
  return '#' + bytes.map((v) => v.toString(16).padStart(2, '0')).join('')
}

/** Source over backdrop at `alpha`, in gamma-encoded sRGB -- what a browser does. */
function over(source, backdrop, alpha) {
  return source.map((v, i) => Math.round(v * alpha + backdrop[i] * (1 - alpha)))
}

function relativeLuminance(bytes) {
  const [r, g, b] = bytes.map((v) => linearFromSrgb(v / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(a, b) {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

function fmt(n) {
  return n.toFixed(2)
}

// Float arithmetic on the parameters below lands on values like 0.0014850000000000002.
// Both the literal and the measurement round through here, so neither can carry the tail.
function num(v) {
  return String(parseFloat(v.toFixed(6)))
}

function pct(v) {
  return String(parseFloat((v * 100).toFixed(4))) + '%'
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

const TONE_SPAN = FOREGROUND_LIGHTNESS - SURFACE
const E1 = 1
const E2 = 1.5
const E3 = 2
const CONTRAST_BORDER_FLOOR = 0.05
const CONTRAST_BORDER_LINEAR = CONTRAST_BORDER_FLOOR + (1 - CONTRAST_BORDER_FLOOR) * CONTRAST
const CONTRAST_BORDER = CONTRAST_BORDER_LINEAR * CONTRAST_BORDER_LINEAR
const OVERLAY_UNIT = ELEVATION_STEP / Math.abs(TONE_SPAN)

const SURFACE_CHROMA = CHROMA * 0.5
const FOREGROUND_CHROMA = CHROMA * 0.55
const PRIMARY_FOREGROUND_CHROMA = CHROMA * 0.45
const BORDER_CHROMA = FOREGROUND_CHROMA * 0.54
const INPUT_CHROMA = FOREGROUND_CHROMA * 0.5
const EXPRESSIVE_CHROMA = 0.14

const MUTED_ALPHA = OVERLAY_UNIT * E1
const ACCENT_ALPHA = OVERLAY_UNIT * E2
const BORDER_ALPHA = 0.02 + 0.2 * CONTRAST_BORDER
const BORDER_OVERLAY_ALPHA = 0.04 + 0.34 * CONTRAST_BORDER
const BORDER_STRONGER_ALPHA = 0.05 + 0.45 * CONTRAST_BORDER

// -- the declarations ----------------------------------------------------------------
//
// `decl` is the only place a token is created. It stores the literal and the bytes side
// by side, so the printed CSS and the measured colour cannot drift apart.

const ORDER = []
const D = {}

function decl(group, name, entry) {
  ORDER.push([group, name])
  D[name] = entry
  return entry
}

function ok(l, c, h) {
  return { css: `oklch(${num(l)} ${num(c)} ${num(h)})`, bytes: oklchBytes(l, c, h), alpha: 1 }
}

function okAlpha(l, c, h, a) {
  return {
    css: `oklch(${num(l)} ${num(c)} ${num(h)} / ${pct(a)})`,
    bytes: oklchBytes(l, c, h),
    alpha: a,
  }
}

function hsl(h, s, l) {
  return { css: `hsl(${num(h)} ${num(s)}% ${num(l)}%)`, bytes: hslBytes(h, s, l), alpha: 1 }
}

function literal(value) {
  return { css: value, bytes: hexBytes(value), alpha: 1 }
}

function raw(value, bytes, alpha) {
  return { css: value, bytes, alpha }
}

// Depth: four opaque steps, --surface plus --elevation-step * ratio.
const background = decl('depth', '--color-background', ok(SURFACE, SURFACE_CHROMA, HUE))
const card = decl('depth', '--color-card', ok(SURFACE + ELEVATION_STEP * E1, SURFACE_CHROMA, HUE))
const popover = decl('depth', '--color-popover', ok(SURFACE + ELEVATION_STEP * E2, SURFACE_CHROMA, HUE))
const secondary = decl('depth', '--color-secondary', ok(SURFACE + ELEVATION_STEP * E3, SURFACE_CHROMA, HUE))
decl('depth', '--color-surface-sunken', background)
decl('depth', '--color-surface', card)

// Ink: three neutral levels, --surface + --tone-span * level.
const foreground = ok(SURFACE + TONE_SPAN, FOREGROUND_CHROMA, HUE)
const inkMuted = ok(SURFACE + TONE_SPAN * MUTED_FOREGROUND_LEVEL, FOREGROUND_CHROMA, HUE)
const inkSecondary = ok(SURFACE + TONE_SPAN * TERTIARY_FOREGROUND_LEVEL, FOREGROUND_CHROMA, HUE)

// State: two foreground overlays.
const surfaceSubtle = decl(
  'state',
  '--color-muted',
  okAlpha(SURFACE + TONE_SPAN, FOREGROUND_CHROMA, HUE, MUTED_ALPHA),
)
const surfaceEmphasis = decl(
  'state',
  '--color-accent',
  okAlpha(SURFACE + TONE_SPAN, FOREGROUND_CHROMA, HUE, ACCENT_ALPHA),
)
decl('state', '--color-surface-subtle', surfaceSubtle)
decl('state', '--color-surface-emphasis', surfaceEmphasis)

decl('ink', '--color-foreground', foreground)
decl('ink', '--color-foreground-light', inkMuted)
decl('ink', '--color-foreground-lighter', inkSecondary)
decl('ink', '--color-foreground-muted', inkSecondary)
decl('ink', '--color-muted-foreground', inkMuted)
decl('ink', '--color-ink', foreground)
decl('ink', '--color-ink-muted', inkMuted)
decl('ink', '--color-ink-secondary', inkSecondary)
decl('ink', '--color-graphics', inkMuted)
decl('ink', '--color-card-foreground', foreground)
decl('ink', '--color-popover-foreground', foreground)
decl('ink', '--color-secondary-foreground', foreground)
decl('ink', '--color-accent-foreground', foreground)

// Boundaries. `--color-input` is deviation 1: the substrate's neutral hue and foreground
// chroma at the lightness this contract's 3:1 requirement needs. `--color-ring` is
// deviation 2: upstream's 55% alpha removed. Both are argued in DESIGN.md.
const LINE_STRONG_LIGHTNESS = 0.578
const line = decl(
  'boundary',
  '--color-border',
  okAlpha(SURFACE + TONE_SPAN, BORDER_CHROMA, HUE, BORDER_ALPHA),
)
const lineStrong = decl('boundary', '--color-input', ok(LINE_STRONG_LIGHTNESS, FOREGROUND_CHROMA, HUE))
decl('boundary', '--color-line', line)
decl('boundary', '--color-line-strong', lineStrong)
decl('boundary', '--color-border-control', lineStrong)
const borderOverlay = decl(
  'boundary',
  '--color-border-overlay',
  okAlpha(SURFACE + TONE_SPAN, INPUT_CHROMA, HUE, BORDER_OVERLAY_ALPHA),
)
const borderStronger = decl(
  'boundary',
  '--color-border-stronger',
  okAlpha(SURFACE + TONE_SPAN, INPUT_CHROMA, HUE, BORDER_STRONGER_ALPHA),
)
const primary = ok(0.76, 0.15, HUE)
decl('boundary', '--color-ring', primary)

// Brand.
decl('brand', '--color-primary', primary)
const primaryForeground = decl(
  'brand',
  '--color-primary-foreground',
  ok(Math.min(SURFACE, FOREGROUND_LIGHTNESS), PRIMARY_FOREGROUND_CHROMA, HUE),
)
const brandDefault = decl('brand', '--color-brand', hsl(153.1, 60.2, 52.7))
const brandLink = decl('brand', '--color-brand-link', hsl(155, 100, 38.6))
const brand600 = decl('brand', '--color-brand-600', hsl(154.9, 59.5, 70))
decl('brand', '--color-brand-500', hsl(154.9, 100, 19.2))
const brand400 = decl('brand', '--color-brand-400', hsl(155.5, 100, 9.6))
decl('brand', '--color-brand-300', hsl(155.1, 100, 8))
decl('brand', '--color-brand-200', hsl(162, 100, 2))
decl('brand', '--color-brand-surface', brand400)

// Status. `serious` is deviation 3: the substrate's own expressive construction on a hue
// between warning's 75 and destructive's 25, inside neither clamp.
const warningInk = ok(0.8, EXPRESSIVE_CHROMA, 75)
const criticalInk = ok(0.75, EXPRESSIVE_CHROMA, 25)
const seriousInk = ok(0.77, EXPRESSIVE_CHROMA, 45)
const seriousMark = ok(0.66, 0.16, 45)
const seriousSurface = ok(0.26, 0.055, 45)
const warningSurface = hsl(33.2, 100, 14.5)
const criticalSurface = hsl(6.7, 60, 20.6)
const criticalMark = hsl(10.2, 77.9, 53.9)
const warningMark = hsl(38.9, 100, 42.9)

decl('status', '--color-good', brandDefault)
decl('status', '--color-good-ink', brand600)
decl('status', '--color-good-surface', brand400)
decl('status', '--color-warning', warningInk)
decl('status', '--color-warning-ink', warningInk)
decl('status', '--color-warning-surface', warningSurface)
const warningForeground = decl(
  'status',
  '--color-warning-foreground',
  ok(0.12, EXPRESSIVE_CHROMA * 0.08, 75),
)
decl('status', '--color-serious', seriousMark)
decl('status', '--color-serious-ink', seriousInk)
decl('status', '--color-serious-surface', seriousSurface)
decl('status', '--color-critical', criticalMark)
decl('status', '--color-critical-ink', criticalInk)
decl('status', '--color-critical-surface', criticalSurface)
decl('status', '--color-destructive', criticalInk)
const destructiveForeground = decl(
  'status',
  '--color-destructive-foreground',
  ok(0.12, EXPRESSIVE_CHROMA * 0.08, 25),
)

decl('scale', '--color-warning-600', warningMark)
decl('scale', '--color-warning-500', hsl(34.8, 90.9, 21.6))
decl('scale', '--color-warning-400', warningSurface)
decl('scale', '--color-warning-300', hsl(32.3, 100, 10.2))
decl('scale', '--color-warning-200', hsl(36.6, 100, 8))
decl('scale', '--color-destructive-600', hsl(9.7, 85.2, 62.9))
decl('scale', '--color-destructive-500', hsl(7.9, 71.6, 29))
decl('scale', '--color-destructive-400', criticalSurface)
decl('scale', '--color-destructive-300', hsl(7.5, 51.3, 15.3))
decl('scale', '--color-destructive-200', hsl(10.9, 23.4, 9.2))

decl('sidebar', '--color-sidebar', background)
decl('sidebar', '--color-sidebar-foreground', foreground)
decl('sidebar', '--color-sidebar-accent', surfaceEmphasis)
decl('sidebar', '--color-sidebar-accent-foreground', foreground)
decl('sidebar', '--color-sidebar-border', line)
decl('sidebar', '--color-sidebar-ring', primary)

decl('compat', '--background-color-overlay', secondary)
decl('compat', '--background-color-overlay-hover', surfaceEmphasis)
decl('compat', '--background-color-selection', surfaceEmphasis)
decl('compat', '--background-color-alternative', background)
decl('compat', '--background-color-surface-100', card)
decl('compat', '--background-color-surface-200', surfaceSubtle)
decl('compat', '--border-color-control', lineStrong)
decl('compat', '--border-color-strong', lineStrong)
decl('compat', '--border-color-stronger', borderStronger)
decl('compat', '--border-color-overlay', borderOverlay)
decl('compat', '--color-background-overlay', secondary)

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
for (const [name, value] of SERIES) {
  decl('series', `--color-series-${name.split(' ')[0]}`, literal(value))
}

decl('chart', '--color-chart-grid', ok(0.29, SURFACE_CHROMA, HUE))
decl('chart', '--color-chart-axis', ok(0.42, SURFACE_CHROMA, HUE))
decl('chart', '--color-chart-label-on-light', literal('#000000'))

// The drop colour of the floating level. Not derived from anything: it is black at the
// opacity a drop shadow needs, and it exists only so `--shadow-float` can reach a colour
// token instead of baking a literal into the compiled class.
decl('chart', '--color-shadow', raw('oklch(0 0 0 / 0.72)', [0, 0, 0], 0.72))

// -- report ---------------------------------------------------------------------------

const DEPTHS = [
  ['background', background.bytes],
  ['card', card.bytes],
  ['popover', popover.bytes],
  ['secondary', secondary.bytes],
]

const FLOOR = 5.05
const NON_TEXT_FLOOR = 3

function line2(label, value) {
  console.log(`${label.padEnd(38)} ${value}`)
}

function composite(token, backdrop) {
  return token.alpha === 1 ? token.bytes : over(token.bytes, backdrop, token.alpha)
}

console.log('\n== declarations -- this block is what index.css carries ==\n')
let group = null
for (const [g, name] of ORDER) {
  if (g !== group) {
    console.log('')
    group = g
  }
  console.log(`  ${name}: ${D[name].css};`)
}

console.log('\n\n== resolved to sRGB ==\n')
for (const [, name] of ORDER) {
  const t = D[name]
  line2(name, t.alpha === 1 ? hex(t.bytes) : `${hex(t.bytes)} at ${pct(t.alpha)}`)
}

console.log('\n== composited state fills, per backdrop ==\n')
for (const [name, token] of [
  ['surface-subtle', surfaceSubtle],
  ['surface-emphasis', surfaceEmphasis],
]) {
  for (const [dname, d] of DEPTHS) {
    line2(`${name} over ${dname}`, hex(composite(token, d)))
  }
}

console.log('\n== ink on surface, WCAG (floor 5.05) ==\n')
const INKS = [
  ['ink', foreground],
  ['ink-muted', inkMuted],
  ['ink-secondary', inkSecondary],
  ['primary', primary],
  ['brand-link', brandLink],
  ['good-ink', brand600],
  ['warning-ink', warningInk],
  ['serious-ink', seriousInk],
  ['critical-ink', criticalInk],
]
const SURFACES = [
  ...DEPTHS,
  ['subtle/bg', composite(surfaceSubtle, background.bytes)],
  ['subtle/card', composite(surfaceSubtle, card.bytes)],
  ['emph/bg', composite(surfaceEmphasis, background.bytes)],
  ['emph/card', composite(surfaceEmphasis, card.bytes)],
]
console.log('ink'.padEnd(38) + SURFACES.map(([n]) => n.padStart(12)).join(''))
const belowFloor = []
for (const [iname, ink] of INKS) {
  const cells = SURFACES.map(([sname, s]) => {
    const r = ratio(ink.bytes, s)
    if (r < FLOOR) belowFloor.push(`${iname} on ${sname}: ${fmt(r)}`)
    return fmt(r).padStart(12)
  })
  console.log(iname.padEnd(38) + cells.join(''))
}

console.log('\n== status ink on its own tint ==\n')
const STATUS = [
  ['good', brandDefault, brand600, brand400],
  ['warning', warningMark, warningInk, warningSurface],
  ['serious', seriousMark, seriousInk, seriousSurface],
  ['critical', criticalMark, criticalInk, criticalSurface],
]
for (const [name, , ink, tint] of STATUS) {
  const r = ratio(ink.bytes, tint.bytes)
  line2(`${name}-ink on ${name}-surface`, fmt(r) + (r < FLOOR ? '   << below 5.05' : ''))
  line2(`  ink on ${name}-surface`, fmt(ratio(foreground.bytes, tint.bytes)))
}
line2('brand on brand-surface', fmt(ratio(brandDefault.bytes, brand400.bytes)))

console.log('\n== on-fill inks (a solid status fill) ==\n')
line2('warning-foreground on warning', fmt(ratio(warningForeground.bytes, warningInk.bytes)))
line2('destructive-foreground on destructive', fmt(ratio(destructiveForeground.bytes, criticalInk.bytes)))
line2('primary-foreground on primary', fmt(ratio(primaryForeground.bytes, primary.bytes)))

console.log('\n== non-text, against the 3:1 floor ==\n')
for (const [name, token] of [
  ['line (a hairline)', line],
  ['border-overlay (a hairline)', borderOverlay],
  ['border-stronger (a hairline)', borderStronger],
  ['line-strong / input, as declared', lineStrong],
  ['ring, as declared', primary],
]) {
  const cells = DEPTHS.map(([, d]) => fmt(ratio(composite(token, d), d)).padStart(9))
  console.log(name.padEnd(38) + cells.join(''))
}
// The two upstream forms this contract refuses, kept measured rather than described.
const upstreamInput = okAlpha(SURFACE + TONE_SPAN, INPUT_CHROMA, HUE, 0.03 + 0.38 * CONTRAST_BORDER)
const upstreamRing = okAlpha(0.76, 0.15, HUE, 0.55)
for (const [name, token] of [
  ['line-strong, as upstream derives it', upstreamInput],
  ['ring, as upstream derives it (55%)', upstreamRing],
]) {
  const cells = DEPTHS.map(([, d]) => fmt(ratio(composite(token, d), d)).padStart(9))
  console.log(name.padEnd(38) + cells.join(''))
}

console.log('\n== the status marks, 3:1 against the card ==\n')
for (const [name, mark] of STATUS.map((entry) => [entry[0], entry[1]])) {
  const r = ratio(mark.bytes, card.bytes)
  line2(`${name} mark on card`, fmt(r) + (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
}
line2('brand mark on card', fmt(ratio(brandDefault.bytes, card.bytes)))

console.log('\n== the series palette against its plotting surface ==\n')
for (const [name, value] of SERIES) {
  const bytes = hexBytes(value)
  const r = ratio(bytes, card.bytes)
  line2(`series-${name} on card`, fmt(r) + (r < NON_TEXT_FLOOR ? '   << below 3:1' : ''))
}

console.log('\n== in-segment label ink, per series fill ==\n')
for (const [name, value] of SERIES) {
  const bytes = hexBytes(value)
  line2(
    `series-${name}`,
    `Lf ${relativeLuminance(bytes).toFixed(4)}  vs black ${fmt(ratio([0, 0, 0], bytes))}` +
      `  vs white ${fmt(ratio([255, 255, 255], bytes))}`,
  )
}

console.log('\n== pairings below the 5.05 text floor ==\n')
if (belowFloor.length === 0) console.log('  none')
else for (const entry of belowFloor) console.log('  ' + entry)
console.log('')

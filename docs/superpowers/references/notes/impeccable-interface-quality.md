# Impeccable, audited for the operator console

Reference: [pbakaus/impeccable](https://github.com/pbakaus/impeccable). First audited 2026-08-04
from the README and the GitHub API. Re-audited the same day from a shallow clone at commit
`620ba1f`, reading the detector's own source, running it, and reading the console it is meant to be
pointed at. Where the two passes disagree, this note says so and shows what was read.

**What changed in the second pass, in one paragraph.** The first pass's structural reading of the
project was right: 59 rules, split 32 `slop` and 27 `quality`, and Sync wants the second category.
Its selection of ten questions was mostly wrong, because eight of the ten were chosen from
one-line rule *descriptions* rather than from the code that implements them, and four of those
descriptions do not describe what the code does. Two of the ten name defects this console cannot
have, one names a defect it has already fixed, and one names a defect the detector is structurally
incapable of seeing on a shadcn table. Two more turn out to be live, currently-failing defects
that the first pass ranked near the bottom. The checklist at the end of this note is seven items,
not ten, and every one of them is tied to a line of the console's own source.

## 1. What this reference actually is

Impeccable is a design-guidance package for AI coding harnesses. It installs one skill into Claude
Code, Cursor, Codex and eleven other tools, gives them 23 shared design commands, and backs those
commands with a deterministic detector that scans source files or rendered pages for 59 named
interface defects.

VERIFIED from the clone: `package.json` declares `name: impeccable`, `version: 3.5.0`,
`license: Apache-2.0`, `engines.node: >=22.18.0`, a `bin` entry at `cli/bin/cli.js`, six runtime
dependencies (`css-select`, `css-tree`, `domutils`, `fflate`, `htmlparser2`, `marked`) and
`puppeteer ^25.1.0` under **optional** dependencies. The command count is 23, read from
`skill/scripts/command-metadata.json`: `craft, init, document, extract, live, adapt, animate, audit,
bolder, clarify, colorize, critique, delight, distill, harden, onboard, layout, optimize, overdrive,
polish, quieter, shape, typeset`. The project is large and active (REPORTED via the GitHub API on
2026-08-04 — 55,055 stars, 3,323 forks, 46 open issues, created 2025-11-16, last pushed the same
day, not archived).

The rule registry is `cli/engine/registry/antipatterns.mjs`, 617 lines, and it is the canonical
copy: the fourteen `.<harness>/skills/impeccable/scripts/detector/registry/antipatterns.mjs` files
are byte-identical to it (VERIFIED by `diff`). Counting the array by importing it rather than by
eye gives exactly 59 rules, 32 `category: slop` and 27 `category: quality`, so the first pass's
count and the README's advertised number both hold.

The split is the fact that decides how Sync uses this. The `slop` rules detect that a page *looks
machine-generated* — gradient text, purple-and-cyan palettes, hero eyebrow chips, radial glow
washes, italic serif display type. The `quality` rules detect that a page is *measurably hard to
read or broken* — contrast below WCAG AA, text spilling its container, headings that skip a level,
content invisible at rest. Sync wants the second category and almost none of the first.

What the second pass adds to that picture is scale. The registry is 28 KB of descriptions; the
implementation behind it, `cli/engine/rules/checks.mjs`, is 257 KB and roughly 8,000 lines, plus
83 KB of browser-injected code in `cli/engine/browser/injected/index.mjs`. **Which parts I read:**
the registry end to end; `cli/engine/cli/main.mjs` end to end (439 lines); `cli/engine/findings.mjs`
(18 lines); `cli/engine/shared/constants.mjs` (113 lines); the puppeteer and page-error sections of
`cli/engine/engines/browser/detect-url.mjs`; the config schema in `cli/lib/impeccable-config.mjs`;
and roughly 700 lines of `checks.mjs` covering the seventeen rules this note reasons about.
**Which parts I did not read:** the other ~7,300 lines of `checks.mjs`, all of the injected browser
bundle, the live-iteration server (`skill/scripts/live-server.mjs`, 70 KB), the browser extension,
and the test suite. Claims about rules outside those seventeen are registry-level only, and are
labelled as such.

## 2. What Sync should adopt

**The quality rule set as a vocabulary, with the implementing constants attached.**
Source: `cli/engine/registry/antipatterns.mjs` and `cli/engine/rules/checks.mjs` (VERIFIED). Each
rule is a stable id, a category, an optional severity, an optional scope tag, and a one-line
statement of the defect. That is the shape a tick needs, because a tick has to be able to say "this
tick fixed `skipped-heading` on the finding page" rather than "made it look better". The second
pass's amendment is that the id is worth adopting and the description is not: four of the
descriptions I checked against their implementations state a different threshold from the one the
code uses, and section 5 lists them. Where it lands: the checklist in section 6, appended to the
four questions in `docs/superpowers/loops/console-improvement-tick.md`.

**The slop/quality split as a decision, not just a taxonomy.**
Source: same registry (VERIFIED). Impeccable itself treats "this is ugly in an AI way" and "this is
unreadable" as different problems with different rules. The plan's Task 3 heading is
"The console — data-dense, unstyled beyond legibility"
(VERIFIED — `docs/superpowers/plans/2026-07-30-sync-m4-dashboard.md:217`), which is a commitment to
ignore the first and enforce the second. Where it lands: the tick's "do not restyle ahead of the
data" prohibition now has a line drawn through somebody else's rule set rather than through taste.

**The severity ladder and the audit health score, with the anti-noise rule attached.**
Source: `skill/reference/audit.md`, now VERIFIED byte for byte rather than through a WebFetch
summary. Lines 89-93 define P0 as blocking task completion, P1 as a major WCAG violation or
significant friction, P2 as having a workaround, P3 as polish with minimal user impact. Line 129
names the failure mode of the audit itself: "Be thorough but actionable. Too many P3 issues creates
noise." The first pass stopped there and missed the more transplantable artifact directly above it:
lines 63-76 define a five-dimension score (accessibility, performance, theming, responsive design,
implementation integrity), each rated 0-4, summed to a total out of 20, with bands at 18-20, 14-17,
10-13, 6-9 and 0-5. Where it lands: the tick's ledger entry. A tick that reports six P3s and no P1
has not measured anything, and a milestone that wants a single number to move should use this one
rather than invent another.

**`craft-floor.md` as the per-tick verification list, in preference to `polish.md`.**
Source: `skill/reference/craft-floor.md` (VERIFIED, read in full). The first pass cited
`polish.md`'s triage order, which is correct as far as it goes — lines 39-45 rank broken tasks and
misleading state first, missing states second, flow and hierarchy third, visual and motion
inconsistencies fourth, cleanup fifth. But `craft-floor.md` is the file written to be run against a
built result rather than to guide a redesign, and the first pass never mentions it. Its "Verify"
section is eight checks, each phrased as an observation rather than an intention, and one of them is
the state-coverage list the first pass wanted: "**States:** hover, disabled, loading, error, empty.
Plus real content, working controls, responsive composition, keyboard focus." Its opening line also
states the anti-duplication principle a repeating loop needs: "When the design hook is active it
already enforces the mechanical checks below as you edit: act on its findings instead of
re-auditing each rule." Where it lands: the same principle governs the checklist in section 6, which
is written to sit *beside* the tick's four questions rather than to restate them.

**The detector as a standalone CLI, pointed at the running dev server — with a mandatory
precondition.**
Source: `cli/engine/cli/main.mjs` (VERIFIED, read in full). The usage line is
`impeccable detect [options] [file-or-dir-or-url...]`; it accepts `http(s)://` and `file://` URLs
directly, so a tick can run it against `http://localhost:5173` while the console is up. The flags
that matter are `--json`, `--quiet`, `--scope type,layout`, `--viewport WxH` (default `1280x800`),
`--no-config`, `--no-design-system` and `--no-advisory`. Exit code is 2 when any non-advisory
finding is present and 0 otherwise (`main.mjs:432`).

The precondition is not optional and section 5 explains why: **the URL path requires puppeteer,
puppeteer is an optional dependency, and its absence produces a green result rather than a red one.**
A tick that runs the detector without first proving the browser engine works has run nothing.
Where it lands: step 4 of the tick, "Verify before claiming", beside `npm run build`, with the
proof-of-life check written into the command rather than assumed.

**`.impeccable/config.json` as the place to record what Sync deliberately ignores.**
Source: `cli/lib/impeccable-config.mjs` (VERIFIED — the schema is documented in its header comment
and the keys are validated at `DETECTOR_CONFIG_KEYS`). The file takes
`detector.ignoreRules`, `detector.ignoreFiles`, `detector.ignoreValues` and
`detector.designSystem.enabled`, with a gitignored `config.local.json` overlay. Where it lands: if
the detector is ever wired into the tick, the 49 dropped rules belong in `ignoreRules` in a
committed file, so the decision is reviewable rather than re-argued every tick. Inline
`// impeccable-disable-next-line <rule>: reason` comments are also honoured and travel with the
file, which is the right shape for a single deliberate exception.

## 3. What to skip, and what adopting it would cost

**The 32 `slop` rules, minus one.** `hero-eyebrow-chip`, `kicker-above-heading`, `gradient-text`,
`radial-halo`, `radial-spotlight-glow`, `italic-serif-display`, `marquee`, `icon-tile-stack`,
`oversized-h1`, `ai-color-palette`, `cream-palette`, `dark-glow`, `pulsing-dot`, `bounce-easing`,
`side-tab` and their neighbours describe defects of a marketing landing page. An operator console
has no hero section, so these can only ever return zero. The concrete cost of keeping them is the
tick's attention, spent on findings that cannot occur. The exception is `flat-type-hierarchy`,
which is filed under `slop` and is one of two rules currently failing on this console; it is in the
checklist.

**The four `design-system-*` rules.** `design-system-font`, `design-system-color`,
`design-system-radius` and `design-system-font-size` validate against a `DESIGN.md` or
`.impeccable/design.json` the project supplies. VERIFIED: there is no `DESIGN.md` at this
repository's root. Adopting them means either four permanently silent rules, or writing a design
system now to feed them, which pre-empts a decision the plan explicitly defers ("Premium components,
bento grids | These are a design-system decision, and the design system comes after the data model
is visible" — VERIFIED at plan line 253). That is the cost: a detector rule driving a product
decision in the wrong order.

**`monotonous-spacing` and `cramped-padding` — dropped by the first pass for the right instinct and
the wrong reason, and now dropped for a better one: they do not fire.** The first pass predicted
both would false-positive on a dense Tailwind grid and train the tick to ignore the detector. I
tested that. `monotonous-spacing` (VERIFIED at `checks.mjs:1510-1516`) needs at least ten spacing
samples, one value accounting for more than 60% of them, **and** three or fewer distinct values
across the whole file; this console uses `p-2`, `p-4`, `px-4`, `py-3`, `py-6`, `gap-1`, `gap-2`,
`gap-3`, `gap-4`, `mt-1`, `mt-2`, `mt-3`, `mb-6` and more, so the unique-value gate alone makes it
unreachable. `cramped-padding` (VERIFIED at `checks.mjs:3209-3235`) scales with font size —
`max(4px, fontSize × 0.3)` vertically and `max(8px, fontSize × 0.5)` horizontally — and only fires
on an element with two or more borders or its own visible background; `TableCell` has `p-2` (8px),
no own background and no borders of its own, so it is not even a candidate. **Empirical
confirmation:** running `node cli/bin/cli.js detect --no-config` over a copy of the entire
`web/src` tree returned **0 findings** and exit 0. Skip both, but skip them because they are silent,
not because they are noisy.

**`docs/STYLE.md` and the four copy rules that enforce it** — `em-dash-overuse`,
`marketing-buzzword`, `aphoristic-cadence`, `theater-slop-phrase`. This remains a genuine conflict
rather than a mismatch. Impeccable's own style document prohibits em dashes outright, and this
repository's `CLAUDE.md`, its rules files and its plans use them constantly and on purpose.
The second pass adds a specific mechanical consequence: `web/src/lib/format.ts:11` defines
`ABSENT = "—"`, an em dash, rendered into every absent cell of every table. `em-dash-overuse` fires
at 8 or more em dashes at a density of roughly one per 500 characters of body text (VERIFIED —
`EM_DASH_FLOOR = 8` and `EM_DASH_CHARS_PER_DASH = 500` at `cli/engine/shared/constants.mjs:77-78`),
which a table of twenty absent values will clear comfortably. It is the only rule in the registry
carrying `advisory: true`, so it never changes the exit code, but it will appear in every JSON
report. Pass `--no-advisory`, or list it in `detector.ignoreRules`, and say why in the config file.

## 4. Who should consult this, and what it answers

**Primary consumer: the M4 console improvement tick,
`docs/superpowers/loops/console-improvement-tick.md`.** Its reference table already routes
"interface quality, polish, the details that separate a tool from a demo" to this repository. The
question this note answers for that tick is: *when questions 1 through 4 all answer yes, what is the
tick's work?* Before this note the honest answer was "taste", which the loop's own step 2 forbids.
Now it is the first item in section 6 that answers no. Read section 6, and read section 5 once, when
first wiring the detector in. Sections 1 through 3 exist so a milestone can decide whether the tool
is worth installing, and that is a once-per-milestone question.

**Secondary consumer: whichever slice finally builds the design system** — the deferred row reading
"Premium components, bento grids". The question it answers there is what the design system must
*not* do, since the 32 `slop` rules are a well-catalogued list of the reflexes an AI-authored design
system reaches for first. That consultation is worth having when the design system is being
designed, and is noise before then. `skill/reference/craft-floor.md` is the file to read at that
point rather than the registry, because its "Refuse" section states each reflex as a decision with
an escape clause ("These are the category's defaults, not bans: the brief's own words can earn any
of them") rather than as a detector rule.

**Not relevant to:** anything under `src/sync/`. The detector reads rendered HTML, CSS and frontend
source; it has no view on the graph, the pipeline stages, the vendor adapters or the remediation
loop. A backend milestone consulting this reference will find nothing, and should say so rather
than look harder.

## 5. What the source says that the documentation does not

This section is the reason for the second pass. Every item here was invisible from the README, the
rule descriptions, and the CLI help text, and four of them change what the tick should do.

**A URL scan without puppeteer exits 0 and reports nothing. It fails as a pass.**
This is the most important thing in the note. `cli/engine/engines/browser/detect-url.mjs:171-181`
imports puppeteer inside a `try` and throws a clear, well-worded error when the import fails:
`'puppeteer is required for URL scanning. Install: npm install puppeteer'`. But
`cli/engine/cli/main.mjs:309-315` wraps the whole URL scan in its own `try`, writes
`Error: ${e.message}` to **stderr**, and then `continue`s to the next target. With no findings
collected, line 423 falls through to line 435 and the process exits **0**. I measured this: with
puppeteer absent, `node cli/bin/cli.js detect file:///…/fixture.html` printed one line to stderr
and returned exit code 0, while the same fixture scanned as a plain path returned exit 2 with two
findings. Puppeteer is an *optional* dependency, so a plain `npm install` on a machine with a
restricted network or a `--omit=optional` policy leaves it out silently. A tick that runs the
detector against `http://localhost:5173`, checks the exit code, and records "clean" has recorded
nothing at all — which is precisely the "a detector that mostly does not detect" failure that
`CLAUDE.md` already has a standing rule about in another context. **Any tick command that scans a
URL must first assert the browser engine is present**, for example by requiring a non-zero finding
count on a known-bad fixture, or by checking `node -e "require.resolve('puppeteer')"` before the
scan.

**`severity: 'advisory'` and `advisory: true` are different things, and only one of them works.**
Eleven rules carry `severity: 'advisory'` in the registry: `blinking-cursor`,
`shape-assembled-illustration`, `numbered-section-labels`, `design-system-color`,
`design-system-radius`, `design-system-font-size`, `gpt-thin-border-wide-shadow`,
`repeating-stripes-gradient`, `codex-grid-background`, `theater-slop-phrase` and
`image-hover-transform`. Exactly one rule carries `advisory: true`: `em-dash-overuse`
(`registry/antipatterns.mjs:218`). The advisory partition that the CLI's help text describes —
separate section, never counted as a failure, never changes the exit code, suppressed by
`--no-advisory` — is driven entirely by the second flag. `findings.mjs:14` stamps
`base.advisory = true` only when `ap.advisory === true`, `main.mjs:45-47` tests only
`finding.advisory === true`, and `ADVISORY_RULE_IDS` at `registry/antipatterns.mjs:574-576` is built
by filtering on `rule.advisory === true`. So `--no-advisory` suppresses one rule, not twelve, and
the eleven `severity: 'advisory'` rules count as failures and set exit code 2. Do not plan around
`--no-advisory` as a way to quiet the advisory tier; it quiets em dashes.

**`text-overflow` cannot see a shadcn table, by design.** `checkElementTextOverflowDOM` at
`checks.mjs:4818-4823` returns an empty array if the element itself or **any ancestor** has
`overflow-x` or `overflow` set to `auto` or `scroll`, with the comment "A scrollable ancestor means
this overflow is intentional and scrollable." `web/src/components/ui/table.tsx:7-10` wraps every
table in this console in `<div data-slot="table-container" className="relative w-full
overflow-x-auto">`. Therefore no cell of any table in the operator console can ever produce a
`text-overflow` finding, no matter how far a call-site path pushes the row. The rule also needs a
spill of at least 16px (`checks.mjs:4824-4826`), which the descriptions do not mention. This is the
single biggest correction to the first pass: it made "can you read the widest table without
scrolling sideways" its third question and attributed it to `text-overflow`. The question is right
and the attribution is wrong — it is an eyes-only check.

**`low-contrast` skips a bare `<span>`, which is what the rung badge is.**
`checkColors` at `checks.mjs:85-108` returns immediately for any element whose tag is in
`SAFE_TAGS` — a set that includes `span`, `a`, `td`, `th`, `tr`, `li`, `label`, `button`, `code`
and `pre` (`shared/constants.mjs:3-9`) — unless the element paints its own background with alpha
above 0.5 or its own gradient, and carries direct text at 9px or larger.
`web/src/components/provenance.tsx:20-29` renders `RungBadge` as
`<span className="rounded border border-border px-1.5 py-0.5 font-mono text-xs">`: a border, no
background. It is never measured. The first pass made rung contrast its second question on the
strength of the one threshold it had verified, and that threshold — 4.5:1 for body text, 3.0:1 for
large text, where large is 18pt or 14pt bold converted to CSS pixels (`checks.mjs:141-142`,
`shared/constants.mjs:68-69`) — is correct but never applied to the element in question. A second
undocumented behaviour in the same area is worth knowing: `checkHoverContrast`
(`checks.mjs:213-225`) runs the same WCAG test against the element's `:hover` colours, which is a
state no screenshot captures and no rule description mentions.

**`content-hidden-at-rest` is a failed-reveal-animation detector, not a disclosure detector.**
`checkContentHiddenAtRest` at `checks.mjs:5044-5052` fires only when more than 30% of the page's
text characters remain at opacity 0 or visibility hidden **after** the URL engine has scrolled the
whole document to give every reveal handler a chance to fire, with floors of 200 total and 150
hidden characters. Crucially, `measureHiddenTextDOM` at `checks.mjs:4998-5000` marks any subtree
with `display: none`, the `hidden` attribute, `aria-hidden="true"` or `content-visibility: hidden`
as **excluded** — removed from the denominator entirely, not counted as invisible. A collapsed
accordion, a closed disclosure, an inactive tab panel: all excluded. The first pass made
"is the abandoned attempt visible without a click" its sixth question and cited this rule as the
one that would catch a collapsed-by-default accordion. It could not have. The question is a good
one and the rule is unrelated to it.

**`flat-type-hierarchy` measures the whole page's range, not the ratio between steps.** The
registry description says "aim for at least a 1.25 ratio between steps". The implementation
(`checks.mjs:4183-4188` for the static path, `3921-3926` for the browser path) collects every
distinct font size on the page from `h1-h6, p, span, a, li, td, th, label, button, div`, requires at
least three of them, and fires when `largest / smallest < 2.0`. That is a far stricter and
differently-shaped test. It matters here: this console renders at 12px, 12.8px, 14px, 16px and 18px,
giving a range ratio of 1.5. I confirmed it by running the detector over a fixture that mirrors the
finding page's DOM, and it fired: `[flat-type-hierarchy] Sizes: 12px, 14px, 16px, 18px (ratio
1.5:1)`. Raising the `h1` from `text-lg` to `text-2xl` (24px) would clear it.

**`line-length` only looks at seven tags.** `QUALITY_TEXT_TAGS` at `checks.mjs:3004` is
`{p, li, td, th, dd, blockquote, figcaption}`. A `<div>` or a `<pre>` holding a wall of text is
never measured. The estimate is `rect.width / (fontSize × 0.5)` and it fires above 85 characters
(`lineMax + 5`, `checks.mjs:3194-3198`). For this console that means the `<pre>` blocks in
`web/src/features/workflows/evidence.tsx:214` are exempt regardless of width, while the prose
paragraphs inside `web/src/components/states.tsx` and
`web/src/features/workflows/run-outcome.tsx` are the only things the rule can see — which happen to
be the console's longest strings.

**`tiny-text` is nearly inert on any real application UI; `undersized-ui-text` is the one that
bites.** `tiny-text` (`checks.mjs:3454-3460`) fires below 12px but exempts anything inside
`button, a, label, summary, pre, nav, footer`, any `[role]` control, and anything whose class
matches `badge`, `caption`, `chip`, `code`, `console`, `diff`, `label`, `meta`, `mock`, `pill`,
`preview`, `tag`, `terminal` — case-insensitively. `undersized-ui-text` (`checks.mjs:3496-3513`)
exists explicitly to close that blind spot: an 11px floor on interactive text and on structural
furniture, where furniture includes `td`, `th`, `[role="gridcell"]`, `nav`, `footer`, and any
class matching `meta`, `label`, `badge`, `timestamp` and friends. Its docstring names the live
failure it closes — a build that shipped its entire furniture layer at 8px and was waved through
because 8px had been added to the `DESIGN.md` ramp — and states that "being ON the DESIGN.md size
ramp does not exempt a value here". That is the rule worth carrying, and the description's talk of
"12px body text" is not.

**`script-error` reports at most three messages, deduplicated, first line only, truncated to 160
characters.** `detect-url.mjs:226-231` attaches the `pageerror` listener before `goto` (a syntax
error fires during the initial parse, long before load) and deduplicates by message;
`detect-url.mjs:307-309` slices the list to three. So the finding count is not the error count, and
a page throwing in a render loop reports as one finding.

**Finally, the palette in the plan is not the palette that shipped.** The first pass cited plan
lines 171-179 as evidence of "a deliberately empty `@theme` block". The plan does show an empty
block, and `web/src/index.css:8-26` ships thirteen tokens. Computing every text pairing in it from
the OKLCH values gives: `foreground` on `background` 17.72:1, `muted-foreground` on `background`
5.51:1, `muted-foreground` on `muted` 5.05:1, `muted-foreground` on `muted/50` 5.28:1,
`destructive` on `background` 6.34:1, and `destructive` on `bg-destructive/10` 5.81:1. Every one
clears WCAG AA for body text. And `web/src/index.css:3-6` pins the console to a single palette on
purpose — `@custom-variant dark (&:is(.dark *))` with no `.dark` element anywhere — so there is no
dark rendering to check. The first pass's "in both the light and dark rendering" describes a mode
this console does not have.

## 6. The checklist

Seven items, to be appended under step 2 of `docs/superpowers/loops/console-improvement-tick.md`,
after the four questions already there. They are written not to overlap those four: the tick already
asks whether a field is missing, whether provenance is rendered, whether every state says what
happened, and whether the top deferred row is ready. These ask whether what *is* rendered can
actually be read. Each is answerable yes or no by a fresh agent with the API and the dev server
running and no memory of this session. Rule ids in backticks are Impeccable's, so a finding can be
named the same way twice.

**Before the list: the one command, and its precondition.** If the detector is installed, the
fastest way to answer items 1, 3, 4, 5 and 7 at once is a URL scan of each route. It is only valid
if the browser engine actually runs:

```bash
node -e "require.resolve('puppeteer')" || echo "URL SCAN INVALID — see section 5"
npx impeccable detect --no-advisory --viewport 1280x800 \
  http://localhost:5173/ \
  http://localhost:5173/vendors/stripe \
  http://localhost:5173/findings/<id> \
  http://localhost:5173/findings/<id>/workflow
```

Exit 2 means findings; exit 0 means either clean **or** that the browser engine was missing and the
scan silently did nothing. Never record a clean result without the first line passing.

1. **Did a full walk of Codebase → API Services → Errors & Incidents → Finding → Solution Workflow
   leave the browser console empty?** (`script-error`, one of only two rules carrying
   `severity: 'error'`.) It is first because in React 19 an uncaught exception unmounts a subtree and
   leaves nothing behind, which is the silent version of the tick's own question 3: the state does
   not say what happened, because there is no state. This console has two places a transport change
   lands first — `run-outcome.tsx:121-130`, the branch for an outcome the console has never heard
   of, and `evidence.tsx:285-293`, which renders unnamed evidence keys through `JSON.stringify` —
   and both are reached by data, not by clicking. A tick that answers the other six while the
   console throws has measured the wrong thing.

2. **At a 1280px window, on the Errors & Incidents table, is the Rung column on screen without
   scrolling the table sideways?** (No rule id — see section 5; `text-overflow` is structurally
   blind to this.) `vendor-findings-table.tsx:47-87` renders seven columns, with Rung sixth, and
   `table.tsx:71,84` puts `whitespace-nowrap` on every header and cell inside a `w-full
   overflow-x-auto` container. The widest cell is `{row.file}:{row.line}`, a path supplied by a
   customer repository, and no fixture will be long enough to catch it. The failure is that the
   provenance column — the thing the tick's own question 2 declares non-negotiable — slides out of
   the viewport. Question 2 asks whether provenance is rendered; this asks whether it is visible,
   and geometry is how the answer diverges.

3. **On each page, does the heading outline descend without skipping a level?** (`skipped-heading`.)
   **This currently fails.** The finding page has `<h1>` at `finding-page.tsx:76` and `<h3>` at
   `finding-page.tsx:33`, with no `<h2>` between them, because shadcn's `CardTitle` renders a
   `<div>` (`card.tsx:36-47`) and is not a heading at all. I reproduced it: a fixture mirroring that
   DOM produced `[skipped-heading] <h1> "f-91ac" followed by <h3> "Argument keys" (missing h2)`. The
   workflow page is fine — `workflow-page.tsx:46` h1, `run-outcome.tsx:37` h2,
   `node-sequence.tsx:97` h3. It earns its place over every other accessibility rule because the
   console's navigation hierarchy *is* the dependency graph, and the heading tree is the only
   machine-readable assertion of which level of that graph you are looking at.

4. **Can you tell a page title, a card title and a row label apart at a glance?**
   (`flat-type-hierarchy`.) **This currently fails**, at a measured 1.5:1 against a threshold of
   2.0. The console lives entirely in 12px, 12.8px, 14px, 16px and 18px, and its `h1` is `text-lg`.
   This is the one `slop` rule that earns a place, because "unstyled beyond legibility" fails at
   exactly this seam: with a deliberately minimal palette and no design system, every level of a
   six-level hierarchy renders at nearly the same weight and the operator loses their place. It is
   also the cheapest of the seven to fix — one class on four `h1` elements.

5. **On a 1920px window, does the prose in an error, empty or abandoned-run panel wrap at a
   readable measure?** (`line-length`, which fires above roughly 85 characters and only inside
   `p/li/td/th/dd/blockquote/figcaption`.) The panels in `states.tsx` and `run-outcome.tsx` render
   the console's longest strings as bare `<p>` inside `max-w-7xl` — the workflow page's
   "no remediation run" explanation is over 300 characters. Tables want the whole viewport and
   paragraphs do not, and this console mixes both on one screen. Evidence nobody reads is the same
   failure as evidence not shown. The `<pre>` blocks are already correct
   (`evidence.tsx:214`, `max-h-72 overflow-auto whitespace-pre-wrap`) and are not what this asks
   about.

6. **Tab to the Next button inside a card. Is its whole focus ring visible?**
   (`clipped-overflow-container`.) `card.tsx:15` sets `overflow-hidden` on every Card in the
   console, and `button.tsx` draws focus with `focus-visible:ring-3`, which is a box-shadow and is
   therefore clipped by an ancestor's `overflow: hidden`. `PageControls` sits at the bottom edge of
   `CardContent` on both vendor tables. The rule itself fires on a positioned child escaping a
   clipping container (`checks.mjs:4693-4715`), which is the same construct seen from the DOM side;
   it also covers any future tooltip or popover added without a portal. Keyboard focus is in
   `craft-floor.md`'s States line and in nobody's screenshot.

7. **Is anything on screen rendered below 11px?** (`undersized-ui-text`, whose floor is 11px and
   whose "furniture" selector explicitly covers `td`, `th` and anything classed `meta`, `label` or
   `badge`.) Today the console's floor is `text-xs`, 12px, so this is a regression guard rather than
   a discovery. It earns its slot because the standing temptation of a data-dense console is to
   reach for `text-[10px]` the next time a table gets crowded, and because the rule's own docstring
   records that exact failure shipping once already. This is the question that says where density
   stops being density and becomes a defect.

### What was dropped from the first pass's ten, and why

- **"Does every provenance marker clear 4.5:1, in light and dark?"** Dropped on two counts. Every
  pairing in `web/src/index.css` clears AA (computed in section 5, worst case 5.05:1), and the
  console has no dark rendering to check (`index.css:3-6`). The specific element it named, the rung
  badge, is a bare `<span>` that `checkColors` skips outright (`checks.mjs:87-108`). It was a real
  question asked against a palette and a theme that do not exist.
- **"Is a failed attempt and its `abandon_reason` visible without a click?"** Dropped as already
  satisfied. `run-outcome.tsx:70-91` renders it at the top of the workflow page inside
  `border-2 border-destructive`, above the node sequence, with a named absence marker when the run
  recorded no reason. The plan's requirement — "prominently rather than in a corner", plan line 238
  — is met. The rule the first pass attached to it could not have detected the failure anyway.
- **"With a table scrolled and a dialog open, is any text painted under an opaque layer?"**
  (`text-occlusion`.) Dropped as not applicable. `table.tsx` has no `sticky` anywhere, the console
  has no dialogs, and the rule needs 30% coverage of a text run by an opaque box or 45% by another
  text run (`checks.mjs:5281`). There is nothing here for it to find.
- **"Does no multi-line block sit below 1.3 line height, and is the smallest text readable?"**
  Folded into item 7. `tight-leading` needs a run of more than 50 characters below 1.3× leading and
  this console sets no custom leading; `tiny-text` exempts virtually everything an application UI
  renders. The 11px functional floor is the part of that question with teeth.
- **The other 49 rules**, for the reasons in section 3.

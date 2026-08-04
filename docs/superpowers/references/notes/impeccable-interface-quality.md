# Impeccable, audited for the operator console

Reference: [pbakaus/impeccable](https://github.com/pbakaus/impeccable). Audited 2026-08-04 against
milestone M4, the Vite + React 19 + Tailwind v4 console in `web/`.

## 1. What this reference actually is

Impeccable is a design-guidance package for AI coding harnesses: it installs a skill into Claude
Code, Cursor, Codex and a dozen other tools, gives them 23 shared design commands such as
`/impeccable audit`, `/impeccable critique` and `/impeccable polish`, and backs those commands with
a deterministic detector that scans rendered pages or source files for 59 named interface defects
(VERIFIED — `package.json` declares `name: impeccable`, `version: 3.5.0`, `license: Apache-2.0`,
`engines.node: >=22.18.0`, and a `bin` entry at `cli/bin/cli.js`). The detector is the substantial
part and it runs offline with no API key; the command layer around it is a prompt library. The
project is large and active (REPORTED via the GitHub API — 55,030 stars, 3,321 forks, created
2025-11-16, last pushed 2026-08-04, not archived).

The important structural fact, and the one that decides how Sync should use it: the 59 rules are
split into two categories that serve different purposes. Thirty-two carry `category: slop` and
detect that a page *looks machine-generated* — gradient text, purple-and-cyan palettes, hero eyebrow
chips, radial glow washes, italic serif display type. Twenty-seven carry `category: quality` and
detect that a page is *measurably hard to read or broken* — contrast below WCAG AA, text spilling its
container, headings that skip a level, content hidden at rest. (VERIFIED — I read the rule registry
at `.agents/skills/impeccable/scripts/detector/registry/antipatterns.mjs` and counted; 32 plus 27 is
59, which matches the count the README advertises.)

Sync wants the second category and almost none of the first.

## 2. What Sync should adopt

**The quality rule set as a vocabulary.**
Source: `.agents/skills/impeccable/scripts/detector/registry/antipatterns.mjs` (VERIFIED). Each rule
is a stable id, a category, a severity, and a one-line statement of the defect. That is exactly the
shape the console improvement tick needs, because a tick has to be able to say "this tick fixed
`text-overflow` on the findings table" rather than "made it look better". Where it lands: the ten
questions in section 3 of this note, appended to the four in
`docs/superpowers/loops/console-improvement-tick.md`.

**The slop/quality split as a decision, not just a taxonomy.**
Source: same file (VERIFIED). Impeccable itself treats "this is ugly in an AI way" and "this is
unreadable" as different problems with different rules. The plan's Task 3 heading is "data-dense,
unstyled beyond legibility"
(VERIFIED — `docs/superpowers/plans/2026-07-30-sync-m4-dashboard.md:217`), which is a commitment to
ignore the first and enforce the second. Where it lands: the tick's "do not restyle ahead of the
data" prohibition now has a defensible line drawn through somebody else's rule set rather than
through taste.

**The detector as a standalone CLI, pointed at the running dev server.**
Source: `.agents/skills/impeccable/scripts/detector/cli/main.mjs` (VERIFIED — I read its help text)
and `detect-antipatterns.mjs`, which the file itself describes as usable both as an importable
library and as a standalone command-line tool. The usage line is
`impeccable detect [options] [file-or-dir-or-url...]`, and it accepts a URL target directly, so a
tick can run it against `http://localhost:5173` while the console is up. The flags that matter here
are `--json` (machine-readable findings with full metadata), `--no-advisory` (suppress the advisory
tier entirely), `--scope type,layout` (restrict to a design domain), `--viewport WxH` (default
`1280x800`), and `--no-design-system` (do not try to load a `DESIGN.md`). Where it lands: step 4 of
the tick, "Verify before claiming", beside `npm run build`. One caveat, stated because it will bite:
`package.json` lists `puppeteer ^25.1.0` under **optional** dependencies (VERIFIED), and I read
`cli/main.mjs` without finding an explicit absence check — so a URL scan on a machine where the
optional install was skipped may fail in an unhelpful way rather than degrading to static analysis.
Confirm the browser engine actually runs before writing a tick that depends on it.

**The severity ladder, with the anti-noise rule attached.**
Source: `.agents/skills/impeccable/reference/audit.md` (REPORTED — retrieved through WebFetch's
summarisation rather than read byte for byte). It defines P0 as blocking task completion, P1 as a
major WCAG violation or significant friction, P2 as having a workaround, P3 as polish with minimal
user impact, and it explicitly names "excessive P3 noise" as a failure mode of the audit itself.
Where it lands: the tick's ledger entry. A tick that reports six P3s and no P1 has not measured
anything.

**The state-coverage list from `polish.md`.**
Source: `.agents/skills/impeccable/reference/polish.md` (REPORTED, same retrieval caveat). Its
triage order puts "missing states (loading, empty, error, success, disabled, permissions)" second,
directly below broken tasks and misleading states. That list is a strict superset of the tick's
question 3, which names four sentences: no findings, API not running, finding not open, still
loading. The console additionally has a *terminal-versus-live* distinction on the workflow view
(`Task 4, Step 4: poll while a run is live; stop when it is terminal`, VERIFIED at plan line 240) and
an abandoned-attempt state, neither of which is a loading state or an error. Where it lands: question
3 of the tick should enumerate states per view rather than trusting the four sentences to cover a
view built after the sentence was written.

## 3. The ten questions, and why these ten

These are written to be appended to the four questions in
`docs/superpowers/loops/console-improvement-tick.md`, under step 2. Each is answerable yes or no by a
fresh agent with the API and the dev server running and no memory of this session. Rule ids in
backticks are Impeccable's, so a finding can be named the same way twice.

A note on thresholds before the list. I attempted to read the implementation file,
`.agents/skills/impeccable/scripts/detector/rules/checks.mjs` (252,227 bytes, VERIFIED size from the
GitHub contents API), and the retrieval returned only a partial excerpt. Two thresholds are VERIFIED
from that implementation: `low-contrast` uses `const threshold = isLargeText ? 3.0 : 4.5;` with large
text defined as 18px or 14px bold, and `monotonous-spacing` fires on
`if (dominantPct > 0.6 && unique.length <= 3)` over at least ten samples. **Every other numeric
threshold below is taken from the rule's one-line description in the registry, not from its
implementation — could not verify the implementing constants.** Treat them as the intended value and
the number to argue with, not as the number the tool will use.

1. **Did a full walk of Codebase → API Services → Errors & Incidents → Finding → Solution Workflow →
   Pull Request produce an empty browser console?** (`script-error`.) It earns first place because it
   is one of only two rules in the registry carrying severity `error` rather than `default`, and
   because in React 19 an uncaught exception unmounts a subtree and leaves nothing behind. That is the
   silent version of the tick's own question 3: the state does not say what happened, because there is
   no state. A tick that answers the other nine while the console throws has measured the wrong thing.

2. **Does every provenance marker — the `static`, `resolved`, `observed` rung and `indexed_at` —
   clear 4.5:1 against what sits behind it, in both the light and dark rendering?** (`low-contrast`,
   the one threshold verified in implementation.) It earns its place because the tick already declares
   provenance non-negotiable, and because muted secondary text on a card surface is precisely where
   an unstyled shadcn build lands near the line. A rung rendered at 3:1 is a rung the operator does
   not read, which is functionally the hiding that question 2 forbids.

3. **Can you read every column of the widest table without the page scrolling sideways, and does a
   long call-site path or vendor `operationId` wrap or truncate visibly rather than pushing the table
   wide?** (`text-overflow`.) It earns its place because the console's identifiers are unbounded
   strings supplied by a customer repository and a vendor spec, and no fixture will be long enough to
   catch it. The specific failure is that the rung column, the rightmost thing on a row, slides off
   the viewport — question 1's "a field the API returns and the console drops", achieved by geometry
   instead of by code.

4. **With a table scrolled and a dialog, tooltip or popover open, is any text painted underneath an
   opaque layer?** (`text-occlusion`.) It earns its place because sticky headers over dense rows are
   the console's default layout and the overlap is invisible until the scroll position is wrong. It is
   cheap to check and it fails in exactly the state a screenshot at rest never captures.

5. **Does every hover tooltip and dropdown escape its container fully, or does something clip it?**
   (`clipped-overflow-container`.) It earns its place as the twin of item 4 and for a Radix-specific
   reason: shadcn `Card` and any scroll region apply `overflow` rules that clip a portal-less popover,
   and evidence-on-hover is one of the console's main affordances for keeping density down. A clipped
   tooltip is evidence the console holds and does not show.

6. **Is a failed remediation attempt and its `abandon_reason` visible without a click, on the
   workflow view?** (`content-hidden-at-rest`, the second rule carrying severity `error`.) It earns
   its place because this is the product claim rather than a detail. The plan requires the failed
   attempt to stay visible "prominently rather than in a corner" (VERIFIED — plan line 238), and
   `.claude/rules` and `CLAUDE.md` both state that abandoned runs are data. A collapsed-by-default
   accordion satisfies "the field is rendered" and defeats the reason the console exists.

7. **Do the heading levels descend without skipping, on each of the six hierarchy levels?**
   (`skipped-heading`.) It earns its place over the other accessibility rules because the console's
   navigation hierarchy *is* the dependency graph, and the heading tree is the only machine-readable
   assertion of which level of that graph you are looking at. It is the single accessibility check
   that also encodes the product's spine, which is why it beats `justified-text`, `all-caps-body` and
   the rest of the WCAG tier.

8. **Does prose evidence — `abandon_reason`, `tsc` diagnostics, CI failure output — wrap at a
   readable measure rather than running the full width of a wide window?** (`line-length`, registry
   description gives roughly 80 characters; implementation constant could not be verified.) It earns
   its place because the console mixes two content types that want opposite widths: tables want the
   whole viewport, paragraphs do not. On a 1920px display an unconstrained evidence block is a
   200-character line, and evidence nobody reads is the same failure as evidence not shown.

9. **Is the smallest text on screen still comfortably readable, and does no multi-line block sit
   below 1.3 line height?** (`undersized-ui-text` at 11px, `tiny-text` at 12px, `tight-leading` at
   1.3x — all three from registry descriptions; could not verify the implementing constants.) These
   are grouped as one question because they share a single cause: the standing temptation of a
   data-dense console is to reach for `text-xs` and tighter leading every time a table gets crowded.
   This is the question that says where density stops being density and starts being a defect. It
   earns its place because "data-dense" is a stated goal and goals need a stated limit.

10. **Can you tell a page title, a section heading and a row label apart at a glance, or do they all
    render at nearly the same size?** (`flat-type-hierarchy`, registry description asks for a ratio of
    at least 1.25 between steps; could not verify the implementing constant.) This is the only rule
    from the `slop` category that earns a place here, and it earns it because "unstyled beyond
    legibility" fails at exactly this seam. With no design system and a deliberately empty `@theme`
    block (VERIFIED — plan lines 171-179 show `src/index.css` with the palette left empty on purpose),
    every level of the graph tends to render at the same weight, and the operator loses the sense of
    where they are in a six-level hierarchy. It is also the cheapest of the ten to fix.

### What was dropped, and the cost of having kept it

The other 49 rules were dropped deliberately. The bulk of them — `hero-eyebrow-chip`,
`gradient-text`, `radial-spotlight-glow`, `italic-serif-display`, `marquee`, `icon-tile-stack`,
`oversized-h1`, `ai-color-palette`, `cream-palette`, `dark-glow` and their neighbours — describe
defects of a marketing landing page. An operator console has no hero section, so these rules can only
ever return zero, and asking a tick to check them spends the tick's attention on findings that cannot
occur.

Four more, `design-system-font`, `design-system-color`, `design-system-radius` and
`design-system-font-size`, are load-bearing for Impeccable and inert for Sync, because they validate
against a `DESIGN.md` or `.impeccable/design.json` that the project supplies. VERIFIED: there is no
`DESIGN.md` at this repository's root. Adopting them means either running four permanently silent
rules, or writing a design system now to feed them, which pre-empts a decision the plan explicitly
defers ("Premium components, bento grids — these are a design-system decision, and the design system
comes after the data model is visible", VERIFIED at plan line 253). That is the concrete cost: a
detector rule would drive a product decision in the wrong order.

Two were dropped because they actively conflict with the console's design. `monotonous-spacing` fires
when one spacing value accounts for more than 60% of samples across three or fewer unique values
(VERIFIED in implementation) — which is a fair description of any correctly built Tailwind v4 table,
where uniform row rhythm is the point. `cramped-padding` wants a minimum of 8 to 16 pixels between
text and container edge, and a dense data grid deliberately runs tighter than that. Adopting either
means a recurring false positive that trains a tick to ignore the detector, which is worse than not
running it.

Finally, `docs/STYLE.md` and the copy rules that enforce it (`em-dash-overuse`, `marketing-buzzword`,
`aphoristic-cadence`, `theater-slop-phrase`) are a genuine conflict worth naming rather than a
mismatch. STYLE.md prohibits em dashes outright (VERIFIED — "Punctuation to avoid: Em dashes"), and
this repository's `CLAUDE.md`, its rules files and its plans use them constantly and on purpose.
Adopting Impeccable's prose rules would start a fight with house style, across every document in the
repository, for no benefit to anybody operating the console.

## 4. Who should consult this, and what it answers

**Primary consumer: the M4 console improvement tick,
`docs/superpowers/loops/console-improvement-tick.md`.** Its reference table already routes "interface
quality, polish, the details that separate a tool from a demo" to this repository. The question this
note answers for that tick is: *when questions 1 through 4 all answer yes, what is the tick's work?*
Before this note the honest answer was "taste", which the loop's own step 2 forbids. Now it is the
first of the ten questions above that answers no. Read section 3 and nothing else; sections 1 and 2
exist so a tick can tell whether the tool is worth installing, and that is a once-per-milestone
question.

**Secondary consumer: whichever slice finally builds the design system** — the deferred row reading
"Premium components, bento grids". The question it answers there is what the design system must *not*
do, since the 32 `slop` rules amount to a well-catalogued list of the reflexes an AI-authored design
system reaches for first. That consultation is worth having when the design system is being designed,
and is noise before then.

**Not relevant to:** anything under `src/sync/`. The detector reads rendered HTML, CSS and frontend
source; it has no view on the graph, the pipeline stages, the vendor adapters or the remediation
loop. A backend milestone consulting this reference will find nothing, and should say so rather than
look harder.

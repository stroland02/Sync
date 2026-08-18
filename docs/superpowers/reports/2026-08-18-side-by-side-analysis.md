# Side-by-side: the drawn mock against the built console, measured

**Run 2026-08-18 at 1440×900**, mock served from `docs/console-mock/Sync Console.dc.html`, console
from `localhost:5173` on current `main`, both measured through the same `getComputedStyle` path.

**No composite score.** A single number would hide which property moved, which is the figure this
console refuses everywhere else.

## The headline: prose volume, and it confirms the owner's own observation

**The built console carries three to twelve times the prose the mock does, on every screen.**

| screen | mock | built | ratio |
|---|---|---|---|
| codebase | 282 | 3362 | **11.9×** |
| signals | 308 | 3778 | **12.3×** |
| observe | 294 | 3085 | 10.5× |
| api-services | 291 | 2316 | 8.0× |
| remediation | 579 | 3921 | 6.8× |
| fleet | 340 | 1885 | 5.5× |
| settings | 324 | 894 | 2.8× |

**This is the static-card problem, measured.** The owner's words were *"a lot of cards that are just
information that's just there instead of the actual dynamic workflow or data."* The eval says the
same thing in numbers, independently. **`M0-W329` is the ruling and this is its evidence** — and note
that Settings, where description is supposed to live, has the *lowest* ratio of any screen. It is the
one place the prose belongs and the one place there is least of it.

**A caution that is not a hedge.** Some of that 3778 on `signals` is protected — the twenty-four
honesty sentences are prose too. The classification pass in `prose-audit.mjs` exists precisely for
this and must run before anything is cut. On Fleet it previously found 580 of 915 characters
protected. **The ratio names the problem; it does not license deletion.**

## Colour is exact, on every screen

`bodyBackground` `oklch(0.19 0.0025 159)` and `bodyColor` `oklch(0.95 0.00275 159)` match the mock on
all eight. The token contract holds and **no colour work is needed anywhere.**

## Composition is mixed, and the built console is ahead in two places

On `regionsBeside` — panels beside panels, table rows excluded, which is the honest metric after
`M14-W355` found `sideBySide` was counting markup technique:

| screen | mock | built | |
|---|---|---|---|
| api-services | 1 | **5** | built ahead |
| fleet | 0 | **2** | built ahead |
| codebase | 2 | 2 | level |
| settings | 1 | 1 | level |
| signals | 1 | **0** | behind |
| observe | 1 | **0** | behind |
| remediation | 1 | **0** | behind |

**Three screens are flat where the mock composes: signals, observe, remediation.** That is the real
layout gap and it is three screens, not nine.

## Type is wider than the mock, deliberately

Built `typeRange` runs 3.83–5.11 against the mock's 1.83–2.33. That is not a deficiency: the console
was rebuilt to clear a 3.4 bar after `2026-08-06-why-the-console-came-out-flat.md` measured it at
2.0. **The mock is the weaker artefact here and should not be matched down to.**

## One real defect the eval found

**`radii` reports `3.35544e+07px`** — 33,554,400px — on `fleet`, `remediation` and `settings`. That
is a nonsense value reaching `getComputedStyle`, almost certainly an unclamped `rounded-full` or an
overflowed calculation. It renders as a pill so nobody has noticed, but it is a real number in the
tree and it is worth one look.

## What this says to do

1. **Run `prose-audit.mjs` on all seven screens, then move what is static to Settings.** Biggest
   ratios first: codebase and signals.
2. **Compose three screens**: signals, observe, remediation. Not nine.
3. **Do nothing about colour.**
4. **Do not match the mock's type range down.**
5. **Chase the 33,554,400px radius.**

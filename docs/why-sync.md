# Why Sync exists

The argument, and what the console refuses to claim. Moved out of `README.md` so the landing
page can get somebody running; nothing here was shortened in the move.

## The problem nobody owns

Every codebase depends on APIs it does not control, and those APIs change. Fields are removed,
endpoints are deprecated, defaults shift, cheaper endpoints ship quietly. The consuming team finds
out when production breaks — if at all. At AWS, more than 30% of one organisation's service
downtime traced to external API and package changes that nobody noticed.

The tooling that exists watches the wrong side of the wire.

| | Watches | Acts on | Verifies |
|---|---|---|---|
| SmartBear, Treblle, Levo, Optic, Postman-Akita | The API **you publish** | Raises an alert | — |
| Dependabot / Renovate | Package **versions** | Opens a version-bump PR | Your CI |
| Codemod tools (`ast-grep`, `jscodeshift`) | Nothing — you point them | Applies a transform you wrote | — |
| **Sync** | The APIs **you consume**, across vendors | Patches the calling code | `tsc`, then **your own CI**, before the PR exists |

Dependabot solved exactly this shape for package *versions* and never extended to API *semantics*.
Sync closes that gap.

### What actually makes it different

Four things, and each is a design decision the rest of the system is built to protect:

1. **It repairs the consuming side.** Everyone else watches the API you ship. The expensive failure
   is the one in code you own, calling an API you don't.
2. **One graph, many detectors, one pipeline.** A breaking change, a wasteful call pattern and a
   production error are three queries against the same **API Dependency Graph**, and all three emit
   the same `Finding` into the same remediation pipeline. Adding a detector adds no pipeline.
3. **Nothing reaches a pull request unverified.** There is no path that skips the gate — see
   [Two invariants](#two-invariants).
4. **Every claim carries the class of evidence behind it.** Not a confidence score — a
   **provenance rung**. See [The honesty discipline](#the-honesty-discipline), which is the part of
   this project that is hardest to copy.

---

## The operator console

Sync's position is that competing tools present a black box and a result, and ask a reviewer to
trust it. The console exists to show the system's reasoning instead — nine levels, from the fleet
down to a single pull request and its evidence.

### Where it is going — the design mock

A ten-screen mock, drawn in HTML/CSS/JS and committed so the build has a target it can be measured
against rather than argued about from memory. **None of it is built yet.** The tour at the top of
this page is this mock; the four screens below are stills from it.

| | |
|---|---|
| <img src="docs/console-mock/screens/05-binding-surface.png" alt="The binding surface in the mock" /> | <img src="docs/console-mock/screens/07-workflow.png" alt="The solution workflow in the mock" /> |
| **Binding surface** — every call site under one operation, each row carrying its own rung, over a shared directory prefix. | **Solution workflow** — eight nodes beside an activity timeline assembled at read time from four sources. |
| <img src="docs/console-mock/screens/09-detectors.png" alt="Detector attribution in the mock" /> | <img src="docs/console-mock/screens/08-pull-request.png" alt="The pull request level in the mock" /> |
| **Detector attribution** — every detector's open findings broken down by the rung behind them, with no colour assigned to any rung. | **Pull request** — the patch beside the evidence bundle, and a panel naming what the bundle does *not* contain. |

| | |
|---|---|
| **Watch it** | [`docs/console-mock/demo.mp4`](docs/console-mock/demo.mp4) — 40s, 1440×900, no audio |
| **Click it** | [the live mock](https://claude.ai/code/artifact/f321ac84-32d5-4181-a680-8bf2df671247) |
| **Read it** | [`docs/console-mock/`](docs/console-mock/) — the source, twelve stills, and which of its facts are fixtures |
| **Build it** | [`plans/2026-08-08-console-mock-to-build.md`](docs/superpowers/plans/2026-08-08-console-mock-to-build.md) — six tasks across M7, M12 and M4 |

Two things make it worth committing rather than linking. It is drawn on **our own token contract** —
its literal OKLCH values are the ones `web/src/index.css` already declares, so a colour in it that
is *new* is conspicuous rather than invisible. And it applies the honesty discipline rather than
decorating it: no composite score, no health figure, no green dot, no liveness pulse, and every
status colour ships with a glyph and a word so the colour is never load-bearing.

It is still the lowest authority in the room. Where it disagrees with the specification's hierarchy,
with `DESIGN.md`, or with a protected sentence, the mock loses — and the plan says so in as many
words.

### What is running today

Not the above. These are captures of the console as it actually is, at commit `25a4a10`, 1920×889,
against `scripts/seed_console.py`'s fixture.

<div align="center">

<img src="docs/superpowers/reports/screens/2026-08-07/01-fleet.png" width="90%" alt="The fleet screen: open findings by vendor, runs by checkpoint thread, and the repair record" />

*The fleet: every run across every repository, and whether one is stuck.*

</div>

| | |
|---|---|
| <img src="docs/superpowers/reports/screens/2026-08-07/07-binding-surface.png" alt="The binding surface" /> | <img src="docs/superpowers/reports/screens/2026-08-07/06-workflow.png" alt="The solution workflow" /> |
| **Binding surface** — every call site bound to one vendor operation, each carrying the rung it was bound on. | **Solution workflow** — the checkpointed node sequence, with the evidence at each step and the reason a run gave up. |
| <img src="docs/superpowers/reports/screens/2026-08-07/03-codebase.png" alt="The codebase level" /> | <img src="docs/superpowers/reports/screens/2026-08-07/04-api-service.png" alt="The API service level" /> |
| **Codebase** — index coverage and open findings for one repository. | **API service** — what a vendor changed, and which of your call sites it reaches. |

More in [`docs/superpowers/reports/screens/`](docs/superpowers/reports/screens/), with the capture
conditions recorded beside them — a screenshot without its viewport and commit is not evidence.

### The honesty discipline

The console renders the product position, so its interface rules are not taste. Four distinctions
are drawn on screen rather than assumed, and twenty-four sentences carry them:

- **Provenance at two levels.** Every binding carries the rung it came from — `static`, `resolved`
  or `observed` — and so does every artifact derived from it. It is a **column, not a join**, and
  the write refuses an unattributed finding. A false positive that cannot be attributed to a rung
  cannot be fixed.
- **Absence is not zero.** A repository configured but never indexed has no row, which is not the
  same as one with nothing in it, and the screen says which it is looking at.
- **Staleness is not liveness.** A checkpoint row is the only evidence a run exists. "Last
  checkpoint" is staleness, and nothing here guesses which silence means death.
- **Never-measured is not nothing-here.** Five distinguishable kinds of nothing, each with its own
  sentence.

**There is no composite health figure, traffic light, green dot or liveness pulse anywhere in this
product, and that is a refusal rather than an omission.** A scalar averaging three gates collapses
*"we could not check"* onto the same axis as *"we checked and it passed"* — which is precisely the
failure this console exists to replace. A mature control plane ships all three patterns and
documents a precondition for each; our data fails those published tests, so we say so instead of
rendering the widget. The provenance rung is the honest version of a confidence score: it names the
class of evidence a claim rests on, and it is attributable, where a `9` is neither.

`tests/test_console_honesty_sentences.py` guards those sentences against a rewrite. It is
deliberately **not file-pinned** — a sentence may move into a new composition; deleting or
shortening one fails the build.

---

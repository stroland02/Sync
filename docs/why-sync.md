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

## The journey, and why it runs in this order

Most tools in this space need instrumentation before they can show you anything: install an SDK,
get a key, wire an exporter, wait for an event. **Sync does not, and that is the strongest thing
about it.** The API dependency graph's first rung is `static` — call sites read straight out of
your code — so there is something true to show before you have configured anything.

1. **Index your repository.** Your call sites, your vendors, your findings. Every binding marked
   `static`, and the console saying plainly that `static` is what it is. No key, no SDK, no signup.
   *(Blocked in the demo container today — `B188` in `docs/superpowers/BACKLOG.md` carries the
   three ways out and what each one costs.)*
2. **Attach telemetry, if you want to, and watch bindings move from `static` to `observed`.** The
   screen shows the upgrade, so you can see exactly what instrumenting bought you. It is an
   argument for instrumenting rather than a precondition for being allowed in. In practice this is
   `sync ingest` over a payload you exported — Sync has no listener and does not ask you to point
   an exporter at a URL.
3. **Let it open a pull request, once you trust it.** Last, not first — after you have seen its
   reasoning on your own code.

**Value before configuration**, and it is not a trick: the provenance rung means the console can
say exactly how much that free first answer is worth.

## Where it stands, and specific about it

M0's definition of done was one thing: a real breaking change producing a CI-green pull request
against a real repository, unattended.

**That has happened once.** One `sync run` against a fork of `stripe/stripe-connect-furever-demo`
produced [pull request #1](https://github.com/stroland02/stripe-connect-furever-demo/pull/1) — two
deletions in one file, removing a withdrawn request argument at both call sites that passed it,
typecheck green on the branch, no human between detection and pull request.

Three qualifications, because they change what the result means:

- **The acceptance run has not re-executed since the pipeline changed underneath it.** It is
  `@pytest.mark.e2e` and deselected by default. Since it last ran, the pipeline gained the tier
  cascade, a push guard, branch deletion on abandonment, the dependency-edit guard and more —
  every one of them on the acceptance path.
- **The vendor change was constructed**: a property removed from a real pinned specification
  rather than one Stripe withdrew, because no window of Stripe's history examined here contains a
  top-level breaking change this application would notice.
- **Three of the five quality axes have never had a sample.** Merge rate, routing accuracy and
  cost per merged patch need pull requests that have not been opened yet. They report `null`
  rather than zero, deliberately.

What *is* measured is measured properly — see
[Quality gates](developing.md#quality-gates).

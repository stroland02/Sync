# What the visual eval needs from CI to be a gate rather than a one-off

**2026-08-17, Lane C.** Read against
`plans/2026-08-17-reference-hierarchy-and-visual-eval.md` and its first run. Nothing built: Lane B
has not settled the extraction mechanism, and a harness built around an unsettled shape is a harness
built twice.

## Where it belongs: the `web` job, beside `beta-gates` and not inside it

**Not inside `beta-gates`, and the reason is a contract rather than a preference.** That job carries
`--exit-zero` because a readiness verdict must never fail a build; a NOT MET gate that reddens CI
teaches every lane to ignore CI. A visual eval that is to be a *gate* needs the opposite — it must
be able to fail. Putting both in one job means either the eval cannot fail, or `beta-gates` acquires
a carve-out, and the carve-out is `continue-on-error`, which swallows a crashed script along with
the verdict. That is the distinction `CI-W290` was built on and it should not be spent here.

**The `web` job is where the artifacts already are.** It has Node, the console source and
`npm run build`; `beta-gates` has none of them and is a three-second job that would become a
four-minute one for an unrelated reason. The mock is a document in `docs/console-mock/`, already in
the checkout.

## What it costs

The plan measures ~90 seconds for a full nine-route run. The honest CI figure is higher and the
difference is all setup: a headless Chrome, a static serve of the built console, and `npm run build`
if the job does not already have the output to hand. Estimate **three to five minutes added to
`web`**, which currently runs lint, build and vitest.

That is affordable **only because it runs on the `web` job's existing schedule** rather than adding
a fifth job to every push. If it needs its own runner, its own browser install and its own build, it
is a nightly, not a per-push gate.

## Can a per-property comparison fail a build without becoming the check that gets disabled?

**Yes for some properties and no for others, and the split is measurable rather than a matter of
taste.** The plan's own first run supplies the evidence.

| Property | Gate or report | Why |
|---|---|---|
| colour | **can gate** | First run: matches the mock *exactly*, both OKLCH values |
| radius | **can gate** | First run: matches exactly |
| font-size, font-weight | **can gate**, once measured stable | Token-derived and discrete |
| side-by-side region count | **report only** | 4 against 17 — a real gap, and a count that moves with content |
| prose characters | **report only** | 915 against 340 — moves on every copy edit |
| density | **report only** | A ratio, already moved 125.2 → 25.0 by legitimate work |

The rule underneath: **a property derived from a token can be asserted, because changing it is a
deliberate decision recorded in `DESIGN.md`. A property that is a count of content cannot, because
the content legitimately changes and the build would fail on a copy edit.**

Gating the counts would make this a snapshot test, and this repository has already ruled on those:
a snapshot in a console being actively restyled fails on every correct change and gets deleted
within a week by whoever it blocks. A per-property eval that asserts exact values on everything is a
snapshot test with extra steps.

## The three things it needs before it can gate anything

**1. It must distinguish "differs" from "could not measure".** This is the same requirement as
`beta_gates`' `CANNOT TELL` and it matters more here, because the failure modes are environmental: a
font absent on the runner changes computed metrics and every type assertion fails for a reason that
has nothing to do with the console. That is the `host.docker.internal` shape — passes locally, fails
on the runner — and it disarmed both B97 positive controls for a day. **A browser that did not load
the mock, or a page that rendered zero measurable elements, must report that it could not measure
rather than report a difference of everything.** A visual gate that fails loudly for environmental
reasons is disabled within a week, and correctly so.

**2. The exceptions file must be read, and an entry must carry a reason.** The plan already has one,
and it is what stops a known-better difference being noise — the console refusing the mock's
invented Settings figures is the console being *better than* the demo. Without it the eval reports a
difference the team has already decided is correct, every run, and a check that reports a known
non-problem every run is one people learn to skim. The entry needs the reason, not just the
property, or the file becomes a suppression list nobody can audit.

**3. The gateable properties need a stability measurement before they gate.** Colour and radius
matched exactly on one run on one machine. Before either fails a build, run it several times, and
once on a runner, and confirm the value does not move. That is one afternoon and it is the
difference between a gate and a future incident — the same argument as measuring `-n auto` before
retiring `-n 4` rather than assuming.

## What I would argue against

**Do not gate the composition counts, however tempting.** They are the owner's actual complaint and
the most valuable thing the eval produces, and that is exactly why they must not fail a build: the
number moves as the layout pass proceeds, and a gate that fails while somebody is fixing the thing
it measures gets turned off by the person fixing it. Report them per-property with the mock value
beside the built value, which is what the plan already says.

**Do not add a similarity score, even as a summary.** The plan already refuses this and it is right:
a single number over five properties is the composite figure this console refuses everywhere else,
and it hides which of the five moved.

**Do not put it on every push before it has a stability measurement.** A new check that fails
intermittently in its first week is disabled in its second, and re-enabling it is a much harder
conversation than starting it in the nightly and promoting it once it has been quiet.

## What I need from Lane B before building

The extraction mechanism, settled — whether it stays the in-house script or moves to `d-extract`
changes what the harness invokes and what it installs, and that is the whole of the CI wiring. Once
that is fixed I can wire it, and the wiring is small: a step in `web`, a serve, a browser, and a
report written where `CI-W294`'s summary check already proved things can be published readably.

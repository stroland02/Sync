# Ship by Wednesday: what is in, what is out, and what only the owner can unblock

**Owner directive, 2026-08-18 (early hours).** A finished product, deployable and ready to use from
the git repository, by **Wednesday 2026-08-19**. That leaves the rest of today, all of Tuesday, and
part of Wednesday. **The UI is the highest priority.**

This document reorders everything against that date. It supersedes the ordering in
`2026-08-17-sync-to-beta-scope.md` — not its rulings, which stand, but its priorities, which were
written against gates rather than against a ship date.

## The owner answered the three decisions, 2026-08-18, and they change this plan

- **Deployment: local-only, documented.** Nothing is hosted. The deliverable is a clean clone that
  comes up with one command. This removes every outward-facing risk and makes fresh-clone bring-up
  the product surface rather than a nicety.
- **`B7`: authorised against a scratch repository we own.** Not a design partner's. This is the
  change that matters most — **the loop can be proven end to end tonight**, with nothing waiting on
  anybody else's CI queue.
- **Finished means complete and honest.** Every screen renders real data, one command brings it up,
  and the meter states what it cannot tell and why.
- **The audience is an investor or stakeholder**, asking *is this real, and does it work*.

**That last answer reorders the rest.** An investor does not check whether a sidebar collapses
without moving a row. They ask whether the thing works, and they discount a claim they cannot check.
So three consequences:

1. **`B7` against the scratch repo is now the single highest-value item in the workspace**, ahead of
   everything including the UI. Gate 1 turning `MET` converts *"the loop has never closed"* into
   *"the loop closed, here is the pull request"*. Nothing else available this week changes the
   answer to *is this real* by as much.
2. **The meter's `CANNOT TELL` stops being an apology and becomes the pitch.** Every competitor
   shows a number. Sync shows a number, its provenance, and an explicit refusal where the evidence
   does not exist. **That refusal is the differentiator and it must read as deliberate on screen**,
   not as an unfinished state. This is Lane B's highest-value work now.
3. **Empty screens are the biggest UI risk, not unpolished ones.** A screen with real data and plain
   styling survives the question. A beautifully composed empty state does not.

## The honest headline, stated first because everything else depends on it

**Two of the four beta gates cannot be met by Wednesday, and pretending otherwise would be the
failure this product exists to replace.**

- **Gate 1 — the loop closes.** Needs `B7`: a real pull request on a real repository that goes green
  in that repository's own CI. That is elapsed time in somebody else's CI queue, not work we can
  schedule, and it needs the owner to say which repository and to authorise the spend.
- **Gate 2 — the evidence exists.** Four of its five axes are denominated on a *merged* pull
  request, so they follow `B7` and cannot precede it. The fifth, routing accuracy, is reachable and
  in flight.

**That does not mean the product is unfinished.** It means the product ships with its readiness
meter reading `CANNOT TELL` on two axes and *saying so* — which is the position this console was
built to make legible. A tool that shows `0 of 4, and here is exactly why` is a more honest artifact
than one that shows a green dot it cannot justify.

## What "deployable and ready to use from the git repo" means concretely

Four things, and only the first is mostly done:

1. **The console renders truthfully against real data.** M7 and M14 are at ~99%. This is the highest
   priority and it is the closest to finished.
2. **The API serves every screen the console has.** One screen is currently unserveable — `B147`,
   where telemetry routes 404 for a repository `/api/repositories` lists.
3. **It comes up on a clean machine from a clean clone.** `scripts/dev_up.py` does this locally
   (`CI-W302`, `CI-W303`). What has never been tested is a *fresh clone by somebody who is not us*.
4. ~~It is served somewhere, behind a credential.~~ **Superseded: deployment is local-only.** What
   replaces it is a packaging target, named by the owner 2026-08-18: **installation must feel like
   `npx skills add superloglabs/skills --all`** — one command, from the repository, and it works.

**That is a specific and checkable bar, so state what it can and cannot mean here.** `npx` gives a
Node entry point. Sync is a Python product with a TypeScript console, and it needs Python 3.12, `uv`,
and a Postgres. **An `npx` wrapper cannot conjure a Python toolchain, and pretending it can is how a
one-command install becomes a five-minute traceback.** What it can do is be the single thing a person
types, check every precondition, and say precisely which one is missing and how to fix it —
`scripts/dev_up.py` already does exactly this (`CI-W302`, `CI-W303`), and it refuses rather than
dying. The `npx` entry point wraps that and surfaces its messages rather than hiding them.

**Read the Superlog command as a *method*, not a feature list — owner clarification, 2026-08-18.**
The point is not that it happens to index. The point is **no assembly required**: one command sets up
*everything the product needs to work*, and the user is never left holding a list of steps. For Sync
that is the toolchain and its shims, the database and its schema, whatever harnesses and skills the
product depends on, the console build, the running services, and the index of the target codebase.

**The test is not "does the command exist". It is: after this one command, is there anything a person
still has to figure out?** Every remaining step is a defect in the command, not a note for the README.

**What the one command actually does, per the owner 2026-08-18: all setup, launch localhost, and
index the codebase.** That third step is the one that matters and it is the one nobody had scoped.
It means first-run is not *bring up a product with seed data* — it is **point Sync at a repository
and watch it build that repository's API dependency graph**. The console then shows the user's own
call sites, their own vendors, their own findings.

Three consequences, and the first is the whole reason this is worth doing before Wednesday:

- **It is the answer to *is this real*.** Seeded data proves nothing to a sceptic; a graph built from
  a repository they chose, in front of them, proves the indexer works on code nobody tuned it for.
- **The INDEX path must survive an arbitrary repository**, not just the corpus fixtures. Unknown
  frameworks, missing lockfiles, a language we do not index, zero call sites — each needs a legible
  outcome rather than a traceback. `sync.index` already attributes an unbindable wrapper rather than
  reporting a false zero (`M5-W311`), which is exactly the shape the rest of it needs.
- **Seed data becomes a fallback, not the demo.** If indexing the target produces nothing, the
  console must say *this repository has no calls we recognise* — never show somebody else's data
  where theirs should be.

The honest form of the promise: **one command to type, one screen of output, and either the product
is running or you know exactly what to install.** Not: one command that silently installs a language
runtime.

## The quickstart, designed from Sync's own data

**A competitor's onboarding was supplied as reference on 2026-08-18 and is treated under
`.claude/rules/interface-originality.md`: the arrangement is learnable, the rendering is not.** What
transfers is the shape of the journey. What does not transfer is their copy, their step order, their
key-first posture, or anything their product needs and ours does not.

**The problem, restated before it becomes a design.** A person with a codebase has to get from
*nothing* to *seeing their own data* without assembling anything. Every step between those two points
is attrition, and a step that produces an empty screen is worse than no step at all.

**Sync's answer differs from a telemetry product's, and the difference is the strongest thing we
have.** A telemetry tool's dashboard is empty until traces arrive, so its onboarding must be about
instrumentation: install an SDK, get a key, wire an exporter, wait for an event. **Sync needs none of
that to show you something true.** The API dependency graph's first rung is *static* — call sites
read out of the code itself. So:

**Point Sync at a repository and it shows you real findings before you have configured anything. No
key, no SDK, no signup, no instrumentation.**

That inverts the usual order — **value before configuration** — and it is not a trick, because the
provenance rung means the console can say exactly how much that free answer is worth. Which produces
Sync's own second step, and it is one a telemetry product cannot offer:

1. **Index.** One command. Your repository, your call sites, your vendors, your findings — every
   binding marked `static`, and the console saying plainly that `static` is what it is.
2. **Attach telemetry, optionally, and watch bindings move from `static` to `observed`.** The screen
   shows the upgrade. **You can see precisely what the instrumentation bought you**, which is an
   argument for instrumenting rather than a precondition to being allowed in.
3. **Let it open a pull request, when you trust it.** Not first. After you have seen its reasoning on
   your own code.

**The measurable claim to put in front of an investor:** the local path is *one* command. The
reference product's is five. That is checkable in front of them, and `dev_up.py` already does it.

**What this means for the docs by Wednesday.** A `README` quickstart that is this journey and nothing
else, written against what the product actually does — no placeholder keys, no steps that do not
apply, and no claim the meter cannot support.

## The install target, decided

**Three references now, converging on one shape.** A skills-installer aimed at a coding agent; a
five-command self-host; and — the clearest of them — `npx @deepseek-ai/dsh web`, which starts a web
UI on localhost with no clone and no install steps. **The owner has pointed at the same thing three
times, so stop qualifying it and name a target.**

**Why the clean version is easy for them and not for us, stated once so nobody rediscovers it.** That
harness is a Node program: everything it needs ships inside the npm package, so `npx` can deliver the
whole product. Sync is Python and TypeScript over Postgres. **`npx` cannot ship a Python runtime or a
database**, and a wrapper that pretends otherwise fails in front of the person being shown it.

**So the decision: `npx` → Docker → UI, with Docker as the single stated prerequisite.**

```
npx <sync-package>          # or: docker compose up, for people who prefer it
```

It pulls or builds one image containing the API, the console and the Python toolchain, brings up
Postgres beside it, applies the schema, indexes the repository it was pointed at, and serves the
console on localhost. **One prerequisite, named up front: Docker.** That is the same prerequisite the
reference self-host has, and it is the only honest way to get from three commands to one.

**Why this beats the alternatives, briefly.** Wrapping `dev_up.py` in `npx` still requires Python,
`uv`, and Postgres already installed — three prerequisites instead of one, and each is a place the
demo dies. Cloning and building on the fly is slower, needs the same toolchain, and turns a demo into
a build log. **The container is the artifact; `npx` is the doorbell.**

**What this makes P0 that was not before:** a Dockerfile and compose file that actually produce a
running product, and a published or buildable image. `docker compose up -d` exists for Postgres
today; the product itself has never been containerised. That is the work.

## Correction to the quickstart above: we cannot say "point your exporter at us"

**Checked against the code rather than assumed, after a fourth reference described an OTLP intake
endpoint.** The quickstart section above promised step 2 as *attach telemetry and watch bindings move
from `static` to `observed`*. **Sync has no OTLP listener.** `sync ingest` folds a *captured*
OTLP/JSON payload from a file or stdin, and `cli.py:1519` records that as a deliberate choice — *"a
listener needs a port, a supervisor, and an [ongoing] infrastructure"*.

So the honest version of step 2 is: **export a payload, then `sync ingest` it.** Not: point your
exporter at a URL and wait. That is a real difference from the reference and it must not be papered
over in a README a stranger will follow.

**Decision for Wednesday: do not build a listener.** It is a port, a supervisor, and an operational
surface, and it would be built in two days to serve a demo rather than a user. The `static` rung is
what the one command delivers and it is already the strongest part of the story — findings on your
own code before you configure anything. `observed` is demonstrable from a captured payload, which is
enough to show the rung *moving*, which is the actual argument.

**Two things the fourth reference does supply that we should take, both cheap:**

- **A service endpoint table** — service, URL, purpose — stated before setup rather than discovered.
  Ours is smaller: the console on `localhost:5173`, the API beside it. Say it in the README.
- **Prerequisites stated up front, as a list, before step 1.** Ours is one line: Docker.

**And one thing checked and found already done:** the reference states its licence prominently.
`LICENSE` exists, `pyproject.toml` declares `Apache-2.0`, and the README already carries the badge.
No work.

**One thing their compose does that ours must beat, and can.** Their `docker compose up -d` starts
only the databases and a collector; the application still needs `pnpm install` and `pnpm dev`. Five
steps total. **Our target — one image carrying the product — is genuinely simpler than the thing it
is being compared to, and that is worth stating plainly rather than implying.**

## Agent automation settings, and the one option we refuse

**Two further reference documents supplied 2026-08-18: a GitHub App integration flow, and per-project
agent automation settings.** Same treatment — the shape of the control surface is learnable, the
copy and the specific arrangement are not, and each item has to survive being restated against what
Sync already has.

**What Sync already has, checked rather than assumed:**

- **Project context exists and is better placed than the reference's.** Theirs is a free-text field
  in a dashboard. Ours is `.sync/context.md`, read out of the customer's own repository
  (`sync.context.seed`, `SEED_RELATIVE_PATH`), so it lives with the code it describes, versions with
  it, and needs no dashboard round-trip. `B165` also means it is fenced at instruction position.
  **Nothing to build here; it needs saying in the docs, not implementing.**
- **A read-only Settings screen** (`M4-W231`) and a `settings` feature route.
- **Pull-request outcomes** already recorded and reconciled (`M10-W229`, `sync reconcile-pull-requests`).

**What is genuinely missing: the policy itself.** There is no stored answer to *what happens after
Sync opens a pull request*, no merge strategy, and no base-branch override. Three settings, per
repository rather than per project, because a repository is Sync's unit:

| Setting | Values | Default |
|---|---|---|
| merge policy | `never`, `when_checks_pass` | `never` |
| merge method | `squash`, `merge`, `rebase` | `squash` |
| base branch | any branch name | the repository's default |

**We refuse the third merge-policy value, and the refusal is a product position rather than a gap.**
The reference offers `immediately` — merge the fix without waiting for any check to run. **That
directly contradicts this project's non-negotiable that nothing reaches a pull request unverified,
and it contradicts the whole argument the console exists to make.** A tool that will merge before its
own evidence arrives is the black box Sync was built against. So `immediately` is not implemented,
and the Settings screen says *why* rather than omitting it silently — an absent option a competitor
has reads as an oversight; a refused one reads as a position.

**Scope for Wednesday.** The storage, the API, and the console rendering the current policy are P1 —
they make the product legible as a real product, and the Settings screen already exists to hold them.
The GitHub App OAuth flow is **P2 and explicitly out**: Sync uses the authenticated `gh` CLI, hosting
is out of scope, and an OAuth callback needs a hosted endpoint we have deliberately decided not to
have this week.

## Priority order to Wednesday

**P0 — must be true or there is no product.**

| # | Item | Lane | Why it is P0 |
|---|---|---|---|
| -1 | **`B7` against a scratch repo we own** | A | **Owner-authorised 2026-08-18.** The loop has never run end to end. Proving it once converts the whole pitch, and it is now schedulable because no external CI is involved |
| 0 | **`main` is green** | C | Two `B97` positive controls fail under `-n auto` (measured 2026-08-18: 2 failed, 3997 passed). A red `main` makes every other claim unverifiable |
| 1 | **`B147`** — a 404 claiming absence where the truth is zero | E | One of seven console screens cannot render at all. It is also the honesty principle violated below the console, so no screen can fix it |
| 2 | **The console IA settles and stops moving** | B | Every screen must exist and be reachable. The IA rulings are made (`M14-W365`); what remains is building them |
| 3 | **Fresh-clone bring-up, verified by somebody who did not build it** | C | Item 3 above. This has never been tested and it is the difference between "works here" and "deployable" |
| 4 | **`npx` one-command install from the repo** | C | **Owner-named 2026-08-18**, to feel like `npx skills add superloglabs/skills --all`. This *is* the deployment story now that hosting is out. It wraps `dev_up.py`'s precondition checks rather than replacing them |

**P1 — makes the product credible rather than merely working.**

| # | Item | Lane | Why |
|---|---|---|---|
| 5 | **Gate 3 re-signed, last** | B | A walk of the screens once the console stops changing. Do it *after* the IA work lands, not during — `M0-W302` |
| 6 | **`B97` sandbox wiring** | A | Gate 4's only blocker. The design is settled (`M10-W251` corrected it) and three slices are landed. Closes the containment claim |
| 7 | **Routing accuracy sample** | A + D | The one Gate 2 axis reachable without `B7`. Finding `016de7ef…` exists; the run is queued |
| 8 | **`B148`** — Fleet's N+1 on the landing screen | E | Fifty repositories cost fifty-one round trips. A demo on a real corpus will show it |

**P2 — do not do these before Wednesday.**

Everything in `2026-08-17-sync-to-beta-scope.md`'s post-beta set, plus: M11 fan-in, M13, most of M12,
tenancy, the write path, a user system, the dollar estimate, and any further eval instrumentation.
**The visual eval has done its job** — it proved the console is ahead of the drawing on two screens
and behind by one pairing on three. Building more of it now is measurement instead of product.

## What changes about how the lanes work

**The UI is the priority, so Lane B is the critical path and everything else exists to unblock it.**
That inverts the usual posture: when another lane has a choice between its own queue and something
Lane B is blocked on, it takes the unblock.

**Lane E's `B147` is the single most valuable non-UI item**, because it is the only thing making a
console screen unrenderable. It has been in flight for hours and it is the slowest lane.

**Stop opening new fronts.** Two lanes have context-exhausted today and both handovers cost an hour.
Between now and Wednesday, prefer finishing a started thing to starting a better one.

## The decisions only the owner can make, and when they are needed

1. **Where is the console served, and under what credential?** *Needed today.* Nothing about
   deployment can be prepared without it. Ruling 1 keeps it small — one shared credential, no user
   system — but the target has to be named.
2. **Is `B7` authorised, against which repository, and may Sync open a pull request there?**
   *Needed Tuesday morning at the latest*, because it is elapsed time in someone else's CI. If the
   answer is no, Gates 1 and 2 ship as `CANNOT TELL` and the product is still shippable.
3. **Does "finished" include the loop having closed once, or does it mean the product is complete
   and honest about what it has not yet proved?** These are different products and the second is
   achievable by Wednesday. The first depends on decision 2 and on somebody else's CI.

## What this document does not claim

It does not claim two days is enough to close the loop. It claims two days is enough to ship a
console that renders the truth about a system whose loop has not yet closed — and to say which of
those two things is which, on the screen, without a green dot in sight.

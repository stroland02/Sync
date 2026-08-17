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

# What is left in the console for a design-partner beta that the scope document does not name

Written 2026-08-17 evening at the coordinator's request, after walking every screen twice with a
measurement in hand — the closing mock-parity walk and the Gate 3 pass, plus a third walk on the
production runtime for the re-sign. It is a stock-take rather than a work request: nothing here is
started, and two of the five items I would argue *against* doing before beta.

The scope document is right about what it covers. This is the residue it does not, ordered by what
I would actually refuse to ship without.

## 1. Nobody has ever seen this console against an empty graph — and a design partner will

**This is the one I would refuse to ship without, and it is not in the scope document at all.**

Every walk this console has ever had — the baseline measurement, the closing walk, the Gate 3 pass,
the Gate 3 re-sign — ran against `scripts/seed_console.py`'s fixture. The Gate 3 report names
`seed-console-*` twenty-eight times. **A design partner's first five minutes are the exact opposite
state: their repository is configured, nothing has been indexed yet, and every table is empty.**

That state is not hypothetical and it is not a corner. It is the first thing they see, and it is
the only screen state that has never been examined. The console's honesty discipline makes this
sharper rather than softer: `components/states.tsx` distinguishes four kinds of nothing, and the
whole product argument is that absence is not zero. If any screen renders "0 findings" where the
truth is "nothing has been indexed yet", the first impression a design partner forms is of a tool
making a claim it cannot support — on the exact axis the product is sold on.

I do not know that it does. That is the point: **it has never been looked at**, and it is one
seeded-database-away from being checkable. `seed_console.py --remove` already exists.

**What closes it:** walk all ten routes against an empty graph and record what each renders, the
same way the seeded walk was recorded. Half a session. If every screen is honest, that is a strong
result worth having in writing before a partner sees it; if three screens say zero where they mean
never-measured, that is a defect found before a customer found it.

## 2. A failed panel has no way to re-ask

`ErrorState` (`components/states.tsx:214`) explains what failed and why, and offers nothing. The
only interactive affordance anywhere in the error surface is **Dismiss**
(`components/error-surface.tsx:77-83`), which clears the notice rather than retrying the request.

So when a panel fails — an API restart, a dropped connection, the B117 zombie-API case this
repository has already hit — the operator's only recourse is a full page reload, which re-fetches
every other panel too and loses their scroll position and any filter they set.

This matters more for a hosted beta than it did locally, because the failure rate is higher: a
partner on a network the owner does not control, against a single small process. React Query
already holds `refetch` on every query, so the mechanism exists and is unused.

**What closes it:** a retry control on `ErrorState`, wired to the query's own `refetch`. Small, and
it is the difference between "the console broke" and "the console had a bad minute".

## 3. Nothing on screen says which repository set the console is bound to

The console is single-tenant and renders whatever the configured graph holds — the deployment note
records that there is no tenancy boundary in the product. That is a fine beta posture, but the
screens do not *say* it. A partner looking at Fleet sees repository names with no statement that
this deployment is theirs alone.

The risk is not a data leak; it is a misread. A partner who sees an unfamiliar repository name —
from a stale seed, a shared fixture, a demo left in place — has no way to tell whether they are
looking at their own deployment or somebody else's, and the honest answer matters to them a great
deal more than it does to us.

**What closes it:** one sentence in the shell naming the deployment's scope. It is cheap and it is
the kind of thing that only looks obvious after a partner has asked.

## 4. Route changes do not move focus, so the hierarchy is unavailable to a keyboard

`roadmap-frontend-skills.md` raised this months ago with the argument that matters here: the
console's navigation hierarchy *is* the dependency graph, so focus that does not follow the route
makes the whole hierarchy unavailable to assistive technology. Nothing in `web/src` manages focus
on navigation — I searched; the only `focus()` call in the tree is inside a vendored input
component.

I am listing it fourth rather than first because a named design partner is unlikely to be blocked
by it in week one, and I would rather be honest about that than inflate it. But it is a real defect,
it is cheap, and "we did not think about it" is a worse answer than "it is on the list".

## 5. The evidence disclosure has never been walked on a run that abandoned mid-sequence

The workflow screen's most product-defining behaviour — the outcome rendering *inside* the sequence
at the node where the run stopped, rather than in a banner — has only ever been checked against
runs that completed or reported. `narrative-order.ts` has unit coverage for the abandoned case, so
the derivation is tested; what has not been seen is the rendered screen, and the abandoned run is
the one a partner will study hardest because it is the one where Sync gave up on their code.

**What closes it:** seed one abandoned run and walk that screen. Half an hour, and it is the single
highest-value screenshot in the product.

## What I would *not* do before beta, having looked

Two things that will be tempting and that I would argue against:

- **Do not restyle anything.** The type range clears its bar on all ten routes, side-by-side
  composition clears on all nine levels, and the raw-utility baseline is empty with a guard holding
  it there. The next visual change has no measurement asking for it, and this plan's own record is
  that nine ticks went to design refinement while two specified levels did not exist.
- **Do not add the second drawer**, mock-to-build Task 3. It is correctly marked post-beta: it has
  one consumer, and extracting a shared component for one caller is the debt this repository has a
  rule against.

## The honest summary

Of the five, **only the first would make me refuse to ship**, and it would take half a session to
resolve either way. Items 2 and 3 are what I would want fixed before a partner's second day rather
than their first. Items 4 and 5 are real and can be scheduled.

The thing worth saying plainly: the console's *claims* are in good shape and that is now measured
rather than asserted — Gate 3 is signed on evidence, twice, the second time against the runtime it
will actually be served from. What has never been tested is the console's *behaviour when there is
nothing to show*, which is the state every design partner starts in and the one state the seeded
fixture guarantees we never see.

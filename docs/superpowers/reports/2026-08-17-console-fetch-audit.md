# What each console screen asks the API for — a cost audit, not a gate

**2026-08-17.** Measured with `web/scripts/fetch-audit.mjs`, which counts every `/api/` request a
screen issues between navigation and settling, at 1440×900 against the seeded graph.

**This reports and does not fail.** Over-fetching is a cost finding rather than a correctness one,
and a gate that refused on it would block correct work — a screen can be entirely honest and still
ask for the same page twice. It is run ahead of the remaining prose audits because it changes how
later units are scored, and doing it afterwards would mean re-scoring them.

**No dependency was added, and none was needed.** It speaks Chrome DevTools Protocol over the
`WebSocket` Node ships as a global — the same transport `visual-eval.mjs`, `prose-audit.mjs` and
`superpowers-chrome`'s browsing skill all use. `Network.requestWillBeSent` is a protocol event that
was already available; nothing about counting requests required a package. That is the same verdict
`M14-W354`'s tool trial reached, reached again for the same reason: we own the primitives, and what
was missing was pointing them at the question.

The instrument shares `visual-eval.mjs`'s readiness rule: a screen measured mid-load *under-counts*
its own requests, so an unsettled screen is reported as unmeasured rather than as a low number
somebody would read as good news.

## The measurements

| screen | requests | distinct routes | notable |
|---|---|---|---|
| **fleet** | **12** | 6 | `/api/overview` **×6**, `/api/runs` ×2 |
| codebase | 6 | 5 | `/api/overview` ×2 |
| api-services | 4 | 4 | — |
| signals | 4 | 4 | — |
| observe | 3 | 3 | — |
| remediation | 3 | 3 | — |
| settings | 3 | 3 | — |

## Finding 1 — Fleet issues one `/api/overview` per repository, and that is an N+1

Six requests to `/api/overview`, each a **distinct URL**: one fleet-wide, plus one scoped to each of
the five seeded repositories. React Query is behaving correctly — the URLs differ, so the answers
differ, and nothing is being fetched twice.

**The cost is structural rather than a bug.** `useRepoOverviews` in `codebases-panel.tsx` issues one
scoped query per repository, and it exists for a good reason: `M14-W265` fixed a real honesty defect
where every card showed the *fleet-wide* finding count, because the payload echoes the scope it was
computed for and a fleet-wide figure under a repository's name is a false claim about that
repository. The scoped call is what makes each card true.

**But it scales linearly with the repository count.** Five repositories cost six overview round
trips; fifty would cost fifty-one, on the console's landing screen. That is the classic N+1, and it
is the one measurement here that will not hold as a customer's fleet grows.

**Fixing it is not Lane B's alone.** The honest options are an `/api/overview` that accepts several
repository ids and answers per-scope, or a fleet-wide payload that carries a per-repository
breakdown — both are `sync.dashboard` and `sync.api`, which are Lane E's files. **Filed as B148.**
The console half is small once such a payload exists.

## Finding 2 — Fleet fetches `/api/runs` twice, for overlapping data

Two requests, different query strings. `FleetPage` asks for `{limit: 20, offset: 0}` to find the
newest opened run for its one primary action; the runs table asks for `{limit: DEFAULT_LIMIT,
offset}` for the rows it renders. Different parameters make different query keys, so React Query
treats them as two answers and fetches both.

This was flagged as a Minor during `M14-W264`'s review — *"the coupling is implicit rather than
enforced"* — and is now measured rather than predicted. The first page of runs almost certainly
contains the row the CTA needs, so one of these two requests is redundant in practice.

**Small and Lane B's own.** Not fixed in this unit, because the audit is what was asked for and
changing a fetch while auditing fetches would make the measurement describe a tree nobody else has.

## Finding 3 — every route pays two shell requests

`/api/overview` and `/api/repositories` are fetched on all seven screens, including `/settings` and
`/detectors`. They are the shell's, not the screen's: `layouts/scope-switchers.tsx` reads both for
the scope trail.

**Both are read, so this is not waste** — it is the floor cost of a navigation, and worth naming so
that a future reader looking at `/settings` making three requests knows that two of them are
furniture rather than something the settings screen wanted.

## The other question: a payload a panel does not read

**None found.** Every route requested on every screen maps to a consumer that can be named — the
shell's scope trail, or a panel that renders the answer. The audit cannot see inside a component, so
this is a negative result from tracing each request to a caller rather than a proof; what it rules
out is the obvious form, a screen fetching an endpoint nothing on it displays.

## What this changes about scoring later units

A screen's request count is now a recorded number, so a prose or composition change that also
changes fetching can be seen to have done so. Fleet is the only screen where the count is
interesting, and its twelve requests are six honest scoped answers plus one redundant runs page plus
the shell's two — not a screen fetching carelessly.

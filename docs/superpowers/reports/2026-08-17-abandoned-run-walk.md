# The abandoned-run workflow screen, rendered for the first time

**2026-08-17.** The stock-take named this screen as unit-tested and never rendered, and the
coordinator ranked it first: abandonment is the outcome a design partner is most likely to meet,
because a run that gives up is more common than one that lands a merged pull request.

**The screen is right. Getting to it is the finding.**

## Why nobody had rendered it, which is a finding rather than an excuse

`/api/workflows/{finding_id}` answers with the **newest** generation for that finding. The seeded
fixture gives finding `9f176dea…` an abandoned generation 0 and an opened generation 1, so the
seeded console serves the *opened* run and the abandoned one appears only as a one-line entry under
*Superseded generations*.

**So the abandoned workflow screen is unreachable from the seeded fixture.** Not hard to reach —
unreachable. That is why it had unit tests and no rendering: there was no URL that produced it.

Stood up by copying the seed into a throwaway database (`sync_abandoned_walk`, dropped afterwards —
the shared graph belongs to five other lanes) and deleting the opened generation's checkpoint, which
leaves the abandoned run newest and therefore served.

## What it renders, and it is the feature working

The sequence, read off the rendered list in order:

| | |
|---|---|
| ◇ | **What arrived** — the opening bracket |
| ✓ | `locate` · ran · evidence `request-parameter-removed` |
| ✓ | `prepare` · ran |
| ✓ | `patch` · ran · evidence `agent` |
| ✓ | `static_verify` · ran · evidence `src/billing/charge.ts(42,8): error TS2345: argument of typ…` |
| ◆ | **"Sync abandoned this run. The attempt is still here in full: the entries above this one are what…"** |
| · | `replay` · **never ran** |
| · | `push_branch` · never ran |
| · | `await_ci` · never ran |
| · | `open_pr` · never ran |

**The outcome sits inside the sequence, immediately after the last node the run reached, and above
the four it never did.** That is `narrative-order.ts`'s whole idea and it is the thing that makes
this screen worth having: a reader sees where the run stopped rather than reading a banner and then
hunting for the point of failure. The four unreached nodes say **"never ran"** rather than "not yet"
— the terminal phrasing, correct for a run that has ended.

The abandon reason renders twice and in the right two places: in the closing bracket entry, and in
the activity timeline as `— run.abandoned · static verification failed after 3 attempts`. The
timestamp column is the absence marker for the outcome row, because the payload records no time for
it and none is invented.

The most useful thing on the screen is not prose at all: `static_verify`'s evidence carries the real
compiler diagnostic, so a reviewer sees *why* Sync gave up rather than being told that it did.

**No defect found, and none manufactured.**

## The one real gap: a superseded abandoned run has no address

`superseded-generations.tsx` renders each earlier generation's number, thread id, outcome and
abandon reason — and **no link.** Grepped: no `Link`, no `to=`, no `href`.

That is not an oversight in the component. **The API cannot serve it**: `/api/workflows/{finding_id}`
takes a finding and returns the newest generation, and there is no generation parameter to ask for
an older one. The console cannot link to an address that does not exist.

The consequence, stated precisely rather than dramatically: for a finding that abandoned and was
then retried successfully, the abandon *reason* stays visible as a line, and the node-by-node
evidence behind it — which nodes ran, and the compiler output that stopped it — is not reachable
from the console at all. The product's claim that abandoned attempts stay visible with their reason
is **true as written**; what is unreachable is the evidence under the reason.

I have not built this. It needs a route change in `src/sync/api` and a view-model change in
`sync.dashboard`, both Lane E's files, and it is a design decision about the shape of the address
rather than a defect I caused. **Filed as B146.**

## Method note

Throwaway database created and dropped; the shared container was never restarted. API on 8805 and
consoles on 4205/4206, all stopped and confirmed refusing connections by asking the socket — one
API survived the first sweep under a `multiprocessing.spawn` child and had to be found by command
line, which is the trap `.claude/rules/console-dev-loop.md` documents and the second time this lane
has hit it today. Chrome's viewport override was cleared.

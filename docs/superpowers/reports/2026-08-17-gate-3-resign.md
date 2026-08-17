# Gate 3, re-signed — 2026-08-17, after W277, W278, W279 and W340

The first pass (`2026-08-17-gate-3-screen-pass.md`) was signed at 11:10 and the console changed at
11:54. The changes are this lane's own, and they are named, so this is a re-walk of what moved
rather than ten screens again. **Gate 3 is re-signed.**

It also answers two questions the coordinator asked alongside the signature: whether the staleness
check that flagged this is too crude, and whether the production-serving path built in W340 breaks
any honesty distinction. The second question turned out to be the substantive one.

## What moved, and what each change could have broken

| Work item | What it changed | The honesty risk it carried |
|---|---|---|
| W277 | Fleet reads `/api/change-units` instead of deriving the grain client-side | A new table of columns sourced from a payload nobody had rendered before — every column is a fresh chance to assert a number nothing computed |
| W278 | Settings composed as a grid | Re-placement of sentences; a moved refusal is a refusal that can be dropped |
| W279 | Deleted a stale drift-guard exemption | No console surface; listed for completeness |
| W340 | The console became servable as static assets behind one shared credential | **A different runtime.** Absence-versus-zero survives a rebuild; it does not automatically survive a different fetch path |

## W340 is the one that needed real evidence, and it got it

A production build served statically with `/api` proxied is not the runtime the first pass was
signed against. The first pass ran through the Vite dev proxy. The question is not whether the
console still renders — it is whether the *same bytes* reach it, because every absence-versus-zero
distinction in this console is driven by `null` versus `0` in a payload field.

**Measured rather than reasoned.** The API was run on 8799, the production server on 4199, and each
endpoint fetched both ways and compared byte for byte:

| Endpoint | Direct from the API vs through the production proxy |
|---|---|
| `/api/repositories` | identical, 118 bytes |
| `/api/overview` | identical, 492 bytes |
| `/api/runs` | identical, 1442 bytes |
| `/api/change-units` | identical, 3616 bytes |
| `/api/corpus` | identical, 175 bytes |
| `/api/detectors` | identical, 889 bytes |

**Byte-identity is only meaningful if the payloads actually carry the nulls**, otherwise the test
passes on data that could not have failed it. `/api/change-units` carries 23 `null`s including
`"standing":null`, so the distinction is genuinely present in the compared bytes.

**Status codes pass through unaltered**: `/api/findings/does-not-exist` returns 404 on both paths.
That matters more than it looks — a not-found collapsed into a 200 with an empty body would render
as absence, and "this finding does not exist" and "this finding has nothing recorded" are two
different answers.

## What the screens actually render on the production runtime

Walked in Chrome through the gate, on the built assets:

- **Fleet** — 9 absence markers, 78 data cells, the protected staleness sentence present, no error
  banners. The two matches for "health" are the *refusal* paragraph ("There is no composite health
  figure here on purpose…"), not a health figure.
- **The change-unit STANDING column**, which is the newest surface and the one with no prior pass,
  renders: *"— no remediation run has ever been attempted for this change unit, or this deployment
  has no checkpointer to ask — the two look the same from here"*, and `— no checkpoint recorded`
  for the timestamp. That is absence, and it goes further than the bar by naming the two kinds of
  nothing it cannot separate.
- **Solution workflow** — "Node by node" and "Activity" both present, the assembled-at-read-time
  caption intact, "nothing here says a node is executing" intact, 7 absence markers, no errors.
  The ticking evidence-age does **not** render, and that is correct rather than broken: the run is
  `outcome: "reported"`, and the ticker renders only while a run has no outcome. Verified against
  the payload rather than assumed.
- **Settings** — one side-by-side region (W278's change holds on this runtime; it measured 0
  before), and the merge-policy refusal renders in full: *"Sync has no merge policy to show.
  Nothing in the pull-request path reads a configured merge strategy, a required-reviewer rule or
  an auto-merge switch…"*
- **Deep links work**: `/findings/…/workflow` and `/settings` are served by the SPA fallback and the
  router takes over, so a link a design partner is sent does not 404.
- **The gate is real in a browser, not just under curl**: Chrome raised the Basic auth dialog before
  any of the above rendered.

**No honesty distinction was broken by the production path.** The reason is structural rather than
lucky: the proxy passes the response body through as bytes and never parses or re-serialises it, so
there is no code path on which a `null` could become a `0`.

## Verdict

**Gate 3 re-signed.** Every screen that changed since the first pass was re-checked on the runtime
it will actually be served from, and the answer to the gate's question — does anything here assert
a number nothing computed — is still no.

## On the staleness check: yes, it is too crude, and here is the specific defect

`scripts/beta_gates.py`'s `gate_three_console_truth` compares the last commit touching the report
against the last commit touching the console directory, and returns `CANNOT TELL` whenever the
console is newer. **The conservatism is right and the granularity is wrong.**

It watches all of `web/`. That means it will return `CANNOT TELL` after a commit that changes a
test file, a comment, a token value, a build config, or a script — none of which can change what a
screen asserts about data. Gate 3's question is about claims made over payload fields; most console
commits cannot touch that.

The consequence is the one the coordinator anticipated: a signal that fires on every commit is a
signal lanes learn to clear reflexively rather than read. This re-sign is genuine — four real
changes, one of them a new runtime — but the *next* one will fire on a CSS tweak, and the lane will
correctly notice that clearing it is ceremony.

**The refinement I would make**, offered for routing to Lane C since `scripts/` is its file and I
have not touched it: narrow the watched set from `web/` to the surfaces that can actually change a
claim — `web/src/features/**`, `web/src/components/**`, and `web/src/api/**` — excluding
`*.test.*`. That keeps every real risk (a render change or a payload-type change trips it) and
stops the alert firing on test-only, tooling and styling commits. It stays conservative: it can
still only say `MET` or `CANNOT TELL`, never `NOT MET`, so a narrowed watch cannot manufacture a
pass.

A stronger version exists — hash the payload-consuming surface rather than compare timestamps, so
a commit that touches those files without changing what they claim does not trip it either — but
that is more machinery than the problem currently justifies, and the path narrowing gets most of
the benefit for one line.

## Method note

API on 8799 and the console on 4199, both stopped afterwards and **confirmed dead by asking the
socket rather than by reading a log**. That mattered: killing the API left two orphaned
`multiprocessing.spawn` workers from uvicorn's reloader holding the port under a parent PID that no
longer existed — the exact trap `.claude/rules/console-dev-loop.md` documents — and the port kept
answering `200` after every process the obvious search found was dead. Both ports refuse
connections now. The Chrome viewport override was cleared.

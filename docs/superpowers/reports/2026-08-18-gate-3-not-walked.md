# Gate 3 — not walked, and why that is the answer rather than a delay

Historical: this report is unsigned on purpose. It records a walk that did not happen, so it
carries no `Signed:` line and must never be read as one. Gate 3 stays `CANNOT TELL`.

## The ruling this satisfies

Gate 3 signs last, against a frozen tree, because four lanes shipping console changes make any
walk stale before it is written up. The instruction was to confirm no lane had console work
outstanding, to abandon rather than sign if a change landed mid-walk, and — if a screen could not
be verified — to say which and why and leave the gate unmeasured. **Unmeasured is a legitimate
verdict.** This is that verdict, with its evidence.

## The measurement

The precondition question was put to the coordinator and timed out unanswered after 900 seconds.
Rather than wait or guess, the tree was measured directly, using the same path specification the
gate itself uses — `web/src`, excluding `*.test.*`, `*.css` and `*.md`.

Console changes on `origin/main`, 2026-08-18:

| landed | commit | |
|---|---|---|
| 12:16:19 | `e20afedb` | `M14-W432` Findings gets a destination |
| 11:53:35 | `4ca73c4a` | `M14-W444` no exempted links |
| 11:41:50 | `fea7c6f7` | `M14-W438` the run link was dead |
| 11:16:20 | `d05c5916` | `M14-W436` every finding and vendor link pointed at a dead route |

**Four changes in eighty-two minutes. The longest gap between them is twenty-three minutes.**

The bar applied was twenty-five minutes of quiet — chosen before the measurement, not after it,
and proposed to the coordinator in writing as a rule a worker could evaluate without a round trip.
**The console never cleared it.** That is not impatience: at this cadence there was no window in
which a walk could have started and finished against one tree.

## What was ready, so the next attempt is cheap

Everything except the tree standing still:

- **The stack is up and does not disturb anybody.** API on `8811`, console on `5173`, both
  answering. Port `8787` is held by another lane and was left alone; no seed was run, because the
  database already carried 67 call sites and the schema had completed.
- **The data is real.** Five repositories, ten open findings, `bindings_by_rung` populated.
- **Chrome is reachable** on `9222`, which `capture-console.mjs` needs.

A re-dispatch against a frozen tree can capture immediately.

## One thing found on the way, and fixed

`scripts/dev_up.py` started the API on `SYNC_API_PORT` and checked readiness on a hardcoded
`8787`. Its own busy-port message recommends setting `SYNC_API_PORT`, and the same message says a
busy port means *a readiness check would answer from whatever is already there* — so taking its
advice produced exactly that: the probe hit the old port and another lane's API answered it.
Fixed in `CI-W447`, derived from `API_PORT` and proven able to fail.

**This is why the walk was not attempted blind.** The environment that looked ready was reporting
readiness from somebody else's server.

## What would close this

One window in which no lane lands a change to `web/src` for long enough to capture nine screens
and read them. That is a scheduling decision rather than an engineering one, and it belongs to
whoever can hold the console lanes still.

The binding surface remains absent from `capture-console.mjs` and would have been recorded as
**not verified rather than assumed to pass**, exactly as the previous walk recorded it.

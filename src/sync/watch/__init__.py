"""The continuous watch loop: one idempotent tick a clock can call.

Sync ships no daemon and no scheduler -- the ruling in
`docs/superpowers/plans/2026-08-18-continuous-watch-loop.md` is that the contract is the tick,
and the clock is cron's, Task Scheduler's, or a CI schedule's. Everything here composes stages
that already exist; the only new state is `watch_subscription` and `vendor_cursor`.
"""

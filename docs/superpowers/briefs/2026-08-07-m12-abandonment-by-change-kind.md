# Brief — M12 Phase 1, first aggregate: which change kinds are not mechanically safe

You are working in your own Orca workspace. **Start by rebasing:**
`git fetch origin && git checkout -B m12-abandonment origin/console-identity`.

## Stay out of `web/`

**A second session owns the entire console presentation layer** and is working in parallel right now.
Nothing under `web/`, `DESIGN.md`, `.claude/rules/console-*.md` or the M7 plans is yours. **This item
builds no UI at all** — it is the query, the view model, the route and their tests. The panel that
renders it is a later item and belongs to whoever holds `web/` when it is scheduled.

Your territory: `src/sync/dashboard/`, `src/sync/api/`, `tests/`.

## The question this answers

`docs/superpowers/plans/2026-08-07-m12-dashboards-that-earn-their-screen.md` sets the rule for this
milestone: **the question first, the panel second.** A panel that cannot name the decision it changes
does not get built. This one answers:

> **Which change kinds are not mechanically safe, and which tier is failing them?**

The decision it changes is concrete: a change kind that abandons repeatedly at a given tier is a
routing-table row to correct, or a codemod to write. Today nobody can see that, because nothing
reads abandonment back.

`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` already argues that this data exists
for exactly this purpose — *"abandoned attempts are where routing learns which change kinds are not
mechanically safe"* — and then nothing ever learns from them. This closes that loop's first half.

## What to build

A new aggregate in `sync.dashboard`, a read-only route, and the tests for both.

**The grain is the whole problem, so start there.** `migration_outcome` is **one row per attempt**,
not one per finding. `schema.sql` says so and `CLAUDE.md` names it as the example: *"a query that
counts findings by counting rows is wrong, and wrong quietly."* A finding retried three times writes
three rows. So the aggregate must report **both** numbers and label them unambiguously:

- **attempts** — a count of rows.
- **findings** — a count of distinct `finding_id`.

A panel that shows one while its label implies the other is the defect this milestone exists to
avoid. Name the keys so they cannot be confused: `attempt_count` and `distinct_finding_count`, never
a bare `count`.

**The shape**, grouped by `change_kind` and by the tier that was routed:

- `change_kind`
- `tier` — the routing tier the attempt reached
- `attempt_count`, `distinct_finding_count`
- `abandoned_attempt_count`, and the distinct findings behind it
- the abandonment reasons that occurred, as a closed set with counts

`migration_outcome_kind_idx` already exists on `change_kind`, so the group-by has an index.

**Read the columns before you design the query.** `migration_outcome` carries `change_kind`,
`change_severity`, `vendor_id`, `from_version`, `to_version`, `language`, `symbol_shape`,
`arg_arity` and more. Do not assume which column holds the tier or the abandonment reason — find
them, and if the tier is not on the table say so in your report rather than inventing a join.

## What must not happen

- **No composite score, health figure, traffic light, green dot or "safety rating".** A change kind
  that abandons 3 of 4 times is not "25% healthy" — it is three abandonments with reasons, and the
  reasons are the useful part. This refusal is in `CLAUDE.md` and is not reopened by a number that
  looks ratio-shaped.
- **A rate needs a denominator that means something.** If you emit any ratio, the denominator is
  stated in the payload beside it. `has no denominator` is one of the twenty-four protected
  sentences precisely because this went wrong before.
- **Absence is not zero.** A change kind with no attempts has no row; that is not the same as one
  with attempts that never abandoned. The payload must let a caller tell them apart — do not emit a
  zero where the honest answer is "never seen".
- **The API stays read-only.** `test_no_route_reaches_past_the_read_surface`
  (`tests/test_api_routes.py`) holds this behaviourally and extends to every new route. A route it
  does not cover is an untested hole in the guarantee.
- **`sync.core` imports nothing from a sibling.** `tests/test_import_boundary.py` enforces it.

## How to work

Test first, and prove RED for the reason you expect before writing the query. Follow what
`tests/test_dashboard_fleet.py` and `tests/test_api_routes.py` already do rather than inventing a
second way to seed a fixture.

Postgres is on **port 5433**, not 5432 — `docker compose up -d` if it is not running. A fresh
worktree has no `tools/oasdiff`, so run `bash scripts/bootstrap_tools.sh` once or 38 unrelated tests
fail and look like your regression.

Pass `encoding="utf-8"` explicitly to every `read_text`, `write_text`, `open` and
`subprocess.run(..., text=True)`.

**5173 and 8789 are the owner's console and API — leave both alone.** If you want to see your route,
run your own API on a free port with `SYNC_API_PORT`, and stop it before you report, killing its
shell wrapper chain and not only the child process.

## Your gate

```sh
cd <your workspace> && uv run pytest tests/ -q -n0
```

Clean. Baseline at `3278124` is **3428 passed, 4 skipped**; yours should be that plus your new
tests. You do not need the web gates — you are not touching `web/`.

**Plus the thing that makes this an M12 item rather than a query:** state, in your report, what the
aggregate says about the seeded fixture. If it says nothing interesting because the fixture has too
few abandonments, **say that** — it is a fact about the fixture and a finding for the panel item,
not a failure of the query.

Conventional Commits, subject carrying the work item number **you take from
`docs/superpowers/WORKLOG.md` at the moment you start** — numbers have collided three times because
two sessions share this register, so read it immediately before you commit rather than trusting a
number from this brief. Push your branch. **No pull request, nothing on `main`.** Send `worker_done`
when you finish, and name every commit sha in it — a coordinator merged a branch tip once and missed
a second commit pushed after.

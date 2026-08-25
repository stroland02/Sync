# Recovering the Claude-app session's work — audit, 2026-08-24

The owner ran a session named **UI Design V2** in the Claude Code desktop app, against this same
repository and branch, on a different account. It hit its weekly usage limit mid-run. This is the
audit of whether any of its work was lost.

**Verdict: nothing was lost.** Everything it produced is on `main` or was deliberately superseded.
Recorded here so the next session does not spend the same hour re-deriving it.

## Where that session's record lives

Its transcript is on this machine, because the app and the CLI share `~/.claude/projects/`:

| | |
|---|---|
| Transcript | `~/.claude/projects/C--Users-sebastianr-Desktop-Terminal-Claude-Sync/eb6af36e-3bac-4d7a-b919-60dbd04c927c.jsonl` (18MB) |
| Identified by | 7,327 references to `ui-workflow-nav`, plus its own commit subjects |
| Dates | 2026-08-20 to 2026-08-21 |

**The app and the CLI share everything on disk.** `~/.claude/settings.json` (plugins, enabled
skills), `~/.claude/projects/` (transcripts), and the repository's own `.claude/` all carry over
between them. What does *not* carry over is the conversation context — which is why a session with
the same name in a different client starts cold.

## What it produced, and where each piece is now

**Thirteen work items, all on `main`:** `CI-W536`, `CI-W539`, `CI-W540`, `CI-W543`, `CI-W544`,
`CI-W545`, `CI-W547`, `CI-W548`, `CI-W549`, `CI-W550`, `CI-W551`, `CI-W552`, `CI-W553`.

**Eight commits stranded on `worktree-ui-workflow-nav`,** landed 2026-08-24 as `CI-W610`: the live
workflow thought-process panel, the Telemetry page as a live traffic instrument, the run activity
feed, and the findings Solution column.

**Five commits to the customer repository** (`../Sync Test Env/demo-v1`) — the AI concierge,
marketing copy on the legacy Completions API, tax compliance surfaces, and two build fixes. That
clone is clean with **zero unpushed commits**, and `github.com/stroland02/demo-v1` last received a
push at 2026-08-20T12:36:20Z.

## Everywhere else that was checked, and found empty

- **Five worktrees** — `Sync`, `sync-ground`, `st-rev`, `agent-af5449c8616e9ece8`, `ui-workflow-nav`
  — **zero uncommitted files** in every one.
- **No stashes.** (`git stash list` empty, which also means the `refs/stash` hazard in `CLAUDE.md`
  did not bite here.)
- **26 dangling commits.** Every one carrying a work item has that item on `main`. The two without
  one are a merge commit and `7b5b4330` *"wip: M15 Task 7 change units, backend and component
  complete, page not wired"* — which **is** wired on `main`: `IntegrationChangesPage` at
  `/repositories/:repoId/integration-changes`, with `change-units-table.tsx` and both API routes.
- **Six unreachable commits** from 2026-08-19, all duplicates of `CI-W535`, `CI-W536`, `CI-W538`
  and `CI-W540`. Two of those appear on `main` as *reverts* — "to be rebuilt from
  HANDOFF-console-features.md" — and **both were rebuilt**: `parked` appears in `api/types.ts` and
  `change-units-table.tsx`, and the clean-calls figure is in `api-surface-panel.tsx` (the rebuild
  landed as `CI-W549`). The HANDOFF brief itself is gone, consistent with a completed rebuild.
- **Three unmerged branches** — `preserve/dev-tree-2026-08-20`,
  `wip/dev-tree-preserved-2026-08-19`, `backup/revert-stack-2026-08-19`. They are dev-tree
  snapshots from the 2026-08-19/20 incident (`16be5880` is the one `CLAUDE.md` credits for that
  night being recoverable). Between them they hold **21 files `main` does not** — every one
  deliberately deleted later: `PageHeader` by `CI-W598`, the duplicate Supabase primitives by
  `CI-W599`, `routes-question.test.ts` by `CI-W597`, and `not-attached-state` / `subject-catalogue`
  / `roles.ts` by the Telemetry rewrite. All five components that looked like unique losses
  (`table-toolbar`, `rung-mix-card`, `page-tabs`, `findings-per-integration`, `sonner`) reached
  `main` and were removed on purpose.

## The mistake this audit corrects

The stranded branch was missed on the first sweep because branches were filtered **by name** —
`preserve/`, `backup/`, `wip/` read as archives — rather than by content. `git branch --no-merged`
plus `git fsck --lost-found` is the sweep that does not care what a branch is called, and it is
what found both the eight-commit branch and the 26 dangling commits.

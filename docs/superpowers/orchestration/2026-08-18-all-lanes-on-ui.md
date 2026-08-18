# Every lane on the UI, split by feature directory

**Owner directive, 2026-08-18: the UI is the main priority and all agent work moves to it.** Taken as
given. This is the split that lets five lanes work `web/` at once without the collision that has been
arbitrated four times today.

**The lane-owns-files rule is unchanged — only the file list moves.** `web/src/features/` is a
directory per surface, so the split is clean at the filesystem level rather than by convention.

| Lane | Owns, exclusively | Surface, from the verbatim brief |
|---|---|---|
| **B** | `web/src/features/workflows/**`, `web/src/layouts/**`, the sidebar and app chrome | **The solution workflow** — the largest item and the one the product argument rests on. Plus the chrome it already started tonight |
| **C** | `web/src/features/findings/**`, `web/src/features/bindings/**`, `web/src/features/pullrequests/**` | **The table format** for hundreds of rows — typed headers, sort, filter, pagination with a record count |
| **F** | `web/src/features/fleet/**`, `web/src/features/repositories/**` | **The Overview as the codebase dashboard** — fact tile grid, the totals line, per-vendor cards |
| **G** | `web/src/features/settings/**`, `web/src/features/vendors/**` | **Settings that contain settings**, plus the vendor/API-service cards. G already owns the settings API |
| **A** | `web/src/features/index-graph/**`, `web/src/features/signals/**`, `web/src/features/detectors/**` | **The indexing canvas** and **triage headers with counts** |

**Shared files nobody edits without saying so:** `DESIGN.md`, `web/src/vendor/supabase/**`,
`web/src/api/client.ts`. A change any of those needs goes through the coordinator, because they are
the three places a change breaks every lane at once.

## What does not change

**Read the verbatim brief and open the images.** `docs/superpowers/briefs/2026-08-18-owner-ui-brief-verbatim.md`
quotes the owner directly and names the image file for each point. The previous pass worked from
prose about those images and the owner's verdict was that it did not look different.

**The three refusals stand at the screens where they tempt.** No confidence scalars on the workflow.
No health tile on the Overview. No status dots on the sidebar. These are not polish to drop under
deadline; they are the argument the product makes.

**Test-first still applies, and the scope is `console-dev-loop.md`'s:** classification, derivation and
structural invariants. Never class names, never snapshots.

**Land each unit on `main` by fast-forward.** Five lanes in one directory makes unlanded work far more
expensive than it was this morning — a branch that sits is a branch that conflicts.

## The one thing still running that is not UI

`B7` is detached and watched by a monitor on Lane A. **It costs nothing to leave running** and it is
the only thing that can move Gate 1. Lane A does UI work while it finishes and reports the result
when it lands.

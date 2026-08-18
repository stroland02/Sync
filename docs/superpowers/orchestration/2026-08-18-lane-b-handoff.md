# Lane B handoff — the show-all removal, half landed

**Written at 98% context, on instruction to stop taking scope.** Everything described here is on
`main`; the working tree is clean. Commits are named rather than intentions.

## The measurement, and the exact grep

Use this, unchanged, so you measure what the coordinator measures:

```
grep -rn "repoId === null" web/src --include=*.tsx --include=*.ts     # excluding tests
```

**26 non-test branches before `M14-W400`, 20 after.**

| file | before | after | bucket |
|---|---|---|---|
| `features/vendors/vendor-findings-table.tsx` | 7 | 6 | **prop stays** — two callers |
| `features/bindings/binding-surface-page.tsx` | 4 | 4 | dead — delete |
| `features/vendors/vendor-page.tsx` | 3 | 3 | dead — delete |
| `layouts/scope-switchers.tsx` | 2 | 2 | **prop stays** — chrome, see below |
| `features/vendors/vendor-changes-table.tsx` | 2 | 1 | dead — orphaned component |
| `features/detectors/detectors-page.tsx` | 2 | **0** | done |
| `features/detectors/detector-accountability.tsx` | 2 | 1 | dead — one caller |
| `features/vendors/vendor-exposure-card.tsx` | 1 | **0** | done |
| `features/fleet/vendor-distribution.tsx` | 1 | 1 | dead — orphaned component |
| `features/fleet/fleet-page.tsx` | 1 | 1 | **LIVE — keep** (corrected, see below) |
| `api/client.ts` | 1 | 1 | **not narrowed, by ruling** |

## Which bucket each remaining branch is in

The coordinator's ruling, settled and reproduced here so nobody re-derives it:

> A component that is not a page is NOT narrowed by this ruling. The owner ruled on pages and
> screens. **The test is what a SCREEN renders, not what a component could render.** If a component
> is only ever mounted by one page, its null branch is dead and dead paths get deleted; if it has two
> callers with different scopes, the scope stays a prop.

Applied, with the caller counts measured rather than assumed
(`grep -rl "<ComponentName" web/src --include=*.tsx | grep -v test`):

- **`VendorFindingsTable` — 2 callers**, `features/fleet/vendor-distribution.tsx` and
  `features/repositories/open-findings-card.tsx`. **The scope stays a prop.** Its six branches are
  legitimate: forcing a route read into it would make it unmountable in the one place a broader view
  is legitimate. Do not touch these six.
- **`DetectorCatalogue` — 1 caller** (`detector-accountability.tsx`). Dead. Delete its branch.
- **`VendorChangesTable` — 0 non-test callers.** Orphaned. Its branch is dead; the component's own
  reachability is a separate question and is not mine to answer.
- **`VendorDistributionCard` — 0 non-test callers.** Same. `M14-W400` gave it a required `repoId`
  because it called `useOverview()` with no argument at all, counting every repository the index has
  seen — the show-all in its purest form.
- **`binding-surface-page` and `vendor-page`** held branches unreachable after `M14-W400` typed
  their `repoId` as `string`. Deleted in `M14-W405`.
- **`fleet-page` is a CORRECTION to this table.** I bucketed its branch as dead; it is **live**. That
  screen is the workspace *picker* at `/`, and its `repoId` comes from `resolveCodebaseScope`, which
  genuinely returns `unselected`, `none`, `pending` and `unknown`. `if (repoId === null) return null`
  is the guard that stops the fact band claiming a workspace nobody chose. Deleting it would have
  been the absence-into-zero failure this sweep exists to avoid, reached by trusting my own table
  over the code.
- **`layouts/scope-switchers.tsx` — chrome, not a screen.** Its two branches describe an *unset*
  switcher, which is exactly where the coordinator said an unscoped state belongs. Keep.
- **`api/client.ts` — deliberately not narrowed.** The transport may be asked an unscoped question by
  something that is not a page. That is a separate decision from what a screen renders.

## What landed

- **`M14-W400`, landed `ef103f13..967eda11`** — the urgent half. Three pages read their workspace
  from a **query string** while their route carried `:repoId`: `detectors-page`, `vendor-page`,
  `binding-surface-page`. All three read `useParams` now with an `UnknownRoute` guard.
- **`M14-W398`, landed `ab5a1770..bd5b34df`** — the vendor change-volume total was a page count
  wearing a vendor name. Reads `GET /api/vendors/{vendor_id}/change-volume` now; the client-side
  aggregate is deleted. Declared fenced-file edit: one new fetcher in `api/client.ts`.
- **`M14-W391`, landed `e54329b4..be353fec`** — the page header removed from eleven of twelve pages.
  `findings/finding-page.tsx` passes `actions` and was deliberately skipped for a human read.
- **`M14-W392`, landed `d1473da2..f5dcaccf`** — one charting library. `chart.tsx` deleted, `recharts`
  dropped; the console uses echarts.
- **`M14-W386`, landed `eee14693..aa9708ed`** — one region, every route scoped, `nav` added.
- **`M14-W388`, landed `fe50b835..f07c62cb`** — eighteen shadcn components with a separate MIT NOTICE
  section.

## What surprised me, and is worth carrying

**The instrument beat the grep.** Rather than delete branches a grep found, `M14-W400` tightened
`repoId: string | null` → `string` on seven components and let the compiler enumerate the callers.
That catches the ones spelled `!repoId` or `repoId == null`, which the grep does not, and it turned
the owner's ruling into a fact in the type system rather than a convention twenty-six branches were
free to ignore. It also surfaced one nobody had listed: `VendorDistributionCard` called
`useOverview()` with **no argument at all**.

**`npx shadcn add` does more and less than it says**, recorded in `M14-W387`
(`b783dfec..56e91c00`). It reached `button.tsx`, a file nobody named, as a transitive dependency and
**deleted a recorded contrast decision** — six lines explaining that the destructive variant's old
focus ring composited to 1.40:1 and 2.03:1 against its own surface, below the 3:1 non-text floor. No
guard here can see that: the colour guard catches literals and `ring-ring/50` is a token reference,
and class-name assertions are ruled out by `console-dev-loop.md`. Check `git status` after every
`add` and read the `M` lines, not the `??` lines.

**`prose-audit.mjs` was counting text no reader can see**, fixed in `M14-W385`
(`fcc481e1..8f30ad5d`). It selected every `<p>` including those inside a closed `<details>`. On the
remediation screen that was 827 of 3921 characters — 21%. Five lanes were cutting prose against those
ratios, and an inflated figure argues for deleting *visible* sentences to pay for invisible ones.
Re-read any ratio against the visible figure before cutting.

**JSX is not a regex problem.** The page-header sweep took three attempts: a non-greedy regex broke
four files because `trail={<Breadcrumbs />}` carries its own `/>`; a brace-depth scanner then handled
only the first header per file and only the inline form. The third looped and handled the assigned
form too. If you rewrite JSX mechanically, scan balanced, loop, and typecheck before believing it.

## The part I most want carried forward

**Nothing turned absence into zero.** No fleet-wide branch was replaced by a default, and every
screen that said what it had checked still says it. That was the standing risk in this whole sweep —
removing a scope mode is one edit away from turning *we have not indexed this workspace* into a
silent zero or an unexplained empty table — and it did not happen.

## Not done, and not started

- The 20 dead branches above. Mechanical, bucketed, ready.
- Mounting Lane I's dashboards 5 and 6 — reported propless, one import each. **Ask Lane I for the
  paths rather than searching.**
- The `openFindings / callSites` filled track captioned Clean/Active, from Lane H's handover. I never
  located it. It is a per-vendor composite *and* a rate, and the caption is a green dot written in
  words. Refuse it wherever it is.
- `finding-page.tsx` still has its page header, because it passes `actions`.
- **Six Python design-token guards are red on `main`** from other lanes' files — raw `gap-1`/`gap-2`/
  `p-3` and colour literals under `features/settings/` and elsewhere. None is in Lane B's diff. They
  are independent of the TypeScript build being green, and somebody should own them.
- `text-display` now has no consumer: `layouts/page-header.tsx` is dead code kept only because
  deleting it would leave `DESIGN.md` declaring a type step nothing spends, and `DESIGN.md` is
  fenced. **That is an owner decision, not a cleanup.**

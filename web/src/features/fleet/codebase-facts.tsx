/**
 * What is true about one codebase, as a band of facts that do not average.
 *
 * The Overview is a dashboard for the codebase you have already chosen — selection is chrome and
 * lives in the scope switcher (`2026-08-18-owner-console-review.md`, item 1). This band is the top
 * of that dashboard: six labelled facts, each read from a route that actually answers it, each
 * stating its own scope and its own limit.
 *
 * **No tile here averages another.** The reference project overview leads with `STATUS — Healthy`
 * over a cluster of dots; that is a composite health figure and it is refused on the record three
 * times over. A scalar over these six would collapse "we could not check" onto the same axis as
 * "we checked and it passed", which is the failure this console exists to replace. Every figure
 * names what it is counted over instead, and the two facts nothing here can answer say so in words.
 *
 * **Three tiles read `/api/repositories/{repo_id}/coverage`, and that route cannot see a
 * repository whose id contains a slash.** `app.py:422` declares it with the default path converter
 * while `:426-429` already use `{repo_id:path}` — filed as `B147`, Lane E's. So the tiles it feeds
 * render the console's absence marker naming that defect rather than a zero: absence and zero are
 * the distinction this product argues about, and a `?? 0` is exactly how it is lost. They come
 * alive with no change here the moment the converter is fixed.
 *
 * **The last run is read from change units, never from `/api/runs`.** `RunRow` carries no
 * `repo_id`, so the fleet's newest run rendered under a codebase's name would be an attribution
 * the transport cannot support — `codebases-panel.tsx` refuses the same claim on a row. A change
 * unit is scoped to a repository, and its `last_checkpoint_at` is the newest checkpoint behind that
 * codebase's own findings. It is staleness and never liveness: nothing in this payload tells a run
 * parked on the customer's CI from one that has died, which is why there is no dot beside it.
 *
 * **The rung is not a confidence score.** It is the class of evidence a finding rests on, and it
 * is the answer this console gives where a reference screen gives `Root cause confidence: 9`.
 */

import type { ReactNode } from "react"
import { useLocation } from "react-router"

import {
  useChangeUnits,
  useDetectors,
  useOverview,
  useRepositories,
  useRepositoryCoverage,
} from "@/api/queries"
import { NotFoundError } from "@/api/errors"
import {
  BINDING_SOURCES,
  type ChangeUnitRow,
  type ChangeUnitsPage,
  type DetectorAccountabilityResponse,
} from "@/api/types"
import { FactTile } from "@/components/fact-tile"
import { Skeleton } from "@/components/skeleton"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { boundedTotalCaveat, describeBoundedTotal } from "@/features/fleet/cardinality"
import { scopeFromLocation } from "@/layouts/scope-switchers"
import { formatTimestamp } from "@/lib/format"

/**
 * Which codebase this screen is about, and how that was decided.
 *
 * Six answers rather than a `string | null`, because the four that are not a repository id are
 * four different facts and a screen that collapsed them would claim one of them wrongly. `unknown`
 * in particular has to exist: every scoped route answers a repository the index has never seen
 * with a legitimate zero, so rendering the band for it would put six measurements on screen that
 * nothing measured.
 */
export type CodebaseScope =
  | { kind: "selected"; repoId: string }
  | { kind: "only"; repoId: string }
  | { kind: "unknown"; repoId: string }
  | { kind: "unselected"; available: number }
  | { kind: "none" }
  | { kind: "pending" }

/**
 * The codebase the address names, or the only one there is.
 *
 * The address wins, and it wins even while the repository list is in flight — a fact band that
 * waited on a membership check it has not received would blank the screen on every load for a
 * question it will answer a moment later. Once the list has arrived, an id absent from it is
 * reported as `unknown` rather than rendered.
 *
 * Falling back to the single repository is not an inference. With one repository in the index
 * there is nothing else the selected codebase could be, and the band says on screen that this is
 * how it was chosen. With several it refuses: picking one would be the console deciding what the
 * operator is looking at.
 */
export function resolveCodebaseScope(
  urlRepoId: string | null,
  repoIds: readonly string[] | undefined
): CodebaseScope {
  if (urlRepoId !== null) {
    if (repoIds !== undefined && !repoIds.includes(urlRepoId)) {
      return { kind: "unknown", repoId: urlRepoId }
    }
    return { kind: "selected", repoId: urlRepoId }
  }
  if (repoIds === undefined) return { kind: "pending" }
  if (repoIds.length === 0) return { kind: "none" }
  if (repoIds.length === 1) return { kind: "only", repoId: repoIds[0] }
  return { kind: "unselected", available: repoIds.length }
}

/**
 * The newest `indexed_at` across every vendor coverage reports for this codebase.
 *
 * `last_indexed` is keyed by vendor and holds only vendors with at least one indexed call site, so
 * an empty object is "the index holds no call site here", not "the index has never run" — and the
 * caller renders absence rather than a date either way.
 */
export function newestIndexedAt(lastIndexed: Record<string, string> | undefined): string | null {
  if (lastIndexed === undefined) return null
  const times = Object.values(lastIndexed)
  if (times.length === 0) return null
  return times.reduce((newest, candidate) => (candidate > newest ? candidate : newest))
}

export interface RungCount {
  readonly rung: string
  readonly count: number
}

/**
 * Open findings by the rung of the call site behind each, summed across every detector.
 *
 * `/api/detectors` reports `by_rung` per detector; the sum over them is the scope's own
 * distribution because every open finding belongs to exactly one detector. The declared rung order
 * is kept — `BINDING_SOURCES` is load-bearing elsewhere and a band that reordered it would read
 * differently from the composition chart for the same numbers — and any key the vocabulary does not
 * declare is appended rather than dropped, because a rung this console has never heard of is
 * exactly the fact a silent filter would hide.
 */
export function rungTally(
  detectors: DetectorAccountabilityResponse | undefined
): readonly RungCount[] {
  if (detectors === undefined) return []
  const totals = new Map<string, number>()
  for (const row of detectors.detectors) {
    for (const [rung, count] of Object.entries(row.by_rung)) {
      totals.set(rung, (totals.get(rung) ?? 0) + count)
    }
  }
  const declared = BINDING_SOURCES.filter((rung) => totals.has(rung)).map((rung) => ({
    rung: rung as string,
    count: totals.get(rung) as number,
  }))
  const undeclared = [...totals.keys()]
    .filter((rung) => !(BINDING_SOURCES as readonly string[]).includes(rung))
    .sort()
    .map((rung) => ({ rung, count: totals.get(rung) as number }))
  return [...declared, ...undeclared]
}

export interface NewestCheckpoint {
  readonly at: string
  readonly standing: ChangeUnitRow["standing"]
  /** Whether the page the answer was read from held every change unit in this scope. */
  readonly complete: boolean
}

/**
 * The newest checkpoint behind this codebase's change units, and the standing recorded with it.
 *
 * `standing` and `last_checkpoint_at` arrive null together, and a page on which every unit is null
 * is genuinely two facts at once — no run has ever been attempted for any finding here, or this
 * deployment has no checkpointer to ask. The payload cannot separate them, so this returns null and
 * the tile says both.
 *
 * `complete` is false when the route paged. The change-unit ordering is by the finding's own
 * creation time, not by checkpoint, so a max over one page is a max over the newest change units
 * rather than over the codebase — a real limit, and one the tile states rather than hides.
 */
export function newestCheckpoint(page: ChangeUnitsPage | undefined): NewestCheckpoint | null {
  if (page === undefined) return null
  let newest: ChangeUnitRow | null = null
  for (const row of page.items) {
    if (row.last_checkpoint_at === null) continue
    if (newest === null || row.last_checkpoint_at > (newest.last_checkpoint_at as string)) {
      newest = row
    }
  }
  if (newest === null) return null
  return {
    at: newest.last_checkpoint_at as string,
    standing: newest.standing,
    complete: page.items.length >= page.total,
  }
}

/**
 * Why the coverage route has no answer for this codebase.
 *
 * A 404 for an id carrying a slash is `B147` and nothing else: the route is declared with the
 * default path converter, which cannot match `host/owner/name`. Naming it keeps the tile from
 * reading as "this repository does not exist", which is the false claim the defect produces one
 * layer down. Every other failure is reported as itself.
 */
export function describeCoverageAbsence(repoId: string, error: unknown): string {
  if (error instanceof NotFoundError && repoId.includes("/")) {
    return (
      "the coverage route cannot match a repository id containing a slash, so it answers 404 for " +
      "every real repository id — filed as B147. This is a defect in the route, not a statement " +
      "that this codebase was never indexed."
    )
  }
  return "the coverage route did not answer for this codebase"
}

/** The standing word, from the closed vocabulary the checkpointer writes. Legible without colour. */
function describeStanding(standing: ChangeUnitRow["standing"]): string {
  return standing === "in_progress" ? "in progress" : (standing ?? "recorded without a standing")
}

/**
 * One tile's value across the three states a query has, so they cannot be spelled differently from
 * one tile to the next. A pending query says nothing on purpose; a failed one says which nothing.
 */
function TileValue({
  pending,
  failed,
  reason,
  width,
  children,
}: {
  pending: boolean
  failed: boolean
  reason: string
  width: string
  children: ReactNode
}) {
  if (pending) return <Skeleton width={width} />
  if (failed) return <Absent>{reason}</Absent>
  return <>{children}</>
}

export interface CodebaseFactsProps {
  readonly repoId: string
  /** How this codebase came to be the one on screen. A scope that does not say so is a claim. */
  readonly scopeNote: string
}

export function CodebaseFacts({ repoId, scopeNote }: CodebaseFactsProps) {
  const coverage = useRepositoryCoverage(repoId)
  const overview = useOverview(repoId)
  const detectors = useDetectors(repoId)
  const units = useChangeUnits({ repoId })

  const coverageReason = describeCoverageAbsence(repoId, coverage.error)
  const indexedAt = newestIndexedAt(coverage.data?.last_indexed)
  const rungs = rungTally(detectors.data)
  const checkpoint = newestCheckpoint(units.data)

  return (
    <div className="flex flex-col gap-section">
      <div className="flex flex-col gap-field">
        <h2 className="font-mono text-section text-foreground">{repoId}</h2>
        <p className="text-meta text-ink-muted">{scopeNote}</p>
      </div>

      <div className="grid gap-section grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <FactTile
          label="Last indexed"
          value={
            <TileValue
              pending={coverage.isPending}
              failed={coverage.isError}
              reason={coverageReason}
              width="w-40"
            >
              {indexedAt === null ? (
                <Absent>the index holds no call site here, so nothing has an indexed time</Absent>
              ) : (
                <Formatted value={formatTimestamp(indexedAt)} />
              )}
            </TileValue>
          }
          note="The newest indexed time across every vendor in this codebase. Staleness, not a promise the index is current: a codebase re-scanned weeks ago reports the same time every day after, until another re-index moves it."
        />

        <FactTile
          label="Call sites indexed"
          figure
          value={
            <TileValue
              pending={coverage.isPending}
              failed={coverage.isError}
              reason={coverageReason}
              width="w-16"
            >
              {coverage.data?.total_call_sites.toLocaleString()}
            </TileValue>
          }
          note="Every call site the index holds for this codebase, across every vendor."
        />

        <FactTile
          label="Vendors detected"
          figure
          value={
            <TileValue
              pending={coverage.isPending}
              failed={coverage.isError}
              reason={coverageReason}
              width="w-12"
            >
              {Object.keys(coverage.data?.by_vendor ?? {}).length.toLocaleString()}
            </TileValue>
          }
          note="Vendors with at least one indexed call site here. A vendor with no entry is a question this route cannot answer — whether the indexer looked and found nothing, or nothing declares which package to look for — never a zero."
        />

        <FactTile
          label="Open findings"
          figure
          value={
            <TileValue
              pending={overview.isPending}
              failed={overview.isError}
              reason="the overview route did not answer for this codebase"
              width="w-20"
            >
              {overview.data !== undefined &&
                describeBoundedTotal(
                  overview.data.total_findings,
                  overview.data.total_findings_bound_reached
                )}
            </TileValue>
          }
          note={
            overview.data?.total_findings_bound_reached === true
              ? boundedTotalCaveat(overview.data.total_findings_bound)
              : "Open findings against this codebase, across every vendor. A closed finding is invisible to this count, here as everywhere else in the console."
          }
        />

        <FactTile
          label="Open findings by rung"
          value={
            <TileValue
              pending={detectors.isPending}
              failed={detectors.isError}
              reason="the detector roll-up did not answer for this codebase"
              width="w-32"
            >
              {rungs.length === 0
                ? "No open finding, so no rung to attribute."
                : rungs.map((entry) => `${entry.rung} ${entry.count.toLocaleString()}`).join(" · ")}
            </TileValue>
          }
          note="The rung is the class of evidence a finding rests on — read out of the source, resolved, or correlated from watched traffic — and never a score for how sure a model is. It counts open findings; a rung breakdown over every binding in this codebase has no route today."
        />

        <FactTile
          label="Last run"
          value={
            <TileValue
              pending={units.isPending}
              failed={units.isError}
              reason="the change-unit route did not answer for this codebase"
              width="w-24"
            >
              {checkpoint === null ? (
                <Absent>
                  no change unit here carries a checkpoint: either no run has ever been attempted
                  for this codebase's findings, or this deployment has no checkpointer to ask, and
                  the payload cannot tell those apart
                </Absent>
              ) : (
                describeStanding(checkpoint.standing)
              )}
            </TileValue>
          }
          note={
            checkpoint === null
              ? "A run is attributed through the change units this codebase's open findings group into, because a run row carries no repository of its own."
              : (
                  /* The age is a component rather than an interpolated string, because a string
                     is formatted once and this note can sit on screen for hours. Decision 38. */
                  <>
                    Newest checkpoint <RelativeTime iso={checkpoint.at} />. A checkpoint age is
                    staleness, not liveness — it says how old the evidence is, not whether the run
                    is still going.
                    {checkpoint.complete
                      ? ""
                      : " Read across the change units on the first page, ordered by newest finding, not across every change unit in this codebase."}
                  </>
                )
          }
        />
      </div>
    </div>
  )
}

/**
 * The band as the Overview mounts it: the codebase the address names, or a plain statement of why
 * there is none.
 *
 * The scope key is `scope-switchers.tsx`'s own `?repo_id=`, read through its derivation rather than
 * restated here — one fact, one spelling. The Overview is not yet in `REPO_SCOPED_PATHS`, so the
 * switcher navigates away from it instead of rewriting the scope in place; that entry is the
 * switcher's file and belongs to another lane.
 */
export function CodebaseFactsBand() {
  return (
    <section aria-label="Codebase facts" className="flex flex-col gap-section">
      <CodebaseFactsBody />
    </section>
  )
}

/**
 * Which of the six scopes the address resolves to, rendered.
 *
 * Split from the band so the labelled section exists on the page whichever answer comes back. A
 * wrapper that appeared only once a codebase was chosen would make the screen's shape depend on the
 * scope, and the statement explaining why there is no codebase is exactly the thing that must not
 * be hard to find.
 */
function CodebaseFactsBody() {
  const { pathname, search } = useLocation()
  const repositories = useRepositories()
  const scope = resolveCodebaseScope(
    scopeFromLocation(pathname, search).repoId,
    repositories.data?.repo_ids
  )

  if (repositories.isError && scope.kind === "pending") {
    return (
      <ErrorState
        error={repositories.error}
        what="the list of repositories this codebase is chosen from"
        onRetry={() => void repositories.refetch()}
      />
    )
  }

  switch (scope.kind) {
    case "pending":
      return <LoadingState what="the selected codebase" />
    case "none":
      return (
        <EmptyState
          headline="The index has seen no repository."
          detail="This band states facts about one codebase, and there is none to state them about. A repository configured but never indexed writes no call site, so it has no entry here — that is absence, not a codebase with nothing in it."
        />
      )
    case "unselected":
      return (
        <EmptyState
          headline="No codebase is selected."
          detail={`The Overview is a dashboard for one codebase, and the index holds ${scope.available.toLocaleString()}. Nothing here states a figure until one is chosen, because a fleet-wide number rendered under a codebase's name is a false claim about that codebase. The scope switcher above opens a codebase's own screen rather than scoping this one: the Overview is not yet listed among the screens that take a repository scope, so this band reads the address.`}
        />
      )
    case "unknown":
      return (
        <EmptyState
          headline="The index has never seen this repository."
          detail={`Every scoped route answers ${scope.repoId} with a legitimate zero, and six zeros nobody measured is the claim this band exists to refuse. Choose a repository the index holds.`}
        />
      )
    case "only":
      return (
        <CodebaseFacts
          repoId={scope.repoId}
          scopeNote="The only repository the index holds, so it is the codebase this screen is about."
        />
      )
    case "selected":
      return <CodebaseFacts repoId={scope.repoId} scopeNote="Selected in the scope switcher." />
  }
}

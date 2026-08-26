/**
 * The four counts an operator acts on, published into the chrome's instrument bar.
 *
 * Owner ruling 2026-08-25: every page's figures live in the top bar's second 48px row, so the
 * canvas below is panes and nothing else. This used to be a grid of four tiles at the top of the
 * fleet screen, which spent a band of the first screen on facts the chrome now carries on every
 * screen — and left the bento's first row starting below the fold.
 *
 * **Four queries, not a new one.** Each tile reads the query its own panel below already issues, at
 * the same key, so the rail costs no request: `useRuns` is called with the same offset the runs panel
 * reads from the URL, which is what makes it one cache entry rather than two. A fifth aggregate route
 * that returned these four numbers would be a second answer to a question four routes already
 * answer, and the first time one of them disagreed nobody would know which was right.
 *
 * **A tile never renders an empty value**, which `fact-tile.tsx` states and this file is the first
 * caller to have to honour. Three states, and they are three different facts:
 *
 * - The query is in flight: `Skeleton`, at the width the count will be. It says nothing on purpose.
 * - The query failed: `Absent`, with which nothing it is — the panel below carries `ErrorState` and
 *   the sentence; a tile that repeated it would say one thing twice.
 * - The count is bounded: the `+` glyph from `describeBoundedTotal`, and the note says in words that
 *   the system stopped counting. The glyph is never the only channel — `cardinality.tsx` requires
 *   that, on the same grounds a status colour never travels without a word.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { usePrecedent, useDetectors, useOverview, useRepositories, useRuns } from "@/api/queries"
import { KpiStrip, type Kpi } from "@/components/kpi-strip"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"
import { describeBoundedTotal } from "@/features/fleet/cardinality"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * The one place a count turns into a tile value, so the three states cannot be spelled differently
 * from one tile to the next.
 *
 * `width` is the skeleton's, and it is the caller's decision because only the caller knows how many
 * digits are coming — a bar unrelated to its value reflows the rail when the value lands, which is
 * the one thing a skeleton exists to prevent.
 */
function CountValue({
  pending,
  failed,
  absent,
  text,
  width,
}: {
  pending: boolean
  failed: boolean
  /** Why this figure is not a number, when the read succeeded and the answer is still not one. */
  absent?: string | null
  text: string
  width: string
}) {
  if (pending) return <Skeleton width={width} />
  if (failed) return <Absent>the API did not answer</Absent>
  // The docstring below has argued since 2026-08-17 that a zero over an empty index is absence
  // rather than a measurement. The note said so while the value still printed `0`, and the status
  // band saying the opposite six inches down is what made the disagreement visible.
  if (absent) return <Absent>{absent}</Absent>
  return <>{text}</>
}

/**
 * What qualifies the open-findings count, which depends on whether anything was ever searched.
 *
 * A count of zero has two readings and the tile cannot carry both. When the index holds at least
 * one repository, zero open findings is a measurement — Sync read the code and flagged nothing —
 * and the note names the scope that measurement covers. When the index holds nothing, the same
 * zero is not a measurement at all: no call site has been read, so nothing could have been found,
 * and "across every vendor, every repository" describes a search that never ran.
 *
 * That second case is a design partner's first five minutes, and it is the one this console must
 * not get wrong: a clean bill of health for code nobody has opened is absence rendered as zero on
 * the exact axis the product argues about. Measured against an empty graph on 2026-08-17 and
 * recorded in `reports/2026-08-17-gate-3-empty-state.md`.
 *
 * The bounded-scan qualification still wins where it applies, because a count that stopped early
 * is a floor whatever the index holds.
 */
function openFindingsNote(
  overview: ReturnType<typeof useOverview>,
  repositories: ReturnType<typeof useRepositories>
): string {
  if (overview.isSuccess && overview.data.total_findings_bound_reached) {
    return `At least this many: counting stopped at ${overview.data.total_findings_bound.toLocaleString()}.`
  }
  if (repositories.isSuccess && repositories.data.repo_ids.length === 0) {
    return "No repository has been indexed, so nothing has been searched — this is not a measurement that found nothing."
  }
  return "Across every vendor, every repository."
}

export function FleetKpis() {
  // `Repositories indexed` is deliberately not one of these: its read succeeded and its answer is
  // zero, so it is the one figure here that a number describes correctly.
  const nothingSearched = (repositories: { isSuccess: boolean; data?: { repo_ids: string[] } }) =>
    repositories.isSuccess && repositories.data!.repo_ids.length === 0
      ? "no codebase indexed, so nothing has been searched"
      : null

  // The same offset the runs panel reads, so both share one query rather than issuing two.
  const [offset] = useOffsetParam("runs_offset")
  const overview = useOverview()
  const runs = useRuns({ limit: DEFAULT_LIMIT, offset })
  const repositories = useRepositories()
  const detectors = useDetectors()
  const corpus = usePrecedent()

  const items: readonly [Kpi, Kpi, Kpi, Kpi] = [
    {
      label: "Open findings",
      value: (
        <CountValue
          absent={nothingSearched(repositories)}
          pending={overview.isPending}
          failed={overview.isError}
          width="w-20"
          text={
            overview.isSuccess
              ? describeBoundedTotal(
                  overview.data.total_findings,
                  overview.data.total_findings_bound_reached
                )
              : ""
          }
        />
      ),
      note: openFindingsNote(overview, repositories),
    },
    {
      label: "Runs",
      value: (
        <CountValue
          absent={nothingSearched(repositories)}
          pending={runs.isPending}
          failed={runs.isError}
          width="w-20"
          text={runs.isSuccess ? runs.data.total.toLocaleString() : ""}
        />
      ),
      note: "One per checkpoint thread, not one per finding.",
    },
    {
      label: "Repositories indexed",
      value: (
        <CountValue
          pending={repositories.isPending}
          failed={repositories.isError}
          width="w-12"
          text={repositories.isSuccess ? repositories.data.repo_ids.length.toLocaleString() : ""}
        />
      ),
      note: "Holding at least one call site. Never indexed has no row.",
    },
    {
      label: "Repair attempts",
      value: (
        <CountValue
          absent={nothingSearched(repositories)}
          pending={corpus.isPending}
          failed={corpus.isError}
          width="w-16"
          text={corpus.isSuccess ? corpus.data.attempts.toLocaleString() : ""}
        />
      ),
      note: detectors.isSuccess
        ? `One row per attempt. ${detectors.data.detectors.length.toLocaleString()} ${
            detectors.data.detectors.length === 1 ? "detector has" : "detectors have"
          } open findings.`
        : "One row per attempt, not one per finding.",
    },
  ]

  return <KpiStrip items={items} />
}

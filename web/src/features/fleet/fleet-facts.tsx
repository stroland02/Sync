/**
 * The four counts an operator acts on, placed beside one another at the top of the fleet screen.
 *
 * This is the region that replaces the prose intro's job as the first thing on the page. The
 * paragraph is still there and still says what it said — it qualifies these figures rather than
 * standing in for them, which is the arrangement `references/direction/NOTES.md` describes and
 * `reports/2026-08-06-why-the-console-came-out-flat.md` says the console never had: "the console had
 * `text-meta` but never used it as a distinct register, so a label and the thing it labelled arrived
 * at the same weight and the eye had nothing to sort by."
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
import { useCorpus, useDetectors, useOverview, useRepositories, useRuns } from "@/api/queries"
import { FactTile } from "@/components/fact-tile"
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
  text,
  width,
}: {
  pending: boolean
  failed: boolean
  text: string
  width: string
}) {
  if (pending) return <Skeleton width={width} />
  if (failed) return <Absent>the API did not answer</Absent>
  return <>{text}</>
}

export function FleetFacts() {
  // The same offset the runs panel reads, so both share one query rather than issuing two.
  const [offset] = useOffsetParam("runs_offset")
  const overview = useOverview()
  const runs = useRuns({ limit: DEFAULT_LIMIT, offset })
  const repositories = useRepositories()
  const detectors = useDetectors()
  const corpus = useCorpus()

  return (
    <div className="grid gap-section sm:grid-cols-2">
      <FactTile
        label="Open findings"
        figure
        value={
          <CountValue
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
        }
        note={
          overview.isSuccess && overview.data.total_findings_bound_reached
            ? `At least this many: counting stopped at ${overview.data.total_findings_bound.toLocaleString()}.`
            : "Across every vendor, every repository."
        }
      />
      <FactTile
        label="Runs"
        figure
        value={
          <CountValue
            pending={runs.isPending}
            failed={runs.isError}
            width="w-20"
            text={runs.isSuccess ? runs.data.total.toLocaleString() : ""}
          />
        }
        note="One per checkpoint thread, not one per finding."
      />
      <FactTile
        label="Repositories indexed"
        figure
        value={
          <CountValue
            pending={repositories.isPending}
            failed={repositories.isError}
            width="w-12"
            text={repositories.isSuccess ? repositories.data.repo_ids.length.toLocaleString() : ""}
          />
        }
        note="Holding at least one call site. Never indexed has no row."
      />
      <FactTile
        label="Repair attempts"
        figure
        value={
          <CountValue
            pending={corpus.isPending}
            failed={corpus.isError}
            width="w-16"
            text={corpus.isSuccess ? corpus.data.attempts.toLocaleString() : ""}
          />
        }
        note={
          detectors.isSuccess
            ? `One row per attempt. ${detectors.data.detectors.length.toLocaleString()} ${
                detectors.data.detectors.length === 1 ? "detector has" : "detectors have"
              } open findings.`
            : "One row per attempt, not one per finding."
        }
      />
    </div>
  )
}

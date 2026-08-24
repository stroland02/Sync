/**
 * Telemetry: the Observe stage's page — what traffic actually showed up for one repository,
 * as a live instrument.
 *
 * The owner ruled twice (2026-08-19, 2026-08-20) that this page is about live signals, so the
 * "Attached by role" catalogue that used to fill it is gone from here: the vendor roster has
 * its own page under the Signal stage, and a role card was a fact about configuration sitting
 * where an operator comes to watch traffic. What remains is the KPI strip, the traffic
 * instrument (requests over time, the per-operation rollup, and the unattributed gap), and
 * the recorded-evidence tables `SignalSourcePanel` has always drawn.
 *
 * The page polls its one route every 15 seconds while mounted. No pulse and no `Live` badge —
 * `FetchedAt` states when the answer was last true, which is the honest form of "live".
 */

import { useParams } from "react-router"

import { useRepositoryObserved } from "@/api/queries"
import { FetchedAt } from "@/components/fetched-at"
import { ErrorState, LoadingState } from "@/components/states"
import { SignalsKpis } from "@/features/signals/signals-kpis"
import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"
import { TrafficOverTimeCard } from "@/features/telemetry/traffic-over-time-card"
import { TrafficRollupTable } from "@/features/telemetry/traffic-rollup-table"
import { UnattributedPanel } from "@/features/telemetry/unattributed-panel"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

const TELEMETRY_POLL_MS = 15_000

export function SignalsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <SignalsDetail repoId={repoId} />
}

/**
 * The strip's own read, kept out of `SignalsDetail` so a telemetry route that does not answer
 * costs the tiles and not the panels beneath.
 */
function SignalsKpisRegion({ repoId }: { repoId: string }) {
  const query = useRepositoryObserved(repoId)
  if (query.isPending) return <LoadingState what="the observed telemetry totals" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the observed telemetry totals"
        onRetry={() => void query.refetch()}
      />
    )
  }
  return <SignalsKpis observed={query.data} />
}

/**
 * The instrument: the chart leads, the rollup carries the figures, the unattributed panel
 * closes with the traffic nothing could attribute. This is the observer that keeps the
 * page's shared query polling.
 */
function TrafficInstrument({ repoId }: { repoId: string }) {
  const query = useRepositoryObserved(repoId, {}, { refetchIntervalMs: TELEMETRY_POLL_MS })
  // Loading and failure are already on screen: the KPI strip above reads the same route and
  // renders both states, and a second copy here would say one failure twice.
  if (!query.isSuccess) return null
  const { series, traffic, unattributed, telemetry_attached_at } = query.data
  // Never-attached is one fact about the repository and the evidence panel below says it
  // once. The rollup's "0 observed operations" is a measured nought, and drawing it for a
  // repository nobody watched would render one nothing as the other.
  if (telemetry_attached_at === null) return null
  return (
    <div className="flex flex-col gap-section">
      <FetchedAt
        at={query.dataUpdatedAt}
        polling
        idleReason="The poll stops when this page closes."
      />
      <TrafficOverTimeCard series={series} />
      <TrafficRollupTable repoId={repoId} traffic={traffic} />
      <UnattributedPanel unattributed={unattributed} />
    </div>
  )
}

function SignalsDetail({ repoId }: { repoId: string }) {
  // The band states the cadence rather than a count: every figure here belongs to a region with
  // its own read, and a total lifted to the band would be a second answer to a question the
  // regions already answer -- a differing one while any of their fetches is in flight.
  const status: StatusSegment[] = [
    {
      kind: "note",
      text: "Polled every 15 seconds while this screen is open. Each panel states when its own answer was last true.",
    },
  ]

  return (
    <ScreenFrame status={status}>
      <section className="flex flex-col gap-8">
      {/* Every tile distinguishes "no source attached" from "attached and quiet", which is
          the distinction this whole rung exists to make. */}
      <SignalsKpisRegion repoId={repoId} />

      <TrafficInstrument repoId={repoId} />

      {/* The recorded evidence under the instrument: observed calls, response shapes and
          error windows, with the never-attached / attached-and-quiet distinction those
          panels already carry. */}
        <SignalSourcePanel repoId={repoId} />
      </section>
    </ScreenFrame>
  )
}

/**
 * Metrics: the workspace's measured trends, in one place — the owner's naming scheme of
 * 2026-08-18 gives charts their own rail entry beside Findings' list.
 *
 * Composed from the dashboard cards that already exist rather than new queries: findings over
 * time and observed-call volume, each carrying its own scope statement and its own refusals.
 * A chart absent here is a chart whose data the graph does not hold yet — the dashboards plan
 * built all nine it could stand behind, and this page is their room, not a promise of more.
 *
 * **The status band is one segment per panel, because there is no instant at which this page is
 * loaded.** Five panels answer from four independent reads — the opening strip shares its two
 * with the two series beside it — so a single count would be true of one panel while the others
 * were still asking. Each segment carries its own absence and says in words which absence it is:
 * still asking, did not answer, or never measured are three facts and the glyph alone renders
 * them as one.
 */

import { useQuery } from "@tanstack/react-query"
import { useParams } from "react-router"

import { useFindingsOverTime, useRepositoryObserved } from "@/api/queries"
import { FindingsOverTimeCard } from "@/features/dashboards/findings-over-time-card"
import {
  ChangesOverTimeCard,
  fetchChangesOverTime,
} from "@/features/dashboards/changes-over-time-card"
import { observedVolumeByOperation } from "@/features/dashboards/observed-volume-option"
import { TrendsKpis } from "@/features/dashboards/trends-kpis"
import {
  AttemptsOverTime,
  fetchRemediationActivity,
} from "@/features/workflows/remediation-activity"
import { ObservedVolumeCard } from "@/features/dashboards/observed-volume-card"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

/**
 * The width `observed-volume-card.tsx` asks for, repeated rather than imported. Repeated because
 * `useRepositoryObserved` keys on the offsets and not on the limit: an observer here asking for a
 * narrower page would serve the card a truncated ranking out of the same cache entry.
 */
const OBSERVED_CALLS_LIMIT = 500

/** Which absence a figure is in, beside the glyph — a read still in flight is not a failed one. */
function absentScope(failed: boolean): string {
  return failed ? "did not answer" : "still asking"
}

export function MetricsPage() {
  const { repoId } = useParams<{ repoId: string }>()

  // The panels' own keys, so the band reads the answers already on screen rather than opening
  // four more requests for them.
  const findings = useFindingsOverTime(null)
  const changes = useQuery({
    queryKey: ["integration-changes", "over-time"],
    queryFn: ({ signal }) => fetchChangesOverTime(signal),
  })
  const attempts = useQuery({
    queryKey: ["corpus-activity"],
    queryFn: ({ signal }) => fetchRemediationActivity(signal),
  })
  const observed = useRepositoryObserved(repoId ?? "", { callsLimit: OBSERVED_CALLS_LIMIT })

  if (repoId === undefined) return <UnknownRoute />

  const activeDays =
    findings.isSuccess && changes.isSuccess
      ? new Set([
          ...findings.data.days.map((day) => day.day),
          ...changes.data.days.map((day) => day.day),
        ]).size
      : null

  const attemptCount = attempts.isSuccess
    ? attempts.data.days.reduce(
        (total, day) => total + Object.values(day.counts).reduce((sum, n) => sum + n, 0),
        0,
      )
    : null

  const volume = observed.isSuccess ? observedVolumeByOperation(observed.data) : null

  const status: StatusSegment[] = [
    {
      kind: "figure",
      label: "Days with activity",
      value: activeDays === null ? null : activeDays.toLocaleString(),
      scope:
        activeDays === null
          ? absentScope(findings.isError || changes.isError)
          : "days either series recorded something, never the length of the window",
    },
    {
      kind: "figure",
      label: "Findings recorded",
      value: findings.isSuccess ? findings.data.total.toLocaleString() : null,
      scope: findings.isSuccess
        ? "fleet-wide, including findings since closed"
        : absentScope(findings.isError),
    },
    {
      kind: "figure",
      label: "Changes published",
      value: changes.isSuccess ? changes.data.total.toLocaleString() : null,
      scope: changes.isSuccess
        ? "fleet-wide, by the watched integrations"
        : absentScope(changes.isError),
    },
    {
      kind: "figure",
      label: "Repair attempts",
      value: attemptCount === null ? null : attemptCount.toLocaleString(),
      scope:
        attemptCount === null
          ? absentScope(attempts.isError)
          : "every workspace rather than this one — one row is one attempt, not one finding",
    },
    {
      kind: "figure",
      // Never-measured is an absence and says so in words (B157): a repository nothing has looked
      // at would otherwise carry the same bare glyph as one whose read is still in flight.
      label: "Observed-call rows",
      value: volume?.telemetryAttached ? volume.totalRows.toLocaleString() : null,
      scope: !volume
        ? absentScope(observed.isError)
        : volume.telemetryAttached
          ? repoId
          : `never measured — no telemetry attached to ${repoId}`,
    },
  ]

  return (
    <ScreenFrame status={status}>
      <section className="flex flex-col gap-8">
        {/* Dashboard T1. Every page opens with its strip (owner ruling), and here the tiles
            are the totals the two charts below sum to -- which is what makes the charts
            checkable rather than merely decorative. */}
        <TrendsKpis />

        {/* Two subjects, deliberately adjacent (T2 and T3). The findings series is what Sync
            produced; the changes series is what the vendors published. A day with changes and no
            findings is the product working rather than a gap, and neither chart says that on its
            own — they say it by sitting together. */}
        <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
          <FindingsOverTimeCard />
          <ChangesOverTimeCard />
        </div>
        {/* Dashboard T4, the third subject on this screen: what Sync's own pipeline attempted.
            The three series answer what the vendors published, what Sync found, and what Sync did
            about it -- in that causal order, which is why they read down the page rather than
            summarising each other. */}
        <AttemptsOverTime />
        <ObservedVolumeCard />
      </section>
    </ScreenFrame>
  )
}

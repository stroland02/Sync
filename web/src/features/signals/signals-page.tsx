/**
 * Telemetry: the Observe stage's live instrument (owner rulings, 2026-08-19).
 *
 * This page is all about live signals. It led with a three-role integration catalogue until the
 * owner ruled the vendor and human-surface cards off it — the vendor roster lives on the Vendors
 * page and the delivery surface in Settings; what this page owes is what the traffic said. The
 * spec's M5 roles still exist as vocabulary; this level stopped being their catalogue.
 *
 * Top to bottom: the opening facts (requests, errors with their denominator, coverage of the
 * indexed surface, the unattributed gap), traffic per hour, traffic per operation, the
 * unattributed panel, then the raw record — the three tables the rollup is pooled from.
 *
 * **Polling, not a "live" badge.** The page re-asks every fifteen seconds while open and states
 * when it last asked. A pulse or a "live" label would claim a push this transport does not
 * have; a stamped time is a measured fact.
 *
 * **Absence apart from zero, unchanged.** Never-attached renders as the sentence it always had;
 * attached-and-quiet renders figures, including zeroes. The two must never merge (B157).
 */

import { useParams } from "react-router"

import { useRepositoryObserved } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { SignalsKpis } from "@/features/signals/signals-kpis"
import { SignalSourcePanel } from "@/features/telemetry/signal-source-panel"
import { TrafficOverTimeCard } from "@/features/telemetry/traffic-over-time-card"
import { TrafficRollupTable } from "@/features/telemetry/traffic-rollup-table"
import { UnattributedPanel } from "@/features/telemetry/unattributed-panel"
import { UnknownRoute } from "@/layouts/unknown-route"

/** The poll while the page is open. A number here is a promise the stamp below keeps. */
const POLL_MS = 15_000

export interface SignalsPageProps {
  readonly question?: string
}

export function SignalsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <SignalsDetail repoId={repoId} />
}

function SignalsDetail({ repoId }: { repoId: string }) {
  const query = useRepositoryObserved(repoId, {}, { refetchIntervalMs: POLL_MS })

  if (query.isPending) return <LoadingState what="the observed telemetry" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the observed telemetry"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const observed = query.data
  const attached = observed.telemetry_attached_at !== null

  return (
    <section className="flex flex-col gap-8">
      <SignalsKpis observed={observed} />

      {/* The freshness stamp is the honest form of a "live" badge: when the console last asked,
          and how often it re-asks — both measured facts about this page, not claims about a
          push. Rendered whenever a read has succeeded, including for a never-attached repo,
          because "checked just now, still nothing attached" is itself the live answer. */}
      <p className="text-meta text-ink-muted" data-testid="telemetry-freshness">
        As of {new Date(query.dataUpdatedAt).toLocaleTimeString()} — re-asked every{" "}
        {POLL_MS / 1000}s while this page is open.
      </p>

      {attached && (
        <>
          <TrafficOverTimeCard series={observed.series} />
          <TrafficRollupTable repoId={repoId} traffic={observed.traffic} />
          <UnattributedPanel unattributed={observed.unattributed} />
        </>
      )}

      {/* The raw record the rollup above is pooled from: per-unit-of-work calls, response
          shapes, error windows. Kept beneath the aggregates — a reader confirms a figure by
          opening the rows it was pooled from. This panel also carries the never-attached
          sentences when nothing is attached, so the page never renders empty tables as quiet. */}
      <SignalSourcePanel repoId={repoId} />
    </section>
  )
}

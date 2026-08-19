/**
 * Metrics: the workspace's measured trends, in one place — the owner's naming scheme of
 * 2026-08-18 gives charts their own rail entry beside Findings' list.
 *
 * Composed from the dashboard cards that already exist rather than new queries: findings over
 * time and observed-call volume, each carrying its own scope statement and its own refusals.
 * A chart absent here is a chart whose data the graph does not hold yet — the dashboards plan
 * built all nine it could stand behind, and this page is their room, not a promise of more.
 */

import { useParams } from "react-router"

import { FindingsOverTimeCard } from "@/features/dashboards/findings-over-time-card"
import { ChangesOverTimeCard } from "@/features/dashboards/changes-over-time-card"
import { TrendsKpis } from "@/features/dashboards/trends-kpis"
import { ObservedVolumeCard } from "@/features/dashboards/observed-volume-card"
import { PageTabs, metricsTabs } from "@/components/page-tabs"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function MetricsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Metrics" }]} />
      <PageTabs label="Metrics" tabs={metricsTabs(repoId)} />
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
      <ObservedVolumeCard />
    </section>
  )
}

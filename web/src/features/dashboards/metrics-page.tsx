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
      <FindingsOverTimeCard />
      <ObservedVolumeCard />
    </section>
  )
}

/**
 * The Overview's opening facts — the four numbers a reader wants before scrolling.
 *
 * **Strip only on this screen, by the owner's ruling of 2026-08-19.** The Overview already
 * carries the map, the topology card, the census and two panels; bindings-by-rung stays on
 * Detectors where it is built rather than being drawn twice.
 *
 * Each tile reads a query the page already issues, at the same key, so the strip costs no
 * request: React Query dedupes on the key, which is what makes four tiles free rather than
 * four round trips.
 *
 * **Three states per tile and they are three different facts** — in flight is a skeleton, a
 * failed read is the absence marker with which nothing it is, and a number is a number. A tile
 * that showed nought while its query was failing would be the collapse this console refuses.
 */

import { useQuery } from "@tanstack/react-query"

import { useOverview, useRepositoryCoverage } from "@/api/queries"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"
import { fetchTopology } from "@/features/repositories/api-topology-card"

/** The newest index time across the vendors coverage reports, or null when none is recorded. */
function newestIndexed(lastIndexed: Record<string, string> | undefined): string | null {
  const stamps = Object.values(lastIndexed ?? {}).filter(Boolean)
  if (stamps.length === 0) return null
  return stamps.reduce((newest, stamp) => (stamp > newest ? stamp : newest))
}

export function OverviewKpis({ repoId }: { repoId: string }) {
  const topology = useQuery({
    queryKey: ["api-topology", repoId],
    queryFn: ({ signal }) => fetchTopology(repoId, signal),
  })
  const overview = useOverview(repoId)
  const coverage = useRepositoryCoverage(repoId)

  const figure = (
    query: { isPending: boolean; isError: boolean },
    value: () => number | undefined,
    width: string
  ) => {
    if (query.isPending) return <Skeleton width={width} />
    if (query.isError) return <Absent>the API did not answer</Absent>
    const resolved = value()
    return resolved === undefined ? <Absent>this view cannot see it</Absent> : resolved.toLocaleString()
  }

  const indexedAt = newestIndexed(coverage.data?.last_indexed)

  return (
    <KpiStrip
      items={[
        {
          label: "Call sites indexed",
          value: figure(topology, () => topology.data?.totals.call_sites, "4rem"),
          note: "places this codebase calls an integration",
        },
        {
          label: "Integrations called",
          value: figure(topology, () => topology.data?.totals.vendors, "2rem"),
          note: `across ${topology.data?.totals.operations ?? "—"} operations`,
        },
        {
          label: "Open findings",
          value: figure(overview, () => overview.data?.total_findings, "3rem"),
          note:
            overview.data?.total_findings_bound_reached === true
              ? "at least this many — the count was bounded"
              : "detectors have these open here",
        },
        {
          label: "Last indexed",
          value:
            coverage.isPending ? (
              <Skeleton width="6rem" />
            ) : indexedAt === null ? (
              <Absent>no index pass recorded</Absent>
            ) : (
              <RelativeTime iso={indexedAt} />
            ),
          note: "newest pass across this codebase's integrations",
          figure: false,
        },
      ]}
    />
  )
}

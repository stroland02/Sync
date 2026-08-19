/**
 * The integration map's opening facts: how wide the API surface this canvas draws actually is.
 *
 * **Four counts, no composite, and no coupling score.** Integrations, operations, files and call
 * sites are four different widths of the same surface and none of them substitutes for another —
 * a codebase reaching three operations from a hundred files is a different shape from one
 * reaching a hundred operations from three, and a single "surface size" figure would render both
 * identically. `api-topology-card.tsx` carries the same refusal for the same reason.
 *
 * Reads `["api-topology", repoId]` — the key the topology card beneath uses, and the key the
 * Call sites page's dashboards use — so the strip is free wherever either has been opened.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchTopology } from "@/features/repositories/api-topology-card"
import { KpiStrip } from "@/components/kpi-strip"
import { ErrorState, LoadingState } from "@/components/states"

export function TopologyKpis({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["api-topology", repoId],
    queryFn: ({ signal }) => fetchTopology(repoId, signal),
  })

  if (query.isPending) return <LoadingState what="the API surface totals" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the API surface totals"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { totals, multi_vendor_files } = query.data

  return (
    <KpiStrip
      items={[
        {
          label: "Integrations called",
          value: totals.vendors.toLocaleString(),
          note: "this codebase binds a call site to each",
        },
        {
          label: "Operations reached",
          value: totals.operations.toLocaleString(),
          note: "distinct endpoints, not calls to them",
        },
        {
          label: "Call sites",
          value: totals.call_sites.toLocaleString(),
          note: `across ${totals.files.toLocaleString()} file${totals.files === 1 ? "" : "s"}`,
        },
        {
          label: "Files calling two or more",
          value: multi_vendor_files.length.toLocaleString(),
          // Where a change costs most, which is the one figure here that is not a plain width.
          note: "a change to either integration lands in the same file",
        },
      ]}
    />
  )
}

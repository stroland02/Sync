/**
 * Dashboard I1: the Integrations page's opening facts.
 *
 * **Every figure is a count the catalogue already computed**, not one derived here. `by_state`
 * and `total` come off `/api/integrations`, and the changes figure is a sum over the rows'
 * `changes_recorded` — summed in one place so the tile and the table cannot disagree.
 *
 * **The three states are not a funnel and the tiles do not imply one.** *Watched* means this
 * codebase calls it, *staged* means an adapter has fetched a spec for it, *available* means an
 * adapter exists and nothing has happened yet. A vendor can be staged without ever becoming
 * watched, because whether it is watched is a fact about the customer's code rather than about
 * Sync's progress. Labelling these as steps would make an integration nobody calls look like
 * work left undone.
 *
 * **No tile restates the table's footer.** The table beneath lists the vendors bound to this
 * repository; these tiles count the whole registry, which is a scope the table is filtered away
 * from — that is the `kpi-strip.tsx` rule, and it is why the "available" figure earns a slot
 * while a row count would not.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchCatalogue } from "@/features/vendors/catalogue"
import { KpiStrip } from "@/components/kpi-strip"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"

export function IntegrationsKpis({ repoId }: { repoId: string }) {
  const query = useQuery({
    queryKey: ["integrations-catalogue", repoId],
    // Same key as the Settings panel's, so the two share one read rather than issuing two.
    queryFn: ({ signal }) => fetchCatalogue(repoId, signal),
  })

  if (query.isPending) return <LoadingState what="the integrations catalogue" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the integrations catalogue"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { by_state, total, integrations } = query.data
  const changes = integrations.reduce((sum, row) => sum + row.changes_recorded, 0)

  return (
    <KpiStrip
      items={[
        {
          label: "Watched here",
          value: (by_state.watched ?? 0).toLocaleString(),
          note: "this codebase calls them",
        },
        {
          label: "Staged",
          value: (by_state.staged ?? 0).toLocaleString(),
          note: "a spec is cached, no call site found",
        },
        {
          label: "Available",
          value: (by_state.available ?? 0).toLocaleString(),
          note: `of ${total.toLocaleString()} adapters registered`,
        },
        {
          label: "Changes recorded",
          value:
            changes === 0 ? <Absent>none yet</Absent> : changes.toLocaleString(),
          // The scope matters and the tile states it: a vendor publishes to everyone, so this
          // is not a count of what happened to this codebase.
          note: "across every watched integration",
          figure: changes !== 0,
        },
      ]}
    />
  )
}

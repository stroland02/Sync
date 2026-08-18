/**
 * The dependency graph the Overview draws, and the mapping that feeds it.
 *
 * Owner decision 2 puts this panel beside the fact tiles on the first screen, which makes it not
 * optional. `DependencyCanvas` already draws the picture and already refuses what it must; this
 * file is the join between one scoped route and that canvas, and the whole of its work is not
 * losing a distinction on the way across.
 *
 * **What the route answers, and what it does not.** `/api/repositories/{repo_id}/graph` counts
 * call sites and names vendors. It does not count findings, so `openFindingCount` stays `null`
 * rather than becoming a zero this panel never read. `VendorInput` documents that `null` and a
 * count of nought are different facts, and this is exactly the seam where they get confused.
 *
 * **`bindingsQueried` is true here and that is a claim, not a formality.** The flag exists so a
 * vendor with no rows can say whether nothing was asked or the answer was none. This route asks
 * for every binding in one read, so when it answers, the answer arrived.
 *
 * **A truncated graph says so.** The route bounds what it draws and reports the total it was
 * bounded against. A picture quietly missing edges misreports a codebase's exposure, which is
 * the one thing the picture is for, so the notice below is not decoration.
 */

import { useRepositoryGraph } from "@/api/queries"
import type { RepositoryGraphResponse } from "@/api/types"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { DependencyCanvas } from "@/features/index-graph/dependency-canvas"
import type { BindingRow, VendorInput } from "@/features/index-graph/graph-layout"

export interface CanvasInput {
  vendors: VendorInput[]
  rows: BindingRow[]
}

/** The payload, as the canvas's two inputs, with every unanswered question left `null`. */
export function toCanvasInput(payload: RepositoryGraphResponse): CanvasInput {
  return {
    vendors: payload.vendors.map((vendor) => ({
      vendorId: vendor.vendor_id,
      openFindingCount: null,
      indexedCallSiteCount: vendor.indexed_call_sites,
      lastIndexed: vendor.last_indexed,
      bindingsQueried: true,
    })),
    rows: payload.bindings.map((binding) => ({
      vendor: binding.vendor_id,
      operation: binding.operation_id,
      file: binding.path,
      line: binding.line,
      symbol: binding.symbol,
      rung: binding.binding_rung,
    })),
  }
}

export function PartialGraphNotice({ drawn, total }: { drawn: number; total: number }) {
  return (
    <p className="text-meta text-muted-foreground">
      Drawing {drawn} of {total} call sites. The rest are indexed and reachable from the call-site
      tables; they are not drawn here because the picture stops being legible before the codebase
      stops having edges.
    </p>
  )
}

export function OverviewGraphPanel({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)

  if (query.isPending) {
    return <LoadingState what="the dependency graph" />
  }
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the dependency graph"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const payload = query.data
  const { vendors, rows } = toCanvasInput(payload)

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <div className="flex flex-col gap-field">
        <h2 className="text-emphasis font-medium text-foreground">Your codebase, out to its vendors</h2>
        <p className="text-meta text-muted-foreground">
          Every place <span className="font-mono">{repoId}</span> calls an API the index found,
          and the operation each call reaches.
        </p>
      </div>

      {payload.total_bindings === 0 ? (
        <EmptyState
          headline="No call site has been indexed for this codebase."
          detail="A vendor call appears here once INDEX has run against this repository and found one. A repository the index never ran against shows the same nothing as one that calls no vendor, and neither is a claim that it calls none."
        />
      ) : (
        <>
          <DependencyCanvas vendors={vendors} rows={rows} />
          {payload.truncated && (
            <PartialGraphNotice drawn={rows.length} total={payload.total_bindings} />
          )}
        </>
      )}
    </div>
  )
}

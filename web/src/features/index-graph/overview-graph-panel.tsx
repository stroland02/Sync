/**
 * The dependency graph the Overview draws.
 *
 * Owner decision 2 puts this panel beside the fact tiles on the first screen, which makes it not
 * optional. `FileTreeCanvas` already draws the picture and already refuses what it must -- this
 * file is the join between one scoped route and that canvas.
 *
 * **Replaces `DependencyCanvas` (2026-08-18).** Owner decisions 8 and 13
 * (`docs/superpowers/plans/2026-08-18-owner-ui-decisions.md`) supersede the vendor-first shape
 * `DependencyCanvas` drew in favour of a file tree with edges out to vendors -- see
 * `file-tree-canvas.tsx`'s own docstring. `FileTreeCanvas` takes the route's `bindings` directly;
 * there is no separate `vendors` input to assemble, since the tree derives its vendor nodes from
 * the bindings themselves.
 *
 * **A truncated graph says so.** The route bounds what it draws and reports the total it was
 * bounded against. A picture quietly missing edges misreports a codebase's exposure, which is
 * the one thing the picture is for, so the notice below is not decoration.
 */

import { Link } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ForceMap } from "@/features/index-graph/force-map"

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

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <div className="flex flex-wrap items-start justify-between gap-row">
        <div className="flex flex-col gap-field">
          <h2 className="text-emphasis font-medium text-foreground">Your codebase, out to its vendors</h2>
          <p className="text-meta text-muted-foreground">
            Every place <span className="font-mono">{repoId}</span> calls an API the index found,
            and the operation each call reaches.
          </p>
        </div>
        {payload.total_bindings > 0 && (
          <Link
            to={`/repositories/${encodeURIComponent(repoId)}/graph`}
            className="shrink-0 text-meta text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            View full graph
          </Link>
        )}
      </div>

      {payload.total_bindings === 0 ? (
        <EmptyState
          headline="No call site has been indexed for this codebase."
          detail="A vendor call appears here once INDEX has run against this repository and found one. A repository the index never ran against shows the same nothing as one that calls no vendor, and neither is a claim that it calls none."
          command={`uv run sync index --repo-id ${repoId}`}
        />
      ) : (
        <>
          <ForceMap rows={payload.bindings} />
          {payload.truncated && (
            <PartialGraphNotice drawn={payload.bindings.length} total={payload.total_bindings} />
          )}
        </>
      )}
    </div>
  )
}

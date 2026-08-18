/**
 * The indexing canvas as a page: `FileTreeCanvas` fed `GET /api/repositories/{repo_id}/graph`
 * through `useRepositoryGraph`, the same route `overview-graph-panel.tsx` draws its own copy of
 * the graph from.
 *
 * Scope comes from the route path parameter and never from a query string.
 *
 * **Two nothings, told apart.** This page used to render one empty state for both, and said so
 * in its own copy: "a repository the index never ran against shows the same nothing as one that
 * calls no vendor". That was honest about a payload that could not distinguish them.
 * `indexed_at` now can, and `index-state.ts` carries the classification — *never recorded* is
 * the canvas not being evidence about this codebase at all, and *indexed and found none* is a
 * measurement about it.
 *
 * **Off-path evidence is reported in every state, including the empty ones.** A repository whose
 * call sites were all retracted still holds observed traffic and unattributed findings, so
 * "nothing here" would drop what the graph is holding.
 *
 * **Not registered in `routes.ts`.** `docs/superpowers/plans/2026-08-18-workspace-is-the-only-
 * scope.md` gives that file to Lane B exclusively -- this component is built and ready, and the
 * route entry (path, region, level, question) is Lane B's to add.
 */

import { useParams } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { FileTreeCanvas } from "@/features/index-graph/file-tree-canvas"
import { classifyIndexState } from "@/features/index-graph/index-state"
import { OffPathNote } from "@/features/index-graph/off-path-note"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"

export interface IndexGraphPageProps {
  readonly question?: string
}

export function IndexGraphPage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <IndexGraphDetail repoId={repoId} />
}

function IndexGraphDetail({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)

  if (query.isPending) return <LoadingState what={`the indexed graph for ${repoId}`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`the indexed graph for ${repoId}`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const graph = query.data
  const state = classifyIndexState(graph)

  return (
    <section className="flex flex-col gap-8">
      {state.kind === "never-recorded" && (
        <div className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
          <h2 className="text-emphasis font-medium text-ink">
            Nothing has ever been recorded for <span className="font-mono">{repoId}</span>.
          </h2>
          <p className="max-w-prose text-body text-ink-muted">
            No call site has ever been written here. That is either an index that has not run
            against this repository, or one that ran and found no vendor call — and nothing
            records an index attempt, only its result, so this screen cannot tell you which. It is
            not a finding that this codebase calls no vendor.
          </p>
          <OffPathNote graph={graph} total={state.offPathTotal} />
        </div>
      )}

      {state.kind === "indexed-empty" && (
        <div className="flex flex-col gap-field rounded-surface border border-line bg-surface p-section">
          <h2 className="text-emphasis font-medium text-ink">
            Indexed, and holding no vendor call.
          </h2>
          <p className="max-w-prose text-body text-ink-muted">
            The index last wrote a call site for <span className="font-mono">{repoId}</span> on{" "}
            {formatTimestamp(state.indexedAt) ?? "a date it did not record"}, and none is current
            now. This is a measurement rather than an absence of one: something looked here. A
            repository whose calls have all since moved reads this way too, because a retracted
            call site still proves the index ran.
          </p>
          <OffPathNote graph={graph} total={state.offPathTotal} />
        </div>
      )}

      {state.kind === "drawn" && (
        <>
          {graph.truncated && (
            <p className="max-w-prose text-body text-muted-foreground">
              Drawing {graph.bindings.length} of {graph.total_bindings} call sites. The rest are
              indexed and reachable from the call-site tables; they are not drawn here because the
              picture stops being legible before the codebase stops having edges.
            </p>
          )}
          <FileTreeCanvas
            rows={graph.bindings}
            knownVendorIds={graph.vendors.map((v) => v.vendor_id)}
          />
          <OffPathNote graph={graph} total={state.offPathTotal} />
        </>
      )}
    </section>
  )
}

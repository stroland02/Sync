/**
 * The file tree, full screen, with this codebase's technical census beside it.
 *
 * **Owner ruling, 2026-08-19:** the Overview shows both maps small, and each opens into a page
 * that carries *its own* analytics. This page's subject is the codebase's shape — how it is laid
 * out, what it is made of, how old it is — so the census lives here rather than on the Overview.
 * The integration map's page carries the topology figures for the same reason.
 *
 * The tree fills the viewport, which is the reason this route exists separately from the
 * Overview's preview: the preview answers *what shape is this*, and the full view answers
 * *where is everything*.
 */

import { useParams } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import { ErrorState, LoadingState } from "@/components/states"
import { TreeMapD3 } from "@/features/index-graph/tree-map-d3"
import { CodebaseFactsCard } from "@/features/repositories/codebase-facts-card"
import { CodebaseFactsKpis } from "@/features/repositories/codebase-facts-kpis"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function FileTreePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <FileTreeDetail repoId={repoId} />
}

function FileTreeDetail({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "File tree" }]} />

      {/* The strip opens this page as it opens every other (owner ruling). Its subject is
          the tree's -- how large this codebase is and what it is made of -- so it reads the
          same census the card at the foot of the page draws in full, on one key. */}
      <CodebaseFactsKpis repoId={repoId} />

      {query.isPending && <LoadingState what={`the file tree for ${repoId}`} />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what={`the file tree for ${repoId}`}
          onRetry={() => void query.refetch()}
        />
      )}

      {query.isSuccess && (
        <>
          <div className="h-[calc(100svh-16rem)] min-h-[32rem]">
            <TreeMapD3 rows={query.data.bindings} fill />
          </div>
          {/* The census is this page's analytics: what the codebase is made of, measured with
              the index pass that produced the tree above it. */}
          <CodebaseFactsCard repoId={repoId} />
        </>
      )}
    </section>
  )
}

/**
 * The indexing canvas as a page: `FileTreeCanvas` fed `GET /api/repositories/{repo_id}/graph`
 * through `useRepositoryGraph`, the same route `overview-graph-panel.tsx` draws its own copy of
 * the graph from.
 *
 * **Not registered in `routes.ts`.** `docs/superpowers/plans/2026-08-18-workspace-is-the-only-
 * scope.md` gives that file to Lane B exclusively -- this component is built and ready, and the
 * route entry (path, region, level, question) is Lane B's to add. `level: "API Services"` is the
 * fit if a citation is needed: this canvas aggregates over that level's vendors the same way
 * `/detectors` aggregates over Errors & Incidents, per `.claude/rules/console-hierarchy.md`.
 */

import { useParams } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { FileTreeCanvas } from "@/features/index-graph/file-tree-canvas"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"

const DEFAULT_QUESTION = "What does this codebase actually call, and what has the index found there?"

export interface IndexGraphPageProps {
  readonly question?: string
}

export function IndexGraphPage({ question = DEFAULT_QUESTION }: IndexGraphPageProps) {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <IndexGraphDetail repoId={repoId} question={question} />
}

function IndexGraphDetail({ repoId, question }: { repoId: string; question: string }) {
  const query = useRepositoryGraph(repoId)

  return (
    <section className="flex flex-col gap-8">
      <PageHeader
        title={<span className="font-mono">{repoId}</span>}
        question={question}
        trail={<Breadcrumbs trail={[{ label: "Index" }]} />}
      />

      {query.isPending && <LoadingState what={`the file tree for ${repoId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`the file tree for ${repoId}`} onRetry={() => void query.refetch()} />
      )}
      {query.isSuccess && query.data.bindings.length === 0 && (
        <EmptyState
          headline={`No call site has been indexed for ${repoId} yet.`}
          detail="A vendor call appears here once INDEX has run against this repository and found one. A repository the index never ran against shows the same nothing as one that calls no vendor, and neither is a claim that it calls none."
        />
      )}
      {query.isSuccess && query.data.bindings.length > 0 && (
        <>
          {query.data.truncated && (
            <p className="max-w-prose text-body text-muted-foreground">
              Drawing {query.data.bindings.length} of {query.data.total_bindings} call sites. The
              rest are indexed and reachable from the call-site tables; they are not drawn here
              because the picture stops being legible before the codebase stops having edges.
            </p>
          )}
          <FileTreeCanvas
            rows={query.data.bindings}
            knownVendorIds={query.data.vendors.map((v) => v.vendor_id)}
          />
        </>
      )}
    </section>
  )
}

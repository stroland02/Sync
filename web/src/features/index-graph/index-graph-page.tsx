/**
 * The indexing canvas as a page: `FileTreeCanvas` fed real data through `useRepositoryRiskRows`.
 *
 * **Not registered in `routes.ts`.** `docs/superpowers/plans/2026-08-18-workspace-is-the-only-
 * scope.md` gives that file to Lane B exclusively -- this component is built and ready, and the
 * route entry (path, region, level, question) is Lane B's to add once the workspace-scoped
 * routing shape it describes lands. `level: "API Services"` is the fit if a citation is needed:
 * this canvas aggregates over that level's vendors the same way `/detectors` aggregates over
 * Errors & Incidents, per `.claude/rules/console-hierarchy.md`.
 */

import { useParams } from "react-router"

import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { FileTreeCanvas } from "@/features/index-graph/file-tree-canvas"
import { useRepositoryRiskRows } from "@/features/index-graph/use-repository-risk-rows"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"

const DEFAULT_QUESTION = "What does this codebase actually call, and what has Sync found there?"

export interface IndexGraphPageProps {
  readonly question?: string
}

export function IndexGraphPage({ question = DEFAULT_QUESTION }: IndexGraphPageProps) {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />
  return <IndexGraphDetail repoId={repoId} question={question} />
}

function IndexGraphDetail({ repoId, question }: { repoId: string; question: string }) {
  const query = useRepositoryRiskRows(repoId)

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
      {query.isSuccess && query.data.rows.length === 0 && (
        <EmptyState
          headline={`Nothing to draw for ${repoId} yet.`}
          detail="Either the index has not found a call site here, or none of them currently have an open finding -- this canvas draws call sites with an open finding, not every file the index holds."
        />
      )}
      {query.isSuccess && query.data.rows.length > 0 && (
        <>
          {query.data.truncated && (
            <p className="max-w-prose text-body text-muted-foreground">
              This repository has more open findings than this canvas fetched in one page. The
              tree below is a real subset, not the whole graph -- say so rather than silently
              drawing an incomplete picture as if it were complete.
            </p>
          )}
          <FileTreeCanvas rows={query.data.rows} />
        </>
      )}
    </section>
  )
}

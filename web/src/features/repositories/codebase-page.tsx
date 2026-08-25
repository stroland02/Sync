/**
 * Codebase: the selected repository, and the root of everything beneath it.
 *
 * Every figure here and on every screen below is scoped to `repoId` and names the scope it was
 * computed in. Owner ruling 2026-08-19: this screen shows the shape of the loop and the doors into
 * it, never a truncated copy of a screen below it, and no figure combines the five stages -- a
 * scalar over "what we read", "what we watched" and "what is broken" would collapse three kinds of
 * not-knowing onto one axis. No runs panel and no repair record until `B149` closes: `RunRow`
 * carries no `repo_id` and `/api/precedent` accepts no repository parameter, so either would render
 * every repository's rows under one repository's name (`codebase-page.test.tsx` holds the absence).
 */

import { Link, useParams } from "react-router"

import { Button } from "@/components/ui/button"
import { MapPreviews } from "@/features/index-graph/map-previews"
import { WorkflowGrid } from "@/features/repositories/workflow-grid"
import { PipelineStrip } from "@/features/repositories/pipeline-strip"
import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import { useRepositoryGraph, useRepositoryCoverage } from "@/api/queries"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"


/** The two map previews, fed one read: both draw the same bindings. */
function MapsRegion({ repoId }: { repoId: string }) {
  const query = useRepositoryGraph(repoId)
  if (query.isPending) return <LoadingState what="the codebase maps" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="the codebase maps"
        onRetry={() => void query.refetch()}
      />
    )
  }
  if (query.data.total_bindings === 0) {
    return (
      <EmptyState
        headline="No call site has been indexed for this codebase."
        detail="Both maps draw indexed call sites, and there are none. A vendor call appears once INDEX has run against this repository and found one -- a repository the index never ran against shows the same nothing as one that calls no vendor, and neither is a claim that it calls none."
          command={`uv run sync index --repo ${repoId}`}
      />
    )
  }
  return <MapPreviews repoId={repoId} bindings={query.data.bindings} />
}

export interface CodebasePageProps {
  readonly question?: string
}

export function CodebasePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return <CodebaseScreen repoId={repoId} />
}

/**
 * The screen itself, split from the route guard so the band's two reads are unconditional hooks.
 */
function CodebaseScreen({ repoId }: { repoId: string }) {
  // Both reads are already issued below and React Query dedupes on the key, so counting them
  // here costs no request.
  const graph = useRepositoryGraph(repoId)
  const coverage = useRepositoryCoverage(repoId)

  const surface =
    coverage.isSuccess && coverage.data.repo_id === repoId ? coverage.data.by_binding_status : null
  // `null` until coverage answers, a number once it has -- including a counted zero. Collapsing
  // the two rendered an unanswered read as a measured absence under a scope string asserting it.
  const operations =
    surface === null ? null : Object.values(surface).reduce((sum: number, n) => sum + Number(n ?? 0), 0)

  const figures: StatusSegment[] = [
    {
      kind: "figure",
      label: "Operations",
      // An empty `binding_status_rollup` is no call site at all, not three examined zeroes.
      value: operations === null ? null : operations.toLocaleString(),
      scope: "counted once each, however many times called",
    },
    {
      kind: "figure",
      label: "Call sites",
      value: graph.isSuccess ? graph.data.total_bindings.toLocaleString() : null,
      scope: "indexed in this repository",
    },
    {
      kind: "figure",
      label: "Integrations",
      value: graph.isSuccess ? graph.data.vendors.length.toLocaleString() : null,
      scope: "called by this repository",
    },
  ]

  // Before either read answers, three absence glyphs would say what is missing and not why.
  const status: StatusSegment[] =
    graph.isSuccess || coverage.isSuccess
      ? figures
      : [
          {
            kind: "none",
            why:
              graph.isError || coverage.isError
                ? "the graph did not answer for this codebase"
                : "asking the graph about this codebase",
          },
        ]

  return (
    <ScreenFrame status={status}>
      <section className="flex flex-col gap-8">
        <PageHeaderRegion repoId={repoId} />
        {/* Getting started leads, the pipeline follows -- owner ruling 2026-08-25. A new
            operator meets setup before metrics. */}
        <GettingStartedCard repoId={repoId} />
        <PipelineStrip repoId={repoId} />
        {/* The integration map and the file tree are the two the owner kept on 2026-08-25.
            The stage-door grid went with the rest: every dashboard on this screen is to be
            rebuilt against the Stitch references rather than reskinned in place. */}
        <MapsRegion repoId={repoId} />

        <WorkflowGrid repoId={repoId} />
        {/* Good news as a number, W541 owner-picked: verified clean beside at risk. */}
      </section>
    </ScreenFrame>
  )
}

function PageHeaderRegion({ repoId }: { repoId: string }) {
  // The Scope sentence that used to fill this bar was ruled out on 2026-08-25 -- the trail and
  // the workspace switcher already scope the page. One action survives it.
  return (
    <div className="flex justify-end">
      <Button asChild variant="outline" size="sm">
        <Link to={`/repositories/${encodeURIComponent(repoId)}/observed`}>
          Signals for this repository
        </Link>
      </Button>
    </div>
  )
}

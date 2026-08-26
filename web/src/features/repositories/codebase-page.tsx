/**
 * Codebase: the selected repository, as a viewport-locked bento of four panes.
 *
 * Two maps across the top row, the setup stepper and the stage doors across the bottom; the grid
 * fills the window and each pane scrolls its own body, so nothing on this screen is below a fold.
 * Every figure here and on every screen below is scoped to `repoId` and names the scope it was
 * computed in. Owner ruling 2026-08-19: this screen shows the shape of the loop and the doors into
 * it, never a truncated copy of a screen below it, and no figure combines the five stages -- a
 * scalar over "what we read", "what we watched" and "what is broken" would collapse three kinds of
 * not-knowing onto one axis. No runs panel and no repair record until `B149` closes: `RunRow`
 * carries no `repo_id` and `/api/precedent` accepts no repository parameter, so either would render
 * every repository's rows under one repository's name (`codebase-page.test.tsx` holds the absence).
 */

import { useParams } from "react-router"

import { FileTreePane, IntegrationMapPane } from "@/features/index-graph/map-previews"
import { WorkflowGrid } from "@/features/repositories/workflow-grid"
import { PipelineStrip } from "@/features/repositories/pipeline-strip"
import { GettingStartedCard } from "@/features/repositories/getting-started-card"
import { useRepositoryGraph, useRepositoryCoverage } from "@/api/queries"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

export function CodebasePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return <CodebaseScreen repoId={repoId} />
}

/**
 * The screen itself, split from the route guard so the band's two reads are unconditional hooks.
 */
function CodebaseScreen({ repoId }: { repoId: string }) {
  // Both reads are already issued by the panes below and React Query dedupes on the key, so
  // counting them here costs no request.
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
    <ScreenFrame status={status} layout="locked">
      {/* Outside the grid, a sibling before it: inside the chassis this renders a portal into the
          top bar and no in-place DOM at all, and outside one its fallback strip must land above
          the bento rather than being auto-placed into a cell. */}
      <PipelineStrip repoId={repoId} />

      {/* Row A holds the two maps at equal span, which is the 2026-08-19 ruling made structural:
          neither map summarises the other, so no viewport may rank them. Row B takes the compact
          action column beside the wide card grid. */}
      <div className="bento-lock grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-8 lg:grid-cols-12">
        <IntegrationMapPane repoId={repoId} span="lg:col-span-6" />
        <FileTreePane repoId={repoId} span="lg:col-span-6" />
        <GettingStartedCard repoId={repoId} span="lg:col-span-4" />
        <WorkflowGrid repoId={repoId} span="lg:col-span-8" />
      </div>
    </ScreenFrame>
  )
}

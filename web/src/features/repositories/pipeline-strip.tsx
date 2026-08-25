/**
 * The pipeline this workspace is in, drawn: five stages, one measured figure each, every stage a
 * door into the page that answers it.
 *
 * The rail groups its rows by the same `WORKFLOW_STAGES`, and this is that story as a shape rather
 * than as a list Ã¢â‚¬â€ what Sync read, what the vendors published, what traffic arrived, what broke,
 * and what was done about it, in the order those happen.
 *
 * **Not a `KpiStrip`, and the five cells are why.** That component takes three or four because four
 * tiles divide a page evenly and five leave a widow; a pipeline has as many cells as it has stages,
 * and dropping one to fit a grid would let the layout decide what the product does.
 *
 * **Nothing here is drawn to scale.** `remediation-flow.tsx` records the rule and the caption
 * repeats it on screen: the stages count call sites, integrations, calls and findings, which are
 * four different units, so a band whose width meant a proportion would mean nothing. The connectors
 * carry order and no magnitude.
 */

import { ChevronRight } from "lucide-react"
import { Fragment, type ReactNode } from "react"
import { Link } from "react-router"

import { useOverview, useRepositoryGraph, useRepositoryObserved } from "@/api/queries"
import { FactTile } from "@/components/fact-tile"
import { InfoHint } from "@/components/info-hint"
import { RelativeTime } from "@/components/relative-time"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"
import { createPortal } from "react-dom"

import { STAGE_DOES, pagesByStage } from "@/lib/stage-pages"
import { useTopbarStatsTarget } from "@/layouts/topbar-stats"
import { destinationHref, type RouteEntry, type WorkflowStage } from "@/lib/stage-pages"

interface StageFigure {
  value: ReactNode
  /** What the figure counts. Never omitted: a bare number is whatever the reader guesses. */
  unit: string
  /** `false` for anything that is not a number, which takes the body step instead. */
  figure: boolean
}

/** A figure in the three states a query has, which are three different facts. */
function counted(
  query: { isPending: boolean; isError: boolean },
  value: () => number | undefined,
  unit: string,
  width: string
): StageFigure {
  if (query.isPending) return { value: <Skeleton width={width} />, unit, figure: false }
  if (query.isError) return { value: <Absent>the API did not answer</Absent>, unit, figure: false }
  const resolved = value()
  if (resolved === undefined) {
    return { value: <Absent>this view cannot see it</Absent>, unit, figure: false }
  }
  return { value: resolved.toLocaleString(), unit, figure: true }
}

function StageCell({
  stage,
  figure,
  destination,
  href,
}: {
  stage: WorkflowStage
  figure: StageFigure
  destination: RouteEntry
  href: string
}) {
  return (
    <Link
      to={href}
      title={`${stage} ${STAGE_DOES[stage]} Ã¢â‚¬â€ open ${destination.label}`}
      className="flex min-w-0 flex-1 flex-col rounded-control px-section py-row transition-colors hover:bg-surface-subtle focus:outline-none focus:ring-1 focus:ring-ring"
    >
      <FactTile
        label={stage}
        value={figure.value}
        figure={figure.figure}
        note={
          <>
            <span className="block">{figure.unit}</span>
            <span className="block text-ink">{destination.label} &rarr;</span>
          </>
        }
      />
    </Link>
  )
}

/** The order marker between two stages: vertical while the cells stack, horizontal once they do not. */
function StageJoin() {
  return (
    <li aria-hidden="true" className="flex items-center justify-center px-field">
      <ChevronRight className="size-4 rotate-90 text-graphics lg:rotate-0" />
    </li>
  )
}

export function PipelineStrip({ repoId }: { repoId: string }) {
  const overview = useOverview(repoId)
  const graph = useRepositoryGraph(repoId)
  const observed = useRepositoryObserved(repoId)

  const attached = observed.data?.telemetry_attached_at ?? null
  const figures: Record<WorkflowStage, StageFigure> = {
    Index: counted(graph, () => graph.data?.total_bindings, "call sites indexed", "4rem"),
    Signal: counted(graph, () => graph.data?.vendors.length, "integrations called", "2rem"),
    // An empty page of calls under telemetry nobody attached is nobody having looked, and the
    // payload carries the attachment stamp precisely so the two do not render alike (B157).
    Observe:
      observed.isSuccess && attached === null
        ? {
            value: <Absent>telemetry never attached</Absent>,
            unit: "no source is reporting here",
            figure: false,
          }
        : counted(observed, () => observed.data?.calls.total, "calls observed", "3rem"),
    Detect: counted(overview, () => overview.data?.total_findings, "open findings", "3rem"),
    // No run and no pull request carries a repository (B149), so this stage has no figure this
    // screen may print: a fleet-wide count under one workspace's name is the attribution
    // `codebase-page.test.tsx` exists to keep off this page.
    Remediate: {
      value: <Absent>not counted per workspace</Absent>,
      unit: "a run carries no repository yet",
      figure: false,
    },
  }

  // In the chrome, compact -- owner ruling 2026-08-25: the pipeline reads as one line in the
  // top bar on every page load of this screen. Each stage keeps its link, an uncounted stage
  // keeps its dash with the reason one hover away, and the arrows say the order without
  // asserting a proportion. Outside the chassis the full strip below still renders.
  const target = useTopbarStatsTarget()
  if (target !== null) {
    return createPortal(
      <>
        {pagesByStage().map(({ stage, pages }) => {
          const destination = pages[0]
          const href = destinationHref(destination, { repoId })
          if (href === null) return null
          const figure = figures[stage]
          // The same instrument cell the KPI segments take: full-width even division, label
          // centered over value, the stage's sentence one hover away. The arrows went with the
          // owner's simpler form -- the order is the order of the cells.
          return (
            <Link
              key={stage}
              to={href}
              title={`${stage} — ${typeof figure.unit === "string" ? figure.unit : ""}`}
              className="flex h-full min-w-0 flex-1 flex-col items-center justify-center px-row text-center transition-colors hover:bg-surface-subtle focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <span className="truncate font-furniture text-ink-secondary">{stage}</span>
              <span className="min-w-0 max-w-full truncate font-mono text-body font-medium text-ink">
                {figure.figure === false ? "—" : figure.value}
              </span>
            </Link>
          )
        })}
      </>,
      target,
    )
  }

  return (
    <section aria-label="The pipeline in this workspace" className="flex flex-col gap-section">
      <div className="flex flex-wrap items-baseline justify-between gap-row">
        <div className="flex items-center gap-row">
          <h2 className="furniture text-meta text-ink-muted">The pipeline in this workspace</h2>
          <InfoHint label="About the pipeline">
            Five stages, in the order they run: Index reads the code, Signal downloads vendor specs
            and diffs them, Observe records the traffic a deployment shows it, Detect turns that
            evidence into findings, and Remediate patches and opens the pull request. Each cell
            carries one measured figure and opens the page that answers that stage. The stages count
            four different things, so no cell and no connector is drawn to scale &mdash; a width
            here would assert a proportion between call sites and findings, and that is not a ratio
            that means anything.
          </InfoHint>
        </div>
        <LastIndexPass query={overview} />
      </div>

      <ol className="flex flex-col rounded-surface border border-line bg-surface p-field lg:flex-row lg:items-stretch">
        {pagesByStage().map(({ stage, pages }, position) => {
          const destination = pages[0]
          const href = destinationHref(destination, { repoId })
          if (href === null) return null
          return (
            <Fragment key={stage}>
              {position > 0 && <StageJoin />}
              <li className="flex min-w-0 flex-1">
                <StageCell
                  stage={stage}
                  figure={figures[stage]}
                  destination={destination}
                  href={href}
                />
              </li>
            </Fragment>
          )
        })}
      </ol>

    </section>
  )
}

/**
 * The pipeline's own provenance: when the index last finished here.
 *
 * `null` is never-indexed rather than a pass that found nothing Ã¢â‚¬â€ a pass that completed and wrote
 * no call site is a `completed` row with a count of zero, which the payload keeps apart.
 */
function LastIndexPass({ query }: { query: ReturnType<typeof useOverview> }) {
  if (query.isPending) return <Skeleton width="8rem" />
  if (query.isError) {
    return (
      <span className="text-meta text-ink-muted">
        <Absent>the API did not answer</Absent>
      </span>
    )
  }
  const pass = query.data?.last_index_run ?? null
  if (pass === null || pass.finished_at === null) {
    return (
      <span className="text-meta text-ink-muted">
        <Absent>no index pass has finished here</Absent>
      </span>
    )
  }
  return (
    <span className="text-meta text-ink-muted">
      last index pass <RelativeTime iso={pass.finished_at} />
      {pass.outcome !== null && pass.outcome !== "completed" ? ` Ã¢â‚¬â€ ${pass.outcome}` : ""}
    </span>
  )
}

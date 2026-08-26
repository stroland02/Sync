/**
 * The two maps of the Overview bento's top row, each a pane that fills its grid track.
 *
 * **Owner ruling, 2026-08-19.** The Overview drew one map and it was the wrong one to draw
 * alone: a codebase has two shapes worth seeing — what it *calls*, and how it is *laid out* —
 * and they answer different questions. Neither is a summary of the other, so the Overview shows
 * both and each opens full-screen, where its own analytics live. The equality that ruling asked
 * for is structural now: both panes take `lg:col-span-6` of one grid row, so no viewport can
 * rank them.
 *
 * Each pane issues `useRepositoryGraph` itself and React Query dedupes on
 * `["repositories", repoId, "graph"]`, so two panes cost one request. The empty branches are
 * classified once in `index-state.ts` rather than here, so this screen and `/graph` cannot
 * disagree about whether an index ever ran.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import { useRepositoryGraph } from "@/api/queries"
import type { RepositoryGraphBinding } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RelativeTime } from "@/components/relative-time"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { ForceMap } from "@/features/index-graph/force-map"
import { TreeMapD3 } from "@/features/index-graph/tree-map-d3"
import { classifyIndexState } from "@/features/index-graph/index-state"

interface MapPaneProps {
  repoId: string
  /** The grid track this pane occupies. Placement is the page's decision, never the pane's. */
  span?: string
}

interface GraphPaneProps extends MapPaneProps {
  title: string
  hint: ReactNode
  href: string
  action: string
  /** Named in every state string, so one pane's nothing cannot be read as the other's. */
  what: string
  /** The headline for an index that has never written a call site here. */
  neverRecorded: string
  /** The headline for an index that ran here and drew nothing — a measurement, not an absence. */
  indexedEmpty: string
  draw: (rows: RepositoryGraphBinding[]) => ReactNode
}

function GraphPane({
  repoId,
  span,
  title,
  hint,
  href,
  action,
  what,
  neverRecorded,
  indexedEmpty,
  draw,
}: GraphPaneProps) {
  const query = useRepositoryGraph(repoId)
  const state = query.data === undefined ? null : classifyIndexState(query.data)
  const drawn = state?.kind === "drawn"

  return (
    <PanelPane
      className={span}
      // Only the drawn branch holds a self-measuring canvas; the prose branches are allowed to
      // scroll, because an error sentence clipped by a fixed grid track says nothing at all.
      scroll={!drawn}
      bodyClassName={drawn ? undefined : "p-section"}
      label={title}
      hint={<InfoHint label={`About the ${title.toLowerCase()}`}>{hint}</InfoHint>}
      actions={
        <>
          {drawn && query.data !== undefined && (
            <span className="hidden font-furniture text-ink-secondary lg:inline">
              {query.data.truncated
                ? `${query.data.bindings.length.toLocaleString()} of ${query.data.total_bindings.toLocaleString()} drawn`
                : `${query.data.bindings.length.toLocaleString()} drawn`}
            </span>
          )}
          <Button asChild variant="outline" size="sm">
            <Link to={href}>{action}</Link>
          </Button>
        </>
      }
    >
      {query.isPending && <LoadingState what={what} />}
      {query.isError && (
        <ErrorState error={query.error} what={what} onRetry={() => void query.refetch()} />
      )}
      {state?.kind === "never-recorded" && (
        <EmptyState
          headline={neverRecorded}
          detail="Nothing records an index attempt, only its result — an index that never ran and one that ran and found no vendor call are the same silence here, and neither is a claim that this codebase calls none."
          command={`uv run sync index --repo ${repoId}`}
        />
      )}
      {state?.kind === "indexed-empty" && state.indexedAt !== null && (
        <EmptyState
          headline={indexedEmpty}
          detail={
            <>
              The index wrote here <RelativeTime iso={state.indexedAt} /> and drew no vendor call.
              That is a measurement about the code, not an absence of evidence — a repository the
              index has never reached says something different, and says it in different words.
            </>
          }
        />
      )}
      {drawn && query.data !== undefined && (
        <div className="h-full w-full">{draw(query.data.bindings)}</div>
      )}
    </PanelPane>
  )
}

export function IntegrationMapPane({ repoId, span }: MapPaneProps) {
  return (
    <GraphPane
      repoId={repoId}
      span={span}
      title="Integration map"
      hint="Every file that calls an integration, the operations it reaches, and the integrations behind them — laid out by force, so a codebase clusters around what it depends on. Opens full screen with the API topology figures beside it."
      href={`/repositories/${encodeURIComponent(repoId)}/graph`}
      action="Open integration map"
      what="the integration map"
      neverRecorded="No index pass has ever written a call site here."
      indexedEmpty="The index ran here and drew no vendor call."
      draw={(rows) => <ForceMap rows={rows} fill controls={false} />}
    />
  )
}

export function FileTreePane({ repoId, span }: MapPaneProps) {
  return (
    <GraphPane
      repoId={repoId}
      span={span}
      title="File tree"
      hint="The same call sites arranged the way the codebase is — directory by directory, with the level of detail fitted to the window. Opens full screen with this codebase's technical census beside it."
      href={`/repositories/${encodeURIComponent(repoId)}/file-tree`}
      action="Open file tree"
      what="the file tree"
      neverRecorded="No directory here holds an indexed call site."
      indexedEmpty="The index walked this tree and found no vendor call in it."
      draw={(rows) => <TreeMapD3 rows={rows} fill controls={false} />}
    />
  )
}

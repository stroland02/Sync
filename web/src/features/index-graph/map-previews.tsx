/**
 * The two maps, side by side on the Overview, each a door into its own full-screen view.
 *
 * **Owner ruling, 2026-08-19.** The Overview drew one map and it was the wrong one to draw
 * alone: a codebase has two shapes worth seeing — what it *calls*, and how it is *laid out* —
 * and they answer different questions. Neither is a summary of the other, so the Overview shows
 * both small and each opens full-screen, where its own analytics live.
 *
 * That division is also what un-crowds the Overview: the topology figures follow the
 * integration map to `/graph`, and the technical census follows the file tree to `/file-tree`.
 * Each page becomes a subject rather than the Overview becoming a scroll.
 *
 * **Both panels are the same height and open the same way**, which is the layout ruling applied:
 * two panels of one row at two heights read as a mistake rather than as two answers.
 */

import { Link } from "react-router"

import type { RepositoryGraphBinding } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { Button } from "@/components/ui/button"
import { ForceMap } from "@/features/index-graph/force-map"
import { TreeMapD3 } from "@/features/index-graph/tree-map-d3"

function MapPanel({
  title,
  hint,
  href,
  action,
  children,
}: {
  title: string
  hint: string
  href: string
  action: string
  children: React.ReactNode
}) {
  return (
    <div className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-surface p-section">
      <div className="flex flex-wrap items-center justify-between gap-row">
        <div className="flex items-center gap-row">
          <h3 className="text-section">{title}</h3>
          <InfoHint label={`About the ${title.toLowerCase()}`}>{hint}</InfoHint>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to={href}>{action}</Link>
        </Button>
      </div>
      {/* A fixed preview height on both, so the row is symmetric whatever each map contains. */}
      <div className="h-[22rem] min-w-0">{children}</div>
    </div>
  )
}

export function MapPreviews({
  repoId,
  bindings,
}: {
  repoId: string
  bindings: RepositoryGraphBinding[]
}) {
  const scoped = encodeURIComponent(repoId)
  return (
    <div className="grid auto-rows-fr gap-8 xl:grid-cols-2">
      <MapPanel
        title="Integration map"
        hint="Every file that calls an integration, the operations it reaches, and the integrations behind them — laid out by force, so a codebase clusters around what it depends on. Opens full screen with the API topology figures beside it."
        href={`/repositories/${scoped}/graph`}
        action="Open integration map"
      >
        <ForceMap rows={bindings} fill />
      </MapPanel>

      <MapPanel
        title="File tree"
        hint="The same call sites arranged the way the codebase is — directory by directory, with the level of detail fitted to the window. Opens full screen with this codebase's technical census beside it."
        href={`/repositories/${scoped}/file-tree`}
        action="Open file tree"
      >
        <TreeMapD3 rows={bindings} fill />
      </MapPanel>
    </div>
  )
}

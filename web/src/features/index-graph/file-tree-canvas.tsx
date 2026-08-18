/**
 * The indexing canvas, owner decision 8 (2026-08-18): a repository's own file tree, with an edge
 * from each file to the vendors its call sites bind -- `src/api/billing.ts ──▶ stripe`, framed as
 * the reader's own codebase rather than as Sync's internal model of it. Replaces
 * `dependency-canvas.tsx`, which drew the inverse shape (vendor → operation → call site) that
 * decisions 8 and 13 superseded; that file and `graph-layout.ts`'s rank-column layout are not
 * reused here beyond the pan/zoom/minimap arithmetic in `file-tree-layout.ts`, which is
 * shape-agnostic.
 *
 * **Viewport culling is real, not cosmetic.** `visibleNodes` filters the mounted node set to
 * whatever the current pan/zoom actually shows, recomputed on every interaction -- a repository
 * with ten thousand indexed files never mounts more DOM than the viewport can hold at once. The
 * layout itself is computed once; culling is a filter over it, never a second layout pass.
 *
 * **Scope, and why it changed since this canvas was first written.** `rows` was first drawn from
 * `GET /api/vendors/{id}`'s open findings -- an honest but partial picture, since most call sites
 * carry no open finding. `GET /api/repositories/{repo_id}/graph` (`RepositoryGraphBinding`)
 * landed after and is what this canvas draws now: every indexed call site, whether or not a
 * detector has claimed it, bounded and reporting its own truncation rather than silently drawing
 * a partial graph as if it were complete.
 *
 * A rung is drawn as a word on the edge, never a colour, for the same reason
 * `dependency-canvas.tsx`'s docstring gives: `DESIGN.md` holds the provenance rung monochrome at
 * every level this console has, and a canvas is not the exception.
 */

import { useMemo, useRef, useState } from "react"
import type { PointerEvent as ReactPointerEvent } from "react"

import { BINDING_SOURCES, type RepositoryGraphBinding } from "@/api/types"
import { Button } from "@/components/ui/button"
import { describeRung } from "@/lib/format"
import { cn } from "@/lib/utils"
import { buildFileTreeGraph, type FileVendorRow } from "@/features/index-graph/file-tree-graph"
import {
  fitViewport,
  layoutFileTree,
  panViewport,
  visibleNodes,
  zoomViewport,
  type FileTreeLayoutNode,
  type Viewport,
} from "@/features/index-graph/file-tree-layout"

export const CANVAS_LABEL = "Your codebase, and what it calls"
export const MINIMAP_LABEL = "The whole tree, with the current view marked"

export const SCOPE_NOTE =
  "This tree draws every call site the index currently holds for this repository, whether or not a detector has claimed it."

export const EMPTY_GRAPH_NOTE =
  "Nothing was passed to this canvas. That is a statement about what this view was given, not about what the index holds."

const CANVAS_HEIGHT = "h-[36rem]"

function rowToFileVendorRow(row: RepositoryGraphBinding): FileVendorRow {
  return { file: row.path, vendor: row.vendor_id, binding_source: row.binding_rung }
}

function NodeLabel({ node }: { node: FileTreeLayoutNode }) {
  if (node.kind === "vendor") {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-surface border border-line bg-surface px-field text-emphasis">
        <span className="min-w-0 truncate">{node.vendorId}</span>
      </div>
    )
  }
  return (
    <div
      className={cn(
        "flex h-full w-full items-center gap-field truncate px-field",
        node.kind === "folder" ? "furniture text-meta text-ink-muted" : "font-mono text-body"
      )}
    >
      {node.kind === "folder" ? "▸" : "•"}
      <span className="min-w-0 truncate">{node.name}</span>
    </div>
  )
}

function TreeEdge({ from, to, label }: { from: FileTreeLayoutNode; to: FileTreeLayoutNode; label: string }) {
  const x1 = from.x + from.width
  const y1 = from.y + from.height / 2
  const x2 = to.x
  const y2 = to.y + to.height / 2
  const bend = (x2 - x1) / 2
  return (
    <g>
      <path
        d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`}
        fill="none"
        strokeWidth={1.5}
        className="stroke-line-strong"
      />
      <text
        x={(x1 + x2) / 2}
        y={(y1 + y2) / 2 - 6}
        textAnchor="middle"
        paintOrder="stroke"
        strokeWidth={5}
        className="furniture fill-ink-muted stroke-background text-meta"
      >
        {label}
      </text>
    </g>
  )
}

function Minimap({ nodes, frame, view }: { nodes: FileTreeLayoutNode[]; frame: Viewport; view: Viewport }) {
  return (
    <svg
      aria-label={MINIMAP_LABEL}
      role="img"
      viewBox={`${frame.x} ${frame.y} ${frame.width} ${frame.height}`}
      preserveAspectRatio="xMidYMid meet"
      className="h-24 w-40 rounded-surface border border-line bg-background"
    >
      {nodes.map((node) => (
        <rect key={node.id} data-node={node.id} x={node.x} y={node.y} width={node.width} height={node.height} className="fill-line-strong" />
      ))}
      <rect data-view="current" x={view.x} y={view.y} width={view.width} height={view.height} fill="none" strokeWidth={8} className="stroke-ring" />
    </svg>
  )
}

export function FileTreeCanvas({
  rows,
  knownVendorIds,
  className,
}: {
  rows: RepositoryGraphBinding[]
  /** Every vendor the caller already knows exists, so a truncated response cannot silently drop one -- see `buildFileTreeGraph`'s own docstring. */
  knownVendorIds?: string[]
  className?: string
}) {
  const graph = useMemo(
    () => buildFileTreeGraph(rows.map(rowToFileVendorRow), knownVendorIds),
    [rows, knownVendorIds]
  )
  const layout = useMemo(() => layoutFileTree(graph), [graph])
  const fit = useMemo(() => fitViewport(layout.bounds), [layout.bounds])
  const [panned, setPanned] = useState<Viewport | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)

  const view = panned ?? fit
  const byId = useMemo(() => new Map(layout.nodes.map((n) => [n.id, n] as const)), [layout.nodes])
  const shown = useMemo(() => visibleNodes(layout.nodes, view), [layout.nodes, view])
  const shownIds = useMemo(() => new Set(shown.map((n) => n.id)), [shown])
  // An edge draws once either endpoint is on screen, the same "half in view still matters" rule
  // `visibleNodes` applies to a single node -- a long edge crossing the whole viewport must not
  // vanish just because its midpoint sits off-frame.
  const shownEdges = useMemo(
    () => layout.edges.filter((edge) => shownIds.has(edge.from) || shownIds.has(edge.to)),
    [layout.edges, shownIds]
  )

  function onPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY }
  }

  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const start = drag.current
    if (start === null) return
    const box = event.currentTarget.getBoundingClientRect()
    if (box.width === 0 || box.height === 0) return
    const dx = ((start.x - event.clientX) * view.width) / box.width
    const dy = ((start.y - event.clientY) * view.height) / box.height
    drag.current = { x: event.clientX, y: event.clientY }
    setPanned(panViewport(view, dx, dy, fit))
  }

  function endDrag() {
    drag.current = null
  }

  const rungsByEdgeId = useMemo(() => new Map(graph.edges.map((e) => [`edge:${e.file}->${e.vendorId}`, e.rungs])), [graph.edges])

  return (
    <section className={cn("flex min-w-0 flex-col gap-section", className)}>
      <div className="flex flex-wrap items-center justify-between gap-section">
        <div className="flex flex-wrap items-center gap-field">
          <Button variant="outline" size="sm" onClick={() => setPanned(zoomViewport(view, 2, fit))}>
            Zoom in
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPanned(zoomViewport(view, 0.5, fit))}>
            Zoom out
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPanned(null)}>
            Fit tree
          </Button>
        </div>
        <p className="max-w-prose text-meta text-ink-muted">{SCOPE_NOTE}</p>
      </div>

      <div className="relative min-w-0 overflow-hidden rounded-surface border border-line bg-background">
        <svg
          aria-label={CANVAS_LABEL}
          role="group"
          viewBox={`${view.x} ${view.y} ${view.width} ${view.height}`}
          preserveAspectRatio="xMidYMid meet"
          className={cn("block w-full cursor-grab touch-none select-none", CANVAS_HEIGHT)}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerLeave={endDrag}
        >
          <g>
            {shownEdges.map((edge) => {
              const from = byId.get(edge.from)
              const to = byId.get(edge.to)
              const rungs = rungsByEdgeId.get(edge.id) ?? []
              return from === undefined || to === undefined ? null : (
                <TreeEdge key={edge.id} from={from} to={to} label={rungs.join(" + ")} />
              )
            })}
          </g>
          <g>
            {shown.map((node) => (
              <foreignObject key={node.id} x={node.x} y={node.y} width={node.width} height={node.height}>
                <NodeLabel node={node} />
              </foreignObject>
            ))}
          </g>
        </svg>

        {layout.nodes.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center p-section text-center text-body text-ink-muted">{EMPTY_GRAPH_NOTE}</p>
        )}

        <div className="absolute right-0 bottom-0 p-section">
          <Minimap nodes={layout.nodes} frame={fit} view={view} />
        </div>
      </div>

      <ul aria-label="Provenance rungs" className="flex flex-wrap gap-section">
        {BINDING_SOURCES.map((rung) => (
          <li key={rung} className="flex min-w-0 flex-col gap-field">
            <span className="furniture rounded-control border border-line px-field text-meta">{rung}</span>
            <span className="text-meta text-ink-muted">{describeRung(rung)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

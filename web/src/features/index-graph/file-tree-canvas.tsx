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
import { buildFileTree, foldersAtDepth, visiblePath } from "@/features/index-graph/file-tree-graph"
import { buildOperationGraph, type CallBindingRow } from "@/features/index-graph/operation-graph"
import {
  fitViewport,
  readableViewport,
  layoutOperationGraph,
  ROW_HEIGHT,
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
/** The same 36rem, in the pixels the legibility arithmetic is done in. */
const CANVAS_HEIGHT_PX = 576
/** Past this many call sites the tree opens folded; below it, folding helps nobody. */
const AGGREGATE_ABOVE = 40
/** How deep the default fold reaches: the top level stays open, everything under it folds. */
const DEFAULT_FOLD_DEPTH = 1

function rowToBinding(row: RepositoryGraphBinding): CallBindingRow {
  return {
    file: row.path,
    vendorId: row.vendor_id,
    operationId: row.operation_id,
    rung: row.binding_rung,
  }
}

function NodeLabel({
  node,
  foldedCount,
}: {
  node: FileTreeLayoutNode
  /** How many call sites this folder stands for while folded, or undefined when open. */
  foldedCount?: number
}) {
  if (node.kind === "operation") {
    // The operation carries the vendor's name as well as its own: two vendors may both publish
    // `Charge`, and a node showing only the id would read as one operation in two places.
    return (
      <div className="flex h-full w-full flex-col justify-center rounded-control border border-line bg-surface-muted px-field">
        <span className="min-w-0 truncate font-mono text-meta text-ink">{node.operationId}</span>
        <span className="min-w-0 truncate text-meta text-ink-muted">{node.vendorId}</span>
      </div>
    )
  }
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
      {/* The glyph says which way the fold goes, so a folded folder is legible as folded
          rather than as an empty directory. */}
      {node.kind === "folder" ? (foldedCount === undefined ? "▾" : "▸") : "•"}
      <span className="min-w-0 truncate">{node.name}</span>
      {foldedCount !== undefined && (
        <span className="shrink-0 tabular-nums text-ink-muted">
          {foldedCount} {foldedCount === 1 ? "call site" : "call sites"}
        </span>
      )}
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
  /** Every vendor the caller already knows exists, so a truncated response cannot silently drop one -- see `buildOperationGraph`'s own docstring. */
  knownVendorIds?: string[]
  className?: string
}) {
  const bindings = useMemo(() => rows.map(rowToBinding), [rows])

  // The full tree, computed once: what a reader could expand into, and the source of the
  // default fold below.
  const fullTree = useMemo(() => buildFileTree(bindings.map((b) => b.file)), [bindings])
  // A large tree opens folded past its first level -- the aggregation every large-graph tool
  // does. Small trees open whole, because folding three folders helps nobody.
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() =>
    bindings.length > AGGREGATE_ABOVE
      ? new Set(foldersAtDepth(buildFileTree(bindings.map((b) => b.file)), DEFAULT_FOLD_DEPTH))
      : new Set()
  )

  // How many call sites each collapsed folder now stands for, so a folded node says what it
  // is hiding rather than looking like an empty directory.
  const foldedCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const binding of bindings) {
      const at = visiblePath(binding.file, collapsed)
      if (at !== binding.file) counts.set(at, (counts.get(at) ?? 0) + 1)
    }
    return counts
  }, [bindings, collapsed])

  // Bindings re-attached to the nearest visible ancestor: collapsing changes the picture's
  // resolution, never its claims.
  const visibleBindings = useMemo(
    () => bindings.map((b) => ({ ...b, file: visiblePath(b.file, collapsed) })),
    [bindings, collapsed]
  )
  const tree = useMemo(
    () => buildFileTree(visibleBindings.map((b) => b.file)),
    [visibleBindings]
  )
  const graph = useMemo(
    () => buildOperationGraph(visibleBindings, knownVendorIds),
    [visibleBindings, knownVendorIds]
  )
  const layout = useMemo(() => layoutOperationGraph(tree, graph), [tree, graph])
  const fit = useMemo(() => fitViewport(layout.bounds), [layout.bounds])
  // Where the canvas opens. On a small graph this *is* the fit; on a large one it is the
  // top-left at the scale where a row still reads, because fitting a codebase with hundreds of
  // call sites into 576px renders every row at about three pixels -- a texture, not a graph.
  const readable = useMemo(
    () => readableViewport(fit, { rowHeight: ROW_HEIGHT, canvasHeightPx: CANVAS_HEIGHT_PX }),
    [fit]
  )
  const [panned, setPanned] = useState<Viewport | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)

  const view = panned ?? readable
  // Whether the opening view is showing less than the whole tree, which decides whether the
  // "Fit tree" control has anything to do and whether the notice below has anything to say.
  const clipped = readable.height < fit.height
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

  // Both hops, keyed by the ids `layoutOperationGraph` builds. Every edge on this canvas has a
  // rung, which is what the operation level bought: a file drawn straight to a vendor spanned two
  // bindings and a rung on that hop named neither of them.
  const rungsByEdgeId = useMemo(
    () =>
      new Map<string, typeof graph.fileEdges[number]["rungs"]>([
        ...graph.fileEdges.map(
          (e) => [`edge:${e.file}->${e.vendorId}:${e.operationId}`, e.rungs] as const
        ),
        ...graph.vendorEdges.map(
          (e) => [`edge:${e.vendorId}:${e.operationId}->${e.vendorId}`, e.rungs] as const
        ),
      ]),
    [graph.fileEdges, graph.vendorEdges]
  )

  const foldable = useMemo(() => foldersAtDepth(fullTree, DEFAULT_FOLD_DEPTH), [fullTree])
  const zoom = { rowHeight: ROW_HEIGHT, canvasHeightPx: CANVAS_HEIGHT_PX }

  return (
    <section className={cn("flex min-w-0 flex-col gap-section", className)}>
      {/* Every control lives inside the card, floating over the picture — the owner's
          instruction, and the convention every node canvas follows: a toolbar above the frame
          reads as page furniture rather than as part of the map. */}
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
            {shown.map((node) => {
              const path = node.kind === "folder" || node.kind === "file" ? node.path : null
              const folded = path !== null && collapsed.has(path)
              const foldable_here = node.kind === "folder"
              return (
                <foreignObject
                  key={node.id}
                  x={node.x}
                  y={node.y}
                  width={node.width}
                  height={node.height}
                  // A folder opens or closes on click — expand-on-demand, the rule every large
                  // graph tool follows. Stops the pointer from starting a pan so a click that
                  // means "open this" is never read as a drag.
                  onPointerDown={
                    foldable_here
                      ? (event) => {
                          event.stopPropagation()
                        }
                      : undefined
                  }
                  onClick={
                    foldable_here && path !== null
                      ? () =>
                          setCollapsed((current) => {
                            const next = new Set(current)
                            if (next.has(path)) next.delete(path)
                            else next.add(path)
                            return next
                          })
                      : undefined
                  }
                  className={foldable_here ? "cursor-pointer" : undefined}
                >
                  <NodeLabel node={node} foldedCount={folded ? foldedCounts.get(path) : undefined} />
                </foreignObject>
              )
            })}
          </g>
        </svg>

        {layout.nodes.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center p-section text-center text-body text-ink-muted">{EMPTY_GRAPH_NOTE}</p>
        )}

        {/* Top-left: the view controls, over the canvas. */}
        <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-start justify-between gap-row p-row">
          <div className="pointer-events-auto flex flex-wrap items-center gap-field rounded-surface border border-line bg-surface/90 p-field backdrop-blur">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPanned(zoomViewport(view, 1.6, fit, zoom))}
            >
              Zoom in
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPanned(zoomViewport(view, 0.625, fit, zoom))}
            >
              Zoom out
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPanned(readable)}>
              Readable
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPanned(fit)}>
              Fit all
            </Button>
          </div>

          {/* Top-right: the aggregation controls, because folding is what makes a large tree
              readable at all and it belongs beside the zoom rather than under the picture. */}
          {foldable.length > 0 && (
            <div className="pointer-events-auto flex flex-wrap items-center gap-field rounded-surface border border-line bg-surface/90 p-field backdrop-blur">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCollapsed(new Set(foldable))}
                disabled={collapsed.size === foldable.length}
              >
                Fold folders
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCollapsed(new Set())}
                disabled={collapsed.size === 0}
              >
                Expand all
              </Button>
            </div>
          )}
        </div>

        <div className="pointer-events-none absolute right-0 bottom-0 p-row">
          <Minimap nodes={layout.nodes} frame={fit} view={view} />
        </div>
      </div>

      <p className="max-w-prose text-meta text-ink-muted">
        {SCOPE_NOTE}
        {collapsed.size > 0 && (
          <>
            {" "}
            {collapsed.size} {collapsed.size === 1 ? "folder is" : "folders are"} folded, each
            standing for the call sites inside it — click one to open it. Nothing is hidden by
            folding: a folded folder carries its subtree&rsquo;s edges.
          </>
        )}
        {clipped && collapsed.size === 0 && (
          <>
            {" "}
            This tree is larger than one screen can render legibly, so it opens at the top at a
            scale where a row still reads — pan, or use the minimap, to reach the rest.
          </>
        )}
      </p>

      {graph.unroutable.length > 0 && (
        <p className="text-meta text-ink-muted leading-relaxed">
          <span className="furniture rounded-control border border-line px-field text-meta">
            not drawn
          </span>{" "}
          {graph.unroutable.length}{" "}
          {graph.unroutable.length === 1 ? "binding names" : "bindings name"} no operation, so
          there is no node to route {graph.unroutable.length === 1 ? "it" : "them"} through.{" "}
          {graph.unroutable.map((b) => b.file).join(", ")} — held by the graph and left off the
          picture rather than given an invented node.
        </p>
      )}

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

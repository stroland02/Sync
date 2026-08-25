/**
 * The codebase map: a force-directed graph of files, the operations they call, and the
 * integrations behind them. Owner ruling, 2026-08-18 — d3-force is the map's layout.
 *
 * ## Why force here and ECharts everywhere else
 *
 * The console's nine dashboards are ECharts and stay ECharts: a stacked bar chart in raw d3 is
 * hand-written axes, legends, tooltips and responsive behaviour that a chart library already
 * gives, and two charting stacks is one fact written twice. **What d3 is uniquely right for is
 * this**: a bespoke layout nothing off the shelf draws, over a graph whose shape changes with
 * every codebase. `d3-force` computes the positions, `d3-zoom` owns pan and zoom, `d3-drag`
 * lets a reader pull a node aside — three modules, not the whole library.
 *
 * ## The simulation is settled, not performed
 *
 * A force graph that animates on arrival is motion the operator did not ask for, and
 * `DESIGN.md` gates motion on *frequency* — a canvas crossed repeatedly takes none. So the
 * simulation is **ticked to completion before the first paint**: `simulation.stop()` then
 * `tick(n)` in a loop, which d3 supports precisely for this. The reader meets a settled map,
 * every time, with no flying nodes and nothing to wait for. It is also deterministic, which a
 * live simulation is not: the same codebase draws the same map twice, so a reader can compare
 * two visits rather than two random layouts.
 *
 * Under `prefers-reduced-motion` nothing changes, because there was never an animation to skip.
 *
 * ## What the marks are allowed to say
 *
 * **Radius carries a count** — how many call sites a file holds, how many reach an operation.
 * That is a measurement.
 *
 * **Colour carries integration identity and nothing else** (`lib/palette.ts`). Which vendor a
 * mark belongs to is a closed vocabulary, every coloured mark also carries its label, and the
 * assignment is the series scale every chart uses — so a vendor is the same colour here and on
 * every dashboard. What colour still may not carry: a rung, a severity, a health. The rung is
 * a word on the selected node's detail, because `DESIGN.md` holds provenance monochrome at
 * every level and a map is not the exception; a file belongs to no vendor and stays ink.
 */

import { useEffect, useMemo, useRef, useState } from "react"
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force"
import { select } from "d3-selection"
import { zoom as d3zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from "d3-zoom"

import type { RepositoryGraphBinding } from "@/api/types"
import { Button } from "@/components/ui/button"
import { seriesScale } from "@/lib/palette"
import { cn } from "@/lib/utils"

export const FORCE_MAP_LABEL = "Codebase map: files, the operations they call, and their integrations"

/** How many ticks the simulation is run before the first paint. d3's own settled default. */
const SETTLE_TICKS = 300
const WIDTH = 1200
const HEIGHT = 700

export type ForceNodeKind = "file" | "operation" | "vendor"

export interface ForceNode extends SimulationNodeDatum {
  id: string
  kind: ForceNodeKind
  label: string
  /** What the radius stands for: call sites at a file, call sites reaching an operation. */
  weight: number
  /** Only on operation and vendor nodes. */
  vendorId?: string
  /** The rungs the edges into this node carry, as words. */
  rungs?: string[]
}

interface ForceLink extends SimulationLinkDatum<ForceNode> {
  id: string
  rung: string
}

/**
 * The graph the map draws, derived from the same bindings every other view reads.
 *
 * Exported and pure because it is a derivation with a wrong answer — a node whose weight does
 * not equal the rows behind it is a mark that lies about a measurement.
 */
export function buildForceGraph(rows: RepositoryGraphBinding[]): {
  nodes: ForceNode[]
  links: ForceLink[]
} {
  const nodes = new Map<string, ForceNode>()
  const links = new Map<string, ForceLink>()

  const ensure = (id: string, node: () => ForceNode): ForceNode => {
    const existing = nodes.get(id)
    if (existing !== undefined) return existing
    const created = node()
    nodes.set(id, created)
    return created
  }

  for (const row of rows) {
    const fileId = `file:${row.path}`
    const operationId = `op:${row.vendor_id}:${row.operation_id}`
    const vendorId = `vendor:${row.vendor_id}`

    const file = ensure(fileId, () => ({
      id: fileId,
      kind: "file",
      // The basename reads at map scale; the full path is the node's title.
      label: row.path.split("/").pop() ?? row.path,
      weight: 0,
    }))
    file.weight += 1

    const operation = ensure(operationId, () => ({
      id: operationId,
      kind: "operation",
      label: row.operation_id,
      vendorId: row.vendor_id,
      weight: 0,
      rungs: [],
    }))
    operation.weight += 1
    if (operation.rungs !== undefined && !operation.rungs.includes(row.binding_rung)) {
      operation.rungs.push(row.binding_rung)
    }

    const vendor = ensure(vendorId, () => ({
      id: vendorId,
      kind: "vendor",
      label: row.vendor_id,
      vendorId: row.vendor_id,
      weight: 0,
    }))
    vendor.weight += 1

    const fileEdge = `${fileId}->${operationId}`
    if (!links.has(fileEdge)) {
      links.set(fileEdge, { id: fileEdge, source: fileId, target: operationId, rung: row.binding_rung })
    }
    const vendorEdge = `${operationId}->${vendorId}`
    if (!links.has(vendorEdge)) {
      links.set(vendorEdge, {
        id: vendorEdge,
        source: operationId,
        target: vendorId,
        rung: row.binding_rung,
      })
    }
  }

  return { nodes: [...nodes.values()], links: [...links.values()] }
}

/** The radius a weight draws at: area proportional to the count, floored so a 1 is still a mark. */
export function radiusFor(node: ForceNode): number {
  const base = node.kind === "vendor" ? 14 : node.kind === "operation" ? 8 : 5
  return base + Math.sqrt(node.weight) * (node.kind === "file" ? 1.6 : 2.4)
}

export function ForceMap({
  rows,
  className,
  fill = false,
  controls = true,
}: {
  rows: RepositoryGraphBinding[]
  className?: string
  /** Fill the height its container gives, rather than the card's own 44rem. */
  fill?: boolean
  /** Owner ruling 2026-08-25: zoom and fit belong to the graph page. The Overview's preview is
      a picture you click through, and the buttons over it were chrome for an interaction
      nobody performs there. Node selection stays -- it is the picture, not chrome. */
  controls?: boolean
}) {
  const { nodes, links } = useMemo(() => buildForceGraph(rows), [rows])
  // One scale over the vendors present, so a vendor wears the same colour here as in every
  // chart, and the same colour on the next visit — the scale sorts its domain for exactly that.
  const vendorInk = useMemo(
    () => seriesScale(nodes.filter((n) => n.vendorId !== undefined).map((n) => n.vendorId!)),
    [nodes]
  )
  const [settled, setSettled] = useState<{ nodes: ForceNode[]; links: ForceLink[] } | null>(null)
  const [selected, setSelected] = useState<ForceNode | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const svgRef = useRef<SVGSVGElement>(null)
  // The behaviour itself, so a control reuses the one bound to the element rather than
  // building a second that d3 does not consider current.
  const behaviourRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)

  // The layout, computed once per graph and settled before it is shown. `stop()` before the
  // loop is what makes this deterministic rather than a race with the animation frame.
  useEffect(() => {
    if (nodes.length === 0) {
      setSettled({ nodes: [], links: [] })
      return
    }
    // The simulation mutates its inputs, so it gets copies -- otherwise a re-render with the
    // same bindings would re-settle nodes that already carry positions.
    const simNodes: ForceNode[] = nodes.map((node) => ({ ...node }))
    const simLinks: ForceLink[] = links.map((link) => ({ ...link }))

    const simulation: Simulation<ForceNode, ForceLink> = forceSimulation(simNodes)
      .force(
        "link",
        forceLink<ForceNode, ForceLink>(simLinks)
          .id((node) => node.id)
          // Vendors sit further from their operations than files do, so the three tiers read
          // as tiers rather than as one cloud.
          .distance((link) => ((link.target as ForceNode).kind === "vendor" ? 120 : 70))
          .strength(0.6)
      )
      .force("charge", forceManyBody<ForceNode>().strength((node) => (node.kind === "vendor" ? -900 : -140)))
      .force("collide", forceCollide<ForceNode>().radius((node) => radiusFor(node) + 6))
      .force("centre", forceCenter(WIDTH / 2, HEIGHT / 2))
      // A gentle left-to-right bias: files, then what they call, then who publishes it. The
      // reading order of every other screen, applied to a layout that has no axis of its own.
      .force(
        "tier",
        forceX<ForceNode>((node) =>
          node.kind === "file" ? WIDTH * 0.2 : node.kind === "operation" ? WIDTH * 0.55 : WIDTH * 0.85
        ).strength(0.32)
      )
      .force("vertical", forceY<ForceNode>(HEIGHT / 2).strength(0.05))
      .stop()

    for (let tick = 0; tick < SETTLE_TICKS; tick += 1) simulation.tick()
    simulation.stop()
    setSettled({ nodes: simNodes, links: simLinks })
  }, [nodes, links])

  /**
   * The transform that frames the settled graph.
   *
   * The simulation has no bounds of its own — forces push nodes wherever they balance, which
   * is regularly outside the viewBox — so a fixed viewBox drew a map with its edges cropped and
   * no way to reach them. This measures what settled and frames it, which is the fit the reader
   * should open at.
   */
  const fitTransform = useMemo(() => {
    if (settled === null || settled.nodes.length === 0) return zoomIdentity
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    for (const node of settled.nodes) {
      const radius = radiusFor(node)
      minX = Math.min(minX, (node.x ?? 0) - radius)
      minY = Math.min(minY, (node.y ?? 0) - radius)
      maxX = Math.max(maxX, (node.x ?? 0) + radius)
      maxY = Math.max(maxY, (node.y ?? 0) + radius)
    }
    // Room for the labels that hang off a node's right edge, which the radius does not cover.
    const pad = 90
    const width = maxX - minX + pad * 2
    const height = maxY - minY + pad * 2
    const scale = Math.min(WIDTH / width, HEIGHT / height, 1.6)
    return zoomIdentity
      .translate(
        (WIDTH - (maxX + minX) * scale) / 2,
        (HEIGHT - (maxY + minY) * scale) / 2
      )
      .scale(scale)
  }, [settled])

  // Pan and zoom, owned by d3 rather than by hand-rolled pointer arithmetic: wheel, drag,
  // pinch and double-click all arrive already correct, and the transform is the one piece of
  // state React needs to know about.
  //
  // **Keyed on `settled`, and that is the whole of a bug worth naming.** This effect ran once
  // on mount, when the component was still rendering the settling placeholder rather than the
  // svg — so `svgRef.current` was null, the behaviour bound to nothing, and the map could not
  // be zoomed at all. An effect that reaches for a ref must run when that ref is filled.
  useEffect(() => {
    const element = svgRef.current
    if (element === null || settled === null) return
    const behaviour = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 12])
      .on("zoom", (event) => setTransform(event.transform))
    behaviourRef.current = behaviour
    const selection = select(element)
    selection.call(behaviour)
    // The opening frame is applied through the behaviour rather than to state alone, so d3's
    // own notion of the current transform matches the one on screen — set only in state, the
    // first wheel tick would jump back to identity.
    selection.call(behaviour.transform, fitTransform)
    return () => {
      selection.on(".zoom", null)
      behaviourRef.current = null
    }
  }, [settled, fitTransform])

  function resetView() {
    const element = svgRef.current
    const behaviour = behaviourRef.current
    if (element === null || behaviour === null) return
    select(element).call(behaviour.transform, fitTransform)
  }

  /** The buttons drive d3's own `scaleBy`, so wheel and button share one transform. */
  function scaleBy(factor: number) {
    const element = svgRef.current
    const behaviour = behaviourRef.current
    if (element === null || behaviour === null) return
    select(element).call(behaviour.scaleBy, factor)
  }

  if (settled === null) {
    return (
      <div className={cn("flex items-center justify-center rounded-surface border border-line bg-background", fill ? "h-full" : "h-[44rem]", className)}>
        <p className="text-meta text-ink-muted">Settling the map…</p>
      </div>
    )
  }

  if (settled.nodes.length === 0) {
    return (
      <div className={cn("flex items-center justify-center rounded-surface border border-line bg-background p-section", fill ? "h-full" : "h-[44rem]", className)}>
        <p className="max-w-prose text-center text-body text-ink-muted">
          Nothing was passed to this map. That is a statement about what this view was given,
          not about what the index holds.
        </p>
      </div>
    )
  }

  const byId = new Map(settled.nodes.map((node) => [node.id, node] as const))

  return (
    <div className={cn("relative overflow-hidden rounded-surface border border-line bg-background", fill && "h-full", className)}>
      <svg
        ref={svgRef}
        role="group"
        aria-label={FORCE_MAP_LABEL}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        className={cn("block w-full cursor-grab touch-none select-none", fill ? "h-full" : "h-[44rem]")}
      >
        <g transform={transform.toString()}>
          <g>
            {settled.links.map((link) => {
              const source = typeof link.source === "object" ? (link.source as ForceNode) : byId.get(String(link.source))
              const target = typeof link.target === "object" ? (link.target as ForceNode) : byId.get(String(link.target))
              if (source?.x === undefined || target?.x === undefined) return null
              const active =
                selected !== null && (source.id === selected.id || target.id === selected.id)
              return (
                <line
                  key={link.id}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  strokeWidth={active ? 2 : 1}
                  className={active ? "stroke-ring" : "stroke-line"}
                />
              )
            })}
          </g>
          <g>
            {settled.nodes.map((node) => {
              const radius = radiusFor(node)
              const isSelected = selected?.id === node.id
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x ?? 0} ${node.y ?? 0})`}
                  onClick={() => setSelected(isSelected ? null : node)}
                  className="cursor-pointer"
                >
                  {/* Kind is carried by shape, never by hue: a vendor is a square, an
                      operation a ring, a file a disc. DESIGN.md holds this palette
                      monochrome and a map is not the exception. */}
                  {node.kind === "vendor" ? (
                    <rect
                      x={-radius}
                      y={-radius}
                      width={radius * 2}
                      height={radius * 2}
                      rx={3}
                      fill={vendorInk(node.vendorId ?? "")}
                      stroke={isSelected ? "currentColor" : undefined}
                      strokeWidth={isSelected ? 2 : 0}
                      className="text-foreground"
                    />
                  ) : node.kind === "operation" ? (
                    <circle
                      r={radius}
                      fill="var(--color-background)"
                      stroke={vendorInk(node.vendorId ?? "")}
                      strokeWidth={isSelected ? 3.5 : 2}
                    />
                  ) : (
                    // A file belongs to no single integration -- it may call several -- so it
                    // stays ink rather than borrowing one vendor's identity.
                    <circle
                      r={radius}
                      className={isSelected ? "fill-foreground" : "fill-line-strong"}
                    />
                  )}
                  <title>
                    {node.label} — {node.weight} call {node.weight === 1 ? "site" : "sites"}
                  </title>
                  {/* Labels only where they can be read: every vendor, and anything the reader
                      selected or that carries real weight. A label on all 165 files is a wall
                      of overlapping text, which is the failure the fold solved on the tree. */}
                  {(node.kind === "vendor" || isSelected || node.weight >= 4) && (
                    <text
                      x={radius + 4}
                      y={4}
                      className={cn(
                        "pointer-events-none text-meta",
                        node.kind === "vendor" ? "fill-ink" : "fill-ink-muted"
                      )}
                      paintOrder="stroke"
                      strokeWidth={4}
                      stroke="var(--color-background)"
                    >
                      {node.label}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-start justify-between gap-row p-row">
        {controls && (
        <div className="pointer-events-auto flex flex-wrap items-center gap-field rounded-surface border border-line bg-surface/90 p-field backdrop-blur">
          <Button variant="outline" size="sm" onClick={() => scaleBy(1.5)}>
            Zoom in
          </Button>
          <Button variant="outline" size="sm" onClick={() => scaleBy(1 / 1.5)}>
            Zoom out
          </Button>
          <Button variant="outline" size="sm" onClick={resetView}>
            Fit
          </Button>
          <span className="px-field text-meta text-ink-muted tabular-nums">
            {settled.nodes.length} nodes · {Math.round(transform.k * 100)}% · scroll to zoom,
            drag to pan
          </span>
        </div>
        )}

        {selected !== null && (
          <div className="pointer-events-auto flex max-w-sm flex-col gap-field rounded-surface border border-line bg-surface/95 p-section backdrop-blur">
            <span className="furniture text-meta text-ink-muted">{selected.kind}</span>
            <span className="min-w-0 break-all font-mono text-body text-ink">{selected.label}</span>
            <span className="text-meta text-ink-muted">
              {selected.weight} call {selected.weight === 1 ? "site" : "sites"}
              {selected.vendorId !== undefined && ` · ${selected.vendorId}`}
            </span>
            {selected.rungs !== undefined && selected.rungs.length > 0 && (
              <span className="text-meta text-ink-muted">
                rung{selected.rungs.length === 1 ? "" : "s"}: {selected.rungs.join(", ")}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

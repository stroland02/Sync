/**
 * The file tree, laid out by d3 — the second half of the owner's ruling that both codebase
 * views are d3-drawn.
 *
 * `d3-hierarchy`'s `tree()` is the Reingold–Tilford tidy layout: the algorithm that guarantees
 * no two nodes overlap, that a parent sits centred over its children, and that the whole thing
 * is as narrow as those constraints allow. The hand-rolled layout it replaces stacked rows at a
 * fixed indent, which is legible for twenty files and a column of noise for a thousand.
 * `d3-zoom` owns pan and zoom, so this view and the force map interact identically.
 *
 * **The tree is separation-based rather than fixed-height.** `nodeSize` gives every node the
 * same slot and lets the layout grow, which is what makes a deep repository readable at all —
 * a `size`-based layout squeezes a thousand rows into a fixed box and hands back sub-pixel
 * spacing, which is the defect the owner reported on the previous canvas.
 *
 * **Folding is the same idea as the map's aggregation and shares its rule**: a folded directory
 * carries its subtree's call sites, so folding changes the picture's resolution and never its
 * claims. It is the reader's control, and a large tree opens folded because the alternative is
 * a wall.
 *
 * Colour carries integration identity only (`lib/palette.ts`), the same scale the map and the
 * charts use, so stripe is one colour everywhere. A directory belongs to no single integration
 * and stays ink.
 */

import { useEffect, useMemo, useRef, useState } from "react"
import { hierarchy, tree as d3tree, type HierarchyPointNode } from "d3-hierarchy"
import { select } from "d3-selection"
import { zoom as d3zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from "d3-zoom"

import type { RepositoryGraphBinding } from "@/api/types"
import { Button } from "@/components/ui/button"
import { seriesScale } from "@/lib/palette"
import { cn } from "@/lib/utils"

export const TREE_LABEL = "File tree: every directory and file that calls an integration"

const WIDTH = 1200
const HEIGHT = 700
/** Vertical slot per node, and horizontal distance per depth. */
const NODE_STEP: [number, number] = [26, 260]
/** Past this many files the tree opens folded below the top level. */
const FOLD_ABOVE = 40

interface TreeDatum {
  id: string
  name: string
  path: string
  kind: "dir" | "file"
  /** Call sites at or under this node. */
  weight: number
  /** The integrations reached from at or under this node. */
  vendors: string[]
  children?: TreeDatum[]
}

/**
 * The directory tree behind the bindings, with counts rolled up.
 *
 * Pure and exported: a node whose weight does not equal the rows beneath it is a mark that
 * lies about a measurement, which is the one wrong answer this derivation has.
 */
export function buildTreeData(rows: RepositoryGraphBinding[]): TreeDatum {
  const root: TreeDatum = { id: "", name: "/", path: "", kind: "dir", weight: 0, vendors: [], children: [] }

  for (const row of rows) {
    const segments = row.path.split("/").filter(Boolean)
    let cursor = root
    cursor.weight += 1
    if (!cursor.vendors.includes(row.vendor_id)) cursor.vendors.push(row.vendor_id)

    segments.forEach((segment, index) => {
      const isLeaf = index === segments.length - 1
      const path = segments.slice(0, index + 1).join("/")
      cursor.children ??= []
      let next = cursor.children.find((child) => child.name === segment)
      if (next === undefined) {
        next = {
          id: path,
          name: segment,
          path,
          kind: isLeaf ? "file" : "dir",
          weight: 0,
          vendors: [],
          children: isLeaf ? undefined : [],
        }
        cursor.children.push(next)
      }
      next.weight += 1
      if (!next.vendors.includes(row.vendor_id)) next.vendors.push(row.vendor_id)
      cursor = next
    })
  }

  const sort = (node: TreeDatum) => {
    node.children?.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "dir" ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    node.children?.forEach(sort)
  }
  sort(root)
  return root
}

/** The tree with folded directories pruned to leaves, so the layout draws what is open. */
function prune(node: TreeDatum, folded: ReadonlySet<string>): TreeDatum {
  if (node.kind === "file" || node.children === undefined) return node
  if (folded.has(node.path) && node.path !== "") return { ...node, children: undefined }
  return { ...node, children: node.children.map((child) => prune(child, folded)) }
}

/** Every directory one level under the root — what the default fold closes. */
function topLevelDirs(root: TreeDatum): string[] {
  return (root.children ?? []).filter((child) => child.kind === "dir").map((child) => child.path)
}

export function TreeMapD3({
  rows,
  className,
  fill = false,
}: {
  rows: RepositoryGraphBinding[]
  className?: string
  fill?: boolean
}) {
  const data = useMemo(() => buildTreeData(rows), [rows])
  const [folded, setFolded] = useState<ReadonlySet<string>>(() =>
    rows.length > FOLD_ABOVE ? new Set(topLevelDirs(buildTreeData(rows))) : new Set()
  )
  const [selected, setSelected] = useState<TreeDatum | null>(null)
  const [transform, setTransform] = useState<ZoomTransform>(zoomIdentity)
  const svgRef = useRef<SVGSVGElement>(null)
  const behaviourRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null)

  const vendorInk = useMemo(() => seriesScale(rows.map((row) => row.vendor_id)), [rows])
  const foldable = useMemo(() => topLevelDirs(data), [data])

  // `nodeSize` rather than `size`: every node gets an equal slot and the layout grows to fit,
  // which is what keeps a deep repository legible instead of squeezing it into a fixed box.
  const layout = useMemo(() => {
    const root = hierarchy<TreeDatum>(prune(data, folded))
    return d3tree<TreeDatum>().nodeSize(NODE_STEP)(root)
  }, [data, folded])

  const nodes = useMemo(() => layout.descendants(), [layout])
  const links = useMemo(() => layout.links(), [layout])

  /** The frame that fits the laid-out tree — `nodeSize` centres on zero and grows both ways. */
  const fitTransform = useMemo(() => {
    if (nodes.length === 0) return zoomIdentity
    // d3's tree lays out along x as the cross-axis and y as depth; this view draws depth
    // horizontally, so the two swap when they are read.
    const xs = nodes.map((node) => node.y)
    const ys = nodes.map((node) => node.x)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs) + 220
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys) + 24
    const scale = Math.min(WIDTH / (maxX - minX + 80), HEIGHT / (maxY - minY + 80), 1.4)
    return zoomIdentity
      .translate((WIDTH - (maxX + minX) * scale) / 2, (HEIGHT - (maxY + minY) * scale) / 2)
      .scale(scale)
  }, [nodes])

  useEffect(() => {
    const element = svgRef.current
    if (element === null) return
    const behaviour = d3zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 12])
      .on("zoom", (event) => setTransform(event.transform))
    behaviourRef.current = behaviour
    const selection = select(element)
    selection.call(behaviour)
    selection.call(behaviour.transform, fitTransform)
    return () => {
      selection.on(".zoom", null)
      behaviourRef.current = null
    }
  }, [fitTransform])

  function drive(action: (behaviour: ZoomBehavior<SVGSVGElement, unknown>, selection: ReturnType<typeof select<SVGSVGElement, unknown>>) => void) {
    const element = svgRef.current
    const behaviour = behaviourRef.current
    if (element === null || behaviour === null) return
    action(behaviour, select(element))
  }

  function toggle(path: string) {
    setFolded((current) => {
      const next = new Set(current)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-surface border border-line bg-background",
        fill && "h-full",
        className
      )}
    >
      <svg
        ref={svgRef}
        role="group"
        aria-label={TREE_LABEL}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        className={cn("block w-full cursor-grab touch-none select-none", fill ? "h-full" : "h-[44rem]")}
      >
        <g transform={transform.toString()}>
          <g>
            {links.map((link) => (
              <path
                key={`${link.source.data.id}->${link.target.data.id}`}
                d={elbow(link.source, link.target)}
                fill="none"
                strokeWidth={1.2}
                className="stroke-line"
              />
            ))}
          </g>
          <g>
            {nodes.map((node) => {
              const datum = node.data
              const isFolded = folded.has(datum.path) && datum.path !== ""
              const isSelected = selected?.id === datum.id
              const ink =
                datum.vendors.length === 1 ? vendorInk(datum.vendors[0]) : undefined
              return (
                <g
                  key={datum.id || "root"}
                  transform={`translate(${node.y} ${node.x})`}
                  className={datum.kind === "dir" ? "cursor-pointer" : "cursor-default"}
                  onClick={() => {
                    setSelected(isSelected ? null : datum)
                    if (datum.kind === "dir" && datum.path !== "") toggle(datum.path)
                  }}
                >
                  {datum.kind === "dir" ? (
                    <rect
                      x={-5}
                      y={-5}
                      width={10}
                      height={10}
                      rx={2}
                      className={isSelected ? "fill-foreground" : "fill-line-strong"}
                    />
                  ) : (
                    <circle
                      r={4}
                      fill={ink ?? undefined}
                      className={ink === undefined ? (isSelected ? "fill-foreground" : "fill-line-strong") : undefined}
                    />
                  )}
                  <text
                    x={10}
                    y={4}
                    className={cn(
                      "pointer-events-none text-meta",
                      datum.kind === "dir" ? "fill-ink" : "fill-ink-muted"
                    )}
                    paintOrder="stroke"
                    strokeWidth={4}
                    stroke="var(--color-background)"
                  >
                    {datum.name || "/"}
                    {datum.kind === "dir" && (
                      <tspan className="fill-ink-muted">
                        {" "}
                        {isFolded ? `▸ ${datum.weight}` : `▾ ${datum.weight}`}
                      </tspan>
                    )}
                  </text>
                  <title>
                    {datum.path || "/"} — {datum.weight} call{" "}
                    {datum.weight === 1 ? "site" : "sites"}
                    {datum.vendors.length > 0 && `, ${datum.vendors.join(", ")}`}
                  </title>
                </g>
              )
            })}
          </g>
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-wrap items-start justify-between gap-row p-row">
        <div className="pointer-events-auto flex flex-wrap items-center gap-field rounded-surface border border-line bg-surface/90 p-field backdrop-blur">
          <Button
            variant="outline"
            size="sm"
            onClick={() => drive((behaviour, selection) => selection.call(behaviour.scaleBy, 1.5))}
          >
            Zoom in
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => drive((behaviour, selection) => selection.call(behaviour.scaleBy, 1 / 1.5))}
          >
            Zoom out
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => drive((behaviour, selection) => selection.call(behaviour.transform, fitTransform))}
          >
            Fit
          </Button>
          <span className="px-field text-meta text-ink-muted tabular-nums">
            {nodes.length} nodes · {Math.round(transform.k * 100)}%
          </span>
        </div>

        {foldable.length > 0 && (
          <div className="pointer-events-auto flex flex-wrap items-center gap-field rounded-surface border border-line bg-surface/90 p-field backdrop-blur">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFolded(new Set(foldable))}
              disabled={folded.size === foldable.length}
            >
              Fold all
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFolded(new Set())}
              disabled={folded.size === 0}
            >
              Expand all
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

/** A right-angled link: a file tree reads as a tree, not as a flow. */
function elbow(source: HierarchyPointNode<TreeDatum>, target: HierarchyPointNode<TreeDatum>): string {
  const midpoint = (source.y + target.y) / 2
  return `M ${source.y} ${source.x} H ${midpoint} V ${target.x} H ${target.y}`
}

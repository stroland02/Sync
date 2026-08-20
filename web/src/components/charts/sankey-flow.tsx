/**
 * A conserving flow diagram: where work goes, and where it stops.
 *
 * **A Sankey's whole claim is conservation** — what enters a node leaves it. That is what makes a
 * narrowing band mean *attrition* rather than *a smaller number happened to be nearby*. So this
 * component refuses to draw a non-conserving flow rather than rendering one that misleads, and
 * `assertConserves` is exported so a caller can check its own data before building links.
 *
 * **The unit must not change across the diagram**, which is the trap this was written against.
 * Measured on Sync's own graph: 8,723 vendor changes produced 13 change units which carry 24 open
 * findings. Drawing that as one flow would put three different units on one set of bands and make
 * a widening look like growth — a change unit is not a finding, and a finding is not a change. A
 * caller with two units has two diagrams, or one diagram and a stated figure beside it.
 *
 * **Colour is `volumeScale`, and it encodes the band's own share** — not good or bad. A terminal
 * node is not a failure: *not yet attempted* is the ordinary state of a codebase whose remediation
 * loop has not run, and it is drawn like any other destination.
 */

import { useMemo } from "react"
import { sankey, sankeyLinkHorizontal, sankeyJustify } from "d3-sankey"

import { SERIES_SLOTS, volumeScale } from "@/lib/palette"

export interface FlowNode {
  readonly id: string
  /** What the reader sees. Short — this sits inside the diagram. */
  readonly label: string
  /**
   * A reserved status tone for a node that IS a state (an outcome, a lifecycle stage), or
   * absent for a structural node. The band flowing INTO a toned node wears its ink, so the
   * flow's colours agree with the tags the same outcomes wear everywhere else (owner ruling
   * 2026-08-19). Colour is never alone — the label and count sit on every node, and the
   * hover says the whole sentence.
   */
  readonly tone?: "good" | "warning" | "serious" | "critical"
}

export interface FlowLink {
  readonly source: string
  readonly target: string
  readonly value: number
}

/**
 * Every node's inflow equals its outflow, except sources and sinks.
 *
 * Returns the offending node ids rather than a boolean, so a failure names what to fix. A caller
 * that ignores this draws bands whose widths do not add up, which is the one thing a Sankey
 * promises they do.
 */
export function assertConserves(links: readonly FlowLink[]): string[] {
  const inflow = new Map<string, number>()
  const outflow = new Map<string, number>()
  for (const link of links) {
    outflow.set(link.source, (outflow.get(link.source) ?? 0) + link.value)
    inflow.set(link.target, (inflow.get(link.target) ?? 0) + link.value)
  }
  const broken: string[] = []
  for (const [id, into] of inflow) {
    const out = outflow.get(id)
    // A sink has no outflow and is fine. A node that forwards *some* of what it receives is not.
    if (out !== undefined && Math.abs(into - out) > 1e-9) broken.push(id)
  }
  return broken
}

interface LaidOutNode {
  tone?: "good" | "warning" | "serious" | "critical"
  id: string
  label: string
  x0: number
  x1: number
  y0: number
  y1: number
  value: number
}

interface LaidOutLink {
  source: string
  target: string
  value: number
  /** Filled by the layout, absent on the input. */
  width?: number
}

export function SankeyFlow({
  nodes,
  links,
  unit,
  height = 300,
}: {
  readonly nodes: readonly FlowNode[]
  readonly links: readonly FlowLink[]
  /** The one unit every band is counted in. Rendered, because a Sankey with two units lies. */
  readonly unit: string
  readonly height?: number
}) {
  const broken = assertConserves(links)
  const layout = useMemo(() => {
    if (broken.length > 0 || links.length === 0) return null
    const width = 720
    const generator = sankey<LaidOutNode, LaidOutLink>()
      .nodeId((node) => node.id)
      .nodeWidth(10)
      .nodePadding(18)
      // `sankeyJustify` pins terminal nodes to the right edge, so every destination lines up in
      // one column and the diagram reads as stages rather than as a drift.
      .nodeAlign(sankeyJustify)
      .extent([
        [1, 6],
        [width - 1, height - 6],
      ])
    return generator({
      nodes: nodes.map((node) => ({ ...node })) as LaidOutNode[],
      links: links.map((link) => ({ ...link })),
    })
  }, [nodes, links, height, broken.length])

  if (broken.length > 0) {
    // Loud rather than quiet: a Sankey whose bands do not add up is worse than no diagram,
    // because its whole claim is that they do.
    return (
      <p className="max-w-prose text-body text-ink-muted">
        This flow does not conserve at {broken.join(", ")} — what enters those stages does not
        equal what leaves. Nothing is drawn, because a Sankey whose bands do not add up asserts an
        attrition that was never measured.
      </p>
    )
  }
  if (layout === null) return null

  const total = Math.max(...layout.nodes.map((node) => node.value ?? 0), 1)
  const ramp = volumeScale(SERIES_SLOTS[0])

  return (
    <svg
      viewBox={`0 0 720 ${height}`}
      className="w-full"
      role="img"
      aria-label={`Flow diagram, ${unit}: ${links
        .map((l) => `${l.value} from ${l.source} to ${l.target}`)
        .join("; ")}`}
    >
      <g>
        {layout.links.map((link, index) => (
          <path
            key={index}
            d={sankeyLinkHorizontal()(link as never) ?? undefined}
            fill="none"
            stroke={
              (link.target as LaidOutNode).tone !== undefined
                ? `var(--color-${(link.target as LaidOutNode).tone}-ink)`
                : ramp((link.value ?? 0) / total)
            }
            strokeOpacity={0.55}
            strokeWidth={Math.max(link.width ?? 1, 1)}
            className="hover:[stroke-opacity:0.85]"
          >
            <title>
              {`${link.value} ${unit}: ${(link.source as LaidOutNode).label} to ${(link.target as LaidOutNode).label}`}
            </title>
          </path>
        ))}
      </g>
      <g>
        {layout.nodes.map((node) => {
          const atEnd = node.x0 > 620
          return (
            <g key={node.id}>
              <rect
                x={node.x0}
                y={node.y0}
                width={node.x1 - node.x0}
                height={Math.max(node.y1 - node.y0, 1)}
                fill={
                  node.tone !== undefined
                    ? `var(--color-${node.tone}-ink)`
                    : ramp((node.value ?? 0) / total)
                }
              >
                <title>{`${node.label}: ${(node.value ?? 0).toLocaleString()} ${unit}`}</title>
              </rect>
              {/* The count travels with the label. A reader must never have to recover a
                  quantity from a band's thickness. */}
              <text
                x={atEnd ? node.x0 - 8 : node.x1 + 8}
                y={(node.y0 + node.y1) / 2}
                dy="0.35em"
                textAnchor={atEnd ? "end" : "start"}
                className="fill-ink text-[11px]"
              >
                {node.label}
                <tspan className="fill-ink-muted"> {(node.value ?? 0).toLocaleString()}</tspan>
              </text>
            </g>
          )
        })}
      </g>
    </svg>
  )
}

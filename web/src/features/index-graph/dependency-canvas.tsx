/**
 * The API dependency graph, drawn.
 *
 * Vendor, then operation, then call site, on a pannable plane — the one screen that shows what the
 * indexer actually built rather than describing it. It is deliberately not a database-schema
 * picture: the entities are Sync's own, and the edge between an operation and a call site carries
 * **the rung that binding was established at**, which is the fact this whole console exists to keep
 * visible.
 *
 * **Three refusals are load-bearing here and each is asserted in `dependency-canvas.test.tsx`.**
 *
 * 1. **No rung is drawn as better than another.** A rung is a class of evidence, not a grade, so
 *    every edge is one ink and one weight and the rung is the *word* written on it. Nothing here
 *    reads as strong-to-weak, and nothing depends on telling two colours apart. `DESIGN.md` already
 *    holds the rung monochrome at both existing levels; this is the third.
 * 2. **Containment carries no rung.** A vendor contains an operation because the payload names the
 *    pair, not because anything was observed. Its edge is unlabelled and the legend says why.
 *    Aggregating the rungs beneath it would be the composite figure this console refuses.
 * 3. **Absence, zero and never-measured stay three facts.** A vendor whose bindings were never
 *    fetched, one fetched and holding none, and one holding some are three different sentences on
 *    the card. Coverage that was never read — every repository whose id contains a slash, which
 *    `/api/repositories/{repo_id}/coverage` answers 404 for (`B147`) — says so rather than showing
 *    a nought.
 *
 * Geometry lives in `graph-layout.ts` and nothing is measured from the DOM, so the canvas behaves
 * identically in jsdom and in Chrome and the hard part is testable. The component takes its data as
 * props: a caller assembles `vendors` from `/api/overview` and `.../coverage`, and `rows` from
 * `/api/vendors/{id}` or `.../operations/{id}/bindings`, whichever it already holds.
 */

import { useId, useMemo, useRef, useState } from "react"
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react"

import { BINDING_SOURCES } from "@/api/types"
import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { describeRung, formatTimestamp } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  type BindingRow,
  type GraphEdge,
  type GraphNode,
  type VendorInput,
  type Viewport,
  edgeRungLabel,
  fitViewport,
  layoutDependencyGraph,
  panViewport,
  zoomViewport,
} from "@/features/index-graph/graph-layout"

export const CANVAS_LABEL = "API dependency graph"
export const MINIMAP_LABEL = "The whole graph, with the current view marked"

export const SCOPE_NOTE =
  "This plane draws the vendors, operations and call sites the loaded payloads hold. It is what the indexer found, not a claim about what the repository contains."

export const RUNG_LEGEND_NOTE =
  "A rung names the class of evidence behind a binding. It is not a grade, and nothing on this plane draws one rung as stronger than another: every edge is the same weight in the same ink, and the rung is the word written on it."

export const CONTAINMENT_NOTE =
  "Only a call site's edge to its operation carries a rung, because only that edge is a binding. The edge from a vendor to one of its operations is containment, and it carries none rather than borrowing one from the call sites beneath it."

export const STALENESS_NOTE =
  "Last indexed is the newest call site the index holds for that vendor. It is the age of the evidence, not a promise that the index is current."

export const COVERAGE_NOT_READ_NOTE = "coverage not read"

export const COVERAGE_QUALIFICATION =
  "A vendor missing from index coverage is not a zero: that route cannot tell an indexer that looked and found nothing from a repository nothing declares a package for. Coverage is unread for any repository whose id contains a slash, which the route answers 404 for."

export const NOT_COUNTED_NOTE = "not counted in this scope"
export const NOT_RECORDED_NOTE = "not recorded"
export const BINDINGS_NOT_QUERIED_NOTE = "bindings not queried"
export const NO_BINDINGS_NOTE = "queried, no call sites"
export const NO_CHANGE_KIND_NOTE = "no change kind emitted"
/**
 * Its own sentence rather than the generic one, because it is its own fact: the indexer bound this
 * call site and recorded no symbol for it. Sharing a phrase with an unrecorded index time would put
 * two different silences under one wording.
 */
export const NO_SYMBOL_NOTE = "no symbol recorded"
export const UNATTRIBUTED_OPERATION_LABEL = "no operation attributed"

export const EMPTY_GRAPH_NOTE =
  "Nothing was passed to this canvas. That is a statement about what this view was given, not about what the index holds."

/** The plane's fixed height. A page-layout number used once, spelled here rather than tokenised. */
const CANVAS_HEIGHT = "h-[36rem]"

/**
 * The absence marker with the fact it names, each in its own element.
 *
 * `<Absent>` owns the glyph and its ink; the note sits inside it so a reader gets the marker *and*
 * the sentence, which is the whole distinction between "nothing here", "never measured" and a
 * confirmed nought that this canvas has to keep apart.
 */
function AbsentNote({ children }: { children: string }) {
  return (
    <Absent>
      <span>{children}</span>
    </Absent>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-field">
      <span className="furniture shrink-0 text-meta text-ink-muted">{label}</span>
      <span className="min-w-0 truncate text-meta">{children}</span>
    </div>
  )
}

function VendorCardBody({ node }: { node: Extract<GraphNode, { kind: "vendor" }> }) {
  const { vendor, operationCount } = node
  return (
    <>
      <span className="min-w-0 truncate text-emphasis">{vendor.vendorId}</span>
      <Field label="Open findings">
        {vendor.openFindingCount === null ? (
          <AbsentNote>{NOT_COUNTED_NOTE}</AbsentNote>
        ) : (
          <span>{vendor.openFindingCount}</span>
        )}
      </Field>
      <Field label="Indexed call sites">
        {vendor.indexedCallSiteCount === null ? (
          <AbsentNote>{COVERAGE_NOT_READ_NOTE}</AbsentNote>
        ) : (
          <span>{vendor.indexedCallSiteCount}</span>
        )}
      </Field>
      <Field label="Last indexed">
        {vendor.lastIndexed === null ? (
          <AbsentNote>{NOT_RECORDED_NOTE}</AbsentNote>
        ) : (
          <Formatted value={formatTimestamp(vendor.lastIndexed)} />
        )}
      </Field>
      <Field label="Operations drawn">
        {operationCount > 0 ? (
          <span>{operationCount}</span>
        ) : vendor.bindingsQueried ? (
          <AbsentNote>{NO_BINDINGS_NOTE}</AbsentNote>
        ) : (
          <AbsentNote>{BINDINGS_NOT_QUERIED_NOTE}</AbsentNote>
        )}
      </Field>
    </>
  )
}

function OperationCardBody({ node }: { node: Extract<GraphNode, { kind: "operation" }> }) {
  return (
    <>
      <span className="min-w-0 truncate text-emphasis">
        {node.operationId === null ? (
          <AbsentNote>{UNATTRIBUTED_OPERATION_LABEL}</AbsentNote>
        ) : (
          node.operationId
        )}
      </span>
      <Field label="Call sites">
        <span>{node.callSiteCount}</span>
      </Field>
    </>
  )
}

function CallSiteCardBody({ node }: { node: Extract<GraphNode, { kind: "call-site" }> }) {
  return (
    <>
      <span className="min-w-0 truncate font-mono text-body">{`${node.file}:${node.line}`}</span>
      <Field label="Symbol">
        {node.symbol === null ? (
          <AbsentNote>{NO_SYMBOL_NOTE}</AbsentNote>
        ) : (
          <span className="font-mono">{node.symbol}</span>
        )}
      </Field>
      <Field label="Change kind">
        {node.changeKinds.length === 0 ? (
          <AbsentNote>{NO_CHANGE_KIND_NOTE}</AbsentNote>
        ) : (
          <span className="font-mono">{node.changeKinds.join(", ")}</span>
        )}
      </Field>
    </>
  )
}

function NodeCard({
  node,
  selected,
  onSelect,
}: {
  node: GraphNode
  selected: boolean
  onSelect: () => void
}) {
  return (
    <foreignObject x={node.x} y={node.y} width={node.width} height={node.height}>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className={cn(
          "flex h-full w-full min-w-0 flex-col gap-field overflow-hidden rounded-surface border bg-surface p-row text-left",
          // The brand accent marks the current node. DESIGN.md licenses exactly that use, and it
          // is the only chromatic thing on this plane.
          selected ? "border-ring ring-1 ring-ring" : "border-line"
        )}
      >
        {node.kind === "vendor" ? (
          <VendorCardBody node={node} />
        ) : node.kind === "operation" ? (
          <OperationCardBody node={node} />
        ) : (
          <CallSiteCardBody node={node} />
        )}
      </button>
    </foreignObject>
  )
}

function Edge({ edge, from, to }: { edge: GraphEdge; from: GraphNode; to: GraphNode }) {
  const x1 = from.x + from.width
  const y1 = from.y + from.height / 2
  const x2 = to.x
  const y2 = to.y + to.height / 2
  const bend = (x2 - x1) / 2
  const label = edgeRungLabel(edge)
  return (
    <g>
      <path
        d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`}
        fill="none"
        strokeWidth={1.5}
        className="stroke-line-strong"
      />
      {label !== null && (
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
      )}
    </g>
  )
}

function Minimap({
  nodes,
  frame,
  view,
}: {
  nodes: GraphNode[]
  frame: Viewport
  view: Viewport
}) {
  return (
    <svg
      aria-label={MINIMAP_LABEL}
      role="img"
      viewBox={`${frame.x} ${frame.y} ${frame.width} ${frame.height}`}
      preserveAspectRatio="xMidYMid meet"
      className="h-24 w-40 rounded-surface border border-line bg-background"
    >
      {nodes.map((node) => (
        <rect
          key={node.id}
          data-node={node.id}
          x={node.x}
          y={node.y}
          width={node.width}
          height={node.height}
          className="fill-line-strong"
        />
      ))}
      <rect
        data-view="current"
        x={view.x}
        y={view.y}
        width={view.width}
        height={view.height}
        fill="none"
        strokeWidth={8}
        className="stroke-ring"
      />
    </svg>
  )
}

export function DependencyCanvas({
  vendors,
  rows,
  className,
}: {
  /** One entry per vendor the overview named, with every unanswered question left `null`. */
  vendors: VendorInput[]
  /** The bindings to draw. A vendor a row names but the overview did not still gets a node. */
  rows: BindingRow[]
  className?: string
}) {
  const patternId = useId()
  const layout = useMemo(() => layoutDependencyGraph({ vendors, rows }), [vendors, rows])
  const fit = useMemo(() => fitViewport(layout.bounds), [layout.bounds])
  const [panned, setPanned] = useState<Viewport | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const drag = useRef<{ x: number; y: number } | null>(null)

  const view = panned ?? fit
  const byId = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node] as const)),
    [layout.nodes]
  )

  function onPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY }
  }

  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const start = drag.current
    if (start === null) return
    // The only place the rendered size is read, and it is read to convert a pointer delta into
    // graph units. jsdom reports zero here, which makes dragging a no-op rather than a crash --
    // and nothing about the canvas's correctness depends on this path.
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

  return (
    <section className={cn("flex min-w-0 flex-col gap-section", className)}>
      <div className="flex flex-wrap items-center justify-between gap-section">
        <div className="flex flex-wrap items-center gap-field">
          <Button variant="outline" size="sm" onClick={() => setPanned(zoomViewport(view, 2, fit))}>
            Zoom in
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPanned(zoomViewport(view, 0.5, fit))}
          >
            Zoom out
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPanned(null)}>
            Auto-layout
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
          <defs>
            <pattern
              id={patternId}
              x={0}
              y={0}
              width={32}
              height={32}
              patternUnits="userSpaceOnUse"
            >
              {/* The plane's grain, at DESIGN.md's recessive gridline step. It carries no data,
                  so it carries no contrast obligation either -- it is there to make panning
                  legible as movement across a surface. */}
              <circle cx={1} cy={1} r={1.5} className="fill-chart-grid" />
            </pattern>
          </defs>
          {/* Drawn a whole view wider than the view on every side: `meet` letterboxes the viewBox
              inside the element's own box, so a rect sized exactly to the view leaves the
              letterboxed margin bare. */}
          <rect
            x={view.x - view.width}
            y={view.y - view.height}
            width={view.width * 3}
            height={view.height * 3}
            fill={`url(#${patternId})`}
          />
          <g>
            {layout.edges.map((edge) => {
              const from = byId.get(edge.from)
              const to = byId.get(edge.to)
              return from === undefined || to === undefined ? null : (
                <Edge key={edge.id} edge={edge} from={from} to={to} />
              )
            })}
          </g>
          <g>
            {layout.nodes.map((node) => (
              <NodeCard
                key={node.id}
                node={node}
                selected={selected === node.id}
                onSelect={() => setSelected(selected === node.id ? null : node.id)}
              />
            ))}
          </g>
        </svg>

        {layout.nodes.length === 0 && (
          <p className="absolute inset-0 flex items-center justify-center p-section text-center text-body text-ink-muted">
            {EMPTY_GRAPH_NOTE}
          </p>
        )}

        <div className="absolute right-0 bottom-0 p-section">
          <Minimap nodes={layout.nodes} frame={fit} view={view} />
        </div>
      </div>

      <div className="flex flex-col gap-section">
        <ul aria-label="Provenance rungs" className="flex flex-wrap gap-section">
          {BINDING_SOURCES.map((rung) => (
            <li key={rung} className="flex min-w-0 flex-col gap-field">
              <span className="furniture rounded-control border border-line px-field text-meta">
                {rung}
              </span>
              <span className="text-meta text-ink-muted">{describeRung(rung)}</span>
            </li>
          ))}
        </ul>
        <p className="max-w-prose text-body text-ink-muted">{RUNG_LEGEND_NOTE}</p>
        <p className="max-w-prose text-body text-ink-muted">{CONTAINMENT_NOTE}</p>
        <p className="max-w-prose text-body text-ink-muted">{STALENESS_NOTE}</p>
        <p className="max-w-prose text-body text-ink-muted">{COVERAGE_QUALIFICATION}</p>
      </div>
    </section>
  )
}

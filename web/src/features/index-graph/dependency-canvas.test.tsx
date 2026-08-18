/**
 * The indexing canvas: what it draws, and — more importantly — what it refuses to draw.
 *
 * This screen is the one that says what Sync is in a single picture, which makes it the screen most
 * likely to grow a reassuring number nobody computed. Every assertion below is either a structural
 * invariant of the graph it renders or a refusal from `CLAUDE.md`'s console section.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structure. Never a
 * class name, never a snapshot. Node geometry is asserted in `graph-layout.test.ts`, where it is
 * arithmetic; jsdom has no layout engine and an assertion about pixels here would be worthless.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { BINDING_SOURCES } from "@/api/types"
import { describeRung } from "@/lib/format"
import {
  BINDINGS_NOT_QUERIED_NOTE,
  CANVAS_LABEL,
  CONTAINMENT_NOTE,
  COVERAGE_NOT_READ_NOTE,
  DependencyCanvas,
  EMPTY_GRAPH_NOTE,
  MINIMAP_LABEL,
  NO_BINDINGS_NOTE,
  NO_CHANGE_KIND_NOTE,
  NO_SYMBOL_NOTE,
  NOT_COUNTED_NOTE,
  NOT_RECORDED_NOTE,
  RUNG_LEGEND_NOTE,
  STALENESS_NOTE,
  UNATTRIBUTED_OPERATION_LABEL,
} from "@/features/index-graph/dependency-canvas"
import type { BindingRow, VendorInput } from "@/features/index-graph/graph-layout"

afterEach(cleanup)

function vendor(vendorId: string, over: Partial<VendorInput> = {}): VendorInput {
  return {
    vendorId,
    openFindingCount: 0,
    indexedCallSiteCount: 0,
    lastIndexed: null,
    bindingsQueried: true,
    ...over,
  }
}

/** Shrunk from what `/api/overview`, `/api/vendors/stripe` and `.../coverage` actually answer. */
const vendors: VendorInput[] = [
  vendor("stripe", {
    openFindingCount: 10,
    indexedCallSiteCount: 31,
    lastIndexed: "2026-08-17T22:09:22.206496+00:00",
  }),
  vendor("seed-console-twilio", { openFindingCount: 1, indexedCallSiteCount: 2 }),
]

const rows: BindingRow[] = [
  {
    vendor: "stripe",
    operation: "PostCharges",
    file: "src/checkout.ts",
    line: 5,
    symbol: "stripe.charges.create",
    rung: "static",
    changeKind: "request-property-removed",
  },
  {
    vendor: "stripe",
    operation: "GetAccounts",
    file: "app/api/debug/get_demo_account/route.ts",
    line: 9,
    symbol: "stripe.accounts.list",
    rung: "observed",
    changeKind: "response-optional-property-removed",
  },
  {
    vendor: "seed-console-twilio",
    operation: null,
    file: "lib/sms.ts",
    line: 42,
    symbol: null,
    rung: "unresolved",
    changeKind: null,
  },
]

function canvasSvg(container: HTMLElement): SVGSVGElement {
  const svg = container.querySelector<SVGSVGElement>(`svg[aria-label="${CANVAS_LABEL}"]`)
  if (svg === null) throw new Error("the canvas did not render")
  return svg
}

function viewBoxOf(svg: SVGSVGElement): number[] {
  return (svg.getAttribute("viewBox") ?? "").split(" ").map(Number)
}

/** Every `<text>` in the canvas is an edge label; node cards render HTML inside `foreignObject`. */
function edgeLabels(container: HTMLElement): string[] {
  return [...canvasSvg(container).querySelectorAll("text")].map((node) => node.textContent ?? "")
}

describe("DependencyCanvas — the graph it draws", () => {
  it("draws the vendor, the operation and the call site as three ranks of cards", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    expect(screen.getByText("stripe")).toBeTruthy()
    expect(screen.getByText("PostCharges")).toBeTruthy()
    expect(screen.getByText("GetAccounts")).toBeTruthy()
    expect(screen.getByText("src/checkout.ts:5")).toBeTruthy()
    expect(screen.getByText("stripe.charges.create")).toBeTruthy()
  })

  it("makes every node a control a keyboard can reach and select", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const nodes = screen.getAllByRole("button", { pressed: false })
    expect(nodes.length).toBeGreaterThan(0)

    const vendorNode = screen.getByRole("button", { name: /^stripe/ })
    fireEvent.click(vendorNode)
    expect(vendorNode.getAttribute("aria-pressed")).toBe("true")
  })

  it("renders the change kind the detector emitted, and never a severity of its own", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    expect(screen.getByText("request-property-removed")).toBeTruthy()
    expect(screen.getByText("response-optional-property-removed")).toBeTruthy()
    // A call site whose finding emitted no kind says so rather than borrowing one.
    expect(screen.getByText(NO_CHANGE_KIND_NOTE)).toBeTruthy()
  })
})

describe("DependencyCanvas — the rung on the edge", () => {
  it("writes each binding's rung on its own edge, as a word", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const labels = edgeLabels(container)
    expect(labels.length).toBeGreaterThan(0)
    expect(labels).toContain("static")
    expect(labels).toContain("observed")
    expect(labels).toContain("unresolved")
  })

  it("labels exactly the binding edges and leaves containment carrying no rung", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    // Three call sites, so three bindings. The three vendor-to-operation edges carry nothing:
    // a rung is established by evidence and nothing established containment.
    const labels = edgeLabels(container)
    expect(labels).toHaveLength(3)
    expect(screen.getByText(CONTAINMENT_NOTE)).toBeTruthy()
  })

  it("keeps both rungs when two rows disagree about one call site, rather than choosing", () => {
    const { container } = render(
      <DependencyCanvas
        vendors={[vendor("stripe")]}
        rows={[
          { ...rows[0], rung: "static" },
          { ...rows[0], rung: "observed" },
        ]}
      />
    )

    const labels = edgeLabels(container)
    expect(labels).toHaveLength(1)
    expect(labels[0]).toContain("static")
    expect(labels[0]).toContain("observed")
  })

  it("explains every rung in the vocabulary and states that none outranks another", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const legend = screen.getByRole("list", { name: /rung/i })
    expect(BINDING_SOURCES.length).toBeGreaterThan(0)
    for (const rung of BINDING_SOURCES) {
      expect(within(legend).getByText(rung)).toBeTruthy()
      expect(within(legend).getByText(describeRung(rung))).toBeTruthy()
    }
    expect(screen.getByText(RUNG_LEGEND_NOTE)).toBeTruthy()
  })
})

describe("DependencyCanvas — absence, zero and never-measured stay apart", () => {
  it("says a vendor's bindings were never queried rather than drawing it as empty", () => {
    render(
      <DependencyCanvas
        vendors={[vendor("never", { bindingsQueried: false }), vendor("empty")]}
        rows={[]}
      />
    )

    expect(screen.getByText(BINDINGS_NOT_QUERIED_NOTE)).toBeTruthy()
    expect(screen.getByText(NO_BINDINGS_NOTE)).toBeTruthy()
  })

  it("prints a confirmed count as a number and an unread coverage as its own note", () => {
    render(
      <DependencyCanvas
        vendors={[
          vendor("counted", { openFindingCount: 0, indexedCallSiteCount: 31 }),
          vendor("uncounted", { openFindingCount: null, indexedCallSiteCount: null }),
        ]}
        rows={[]}
      />
    )

    // A confirmed nought is a number on screen, never the absence marker.
    expect(screen.getByText("0")).toBeTruthy()
    expect(screen.getByText("31")).toBeTruthy()
    expect(screen.getByText(NOT_COUNTED_NOTE)).toBeTruthy()
    expect(screen.getByText(COVERAGE_NOT_READ_NOTE)).toBeTruthy()
  })

  it("names an unrecorded index time and says the recorded one is staleness, not currency", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    expect(screen.getByText(NOT_RECORDED_NOTE)).toBeTruthy()
    expect(screen.getByText(STALENESS_NOTE)).toBeTruthy()
    // A call site the indexer bound without recording a symbol is its own silence, not the same
    // one as a vendor with no index time. Two facts, two sentences.
    expect(screen.getByText(NO_SYMBOL_NOTE)).toBeTruthy()
    expect(NO_SYMBOL_NOTE).not.toBe(NOT_RECORDED_NOTE)
  })

  it("files a call site attributed to no operation under a named absence", () => {
    render(<DependencyCanvas vendors={vendors} rows={rows} />)

    expect(screen.getByText(UNATTRIBUTED_OPERATION_LABEL)).toBeTruthy()
    expect(screen.getByText("lib/sms.ts:42")).toBeTruthy()
  })

  it("says what an empty canvas means instead of rendering a blank plane", () => {
    const { container } = render(<DependencyCanvas vendors={[]} rows={[]} />)

    expect(screen.getByText(EMPTY_GRAPH_NOTE)).toBeTruthy()
    // Still a drawable frame: a zero-width viewBox is an invalid SVG, not an empty one.
    const [, , width, height] = viewBoxOf(canvasSvg(container))
    expect(width).toBeGreaterThan(0)
    expect(height).toBeGreaterThan(0)
  })
})

describe("DependencyCanvas — the view controls", () => {
  it("narrows the view on zoom in and returns it to the fitted frame on auto-layout", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const fitted = viewBoxOf(canvasSvg(container))
    fireEvent.click(screen.getByRole("button", { name: /zoom in/i }))
    const zoomed = viewBoxOf(canvasSvg(container))
    expect(zoomed[2]).toBeLessThan(fitted[2])

    fireEvent.click(screen.getByRole("button", { name: /auto-layout/i }))
    expect(viewBoxOf(canvasSvg(container))).toEqual(fitted)
  })

  it("widens the view on zoom out", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const fitted = viewBoxOf(canvasSvg(container))
    fireEvent.click(screen.getByRole("button", { name: /zoom out/i }))
    expect(viewBoxOf(canvasSvg(container))[2]).toBeGreaterThan(fitted[2])
  })

  it("shows the whole graph in the minimap with the current view marked on it", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const minimap = container.querySelector<SVGSVGElement>(`svg[aria-label="${MINIMAP_LABEL}"]`)
    expect(minimap).not.toBeNull()
    if (minimap === null) return

    // One mark per node, so the minimap cannot fall out of step with what the canvas draws.
    const marks = minimap.querySelectorAll("rect[data-node]")
    expect(marks.length).toBe(canvasSvg(container).querySelectorAll("foreignObject").length)
    expect(marks.length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole("button", { name: /zoom in/i }))
    const frame = minimap.querySelector("rect[data-view]")
    expect(frame).not.toBeNull()
    const [x, y, width, height] = viewBoxOf(canvasSvg(container))
    expect(Number(frame?.getAttribute("x"))).toBeCloseTo(x, 6)
    expect(Number(frame?.getAttribute("y"))).toBeCloseTo(y, 6)
    expect(Number(frame?.getAttribute("width"))).toBeCloseTo(width, 6)
    expect(Number(frame?.getAttribute("height"))).toBeCloseTo(height, 6)
  })
})

describe("DependencyCanvas — the refusals", () => {
  it("carries no confidence scalar, no health figure and no invented severity", () => {
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const text = container.textContent ?? ""
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toMatch(/confidence|health|healthy|risk score|sev-\d|\d\s*\/\s*10|%/i)
  })

  it("renders no status mark anywhere, on a rung or on anything else", () => {
    // A dot, a pulse or a traffic light on this screen would be a claim about liveness the graph
    // does not hold. The canvas draws rectangles, paths and text and nothing else.
    const { container } = render(<DependencyCanvas vendors={vendors} rows={rows} />)

    const svg = canvasSvg(container)
    const drawn = [...svg.querySelectorAll("circle, ellipse")]
    // The only circles are the dots of the canvas grain, which live in a `<pattern>` and carry
    // no data at all.
    expect(drawn.length).toBeGreaterThan(0)
    for (const shape of drawn) {
      expect(shape.closest("pattern")).not.toBeNull()
    }
  })
})

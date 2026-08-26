/**
 * The map's derivation and its two selection modes.
 *
 * `buildForceGraph` is exported precisely because it is a derivation with a wrong answer: a node
 * addressed by the label a reader sees is addressed by a basename, and two files in one codebase
 * routinely share one. The controlled mode is the other half — the graph page's inspector is the
 * only place a node's detail is read there, so the map must hand the selection out rather than
 * keep it and draw its own card.
 *
 * Scope is `web/CLAUDE.md`'s: derivation and structural invariants, never class names.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { RepositoryGraphBinding } from "@/api/types"
import { buildForceGraph, FORCE_MAP_LABEL, ForceMap } from "@/features/index-graph/force-map"

afterEach(cleanup)

function binding(over: Partial<RepositoryGraphBinding> = {}): RepositoryGraphBinding {
  return {
    vendor_id: "stripe",
    operation_id: "charge",
    path: "src/a/route.ts",
    line: 4,
    symbol: "charge",
    binding_rung: "static",
    ...over,
  }
}

/** Two files whose basenames collide, which is the case the label cannot address. */
const COLLIDING = [
  binding({ path: "src/a/route.ts" }),
  binding({ path: "src/b/route.ts", operation_id: "refund" }),
]

describe("what a node carries beyond its label", () => {
  it("gives a file node the recorded path, not the basename it is drawn with", () => {
    const { nodes } = buildForceGraph(COLLIDING)
    const files = nodes.filter((node) => node.kind === "file")

    expect(files.map((node) => node.label)).toEqual(["route.ts", "route.ts"])
    // The labels are indistinguishable; the paths are the thing an inspector may key on.
    expect(files.map((node) => node.path).sort()).toEqual(["src/a/route.ts", "src/b/route.ts"])
  })

  it("gives an operation node the recorded operation id", () => {
    const { nodes } = buildForceGraph([binding()])
    const operation = nodes.find((node) => node.kind === "operation")

    expect(operation?.operationId).toBe("charge")
    expect(operation?.vendorId).toBe("stripe")
  })

  it("counts a file's weight as the call sites in it", () => {
    const { nodes } = buildForceGraph([
      binding({ line: 4 }),
      binding({ line: 9, operation_id: "refund" }),
    ])
    const file = nodes.find((node) => node.kind === "file")

    expect(file?.weight).toBe(2)
  })
})

describe("the controlled map hands its selection out", () => {
  it("reports the clicked node and draws no card of its own", () => {
    const onSelect = vi.fn()
    render(<ForceMap rows={[binding()]} controls={false} selectedId={null} onSelect={onSelect} />)

    const node = screen.getByRole("button", { name: /^vendor stripe/ })
    fireEvent.click(node)

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect.mock.calls[0][0].id).toBe("vendor:stripe")
    // The inspector owns the detail once the map is controlled; a card over the canvas would be
    // the same facts in two places, disagreeing the moment one is edited. The kind register is
    // the card's own first line and appears nowhere else in the map.
    expect(screen.queryByText("vendor")).toBeNull()
    expect(screen.getByLabelText(FORCE_MAP_LABEL)).toBeTruthy()
  })

  it("reports null when the already-selected node is clicked again", () => {
    const onSelect = vi.fn()
    render(
      <ForceMap
        rows={[binding()]}
        controls={false}
        selectedId="vendor:stripe"
        onSelect={onSelect}
      />,
    )

    fireEvent.click(screen.getByRole("button", { name: /^vendor stripe/ }))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it("reaches every mark from the keyboard", () => {
    const onSelect = vi.fn()
    render(<ForceMap rows={[binding()]} controls={false} selectedId={null} onSelect={onSelect} />)

    // The inspector is the only way to read a node's detail, so a mark only a pointer can reach
    // hides that detail from anyone not using one.
    const node = screen.getByRole("button", { name: /^file route\.ts/ })
    fireEvent.keyDown(node, { key: "Enter" })

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect.mock.calls[0][0].kind).toBe("file")
  })
})

describe("the uncontrolled map keeps its own card", () => {
  it("draws the selected node's detail over the canvas", () => {
    render(<ForceMap rows={[binding()]} controls={false} />)

    fireEvent.click(screen.getByRole("button", { name: /^vendor stripe/ }))

    // The Overview's preview has no inspector beside it, so the card is the only detail there is.
    expect(screen.getByText("vendor")).toBeTruthy()
  })
})

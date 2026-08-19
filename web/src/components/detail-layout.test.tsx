/**
 * The list-detail layout: the list keeps its width when nothing is selected, and the arrow keys
 * move the selection without stealing them from somebody typing.
 *
 * Scope is `console-dev-loop.md`'s — structure and derivation. The one with a wrong answer is the
 * key handler: an arrow key taken from a filter input is a defect a reader meets while searching.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { DetailLayout, useSelectionKeys } from "@/components/detail-layout"

afterEach(cleanup)

function Keys({
  ids,
  selected,
  onSelect,
}: {
  ids: string[]
  selected: string | null
  onSelect: (next: string | null) => void
}) {
  useSelectionKeys(ids, selected, onSelect)
  return <input aria-label="filter" />
}

describe("the detail layout", () => {
  it("gives the list the whole width when nothing is selected", () => {
    const { container } = render(
      <DetailLayout title="none" onClose={() => {}} detail={null} list={<p>the list</p>} />,
    )

    // No empty panel and no reserved column: a screen with nothing selected should look like a
    // screen with nothing selected, not like one whose detail failed to load.
    expect(screen.queryByRole("complementary")).toBeNull()
    expect(container.textContent).toContain("the list")
  })

  it("renders the detail beside the list, not over it", () => {
    render(
      <DetailLayout
        title="src/a.ts:12"
        onClose={() => {}}
        detail={<p>the detail</p>}
        list={<p>the list</p>}
      />,
    )

    // Both readable at once is the whole reason this is not a modal.
    expect(screen.getByText("the list")).toBeTruthy()
    expect(screen.getByText("the detail")).toBeTruthy()
    expect(screen.getByRole("complementary", { name: "src/a.ts:12" })).toBeTruthy()
  })
})

describe("arrow keys with a panel open", () => {
  it("moves the selection down and up", () => {
    const onSelect = vi.fn()
    render(<Keys ids={["a", "b", "c"]} selected="b" onSelect={onSelect} />)

    fireEvent.keyDown(document, { key: "ArrowDown" })
    expect(onSelect).toHaveBeenCalledWith("c")

    fireEvent.keyDown(document, { key: "ArrowUp" })
    expect(onSelect).toHaveBeenCalledWith("a")
  })

  it("stops at the ends rather than wrapping", () => {
    // A list that wraps sends a reader who held the key back to the top believing they are still
    // descending, which is worse than stopping.
    const onSelect = vi.fn()
    render(<Keys ids={["a", "b"]} selected="b" onSelect={onSelect} />)

    fireEvent.keyDown(document, { key: "ArrowDown" })

    expect(onSelect).not.toHaveBeenCalled()
  })

  it("closes on Escape", () => {
    const onSelect = vi.fn()
    render(<Keys ids={["a", "b"]} selected="a" onSelect={onSelect} />)

    fireEvent.keyDown(document, { key: "Escape" })

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it("never steals a key from somebody typing", () => {
    // The defect this prevents: a reader in the filter input pressing Down to reach a suggestion
    // and having the table's selection move instead.
    const onSelect = vi.fn()
    render(<Keys ids={["a", "b"]} selected="a" onSelect={onSelect} />)

    fireEvent.keyDown(screen.getByLabelText("filter"), { key: "ArrowDown" })

    expect(onSelect).not.toHaveBeenCalled()
  })

  it("binds nothing while no row is selected", () => {
    const onSelect = vi.fn()
    render(<Keys ids={["a", "b"]} selected={null} onSelect={onSelect} />)

    fireEvent.keyDown(document, { key: "ArrowDown" })

    expect(onSelect).not.toHaveBeenCalled()
  })
})

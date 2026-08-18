/**
 * Decision 61: an empty table keeps its column headers.
 *
 * The headers are the point. "The shape of the data is legible before there is data, so a reader
 * learns what a finding *is* from a screen that has none" — which a panel replacing the whole
 * table cannot do.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { Table, TableHead, TableHeader, TableRow } from "@/components/data-table"
import { TableEmptyState } from "@/components/table-empty"

afterEach(cleanup)

function renderEmpty(props: Partial<React.ComponentProps<typeof TableEmptyState>> = {}) {
  return render(
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Operation</TableHead>
          <TableHead>Calls</TableHead>
        </TableRow>
      </TableHeader>
      <TableEmptyState
        columns={2}
        headline="Nothing here."
        detail="The read happened and returned no row."
        {...props}
      />
    </Table>
  )
}

describe("TableEmptyState", () => {
  it("leaves the column headers standing, so the shape is legible with no data", () => {
    renderEmpty()

    expect(screen.getByText("Operation")).toBeTruthy()
    expect(screen.getByText("Calls")).toBeTruthy()
  })

  it("states what was checked rather than only that there is nothing", () => {
    renderEmpty()

    expect(screen.getByText("Nothing here.")).toBeTruthy()
    expect(screen.getByText(/read happened and returned no row/)).toBeTruthy()
  })

  it("spans every column, so the sentence is not squeezed into the first one", () => {
    const { container } = renderEmpty()

    expect(container.querySelector("td")?.getAttribute("colspan")).toBe("2")
  })

  /**
   * Decision 61 asks for one next action. It is optional here because it must never be invented:
   * a table with no honest next step says nothing rather than offering a button that does not
   * lead anywhere.
   */
  it("renders a next action when there is one", () => {
    renderEmpty({ action: <a href="/settings">Attach telemetry</a> })

    expect(screen.getByRole("link", { name: "Attach telemetry" })).toBeTruthy()
  })

  it("renders no action slot at all when none was given", () => {
    const { container } = renderEmpty()

    expect(container.querySelector("a")).toBeNull()
  })
})

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  COLUMN_TYPE_LABEL,
  Table,
  TableBody,
  TableCell,
  TableColumnHead,
  TableEmptyRow,
  TableFrame,
  TableHead,
  TableHeader,
  TableHeadTitle,
  TableRow,
  ariaSortFor,
  describeAppliedSort,
  nextSortDirection,
  type ColumnType,
} from "@/components/data-table"

afterEach(cleanup)

describe("DataTable Anatomy", () => {
  it("renders TableHeader with background strip styling and font-medium TableHead", () => {
    const { container } = render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Repository</TableHead>
            <TableHead>Findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>repo-1</TableCell>
            <TableCell>4</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    )

    const thead = container.querySelector("thead")
    expect(thead).not.toBeNull()
    expect(thead?.className).toContain("bg-surface-subtle")

    const th = container.querySelector("th")
    expect(th).not.toBeNull()
    expect(th?.className).toContain("font-medium")
  })

  it("renders TableRow with selected row styling when data-state is selected", () => {
    const { container } = render(
      <Table>
        <TableBody>
          <TableRow data-state="selected">
            <TableCell>selected-row</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    )

    const tr = container.querySelector("tr")
    expect(tr?.className).toContain("data-[state=selected]:bg-surface-emphasis")
  })

  it("renders TableEmptyRow spanning colSpan with empty state contents", () => {
    render(
      <Table>
        <TableBody>
          <TableEmptyRow colSpan={4}>No findings open</TableEmptyRow>
        </TableBody>
      </Table>
    )

    const td = screen.getByText("No findings open")
    expect(td).not.toBeNull()
    expect(td.getAttribute("colspan")).toBe("4")
  })

  it("renders TableHeadTitle with title, optional suffix, rung badge, and bounded indicator", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <TableHeadTitle
                title="Call sites"
                suffix="count"
                rung="static"
                bounded={true}
              />
            </TableHead>
          </TableRow>
        </TableHeader>
      </Table>
    )

    expect(screen.getByText("Call sites")).not.toBeNull()
    expect(screen.getByText("count")).not.toBeNull()
    expect(screen.getByText("static")).not.toBeNull()
    expect(screen.getByText("(bounded)")).not.toBeNull()
  })
})

/**
 * A column type is a fact about the column, not a judgement about its values. It is the one
 * thing a spreadsheet-shaped table gains over a list: a reader can tell a count from an
 * identifier that happens to be digits before reading a single row.
 */
describe("column types", () => {
  it("labels every member of the closed type vocabulary", () => {
    const entries = Object.entries(COLUMN_TYPE_LABEL)

    expect(entries.length).toBeGreaterThan(0)
    for (const [value, label] of entries) {
      expect(value).not.toBe("")
      expect(label).not.toBe("")
    }
  })

  it("renders the column's type beside its name", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead column="path" label="Call site" type="path" />
          </TableRow>
        </TableHeader>
      </Table>
    )

    const th = screen.getByRole("columnheader")
    expect(th.textContent).toContain("Call site")
    expect(th.textContent).toContain(COLUMN_TYPE_LABEL.path)
  })

  it("renders each declared column's own type rather than one type for the table", () => {
    const columns: { column: string; label: string; type: ColumnType }[] = [
      { column: "path", label: "Call site", type: "path" },
      { column: "calls", label: "Calls", type: "count" },
      { column: "seen", label: "Last seen", type: "timestamp" },
    ]

    render(
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableColumnHead
                key={column.column}
                column={column.column}
                label={column.label}
                type={column.type}
              />
            ))}
          </TableRow>
        </TableHeader>
      </Table>
    )

    const headers = screen.getAllByRole("columnheader")
    expect(headers).toHaveLength(columns.length)
    expect(columns.length).toBeGreaterThan(0)
    columns.forEach((column, index) => {
      expect(headers[index].textContent).toContain(column.label)
      expect(headers[index].textContent).toContain(COLUMN_TYPE_LABEL[column.type])
    })
  })
})

describe("sort state", () => {
  it("cycles a column through ascending, descending, and back to the query's own ordering", () => {
    expect(nextSortDirection(null)).toBe("ascending")
    expect(nextSortDirection("ascending")).toBe("descending")
    expect(nextSortDirection("descending")).toBeNull()
  })

  it("reports aria-sort for the sorted column and none for the others", () => {
    const sort = { column: "calls", direction: "descending" as const }
    const others = ["path", "seen"]

    expect(ariaSortFor("calls", sort)).toBe("descending")
    expect(others.length).toBeGreaterThan(0)
    for (const column of others) {
      expect(ariaSortFor(column, sort)).toBe("none")
    }
  })

  it("reports none on every column when no column sort is applied", () => {
    expect(ariaSortFor("calls", null)).toBe("none")
  })

  it("marks the sorted column header with aria-sort and leaves the rest at none", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead
              column="path"
              label="Call site"
              type="path"
              sort={{ column: "calls", direction: "ascending" }}
              onSortChange={() => {}}
            />
            <TableColumnHead
              column="calls"
              label="Calls"
              type="count"
              sort={{ column: "calls", direction: "ascending" }}
              onSortChange={() => {}}
            />
          </TableRow>
        </TableHeader>
      </Table>
    )

    const headers = screen.getAllByRole("columnheader")
    expect(headers).toHaveLength(2)
    expect(headers[0].getAttribute("aria-sort")).toBe("none")
    expect(headers[1].getAttribute("aria-sort")).toBe("ascending")
  })

  it("exposes no sort control and no aria-sort on a column that cannot be sorted", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead column="path" label="Call site" type="path" />
          </TableRow>
        </TableHeader>
      </Table>
    )

    expect(screen.getByRole("columnheader").hasAttribute("aria-sort")).toBe(false)
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("asks for the next direction on the column that was clicked", () => {
    const onSortChange = vi.fn()

    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead
              column="calls"
              label="Calls"
              type="count"
              sort={{ column: "calls", direction: "ascending" }}
              onSortChange={onSortChange}
            />
          </TableRow>
        </TableHeader>
      </Table>
    )

    fireEvent.click(screen.getByRole("button", { name: /Calls/ }))

    expect(onSortChange).toHaveBeenCalledWith({ column: "calls", direction: "descending" })
  })

  it("starts a column that is not the sorted one at ascending rather than continuing the other column's cycle", () => {
    const onSortChange = vi.fn()

    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead
              column="path"
              label="Call site"
              type="path"
              sort={{ column: "calls", direction: "descending" }}
              onSortChange={onSortChange}
            />
          </TableRow>
        </TableHeader>
      </Table>
    )

    fireEvent.click(screen.getByRole("button", { name: /Call site/ }))

    expect(onSortChange).toHaveBeenCalledWith({ column: "path", direction: "ascending" })
  })

  it("clears to the query's own ordering rather than to nothing when the cycle completes", () => {
    const onSortChange = vi.fn()

    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableColumnHead
              column="calls"
              label="Calls"
              type="count"
              sort={{ column: "calls", direction: "descending" }}
              onSortChange={onSortChange}
            />
          </TableRow>
        </TableHeader>
      </Table>
    )

    fireEvent.click(screen.getByRole("button", { name: /Calls/ }))

    expect(onSortChange).toHaveBeenCalledWith(null)
  })
})

/**
 * An unsorted table is not sorted by nothing — it is in the order the query returned. A reader
 * who cannot see that reads a page boundary that moved as a record that changed, which is the
 * distinction `components/ordering.tsx` was written to keep.
 */
describe("describeAppliedSort", () => {
  const label = (column: string) => (column === "calls" ? "Calls" : column)

  it("names the query's own ordering when no column sort is applied, rather than calling it unsorted", () => {
    const sentence = describeAppliedSort(null, label, "the order Sync indexed them")

    expect(sentence).toContain("the order Sync indexed them")
    expect(sentence.toLowerCase()).not.toContain("unsorted")
  })

  it("names the column and the direction when a column sort is applied", () => {
    expect(describeAppliedSort({ column: "calls", direction: "descending" }, label, "x")).toContain(
      "Calls"
    )
    expect(describeAppliedSort({ column: "calls", direction: "descending" }, label, "x")).toContain(
      "descending"
    )
  })
})

describe("TableFrame", () => {
  it("holds the table inside the frame so the scroll belongs to the table rather than the page", () => {
    const { container } = render(
      <TableFrame>
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>src/pay.ts</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableFrame>
    )

    const frame = container.querySelector('[data-slot="table-frame"]')
    expect(frame).not.toBeNull()
    expect(frame?.querySelector("table")).not.toBeNull()
  })
})

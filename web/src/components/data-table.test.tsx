import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableHeadTitle,
  TableRow,
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

/**
 * What the footer of a long table is allowed to claim.
 *
 * Three answers to "how many records are there" have to stay apart, and every one of them has
 * been collapsed onto another somewhere in this console before: a confirmed zero, a total that
 * stopped counting at a ceiling, and a count nothing answered. The first is a measurement, the
 * second is a floor, the third is absence. A footer that renders `0` for all three is the
 * defect this file exists to catch.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  TableFooterBar,
  TableToolbar,
  boundedRecordCaveat,
  describeRecordWindow,
  type RecordTotal,
} from "@/components/table-toolbar"
import { ABSENT } from "@/lib/format"

afterEach(cleanup)

const CONFIRMED = (count: number): RecordTotal => ({ count, boundReached: false })
const BOUNDED = (count: number): RecordTotal => ({ count, boundReached: true })
const UNANSWERED: RecordTotal = { count: null, boundReached: false }

describe("describeRecordWindow", () => {
  it("states a confirmed zero in words rather than as absence", () => {
    expect(describeRecordWindow(0, 0, CONFIRMED(0), "call site", "call sites")).toBe(
      "No call sites."
    )
  })

  it("returns null for a count nothing answered, so the caller renders the absence marker", () => {
    expect(describeRecordWindow(0, 0, UNANSWERED, "call site", "call sites")).toBeNull()
  })

  it("says the page is the whole set when one page holds every record", () => {
    const sentence = describeRecordWindow(0, 7, CONFIRMED(7), "call site", "call sites")

    expect(sentence).toContain("7")
    expect(sentence).toContain("call sites")
    expect(sentence).not.toContain("Showing")
  })

  it("uses the singular noun for exactly one record", () => {
    expect(describeRecordWindow(0, 1, CONFIRMED(1), "call site", "call sites")).toContain(
      "1 call site."
    )
  })

  it("places the page inside the total when the set is longer than a page", () => {
    const sentence = describeRecordWindow(50, 50, CONFIRMED(4213), "call site", "call sites")

    expect(sentence).toContain("51")
    expect(sentence).toContain("100")
    expect(sentence).toContain("4,213")
  })

  it("marks a total that stopped counting with the + convention and never as an exact figure", () => {
    const bounded = describeRecordWindow(0, 50, BOUNDED(1000), "call site", "call sites")
    const confirmed = describeRecordWindow(0, 50, CONFIRMED(1000), "call site", "call sites")

    expect(bounded).toContain("1,000+")
    expect(confirmed).toContain("1,000")
    expect(confirmed).not.toContain("1,000+")
    expect(bounded).not.toBe(confirmed)
  })

  it("never claims a bounded page is the whole set, even when the page holds the counted total", () => {
    const sentence = describeRecordWindow(0, 1000, BOUNDED(1000), "call site", "call sites")

    expect(sentence).toContain("1,000+")
    expect(sentence).toContain("Showing")
  })

  it("says a page is empty rather than rendering an impossible range when the set moved underneath it", () => {
    const sentence = describeRecordWindow(200, 0, CONFIRMED(120), "call site", "call sites")

    expect(sentence).not.toContain("201")
    expect(sentence).toContain("120")
  })
})

describe("boundedRecordCaveat", () => {
  it("says in words what the + glyph means, so the glyph is never the only channel", () => {
    const caveat = boundedRecordCaveat(1000, "call sites")

    expect(caveat).toContain("1,000")
    expect(caveat).toContain("at least")
    expect(caveat).toContain("call sites")
  })
})

function renderFooter(overrides: Partial<Parameters<typeof TableFooterBar>[0]> = {}) {
  const props = {
    offset: 0,
    limit: 50,
    shown: 50,
    total: CONFIRMED(4213),
    singular: "call site",
    plural: "call sites",
    nextOffset: 50 as number | null,
    busy: false,
    onOffsetChange: vi.fn(),
    ...overrides,
  }
  render(<TableFooterBar {...props} />)
  return props
}

describe("TableFooterBar", () => {
  it("states the record count explicitly rather than leaving the reader to count rows", () => {
    renderFooter()

    expect(screen.getByText(/4,213 call sites/)).not.toBeNull()
  })

  it("renders the absence marker, not a zero, when nothing answered the count", () => {
    renderFooter({ total: UNANSWERED, shown: 0, nextOffset: null })

    expect(screen.getByText(new RegExp(ABSENT))).not.toBeNull()
    expect(screen.queryByText(/No call sites\./)).toBeNull()
  })

  it("states a confirmed zero in words, keeping it apart from an unanswered count", () => {
    renderFooter({ total: CONFIRMED(0), shown: 0, nextOffset: null })

    expect(screen.getByText("No call sites.")).not.toBeNull()
  })

  it("carries the caveat sentence beside a bounded total", () => {
    renderFooter({ total: BOUNDED(1000), bound: 1000 })

    expect(screen.getByText(/at least/)).not.toBeNull()
  })

  it("carries no caveat sentence when the total is confirmed", () => {
    renderFooter()

    expect(screen.queryByText(/at least/)).toBeNull()
  })

  it("disables Previous on the first page and Next when the transport reports no next offset", () => {
    renderFooter({ offset: 0, nextOffset: null })

    expect(screen.getByRole("button", { name: "Previous" }).hasAttribute("disabled")).toBe(true)
    expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(true)
  })

  it("asks for the offset the transport reported rather than computing one past the end", () => {
    const props = renderFooter({ offset: 50, nextOffset: 137 })

    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    expect(props.onOffsetChange).toHaveBeenCalledWith(137)
  })

  it("steps Previous back by one page and never below zero", () => {
    const props = renderFooter({ offset: 20, limit: 50 })

    fireEvent.click(screen.getByRole("button", { name: "Previous" }))

    expect(props.onOffsetChange).toHaveBeenCalledWith(0)
  })

  it("disables both controls while a page is in flight", () => {
    renderFooter({ offset: 50, busy: true })

    expect(screen.getByRole("button", { name: "Previous" }).hasAttribute("disabled")).toBe(true)
    expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(true)
  })
})

describe("TableToolbar", () => {
  const filter = {
    legend: "Path",
    value: null,
    placeholder: "src/",
    note: "Applied by the query, not to the rows on screen.",
  }

  it("holds a filter field above the table", () => {
    render(
      <TableToolbar filter={{ ...filter, onSubmit: () => {} }}>
        <button type="button">Export</button>
      </TableToolbar>
    )

    expect(screen.getByLabelText("Path")).not.toBeNull()
    expect(screen.getByRole("button", { name: "Export" })).not.toBeNull()
  })

  it("submits the filter on submit rather than on every keystroke", () => {
    const onSubmit = vi.fn()
    render(<TableToolbar filter={{ ...filter, onSubmit }} />)

    fireEvent.change(screen.getByLabelText("Path"), { target: { value: "src/pay" } })
    expect(onSubmit).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Filter" }))
    expect(onSubmit).toHaveBeenCalledWith("src/pay")
  })

  it("renders its actions without a filter field when a table offers no filter", () => {
    render(
      <TableToolbar>
        <button type="button">Export</button>
      </TableToolbar>
    )

    expect(screen.queryByRole("textbox")).toBeNull()
    expect(screen.getByRole("button", { name: "Export" })).not.toBeNull()
  })
})

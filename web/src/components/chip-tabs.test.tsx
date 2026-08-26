/**
 * The chip strip, and the count rule it inherited from the tablist it replaced.
 *
 * Three of these assertions came across from `describe("TriageTabs")` when that component was
 * deleted on 2026-08-26 — a confirmed zero renders `0`, an unanswered count renders the absence
 * marker and never a zero, and nothing sums across the strip. The component changed; the claims
 * about the counts did not, and they are the reason the strip is worth testing at all.
 *
 * Scope, per `.claude/rules/console-dev-loop.md`: structural invariants and classification, never
 * class names.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChipTabs, type ChipOption } from "@/components/chip-tabs"
import { ABSENT } from "@/lib/format"

afterEach(cleanup)

/** 12 + 3 + 0 = 15, and 15 is what a control that computed a total would render. */
const OPTIONS: ChipOption[] = [
  { id: "breaking", label: "breaking", count: { kind: "counted", value: 12 } },
  { id: "deprecation", label: "deprecation", count: { kind: "counted", value: 3 } },
  { id: "warning", label: "warning", count: { kind: "counted", value: 0 } },
]

function renderChips(overrides: Partial<React.ComponentProps<typeof ChipTabs>> = {}) {
  return render(
    <ChipTabs
      label="Findings by kind"
      options={OPTIONS}
      activeId="breaking"
      onSelect={() => {}}
      {...overrides}
    />
  )
}

describe("ChipTabs", () => {
  it("renders one chip per value, each carrying its own count", () => {
    renderChips()

    expect(OPTIONS.length).toBeGreaterThan(0)
    expect(screen.getAllByRole("button")).toHaveLength(OPTIONS.length)
    for (const option of OPTIONS) {
      expect(screen.getByRole("button", { name: new RegExp(option.label) })).toBeTruthy()
    }
  })

  it("shows 0 on a chip whose count is a confirmed zero", () => {
    renderChips()

    const zero = screen.getByRole("button", { name: /warning/ })
    expect(within(zero).getByText("0")).toBeTruthy()
    expect(within(zero).queryByText(ABSENT)).toBeNull()
  })

  it("shows the absence marker, never 0, on a chip whose count was not answered", () => {
    renderChips({
      options: [
        OPTIONS[0],
        {
          id: "abandoned",
          label: "abandoned",
          count: { kind: "unanswered", why: "the reason-code route was not queried" },
        },
      ],
    })

    const unanswered = screen.getByRole("button", { name: /abandoned/ })
    expect(within(unanswered).getByText(ABSENT)).toBeTruthy()
    expect(within(unanswered).queryByText("0")).toBeNull()
    // The reason travels with the marker, so a screen reader is not handed a bare glyph.
    expect(within(unanswered).getByText(/the reason-code route was not queried/)).toBeTruthy()
  })

  it("computes no total across the chips", () => {
    renderChips()

    const strip = screen.getByRole("group", { name: "Findings by kind" })
    expect(within(strip).queryByText("15")).toBeNull()
  })

  it("marks exactly one chip pressed", () => {
    renderChips({ activeId: "deprecation" })

    const pressed = screen
      .getAllByRole("button")
      .filter((chip) => chip.getAttribute("aria-pressed") === "true")
    expect(pressed).toHaveLength(1)
    expect(pressed[0].textContent).toContain("deprecation")
  })

  it("reports the value an operator pressed rather than selecting it itself", () => {
    // The strip writes a search parameter; it holds no state of its own, so a chip that selected
    // itself would disagree with the URL the moment Back was pressed.
    const onSelect = vi.fn()
    renderChips({ onSelect })

    fireEvent.click(screen.getByRole("button", { name: /deprecation/ }))

    expect(onSelect).toHaveBeenCalledWith("deprecation")
  })

  it("renders a chip with no count at all, for a control that divides nothing countable", () => {
    renderChips({
      options: [
        { id: "units", label: "By change" },
        { id: "flat", label: "Every finding" },
      ],
      activeId: "units",
    })

    const chip = screen.getByRole("button", { name: "By change" })
    expect(chip.textContent).toBe("By change")
  })
})

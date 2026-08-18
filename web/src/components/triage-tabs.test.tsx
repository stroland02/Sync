/**
 * A triage header's counts and its empty state are claims, and this suite guards the two that
 * are easy to get wrong in a way nothing else catches.
 *
 * **A zero and an unanswered count look identical once either one is rendered as `0`.** The
 * component's type keeps them apart before the render happens, so the tests here assert the
 * derivation (`triagePanelState`) as well as what reaches the DOM — a caller cannot pass a bare
 * number, and the tab for a count nobody answered carries the console's absence marker instead.
 *
 * **An empty list after a real scan is a different fact from one before any scan.** That is the
 * sentence `docs/superpowers/plans/2026-08-18-page-information-architecture.md:122-123` puts on
 * this component, and `TriageTabs` takes what was checked as a required prop so the honest empty
 * state is the only one that compiles. These tests hold both branches of it.
 *
 * Scope, per `.claude/rules/console-dev-loop.md`: classification, derivation and structural
 * invariants. No class names, no snapshots.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ABSENT } from "@/lib/format"
import {
  TriageTabs,
  triagePanelState,
  type TriageChecks,
  type TriageTab,
} from "@/components/triage-tabs"

afterEach(cleanup)

const DETECTORS = ["stripe-openapi-diff", "sdk-symbol-drift"] as const

const CHECKED: TriageChecks = {
  kind: "checked",
  ran: ["stripe-openapi-diff", "sdk-symbol-drift"],
  at: "2026-08-18T09:00:00.000Z",
}

const UNCHECKED: TriageChecks = {
  kind: "unchecked",
  why: "no scan has run against this repository yet",
}

/** 12 + 3 + 0 = 15, and 15 is what a component that computed a total would render. */
const TABS: TriageTab[] = [
  { id: "breaking", label: "Breaking", count: { kind: "counted", value: 12 } },
  { id: "deprecation", label: "Deprecation", count: { kind: "counted", value: 3 } },
  { id: "warning", label: "Warning", count: { kind: "counted", value: 0 } },
]

function renderTabs(
  overrides: Partial<React.ComponentProps<typeof TriageTabs>> = {}
) {
  const props = {
    legend: "Findings by kind",
    noun: "findings",
    tabs: TABS,
    activeId: "breaking",
    onSelect: () => {},
    checks: CHECKED,
    children: <p>a table of findings</p>,
    ...overrides,
  }
  return render(<TriageTabs {...props} />)
}

describe("triagePanelState", () => {
  it("separates a counted zero from a count nothing answered", () => {
    expect(triagePanelState({ kind: "counted", value: 0 }, CHECKED)).toBe("empty-after-check")
    expect(triagePanelState({ kind: "unanswered", why: "the route timed out" }, CHECKED)).toBe(
      "count-unanswered"
    )
  })

  it("separates an empty answer after a check from one before any check", () => {
    expect(triagePanelState({ kind: "counted", value: 0 }, CHECKED)).toBe("empty-after-check")
    expect(triagePanelState({ kind: "counted", value: 0 }, UNCHECKED)).toBe(
      "empty-before-any-check"
    )
  })

  it("reports records for any answered count above zero, whatever was checked", () => {
    expect(triagePanelState({ kind: "counted", value: 1 }, CHECKED)).toBe("records")
    expect(triagePanelState({ kind: "counted", value: 12 }, UNCHECKED)).toBe("records")
  })
})

describe("TriageTabs", () => {
  it("renders one tab per kind, each carrying its own count", () => {
    renderTabs()

    const tabs = screen.getAllByRole("tab")
    expect(TABS.length).toBeGreaterThan(0)
    expect(tabs).toHaveLength(TABS.length)
    for (const tab of TABS) {
      const rendered = screen.getByRole("tab", { name: new RegExp(tab.label) })
      expect(rendered).toBeTruthy()
    }
  })

  it("shows 0 on a tab whose count is a confirmed zero", () => {
    renderTabs()

    const zero = screen.getByRole("tab", { name: /Warning/ })
    expect(within(zero).getByText("0")).toBeTruthy()
    expect(within(zero).queryByText(ABSENT)).toBeNull()
  })

  it("shows the absence marker, never 0, on a tab whose count was not answered", () => {
    renderTabs({
      tabs: [
        TABS[0],
        {
          id: "abandoned",
          label: "Abandoned",
          count: { kind: "unanswered", why: "the reason-code route was not queried" },
        },
      ],
    })

    const unanswered = screen.getByRole("tab", { name: /Abandoned/ })
    expect(within(unanswered).getByText(ABSENT)).toBeTruthy()
    expect(within(unanswered).queryByText("0")).toBeNull()
  })

  it("computes no total across the tabs", () => {
    renderTabs()

    const list = screen.getByRole("tablist")
    expect(within(list).getAllByRole("tab")).toHaveLength(TABS.length)
    expect(within(list).queryByText("15")).toBeNull()
  })

  it("marks exactly one tab selected and gives it a panel", () => {
    renderTabs({ activeId: "deprecation" })

    const selected = screen.getAllByRole("tab").filter((t) => t.getAttribute("aria-selected") === "true")
    expect(selected).toHaveLength(1)
    expect(selected[0].textContent).toContain("Deprecation")
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1)
  })

  it("reports the tab an operator picked rather than selecting it itself", () => {
    const onSelect = vi.fn()
    renderTabs({ onSelect })

    fireEvent.mouseDown(screen.getByRole("tab", { name: /Deprecation/ }))

    expect(onSelect).toHaveBeenCalledWith("deprecation")
  })

  it("renders the caller's records when the active tab has some", () => {
    renderTabs({ activeId: "breaking" })

    expect(screen.getByText("a table of findings")).toBeTruthy()
  })

  it("names the detectors that ran when a checked tab came back empty", () => {
    renderTabs({ activeId: "warning" })

    expect(DETECTORS.length).toBeGreaterThan(0)
    for (const detector of DETECTORS) {
      expect(screen.getByText(detector)).toBeTruthy()
    }
    expect(screen.queryByText("a table of findings")).toBeNull()
  })

  it("says a scope nothing has checked is not a zero", () => {
    renderTabs({ activeId: "warning", checks: UNCHECKED })

    expect(screen.getByText(/no scan has run against this repository yet/)).toBeTruthy()
    for (const detector of DETECTORS) {
      expect(screen.queryByText(detector)).toBeNull()
    }
  })

  it("states why a count went unanswered instead of leaving the panel blank", () => {
    renderTabs({
      activeId: "abandoned",
      tabs: [
        TABS[0],
        {
          id: "abandoned",
          label: "Abandoned",
          count: { kind: "unanswered", why: "the reason-code route was not queried" },
        },
      ],
      children: null,
    })

    const panel = screen.getByRole("tabpanel")
    expect(within(panel).getByText(/the reason-code route was not queried/)).toBeTruthy()
    expect(panel.textContent?.trim()).not.toBe("")
  })

  it("renders the filter slot beside the tabs rather than inside the tablist", () => {
    renderTabs({ filters: <button type="button">Vendor</button> })

    const filter = screen.getByRole("button", { name: "Vendor" })
    expect(filter).toBeTruthy()
    expect(within(screen.getByRole("tablist")).queryByRole("button", { name: "Vendor" })).toBeNull()
  })
})

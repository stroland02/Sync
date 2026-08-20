/**
 * The filter rail's counts are the thing it is for, and a count is a claim.
 *
 * `docs/superpowers/plans/2026-08-18-page-information-architecture.md:150-152` puts the whole
 * value of this surface on the counts: *"they tell you what you would get before you click."* A
 * count that is wrong about what class of answer it is destroys exactly that — an option showing
 * `0` that nobody counted promises an empty result the console never checked for.
 *
 * So the two guards that matter here are the two the type system already forces and the DOM has
 * to agree with:
 *
 * - **A confirmed zero renders `0`. An unanswered count renders the absence marker.** Never the
 *   other way round, and never `0` for both.
 * - **An option counted at zero stays selectable.** It is a real answer — the filter would return
 *   nothing — and disabling or hiding it makes the rail claim the value does not exist, which is
 *   a different fact and a false one.
 *
 * Scope, per `.claude/rules/console-dev-loop.md`: classification, derivation and structural
 * invariants. No class names, no snapshots.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ABSENT } from "@/lib/format"
import {
  FilterRail,
  activeSelections,
  formatFilterCount,
  unansweredCounts,
  type FilterGroup,
} from "@/components/filter-rail"

afterEach(cleanup)

/** 12 + 3 + 0 = 15, so 15 is what a rail that summed a group would put on screen. */
const LEVEL_OPTIONS = [
  { value: "breaking", label: "Breaking", count: { kind: "counted", value: 12 } },
  { value: "deprecation", label: "Deprecation", count: { kind: "counted", value: 3 } },
  { value: "warning", label: "Warning", count: { kind: "counted", value: 0 } },
] as const

/**
 * Chosen so no option's own count collides with any sum: the level group totals 15, the range
 * group 44, and the rail 59, and none of those three is a figure any option carries. A fixture
 * where a real count happened to equal a total would make the "computes no total" guard pass
 * for the wrong reason, or fail for one.
 */
const RANGE_OPTIONS = [
  { value: "24h", label: "Last 24 hours", count: { kind: "counted", value: 4 } },
  { value: "7d", label: "Last 7 days", count: { kind: "counted", value: 40 } },
] as const

function levelGroup(overrides: Partial<FilterGroup> = {}): FilterGroup {
  return {
    id: "level",
    legend: "Level",
    options: LEVEL_OPTIONS,
    selected: [],
    onSelect: () => {},
    ...overrides,
  }
}

function rangeGroup(overrides: Partial<FilterGroup> = {}): FilterGroup {
  return {
    id: "range",
    legend: "Time range",
    options: RANGE_OPTIONS,
    selected: [],
    onSelect: () => {},
    ...overrides,
  }
}

function renderRail(overrides: Partial<React.ComponentProps<typeof FilterRail>> = {}) {
  const props = {
    label: "Narrow these runs",
    countScope: "Counted over every run in this repository, not over the rows on this page.",
    groups: [rangeGroup(), levelGroup()] as readonly [FilterGroup, ...FilterGroup[]],
    ...overrides,
  }
  return render(<FilterRail {...props} />)
}

describe("formatFilterCount", () => {
  it("formats a confirmed zero as a figure and an unanswered count as absence", () => {
    expect(formatFilterCount({ kind: "counted", value: 0 })).toBe("0")
    expect(formatFilterCount({ kind: "unanswered", why: "the route timed out" })).toBeNull()
  })

  it("formats a counted figure for a reader rather than as a bare integer", () => {
    expect(formatFilterCount({ kind: "counted", value: 12000 })).toBe(
      (12000).toLocaleString()
    )
  })
})

describe("unansweredCounts", () => {
  it("names every option nobody counted, with the group it sits in and the reason", () => {
    const groups: FilterGroup[] = [
      rangeGroup(),
      levelGroup({
        options: [
          LEVEL_OPTIONS[0],
          {
            value: "abandoned",
            label: "Abandoned",
            count: { kind: "unanswered", why: "the reason-code route was not queried" },
          },
        ],
      }),
    ]

    const unanswered = unansweredCounts(groups)

    expect(unanswered).toEqual([
      {
        legend: "Level",
        label: "Abandoned",
        why: "the reason-code route was not queried",
      },
    ])
  })

  it("counts the unfiltered option too, because it is a count like any other", () => {
    const groups: FilterGroup[] = [
      levelGroup({
        unfiltered: {
          label: "All levels",
          count: { kind: "unanswered", why: "no total was requested for this facet" },
        },
      }),
    ]

    expect(unansweredCounts(groups)).toEqual([
      {
        legend: "Level",
        label: "All levels",
        why: "no total was requested for this facet",
      },
    ])
  })

  it("returns nothing when every count on the rail was answered", () => {
    expect(unansweredCounts([rangeGroup(), levelGroup()])).toEqual([])
  })
})

describe("activeSelections", () => {
  it("reports a selection through the option it names, and nothing for a group at rest", () => {
    const selections = activeSelections([rangeGroup(), levelGroup({ selected: ["warning"] })])

    expect(selections).toEqual([
      { kind: "option", legend: "Level", value: "warning", label: "Warning" },
    ])
  })

  it("reports a selection its group's vocabulary does not hold, rather than dropping it", () => {
    const selections = activeSelections([levelGroup({ selected: ["retracted"] })])

    expect(selections).toEqual([
      { kind: "outside-vocabulary", legend: "Level", value: "retracted" },
    ])
  })
})

describe("FilterRail", () => {
  it("renders one labelled group per definition", () => {
    renderRail()

    const groups = screen.getAllByRole("group")
    expect(groups).toHaveLength(2)
    for (const legend of ["Time range", "Level"]) {
      expect(screen.getByRole("group", { name: new RegExp(legend) })).toBeTruthy()
    }
  })

  it("renders one option per value, each carrying its own count", () => {
    renderRail()

    const level = screen.getByRole("group", { name: /Level/ })
    expect(LEVEL_OPTIONS.length).toBeGreaterThan(0)
    expect(within(level).getAllByRole("button")).toHaveLength(LEVEL_OPTIONS.length)
    for (const option of LEVEL_OPTIONS) {
      const rendered = within(level).getByRole("button", { name: new RegExp(option.label) })
      expect(within(rendered).getByText(String(option.count.value))).toBeTruthy()
    }
  })

  it("shows 0 beside an option whose count is a confirmed zero", () => {
    renderRail()

    const zero = screen.getByRole("button", { name: /Warning/ })
    expect(within(zero).getByText("0")).toBeTruthy()
    expect(within(zero).queryByText(ABSENT)).toBeNull()
  })

  it("shows the absence marker, never 0, beside an option nobody counted", () => {
    renderRail({
      groups: [
        levelGroup({
          options: [
            LEVEL_OPTIONS[0],
            {
              value: "abandoned",
              label: "Abandoned",
              count: { kind: "unanswered", why: "the reason-code route was not queried" },
            },
          ],
        }),
      ],
    })

    const unanswered = screen.getByRole("button", { name: /Abandoned/ })
    expect(within(unanswered).getByText(ABSENT)).toBeTruthy()
    expect(within(unanswered).queryByText("0")).toBeNull()
  })

  it("keeps an option counted at zero selectable rather than disabling or hiding it", () => {
    const onSelect = vi.fn()
    renderRail({ groups: [levelGroup({ onSelect })] })

    const zero = screen.getByRole("button", { name: /Warning/ })
    expect(zero.hasAttribute("disabled")).toBe(false)
    expect(zero.getAttribute("aria-disabled")).toBeNull()

    fireEvent.click(zero)

    expect(onSelect).toHaveBeenCalledWith("warning")
  })

  it("reports the option an operator picked rather than selecting it itself", () => {
    const onSelect = vi.fn()
    renderRail({ groups: [levelGroup({ onSelect })] })

    fireEvent.click(screen.getByRole("button", { name: /Deprecation/ }))

    expect(onSelect).toHaveBeenCalledWith("deprecation")
    expect(
      screen.getByRole("button", { name: /Deprecation/ }).getAttribute("aria-pressed")
    ).toBe("false")
  })

  it("sends the value itself when an option is picked, pressed or not", () => {
    // The contract moved with M15 Task 4: a press is a *toggle* of one value rather than a
    // replacement of the selection, so the rail names the value and the caller owns membership.
    // A rail that still sent `null` for a pressed option would clear the whole facet when a
    // reader meant to remove one of the three integrations they had chosen.
    const onSelect = vi.fn()
    renderRail({ groups: [levelGroup({ selected: ["deprecation"], onSelect })] })

    fireEvent.click(screen.getByRole("button", { name: /Deprecation/ }))

    expect(onSelect).toHaveBeenCalledWith("deprecation")
  })

  it("clears the whole facet only from the unfiltered option", () => {
    const onSelect = vi.fn()
    renderRail({
      groups: [
        levelGroup({
          selected: ["deprecation", "warning"],
          onSelect,
          unfiltered: { label: "Every level", count: { kind: "counted", value: 44 } },
        }),
      ],
    })

    fireEvent.click(screen.getByRole("button", { name: /Every level/ }))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it("marks exactly one option pressed inside a group that has a selection", () => {
    renderRail({ groups: [levelGroup({ selected: ["warning"] })] })

    const group = screen.getByRole("group", { name: /Level/ })
    const buttons = within(group).getAllByRole("button")
    expect(buttons.length).toBeGreaterThan(0)
    const pressed = buttons.filter((b) => b.getAttribute("aria-pressed") === "true")
    expect(pressed).toHaveLength(1)
    expect(pressed[0].textContent).toContain("Warning")
  })

  it("computes no total across a group's options and none across the rail", () => {
    renderRail()

    const rail = screen.getByRole("complementary", { name: /Narrow these runs/ })
    expect(within(rail).getAllByRole("button").length).toBeGreaterThan(0)
    for (const total of ["15", "44", "59"]) {
      expect(within(rail).queryByText(total)).toBeNull()
    }
  })

  it("renders the unfiltered option only when the caller supplied a count for it", () => {
    renderRail({ groups: [levelGroup()] })
    expect(screen.queryByRole("button", { name: /All levels/ })).toBeNull()
    cleanup()

    renderRail({
      groups: [
        levelGroup({
          unfiltered: { label: "All levels", count: { kind: "counted", value: 15 } },
        }),
      ],
    })
    const all = screen.getByRole("button", { name: /All levels/ })
    expect(within(all).getByText("15")).toBeTruthy()
  })

  it("clears the group when the unfiltered option is picked", () => {
    const onSelect = vi.fn()
    renderRail({
      groups: [
        levelGroup({
          selected: ["warning"],
          onSelect,
          unfiltered: { label: "All levels", count: { kind: "counted", value: 15 } },
        }),
      ],
    })

    fireEvent.click(screen.getByRole("button", { name: /All levels/ }))

    expect(onSelect).toHaveBeenCalledWith(null)
  })

  it("says why a count went unanswered rather than leaving the marker unexplained", () => {
    renderRail({
      groups: [
        levelGroup({
          options: [
            LEVEL_OPTIONS[0],
            {
              value: "abandoned",
              label: "Abandoned",
              count: { kind: "unanswered", why: "the reason-code route was not queried" },
            },
          ],
        }),
      ],
    })

    const reasons = screen.getAllByText(/the reason-code route was not queried/)
    expect(reasons.length).toBeGreaterThan(0)
  })

  it("states what the counts are counted over", () => {
    renderRail()

    expect(
      screen.getByText(/Counted over every run in this repository, not over the rows on this page\./)
    ).toBeTruthy()
  })

  it("says so when a group is narrowed by a value its own vocabulary does not hold", () => {
    renderRail({ groups: [levelGroup({ selected: ["retracted"] })] })

    const group = screen.getByRole("group", { name: /Level/ })
    expect(within(group).getAllByRole("button").filter((b) => b.getAttribute("aria-pressed") === "true")).toHaveLength(0)
    expect(screen.getByText(/retracted/)).toBeTruthy()
  })
})

describe("multi-select and per-facet search (M15 Task 4)", () => {
  const MANY = Array.from({ length: 12 }, (_, index) => ({
    value: `vendor-${index}`,
    label: `Vendor ${index}`,
    count: { kind: "counted" as const, value: index },
  })) as unknown as FilterGroup["options"]

  it("presses every value the caller holds, not just one", () => {
    // The claim multi-select is for. A rail that pressed only the first would look like a
    // single-select rail over a table narrowed by two, and nothing on screen would say so.
    renderRail({ groups: [levelGroup({ selected: ["deprecation", "warning"] })] })

    const group = screen.getByRole("group", { name: /Level/ })
    const pressed = within(group)
      .getAllByRole("button")
      .filter((button) => button.getAttribute("aria-pressed") === "true")

    expect(pressed).toHaveLength(2)
  })

  it("offers no search box for a facet a reader can simply read", () => {
    // A search box over four options costs a decision and returns nothing.
    renderRail({ groups: [levelGroup()] })

    expect(screen.queryByRole("searchbox")).toBeNull()
  })

  it("offers a search box once a facet outgrows the threshold", () => {
    renderRail({ groups: [levelGroup({ options: MANY })] })

    expect(screen.getByRole("searchbox", { name: /Search level/i })).toBeTruthy()
  })

  it("narrows the options to the term, on the value as well as the label", () => {
    renderRail({ groups: [levelGroup({ options: MANY })] })

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "vendor-1" } })

    const group = screen.getByRole("group", { name: /Level/ })
    const labels = within(group)
      .getAllByRole("button")
      .map((button) => button.textContent)
    // A substring match, so vendor-1 brings vendor-10 and vendor-11 with it -- three of twelve.
    // Prefix-only matching would be the wrong rule here: a reader searching an operation facet
    // types a fragment they remember from the middle of a name at least as often as the start.
    expect(labels.filter((label) => label?.includes("Vendor")).length).toBe(3)
  })

  it("keeps a chosen option visible however the term is narrowed", () => {
    // Otherwise typing hides an option that is currently narrowing the table, and the only
    // control that would clear it is the one that just disappeared.
    renderRail({ groups: [levelGroup({ options: MANY, selected: ["vendor-7"] })] })

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "vendor-2" } })

    expect(screen.getByRole("button", { name: /Vendor 7/ }).getAttribute("aria-pressed")).toBe(
      "true",
    )
  })

  it("says the facet is not empty when a term matches none of it", () => {
    renderRail({ groups: [levelGroup({ options: MANY })] })

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } })

    // The distinction the console exists for: no value *matches*, against no value existing.
    expect(screen.getByText(/No value in this facet matches/)).toBeTruthy()
    expect(screen.getByText(/The facet holds 12/)).toBeTruthy()
  })

  it("reports every selection a facet's vocabulary does not hold", () => {
    // A stale URL carrying two retired values must report both. Reporting one would leave a
    // table narrowed by something with nothing on screen accounting for it.
    const selections = activeSelections([
      levelGroup({ selected: ["retracted", "rescinded"] }),
    ])

    expect(selections.filter((s) => s.kind === "outside-vocabulary")).toHaveLength(2)
  })
})

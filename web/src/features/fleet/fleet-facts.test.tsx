/**
 * A fact tile must never render an empty value, and this is the guard for the first caller that
 * had to honour it.
 *
 * `components/fact-tile.tsx` states the rule and the reason: "A dash would collapse 'zero', 'not
 * measured' and 'this view cannot see it' onto one glyph, and distinguishing those is the product's
 * argument." The rail has four tiles and five queries behind them, so there are three states per
 * tile and no compiler anywhere checks that all three say something.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation, never class names
 * and never a snapshot. What is asserted is which *kind* of thing is on screen — a skeleton, an
 * absence marker, or a figure — not how any of them looks.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FleetFacts } from "@/features/fleet/fleet-facts"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

vi.mock("@/api/queries", () => ({
  useOverview: () => mockState.overview,
  useRuns: () => mockState.runs,
  useRepositories: () => mockState.repositories,
  useDetectors: () => mockState.detectors,
  useCorpus: () => mockState.corpus,
}))

/** The five query results the rail reads, swapped per test rather than through a live client. */
const mockState: Record<string, unknown> = {}

function pending() {
  return { isPending: true, isError: false, isSuccess: false, data: undefined }
}

function failed() {
  return { isPending: false, isError: true, isSuccess: false, data: undefined, error: new Error("no") }
}

function settled(data: unknown) {
  return { isPending: false, isError: false, isSuccess: true, data }
}

const OVERVIEW = { total_findings: 42, total_findings_bound_reached: false, total_findings_bound: 1000 }
const BOUNDED = { total_findings: 1000, total_findings_bound_reached: true, total_findings_bound: 1000 }

function setAll(make: () => unknown) {
  mockState.overview = make()
  mockState.runs = make()
  mockState.repositories = make()
  mockState.detectors = make()
  mockState.corpus = make()
}

function renderRail() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <FleetFacts />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** Every tile's value, by the label above it. */
function tileValues(container: HTMLElement): string[] {
  return [...container.querySelectorAll(".furniture")].map((label) => {
    const value = label.nextElementSibling
    return value === null ? "" : value.textContent?.trim() ?? ""
  })
}

describe("a tile never renders an empty value", () => {
  it("renders a skeleton, not a blank, while a count is in flight", () => {
    setAll(pending)
    const { container } = renderRail()

    // Four tiles, four skeletons: the value has not arrived and the tile says nothing rather than
    // showing an empty box that reads as "zero".
    expect(container.querySelectorAll('[role="presentation"]')).toHaveLength(4)
    expect(tileValues(container).every((v) => v === "")).toBe(true)
  })

  it("renders the absence marker, not a blank, when the query failed", () => {
    setAll(failed)
    const { container } = renderRail()

    expect(container.querySelectorAll('[role="presentation"]')).toHaveLength(0)
    // The marker is `components/status.tsx`'s one absence glyph, and it says which nothing it is.
    for (const value of tileValues(container)) {
      expect(value).toContain("the API did not answer")
    }
  })

  it("renders the count once it lands", () => {
    mockState.overview = settled({ ...OVERVIEW, vendors: [] })
    mockState.runs = settled({ total: 7, items: [], next_offset: null })
    mockState.repositories = settled({ repo_ids: ["a", "b"] })
    mockState.detectors = settled({ detectors: [{ detector: "d", total: 1, by_rung: {} }] })
    mockState.corpus = settled({ attempts: 3 })

    const { container } = renderRail()

    expect(container.querySelectorAll('[role="presentation"]')).toHaveLength(0)
    expect(screen.getByText("42")).toBeTruthy()
    expect(screen.getByText("7")).toBeTruthy()
    expect(screen.getByText("2")).toBeTruthy()
    expect(screen.getByText("3")).toBeTruthy()
  })
})

describe("a bounded count is never rendered as if it were exact", () => {
  it("carries the + glyph and says in words what it means", () => {
    mockState.overview = settled({ ...BOUNDED, vendors: [] })
    mockState.runs = settled({ total: 0, items: [], next_offset: null })
    mockState.repositories = settled({ repo_ids: [] })
    mockState.detectors = settled({ detectors: [] })
    mockState.corpus = settled({ attempts: 0 })

    renderRail()

    // `cardinality.tsx` requires the glyph never be the only channel, on the same grounds a status
    // colour never travels without a word. Both, or the tile is claiming a completeness it lacks.
    expect(screen.getByText("1,000+")).toBeTruthy()
    expect(screen.getByText(/counting stopped at 1,000/)).toBeTruthy()
  })

  it("shows the plain number when the count did not stop early", () => {
    mockState.overview = settled({ ...OVERVIEW, vendors: [] })
    mockState.runs = settled({ total: 0, items: [], next_offset: null })
    mockState.repositories = settled({ repo_ids: [] })
    mockState.detectors = settled({ detectors: [] })
    mockState.corpus = settled({ attempts: 0 })

    renderRail()

    expect(screen.getByText("42")).toBeTruthy()
    expect(screen.queryByText(/counting stopped/)).toBeNull()
  })

  it("distinguishes a zero that was counted from a count that has not arrived", () => {
    // The whole reason the three states are separate. A tile showing "0" asserts the graph holds
    // none; a tile showing a skeleton asserts nothing at all. Collapsing them is the defect
    // `states.tsx` and `fact-tile.tsx` both exist to prevent.
    mockState.overview = settled({ total_findings: 0, total_findings_bound_reached: false, total_findings_bound: 1000, vendors: [] })
    mockState.runs = pending()
    mockState.repositories = settled({ repo_ids: [] })
    mockState.detectors = settled({ detectors: [] })
    mockState.corpus = settled({ attempts: 0 })

    const { container } = renderRail()

    expect(screen.getAllByText("0").length).toBeGreaterThan(0)
    expect(container.querySelectorAll('[role="presentation"]')).toHaveLength(1)
  })
})

describe("the open-findings tile against a graph that has never been indexed", () => {
  /**
   * A design partner`s first five minutes are this state: configured, nothing indexed, every
   * table empty. `0 open findings across every vendor, every repository` is then a measured-
   * sounding clean bill of health for code nobody has read, which is absence rendered as zero on
   * the exact axis this console argues about. The count is true; the note has to stop implying
   * a search happened.
   */
  it("says nothing has been indexed rather than implying a search found nothing", () => {
    setAll(() => settled({}))
    mockState.overview = settled({ ...OVERVIEW, total_findings: 0 })
    mockState.repositories = settled({ repo_ids: [] })
    mockState.runs = settled({ items: [], total: 0 })
    mockState.detectors = settled({ detectors: [] })
    mockState.corpus = settled({ attempts: 0, distinct_findings: 0 })

    const { container } = renderRail()
    const text = container.textContent ?? ""

    expect(text).toContain("No repository has been indexed")
    expect(text).not.toContain("Across every vendor, every repository.")
  })

  it("keeps the ordinary scope note once something has been indexed", () => {
    setAll(() => settled({}))
    mockState.overview = settled({ ...OVERVIEW, total_findings: 0 })
    mockState.repositories = settled({ repo_ids: ["org/repo"] })
    mockState.runs = settled({ items: [], total: 0 })
    mockState.detectors = settled({ detectors: [] })
    mockState.corpus = settled({ attempts: 0, distinct_findings: 0 })

    const { container } = renderRail()
    const text = container.textContent ?? ""

    expect(text).toContain("Across every vendor, every repository.")
    expect(text).not.toContain("No repository has been indexed")
  })
})

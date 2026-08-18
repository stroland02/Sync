import { describe, expect, it } from "vitest"

import { cardFacts, matchesFilter } from "@/features/fleet/codebase-cards"
import type { OverviewResponse } from "@/api/types"

const overview = (over: Partial<OverviewResponse>): OverviewResponse => ({
  repo_id: "org/repo",
  vendors: [],
  total_findings: 0,
  total_findings_bound: 0,
  total_findings_bound_reached: true,
  severity_counts: {},
  bindings_by_rung: { static: 0, resolved: 0, observed: 0, unresolved: 0, unattributed: 0 },
  last_index_run: null,
  indexed_at: null,
  feed_fetched_at: null,
  binding_source: null,
  context_savings: 0,
  context_savings_bound_reached: true,
  ...over,
})

describe("cardFacts", () => {
  it("holds openFindings null until the scoped answer arrives", () => {
    expect(cardFacts("org/repo", undefined).openFindings).toBeNull()
  })

  it("refuses an answer computed for a different scope", () => {
    const other = overview({ repo_id: "org/other", total_findings: 7 })
    expect(cardFacts("org/repo", other).openFindings).toBeNull()
  })

  it("carries the scoped count and vendor ids", () => {
    const scoped = overview({
      total_findings: 3,
      vendors: [{ vendor_id: "stripe", open_finding_count: 3 }],
    })
    const facts = cardFacts("org/repo", scoped)
    expect(facts.openFindings).toBe(3)
    expect(facts.vendors).toEqual(["stripe"])
  })
})

describe("matchesFilter", () => {
  const facts = (openFindings: number | null) => ({ repoId: "r", openFindings, vendors: [] })

  it("NEEDS_REVIEW takes only repos with a positive scoped count", () => {
    expect(matchesFilter(facts(2), "NEEDS_REVIEW")).toBe(true)
    expect(matchesFilter(facts(0), "NEEDS_REVIEW")).toBe(false)
    expect(matchesFilter(facts(null), "NEEDS_REVIEW")).toBe(false)
  })

  it("CLEAN takes only a confirmed zero — an unanswered scope is neither clean nor dirty", () => {
    expect(matchesFilter(facts(0), "CLEAN")).toBe(true)
    expect(matchesFilter(facts(null), "CLEAN")).toBe(false)
  })

  it("ALL takes everything", () => {
    expect(matchesFilter(facts(null), "ALL")).toBe(true)
  })
})

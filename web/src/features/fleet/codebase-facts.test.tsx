/**
 * The codebase fact band: what is true about one codebase, stated as facts that do not average.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s — classification, derivation and structural
 * invariants. Never a class name, never a snapshot. The refusals are asserted structurally
 * because they are the product's argument rather than a style: a tile that averaged the others
 * would be the composite health figure this console exists to replace, and nothing but a test
 * stops one arriving under deadline.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NotFoundError, UnreachableApiError } from "@/api/errors"
import type {
  ChangeUnitRow,
  ChangeUnitsPage,
  DetectorAccountabilityResponse,
} from "@/api/types"

const {
  useChangeUnits,
  useDetectors,
  useOverview,
  useRepositories,
  useRepositoryCoverage,
} = vi.hoisted(() => ({
  useChangeUnits: vi.fn(),
  useDetectors: vi.fn(),
  useOverview: vi.fn(),
  useRepositories: vi.fn(),
  useRepositoryCoverage: vi.fn(),
}))

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useChangeUnits,
  useDetectors,
  useOverview,
  useRepositories,
  useRepositoryCoverage,
}))

import {
  CodebaseFacts,
  describeCoverageAbsence,
  newestCheckpoint,
  newestIndexedAt,
  resolveCodebaseScope,
  rungTally,
} from "@/features/fleet/codebase-facts"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const settled = <T,>(data: T) => ({ isPending: false, isError: false, isSuccess: true, data, error: null })
const failed = (error: unknown) => ({ isPending: false, isError: true, isSuccess: false, data: undefined, error })
const pending = () => ({ isPending: true, isError: false, isSuccess: false, data: undefined, error: null })

function unit(overrides: Partial<ChangeUnitRow> = {}): ChangeUnitRow {
  return {
    change_unit_id: "cu-1",
    finding_count: 1,
    findings: [],
    vendor_id: "stripe",
    operation_id: "PostCharges",
    change_kind: "breaking",
    from_version: null,
    to_version: null,
    severity: "high",
    repository_count: 1,
    call_site_count: 2,
    binding_rung: "static",
    finding_ids: ["f-1"],
    repo_ids: ["org/one"],
    standing: null,
    last_checkpoint_at: null,
    ...overrides,
  }
}

function unitsPage(items: ChangeUnitRow[], total = items.length): ChangeUnitsPage {
  return { items, total, next_offset: null }
}

function detectorsPayload(rows: DetectorAccountabilityResponse["detectors"]): DetectorAccountabilityResponse {
  return {
    repo_id: "org/one",
    detectors: rows,
    // Folded from the rows rather than written flat, so a fixture cannot claim a scope-wide
    // rung tally its own detectors do not support.
    by_rung: rows.reduce<Record<string, number>>((tally, row) => {
      for (const [rung, count] of Object.entries(row.by_rung)) {
        tally[rung] = (tally[rung] ?? 0) + count
      }
      return tally
    }, {}),
    total_open_findings: rows.reduce((sum, row) => sum + row.total, 0),
  }
}

// ---------------------------------------------------------------------------------------------
// Which codebase the screen is about
// ---------------------------------------------------------------------------------------------

describe("resolveCodebaseScope", () => {
  it("reads the codebase from the address when one is named", () => {
    expect(resolveCodebaseScope("org/one", ["org/one", "org/two"])).toEqual({
      kind: "selected",
      repoId: "org/one",
    })
  })

  it("takes the only indexed repository as the codebase, because there is nothing else it could be", () => {
    expect(resolveCodebaseScope(null, ["org/only"])).toEqual({ kind: "only", repoId: "org/only" })
  })

  it("refuses to pick a codebase when several exist and the address names none", () => {
    expect(resolveCodebaseScope(null, ["org/one", "org/two", "org/three"])).toEqual({
      kind: "unselected",
      available: 3,
    })
  })

  it("says the index holds no repository rather than naming one", () => {
    expect(resolveCodebaseScope(null, [])).toEqual({ kind: "none" })
  })

  it("waits rather than guessing while the repository list is still in flight", () => {
    expect(resolveCodebaseScope(null, undefined)).toEqual({ kind: "pending" })
  })

  it("flags an address naming a repository the index has never seen, because every figure under it would be a zero nobody measured", () => {
    expect(resolveCodebaseScope("org/ghost", ["org/one"])).toEqual({
      kind: "unknown",
      repoId: "org/ghost",
    })
  })

  it("trusts an address while the repository list is in flight, so the facts do not wait on a check that has not answered", () => {
    expect(resolveCodebaseScope("org/one", undefined)).toEqual({
      kind: "selected",
      repoId: "org/one",
    })
  })
})

// ---------------------------------------------------------------------------------------------
// The derivations behind three tiles
// ---------------------------------------------------------------------------------------------

describe("newestIndexedAt", () => {
  it("reports the newest indexed time across every vendor", () => {
    expect(
      newestIndexedAt({
        stripe: "2026-08-01T10:00:00Z",
        twilio: "2026-08-14T09:30:00Z",
        sendgrid: "2026-07-02T00:00:00Z",
      })
    ).toBe("2026-08-14T09:30:00Z")
  })

  it("reports absence rather than a time when no vendor has an indexed call site", () => {
    expect(newestIndexedAt({})).toBeNull()
  })

  it("reports absence when the coverage answer has not arrived", () => {
    expect(newestIndexedAt(undefined)).toBeNull()
  })
})

describe("rungTally", () => {
  it("sums each rung across every detector and keeps the declared rung order", () => {
    const tally = rungTally(
      detectorsPayload([
        { detector: "breaking-change", total: 4, by_rung: { observed: 1, static: 3 }, by_claim: {}, by_severity: {} },
        { detector: "deprecation", total: 3, by_rung: { static: 2, resolved: 1 }, by_claim: {}, by_severity: {} },
      ])
    )

    expect(tally.length).toBeGreaterThan(0)
    expect(tally).toEqual([
      { rung: "static", count: 5 },
      { rung: "resolved", count: 1 },
      { rung: "observed", count: 1 },
    ])
  })

  it("carries a rung the console's vocabulary does not declare rather than dropping it silently", () => {
    const tally = rungTally(
      detectorsPayload([
        { detector: "drift", total: 2, by_rung: { static: 1, telepathic: 1 }, by_claim: {}, by_severity: {} },
      ])
    )

    expect(tally.length).toBeGreaterThan(0)
    expect(tally).toContainEqual({ rung: "telepathic", count: 1 })
  })

  it("reports nothing to attribute when no detector holds an open finding", () => {
    expect(rungTally(detectorsPayload([]))).toEqual([])
  })
})

describe("newestCheckpoint", () => {
  it("picks the newest checkpoint and the standing recorded beside it", () => {
    const page = unitsPage([
      unit({ change_unit_id: "cu-old", standing: "opened", last_checkpoint_at: "2026-08-10T00:00:00Z" }),
      unit({ change_unit_id: "cu-new", standing: "abandoned", last_checkpoint_at: "2026-08-16T00:00:00Z" }),
      unit({ change_unit_id: "cu-null" }),
    ])

    expect(newestCheckpoint(page)).toEqual({
      at: "2026-08-16T00:00:00Z",
      standing: "abandoned",
      complete: true,
    })
  })

  it("says the answer did not cover every change unit when the route paged", () => {
    const page = unitsPage(
      [unit({ standing: "reported", last_checkpoint_at: "2026-08-16T00:00:00Z" })],
      9
    )

    expect(newestCheckpoint(page)?.complete).toBe(false)
  })

  it("reports absence when no change unit carries a checkpoint, because that is two facts the payload cannot separate", () => {
    expect(newestCheckpoint(unitsPage([unit(), unit({ change_unit_id: "cu-2" })]))).toBeNull()
  })

  it("reports absence when the change-unit answer has not arrived", () => {
    expect(newestCheckpoint(undefined)).toBeNull()
  })
})

describe("describeCoverageAbsence", () => {
  it("names the routing defect when a repository id carrying a slash is answered with 404", () => {
    const reason = describeCoverageAbsence(
      "github.com/org/one",
      new NotFoundError("not found", "/api/repositories/x/coverage", "/api/repositories/x/coverage")
    )

    expect(reason).toContain("B147")
    expect(reason).toContain("slash")
  })

  it("does not blame the routing defect for a repository id with no slash in it", () => {
    const reason = describeCoverageAbsence(
      "seed-repo-a",
      new NotFoundError("not found", "seed-repo-a", "/api/repositories/seed-repo-a/coverage")
    )

    expect(reason).not.toContain("B147")
  })

  it("does not blame the routing defect when the API never answered at all", () => {
    const reason = describeCoverageAbsence(
      "github.com/org/one",
      new UnreachableApiError("/api/repositories/github.com%2Forg%2Fone/coverage")
    )

    expect(reason).not.toContain("B147")
  })
})

// ---------------------------------------------------------------------------------------------
// The band itself
// ---------------------------------------------------------------------------------------------

const LABELS = [
  "Last indexed",
  "Call sites indexed",
  "Vendors detected",
  "Open findings",
  "Open findings by rung",
  "Last run",
]

function settleEverything() {
  useRepositoryCoverage.mockReturnValue(
    settled({
      repo_id: "org/one",
      by_vendor: { stripe: 4, twilio: 2 },
      last_indexed: { stripe: "2026-08-14T09:30:00Z", twilio: "2026-08-01T10:00:00Z" },
      total_call_sites: 6,
    })
  )
  useOverview.mockReturnValue(
    settled({
      repo_id: "org/one",
      vendors: [{ vendor_id: "stripe", open_finding_count: 3 }],
      total_findings: 3,
      total_findings_bound: 1000,
      total_findings_bound_reached: false,
      severity_counts: { high: 3 },
      indexed_at: null,
      feed_fetched_at: null,
      binding_source: null,
      context_savings: 0,
    })
  )
  useDetectors.mockReturnValue(
    settled(
      detectorsPayload([
        { detector: "breaking-change", total: 3, by_rung: { static: 2, observed: 1 }, by_claim: {}, by_severity: {} },
      ])
    )
  )
  useChangeUnits.mockReturnValue(
    settled(unitsPage([unit({ standing: "abandoned", last_checkpoint_at: "2026-08-16T00:00:00Z" })]))
  )
  useRepositories.mockReturnValue(settled({ repo_ids: ["org/one"] }))
}

function tileFor(container: HTMLElement, label: string): HTMLElement {
  const heading = within(container).getByText(label)
  const tile = heading.parentElement
  expect(tile).not.toBeNull()
  return tile as HTMLElement
}

/**
 * A tile's value alone, read off the element rather than out of the tile's whole text.
 *
 * `textContent` concatenates a label, a value and a note with no separator, so a substring test
 * over the tile cannot tell a rendered `0` from the `0` inside a sentence — and a regex with `\b`
 * cannot see a boundary that concatenation removed. `fact-tile.tsx` renders label, value and note
 * as three children in that order, so the value is `children[1]` and asking for it directly is
 * what makes "a zero is not an absence" assertable at all.
 */
function valueOf(container: HTMLElement, label: string): string {
  const tile = tileFor(container, label)
  expect(tile.children.length).toBeGreaterThanOrEqual(2)
  return tile.children[1].textContent ?? ""
}

describe("the codebase fact band", () => {
  it("states six labelled facts about the selected codebase", () => {
    settleEverything()
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    expect(LABELS.length).toBe(6)
    for (const label of LABELS) {
      expect(within(container).getByText(label)).not.toBeNull()
    }
    expect(within(container).getByText("org/one")).not.toBeNull()
  })

  it("renders every figure the payload actually carries", () => {
    settleEverything()
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    expect(valueOf(container, "Call sites indexed")).toBe("6")
    expect(valueOf(container, "Vendors detected")).toBe("2")
    expect(valueOf(container, "Open findings")).toBe("3")
    expect(valueOf(container, "Last run")).toBe("abandoned")
  })

  it("renders a confirmed zero as a number, and never as the absence marker", () => {
    settleEverything()
    useRepositoryCoverage.mockReturnValue(
      settled({ repo_id: "org/one", by_vendor: {}, last_indexed: {}, total_call_sites: 0 })
    )
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    expect(valueOf(container, "Call sites indexed")).toBe("0")
    expect(valueOf(container, "Vendors detected")).toBe("0")
  })

  it("renders an unanswered coverage query as the absence marker naming why, never as a zero", () => {
    settleEverything()
    useRepositoryCoverage.mockReturnValue(
      failed(new NotFoundError("not found", "x", "/api/repositories/x/coverage"))
    )
    const { container } = render(
      <CodebaseFacts repoId="github.com/org/one" scopeNote="Selected codebase." />
    )

    const coverageFed = ["Last indexed", "Call sites indexed", "Vendors detected"]
    expect(coverageFed.length).toBe(3)
    for (const label of coverageFed) {
      const value = valueOf(container, label)
      expect(value).toContain("—")
      // The three tiles the coverage route feeds must not fall back to zero. Absence and zero
      // are the distinction this console exists to keep apart, and a `?? 0` is how it is lost.
      expect(value).not.toBe("0")
      expect(value).toContain("B147")
    }
  })

  it("says nothing at all while a query is in flight, rather than saying zero", () => {
    settleEverything()
    useOverview.mockReturnValue(pending())
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    // A skeleton carries no text: it says nothing on purpose. A zero or an absence marker here
    // would each claim a settled answer the query has not given.
    expect(valueOf(container, "Open findings")).toBe("")
  })

  it("separates never-measured from nothing-here on the last run, because the payload cannot", () => {
    settleEverything()
    useChangeUnits.mockReturnValue(settled(unitsPage([unit()])))
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    const value = valueOf(container, "Last run")
    expect(value).toContain("—")
    expect(value).toContain("no run has ever been attempted")
    expect(value).toContain("no checkpointer")
  })

  it("renders the rung as the class of evidence behind a finding, never a score", () => {
    settleEverything()
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    const tile = tileFor(container, "Open findings by rung")
    expect(tile.textContent).toContain("static")
    expect(tile.textContent).toContain("observed")
    // The refusal, said on screen rather than only in a docstring.
    expect(tile.textContent).toContain("never a score")
    // Nothing here may be a confidence figure: no percentage, no "N out of ten", no /10.
    expect(tile.textContent).not.toMatch(/\d\s*%/)
    expect(tile.textContent).not.toMatch(/\b\d+\s*\/\s*10\b/)
  })

  it("carries no composite figure, no health tile and no status light over the facts", () => {
    settleEverything()
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    // `textContent` concatenates adjacent elements with no separator, so `\b` cannot be relied
    // on here — "StatusHealthyEvery gate is green" has no word boundary around "Healthy" at all,
    // and a guard written with one passes while the refused tile is on screen. Measured while
    // proving this test red against a deliberately added `STATUS — Healthy` tile.
    const text = container.textContent ?? ""
    // A tile that averaged the others is the failure this console exists to replace. Every one
    // of these words has arrived on a reference screen carrying exactly that claim.
    for (const refused of [/healthy/i, /health score/i, /operational/i, /degraded/i, /uptime/i]) {
      expect(text).not.toMatch(refused)
    }
    // No liveness pulse and no traffic light: nothing in this band claims a run is alive.
    expect(container.querySelectorAll("[class*='animate-']").length).toBe(0)
  })

  it("says the newest checkpoint is staleness rather than liveness, because nothing here can tell a parked run from a dead one", () => {
    settleEverything()
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    expect(tileFor(container, "Last run").textContent).toContain("staleness, not liveness")
  })

  it("says the answer was read over one page when the change-unit route paged", () => {
    settleEverything()
    useChangeUnits.mockReturnValue(
      settled(unitsPage([unit({ standing: "opened", last_checkpoint_at: "2026-08-16T00:00:00Z" })], 40))
    )
    const { container } = render(<CodebaseFacts repoId="org/one" scopeNote="Selected codebase." />)

    expect(tileFor(container, "Last run").textContent).toContain("not across every change unit")
  })

  it("carries the scope note it was given, so a reader knows how this codebase was chosen", () => {
    settleEverything()
    render(<CodebaseFacts repoId="org/one" scopeNote="The only repository the index holds." />)

    expect(screen.getByText("The only repository the index holds.")).not.toBeNull()
  })
})

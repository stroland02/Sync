/**
 * The overview: pick a repository, and see the four fleet counts while you do.
 *
 * This screen carried a page-level "Review proposed patch" action, a fleet-wide change-unit table,
 * five repository cards and a three-panel contextual band. The owner's instruction was a simpler
 * landing page built around the list of repositories, so what is asserted here is the shape that
 * survived and — more importantly — the protected sentences that had to survive with it.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: structure and classification, never class names
 * and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FleetPage } from "@/features/fleet/fleet-page"
import type { OverviewResponse } from "@/api/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositories: () => settled({ repo_ids: ["org/one", "org/two"] }),
  useOverview: () =>
    settled({ vendors: [{ vendor_id: "stripe" }], total_findings: 3, total_findings_bound: 1000 }),
  useRuns: () => settled({ items: [], total: 0 }),
  useDetectors: () => settled({ detectors: [] }),
  useCorpus: () => settled({ attempts: 0, distinct_findings: 0 }),
  useRepositoryCoverage: () =>
    settled({ repo_id: "org/one", by_vendor: { stripe: 4 }, last_indexed: {}, total_call_sites: 4 }),
  useChangeUnits: () => settled({ items: [], total: 0, next_offset: null }),
}))

const { fetchOverview } = vi.hoisted(() => ({ fetchOverview: vi.fn() }))
vi.mock("@/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/client")>()),
  fetchOverview,
}))

function renderOverview(entry = "/") {
  fetchOverview.mockImplementation(({ repoId }: { repoId?: string }) =>
    Promise.resolve({ repo_id: repoId ?? null, vendors: [], total_findings: 0 } as unknown as OverviewResponse)
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <FleetPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the overview screen", () => {
  it("is called Overview, so one destination has one name", () => {
    renderOverview()

    // It was titled "Repositories", labelled "Codebases" in the registry, and sits at the "Fleet"
    // level. Three names for one destination is the confusion this rename removes. The *level*
    // stays "Fleet" — that is the specification's word and `test_console_hierarchy.py` holds it.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Overview")
  })

  it("leads with one row per repository, rather than a card each", () => {
    const { container } = renderOverview()

    const rows = container.querySelectorAll("tbody tr")
    expect(rows.length).toBe(2)
    expect(within(rows[0] as HTMLElement).getByText("org/one")).not.toBeNull()
  })

  it("carries no page-level review action, because that belongs to a change unit", () => {
    renderOverview()

    // The action pointed at whichever run happened to be newest with an opened pull request, which
    // reads as "the" patch when there are nine change units. It belongs on the row it acts on.
    expect(screen.queryByRole("link", { name: /review proposed patch/i })).toBeNull()
  })

  it("keeps every protected sentence that qualifies what is on screen", () => {
    const { container } = renderOverview()
    const text = container.textContent ?? ""

    expect(text).toContain("A checkpoint age is staleness, not liveness")
    expect(text).toContain("absence is not zero")
    expect(text).toContain("counts once toward the corpus grain")
    expect(text).toContain("There is no composite health figure here on purpose")
  })

  it("puts the limits panel beside the health-refusal tile, because a protected sentence says it is there", () => {
    const { container } = renderOverview()

    // The health-refusal sentence ends "the panel beside them names what none of these figures can
    // tell you at all". W362 collapsed a three-column band to one column and left both panels
    // stacked inside a single wrapper, which made that clause false while the sentence still read
    // as true. Asserting the text alone could not catch it — that is what this guard adds.
    const section = container.querySelector("section")
    expect(section).not.toBeNull()

    const band = Array.from(section!.children).find(
      (child) =>
        child.textContent?.includes("There is no composite health figure here on purpose") &&
        child.textContent?.includes("What this screen cannot tell you")
    )
    expect(band).toBeDefined()

    // Two children of the band, not one wrapper holding a stack. jsdom has no layout, so the
    // arrangement itself is measured in Chrome; what is held here is the structural precondition
    // without which "beside" cannot be true at any viewport.
    expect(band!.childElementCount).toBe(2)
  })

  it("leads with the codebase fact band, because the Overview is a dashboard for one codebase", () => {
    const { container } = renderOverview("/?repo_id=org%2Fone")

    const band = container.querySelector("[aria-label='Codebase facts']")
    expect(band).not.toBeNull()
    expect(band?.textContent).toContain("org/one")

    // The band is above the repository list. The list is still on this screen — removing it is the
    // owner's ruling and is sequenced after the specification amendment — but the codebase this
    // screen is about comes first, not the directory of codebases it was chosen from.
    const table = container.querySelector("table")
    expect(table).not.toBeNull()
    expect(
      band!.compareDocumentPosition(table!) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeGreaterThan(0)
  })

  it("names no codebase, and states no figure, when the address selects none", () => {
    const { container } = renderOverview()

    const band = container.querySelector("[aria-label='Codebase facts']")
    expect(band).not.toBeNull()
    // Two repositories are indexed and the address names neither. Picking one would be the console
    // deciding what the operator is looking at, and rendering fleet-wide figures under a
    // codebase's name would be a false claim about that codebase.
    expect(band?.textContent).toContain("No codebase is selected")
    expect(band?.textContent).not.toContain("Call sites indexed")
  })

  it("still says the repository list is the thing absence is measured against", () => {
    const { container } = renderOverview()

    // The absence footnote points at "the repository list below". The list stays on this screen, so
    // the sentence keeps its referent and needs no rewording — which is why the list was not moved
    // to the sidebar in this unit.
    expect(container.textContent).toContain("no row in the repository list below")
  })
})

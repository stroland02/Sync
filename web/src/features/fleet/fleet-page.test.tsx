/**
 * The fleet Overview: five panes of a viewport-locked bento, and the sentences that qualify them.
 *
 * **Retitled with the 2026-08-26 rebuild.** This screen was a scrolling column of eight regions,
 * three of which could not draw under any address the console produces — the totals line and the
 * vendor cards returned `null` on every load and the dependency-graph region rendered a paragraph
 * explaining why it had nothing to draw, because `REPO_SCOPED_PATHS` is empty and the
 * sole-codebase install redirects before this component renders. The guards those regions carried
 * are kept where they still describe something: the protected sentences, the refusal, the absent
 * codebase list, the absent page-level action. The two "beside" guards now hold adjacency in the
 * bento grid rather than inside a two-child wrapper, which is the same claim about the same
 * sentence against the composition that replaced it.
 *
 * Scope is `.claude/rules/test-discipline.md`'s: structure and classification, never class names
 * and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
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
  usePrecedent: () => settled({ attempts: 0, distinct_findings: 0 }),
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

/**
 * The pane element a heading names — its header's parent, which is the pane root.
 *
 * Structural rather than a class lookup: `PanelPane` is the chassis primitive and a test that
 * knew its classes would go red on every correct restyle.
 */
function paneNamed(name: string): HTMLElement {
  const heading = screen.getByRole("heading", { name })
  const pane = heading.closest("header")?.parentElement ?? null
  expect(pane).not.toBeNull()
  return pane as HTMLElement
}

describe("the fleet overview's composition", () => {
  it("tiles five panes into one grid, so a dropped pane cannot pass on a surviving one", () => {
    renderOverview()

    const grid = paneNamed("This codebase").parentElement
    expect(grid).not.toBeNull()
    expect(grid!.childElementCount).toBe(5)

    for (const pane of [
      "What Sync has found, over time",
      "What this evidence rests on",
      "This codebase",
      "Health score policy",
      "What this screen cannot tell you",
    ]) {
      expect(screen.getByRole("heading", { name: pane })).toBeTruthy()
    }
  })

  it("mounts dashboard 1, because a card nobody mounts is not shipped", () => {
    const { container } = renderOverview()

    // Fleet-scoped and propless, and now the bento's widest pane. The assertion is on the card
    // being on the screen at all: a finished card left unmounted is the failure this guards, and
    // it is invisible without one. Matches in either state -- mounted-and-loading is still
    // mounted, and the assertion is about the mount rather than about what the API answered.
    expect(screen.getByRole("heading", { name: "What Sync has found, over time" })).toBeTruthy()
    expect(container.textContent).toMatch(/findings over time/i)
  })

  it("carries no page header, because density is dense", () => {
    renderOverview()

    // Owner answer 7: tight rows, small type, minimal padding, no page headers. The screen is
    // named by the breadcrumb and the sidebar; an h1 repeating it spends a band of the first
    // screen on a word the reader just clicked. Recorded conflict: the mock draws one, and
    // answer 20 says the answer wins.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull()
  })

  it("draws no dependency graph, because a map is about one codebase and this screen is not", () => {
    const { container } = renderOverview("/?repo_id=org%2Fone")

    // The graph region on this screen could only ever render the paragraph explaining why it had
    // nothing to draw: nothing in the console produces a `?repo_id=` address here, and the
    // sole-codebase install redirects to the codebase's own Overview before this renders. The map
    // is drawn full size there, in the bento's top row, against the codebase it describes.
    expect(container.textContent).not.toContain("Your codebase, out to its vendors")
    expect(container.textContent).not.toContain("there is no dependency graph to draw")
  })

  it("does not list the codebases, because the Overview is one workspace's findings", () => {
    const { container } = renderOverview("/?repo_id=org%2Fone")

    // Ruled twice by the owner. The directory of codebases answers "which workspace am I in",
    // which the scope switcher answers; this screen answers "what is true about the one I chose".
    // The listing is not deleted -- it is the Codebases group in Settings, where choosing and
    // configuring a codebase is the question being asked.
    expect(screen.queryByRole("heading", { name: /monitored codebases/i })).toBeNull()
    expect(container.querySelector('a[href="/repositories/org%2Ftwo"]')).toBeNull()
  })

  it("carries no page-level review action, because that belongs to a change unit", () => {
    renderOverview()

    // The action pointed at whichever run happened to be newest with an opened pull request, which
    // reads as "the" patch when there are nine change units. It belongs on the row it acts on.
    expect(screen.queryByRole("link", { name: /review proposed patch/i })).toBeNull()
  })
})

describe("what the fleet overview may not stop saying", () => {
  it("keeps every protected sentence that qualifies what is on screen", () => {
    const { container } = renderOverview()
    const text = container.textContent ?? ""

    expect(text).toContain("A checkpoint age is staleness, not liveness")
    expect(text).toContain("absence is not zero")
    expect(text).toContain("counts once toward the corpus grain")
    expect(text).toContain("There is no composite health figure here on purpose")
  })

  it("puts the limits pane beside the refusal, because the refusal's last clause names it", () => {
    renderOverview()

    // The health-refusal sentence ends "the panel beside them names what none of these figures can
    // tell you at all". W362 once collapsed a three-column band to one column and left both panels
    // stacked in a single wrapper, which made that clause false while the sentence still read as
    // true. Asserting the text alone could not catch it -- that is what this guard adds, and in
    // the bento it is adjacency in the grid rather than two children of a wrapper. jsdom has no
    // layout, so "beside" is measured in Chrome; what is held here is the DOM ordering without
    // which it cannot be true at any viewport.
    const refusal = paneNamed("Health score policy")
    expect(refusal.textContent).toContain("There is no composite health figure here on purpose")

    const next = refusal.nextElementSibling
    expect(next).not.toBeNull()
    expect(next!.textContent).toContain("What this screen cannot tell you")
  })

  it("gives the codebase fact band a pane of its own, because it answers which codebase this is", () => {
    renderOverview("/?repo_id=org%2Fone")

    const band = paneNamed("This codebase").querySelector("[aria-label='Codebase facts']")
    expect(band).not.toBeNull()
    expect(band?.textContent).toContain("org/one")
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

  it("keeps absence-is-not-zero pointing at a list that is actually there", () => {
    const { container } = renderOverview()

    // The sentence is protected: it may be restyled and re-placed, never shortened or deleted. Its
    // referent moved with the listing, so the pointer moves with it. A protected sentence naming a
    // list this screen no longer holds would be a true claim with a dead pointer, which is the
    // quiet half of the same defect.
    const text = container.textContent ?? ""
    expect(text).toContain("absence is not zero")
    expect(text).toContain("no row in the codebase list in Settings")
    expect(text).not.toContain("the repository list below")
  })
})

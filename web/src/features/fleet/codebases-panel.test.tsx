/**
 * Panel-level behavior beyond `codebase-cards.ts`'s derivation: a card renders the absence
 * marker while its own scoped `/api/overview` query is still pending, and the scoped count
 * once that answer lands. Scope is `.claude/rules/console-dev-loop.md`'s — classification and
 * derivation, never class names, never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { OverviewResponse } from "@/api/types"
import { CodebasesPanel } from "@/features/fleet/codebases-panel"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

let mockRepositories: unknown

vi.mock("@/api/queries", () => ({
  useRepositories: () => mockRepositories,
}))

const { fetchOverview } = vi.hoisted(() => ({ fetchOverview: vi.fn() }))
vi.mock("@/api/client", () => ({ fetchOverview }))

const overview = (over: Partial<OverviewResponse>): OverviewResponse => ({
  repo_id: "org/repo",
  vendors: [],
  total_findings: 0,
  total_findings_bound: 0,
  total_findings_bound_reached: true,
  severity_counts: {},
  bindings_by_rung: { static: 0, resolved: 0, observed: 0, unresolved: 0, unattributed: 0 },
  indexed_at: null,
  feed_fetched_at: null,
  binding_source: null,
  context_savings: 0,
  context_savings_bound_reached: true,
  ...over,
})

function renderPanel(filter?: "ALL" | "NEEDS_REVIEW" | "CLEAN") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <CodebasesPanel filter={filter} />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("CodebasesPanel", () => {
  it("renders the absence marker on a card while its scoped overview is still pending", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockReturnValue(new Promise<OverviewResponse>(() => {}))

    renderPanel()

    expect(await screen.findByText("org/repo")).toBeTruthy()
    expect(screen.getByText(/open findings not yet answered/)).toBeTruthy()
  })

  it("renders the scoped count once the answer for that repository arrives", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockResolvedValue(overview({ total_findings: 3 }))

    renderPanel()

    expect(await screen.findByText("3 open findings")).toBeTruthy()
  })

  it("refuses to claim a card's scope from a different repository's answer", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockResolvedValue(overview({ repo_id: "org/other", total_findings: 9 }))

    renderPanel()

    expect(await screen.findByText("org/repo")).toBeTruthy()
    expect(screen.queryByText("9 open findings")).toBeNull()
    expect(screen.getByText(/open findings not yet answered/)).toBeTruthy()
  })

  it("does not claim zero matches while a scoped query is still pending under a non-ALL filter", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockReturnValue(new Promise<OverviewResponse>(() => {}))

    renderPanel("NEEDS_REVIEW")

    // "No codebases match" would be claiming the scoped answer is a confirmed zero; the true
    // state is "not yet answered", so the loading state is what must show instead.
    expect(await screen.findByText("Loading monitored codebases…")).toBeTruthy()
    expect(screen.queryByText("No codebases match the selected filter.")).toBeNull()
  })

  it("claims no matches only once every scoped query has settled", async () => {
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/repo"] } }
    fetchOverview.mockResolvedValue(overview({ total_findings: 0 }))

    renderPanel("NEEDS_REVIEW")

    expect(await screen.findByText("No codebases match the selected filter.")).toBeTruthy()
    expect(screen.queryByText("Loading monitored codebases…")).toBeNull()
  })

  it("does not repeat a description that says nothing the card has not already said", () => {
    /**
     * Every card carried "Git repository - Monitored by Sync", once per repository. It carries none
     * of the four protected distinctions and tells a reader nothing they do not already know from
     * being on the Sync console's own repository list. Measured at 170 of Fleet's 450 discretionary
     * characters against the drawn console's 340 -- the largest single piece of prose on the screen
     * carrying no distinction, and the only one where deleting it removes no fact.
     */
    mockRepositories = { isPending: false, isError: false, data: { repo_ids: ["org/one", "org/two"] } }
    fetchOverview.mockResolvedValue(overview({ repo_id: "org/one", total_findings: 0 }))

    const { container } = renderPanel()

    expect(container.textContent).not.toContain("Monitored by Sync")
  })
})

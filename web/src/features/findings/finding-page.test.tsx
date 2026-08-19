import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { FindingDetail } from "@/api/types"
import { FindingPage } from "@/features/findings/finding-page"

afterEach(cleanup)

function renderScreen(findingId = "f1") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/findings/${findingId}`]}>
        <Routes>
          <Route path="/findings/:findingId" element={<FindingPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("FindingPage", () => {
  it("carries no page header, which is the twelfth page and the last exception", () => {
    renderScreen()

    // Answer 7 removed page headers, and Lane B converted eleven of twelve. This page was the
    // one held back, because it passed an action the others did not have. The action is now in
    // the rail beside the two destinations already there, which is where a reader on this screen
    // already scans for somewhere to go, so the exception has nothing left holding it open.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull()
  })

  it("renders severity, repository link, and call site path and line in fact rail", () => {
    const mockFinding: FindingDetail = {
      finding: {
        finding_id: "f1",
        binding_source: "static",
        severity: "breaking",
        file: "src/billing.ts",
        line: 42,
        repo_id: "acme/corp-app",
      },
      symbol: "stripe.charges.create",
      operation: "PostCharges",
      vendor: "stripe",
      args_keys: ["amount", "currency"],
      response_fields_read: ["status"],
      sdk_version: "18.0.0",
      known_changes: [],
      indexed_at: "2026-08-01T00:00:00Z",
      feed_fetched_at: null,
      context_savings: 100,
      context_savings_bound_reached: false,
      binding_source: "static",
      source_served: true,
      call_site_source: null,
    }

    vi.spyOn(queries, "useFinding").mockReturnValue({
      data: mockFinding,
      isLoading: false,
      isError: false,
      error: null,
      isSuccess: true,
      refetch: vi.fn(),
    } as any)

    vi.spyOn(queries, "useWorkflow").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      isSuccess: false,
      refetch: vi.fn(),
    } as any)

    renderScreen("f1")

    expect(screen.getByText("Severity")).toBeTruthy()
    expect(screen.getByText("breaking")).toBeTruthy()

    expect(screen.getByText("Repository")).toBeTruthy()
    const repoLink = screen.getByRole("link", { name: "acme/corp-app" })
    expect(repoLink.getAttribute("href")).toBe("/repositories/acme%2Fcorp-app")

    expect(screen.getByText("Call site")).toBeTruthy()
    expect(screen.getByText("src/billing.ts:42")).toBeTruthy()
  })
})

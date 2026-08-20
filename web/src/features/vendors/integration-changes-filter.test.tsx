/**
 * Narrowing the changes feed, end to end through the page.
 *
 * **Owner report, 2026-08-19: the rail "doesn't work".** The rail renders selectable options in
 * isolation and the route filters correctly when called directly, so the question is whether the
 * page wires the two together — pressing an option has to reach the query and change what is
 * requested. That is the claim this file holds, because it is the one nothing else covered: the
 * rail has its own tests and the route has its own tests, and the seam between them had none.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { IntegrationChangesPage } from "@/features/vendors/integration-changes-page"

const requested: string[] = []

function payload(vendorId: string | null) {
  return {
    repo_id: "demo",
    items: [
      {
        id: "c-1",
        vendor_id: vendorId ?? "stripe",
        from_version: "v1",
        to_version: "v2",
        kind: "response-property-removed",
        operation_id: "PostCharges",
        path_ptr: "/p",
        severity: "breaking",
        source: "oasdiff",
        detected_at: "2026-08-18T00:00:00Z",
      },
    ],
    total: vendorId === null ? 12075 : 107,
    next_offset: null,
    by_vendor: { openai: 107, stripe: 11928 },
    by_severity: { breaking: 108, warning: 11928 },
    by_vendor_severity: { stripe: { warning: 11928 }, openai: { breaking: 107 } },
    unfiltered_total: 12075,
    vendor_id: vendorId,
    severity: null,
  }
}

beforeEach(() => {
  requested.length = 0
  vi.stubGlobal("fetch", (input: string) => {
    requested.push(String(input))
    const url = new URL(String(input), "http://localhost")
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(payload(url.searchParams.get("vendor_id"))),
    } as Response)
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderChanges() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/demo/integration-changes"]}>
        <Routes>
          <Route
            path="/repositories/:repoId/integration-changes"
            element={<IntegrationChangesPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("narrowing the changes feed", () => {
  it("offers an option per integration the facet counted", async () => {
    renderChanges()

    // The rail's options are the claim: a facet that renders its legend and no options is the
    // shape the owner reported, and it would pass every isolated test the rail already has.
    expect(await screen.findByRole("button", { name: /openai/i })).toBeTruthy()
    expect(screen.getByRole("button", { name: /stripe/i })).toBeTruthy()
  })

  it("asks the route for the narrowed set when an option is pressed", async () => {
    renderChanges()
    fireEvent.click(await screen.findByRole("button", { name: /openai/i }))

    // The seam: the press has to reach the query key and change what is fetched. A rail that
    // updates only its own pressed state looks identical on screen and is the defect.
    await waitFor(() =>
      expect(requested.some((url) => url.includes("vendor_id=openai"))).toBe(true),
    )
  })

  it("returns to the whole set when the pressed option is pressed again", async () => {
    renderChanges()
    const option = await screen.findByRole("button", { name: /openai/i })
    fireEvent.click(option)
    await waitFor(() => expect(requested.some((u) => u.includes("vendor_id=openai"))).toBe(true))

    requested.length = 0
    fireEvent.click(await screen.findByRole("button", { name: /openai/i }))

    await waitFor(() => {
      expect(requested.length).toBeGreaterThan(0)
      expect(requested.every((url) => !url.includes("vendor_id="))).toBe(true)
    })
  })
})

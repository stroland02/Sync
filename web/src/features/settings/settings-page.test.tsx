/**
 * Settings measured as the one route still a single stack (M14-W278): `sideBySideRegions` read
 * 0 against the same snippet every other route clears at 4 or higher. `DetailGrid` already owns
 * the console's one two-column detail shape, so this wires the page onto it rather than adding a
 * sixth grid literal — Merge policy (the shorter refusal) as the rail, Adapters (the table) as
 * the wider content column.
 *
 * This is composition, not content: every sentence asserted here is the same sentence the
 * stacked layout rendered, in the same words, just no longer alone on its own row.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { AdapterInventoryResponse } from "@/api/types"
import { SettingsPage } from "@/features/settings/settings-page"

afterEach(cleanup)

function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const data: AdapterInventoryResponse = {
    adapters: [
      {
        vendor_id: "seed-console-stripe",
        kind: "coded",
        source: null,
        changes: 2,
        operations: 2,
        last_change_at: "2026-08-16T10:04:00+00:00",
        sources: ["oasdiff"],
      },
    ],
  }
  vi.spyOn(queries, "useAdapters").mockReturnValue({
    data,
    isPending: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
  } as any)

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("SettingsPage's composition", () => {
  it("renders Merge policy as a rail beside Adapters, not Adapters then Merge policy stacked below it", () => {
    const { container } = renderSettings()
    const text = container.textContent!
    // DetailGrid's own contract (detail-grid.test.tsx) is that the rail precedes the content
    // column in DOM order when railSide is left at its default. Merge policy is the rail here —
    // the stacked layout this replaces rendered Adapters first, so this only passes once the
    // page is actually wired onto DetailGrid rather than two flex-col divs in source order.
    expect(text.indexOf("Merge policy")).toBeLessThan(text.indexOf("Adapters"))
  })

  it("keeps both refusal sentences verbatim -- moving them is allowed, rewording them is not", () => {
    renderSettings()
    expect(
      screen.getByText(
        /Sync has no merge policy to show\. Nothing in the pull-request path reads a configured/,
      ),
    ).toBeTruthy()
    expect(
      screen.getByText(/What has to land first is the write path this whole screen is read-only for/),
    ).toBeTruthy()
    expect(
      screen.getByText(
        /Every adapter this deployment registers, beside what the graph has received from it/,
      ),
    ).toBeTruthy()
  })
})

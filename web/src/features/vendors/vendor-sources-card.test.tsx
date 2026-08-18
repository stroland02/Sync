/**
 * Where vendor changes were read from — test suite for intake provenance card.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { VendorSourcesCard } from "@/features/vendors/vendor-sources-card"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })

const { useAdapters } = vi.hoisted(() => ({ useAdapters: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useAdapters,
}))

function renderCard(vendorId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <VendorSourcesCard vendorId={vendorId} />
    </QueryClientProvider>
  )
}

describe("VendorSourcesCard", () => {
  it("renders intake feed and registered adapter tier when adapter exists", () => {
    useAdapters.mockReturnValue(
      settled({
        adapters: [
          {
            vendor_id: "openai",
            kind: "coded",
            feed: "https://api.openai.com/v1/spec",
            operations_named: 142,
            last_intake_at: "2026-08-16T12:00:00Z",
          },
        ],
      })
    )

    renderCard("openai")

    expect(screen.getByText("Where it was read from")).not.toBeNull()
    expect(screen.getByText("coded adapter feed")).not.toBeNull()
    expect(screen.getByText("https://api.openai.com/v1/spec")).not.toBeNull()
    expect(screen.getByText("sync.signals.openai")).not.toBeNull()
    expect(screen.getByText(/142 operations/)).not.toBeNull()
  })

  it("handles unregistered vendors gracefully without breaking", () => {
    useAdapters.mockReturnValue(settled({ adapters: [] }))

    renderCard("unknown_vendor")

    expect(screen.getByText("Where it was read from")).not.toBeNull()
    expect(screen.getByText("Specification feed")).not.toBeNull()
    expect(screen.getByText("no recorded intake")).not.toBeNull()
    expect(screen.getByText("unregistered")).not.toBeNull()
  })

  it("states that runtime telemetry correlation reads no customer source code", () => {
    useAdapters.mockReturnValue(settled({ adapters: [] }))

    renderCard("stripe")

    expect(screen.getByText("Runtime telemetry")).not.toBeNull()
    expect(screen.getByText(/reads no source|without reading customer source/i)).not.toBeNull()
  })
})

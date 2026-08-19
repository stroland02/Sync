/**
 * Where vendor changes were read from — test suite for intake provenance card.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 *
 * The suite this replaces asserted three fields that are not on `AdapterRow` and never were —
 * `feed`, `operations_named`, `last_intake_at`. Its fixtures supplied them, so it passed while
 * the component beneath it rendered a hard-coded string as fact. The fixtures here are the
 * payload shape, which is what makes a failure here mean something.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { AdapterRow } from "@/api/types"
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

/** A delivering adapter, every field populated, overridable per case. */
function adapter(overrides: Partial<AdapterRow> = {}): AdapterRow {
  return {
    vendor_id: "openai",
    kind: "coded",
    source: "sdk/openai-node",
    changes: 87,
    operations: 142,
    last_change_at: "2026-08-16T12:00:00Z",
    sources: ["openapi", "changelog"],
    last_attempt_at: null,
    last_attempt_outcome: null,
    last_attempt_reason: null,
    last_attempt_changes: null,
    attempts: {},
    ...overrides,
  }
}

function renderCard(vendorId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <VendorSourcesCard vendorId={vendorId} />
    </QueryClientProvider>
  )
}

describe("VendorSourcesCard", () => {
  it("reports the adapter kind, its source, and what it has delivered", () => {
    useAdapters.mockReturnValue(settled({ adapters: [adapter()] }))

    renderCard("openai")

    expect(screen.getByText("Where it was read from")).not.toBeNull()
    expect(screen.getByText("coded adapter")).not.toBeNull()
    expect(screen.getByText("sdk/openai-node")).not.toBeNull()
    expect(screen.getByText("87 changes")).not.toBeNull()
    expect(screen.getByText(/142 distinct operations/)).not.toBeNull()
    expect(screen.getByText("openapi · changelog")).not.toBeNull()
  })

  it("names the newest change as a change, never as an intake", () => {
    useAdapters.mockReturnValue(settled({ adapters: [adapter()] }))

    renderCard("openai")

    // `AdapterRow.last_change_at` records a result, not an attempt. An adapter polled hourly
    // that has found nothing for a week reports last week, so labelling it "intake" would turn
    // staleness into liveness — the distinction the console exists to keep.
    expect(screen.getByText(/last change/)).not.toBeNull()
    expect(screen.queryByText(/intake/i)).toBeNull()
  })

  it("distinguishes an adapter that has delivered nothing from one that has", () => {
    useAdapters.mockReturnValue(
      settled({ adapters: [adapter({ changes: null, operations: null, last_change_at: null })] })
    )

    renderCard("openai")

    expect(screen.getByText("never delivered")).not.toBeNull()
    expect(screen.getByText("no change recorded")).not.toBeNull()
    expect(screen.getByText(/holds no operations from it/)).not.toBeNull()
  })

  it("renders an unrecorded source as absence rather than as a guess", () => {
    useAdapters.mockReturnValue(settled({ adapters: [adapter({ source: null, sources: null })] }))

    renderCard("openai")

    // Two absences: the adapter's own source, and the `source` values its rows carry.
    expect(screen.getAllByText("—")).toHaveLength(2)
  })

  it("says no adapter serves the vendor rather than inventing a feed for it", () => {
    useAdapters.mockReturnValue(settled({ adapters: [] }))

    renderCard("unknown_vendor")

    expect(screen.getByText("Where it was read from")).not.toBeNull()
    expect(screen.getByText(/No adapter is registered for unknown_vendor/)).not.toBeNull()
    expect(screen.queryByText(/Specification feed/)).toBeNull()
  })
})

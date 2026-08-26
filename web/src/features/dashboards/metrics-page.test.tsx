/**
 * The Trends screen, which had no test file at all before the rebuild of 2026-08-26 — which is
 * exactly how five cards could sit in one scrolling column against a brief mandating a locked
 * composition, and nothing go red.
 *
 * Three things are held here and none of them is a class name. **That the screen is locked**, which
 * is the structural difference between the rebuild and the reskin it replaced. **That all five
 * panes are mounted**, anchored on every pane rather than one, so a dropped pane fails instead of
 * passing quietly. **That the form follows the payload** — the rule `daily-series.test.ts` covers
 * as a derivation, asserted here at the surface that consumes it, because a correct derivation
 * nothing calls is the same defect one layer down.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { FindingsOverTimeResponse, ObservedTelemetryResponse } from "@/api/types"
import { MetricsPage } from "@/features/dashboards/metrics-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useFindingsOverTime, useRepositoryObserved } = vi.hoisted(() => ({
  useFindingsOverTime: vi.fn(),
  useRepositoryObserved: vi.fn(),
}))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useFindingsOverTime,
  useRepositoryObserved,
}))

const OBSERVED: ObservedTelemetryResponse = {
  repo_id: "org/payments",
  telemetry_attached_at: null,
  calls: { items: [], total: 0, next_offset: null },
  shapes: { items: [], total: 0, next_offset: null },
  error_windows: { items: [], total: 0, next_offset: null },
  traffic: [],
  unattributed: [],
  series: [],
  totals: {
    requests: 0,
    errors: 0,
    unstatused: 0,
    unattributed_requests: 0,
    operations_observed: 0,
    operations_indexed: 0,
  },
}

/** The three routes this screen reads through a bare `fetch`, keyed by path. */
function stubFetch(changeDays: { day: string; counts: Record<string, number> }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((path: string) => {
      const body =
        path === "/api/integration-changes/over-time"
          ? {
              vendor_id: null,
              vendors: ["stripe", "twilio"],
              days: changeDays,
              total: changeDays.reduce(
                (sum, day) => sum + Object.values(day.counts).reduce((n, v) => n + v, 0),
                0,
              ),
            }
          : path === "/api/precedent/activity"
            ? { days: [{ day: "2026-08-26", counts: { opened: 1, abandoned: 1 } }], by_tier: {} }
            : { counts: { superseded: 2 }, total: 2 }
      return Promise.resolve({ ok: true, json: async () => body } as unknown as Response)
    }),
  )
}

function renderPage(days: FindingsOverTimeResponse["days"]) {
  useFindingsOverTime.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: {
      repo_id: null,
      severities: ["breaking", "warning"],
      days,
      by_rung: { static: 2 },
      total: days.reduce(
        (sum, day) => sum + Object.values(day.counts).reduce((n, v) => n + v, 0),
        0,
      ),
      still_open: 1,
    } satisfies FindingsOverTimeResponse,
  })
  useRepositoryObserved.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: OBSERVED,
  })
  stubFetch(days.map((day) => ({ day: day.day, counts: { stripe: 6 } })))

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fpayments/metrics"]}>
        <Routes>
          <Route path="/repositories/:repoId/metrics" element={<MetricsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const ONE_DAY = [{ day: "2026-08-26", counts: { breaking: 36, warning: 38 } }]
const TWO_DAYS = [
  { day: "2026-08-25", counts: { breaking: 4, warning: 1 } },
  { day: "2026-08-26", counts: { breaking: 36, warning: 38 } },
]

describe("the Trends screen", () => {
  /**
   * The measurement the whole rebuild was dispatched against: eighteen of twenty-one screens
   * rendered `ScreenFrame` at its default `flow` layout. A token swap cannot change this
   * attribute, which is why it is the assertion and not a colour.
   */
  it("owns its own scrollbars rather than growing a page", () => {
    const { container } = renderPage(ONE_DAY)

    expect(container.querySelector('[data-band="content"]')?.getAttribute("data-screen")).toBe(
      "locked",
    )
  })

  /** Anchored on all five panes: a dropped pane must fail rather than pass quietly. */
  it("mounts every pane the screen is composed of", async () => {
    renderPage(ONE_DAY)

    await waitFor(() => {
      expect(screen.getByText("What the integrations published")).toBeTruthy()
    })
    expect(screen.getByText("What Sync found in it")).toBeTruthy()
    expect(screen.getByText("What Sync did about it")).toBeTruthy()
    expect(screen.getByText("What traffic actually called")).toBeTruthy()
    expect(screen.getByText("Set aside")).toBeTruthy()
  })

  /**
   * One day is not a series. Measured against this deployment on 2026-08-26 every series returned
   * exactly one day, and a stacked column over one tick invites a trend nothing measured.
   */
  it("draws a composition and names the day when only one day was recorded", async () => {
    renderPage(ONE_DAY)

    await waitFor(() => {
      expect(screen.getAllByText(/composition by severity rather than a series/).length).toBe(1)
    })
    expect(screen.getAllByText(/2026-08-26/).length).toBeGreaterThan(0)
  })

  it("stops calling it a composition once a second day arrives", async () => {
    renderPage(TWO_DAYS)

    await waitFor(() => {
      expect(screen.getByText("What Sync found in it")).toBeTruthy()
    })
    expect(screen.queryByText(/rather than a series/)).toBeNull()
  })

  /** A count is not a rate. Nothing on this screen divides one measurement by another. */
  it("renders no percentage", async () => {
    const { container } = renderPage(ONE_DAY)

    await waitFor(() => {
      expect(screen.getByText("Set aside")).toBeTruthy()
    })
    expect(container.textContent).not.toMatch(/%/)
  })

  /** Never-measured is not nothing-here: this repository has no telemetry attached at all. */
  it("says which nothing the traffic pane is in", async () => {
    renderPage(ONE_DAY)

    await waitFor(() => {
      expect(screen.getByText("Never measured.")).toBeTruthy()
    })
    expect(
      screen.getByText(/absence of a measurement rather than a measurement of nothing/),
    ).toBeTruthy()
  })
})

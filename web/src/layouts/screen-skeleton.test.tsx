/**
 * The migration ratchet.
 *
 * Every address the console serves is either migrated onto `ScreenFrame` or explicitly pending.
 * The union must equal the declared set, so a route added later cannot dodge the skeleton by
 * being absent from both lists, and `PENDING` can only ever shrink.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import App from "@/App"
import { DESTINATIONS, ROUTES } from "@/lib/routes"

afterEach(cleanup)

/** Screens rendering through `ScreenFrame`. Move a path up as it migrates; never back. */
const MIGRATED = [
  "/settings",
  "/repositories/:repoId/file-tree",
  "/repositories/:repoId/call-sites",
  "/repositories/:repoId/graph",
  "/repositories/:repoId/observed",
  "/",
  "/repositories/:repoId/findings",
  "/repositories/:repoId/services",
  "/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId",
  "/repositories/:repoId/findings/:findingId",
  "/repositories/:repoId/findings/:findingId/workflow",
  "/repositories/:repoId/findings/:findingId/workflow/pull-request",
  "/repositories/:repoId/integration-changes",
  "/repositories/:repoId",
  "/repositories/:repoId/metrics",
  "/repositories/:repoId/precedent",
  "/repositories/:repoId/solutions",
  "/repositories/:repoId/runs",
  "/repositories/:repoId/vendors",
  "/repositories/:repoId/detectors",
]

const PENDING = [
  "/repositories/:repoId/vendors/:vendorId",
]

/** The index route is wired in `App.tsx` rather than the registry, so it is named here as "/". */
const INDEX_ROUTE = "/"

function declaredAddresses(): string[] {
  return [
    INDEX_ROUTE,
    ...ROUTES.map((route) => route.path),
    ...DESTINATIONS.map((destination) => destination.path),
  ]
}

describe("the skeleton migration ratchet", () => {
  it("accounts for every declared address exactly once", () => {
    const claimed = [...MIGRATED, ...PENDING].sort()
    const declared = declaredAddresses().sort()

    expect(claimed).toEqual(declared)
  })

  it("names no address twice", () => {
    const claimed = [...MIGRATED, ...PENDING]
    expect(new Set(claimed).size).toBe(claimed.length)
  })

  it("has migrated at least one screen, so the ratchet is not vacuous", () => {
    // Without this the lists could satisfy the union check with MIGRATED empty forever, and the
    // gate would report a migration that never started.
    expect(MIGRATED.length).toBeGreaterThan(0)
  })
})

/**
 * The bookkeeping above partitions addresses and never renders one, so for twenty screens
 * `MIGRATED` was a claim rather than a finding. These two render the real chassis and read the
 * band `ScreenFrame` stamps, which is the only thing that can tell the lists apart from a wish.
 */
describe("the ratchet's two lists are true of the rendered screens", () => {
  function bandAt(path: string): Element | null {
    // A fresh client per render, for the reason `routes.test.tsx` gives: a shared one carries a
    // previous route's cached failure into the next assertion. Every query here fails -- jsdom
    // has no API -- and a screen that only reaches its frame after data arrives would fail this,
    // correctly, as a screen the skeleton does not yet govern.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path.replace(/:([A-Za-z]+)/g, "subject")]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    )
    return container.querySelector("[data-band='content']")
  }

  it.each(MIGRATED.map((path) => [path]))("%s renders a content band", (path) => {
    expect(bandAt(path)).not.toBeNull()
  })

  it.each(PENDING.map((path) => [path]))("%s renders none, as PENDING claims", (path) => {
    // The half that makes the other half provable. Asserting only the migrated side would pass
    // against a query that matched anything, and it is what goes red first when a screen is
    // migrated without moving its entry up.
    expect(bandAt(path)).toBeNull()
  })
})

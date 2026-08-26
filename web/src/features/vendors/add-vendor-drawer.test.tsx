/**
 * The "Add a vendor" affordance: what it lists, and what it refuses to do.
 *
 * **The read-only assertion is the reason this file stubs `fetch` rather than the query hooks.**
 * Mocking `useAdapters`/`useRepositoryCoverage` would leave nothing calling the transport, and
 * "no route mutated anything" over zero requests is a green test that proves nothing. With the
 * real hooks running against a stub, the drawer's own catalogue read and the page's coverage read
 * both land in `calls`, so the assertion is made over traffic that actually happened — and it
 * fails the day somebody adds a POST behind this button.
 *
 * Scope is `web/CLAUDE.md`'s: classification, derivation and structural invariants. Never class
 * names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RepositoryVendorsPage } from "@/features/vendors/repository-vendors-page"

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const REPO = "org/one"

/** One catalogue row, defaulted to the shape a registered-and-unused vendor actually has. */
function row(vendor_id: string, state: "watched" | "staged" | "available", extra = {}) {
  return {
    vendor_id,
    tier: "generated",
    source: `${vendor_id}/${vendor_id}-sdk-python`,
    sdk_bindings: { python: { distribution: vendor_id, module: vendor_id } },
    staged: null,
    call_sites: state === "watched" ? 3 : 0,
    changes_recorded: 0,
    state,
    ...extra,
  }
}

const CATALOGUE = {
  repo_id: REPO,
  integrations: [row("stripe", "watched"), row("twilio", "staged"), row("vercel", "available")],
  by_tier: { generated: 3 },
  by_state: { watched: 1, staged: 1, available: 1 },
  total: 3,
}

const COVERAGE = {
  repo_id: REPO,
  by_vendor: { stripe: 3 },
  last_indexed: {},
  total_call_sites: 3,
  by_service: [],
  by_operation: [],
  by_binding_status: {},
}

const OVERVIEW = {
  last_index_run: { started_at: "2026-08-20T10:00:00Z", finished_at: "2026-08-20T10:04:00Z" },
}

/**
 * Every route the screen reads, answered from memory.
 *
 * Anything unrecognised answers 404 rather than a stub payload: a route this fake does not know
 * about is a route the test has not been told to expect, and inventing an answer for it would hide
 * exactly the new request this file exists to notice.
 */
function stubFetch() {
  const calls: { url: string; init?: RequestInit }[] = []
  const fetchSpy = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    calls.push({ url, init })
    const body =
      url.startsWith("/api/integrations")
        ? CATALOGUE
        : url.startsWith("/api/overview")
          ? OVERVIEW
          : url.includes("/coverage")
            ? COVERAGE
            : null
    return Promise.resolve(
      body === null
        ? new Response(JSON.stringify({ error: "no such route", identifier: url }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
    )
  })
  vi.stubGlobal("fetch", fetchSpy)
  return calls
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/${encodeURIComponent(REPO)}/vendors`]}>
        <Routes>
          <Route path="/repositories/:repoId/vendors" element={<RepositoryVendorsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Opens the drawer and returns it, so every test below starts from the same two clicks. */
async function openDrawer() {
  fireEvent.click(await screen.findByRole("button", { name: /add a vendor/i }))
  return await screen.findByRole("dialog")
}

describe("the add-vendor drawer", () => {
  it("opens from the vendors screen", async () => {
    stubFetch()
    renderPage()

    // Closed until asked for: a panel of explanation permanently on screen is the "too much
    // information" failure the master brief names.
    expect(screen.queryByRole("dialog")).toBeNull()

    const drawer = await openDrawer()
    expect(drawer.textContent).toContain("Add a vendor")
  })

  it("lists the registered vendors this repository does not watch, and only those", async () => {
    stubFetch()
    renderPage()

    const drawer = await openDrawer()
    await waitFor(() => expect(drawer.textContent).toContain("twilio"))

    // The two unwatched rows are openable; the watched one belongs to the table behind the drawer
    // and listing it here would be the screen telling a reader to add what it already has.
    const rows = within(drawer).getAllByRole("button", { expanded: false })
    const names = rows.map((element) => element.textContent ?? "")
    expect(names.some((name) => name.includes("twilio"))).toBe(true)
    expect(names.some((name) => name.includes("vercel"))).toBe(true)
    expect(names.some((name) => name.includes("stripe"))).toBe(false)
  })

  it("says why a registered vendor is not in the table, rather than implying a failure", async () => {
    stubFetch()
    renderPage()

    const drawer = await openDrawer()
    await waitFor(() => expect(drawer.textContent).toContain("twilio"))

    // The whole honest claim of the panel. Without it the list reads as vendors that failed to
    // attach, which is the one thing none of them did.
    expect(drawer.textContent).toContain(
      "a registered vendor appears there once an index pass finds a call site",
    )
  })

  it("opens a row onto what would make it watched", async () => {
    stubFetch()
    renderPage()

    const drawer = await openDrawer()
    const trigger = await within(drawer).findByRole("button", { name: /twilio/i })
    fireEvent.click(trigger)

    await waitFor(() =>
      expect(within(drawer).getByText(/imports an index pass looks for/i)).not.toBeNull(),
    )
  })

  it("hands over the YAML for a vendor that is not registered at all", async () => {
    stubFetch()
    renderPage()

    const drawer = await openDrawer()

    // The field names are the registry's, and the block says the constraint the loader enforces.
    expect(drawer.textContent).toContain("vendor_id")
    expect(drawer.textContent).toContain("sdk_bindings")
    expect(drawer.textContent).toContain("generated-vendors.yaml")
    expect(drawer.textContent).toContain("exactly one of `manifest` and `spec`")
    expect(within(drawer).getByRole("button", { name: /copy the yaml block/i })).not.toBeNull()
  })

  it("never claims the console performed the addition", async () => {
    stubFetch()
    renderPage()

    const drawer = await openDrawer()

    expect(drawer.textContent).toContain("Nothing here adds anything")
    // No submit path at all: a form in this drawer would be an affordance promising a write the
    // read-only API has no route for.
    expect(drawer.querySelector("form")).toBeNull()
    expect(within(drawer).queryByRole("button", { name: /^(save|create|register|add vendor)$/i })).toBeNull()
  })

  it("calls no route that could mutate anything", async () => {
    const calls = stubFetch()
    renderPage()

    const drawer = await openDrawer()
    await waitFor(() => expect(drawer.textContent).toContain("twilio"))
    fireEvent.click(await within(drawer).findByRole("button", { name: /twilio/i }))

    // Non-vacuous: the screen genuinely talked to the transport, and every one of those requests
    // was a read. `test_no_route_reaches_past_the_read_surface` holds the same rule on the Python
    // side; this is the console's half of it.
    expect(calls.length).toBeGreaterThan(0)
    for (const call of calls) {
      expect((call.init?.method ?? "GET").toUpperCase()).toBe("GET")
      expect(call.init?.body).toBeUndefined()
    }
  })
})

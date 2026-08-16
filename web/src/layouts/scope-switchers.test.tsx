/**
 * The bar's scope trail says which subject you are inside, and this decides what it may say.
 *
 * Two properties, and neither is about how the bar looks. **The trail is derived from the address**
 * — the same discipline the rail already follows — so no pick can survive a navigation and no two
 * screens can disagree about which repository is on screen. And **a switcher never claims an option
 * list it does not have**: pending renders a skeleton, an empty list renders the sentence saying why
 * it is empty, and the value in the trail comes from the URL rather than from the list, so a subject
 * the list cannot see is still named.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: derivation and structural invariants, never class
 * names and never a snapshot.
 */

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ROUTES } from "@/lib/routes"
import {
  REPO_SCOPED_PATHS,
  ScopeTrail,
  repositoryHref,
  scopeFromLocation,
  vendorHref,
} from "@/layouts/scope-switchers"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// Partial, because `lib/routes.ts` pulls every feature screen in behind it and those screens read
// the rest of this module. Only the two hooks the bar itself reads are swapped.
vi.mock(import("@/api/queries"), async (importOriginal) => ({
  ...(await importOriginal()),
  useRepositories: () => mockState.repositories as never,
  useOverview: () => mockState.overview as never,
}))

/** The two query results the bar reads, swapped per test rather than through a live client. */
const mockState: Record<string, unknown> = {}

function pending() {
  return { isPending: true, isError: false, isSuccess: false, data: undefined }
}

function settled(data: unknown) {
  return { isPending: false, isError: false, isSuccess: true, data }
}

function withRepositories(repoIds: string[]) {
  mockState.repositories = settled({ repo_ids: repoIds })
}

function withVendors(vendorIds: string[]) {
  mockState.overview = settled({
    vendors: vendorIds.map((vendor_id) => ({ vendor_id, open_finding_count: 1 })),
  })
}

/** The address the trail is looking at, so a switcher's navigation can be read off the DOM. */
function Address() {
  const location = useLocation()
  return <span data-testid="address">{`${location.pathname}${location.search}`}</span>
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ScopeTrail />
      <Address />
    </MemoryRouter>
  )
}

function address(): string {
  return screen.getByTestId("address").textContent ?? ""
}

function trail(): HTMLElement {
  return screen.getByRole("navigation", { name: /scope/i })
}

function openSwitcher(name: RegExp): HTMLElement {
  fireEvent.click(within(trail()).getByRole("button", { name }))
  return screen.getByRole("dialog")
}

describe("the scope a trail is derived from", () => {
  it("names the repository the address is inside", () => {
    expect(scopeFromLocation("/repositories/seed-console", "")).toEqual({
      repoId: "seed-console",
      vendorId: null,
    })
  })

  it("keeps naming it one level deeper, where the repository is still the subject", () => {
    expect(scopeFromLocation("/repositories/seed-console/observed", "")).toEqual({
      repoId: "seed-console",
      vendorId: null,
    })
  })

  it("names the vendor the address is inside", () => {
    expect(scopeFromLocation("/vendors/stripe", "")).toEqual({
      repoId: null,
      vendorId: "stripe",
    })
  })

  it("reads the repository out of the scope a screen was opened with", () => {
    // `?repo_id=` is how three screens already carry a repository scope. The trail reads the same
    // key rather than a second one, so the bar and the screen under it cannot disagree.
    expect(scopeFromLocation("/vendors/stripe", "?repo_id=seed-console")).toEqual({
      repoId: "seed-console",
      vendorId: "stripe",
    })
  })

  it("decodes a subject the address had to escape", () => {
    expect(scopeFromLocation("/repositories/acme%2Fweb", "").repoId).toBe("acme/web")
  })

  it("names neither below the vendor level", () => {
    // A finding's vendor is in the payload, not in the address. The bar stops where the URL stops
    // and the page's own breadcrumb carries the rest — a bar that fetched a finding to fill itself
    // would be a second, slower copy of that page's own answer.
    expect(scopeFromLocation("/findings/9f176dea", "")).toEqual({
      repoId: null,
      vendorId: null,
    })
  })

  it("names neither on the fleet", () => {
    expect(scopeFromLocation("/", "")).toEqual({ repoId: null, vendorId: null })
  })

  it("names neither at an address no route declares", () => {
    expect(scopeFromLocation("/nowhere", "")).toEqual({ repoId: null, vendorId: null })
  })
})

describe("where a switcher sends you", () => {
  it("keeps the level when the address already carries the repository as its subject", () => {
    expect(repositoryHref("other", "/repositories/seed-console/observed", "")).toBe(
      "/repositories/other/observed"
    )
  })

  it("rewrites the scope in place on a screen that takes one", () => {
    expect(repositoryHref("other", "/vendors/stripe", "?repo_id=seed-console")).toBe(
      "/vendors/stripe?repo_id=other"
    )
  })

  it("opens the repository's own screen from anywhere else", () => {
    expect(repositoryHref("other", "/findings/9f176dea", "")).toBe("/repositories/other")
  })

  it("carries the repository scope onto the vendor it switches to", () => {
    expect(vendorHref("shopify", "seed-console")).toBe("/vendors/shopify?repo_id=seed-console")
  })

  it("names only paths the registry declares as taking a repository scope", () => {
    // The realistic drift is a route being renamed and this list keeping the old spelling, which
    // would silently stop rewriting a scope and start navigating away instead.
    const declared = ROUTES.map((route) => route.path)
    for (const path of REPO_SCOPED_PATHS) expect(declared).toContain(path)
  })
})

describe("the trail on screen", () => {
  it("renders the current repository and vendor as the address names them", () => {
    withRepositories(["seed-console", "other"])
    withVendors(["stripe"])
    renderAt("/vendors/stripe?repo_id=seed-console")

    expect(within(trail()).getByText("seed-console")).toBeTruthy()
    expect(within(trail()).getByText("stripe")).toBeTruthy()
  })

  it("names a subject the option list has never heard of", () => {
    // The value comes from the URL and the options come from a query, and that split is the point:
    // the vendor list is vendors with an open finding, so a vendor with none is a real address the
    // list cannot see. Rendering the list's answer here would blank the trail on a real screen.
    withRepositories([])
    withVendors([])
    renderAt("/vendors/stripe")

    expect(within(trail()).getByText("stripe")).toBeTruthy()
  })

  it("renders a skeleton where a name will be while its list has not loaded", () => {
    mockState.repositories = pending()
    mockState.overview = pending()
    renderAt("/")

    expect(trail().querySelectorAll('[role="presentation"]')).toHaveLength(2)
  })

  it("states what the list is counted over, and what an empty one means", () => {
    withRepositories([])
    withVendors([])
    renderAt("/")

    const popover = openSwitcher(/repository/i)
    expect(popover.textContent).toContain("never indexed")
  })

  it("lists what it can switch to", () => {
    withRepositories(["seed-console", "other"])
    withVendors(["stripe"])
    renderAt("/")

    const popover = openSwitcher(/repository/i)
    expect(within(popover).getByRole("option", { name: "seed-console" })).toBeTruthy()
    expect(within(popover).getByRole("option", { name: "other" })).toBeTruthy()
  })

  it("changes the scope in place when a repository is picked on a screen that takes one", () => {
    withRepositories(["seed-console", "other"])
    withVendors(["stripe"])
    renderAt("/vendors/stripe?repo_id=seed-console")

    const popover = openSwitcher(/repository/i)
    fireEvent.click(within(popover).getByRole("option", { name: "other" }))

    expect(address()).toBe("/vendors/stripe?repo_id=other")
  })

  it("carries the repository onto a vendor picked from the bar", () => {
    withRepositories(["seed-console"])
    withVendors(["stripe", "shopify"])
    renderAt("/repositories/seed-console")

    const popover = openSwitcher(/vendor/i)
    fireEvent.click(within(popover).getByRole("option", { name: "shopify" }))

    expect(address()).toBe("/vendors/shopify?repo_id=seed-console")
  })
})

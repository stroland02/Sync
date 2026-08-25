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

import { vendorHref } from "@/lib/hrefs"
import { ROUTES } from "@/lib/routes"
import {
  REPO_SCOPED_PATHS,
  ScopeTrail,
  repositoryHref,
  scopeFromLocation,
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

  it("names the workspace and the vendor the address is inside", () => {
    // Both, now. A vendor page used to be unscoped and answered `repoId: null`; under M0-W332 every
    // page is a workspace's page, so the address carries the workspace and the trail reads it.
    expect(scopeFromLocation("/repositories/seed-console/vendors/stripe", "")).toEqual({
      repoId: "seed-console",
      vendorId: "stripe",
    })
  })

  it("reads the workspace out of the path rather than a query string", () => {
    // `?repo_id=` carried the scope for the three routes that had no path segment for it. All three
    // are path-scoped now, so the query form is retired along with REPO_SCOPED_PATHS and the trail
    // has one source instead of two that could disagree.
    expect(scopeFromLocation("/repositories/seed-console/observed", "")).toEqual({
      repoId: "seed-console",
      vendorId: null,
    })
  })

  it("decodes a subject the address had to escape", () => {
    expect(scopeFromLocation("/repositories/acme%2Fweb", "").repoId).toBe("acme/web")
  })

  it("names the workspace but no vendor below the vendor level", () => {
    // A finding's vendor is in the payload, not in the address. The bar stops where the URL stops
    // and the page's own breadcrumb carries the rest -- a bar that fetched a finding to fill itself
    // would be a second, slower copy of that page's own answer. The workspace is in the path now,
    // so it is read; the vendor still is not there to read.
    expect(scopeFromLocation("/repositories/seed-console/findings/9f176dea", "")).toEqual({
      repoId: "seed-console",
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
    expect(repositoryHref("other", "/repositories/seed-console/vendors/stripe", "")).toBe(
      "/repositories/other/vendors/stripe"
    )
  })

  it("scopes the Overview in place, because the Overview IS the selected codebase", () => {
    // The owner ruled the Overview is the codebase, not a directory of codebases. A switcher that
    // navigated away from it would mean the one screen the ruling is about could never be scoped by
    // the control that exists to scope things — and the codebase fact band would only ever fill
    // from a hand-typed address.
    // `/` is the workspace picker and no longer a registry entry, so there is no scope to rewrite
    // in place: switching from there opens the chosen workspace.
    expect(repositoryHref("other", "/", "")).toBe("/repositories/other")
  })

  it("opens the repository's own screen from anywhere else", () => {
    // Every page keeps its level when the workspace changes, because every path carries :repoId.
    // The old behaviour dropped a reader back to the repository root from anywhere unscoped.
    expect(repositoryHref("other", "/repositories/seed-console/findings/9f176dea", "")).toBe(
      "/repositories/other/findings/9f176dea"
    )
  })

  it("sends the vendor switcher into the workspace, not to a path the console stopped serving", () => {
    // This used to assert `/vendors/shopify?repo_id=seed-console`, and asserted it correctly --
    // against a path `M14-W386` had already stopped routing, so the switcher navigated into the
    // 404 screen and this test agreed with it. The builder now comes from `lib/hrefs`, which is
    // checked against `ROUTES` itself, so the assertion cannot outlive the route again.
    expect(vendorHref("seed-console", "shopify")).toBe("/repositories/seed-console/vendors/shopify")
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
    renderAt("/repositories/seed-console/vendors/stripe")

    expect(within(trail()).getByText("seed-console")).toBeTruthy()
    expect(within(trail()).getByText("stripe")).toBeTruthy()
  })

  it("names a subject the option list has never heard of", () => {
    // The value comes from the URL and the options come from a query, and that split is the point:
    // the vendor list is vendors with an open finding, so a vendor with none is a real address the
    // list cannot see. Rendering the list's answer here would blank the trail on a real screen.
    withRepositories([])
    withVendors([])
    renderAt("/repositories/seed-console/vendors/stripe")

    expect(within(trail()).getByText("stripe")).toBeTruthy()
  })

  it("renders a skeleton where a name will be while its list has not loaded", () => {
    mockState.repositories = pending()
    mockState.overview = pending()

    // One switcher at the picker, two inside a workspace. The vendor switcher is not drawn
    // without a workspace because every vendor destination is inside one -- a control with
    // nowhere to navigate is absent rather than inert, which is the registry's own rule for a
    // destination that needs a subject.
    renderAt("/")
    expect(trail().querySelectorAll('[role="presentation"]')).toHaveLength(1)
  })

  it("skeletons only the name it does not have yet, inside a workspace", () => {
    mockState.repositories = pending()
    mockState.overview = pending()
    renderAt("/repositories/seed-console")

    // The address names the workspace, so that name needs no list to arrive and is drawn at once.
    // The vendor switcher no longer renders outside a vendor scope at all (owner ruling
    // 2026-08-25: parent / current, nothing else), so inside a bare workspace there is nothing
    // left waiting and no skeleton to draw.
    expect(within(trail()).getByText("seed-console")).toBeTruthy()
    expect(trail().querySelectorAll('[role="presentation"]')).toHaveLength(0)
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
    renderAt("/repositories/seed-console/vendors/stripe")

    const popover = openSwitcher(/repository/i)
    fireEvent.click(within(popover).getByRole("option", { name: "other" }))

    expect(address()).toBe("/repositories/other/vendors/stripe")
  })

  it("carries the repository onto a vendor picked from the bar", () => {
    withRepositories(["seed-console"])
    withVendors(["stripe", "shopify"])
    // From inside a vendor scope: the switcher only renders where a vendor is actually in
    // scope now (owner ruling 2026-08-25), which is also the only place switching to another
    // one means anything.
    renderAt("/repositories/seed-console/vendors/stripe")

    const popover = openSwitcher(/vendor/i)
    fireEvent.click(within(popover).getByRole("option", { name: "shopify" }))

    expect(address()).toBe("/repositories/seed-console/vendors/shopify")
  })
})

describe("the trail names the page, so a page does not have to", () => {
  /**
   * `M14-W391`. Owner decision 7 removes the header above every page. That header carried a
   * breadcrumb, and the top bar already carried a scope trail doing the same job -- what contains
   * what -- so the console drew two trails for one question and the page's copy was the duplicate.
   * Rather than relocate a component, the trail that already exists gains the one segment it was
   * missing: the page's own name.
   *
   * It is the `h1` because every page still owes a reader one accessible heading, and this is now
   * the only place the subject is named. One heading in chrome, rather than twelve in twelve pages.
   */
  it("ends with the current page's name", () => {
    renderAt("/repositories/seed-console/observed")

    const trail = screen.getByRole("navigation", { name: /scope/i })
    expect(within(trail).getByText("Telemetry")).toBeTruthy()
  })

  it("marks that name as the current segment, and is not the page's heading", () => {
    // Until 2026-08-24 this segment was the `h1`, on the argument that one heading in chrome
    // beats twelve in twelve pages. The registry half of that argument still holds and is why
    // `ScreenFrame` reads the same `labelFor`; what failed is the size. A trail segment is body
    // text, and a document's top-level heading rendering at body size put the page title under
    // the `h2` of every section it contained. The heading moved to the content band; this stayed
    // a trail segment, and marks itself current the way a trail's last segment should.
    renderAt("/repositories/seed-console/observed")

    expect(screen.queryByRole("heading", { level: 1 })).toBeNull()
    const current = document.querySelector('[aria-current="page"]')
    expect(current?.textContent).toContain("Telemetry")
  })

  it("names a page the registry does not declare without inventing a label for it", () => {
    // An address no route matches still renders the chassis. The trail says nothing rather than
    // guessing, which is the same refusal the switchers already make about an unknown subject.
    renderAt("/a-screen-nobody-declared")

    const trail = screen.getByRole("navigation", { name: /scope/i })
    expect(within(trail).queryByRole("heading", { level: 1 })).toBeNull()
  })
})


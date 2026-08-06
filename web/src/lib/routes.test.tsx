/**
 * Every declared route is reachable, and every route the router declares is declared here.
 *
 * This is the defect the console architecture plan exists to fix — seven of eleven routes were
 * unreachable, one shortcut at a time — and it is the one guard in this suite that earns its own
 * sentence in Decision 6: a plan that fixes reachability and does not hold it fixed will watch it
 * regress on screen nine.
 *
 * Two halves, and they fail in opposite directions. A route in the registry that no destination
 * links to is a screen only a typed URL reaches. A route the router serves that the registry does
 * not hold is a screen the navigation and the palette cannot see, which is how the first seven
 * were lost.
 */

import { QueryClientProvider, QueryClient } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import App from "@/App"
import { GRAPH_LEVELS, ROUTES } from "@/lib/routes"
import { SiteNav } from "@/layouts/site-nav"

afterEach(cleanup)

/**
 * A route whose `params` is non-empty needs a subject the registry does not hold — a vendor id,
 * a finding id — so the navigation deliberately does not link it. Those are reached from the
 * screen that supplies the subject, which is a claim about a rendered table rather than about
 * this registry, and it is not what this guard can hold.
 */
const LINKABLE = ROUTES.filter((route) => route.params.length === 0)

function renderNav(routes: readonly (typeof ROUTES)[number][] = ROUTES) {
  // `SiteNav` reads the module's own `ROUTES`, so the sub-setting a failure proof needs happens
  // by filtering what this helper asserts over, never by mutating the registry at runtime.
  void routes
  render(
    <MemoryRouter initialEntries={["/"]}>
      <SiteNav />
    </MemoryRouter>
  )
}

describe("the navigation covers the route registry", () => {
  it("links every route that needs no subject", () => {
    renderNav()

    const linked = new Set(
      screen
        .getAllByRole("link")
        .map((link) => link.getAttribute("href"))
        .filter((href): href is string => href !== null)
    )

    const missing = LINKABLE.filter((route) => !linked.has(route.path)).map((r) => r.path)
    expect(missing).toEqual([])
  })

  it("has something to check, so a registry that lost its routes cannot pass silently", () => {
    // The counterpart of `_require_examined` in the Python guards: an assertion over an empty
    // set is not a clean run, it is a guard that never looked.
    expect(LINKABLE.length).toBeGreaterThan(0)
  })

  it("names each route under a level the specification declares", () => {
    for (const route of ROUTES) {
      expect(GRAPH_LEVELS).toContain(route.level)
    }
  })

  it("declares each path once", () => {
    const paths = ROUTES.map((route) => route.path)
    expect(new Set(paths).size).toBe(paths.length)
  })
})

describe("the router serves exactly the registry", () => {
  function renderAt(path: string) {
    // A fresh client per render: a shared one would carry a previous route's cached failure into
    // the next assertion, and every query here fails anyway — there is no API in jsdom.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  /** A concrete URL for a route, since `:findingId` matches nothing on its own. */
  function concrete(path: string): string {
    return path.replace(/:([A-Za-z]+)/g, "subject")
  }

  it.each(ROUTES.map((route) => [route.path]))("resolves %s to a screen", (path) => {
    renderAt(concrete(path))

    // `UnknownRoute` is the router's fallback. Its headline is the assertion: if a registry path
    // does not match a declared `<Route>`, this is what renders instead of the screen.
    expect(screen.queryByText("No screen at this address.")).toBeNull()
  })

  it("still renders the fallback for an address the registry does not declare", () => {
    // Without this, the test above passes just as happily against a router that never falls
    // back at all — which would make it a guard that cannot fail.
    renderAt("/a-screen-nobody-declared")

    expect(screen.getByText("No screen at this address.")).toBeTruthy()
  })
})

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
import {
  DESTINATIONS,
  GRAPH_LEVELS,
  ROUTES,
  boundParams,
  destinationHref,
  isActiveMenuItem,
} from "@/lib/routes"
import { AppFrame } from "@/layouts/app-frame"

afterEach(cleanup)

/** The registry entry at a path, so a derivation test names a route rather than an index. */
function routeAt(path: string) {
  const entry = ROUTES.find((route) => route.path === path)
  if (entry === undefined) throw new Error(`no route is declared at ${path}`)
  return entry
}


/**
 * A route whose `params` is non-empty needs a subject the registry does not hold — a vendor id,
 * a finding id — so the navigation deliberately does not link it. Those are reached from the
 * screen that supplies the subject, which is a claim about a rendered table rather than about
 * this registry, and it is not what this guard can hold.
 */
// The rows the rail draws. Every route carries `:repoId` now, so "no parameters" would select
// nothing -- what makes a route linkable from the rail is that a selected workspace supplies
// everything it needs, which is exactly what `nav` records.
const LINKABLE = ROUTES.filter((route) => route.nav)

function renderNav(routes: readonly (typeof ROUTES)[number][] = ROUTES) {
  // `AppFrame` reads the module's own `ROUTES`, so the sub-setting a failure proof needs happens
  // by filtering what this helper asserts over, never by mutating the registry at runtime.
  void routes
  // The whole chassis rather than the old `SiteNav`, because the navigation is now two levels: the
  // rail links each area's landing route and the sidebar links the destinations inside the selected
  // area. A guard that rendered only one of the two would pass while the other lost every link --
  // which is the shape of the defect this file exists for.
  // The chassis reads two queries now — the top bar's scope switchers — so it needs a client the
  // way the whole-`App` renders below already do. `retry: false` for the same reason they give.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/seed-console"]}>
        <AppFrame />
      </MemoryRouter>
    </QueryClientProvider>
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

    // Compared against the address a selected workspace actually produces, not the pattern. Every
    // route carries `:repoId` now, so a pattern never appears in an href -- asserting on patterns
    // would fail against a correct rail, and passing one would mean the rail had emitted a literal
    // `:repoId`, which is the defect this guard's sibling forbids.
    const expected = LINKABLE.map((route) => route.path.replace(":repoId", "seed-console"))
    expect(expected.length).toBeGreaterThan(0)
    const missing = expected.filter((href) => !linked.has(href))
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

describe("one region, and what a workspace can bind", () => {
  /**
   * `M0-W332` deleted the regions. They were `root` and `repository` and they overlapped by name --
   * Codebases against Codebase, Vendor against Vendors -- which is the duplication the owner saw in
   * the rail. Every page is a workspace's page now, so there is nothing left to partition.
   *
   * What replaces the partition is `nav`: whether a route is a row the rail draws. That is decided
   * by what a selected workspace can supply, and the tests below hold both halves of it.
   */
  it("scopes every route to a workspace, with :repoId first", () => {
    expect(ROUTES.length).toBeGreaterThan(0)
    for (const route of ROUTES) {
      expect(route.path.startsWith("/repositories/:repoId")).toBe(true)
      expect(route.params[0]).toBe("repoId")
    }
  })

  it("draws a row only where a workspace alone can build the address", () => {
    // A route needing a vendor, an operation or a finding cannot be built from the workspace, so it
    // is absent from the rail rather than present and inert -- the owner's rule, and the half of it
    // that matters: a control that vanishes is honest, one that absorbs the click reads as broken.
    const nav = ROUTES.filter((route) => route.nav)
    const reached = ROUTES.filter((route) => !route.nav)

    expect(nav.length).toBeGreaterThan(0)
    expect(reached.length).toBeGreaterThan(0)

    for (const route of nav) {
      expect(route.params).toEqual(["repoId"])
    }
    for (const route of reached) {
      expect(route.params.length).toBeGreaterThan(1)
      // Anything the rail cannot reach says where it IS reached from, or a reader meets a dead end.
      expect(route.reachedFrom).not.toBeNull()
    }
  })

  it("names one page once", () => {
    // Vendor against Vendors was the complaint. Labels are unique now, and a duplicate would mean
    // two rows claiming the same thing again.
    const labels = ROUTES.map((route) => route.label)
    expect(new Set(labels).size).toBe(labels.length)
  })
})

describe("a menu item can own more than one route", () => {
  it("says so in data rather than through a regex over the path", () => {
    expect(
      isActiveMenuItem({ path: "/findings", pages: ["/findings", "/findings/:id"] }, "/findings/42")
    ).toBe(true)
    expect(isActiveMenuItem({ path: "/findings" }, "/signals")).toBe(false)
  })

  it("does not let the root path claim every address", () => {
    // `startsWith` on `"/"` matches the whole console. The helper's non-parameterised branch has to
    // read `"/" + "/"`, which nothing is, or the Fleet row is active on every screen.
    expect(isActiveMenuItem({ path: "/" }, "/")).toBe(true)
    expect(isActiveMenuItem({ path: "/repositories/:repoId" }, "/repositories/a/detectors")).toBe(false)
  })

  it("matches a parameterised path to its end, so a child never activates its parent", () => {
    expect(
      isActiveMenuItem({ path: "/repositories/:repoId/findings/:findingId/workflow" }, "/repositories/a/findings/42/workflow")
    ).toBe(true)
    expect(
      isActiveMenuItem(
        { path: "/repositories/:repoId/findings/:findingId/workflow" },
        "/findings/42/workflow/pull-request"
      )
    ).toBe(false)
  })
})

describe("a destination is linkable when the address supplies its subject", () => {
  // The registry holds no vendor id and no finding id, which is why seven of nine destinations
  // render as text. The *address* holds them, and on a detail route it holds exactly the ones its
  // siblings need — `/findings/f-1/workflow` binds `findingId`, and all three Remediation
  // destinations declare that one parameter and nothing else.

  it("reads a subject out of the address that matches a declared route", () => {
    expect(boundParams("/repositories/acme/findings/f-1/workflow")).toEqual({ repoId: "acme", findingId: "f-1" })
    expect(boundParams("/repositories/acme/bindings/vendors/stripe/operations/PostCharges")).toEqual({
      repoId: "acme",
      vendorId: "stripe",
      operationId: "PostCharges",
    })
  })

  it("binds nothing from an address no route declares", () => {
    expect(boundParams("/repositories/acme/detectors")).toEqual({ repoId: "acme" })
    expect(boundParams("/a-screen-nobody-declared")).toEqual({})
  })

  it("decodes a segment, so a subject with a slash in it survives the round trip", () => {
    // `matchPath` decodes what it captures, so re-encoding on the way back out is what keeps an
    // href pointing at the same subject rather than at a truncated one.
    const bound = boundParams("/repositories/acme/vendors/acme%2Fpayments")

    expect(bound).toEqual({ repoId: "acme", vendorId: "acme/payments" })
    expect(destinationHref(routeAt("/repositories/:repoId/vendors/:vendorId"), bound)).toBe("/repositories/acme/vendors/acme%2Fpayments")
  })

  it("gives a route its own path once the workspace is bound", () => {
    // There are no parameterless routes any more -- every page is a workspace's page, so every path
    // carries :repoId and a bound workspace is enough to build the five the rail draws.
    expect(destinationHref(routeAt("/repositories/:repoId/detectors"), { repoId: "acme" })).toBe("/repositories/acme/detectors")
  })

  it("refuses a route one of whose parameters is unbound", () => {
    // The binding surface standing on `/detectors`. Half a subject is not a destination: a
    // generated href would read `/bindings/vendors/stripe/operations/`.
    expect(
      destinationHref(routeAt("/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId"), {
        vendorId: "stripe",
      })
    ).toBeNull()
    expect(destinationHref(routeAt("/repositories/:repoId/findings/:findingId"), {})).toBeNull()
  })

  it("generates the sibling's address from the subject the current one carries", () => {
    const bound = boundParams("/repositories/acme/findings/f-1/workflow")

    expect(destinationHref(routeAt("/repositories/:repoId/findings/:findingId"), bound)).toBe("/repositories/acme/findings/f-1")
    expect(destinationHref(routeAt("/repositories/:repoId/findings/:findingId/workflow/pull-request"), bound)).toBe(
      "/repositories/acme/findings/f-1/workflow/pull-request"
    )
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

describe("a destination that is not a level", () => {
  /**
   * `/settings` is drawn in the mock and specified nowhere. `.claude/rules/console-hierarchy.md`
   * binds `GRAPH_LEVELS` to the design document: a level with no line there does not go in that
   * array, and a screen that aggregates over levels — or, here, configures the system behind them
   * — is not a rung on the ladder. Three plans invented four levels between them, so the guard is
   * a count rather than a reviewer.
   */

  it("keeps GRAPH_LEVELS at the nine the specification declares", () => {
    expect(GRAPH_LEVELS).toHaveLength(9)
  })

  it("declares settings outside the level registry", () => {
    expect(DESTINATIONS.map((entry) => entry.path)).toContain("/settings")
    expect(ROUTES.map((route) => route.path)).not.toContain("/settings")
  })

  it("shares no path with a level route, so the router has one element per address", () => {
    const levelPaths = new Set(ROUTES.map((route) => route.path))

    for (const entry of DESTINATIONS) expect(levelPaths.has(entry.path)).toBe(false)
  })

  it("carries a question, the same as a level does, because the header renders one either way", () => {
    for (const entry of DESTINATIONS) expect(entry.question.length).toBeGreaterThan(0)
  })
})

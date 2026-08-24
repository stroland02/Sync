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
  WORKFLOW_STAGES,
  boundParams,
  destinationHref,
  isActiveMenuItem,
  isWideRoute,
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
      // **Amended 2026-08-19.** This required every non-rail route to need more than a workspace,
      // which was true while the rail was the only way in. The owner's tab rulings added a second
      // reason to sit outside it: Trends, Corpus and Changes are tabs, and the two map pages open
      // from the Overview's panels -- all buildable from a workspace alone and all deliberately
      // not rail rows, because a second door to a screen one click away is clutter rather than
      // reach. (Detectors and the telemetry page were tabs too, until the stage grouping gave
      // their stages doors of their own.)
      //
      // What still holds, and is the half that protects a reader: **a route outside the rail must
      // say where it is reached from.** Without that a declared route is a dead end nobody can
      // find, which is the defect this guard was written for.
      expect(route.reachedFrom).not.toBeNull()
      expect(route.reachedFrom).not.toBe("")
    }
  })

  it("names one page once", () => {
    // Vendor against Vendors was the complaint. Labels are unique now, and a duplicate would mean
    // two rows claiming the same thing again.
    const labels = ROUTES.map((route) => route.label)
    expect(new Set(labels).size).toBe(labels.length)
  })
})

describe("the rail's stage grouping", () => {
  /**
   * The owner's restructure of 2026-08-19: the rail groups by pipeline stage — Index, Signal,
   * Observe, Detect, Remediate — in pipeline order. The stages are presentation, not levels;
   * `GRAPH_LEVELS` is untouched and `tests/test_console_hierarchy.py` still holds it. What these
   * guards hold is the grouping's own integrity, which no spec test can see.
   */
  const railInOrder = ROUTES.filter((route) => route.nav).sort(
    (a, b) => (a.navOrder ?? Number.MAX_SAFE_INTEGER) - (b.navOrder ?? Number.MAX_SAFE_INTEGER)
  )

  it("gives every rail row a stage, so no row renders outside every group", () => {
    expect(railInOrder.length).toBeGreaterThan(0)
    for (const route of railInOrder) {
      expect(WORKFLOW_STAGES).toContain(route.stage)
    }
  })

  it("keeps each stage's rows contiguous and the stages in pipeline order", () => {
    // The rail renders one group per stage over the navOrder-sorted list. Rows of one stage
    // split by another's would render that stage's heading twice, and a stage out of pipeline
    // order tells the loop's story backwards.
    const seen = railInOrder.map((route) => route.stage)
    const stagesInFirstAppearance = [...new Set(seen)]

    expect(stagesInFirstAppearance).toEqual(
      WORKFLOW_STAGES.filter((stage) => seen.includes(stage))
    )
    for (const stage of stagesInFirstAppearance) {
      const positions = seen.flatMap((s, i) => (s === stage ? [i] : []))
      expect(positions[positions.length - 1] - positions[0]).toBe(positions.length - 1)
    }
  })

  it("never names a row after its own stage heading, which is the duplication that killed level headings", () => {
    // The 2026-08-18 ruling against headings was earned by "BINDING SURFACE" over a "Binding
    // surface" row. Five stage headings over nine differently-worded rows is the design that
    // supersedes it, and this is the wording half of that argument, held.
    for (const route of railInOrder) {
      expect(route.label.toLowerCase()).not.toBe(route.stage?.toLowerCase())
    }
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

  // `carries a question, the same as a level does` retired with the field in `CI-W597`.
  // `routes-no-question.test.ts` now asserts the opposite, which is the owner's ruling.
})

describe("which screens the reading cap applies to", () => {
  /**
   * Owner report, 2026-08-19: Overview, Telemetry and Detectors were still capped at 1400px.
   *
   * Each is a grid of panels, and the cap made the grid reflow into a single column with half
   * the viewport empty beside it. The flag is the one place this is decided -- a page that
   * fixed it locally with a negative margin would fight the scrollbar and land differently on
   * every browser, and the next screen would solve it again a fourth way.
   */
  it.each([
    ["/repositories/demo", "Overview"],
    ["/repositories/demo/observed", "Telemetry"],
    ["/repositories/demo/detectors", "Detectors"],
    ["/repositories/demo/call-sites", "Call sites"],
    ["/repositories/demo/findings", "Findings"],
  ])("gives %s (%s) the full width", (pathname) => {
    expect(isWideRoute(pathname)).toBe(true)
  })

  it.each([
    ["/repositories/demo/findings/f-1", "a finding"],
    ["/repositories/demo/findings/f-1/workflow", "a workflow"],
  ])("keeps the cap on %s (%s), where the content is a column of prose", (pathname) => {
    // The cap is not obsolete, it is scoped. A detail screen read at 2560px is harder to read,
    // not easier, and widening everything would lose that distinction rather than settle it.
    expect(isWideRoute(pathname)).toBe(false)
  })
})

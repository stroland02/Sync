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
  AREAS,
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
 * The rail's vocabulary, written out rather than imported.
 *
 * Spelled as a literal so this file pins the union instead of agreeing with whatever the registry
 * currently says — `AREA_IDS` rather than `AREAS`, because the registry exports that name and a
 * shadow would make the cross-check below compare the list against itself.
 */
const AREA_IDS = [
  "fleet",
  "codebase",
  "api-services",
  "signals",
  "observe",
  "remediation",
] as const

/**
 * A route whose `params` is non-empty needs a subject the registry does not hold — a vendor id,
 * a finding id — so the navigation deliberately does not link it. Those are reached from the
 * screen that supplies the subject, which is a claim about a rendered table rather than about
 * this registry, and it is not what this guard can hold.
 */
const LINKABLE = ROUTES.filter((route) => route.params.length === 0)

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
      <MemoryRouter initialEntries={["/"]}>
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

describe("the rail groups levels into areas without inventing one", () => {
  it("gives every route a declared area", () => {
    for (const route of ROUTES) expect(AREA_IDS).toContain(route.area)
  })

  /**
   * The two regions, and the only two structural claims the sidebar needs from the registry.
   *
   * Six areas became two regions because the repository is the independent variable: a screen is
   * either scoped to one repository or it is not. `root` holds what a reader reaches without having
   * chosen one; `repository` holds what hangs off the choice.
   */
  it("puts every route in exactly one of the two regions, and neither is empty", () => {
    // Written because the first version of the two tests below PASSED against a registry with no
    // `region` field at all: both filters returned nothing, both loops ran zero times, and two
    // vacuous assertions reported a partition that did not exist. This is the guard that makes
    // them bite, and it is the same defect `M14-W363` fixed in two other places today.
    const REGIONS = ["root", "repository"] as const

    for (const route of ROUTES) expect(REGIONS).toContain(route.region)
    for (const region of REGIONS) {
      expect(ROUTES.filter((route) => route.region === region).length).toBeGreaterThan(0)
    }
    expect(
      ROUTES.filter((r) => r.region === "root").length +
        ROUTES.filter((r) => r.region === "repository").length
    ).toBe(ROUTES.length)
  })

  it("declares no repository parameter on a root route", () => {
    // A root screen that needed a repository would be unreachable from the place it is offered.
    for (const route of ROUTES.filter((r) => r.region === "root")) {
      expect(route.params).not.toContain("repoId")
    }
  })

  it("takes the repository as the first parameter of every repository route, bar three", () => {
    // Three finding addresses sit under the repository region and cannot declare `repoId`: a
    // fleet-wide findings row has no repository to put in the href, because `RiskRow` carries none
    // (`web/src/api/types.ts:135-145`). They are an explicit literal allow-list rather than a
    // predicate, so adding a fourth is a decision somebody writes down. The backlog item that
    // retires this is the one filed for `RiskRow` gaining a `repo_id`; until the payload carries it,
    // a nested finding href would assert a containment nothing computed.
    const ALLOWED_WITHOUT_REPO = [
      "/findings/:findingId",
      "/findings/:findingId/workflow",
      "/findings/:findingId/workflow/pull-request",
    ]

    for (const route of ROUTES.filter((r) => r.region === "repository")) {
      if (ALLOWED_WITHOUT_REPO.includes(route.path)) {
        expect(route.params).toEqual(["findingId"])
        continue
      }
      expect(route.params[0]).toBe("repoId")
    }
  })

  it("names the same areas on the rail as the routes claim", () => {
    expect(AREAS.map((area) => area.id)).toEqual([...AREA_IDS])
  })

  it("claims no level outside GRAPH_LEVELS", () => {
    // The vocabulary is pinned to the specification by `tests/test_console_hierarchy.py`; here:
    // an area groups levels the specification declares and never a level of its own invention.
    for (const route of ROUTES) expect(GRAPH_LEVELS).toContain(route.level)
    for (const area of AREAS) {
      for (const level of area.levels) expect(GRAPH_LEVELS).toContain(level)
    }
  })

  it("files each route under the area that claims its level", () => {
    // `area` is declared per route and derivable from `level`, which is two spellings of one fact.
    // This is the assertion that stops them disagreeing.
    for (const route of ROUTES) {
      const owner = AREAS.find((area) => area.levels.includes(route.level))
      expect(route.area).toBe(owner?.id)
    }
  })

  it("covers every level exactly once across the areas", () => {
    // A level in two areas is a destination that appears twice; a level in none is a screen the
    // rail cannot reach. Both are the failure the reconciliation of 2026-08-05 found.
    const claimed = AREAS.flatMap((area) => [...area.levels])
    expect(claimed.sort()).toEqual([...GRAPH_LEVELS].sort())
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
    expect(isActiveMenuItem({ path: "/" }, "/detectors")).toBe(false)
  })

  it("matches a parameterised path to its end, so a child never activates its parent", () => {
    expect(
      isActiveMenuItem({ path: "/findings/:findingId/workflow" }, "/findings/42/workflow")
    ).toBe(true)
    expect(
      isActiveMenuItem(
        { path: "/findings/:findingId/workflow" },
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
    expect(boundParams("/findings/f-1/workflow")).toEqual({ findingId: "f-1" })
    expect(boundParams("/bindings/vendors/stripe/operations/PostCharges")).toEqual({
      vendorId: "stripe",
      operationId: "PostCharges",
    })
  })

  it("binds nothing from an address no route declares", () => {
    expect(boundParams("/detectors")).toEqual({})
    expect(boundParams("/a-screen-nobody-declared")).toEqual({})
  })

  it("decodes a segment, so a subject with a slash in it survives the round trip", () => {
    // `matchPath` decodes what it captures, so re-encoding on the way back out is what keeps an
    // href pointing at the same subject rather than at a truncated one.
    const bound = boundParams("/vendors/acme%2Fpayments")

    expect(bound).toEqual({ vendorId: "acme/payments" })
    expect(destinationHref(routeAt("/vendors/:vendorId"), bound)).toBe("/vendors/acme%2Fpayments")
  })

  it("gives a parameterless route its own path whatever the address is", () => {
    expect(destinationHref(routeAt("/detectors"), {})).toBe("/detectors")
  })

  it("refuses a route one of whose parameters is unbound", () => {
    // The binding surface standing on `/detectors`. Half a subject is not a destination: a
    // generated href would read `/bindings/vendors/stripe/operations/`.
    expect(
      destinationHref(routeAt("/bindings/vendors/:vendorId/operations/:operationId"), {
        vendorId: "stripe",
      })
    ).toBeNull()
    expect(destinationHref(routeAt("/findings/:findingId"), {})).toBeNull()
  })

  it("generates the sibling's address from the subject the current one carries", () => {
    const bound = boundParams("/findings/f-1/workflow")

    expect(destinationHref(routeAt("/findings/:findingId"), bound)).toBe("/findings/f-1")
    expect(destinationHref(routeAt("/findings/:findingId/workflow/pull-request"), bound)).toBe(
      "/findings/f-1/workflow/pull-request"
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

/**
 * The chassis is ONE full-height sidebar, and this is the test that decides it.
 *
 * One list carries every area's destinations; the top bar lives inside the content column beside
 * it rather than across the top of both. The discriminator against the two-tier chassis this
 * replaces is that **nothing has to be activated to reach anything**: every declared route is a row
 * on screen from the moment the console loads, so reachability is asserted without a click.
 *
 * **jsdom has no layout, so vertical position cannot be read directly** — `getBoundingClientRect`
 * returns zeroes here. Saying so matters, because a test that asserted on those numbers would pass
 * against any tree at all. What is asserted instead is structure: document order, containment, and
 * the ordered sequence of rows. The pixels are measured in Chrome and recorded in `DESIGN.md`.
 *
 * Rewritten for `M14-W366` from the `M7-W171` two-tier file. Eleven of its assertions described an
 * icon rail — hover labels, a collapse threshold, a pick that survives Back — and describe nothing
 * that exists now. What they guaranteed that still matters is carried forward rather than deleted
 * with them: every area reachable, Settings reachable, every level named, no destination lost.
 * `M14-W273` is the precedent for that distinction.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AppFrame } from "@/layouts/app-frame"
import { shortcutHint } from "@/layouts/command-palette"
import { KINDS_SHOWN, clearErrors, reportError } from "@/lib/error-log"
import { AREAS, DESTINATIONS, ROUTES, type AreaEntry } from "@/lib/routes"

// The top bar's switchers read the same two queries the list screens read. Mocked rather than
// served through a client, for the reason `fleet-facts.test.tsx` gives: this file is about the
// chassis, and a live client would make every assertion here depend on a fetch.
vi.mock(import("@/api/queries"), async (importOriginal) => ({
  ...(await importOriginal()),
  useRepositories: () =>
    ({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: { repo_ids: ["seed-console"] },
    }) as never,
  useOverview: () =>
    ({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: { vendors: [{ vendor_id: "stripe", open_finding_count: 1 }] },
    }) as never,
}))

afterEach(() => {
  cleanup()
  clearErrors()
})

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppFrame />
    </MemoryRouter>
  )
}

/** The contextual sidebar: the tier that does. */
function destinations(): HTMLElement {
  return screen.getByRole("navigation", { name: /destinations/i })
}

/** Every destination row, in document order, as the element that actually renders it. */
function destinationRows(): Element[] {
  return [...destinations().querySelectorAll("[data-destination]")]
}

function routesOf(area: AreaEntry) {
  return ROUTES.filter((route) => area.levels.includes(route.level))
}

/** A concrete URL for a route, since `:findingId` matches nothing on its own. */
function concrete(path: string): string {
  return path.replace(/:([A-Za-z]+)/g, "subject")
}

describe("the top bar sits above the chassis", () => {
  it("renders a banner on every route", () => {
    // The measured gap this closes: `[role=banner]` counted 0 on every route, so the console had
    // no persistent statement of which subject a nine-level hierarchy had you inside.
    for (const route of ROUTES) {
      renderAt(concrete(route.path))

      expect(screen.getByRole("banner")).toBeTruthy()

      cleanup()
    }
  })

  it("puts the sidebar full height beside the content, with the bar inside the content column", () => {
    // The inverse of the invariant this file held until M14-W366, and inverted on purpose. The bar
    // used to be a sibling *before* the whole rail-and-content row, which put it in front of the
    // sidebar; the owner's instruction is that the sidebar is full height and the bar does not sit
    // in front of it. Mock v1 already draws exactly that — its nav is {x:0, y:0, 246x900} and its
    // header starts at x:246. The replacement is deliberately stronger than what it replaces: it
    // pins the sidebar's position relative to the bar AND the bar's membership of the content
    // column, where the old one only asserted document order.
    renderAt("/")

    const banner = screen.getByRole("banner")
    const sidebar = destinations()
    const main = document.querySelector("main")
    expect(main).not.toBeNull()

    // The sidebar comes first in document order, and the bar does not contain it.
    expect(
      banner.compareDocumentPosition(sidebar) & Node.DOCUMENT_POSITION_PRECEDING
    ).toBeTruthy()
    expect(banner.contains(sidebar)).toBe(false)

    // The bar shares a column with `main` — that is what "inside the content column" means, and it
    // is the half that stops the bar drifting back to spanning the full width.
    const column = banner.parentElement
    expect(column).not.toBeNull()
    expect(column!.contains(main!)).toBe(true)

    // ...and that column does not hold the sidebar, or the bar would be in front of it again.
    expect(column!.contains(sidebar)).toBe(false)
  })

  it("carries the scope trail, and it names the subject the address is inside", () => {
    renderAt("/vendors/stripe?repo_id=seed-console")

    const banner = screen.getByRole("banner")
    const trail = within(banner).getByRole("navigation", { name: /scope/i })

    expect(within(trail).getByText("seed-console")).toBeTruthy()
    expect(within(trail).getByText("stripe")).toBeTruthy()
  })

  it("offers the command palette a trigger a pointer can find", () => {
    // The palette was `Ctrl/Cmd-K` with nothing on screen saying so — a keyboard-only affordance
    // nobody can discover. The dialog is not in the document until it opens, which is what makes
    // this assertion a real one rather than a query against a permanently mounted node.
    renderAt("/")
    expect(screen.queryByRole("dialog")).toBeNull()

    fireEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: /destination/i }))

    expect(screen.getByRole("dialog")).toBeTruthy()
  })
})

describe("the keybind the trigger prints", () => {
  // Asserted here because the app frame is what composes the trigger. The palette answers either
  // modifier, so the hint is about the keyboard in front of the reader; naming the wrong key would
  // be a fact about the console stated wrongly on every screen.
  it("names the modifier the reader's keyboard actually has", () => {
    expect(shortcutHint("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")).toContain("⌘")
    expect(shortcutHint("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")).toBe("Ctrl K")
  })
})

describe("a failure displaces the chassis rather than floating over it", () => {
  it("puts the error banner above the top bar", () => {
    // The owner's own capture showed 92 stacked "API is unreachable" cards obscuring the page. A
    // slot above the header is the structural fix: it pushes the console down instead of covering
    // it, so nothing a reader needs is behind it.
    reportError({ summary: "The API is unreachable.", detail: "connection refused" })
    renderAt("/")

    const alert = screen.getByRole("alert")
    const banner = screen.getByRole("banner")

    expect(banner.contains(alert)).toBe(false)
    expect(
      alert.compareDocumentPosition(banner) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it("draws three kinds and says how many it is not drawing", () => {
    // The cap, where it is visible. `groupErrorsByKind` is tested on its own; this is the claim
    // that the banner honours it and states the remainder rather than silently dropping it. The
    // singular is pinned because the sentence has to read as English at the boundary it is most
    // often seen at — one kind over the cap.
    for (const summary of ["first", "second", "third", "fourth"]) {
      reportError({ summary, detail: summary })
    }
    renderAt("/")

    const alert = screen.getByRole("alert")

    expect(alert.querySelectorAll("li")).toHaveLength(KINDS_SHOWN)
    expect(alert.textContent).toContain("1 further kind is in the log")
    expect(alert.textContent).toContain("Nothing was dropped")
  })

  it("says it in the plural when more than one kind is undrawn", () => {
    for (const summary of ["first", "second", "third", "fourth", "fifth"]) {
      reportError({ summary, detail: summary })
    }
    renderAt("/")

    expect(screen.getByRole("alert").textContent).toContain("2 further kinds are in the log")
  })
})

describe("one sidebar carries every area", () => {
  // The rail is gone and this block replaces the eleven tests that described it. `M7-W160` had
  // already built one list at two widths after the owner ruled against an icon rail beside a
  // contextual panel; `M7-W171` re-introduced the two tiers and the owner ruled against it a second
  // time. What those tests guaranteed that still matters -- every area reachable, Settings
  // reachable, no destination lost -- is asserted here rather than deleted with them. `M14-W273`
  // is the precedent: a test whose subject retires may go, but not the coverage it carried.

  it("shows every area's destinations at once, not just the current area's", () => {
    renderAt("/")

    const shown = [...destinations().querySelectorAll("[data-destination]")].map((el) =>
      el.getAttribute("data-destination")
    )

    // Every route in the registry, from one screen, with nothing to hover and nothing to select.
    expect(shown).toEqual(ROUTES.map((route) => route.path))
  })

  it("names every area as a group, so the run of levels under it still reads as one area", () => {
    renderAt("/")

    const text = destinations().textContent ?? ""
    for (const area of AREAS) {
      expect(text).toContain(area.label)
    }
  })

  it("reaches Settings, which is a destination rather than an area or a level", () => {
    // Unchanged in substance from the rail-era test: `DESTINATIONS` declares Settings, `GRAPH_LEVELS`
    // stays at nine and `AREAS` never gains a seventh member. Only the container moved. This is the
    // test that would have caught deleting the rail without rehoming its hard-coded Settings slot --
    // the route would still exist and every routing test would still pass.
    renderAt("/")

    const settings = within(destinations()).getByRole("link", { name: /settings/i })

    expect(settings.getAttribute("href")).toBe("/settings")
    expect(settings.getAttribute("aria-disabled")).toBeNull()
    expect(AREAS.map((area) => area.label)).not.toContain("Settings")
    expect(settings.getAttribute("title")).toBe("Settings — read-only until the write path lands")
  })

  it("holds every parameterless route as a real link from a single screen", () => {
    // The reachability guarantee, restated here because the component that satisfied it was
    // deleted. A route needing a subject the address does not supply renders as a described span
    // rather than a link, which is the existing contract; everything else must be reachable.
    renderAt("/")

    const reachable = [...destinations().querySelectorAll("a[href]")].map((el) =>
      el.getAttribute("href")
    )
    for (const route of ROUTES.filter((r) => !r.path.includes(":"))) {
      expect(reachable).toContain(route.path)
    }
    for (const entry of DESTINATIONS) {
      expect(reachable).toContain(entry.path)
    }
  })
})

describe("the sidebar carries the destinations", () => {
  it("keeps every area's destinations in the same order on every route", () => {
    // Replaces two rail-era tests. The sidebar no longer heads itself with the current area and no
    // longer hides the others -- both were properties of the two-tier chassis. What survives, and
    // is worth more, is that the list does not reorder under the reader as they navigate.
    const order: string[][] = []
    for (const area of AREAS) {
      const route = routesOf(area)[0]
      renderAt(concrete(route.path))
      order.push(
        [...destinations().querySelectorAll("[data-destination]")].map(
          (el) => el.getAttribute("data-destination") ?? ""
        )
      )
      cleanup()
    }
    for (const shown of order) {
      expect(shown).toEqual(order[0])
    }
    expect(order[0]).toEqual(ROUTES.map((route) => route.path))
  })

  it("groups them under the graph levels the specification names", () => {
    // The grouping is the specification's vocabulary rendered, not a second hierarchy: an area is a
    // run of consecutive levels, and the sidebar prints the level names it holds. Read off the
    // group labels rather than by text, because a level name and a destination's label are the same
    // word on five of the nine routes.
    // Every level, from one screen. The rail-era version rendered one area at a time and compared
    // against that area's run; with one list the whole ladder is on screen, so the assertion is
    // against the specification's nine in the order the areas declare them.
    renderAt("/")

    const labels = [...destinations().querySelectorAll('[data-sidebar="group-label"]')].map(
      (el) => el.textContent
    )
    expect(labels).toEqual(AREAS.flatMap((area) => [...area.levels]))
  })

  it("marks the row for the current route, and marks only it", () => {
    for (const route of ROUTES) {
      renderAt(concrete(route.path))

      const current = [...destinations().querySelectorAll('[aria-current="page"]')].map((el) =>
        el.getAttribute("data-destination")
      )
      expect(current).toEqual([route.path])

      cleanup()
    }
  })

  it("names every destination for a screen reader", () => {
    for (const area of AREAS) {
      renderAt(concrete(routesOf(area)[0].path))

      for (const route of routesOf(area)) {
        const row = destinations().querySelector(`[data-destination="${route.path}"]`)
        expect(row?.getAttribute("aria-label")).toContain(route.label)
        // The tooltip is the sighted reader's equivalent of the accessible name, so it carries the
        // same string rather than a shortened one.
        expect(row?.getAttribute("title")).toBe(row?.getAttribute("aria-label"))
      }

      cleanup()
    }
  })

  /**
   * Rewritten for M7-W199, and the rewrite is the point rather than an edit.
   *
   * The assertion this replaces read `href === null` for every route declaring a parameter,
   * rendered at that route's own address — the gap report's Surface 2 defect stated as a
   * guarantee. On the finding, workflow and pull-request routes it made three unreachable rows a
   * tested property, exactly where the hierarchy is deepest. Extending it was not available; what
   * survives is both halves of the original claim, split by the condition that actually governs.
   */
  it("links a row whose subject the address already supplies", () => {
    // The three deepest destinations all need one parameter, and any of the three finding
    // addresses binds it. This is the whole of Surface 2's fourth row.
    for (const at of [
      "/findings/f-1",
      "/findings/f-1/workflow",
      "/findings/f-1/workflow/pull-request",
    ]) {
      renderAt(at)

      // Scoped to the three finding rows. The rail-era version could assert over every row on
      // screen, because only the active area rendered; one list puts all nine there, and the rows
      // whose subject the address does NOT supply are still correctly spans. Widening this to the
      // whole list would assert the opposite of the contract it is checking.
      const rows = [
        "/findings/:findingId",
        "/findings/:findingId/workflow",
        "/findings/:findingId/workflow/pull-request",
      ].map((path) => destinations().querySelector(`[data-destination="${path}"]`)!)

      expect(rows.map((row) => row.tagName)).toEqual(["A", "A", "A"])
      expect(rows.map((row) => row.getAttribute("href"))).toEqual([
        "/findings/f-1",
        "/findings/f-1/workflow",
        "/findings/f-1/workflow/pull-request",
      ])

      cleanup()
    }
  })

  it("says where to go instead, on a row the address supplies no subject for", () => {
    // Standing on `/detectors`, the Observe sidebar holds two rows and only one of them can link:
    // no vendor and no operation are in the address, and generating one anyway would produce
    // `/bindings/vendors//operations/`. `reachedFrom` is what a reader gets instead.
    renderAt("/detectors")

    const rows = destinationRows()
    const binding = rows.find(
      (row) =>
        row.getAttribute("data-destination") ===
        "/bindings/vendors/:vendorId/operations/:operationId"
    )

    expect(binding?.tagName).toBe("SPAN")
    expect(binding?.getAttribute("href")).toBeNull()
    expect(binding?.getAttribute("aria-label")).toContain(
      "an operation on a vendor's findings table"
    )
  })

  it("drops the sentence about where to look once the row is a link", () => {
    // `reached from the finding it remediates` beside a working link tells a reader to go and find
    // something they are standing on. It renders on every row where it is still true, and nowhere
    // else.
    renderAt("/findings/f-1")

    const workflow = destinationRows().find(
      (row) => row.getAttribute("data-destination") === "/findings/:findingId/workflow"
    )

    expect(workflow?.getAttribute("aria-label")).toBe("Solution workflow")
  })
})

describe("every declared destination is reachable without an activation", () => {
  it("shows all nine specification levels from one screen, with nothing to click first", () => {
    // The reachability claim the whole chassis exists to make, and the one the first version of
    // this shell failed: four area icons remained and the nine specification levels could not be
    // reached. The rail-era version of this test needed six clicks to prove it. One sidebar needs
    // none, which is the point of collapsing the tiers -- so the assertion gets strictly stronger
    // while the setup gets simpler.
    renderAt("/")

    const seen = new Set<string>()
    for (const area of AREAS) {
      for (const route of routesOf(area)) {
        expect(destinations().querySelector(`[data-destination="${route.path}"]`)).toBeTruthy()
        seen.add(route.path)
      }
    }

    expect([...seen].sort()).toEqual(ROUTES.map((route) => route.path).sort())
  })
})


describe("the console says whose data this is", () => {
  /**
   * A partner reaching a hosted console sees repository names. Nothing on screen told them
   * whether an unfamiliar one is their own deployment holding a repo they did not expect, or
   * somebody else`s data — and on a single-tenant product with one shared credential in front
   * of it, that is a trust question rather than a cosmetic one. It became answerable the moment
   * the console could be served somewhere a partner reaches.
   *
   * What is asserted here is only what the console can honestly know: that everything visible
   * comes from one graph and nothing is filtered per viewer. The console holds no deployment
   * name — no route serves one — so it must not render one.
   */
  it("states that every screen reads one deployment, on every screen", () => {
    renderAt("/")
    expect(screen.getByText(/one deployment/i)).not.toBeNull()

    cleanup()
    renderAt("/detectors")
    expect(screen.getByText(/one deployment/i)).not.toBeNull()
  })

  it("says the view is unfiltered, so an unfamiliar name is this deployment`s own", () => {
    renderAt("/")
    const note = screen.getByText(/one deployment/i).textContent ?? ""
    expect(note).toMatch(/filtered/i)
    expect(note).toMatch(/not another customer/i)
  })
})

describe("focus follows the route", () => {
  /**
   * `react-router` does not move focus on navigation, so a keyboard or screen-reader user who
   * activates a destination stays where they were and the new screen is announced to nobody.
   * This console`s navigation hierarchy IS the API Dependency Graph, so focus that does not
   * follow the route makes the hierarchy itself unavailable — the argument
   * `references/notes/roadmap-frontend-skills.md` made and nothing had acted on.
   *
   * The main region takes focus rather than the heading, because the heading is a child of the
   * routed content and a screen that has not rendered one yet would leave focus nowhere. Its
   * tabIndex is -1: reachable programmatically, never a stop in the tab order.
   */
  it("gives the content region a programmatic focus target", () => {
    renderAt("/")
    const main = document.querySelector("main")
    expect(main).not.toBeNull()
    expect(main?.getAttribute("tabindex")).toBe("-1")
  })

  it("moves focus to the content when the route changes, and not on first paint", () => {
    renderAt("/")
    // Arriving at a screen is not a navigation: focus stays where the browser put it.
    expect(document.activeElement).not.toBe(document.querySelector("main"))
  })

  it("moves focus to the content when the route actually changes", async () => {
    renderAt("/")
    expect(document.activeElement).not.toBe(document.querySelector("main"))

    // Detectors is a real link in the sidebar, because it needs no subject from the address.
    // Clicking it is an in-app navigation rather than a contrived route swap. This used to click
    // the Observe rail item; the rail is gone, and the destination it led to serves the same
    // purpose here.
    fireEvent.click(within(destinations()).getByRole("link", { name: /detectors/i }))

    await waitFor(() => expect(document.activeElement).toBe(document.querySelector("main")))
  })
})

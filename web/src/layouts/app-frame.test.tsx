/**
 * The chassis is two tiers, and this is the test that decides it.
 *
 * A fixed icon rail carries the product's areas; a contextual sidebar carries the destinations
 * inside the area that is active. The discriminator between that and the single sidebar it
 * replaces is **which tier changes when you navigate**: the rail's items are the same items in
 * the same order on every route, and only the sidebar's contents move.
 *
 * **jsdom has no layout, so vertical position cannot be read directly** — `getBoundingClientRect`
 * returns zeroes here. Saying so matters, because a test that asserted on those numbers would pass
 * against any tree at all. What is asserted instead is the structural cause: the rail's ordered
 * sequence of accessible names is identical on every route, and an item can only move if one above
 * it appears or disappears. The pixels are measured in Chrome and recorded in `DESIGN.md`; this
 * holds the property that makes that measurement come out right.
 *
 * Rewritten for M7-W171 from the M7-W160 file that pinned the one-sidebar arrangement. Four of its
 * assertions described a collapse threshold and a reserved heading row and describe nothing that
 * exists now; three described reachability, accessible naming and `reachedFrom`, which the two-tier
 * shell owes exactly as much, and those are carried forward against the new tiers.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, useNavigate } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AppFrame } from "@/layouts/app-frame"
import { shortcutHint } from "@/layouts/command-palette"
import { KINDS_SHOWN, clearErrors, reportError } from "@/lib/error-log"
import { AREAS, ROUTES, type AreaEntry } from "@/lib/routes"

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

/** The icon rail: the tier that does not change. */
function rail(): HTMLElement {
  return screen.getByRole("navigation", { name: /areas/i })
}

/** The contextual sidebar: the tier that does. */
function destinations(): HTMLElement {
  return screen.getByRole("navigation", { name: /destinations/i })
}

/**
 * Every rail item's accessible name, in document order.
 *
 * Read off `aria-label` rather than through `getAllByRole("link")`, because the rail deliberately
 * holds three kinds of control: a link for an area with a landing route, a button for an area whose
 * every destination needs a subject the registry does not hold, and one `aria-disabled` entry for
 * Settings. A role query would see one of the three and report the rail as shorter than it is.
 */
function railNames(): string[] {
  return [...rail().querySelectorAll("[aria-label]")].map(
    (el) => el.getAttribute("aria-label") ?? ""
  )
}

/** The rail item the chassis is marking as the one being looked at. */
function railCurrent(): (string | null)[] {
  return [...rail().querySelectorAll('[aria-current="true"]')].map((el) =>
    el.getAttribute("aria-label")
  )
}

/**
 * Whether the rail is showing its labels, read off the vendored primitive's own attribute.
 *
 * `data-state` is what `SidebarProvider` computes and what every `group-data-[collapsible=icon]`
 * class in `vendor/supabase/ui/sidebar.tsx` reads. Asserting on it rather than on a width class
 * keeps this a claim about the primitive's state machine, which is the thing being consumed.
 */
function railState(): string | null {
  return rail().getAttribute("data-state")
}

/**
 * The rail's flow skeleton: one entry per element inside it, in document order.
 *
 * This is the structural cause of NOTES entry 6's mechanical test — an icon must not move
 * vertically across the collapse. jsdom has no layout, so the offsets themselves are measured in
 * Chrome and recorded in `DESIGN.md`; what can be held here is the property that makes them come
 * out equal. Every rail row is one fixed-height box in a column, so an icon can only travel
 * vertically if an element above it enters or leaves the flow between the two states. A
 * `SidebarGroupLabel` is exactly that shape — `h-8` expanded, `-mt-8 opacity-0` collapsed — and it
 * is the defect this comparison catches.
 *
 * Read as tag plus accessible name rather than as markup, so restyling a row does not fail it.
 */
function railSkeleton(): string[] {
  return [...rail().querySelectorAll("*")].map(
    (el) => `${el.tagName}/${el.getAttribute("aria-label") ?? ""}`
  )
}

/** Every second-tier row, in document order, as the element that actually renders it. */
function destinationRows(): Element[] {
  return [...destinations().querySelectorAll("[data-destination]")]
}

/**
 * A real Back, rather than a second click forward onto the same address.
 *
 * The two are not the same assertion. A forward click would prove the rail agrees with the address
 * it arrives at; Back proves it does not resurrect a state it left behind, which is where a pick
 * that is masked rather than dropped goes wrong.
 */
function BackButton() {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => navigate(-1)}>
      go back
    </button>
  )
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

  it("puts the bar above the rail rather than inside the scrolling column", () => {
    // The structural claim, asserted where jsdom can see it: the header is a sibling *before* the
    // rail-and-content row. Inside `main` it would be the breadcrumb again — gone on first scroll.
    renderAt("/")

    const banner = screen.getByRole("banner")

    expect(banner.contains(rail())).toBe(false)
    expect(
      banner.compareDocumentPosition(rail()) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
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

describe("the rail carries the product's areas", () => {
  it("names every area exactly once and Settings last", () => {
    renderAt("/")

    const items = railNames()

    expect(items[items.length - 1]).toMatch(/settings/i)
    expect(new Set(items).size).toBe(items.length)
    expect(items).toHaveLength(AREAS.length + 1)
  })

  it("keeps every rail item in the same position on every route", () => {
    // The two-tier property, asserted where jsdom can see it. If the rail's sequence differed
    // between two routes, an icon would move under the pointer as an operator navigated, which is
    // the one thing a persistent rail must not do.
    renderAt("/")
    const atRoot = railNames()
    cleanup()

    for (const route of ROUTES) {
      renderAt(concrete(route.path))
      expect(railNames()).toEqual(atRoot)
      cleanup()
    }

    expect(atRoot.length).toBeGreaterThan(1)
  })

  it("names each rail item for a screen reader, not only in a tooltip", () => {
    // A tooltip supplements the name; it is not the mechanism that supplies it. Every rail control
    // is icon-only, so without `aria-label` the rail is a column of unnamed buttons.
    renderAt("/")

    expect(within(rail()).getByRole("link", { name: /codebases|repositories|fleet/i })).toBeTruthy()
    for (const area of AREAS) {
      expect(railNames()).toContain(area.label)
    }
  })

  it("reaches Settings without making it an area or a level", () => {
    // Settings is a destination, not a rung: `DESTINATIONS` declares it, `GRAPH_LEVELS` stays at
    // nine, and `AREAS` never gains a seventh member. This rail slot held a disabled button for as
    // long as no screen existed; the screen exists now and is read-only, so the entry links and its
    // note says which of those two things is true rather than continuing to promise the other.
    renderAt("/")

    const settings = within(rail()).getByLabelText(/settings/i)

    expect(settings.getAttribute("href")).toBe("/settings")
    expect(settings.getAttribute("aria-disabled")).toBeNull()
    expect(AREAS.map((area) => area.label)).not.toContain("Settings")
    // Asserted on `title` rather than on the tooltip: a Radix tooltip is in the document only while
    // it is open, so the sentence has to be readable without one.
    expect(settings.getAttribute("title")).toBe("Settings — read-only until the write path lands")
  })

  it("keeps an area's rail item current on every route that area owns", () => {
    // This is the `pages` mechanism where it is genuinely load-bearing. A rail item owns a run of
    // levels rather than one address, so it says which addresses it owns in data — the alternative
    // is a regex over the path, which quietly stops matching the day a route is added beneath it.
    for (const area of AREAS) {
      for (const route of routesOf(area)) {
        renderAt(concrete(route.path))

        expect(railCurrent()).toEqual([area.label])

        cleanup()
      }
    }
  })

  it("shows its labels while a pointer is on it and hides them again after", () => {
    // The measured gap: the rail was 40px and fixed, so six areas were six permanently unlabelled
    // glyphs and `[data-collapsible]` counted zero. The mechanism is the vendored primitive's own
    // open state; what this project supplies is the pointer that drives it.
    renderAt("/")

    expect(railState()).toBe("collapsed")

    fireEvent.mouseEnter(rail())
    expect(railState()).toBe("expanded")

    fireEvent.mouseLeave(rail())
    expect(railState()).toBe("collapsed")
  })

  it("shows them for a keyboard too, not only for a pointer", () => {
    // A rail that only labels itself under a pointer is a rail nobody tabbing through it can read.
    renderAt("/")

    fireEvent.focusIn(within(rail()).getByLabelText("Codebase"))

    expect(railState()).toBe("expanded")
  })

  it("moves nothing above an icon between the collapsed and expanded states", () => {
    // NOTES entry 6, held where jsdom can see it. `railSkeleton`'s docstring carries why this is
    // the structural cause rather than the pixels, and where the pixels are read instead.
    renderAt("/")

    const collapsed = railSkeleton()
    fireEvent.mouseEnter(rail())
    const expanded = railSkeleton()

    expect(expanded).toEqual(collapsed)
    // Guards the comparison itself: two empty lists are equal, and would report a rail that
    // rendered nothing as one that moves nothing.
    expect(collapsed.length).toBeGreaterThan(AREAS.length)
  })

  it("drops a pick when the address changes, and does not revive it on Back", () => {
    // Picking an area with no landing route is a browse, not a navigation, so it has to be dropped
    // the moment the address moves rather than suspended while the address differs. Suspended, it
    // comes back the instant its own address does — and then the rail marks one area while another
    // area's screen renders underneath it, which is the one disagreement this shell must not have.
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppFrame />
        <BackButton />
      </MemoryRouter>
    )
    expect(railCurrent()).toEqual(["Codebases"])

    fireEvent.click(within(rail()).getByLabelText("Codebase"))
    expect(railCurrent()).toEqual(["Codebase"])

    // A link, so this is a real navigation away from the address the pick was made at.
    fireEvent.click(within(rail()).getByLabelText("Observe"))
    expect(railCurrent()).toEqual(["Observe"])

    fireEvent.click(screen.getByRole("button", { name: "go back" }))

    // Back at `/`, where the Codebases screen renders. The rail says Codebases, not the area browsed here
    // three clicks ago.
    expect(railCurrent()).toEqual(["Codebases"])
  })
})

describe("the contextual sidebar carries the active area's destinations", () => {
  it("heads itself with the area the current route belongs to", () => {
    for (const area of AREAS) {
      const route = routesOf(area)[0]
      renderAt(concrete(route.path))

      expect(within(destinations()).getByRole("heading", { name: area.label })).toBeTruthy()

      cleanup()
    }
  })

  it("renders the active area's destinations and no other area's", () => {
    for (const area of AREAS) {
      const route = routesOf(area)[0]
      renderAt(concrete(route.path))

      const shown = [...destinations().querySelectorAll("[data-destination]")].map((el) =>
        el.getAttribute("data-destination")
      )
      expect(shown).toEqual(routesOf(area).map((r) => r.path))

      cleanup()
    }
  })

  it("groups them under the graph levels the specification names", () => {
    // The grouping is the specification's vocabulary rendered, not a second hierarchy: an area is a
    // run of consecutive levels, and the sidebar prints the level names it holds. Read off the
    // group labels rather than by text, because a level name and a destination's label are the same
    // word on five of the nine routes.
    for (const area of AREAS) {
      renderAt(concrete(routesOf(area)[0].path))

      const labels = [...destinations().querySelectorAll('[data-sidebar="group-label"]')].map(
        (el) => el.textContent
      )
      expect(labels).toEqual([...area.levels])

      cleanup()
    }
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

      const rows = destinationRows()
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

describe("every declared destination is one rail activation away", () => {
  it("shows an area's whole run of levels the moment its rail item is used", () => {
    // The reachability claim the whole chassis exists to make, and the one the first version of this
    // shell failed: four area icons remained and the nine specification levels could not be reached.
    renderAt("/")

    const seen = new Set<string>()
    for (const area of AREAS) {
      fireEvent.click(within(rail()).getByLabelText(area.label))

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

    // The Observe rail item is a real link, because its area has a landing that needs no subject.
    // Clicking it is an in-app navigation rather than a contrived route swap.
    fireEvent.click(screen.getByRole("link", { name: /observe/i }))

    await waitFor(() => expect(document.activeElement).toBe(document.querySelector("main")))
  })
})

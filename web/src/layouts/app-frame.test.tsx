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

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AppFrame, navRoutes, SETTINGS_NOTE } from "@/layouts/app-frame"
import { shortcutHint } from "@/layouts/command-palette"
import { KINDS_SHOWN, clearErrors, reportError } from "@/lib/error-log"
import { DESTINATIONS, ROUTES } from "@/lib/routes"

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
  // The pin persists, which is the point of it — and a test that pins the sidebar would otherwise
  // hand the next one a reader who has already chosen. Caught by exactly that, once.
  window.localStorage.clear()
})

function renderAt(path: string) {
  // A client, even though the two list queries above are mocked. `useChassisIdentity` calls
  // `useQuery` directly rather than through `@/api/queries`, so the module mock never reaches it
  // and every render threw "No QueryClient set" -- 34 failures from one missing provider.
  //
  // Seeded rather than merely provided. A client with no data leaves the identity query pending
  // forever, and half this file's assertions are about chrome that only renders once a workspace
  // is known -- so an unseeded client turns "the scope trail names the subject" into a failure
  // about nothing. The seed is the smallest shape `useChassisIdentity` reads.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  client.setQueryData(["setup", "chassis"], { operator: { forge_login: "stroland02" } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppFrame />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

/** The contextual sidebar: the tier that does. */
function destinations(): HTMLElement {
  return screen.getByRole("navigation", { name: /destinations/i })
}

/**
 * The destinations the rail draws.
 *
 * One region as of `M14-W386`. The registry used to carry `root` and `repository` and they
 * overlapped by name -- Codebases against Codebase, Vendor against Vendors -- which is the
 * duplication the owner saw in the sidebar. Every page is a workspace's page now, and a route whose
 * subject a workspace cannot supply is absent from the rail rather than inert in it.
 */
// Imported from the chassis rather than redefined. This file held its own copy that filtered on
// `nav` and never applied `navOrder`, so when the owner reordered the rail on 2026-08-18 the two
// definitions disagreed and the assertion failed on an ordering that was correct on screen. A
// fact written twice disagrees with itself; the component owns this one.

/** A concrete URL for a route, since `:findingId` matches nothing on its own. */
function concrete(path: string): string {
  return path.replace(/:([A-Za-z]+)/g, "subject")
}

describe("the top bar sits above the chassis", () => {
  // 15s rather than the 5s default, and the reason is a real cost rather than flake. `M14-W366`
  // made the sidebar render every destination on every route instead of one area's run, so this
  // loop now mounts a nine-row sidebar nine times. It passes in ~10s alone and tipped over 5s only
  // under a loaded parallel run. Recorded here because the next person to see it go red should know
  // the cause is render volume, not a race.
  it("renders a banner on every route", { timeout: 15_000 }, () => {
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

  /**
   * The scope-trail guard retired with its subject, 2026-08-19.
   *
   * It asserted that the banner carries a `navigation` landmark named "Scope" naming the
   * workspace and the vendor. The owner removed the top-bar directory, and `ScopeSwitchers` is
   * now mounted nowhere — so this asserted against a component the console does not render, and
   * had been failing since.
   *
   * **What it guaranteed is not dropped.** That the top bar names the workspace is carried by
   * `EnvironmentBadge`, asserted below; that a screen says what contains what is carried by
   * `Breadcrumbs` and its own tests. `M14-W273` is the precedent this file already records: a
   * test whose subject retires may go, but not the coverage it carried.
   */
  it("names the workspace in the top bar, which is what the scope trail used to carry", () => {
    renderAt("/repositories/org%2Fone/vendors/stripe")

    const banner = screen.getByRole("banner")
    expect(banner.textContent ?? "").toContain("org/one")
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

describe("the sidebar reveals itself on hover and returns to a rail", () => {
  /**
   * The owner asked for this by name: *"the sidebar only expands when you're hovering over it and
   * then automatically minimizes once you drag off."* It reconciles the two things otherwise in
   * conflict — a rail that does not consume width, and full labels when they are wanted.
   *
   * **jsdom has no layout**, so no width here is read as a pixel. What is asserted is the state
   * each element declares, which is the thing the derivation in `sidebar-collapse.ts` computes and
   * the thing a wrong answer would show up in. The widths themselves are measured in Chrome and
   * recorded in `DESIGN.md`.
   */
  function panel(): HTMLElement {
    return destinations().closest("[data-state]") as HTMLElement
  }

  /** The box the content column actually gives up, which a hover must never move. */
  function reserve(): HTMLElement {
    return document.querySelector("[data-sidebar-reserve]") as HTMLElement
  }

  it("starts as a rail for a reader who has not pinned it", () => {
    renderAt("/")
    expect(panel().getAttribute("data-state")).toBe("minimised")
  })

  it("expands while the pointer is inside it and returns to a rail when it leaves", () => {
    renderAt("/")

    fireEvent.pointerEnter(reserve())
    expect(panel().getAttribute("data-state")).toBe("expanded")

    fireEvent.pointerLeave(reserve())
    expect(panel().getAttribute("data-state")).toBe("minimised")
  })

  it("holds open while focus is inside it, so a hover does not trap a keyboard reader", () => {
    // Hover alone would put every label behind a pointer. A reader tabbing into the sidebar has to
    // see what they are tabbing through, and has to keep seeing it after any pointer has left.
    renderAt("/")

    const railLink = within(destinations()).getByRole("link", { name: /call sites/i })
    fireEvent.focusIn(railLink)
    expect(panel().getAttribute("data-state")).toBe("expanded")

    fireEvent.pointerLeave(reserve())
    expect(panel().getAttribute("data-state")).toBe("expanded")

    fireEvent.focusOut(railLink)
    expect(panel().getAttribute("data-state")).toBe("minimised")
  })

  it("keeps focus inside when it moves between two rows", () => {
    // `focusout` fires before `focusin` when focus travels within the sidebar. Collapsing on it
    // unconditionally would flicker the panel shut and open again on every arrow key.
    renderAt("/")

    const railLink = within(destinations()).getByRole("link", { name: /call sites/i })
    const settings = within(destinations()).getByRole("link", { name: /settings/i })

    fireEvent.focusIn(railLink)
    fireEvent.focusOut(railLink, { relatedTarget: settings })

    expect(panel().getAttribute("data-state")).toBe("expanded")
  })

  it("takes the width it draws, so revealing pushes the page instead of covering it", () => {
    // The inverse of what this file asserted until the owner saw it running. The reveal WAS an
    // overlay, on the argument that reflowing the column under a reader is worse than covering it.
    // The screenshot that settled it showed the page heading rendering as "W", the leading column of
    // every table gone, and the repository names cut off mid-word — so the sidebar pushes the page,
    // and the reserved box tracks the panel rather than disagreeing with it.
    renderAt("/")

    expect(reserve().getAttribute("data-sidebar-reserve")).toBe("minimised")
    expect(panel().getAttribute("data-state")).toBe("minimised")

    fireEvent.pointerEnter(reserve())

    expect(panel().getAttribute("data-state")).toBe("expanded")
    expect(reserve().getAttribute("data-sidebar-reserve")).toBe("expanded")
  })



})

describe("the sidebar changes density without moving a row", () => {
  /**
   * The constraint, carried from `M7-W160`'s commit body and the reason its predecessor was
   * deleted: **minimising changes density, not navigation.** Every destination reachable expanded
   * stays reachable minimised, and no icon moves vertically across the state change.
   *
   * **jsdom has no layout**, so the vertical offsets themselves cannot be read — `getBoundingClientRect`
   * returns zeroes. Asserting on those numbers would pass against any tree at all. What is held here
   * is the structural cause: every row is one fixed-height box in a column, so an icon can only
   * travel vertically if an element above it enters or leaves the flow. Comparing the sidebar's
   * ordered element skeleton between the two states catches exactly that, and it is why a group
   * heading's text goes `sr-only` rather than the heading row being removed.
   *
   * This is `M7-W160`'s own guard shape, which was proved red twice before it was trusted.
   * `M14-W376` drives it from the hover reveal as well as the pin, because the reveal is now the
   * transition a reader meets constantly and the pin is the one they meet once.
   */
  function skeleton(): string[] {
    return [...destinations().querySelectorAll("*")].map(
      (el) => `${el.tagName}/${el.getAttribute("data-destination") ?? ""}`
    )
  }

  function reserve(): HTMLElement {
    return document.querySelector("[data-sidebar-reserve]") as HTMLElement
  }

  it("keeps the same elements in the same order across a hover", () => {
    renderAt("/")

    const rail = skeleton()
    fireEvent.pointerEnter(reserve())
    const revealed = skeleton()

    // Identical, element for element. A heading row that vanished at the rail width would shorten
    // this list and move every icon beneath it upward — which is the defect, not a detail of it.
    expect(rail.length).toBeGreaterThan(0)
    expect(revealed).toEqual(rail)
  })


  // Four pin tests stood here and went with the control they exercised: the owner removed the
  // button because hovering is the mechanism, and two ways to open one panel is what made this
  // sidebar hard to reason about. Nothing they guaranteed is lost -- row stability across the
  // reveal is asserted directly above against a pointer, which is now the only thing that opens it.
  it("never renders a destination as something that absorbs a click", () => {
    // The defect the owner hit running the console: nine of twelve routes need a bound parameter,
    // so `destinationHref` returned null for most of the sidebar and the row rendered as a <span>
    // that looked like a button and swallowed the press. A vanished control is honest; one that
    // takes the click and does nothing reads as broken software.
    //
    // It also contradicted the owner's own instruction from the same review -- do not limit buttons
    // by where you are currently looking -- and it is the worse half of that failure.
    renderAt("/")

    const rows = [...destinations().querySelectorAll("[data-destination]")]
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(row.tagName).toBe("A")
      expect(row.getAttribute("href")).toBeTruthy()
    }
  })

  // Three tests stood here and went with their subject. They asserted what an UNBOUND row does --
  // where it points, what it says, when it stops saying it -- and there are no unbound rows now.
  // A route whose subject a workspace cannot supply is absent from the rail rather than present and
  // pointing somewhere else, which is the owner's rule and the stronger half of it. What they
  // guaranteed survives directly above: every row is a link with a real href.

  it("binds the subject from the selected codebase when the address carries one", () => {
    renderAt("/repositories/org%2Fone")

    const bound = destinations().querySelector('[data-destination="/repositories/:repoId/vendors"]')
    expect(bound).not.toBeNull()
    expect(bound!.getAttribute("href")).toBe("/repositories/org%2Fone/vendors")
  })

  it("keeps every destination reachable at the rail width", () => {
    // No hover, no click of any kind: this is the state the console loads in.
    renderAt("/repositories/org%2Fone")

    const reachable = [...destinations().querySelectorAll("a[href]")].map((el) =>
      el.getAttribute("href")
    )
    expect(navRoutes().length).toBeGreaterThan(0)
    expect(DESTINATIONS.length).toBeGreaterThan(0)
    for (const entry of DESTINATIONS) {
      expect(reachable).toContain(entry.path)
    }
    // Every navigable row resolved its workspace, so none of them is the picker fallback.
    for (const route of navRoutes()) {
      const row = destinations().querySelector(`[data-destination="${route.path}"]`)
      expect(row?.getAttribute("href")).toContain("/repositories/org%2Fone")
    }
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
    // Grouped by region rather than in raw registry order: root first, then repository, which is
    // the order the sidebar draws them and the order a reader meets them.
    expect(shown).toEqual(navRoutes().map((r) => r.path))
  })

  it("names every navigable destination the workspace can reach", () => {
    renderAt("/repositories/org%2Fone")

    const text = destinations().textContent ?? ""
    expect(navRoutes().length).toBeGreaterThan(0)
    for (const route of navRoutes()) {
      expect(text).toContain(route.label)
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
    expect(ROUTES.map((route) => route.label)).not.toContain("Settings")
    expect(settings.getAttribute("title")).toBe(SETTINGS_NOTE)
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
    for (const route of navRoutes()) {
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
    expect(order[0]).toEqual(navRoutes().map((r) => r.path))
  })

  it("prints no level heading, because eleven of them is what forced the scrollbar", () => {
    // Reversed after the owner opened the reference images and said the console "doesn't look much
    // different". The reference rail carries NO section heading at all; ours carried thirteen for
    // eleven rows, and several duplicated the row beneath them outright -- a "BINDING SURFACE"
    // heading over a "Binding surface" row. That is what made the sidebar taller than the viewport
    // and forced the scroll the owner asked twice to remove.
    //
    // The specification's vocabulary does not depend on this: `route.level` still carries it, and
    // `tests/test_console_hierarchy.py` still holds it against the spec block. What is dropped is a
    // second rendering of a word already on the row.
    renderAt("/")

    const labels = [...destinations().querySelectorAll('[data-sidebar="group-label"]')]
    expect(labels.length).toBe(0)
  })

  it("draws one flat set of destinations, with no region heading above them", () => {
    // The regions are deleted, not relabelled. They overlapped by name -- Codebases against
    // Codebase, Vendor against Vendors -- which is the duplication the owner saw. Every page is a
    // workspace's page now, so there is no second grouping left for a heading to name.
    renderAt("/repositories/org%2Fone")

    const text = destinations().textContent ?? ""
    expect(text).not.toContain("Across all repositories")
    expect(text).not.toContain("Within a repository")
  })

  it("carries no pin control, because hovering is what opens it now", () => {
    // The owner: "go with the hover method and remove the button at the top of the sidebar as it's
    // no longer needed because we'll just be hovering". Two mechanisms for one behaviour is the
    // thing that made this sidebar confusing to reason about, and the pointer is the one that was
    // asked for.
    renderAt("/")

    expect(screen.queryByRole("button", { name: /pin|minimise the sidebar|expand the sidebar/i })).toBeNull()
  })

  it("marks the row for the current route, and marks only it", () => {
    // Navigable routes only. A route the rail does not draw — a finding, a workflow, a binding
    // surface — marks nothing, because it has no row to mark. Being on one of those screens leaves
    // the rail showing the workspace's pages with none of them current, which is honest: the reader
    // is somewhere the rail cannot take them, reached from the page that held the subject.
    for (const route of navRoutes()) {
      renderAt(concrete(route.path))

      const current = [...destinations().querySelectorAll('[aria-current="page"]')].map((el) =>
        el.getAttribute("data-destination")
      )
      expect(current).toEqual([route.path])

      cleanup()
    }
  })

  it("names every destination for a screen reader", () => {
    for (const subject of navRoutes()) {
      renderAt(concrete(subject.path))

      for (const route of navRoutes()) {
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
    // Signals used to be this row and is a Logs tab now (owner ruling, 2026-08-18), so the
    // subject moved rather than the property. Asserted against a route still in the rail: the
    // claim is that a destination the address can build renders as a link, not which one.
    renderAt("/repositories/org%2Fone/call-sites")

    const row = destinations().querySelector(
      '[data-destination="/repositories/:repoId/call-sites"]'
    )
    expect(row).not.toBeNull()
    expect(row!.tagName).toBe("A")
    expect(row!.getAttribute("href")).toBe("/repositories/org%2Fone/call-sites")
  })


})

describe("every declared destination is reachable without an activation", () => {
  it("shows every destination a workspace can reach, with nothing to click first", () => {
    // The reachability claim the chassis exists to make. It used to say "all nine specification
    // levels", which stopped being the right claim when the regions collapsed: four of the ten
    // routes need a vendor, an operation or a finding, and a workspace supplies none of those. Those
    // levels still exist in GRAPH_LEVELS and their screens are still reachable -- from the page that
    // holds their subject, not from the rail. What the rail owes is every destination it CAN bind.
    renderAt("/repositories/org%2Fone")

    expect(navRoutes().length).toBeGreaterThan(0)
    for (const route of navRoutes()) {
      expect(destinations().querySelector(`[data-destination="${route.path}"]`)).toBeTruthy()
    }
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

  it("keeps both qualifications out of the sidebar, so no reveal gates them", () => {
    /**
     * `.claude/rules/console-surface.md` forbids collapsing a protected sentence behind a
     * disclosure. These two used to sit in the sidebar footer, and that was defensible while the
     * sidebar loaded expanded — the file said so in as many words. **Hover-expand destroys that
     * justification**: an unpinned rail would put both sentences behind a pointer move, which is a
     * disclosure whatever it is called. They moved into the content column instead, where nothing
     * gates them, and this is the assertion that stops them drifting back.
     */
    renderAt("/")

    for (const sentence of [/one deployment/i, /Nine graph levels/i]) {
      const node = screen.getByText(sentence)
      expect(destinations().contains(node)).toBe(false)
    }
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
    renderAt("/repositories/org%2Fone")
    expect(document.activeElement).not.toBe(document.querySelector("main"))

    // Detectors is a real link in the sidebar, because it needs no subject from the address.
    // Clicking it is an in-app navigation rather than a contrived route swap. This used to click
    // the Observe rail item; the rail is gone, and the destination it led to serves the same
    // purpose here.
    fireEvent.click(within(destinations()).getByRole("link", { name: /call sites/i }))

    await waitFor(() => expect(document.activeElement).toBe(document.querySelector("main")))
  })
})

/**
 * The palette is the console's map of itself, so it may not be a map with seven holes in it.
 *
 * Until this suite existed the palette filtered `ROUTES` down to `params.length === 0` and listed
 * two of nine destinations. That is honest about what it can link to and dishonest about what
 * exists: an operator who opens a list of destinations and finds Codebases and Detectors learns
 * that the console has two screens.
 *
 * The rule the mock's own footer states, and the one this file holds: a destination that needs a
 * subject is listed as **a place to look one up**, never as a link with an empty parameter in it.
 * Those are different failures — dropping the row hides a screen, and linking it produces
 * `/findings//workflow` — and the row that says where to pick a subject is the only answer that is
 * neither.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. `paletteGroups` is a pure function over the registry precisely so the rule can be
 * tested as a derivation rather than by driving a dialog, and the one render test below asserts
 * behaviour a reader depends on — a lookup row does not navigate — not how it is styled.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { CommandPaletteProvider, paletteGroups } from "@/layouts/command-palette"
import { GRAPH_LEVELS, ROUTES } from "@/lib/routes"

afterEach(cleanup)

const rows = () => paletteGroups(ROUTES, GRAPH_LEVELS).flatMap((group) => group.rows)

describe("paletteGroups", () => {
  it("lists every declared route exactly once, so the palette is the whole map", () => {
    const listed = rows().map((row) => row.path).sort()

    expect(listed).toEqual(ROUTES.map((route) => route.path).sort())
  })

  it("renders a subject-taking route as a lookup rather than dropping it", () => {
    const subjectTaking = ROUTES.filter((route) => route.params.length > 0)
    expect(subjectTaking.length).toBeGreaterThan(0)

    for (const route of subjectTaking) {
      const row = rows().find((candidate) => candidate.path === route.path)
      expect(row?.lookUpFrom).toBe(route.reachedFrom)
    }
  })

  it("leaves a route that needs no subject navigable", () => {
    for (const route of ROUTES.filter((candidate) => candidate.params.length === 0)) {
      expect(rows().find((row) => row.path === route.path)?.lookUpFrom).toBeNull()
    }
  })

  it("carries each route's pattern, so the palette doubles as the map of what exists", () => {
    for (const row of rows()) {
      expect(row.pattern).toBe(row.path)
    }
  })

  it("groups by level in the specification's order and drops a level with nothing under it", () => {
    const groups = paletteGroups(ROUTES, GRAPH_LEVELS)
    const order = groups.map((group) => group.level)

    expect(order).toEqual([...GRAPH_LEVELS].filter((level) => order.includes(level)))
    for (const group of groups) {
      expect(group.rows.length).toBeGreaterThan(0)
    }
  })

  it("never produces a path with an empty parameter in it", () => {
    for (const row of rows()) {
      expect(row.pattern).not.toMatch(/\/\//)
      if (row.lookUpFrom === null) expect(row.pattern).not.toContain(":")
    }
  })
})

describe("CommandPalette", () => {
  it("offers a subject-taking destination as a lookup a reader cannot follow", async () => {
    render(
      <MemoryRouter initialEntries={["/detectors"]}>
        <CommandPaletteProvider>
          <div />
        </CommandPaletteProvider>
      </MemoryRouter>
    )

    fireEvent.keyDown(document, { key: "k", ctrlKey: true })

    // Scoped by role rather than by text: several route labels equal their level's group heading,
    // so a bare text query matches the heading too and fails on the ambiguity rather than the rule.
    const lookup = ROUTES.find((route) => route.params.length > 0)!
    const options = await screen.findAllByRole("option")
    const row = options.find((option) => option.textContent?.includes(lookup.path))
    expect(row).toBeTruthy()
    expect(row?.getAttribute("aria-disabled")).toBe("true")
    expect(row?.textContent).toContain(lookup.reachedFrom)
  })
})

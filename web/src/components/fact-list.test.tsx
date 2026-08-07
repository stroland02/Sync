/**
 * A fact list is a `<dl>`, and a fact tile never renders an empty value.
 *
 * The semantics are the assertion. A definition list announces a term and its description as a pair,
 * which is exactly the claim the visual arrangement makes — label left, value right, one line each —
 * so a reader on a screen reader gets the same pairing a sighted reader gets from the columns. Built
 * out of `div`s it would read as nine unrelated strings, and nothing about the rendered pixels would
 * look wrong.
 *
 * The tile test is about absence rather than presence, which is where this console's rules live. A
 * caller with nothing to show passes `<Absent>` — the one absence marker, carrying which kind of
 * nothing this is — and the failure mode to guard is a tile that renders an empty box instead,
 * because an empty box and a zero look identical and `.claude/rules/console-surface.md` exists to
 * keep them apart.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { FactList } from "@/components/fact-list"
import { FactTile } from "@/components/fact-tile"
import { Absent } from "@/components/status"

afterEach(cleanup)

describe("FactList", () => {
  it("pairs each label with its value as a definition list", () => {
    const { container } = render(
      <FactList
        facts={[
          { label: "Rung", value: "static" },
          { label: "Indexed at", value: "8/6/2026" },
        ]}
      />
    )

    expect(container.querySelectorAll("dl")).toHaveLength(1)
    expect(container.querySelectorAll("dt")).toHaveLength(2)
    expect(container.querySelectorAll("dd")).toHaveLength(2)
  })

  it("keeps label and value in the same pair, so the eye and the reader agree", () => {
    const { container } = render(
      <FactList facts={[{ label: "Rung", value: "static" }]} />
    )

    const row = container.querySelector("dl > div")
    expect(row?.querySelector("dt")?.textContent).toBe("Rung")
    expect(row?.querySelector("dd")?.textContent).toBe("static")
  })

  it("renders every fact it is given, including one whose value is an absence marker", () => {
    render(
      <FactList
        facts={[
          { label: "Feed fetched at", value: <Absent>no feed recorded</Absent> },
          { label: "Rung", value: "static" },
        ]}
      />
    )

    expect(screen.getAllByRole("term")).toHaveLength(2)
  })
})

describe("FactTile", () => {
  it("renders the label and the value in separate registers", () => {
    const { container } = render(<FactTile label="Open findings" value="2,500" figure />)

    expect(screen.getByText("Open findings")).toBeTruthy()
    expect(screen.getByText("2,500")).toBeTruthy()
    // The label register is what `.furniture` exists for, and it is the one class this suite reads
    // because it is a *semantic* register rather than an appearance: it marks a scanned label, and
    // DESIGN.md's Type section says which of `--text-meta`'s two jobs that is.
    expect(container.querySelector(".furniture")?.textContent).toBe("Open findings")
  })

  it("shows an absence marker rather than an empty value box", () => {
    render(<FactTile label="Last run" value={<Absent>no run has finished</Absent>} />)

    expect(screen.getByText(/no run has finished/)).toBeTruthy()
  })

  it("renders its note when the value needs qualifying", () => {
    render(
      <FactTile
        label="Open findings"
        value="1,000+"
        figure
        note="Counted to a ceiling of 1,000; the true total is higher."
      />
    )

    expect(screen.getByText(/ceiling of 1,000/)).toBeTruthy()
  })
})

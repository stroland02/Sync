import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DetailGrid } from "@/layouts/detail-grid"

describe("DetailGrid", () => {
  it("renders header, then rail before content when railSide is start", () => {
    render(
      <DetailGrid header={<h1>head</h1>} rail={<nav>rail</nav>}>
        <p>content</p>
      </DetailGrid>
    )
    const all = screen.getByText("head").closest("div")!.parentElement!.textContent!
    expect(all.indexOf("head")).toBeLessThan(all.indexOf("rail"))
    expect(all.indexOf("rail")).toBeLessThan(all.indexOf("content"))
  })

  it("renders content before rail when railSide is end", () => {
    const { container } = render(
      <DetailGrid rail={<nav>rail</nav>} railSide="end">
        <p>content</p>
      </DetailGrid>
    )
    const text = container.textContent!
    expect(text.indexOf("content")).toBeLessThan(text.indexOf("rail"))
  })
})

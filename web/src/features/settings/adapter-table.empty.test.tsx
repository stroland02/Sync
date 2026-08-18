/**
 * Decision 61 on the adapter inventory: the headers stay when the table is empty.
 *
 * The colSpan is asserted against the real header count rather than hard-coded, because those
 * two numbers drifting apart is silent — the sentence just stops spanning the table, and nothing
 * else goes wrong. It was already wrong once when this was written.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { AdapterTable } from "@/features/settings/adapter-table"

afterEach(cleanup)

describe("AdapterTable with no adapters", () => {
  it("keeps every column header standing", () => {
    render(<AdapterTable adapters={[]} />)

    expect(screen.getByText("Vendor")).toBeTruthy()
  })

  it("spans the sentence across exactly as many columns as the header declares", () => {
    const { container } = render(<AdapterTable adapters={[]} />)

    const headers = container.querySelectorAll("thead th").length
    expect(container.querySelector("tbody td")?.getAttribute("colspan")).toBe(String(headers))
  })

  it("keeps the whole configured-state sentence rather than a trimmed one", () => {
    render(<AdapterTable adapters={[]} />)

    expect(screen.getByText(/a configured state rather than a failure/)).toBeTruthy()
    expect(screen.getByText(/once a scan has written a change against it/)).toBeTruthy()
  })
})

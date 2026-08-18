/**
 * The banner's three sentences, which are the whole reason it exists rather than a spinner.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { IndexStreamBanner } from "@/features/index-graph/index-stream-banner"

afterEach(cleanup)

describe("IndexStreamBanner", () => {
  it("says nothing at all before anything has arrived", () => {
    const { container } = render(<IndexStreamBanner indexedCount={0} status="live" />)

    expect(container.textContent).toBe("")
  })

  it("carries the live count so the aliveness is in the banner, not the graph", () => {
    render(<IndexStreamBanner indexedCount={214} status="live" />)

    expect(screen.getByText(/214 call sites indexed since you opened this/)).toBeTruthy()
  })

  /**
   * NOTIFY is not queued, so a reader opening this mid-index sees only what arrives after
   * connecting. Saying "since you opened this" is the difference between a window and a claim
   * about the whole run.
   */
  it("says what the count is over rather than implying it watched the whole run", () => {
    render(<IndexStreamBanner indexedCount={214} status="live" />)

    expect(screen.getByText(/since you opened this/)).toBeTruthy()
  })

  it("counts one call site in the singular", () => {
    render(<IndexStreamBanner indexedCount={1} status="live" />)

    expect(screen.getByText(/1 call site indexed/)).toBeTruthy()
  })

  /** Freeze and name: the loss is stated, the cause is refused. */
  it("names the loss and refuses to say whether the index is still running", () => {
    render(<IndexStreamBanner indexedCount={12} status="dropped" />)

    expect(screen.getByText("The live connection ended.")).toBeTruthy()
    expect(screen.getByText(/may\s+still be running and this screen can no longer tell you/)).toBeTruthy()
  })

  it("keeps what had arrived when it dropped rather than discarding it", () => {
    render(<IndexStreamBanner indexedCount={12} status="dropped" />)

    expect(screen.getByText(/12 call sites/)).toBeTruthy()
  })

  /**
   * Revised: the re-read is offered rather than performed. Swapping a live view for a static one
   * without being asked would hide that the screen stopped being live.
   */
  it("offers a re-read the reader triggers, rather than swapping the view for them", () => {
    const onReread = vi.fn()
    render(<IndexStreamBanner indexedCount={12} status="dropped" onReread={onReread} />)

    const control = screen.getByRole("button", { name: "Load the settled graph" })
    control.click()

    expect(onReread).toHaveBeenCalledOnce()
  })

  it("offers no re-read when the caller gave no way to do one", () => {
    render(<IndexStreamBanner indexedCount={12} status="dropped" />)

    expect(screen.queryByRole("button")).toBeNull()
  })

  it("makes no reconnect claim, because nobody has heard from the server", () => {
    const { container } = render(<IndexStreamBanner indexedCount={12} status="dropped" />)

    expect(container.textContent).not.toMatch(/reconnect|retrying/i)
  })
})

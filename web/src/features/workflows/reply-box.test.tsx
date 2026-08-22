/**
 * The reply box, and the fact that it cannot send.
 *
 * This is the point of the Solution Workflow screen and it is also the one turn on it that has
 * no route behind it. Sync's API is read-only — `tests/test_api_routes.py::
 * test_no_route_reaches_past_the_read_surface` holds that behaviourally — so the honest build states
 * the refusal in prose and names the route it is waiting for. These guards hold the refusal: a later
 * change that draws a submit control for a route that does not exist, or drops the sentence
 * explaining why nothing here can be sent, goes red here rather than on somebody's screen.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { REPLY_ROUTE, ReplyBox } from "@/features/workflows/reply-box"

afterEach(cleanup)

describe("the reply box", () => {
  it("renders a labelled field a reviewer can actually type into", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    const field = screen.getByLabelText(/reply to this run/i)
    fireEvent.change(field, { target: { value: "Please narrow the patch to the call site." } })

    expect((field as HTMLTextAreaElement).value).toBe(
      "Please narrow the patch to the call site.",
    )
  })

  it("draws no submit control at all, because no route accepts one", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    // Owner ruling, 2026-08-21: a disabled button naming a route that does not exist draws the
    // shape of a capability the product does not have, and reads as a feature merely switched off.
    expect(screen.queryAllByRole("button")).toHaveLength(0)
  })

  it("draws none after the field is filled in either, which is the whole refusal", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    fireEvent.change(screen.getByLabelText(/reply to this run/i), {
      target: { value: "anything at all" },
    })

    expect(screen.queryAllByRole("button")).toHaveLength(0)
  })

  it("names the route it needs, and says that route does not exist", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    expect(screen.getByText(new RegExp(REPLY_ROUTE.replace(/[{}/]/g, "\\$&")))).not.toBeNull()
    expect(screen.getByText(/does not exist yet/i)).not.toBeNull()
    expect(screen.getByText(/nothing typed here is stored, queued or sent/i)).not.toBeNull()
  })

  it("points the field at that explanation, so the refusal is not visual only", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    const field = screen.getByLabelText(/reply to this run/i)
    const describedBy = field.getAttribute("aria-describedby")

    expect(describedBy).not.toBeNull()
    const explanation = document.getElementById(describedBy as string)
    expect(explanation).not.toBeNull()
    expect(explanation?.textContent ?? "").toContain(REPLY_ROUTE)
  })
})


describe("which refusal applies", () => {
  /**
   * From `superlog-02`, read on 2026-08-18: their run states include `awaiting_human`, and a reply
   * in that state *"will resume the investigation in place -- no new run is created"*. That names
   * something this control was missing. A reply box on a run that is waiting and a reply box on a
   * run that has finished are two different refusals, and saying only "the route is missing"
   * collapses them into one.
   */
  it("says a waiting run is the one a reply would re-enter, and names what it waits on", () => {
    render(<ReplyBox waitingOn="await_ci" />)

    const text = document.body.textContent ?? ""
    expect(text).toContain("await_ci")
    expect(text).toContain("has not finished")
  })

  it("says a finished run would not be resumed by a reply even with the route", () => {
    // The stronger of the two, and the one that would otherwise be a lie by omission. With the route
    // in place a reply here still could not resume anything: the run reached a terminal outcome, so
    // a reply would be the start of something else and nothing in the graph decides what.
    render(<ReplyBox waitingOn={null} />)

    const text = document.body.textContent ?? ""
    expect(text).toContain("reached a terminal outcome")
    expect(text).not.toContain("has not finished")
  })

  it("names the missing route in both states, because that gap does not depend on the run", () => {
    for (const waitingOn of ["await_ci", null]) {
      render(<ReplyBox waitingOn={waitingOn} />)
      expect(document.body.textContent).toContain(REPLY_ROUTE)
      cleanup()
    }
  })
})

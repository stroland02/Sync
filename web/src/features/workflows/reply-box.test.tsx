/**
 * The reply box, and the fact that it cannot send.
 *
 * This is the point of the Solution Workflow screen and it is also the one control on it that has
 * no route behind it. Sync's API is read-only — `tests/test_api_routes.py::
 * test_no_route_reaches_past_the_read_surface` holds that behaviourally — so the honest build is a
 * control that renders, refuses, and names the route it is waiting for. These guards hold the
 * refusal: a later change that quietly enables the button, or drops the sentence that explains why
 * it is off, goes red here rather than on somebody's screen.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { REPLY_ROUTE, ReplyBox } from "@/features/workflows/reply-box"

afterEach(cleanup)

describe("the reply box", () => {
  it("renders a labelled field a reviewer can actually type into", () => {
    render(<ReplyBox />)

    const field = screen.getByLabelText(/reply to this run/i)
    fireEvent.change(field, { target: { value: "Please narrow the patch to the call site." } })

    expect((field as HTMLTextAreaElement).value).toBe(
      "Please narrow the patch to the call site.",
    )
  })

  it("keeps its submit control disabled, because no route accepts it", () => {
    render(<ReplyBox />)

    const submit = screen.getByRole("button", { name: /send reply/i })

    expect(submit).toHaveProperty("disabled", true)
  })

  it("stays disabled after the field is filled in, which is the whole refusal", () => {
    render(<ReplyBox />)

    fireEvent.change(screen.getByLabelText(/reply to this run/i), {
      target: { value: "anything at all" },
    })

    expect(screen.getByRole("button", { name: /send reply/i })).toHaveProperty("disabled", true)
  })

  it("names the route it needs, and says that route does not exist", () => {
    render(<ReplyBox />)

    expect(screen.getByText(new RegExp(REPLY_ROUTE.replace(/[{}/]/g, "\\$&")))).not.toBeNull()
    expect(screen.getByText(/does not exist yet/i)).not.toBeNull()
    expect(screen.getByText(/nothing typed here is stored, queued or sent/i)).not.toBeNull()
  })

  it("points the disabled control at that explanation, so the refusal is not visual only", () => {
    render(<ReplyBox />)

    const submit = screen.getByRole("button", { name: /send reply/i })
    const describedBy = submit.getAttribute("aria-describedby")

    expect(describedBy).not.toBeNull()
    const explanation = document.getElementById(describedBy as string)
    expect(explanation).not.toBeNull()
    expect(explanation?.textContent ?? "").toContain(REPLY_ROUTE)
  })
})

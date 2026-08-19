/**
 * A multi-select filter held in the URL.
 *
 * The derivation with a wrong answer is the write: a toggle has to add or remove one value and
 * clear the offsets in **one** `setSearchParams` call. `CI-W520` is the record of what two writes
 * cost — React Router hands the functional form the *current* params rather than a queued value,
 * so the second write is computed from a location the first has not reached and silently discards
 * it. That defect renders as a pressed option over an unchanged table, which reads as styling.
 */

import { act, cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, useSearchParams } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { useFilterListParam } from "@/lib/use-filter-list-param"

afterEach(cleanup)

let toggle: (value: string) => void
let clear: () => void

function Probe() {
  const [values, setValues, clearValues] = useFilterListParam("vendor", ["offset"])
  const [params] = useSearchParams()
  toggle = setValues
  clear = clearValues
  return (
    <>
      <output data-testid="values">{values.join("|")}</output>
      <output data-testid="url">{params.toString()}</output>
    </>
  )
}

function at(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Probe />
    </MemoryRouter>,
  )
}

const values = () => screen.getByTestId("values").textContent
const url = () => screen.getByTestId("url").textContent

describe("a multi-select filter in the URL", () => {
  it("reads every value given for the key", () => {
    at("/?vendor=stripe&vendor=twilio")

    expect(values()).toBe("stripe|twilio")
  })

  it("is empty when the key is absent", () => {
    at("/")

    expect(values()).toBe("")
  })

  it("adds a value without dropping the ones already chosen", () => {
    at("/?vendor=stripe")

    act(() => toggle("twilio"))

    expect(values()).toBe("stripe|twilio")
  })

  it("removes a value that is already chosen", () => {
    at("/?vendor=stripe&vendor=twilio")

    act(() => toggle("stripe"))

    expect(values()).toBe("twilio")
  })

  it("clears the offset in the same write that changes the filter", () => {
    // The whole of `CI-W520`, in one assertion: narrowing from 300 rows to 2 while sitting at
    // offset 250 asks for a page past the end and gets an empty one, which reads as "nothing
    // matches" rather than "you are past the end of two rows". Two writes lose one of the two.
    at("/?vendor=stripe&offset=250")

    act(() => toggle("twilio"))

    expect(values()).toBe("stripe|twilio")
    expect(url()).not.toContain("offset")
  })

  it("spells the unfiltered state as the key's absence", () => {
    // So an unfiltered table's URL is the URL it had before filtering existed, and two readers
    // who narrowed and un-narrowed by different routes are holding the same link.
    at("/?vendor=stripe")

    act(() => toggle("stripe"))

    expect(url()).not.toContain("vendor")
  })

  it("clears every value at once", () => {
    at("/?vendor=stripe&vendor=twilio&offset=50")

    act(() => clear())

    expect(values()).toBe("")
    expect(url()).not.toContain("offset")
  })

  it("does not add the same value twice", () => {
    // Two identical values would send `?vendor=stripe&vendor=stripe`, and the count beside the
    // option would describe a set the reader cannot get back to by pressing it once.
    at("/?vendor=stripe")

    act(() => toggle("twilio"))
    act(() => toggle("twilio"))

    expect(values()).toBe("stripe")
  })
})

/**
 * Decision 38: relative time, and the defect the decision names.
 *
 * A relative string is computed against `now`. A console tab sits open for hours, so a component
 * that formats once and never recomputes will say "14 minutes ago" at nine about something from
 * four — the console stating a falsehood with total confidence, reached through a formatting
 * helper. What is asserted here is that this one re-renders, and that the absolute is reachable
 * without leaving the row.
 */

import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RelativeTime } from "@/components/relative-time"

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  cleanup()
})

const AT = "2026-08-18T12:00:00Z"

function at(iso: string) {
  vi.setSystemTime(new Date(iso))
}

describe("RelativeTime", () => {
  it("states the age relative to now", () => {
    at("2026-08-18T12:05:00Z")
    render(<RelativeTime iso={AT} />)

    expect(screen.getByText("5m ago")).not.toBeNull()
  })

  it("re-renders as time passes, which is what makes it relative", () => {
    at("2026-08-18T12:05:00Z")
    render(<RelativeTime iso={AT} />)
    expect(screen.getByText("5m ago")).not.toBeNull()

    // The defect decision 38 names: a helper that formats once would still say "5m ago" here.
    act(() => {
      vi.setSystemTime(new Date("2026-08-18T13:05:00Z"))
      vi.advanceTimersByTime(60_000)
    })

    expect(screen.getByText("1h ago")).not.toBeNull()
    expect(screen.queryByText("5m ago")).toBeNull()
  })

  it("carries the exact timestamp in the title, with its UTC offset", () => {
    at("2026-08-18T12:05:00Z")
    render(<RelativeTime iso={AT} />)

    const title = screen.getByText("5m ago").getAttribute("title") ?? ""
    // "The absolute carries its UTC offset" -- a bare local string cannot be checked against a
    // log line by a reader in another zone.
    expect(title).toMatch(/GMT|UTC/)
  })

  it("renders absence rather than a guess when there is no timestamp", () => {
    at("2026-08-18T12:05:00Z")
    render(<RelativeTime iso={null} />)

    expect(screen.getByText("—")).not.toBeNull()
  })

  it("renders absence rather than echoing an unparseable value as if it were a time", () => {
    at("2026-08-18T12:05:00Z")
    render(<RelativeTime iso="not-a-timestamp" />)

    expect(screen.getByText("—")).not.toBeNull()
  })
})

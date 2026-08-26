/**
 * A triage panel's counts and its empty state are claims, and this suite guards the two that are
 * easy to get wrong in a way nothing else catches.
 *
 * **Retitled 2026-08-26, when `TriageTabs` was deleted.** The `describe("TriageTabs")` DOM suite
 * went with the component: its one caller no longer wraps its table in a Radix `Tabs` root, and a
 * component with no caller is deleted rather than deprecated. What that suite actually held about
 * counts — a confirmed zero renders `0`, an unanswered count renders the absence marker, nothing
 * sums across the strip — now belongs to `ChipTabs` and is asserted in `chip-tabs.test.tsx`, so the
 * coverage moved rather than being dropped. `describe("triagePanelState")` is kept verbatim,
 * because the derivation is the half with a wrong answer and is the reason this file is worth
 * having. `describe("TriageEmpty")` is new and holds the three panels the tabs used to render.
 *
 * **A zero and an unanswered count look identical once either one is rendered as `0`.** The types
 * keep them apart before the render happens: a caller cannot pass a bare number.
 *
 * **An empty list after a real scan is a different fact from one before any scan.** That is the
 * sentence `docs/superpowers/plans/2026-08-18-page-information-architecture.md:122-123` puts on
 * this module, and `checks` is a required prop so the honest empty state is the only one that
 * compiles. These tests hold both branches of it.
 *
 * Scope, per `.claude/rules/console-dev-loop.md`: classification, derivation and structural
 * invariants. No class names, no snapshots.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import {
  TriageEmpty,
  triagePanelState,
  type TriageChecks,
  type TriageCount,
} from "@/components/triage"

afterEach(cleanup)

const DETECTORS = ["stripe-openapi-diff", "sdk-symbol-drift"] as const

const CHECKED: TriageChecks = {
  kind: "checked",
  ran: ["stripe-openapi-diff", "sdk-symbol-drift"],
  at: "2026-08-18T09:00:00.000Z",
}

const UNCHECKED: TriageChecks = {
  kind: "unchecked",
  why: "no scan has run against this repository yet",
}

describe("triagePanelState", () => {
  it("separates a counted zero from a count nothing answered", () => {
    expect(triagePanelState({ kind: "counted", value: 0 }, CHECKED)).toBe("empty-after-check")
    expect(triagePanelState({ kind: "unanswered", why: "the route timed out" }, CHECKED)).toBe(
      "count-unanswered"
    )
  })

  it("separates an empty answer after a check from one before any check", () => {
    expect(triagePanelState({ kind: "counted", value: 0 }, CHECKED)).toBe("empty-after-check")
    expect(triagePanelState({ kind: "counted", value: 0 }, UNCHECKED)).toBe(
      "empty-before-any-check"
    )
  })

  it("reports records for any answered count above zero, whatever was checked", () => {
    expect(triagePanelState({ kind: "counted", value: 1 }, CHECKED)).toBe("records")
    expect(triagePanelState({ kind: "counted", value: 12 }, UNCHECKED)).toBe("records")
  })
})

describe("TriageEmpty", () => {
  function renderEmpty(count: TriageCount, checks: TriageChecks, label = "breaking") {
    return render(<TriageEmpty noun="open findings" label={label} count={count} checks={checks} />)
  }

  it("renders nothing at all when the narrowing has records", () => {
    // The caller renders it unconditionally above its table, so "records" has to be silent --
    // otherwise every non-empty screen carries an empty-state panel over its rows.
    const { container } = renderEmpty({ kind: "counted", value: 12 }, CHECKED)

    expect(container.textContent).toBe("")
  })

  it("names the detectors that stood behind a counted zero", () => {
    renderEmpty({ kind: "counted", value: 0 }, CHECKED)

    expect(screen.getByText(/No open findings under breaking/)).toBeTruthy()
    expect(DETECTORS.length).toBeGreaterThan(0)
    for (const detector of DETECTORS) {
      expect(screen.getByText(detector)).toBeTruthy()
    }
  })

  it("refuses to claim a check on the unchecked arm", () => {
    // The distinction the console exists for: nothing has looked is not a measured zero, and the
    // panel may not borrow the other branch's detectors to soften it.
    renderEmpty({ kind: "counted", value: 0 }, UNCHECKED)

    expect(screen.getByText(/Nothing has checked for open findings here/)).toBeTruthy()
    expect(screen.getByText(/no scan has run against this repository yet/)).toBeTruthy()
    for (const detector of DETECTORS) {
      expect(screen.queryByText(detector)).toBeNull()
    }
  })

  it("states why a count went unanswered instead of claiming the set is empty", () => {
    renderEmpty({ kind: "unanswered", why: "the reason-code route was not queried" }, CHECKED)

    expect(screen.getByText(/the reason-code route was not queried/)).toBeTruthy()
    expect(screen.queryByText(/No open findings under/)).toBeNull()
  })
})

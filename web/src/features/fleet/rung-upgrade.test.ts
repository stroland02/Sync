/**
 * The rung as an upgrade path, and the two rungs that are not on it.
 *
 * **The product argument this serves.** Sync shows real findings *before anything is configured*,
 * because the static rung is read out of source code. A telemetry product cannot do that — its
 * dashboard is empty until traces arrive. So the rung has to read on screen as a path with a next
 * step, not as a label: static now, observed once telemetry is attached, and the screen shows what
 * that bought by simply counting again.
 *
 * **What must not happen is a prediction.** Nothing here estimates how many bindings *would* upgrade.
 * The panel counts what each rung holds now; attaching telemetry changes the counts and the same
 * panel shows the difference. A forecast would be exactly the composite-score failure this console
 * exists to replace, wearing a different hat.
 */

import { describe, expect, it } from "vitest"

import type { DetectorRow } from "@/api/types"
import { UPGRADE_PATH, nextStep, offPath, rungSteps } from "@/features/fleet/rung-upgrade"

const detector = (by_rung: Record<string, number>): DetectorRow => ({
  detector: "d",
  total: Object.values(by_rung).reduce((a, b) => a + b, 0),
  by_rung,
  by_claim: {},
  by_severity: {},
})

describe("the rung upgrade path", () => {
  it("is the three rungs that are evidence, in strengthening order", () => {
    // `unresolved` is the named absence of a binding and `unattributed` is a row written before the
    // column existed. Neither is a step somebody can take, so neither is on the path.
    expect([...UPGRADE_PATH]).toEqual(["static", "resolved", "observed"])
  })

  it("sums each rung across every detector in the scope", () => {
    const steps = rungSteps([detector({ static: 3, observed: 1 }), detector({ static: 2 })])

    expect(steps.map((s) => [s.rung, s.count])).toEqual([
      ["static", 5],
      ["resolved", 0],
      ["observed", 1],
    ])
  })

  it("marks a rung reached only when something actually rests on it", () => {
    const steps = rungSteps([detector({ static: 4 })])

    expect(steps.find((s) => s.rung === "static")?.reached).toBe(true)
    // Zero is a measured answer here, not an absence: the scope was counted and observed held none.
    expect(steps.find((s) => s.rung === "observed")?.reached).toBe(false)
  })

  it("names the next step as the weakest rung nothing rests on yet", () => {
    expect(nextStep(rungSteps([detector({ static: 4 })]))?.rung).toBe("resolved")
    expect(nextStep(rungSteps([detector({ static: 4, resolved: 1 })]))?.rung).toBe("observed")
  })

  it("has no next step once the strongest rung is reached", () => {
    // Nothing to sell and nothing to promise. The panel says so rather than inventing a further step.
    expect(nextStep(rungSteps([detector({ static: 4, resolved: 1, observed: 2 })]))).toBeNull()
  })

  it("reports an empty scope as every rung at zero, never as an upgrade opportunity", () => {
    const steps = rungSteps([])

    expect(steps.every((s) => s.count === 0 && !s.reached)).toBe(true)
    // With nothing indexed there is no evidence at any rung, so "attach telemetry" would be advice
    // about a codebase we have not read. The caller renders absence instead; `nextStep` still
    // answers `static`, and the panel is responsible for not turning that into a pitch.
    expect(nextStep(steps)?.rung).toBe("static")
  })

  it("keeps the two off-path rungs visible rather than dropping them", () => {
    // Hiding them would make the counts on screen not add up to the total, which is its own lie.
    const off = offPath([detector({ static: 2, unresolved: 3, unattributed: 1 })])

    expect(off).toEqual([
      { rung: "unresolved", count: 3 },
      { rung: "unattributed", count: 1 },
    ])
  })

  it("omits an off-path rung that holds nothing", () => {
    expect(offPath([detector({ static: 2, unresolved: 1 })])).toEqual([
      { rung: "unresolved", count: 1 },
    ])
  })
})

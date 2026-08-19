/**
 * The ramps, proved against the contract rather than trusted from the slots they were built from.
 *
 * A ramp can clear the mark floor at its top and vanish at its bottom, which is worse than a flat
 * colour because it looks measured. `DESIGN.md` sets 3:1 for a non-text mark, and these assert it
 * at both ends and the middle of every ramp the console ships.
 */

import { describe, expect, it } from "vitest"

import {
  contrastRatio,
  divergingScale,
  PLOTTING_SURFACE,
  rampClearsFloor,
  SERIES_SLOTS,
  volumeScale,
} from "@/lib/palette"

describe("the volume ramp", () => {
  it("clears the mark floor at its floor, not only at its top", () => {
    // The defect this guards: a ramp interpolated from the surface itself renders its smallest
    // values invisible, so a low-volume flow reads as no flow.
    const ramp = volumeScale()
    expect(contrastRatio(ramp(0), PLOTTING_SURFACE)).toBeGreaterThanOrEqual(3)
    expect(rampClearsFloor(ramp)).toBe(true)
  })

  it("clears the floor for every series slot, not just the default", () => {
    for (const slot of SERIES_SLOTS) {
      expect(rampClearsFloor(volumeScale(slot))).toBe(true)
    }
  })

  it("is monotonic in emphasis, so a larger value is never drawn fainter", () => {
    const ramp = volumeScale()
    const steps = [0, 0.25, 0.5, 0.75, 1].map((t) => contrastRatio(ramp(t), PLOTTING_SURFACE))
    for (let i = 1; i < steps.length; i += 1) {
      expect(steps[i]).toBeGreaterThanOrEqual(steps[i - 1] - 0.01)
    }
  })
})

describe("the diverging ramp", () => {
  it("clears the mark floor across its whole range, including the neutral midpoint", () => {
    expect(rampClearsFloor(divergingScale())).toBe(true)
  })

  it("is symmetric about its midpoint, so neither side reads as the default", () => {
    // A diverging scale whose halves have different weight makes one direction look like the
    // norm and the other like a deviation -- which is the worse-versus-better reading this
    // console refuses, arriving through the geometry rather than through the hue.
    const ramp = divergingScale()
    const low = contrastRatio(ramp(0), PLOTTING_SURFACE)
    const high = contrastRatio(ramp(1), PLOTTING_SURFACE)
    expect(Math.abs(low - high)).toBeLessThan(2)
  })
})

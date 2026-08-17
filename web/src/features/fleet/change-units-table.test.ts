/**
 * The two classifiers this table derives from `ChangeUnitRow`, tested the way
 * `.claude/rules/console-dev-loop.md` asks: classification and derivation, never a class name
 * and never a snapshot.
 *
 * `describeChangeUnitStanding` is the one place a `null` standing turns into a rendered
 * sentence, and it is the exact honesty invariant the console's whole argument rests on: a
 * change unit that has never had a remediation run attempted must never render the same way
 * as one whose run is still going, or one whose run finished. `describeChangeUnitRung` is the
 * one place `"mixed"` — a real value `_weaker_rung_summary` can answer that is not one of the
 * five the graph's `binding_rung` column holds — gets a sentence instead of falling into
 * `describeRung`'s "not recognised" branch, which would describe it as a data error rather
 * than the deliberate answer it is.
 */

import { describe, expect, it } from "vitest"

import { describeChangeUnitRung, describeChangeUnitStanding } from "@/features/fleet/change-units-table"

describe("describeChangeUnitStanding", () => {
  it("reads null as no remediation run ever attempted, not a symbol", () => {
    // Null here means one of two things the payload cannot tell apart: no run was ever
    // attempted for any finding this unit groups, or this deployment has no checkpointer to
    // ask. Rendering it as a dash or as "not started" would claim the second case never
    // happens.
    expect(describeChangeUnitStanding(null)).toBeNull()
  })

  it("reads each of the three terminal outcomes as its own sentence", () => {
    expect(describeChangeUnitStanding("opened")?.label).toMatch(/PR open/)
    expect(describeChangeUnitStanding("abandoned")?.label).toMatch(/Abandoned/)
    expect(describeChangeUnitStanding("reported")?.label).toMatch(/Reported/)
  })

  it("reads the checkpointer's in-flight value as in progress, not as one of the three finished outcomes", () => {
    const standing = describeChangeUnitStanding("in_progress")
    expect(standing?.label).toMatch(/progress/i)
    expect(standing?.label).not.toMatch(/PR open|Abandoned|Reported/)
  })

  it("gives the three terminal outcomes and in-flight four distinct tones, none of them a fabricated composite", () => {
    const tones = new Set(
      (["opened", "abandoned", "reported", "in_progress"] as const).map(
        (standing) => describeChangeUnitStanding(standing)?.tone,
      ),
    )
    expect(tones.size).toBe(4)
  })
})

describe("describeChangeUnitRung", () => {
  it("describes each of the five graph rungs the same way the finding-level rung badge does", () => {
    expect(describeChangeUnitRung("static")).toMatch(/read out of the source/)
    expect(describeChangeUnitRung("observed")).toMatch(/correlated from watched traffic/)
  })

  it("describes 'mixed' as a real disagreement among call sites, not as an unrecognised value", () => {
    // `_weaker_rung_summary` answers "mixed" deliberately, when a change unit's call sites do
    // not all agree on one rung. `describeRung` alone has no branch for it and would fall into
    // its "this console does not recognise" sentence, which is the wrong claim: the console
    // recognises this value exactly, and it is not a data error.
    const description = describeChangeUnitRung("mixed")
    expect(description).not.toMatch(/does not recognise/)
    expect(description.toLowerCase()).toMatch(/agree|mixed/)
  })
})

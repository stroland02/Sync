/**
 * The one sentence the Findings band says about the findings it is not listing.
 *
 * Four branches, each a different fact, and three of them are the kind that get folded together in
 * a tidy-up: in flight, did-not-answer, and a measured zero. A pending read rendered as "nobody has
 * dismissed anything" is the absence-as-zero collapse in its purest form.
 *
 * **Every branch carrying a figure names the fleet scope**, because a fleet number beside a
 * workspace-scoped table is the attribution error this console keeps removing. Proven red by
 * dropping the scope clause and watching the last two assertions fail.
 */

import { describe, expect, it } from "vitest"

import { dismissedNote } from "@/features/findings/dismissed-note"

describe("dismissedNote", () => {
  it("says the read is in flight rather than reporting nothing set aside", () => {
    const note = dismissedNote({ isPending: true, isError: false, data: undefined })

    expect(note.kind).toBe("note")
    expect(note).toHaveProperty("text", expect.stringMatching(/asking how many/i))
  })

  it("says the read failed rather than reporting a zero", () => {
    const note = dismissedNote({ isPending: false, isError: true, data: undefined })

    expect(note).toHaveProperty("text", expect.stringMatching(/did not answer/i))
    expect(note).not.toHaveProperty("text", expect.stringMatching(/nobody has dismissed/i))
  })

  it("names a zero as measured, not as a screen that cannot see dismissals", () => {
    const note = dismissedNote({ isPending: false, isError: false, data: { total: 0, counts: {} } })

    const text = (note as { text: string }).text
    expect(text).toMatch(/measured zero/i)
    expect(text).toMatch(/any repository this deployment holds/i)
  })

  it("states the fleet scope beside a non-zero figure", () => {
    const note = dismissedNote({
      isPending: false,
      isError: false,
      data: { total: 12, counts: { "false-positive": 12 } },
    })

    const text = (note as { text: string }).text
    expect(text).toContain("12")
    // The whole reason a fleet figure may sit on a workspace screen at all.
    expect(text).toMatch(/across every repository this deployment holds/i)
    expect(text).toMatch(/not in this workspace alone/i)
    // And what the table beside it is, so the two counts cannot be read as one population.
    expect(text).toMatch(/open findings only/i)
  })

  it("treats an answered read with no payload as a failure, never as a zero", () => {
    // `data === undefined` with `isError` false is the shape a cancelled or unresolved read leaves
    // behind, and reporting it as "nobody has dismissed a finding" would be a measurement nobody
    // took.
    const note = dismissedNote({ isPending: false, isError: false, data: undefined })

    expect(note).toHaveProperty("text", expect.stringMatching(/did not answer/i))
  })
})

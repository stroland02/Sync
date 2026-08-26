/**
 * The catalogue's classifications, each of which has a wrong answer that would put a false claim
 * on screen rather than a misaligned pixel.
 *
 * Three of these are honesty rules rather than arithmetic: an empty catalogue over a corpus
 * nothing read is not an empty catalogue over a corpus that was read; a declared rung the payload
 * omitted is not a rung at nought; and a claim key whose target half is missing is not a claim
 * against an empty pointer.
 */

import { describe, expect, it } from "vitest"

import type { DetectorRow } from "@/api/types"
import {
  catalogueState,
  claimKinds,
  claimParts,
  rungLadder,
  selectDetector,
} from "@/features/detectors/detector-catalogue"

function detector(name: string, by_claim: Record<string, number> = {}): DetectorRow {
  return { detector: name, total: 0, by_rung: {}, by_claim, by_severity: {} }
}

describe("catalogueState", () => {
  it("calls a corpus nothing has read never-indexed rather than an empty catalogue", () => {
    expect(
      catalogueState({ detectorCount: 0, corpus: { indexedAt: null, hasIndexRun: false } }),
    ).toBe("never-indexed")
  })

  it("calls an empty catalogue over a read corpus a counted zero", () => {
    expect(
      catalogueState({
        detectorCount: 0,
        corpus: { indexedAt: "2026-08-26T11:19:43Z", hasIndexRun: false },
      }),
    ).toBe("counted-zero")
  })

  it("counts an index pass as a read even when no call site carries a time", () => {
    // A pass that completed and found nothing wrote no call site, so `indexedAt` is null and the
    // repository has still been read. Reading only `indexedAt` would report that pass as
    // never-indexed, which is the pass's own result rendered as its absence.
    expect(
      catalogueState({ detectorCount: 0, corpus: { indexedAt: null, hasIndexRun: true } }),
    ).toBe("counted-zero")
  })

  it("refuses to say which nothing it is while the corpus read has not answered", () => {
    expect(catalogueState({ detectorCount: 0, corpus: "unanswered" })).toBe("corpus-unknown")
  })

  it("is populated whatever the corpus read did, because rows are their own evidence", () => {
    expect(catalogueState({ detectorCount: 3, corpus: "unanswered" })).toBe("populated")
    expect(
      catalogueState({ detectorCount: 3, corpus: { indexedAt: null, hasIndexRun: false } }),
    ).toBe("populated")
  })
})

describe("rungLadder", () => {
  it("keeps a declared rung the payload omitted as null rather than as a zero", () => {
    // The transport seeds this tally from the whole vocabulary, so a missing key is a defect and
    // not a measurement. Rendering it as 0 claims a count nobody took.
    const ladder = rungLadder({ observed: 4, resolved: 1, static: 2, unresolved: 0 })

    const unattributed = ladder.rows.find((row) => row.rung === "unattributed")!
    expect(unattributed.count).toBeNull()
    expect(ladder.unreported).toEqual(["unattributed"])
    expect(ladder.countedEmpty).toEqual(["unresolved"])
  })

  it("draws every declared rung in evidence order, never in the payload's order", () => {
    const ladder = rungLadder({ unattributed: 1, static: 1, observed: 1, unresolved: 1, resolved: 1 })

    expect(ladder.rows.map((row) => row.rung)).toEqual([
      "observed",
      "resolved",
      "static",
      "unresolved",
      "unattributed",
    ])
  })

  it("totals only what was reported, so an omitted rung is not summed as nothing", () => {
    const ladder = rungLadder({ observed: 4, resolved: 1 })

    expect(ladder.total).toBe(5)
    expect(ladder.carrying).toEqual(["observed", "resolved"])
  })

  it("counts a rung this console has never heard of rather than dropping it", () => {
    const ladder = rungLadder({ static: 3, "correlated-next-month": 2 })

    expect(ladder.unrecognised).toEqual(["correlated-next-month"])
    expect(ladder.total).toBe(5)
    expect(ladder.rows.at(-1)).toMatchObject({ rung: "correlated-next-month", known: false })
  })

  it("names a rung the console does not hold as unrecognised rather than as an absence", () => {
    const ladder = rungLadder({ novel: 1 })

    expect(ladder.countedEmpty).toEqual([])
    expect(ladder.unreported).toEqual([
      "observed",
      "resolved",
      "static",
      "unresolved",
      "unattributed",
    ])
  })

  it("gives every declared rung a clause, so the vocabulary explains itself without a hover", () => {
    const ladder = rungLadder({ observed: 1 })

    for (const row of ladder.rows.filter((candidate) => candidate.known)) {
      expect(row.meaning.length).toBeGreaterThan(0)
    }
  })
})

describe("claimParts", () => {
  it("splits a claim key into the kind matched and the target it was matched against", () => {
    expect(claimParts("claim-removed:/id_token/claims/sub")).toEqual({
      kind: "claim-removed",
      target: "/id_token/claims/sub",
    })
  })

  it("splits at the first colon only, so a pointer carrying colons stays whole", () => {
    expect(claimParts("rpc-deprecated:/google.spanner.v1:ExecuteSql")).toEqual({
      kind: "rpc-deprecated",
      target: "/google.spanner.v1:ExecuteSql",
    })
  })

  it("reports no target rather than an empty one when the key names only a kind", () => {
    expect(claimParts("model-retired")).toEqual({ kind: "model-retired", target: null })
    expect(claimParts("model-retired:")).toEqual({ kind: "model-retired", target: null })
  })

  it("reports no kind rather than an empty one for a key the transport left unnamed", () => {
    expect(claimParts("")).toEqual({ kind: null, target: null })
    expect(claimParts(":/x")).toEqual({ kind: null, target: "/x" })
  })
})

describe("claimKinds", () => {
  it("counts kinds of change rather than the targets they were matched against", () => {
    const rows = [
      detector("a", { "field-removed:/x": 1, "field-removed:/y": 1, "field-deprecated:/z": 1 }),
      detector("b", { "field-removed:/q": 1 }),
    ]

    expect(claimKinds(rows)).toEqual(["field-deprecated", "field-removed"])
  })

  it("drops a key naming no kind rather than counting an unnamed one", () => {
    expect(claimKinds([detector("a", { "": 2, "tool-removed:/t": 1 })])).toEqual(["tool-removed"])
  })
})

describe("selectDetector", () => {
  it("reads an absent and an empty key as no selection", () => {
    const rows = [detector("a")]

    expect(selectDetector(rows, null).state).toBe("none")
    expect(selectDetector(rows, "").state).toBe("none")
  })

  it("carries back a key this roll-up does not hold rather than reading it as no selection", () => {
    // Collapsing this onto `none` would make an address naming a detector that stopped firing
    // look like an address naming nothing, and the pane would say so silently.
    const selection = selectDetector([detector("a")], "b")

    expect(selection).toEqual({ state: "unresolved", key: "b" })
  })

  it("resolves a key the roll-up holds to its own row", () => {
    const rows = [detector("a"), detector("b")]

    expect(selectDetector(rows, "b")).toEqual({ state: "resolved", row: rows[1] })
  })
})

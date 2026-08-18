/**
 * What the canvas is looking at, as a classification.
 *
 * The screen showed one nothing for two facts and said so in its own empty state: "a repository
 * the index never ran against shows the same nothing as one that calls no vendor". `indexed_at`
 * (CI-W403) is what removes that, so these assert the two are now told apart — and that off-path
 * bindings are still a state of their own when no static call site exists at all.
 */

import { describe, expect, it } from "vitest"

import type { RepositoryGraphResponse } from "@/api/types"
import { classifyIndexState } from "@/features/index-graph/index-state"

const graph = (over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse => ({
  repo_id: "org/payments",
  vendors: [],
  bindings: [],
  observed_bindings: [],
  off_path: { unresolved: 0, unattributed: 0 },
  rungs: ["static", "resolved", "observed", "unresolved", "unattributed"],
  indexed_at: null,
  total_bindings: 0,
  truncated: false,
  ...over,
})

describe("classifyIndexState", () => {
  /** The distinction CI-W403 made expressible. */
  it("says nothing has ever been recorded when no call site row has existed", () => {
    expect(classifyIndexState(graph()).kind).toBe("never-recorded")
  })

  it("says the index ran and found nothing when it wrote here but drew no binding", () => {
    const state = classifyIndexState(graph({ indexed_at: "2026-08-18T10:00:00Z" }))

    expect(state.kind).toBe("indexed-empty")
  })

  it("draws the graph when there is one", () => {
    const state = classifyIndexState(
      graph({
        indexed_at: "2026-08-18T10:00:00Z",
        bindings: [
          { vendor_id: "stripe", operation_id: "PostCharges", path: "a.ts", line: 1, symbol: "s", binding_rung: "static" },
        ],
      }),
    )

    expect(state.kind).toBe("drawn")
  })

  /**
   * Traffic and history can exist with no current static call site — a repository whose calls
   * were all retracted still has observed rows and unattributed findings. Rendering that as
   * "nothing here" would drop evidence the graph is holding.
   */
  it("reports off-path evidence even when no static binding is drawn", () => {
    const state = classifyIndexState(
      graph({ indexed_at: "2026-08-18T10:00:00Z", off_path: { unresolved: 3, unattributed: 2 } }),
    )

    expect(state.kind).toBe("indexed-empty")
    expect(state.offPathTotal).toBe(5)
  })

  it("reports off-path as nought rather than absent, because the tables were read", () => {
    expect(classifyIndexState(graph()).offPathTotal).toBe(0)
  })

  /** Never default a count to zero: the never-recorded case has no indexed timestamp to show. */
  it("carries the indexed timestamp only when there is one", () => {
    expect(classifyIndexState(graph()).indexedAt).toBeNull()
    expect(classifyIndexState(graph({ indexed_at: "2026-08-18T10:00:00Z" })).indexedAt).toBe(
      "2026-08-18T10:00:00Z",
    )
  })
})

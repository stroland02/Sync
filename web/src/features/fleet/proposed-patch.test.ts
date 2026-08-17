import { describe, expect, it } from "vitest"

import { proposedPatchTarget } from "@/features/fleet/proposed-patch"
import type { RunRow } from "@/api/types"

const row = (over: Partial<RunRow>): RunRow => ({
  thread_id: "f1:abc:1",
  finding_id: "f1",
  current_node: null,
  outcome: null,
  abandon_reason: null,
  last_checkpoint_at: null,
  ...over,
})

describe("proposedPatchTarget", () => {
  it("is null when no run has opened a pull request", () => {
    expect(proposedPatchTarget([row({ outcome: "abandoned" }), row({})])).toBeNull()
  })

  it("names the first opened run's pull-request route", () => {
    const runs = [row({ outcome: "abandoned" }), row({ finding_id: "f9", outcome: "opened" })]
    expect(proposedPatchTarget(runs)).toBe("/findings/f9/workflow/pull-request")
  })

  it("is null on an empty list", () => {
    expect(proposedPatchTarget([])).toBeNull()
  })
})

import { describe, expect, it } from "vitest"

import { activityEntries, omittedCount } from "@/features/workflows/activity"
import type { WorkflowState, WorkflowNode } from "@/api/types"

const node = (over: Partial<WorkflowNode>): WorkflowNode => ({
  name: "locate",
  status: "done",
  standing: "ran",
  evidence: {},
  ...over,
})

const state = (nodes: WorkflowNode[], over: Partial<WorkflowState> = {}): WorkflowState => ({
  nodes,
  outcome: null,
  abandon_reason: null,
  report_reason: null,
  thread_id: "f1:abc:1",
  generation_count: 1,
  repo_id: null,
  generations: [],
  ...over,
})

describe("activityEntries", () => {
  it("orders stamped entries by time and puts the unstamped outcome last", () => {
    const s = state(
      [
        node({ name: "prepare", first_seen_at: "2026-08-17T14:02:31Z" }),
        node({ name: "locate", first_seen_at: "2026-08-17T14:02:14Z" }),
      ],
      { outcome: "opened" }
    )
    const names = activityEntries(s).map((e) => e.name)
    expect(names).toEqual(["locate.ran", "prepare.ran", "run.opened"])
    expect(activityEntries(s).at(-1)!.at).toBeNull()
  })

  it("emits no entry for a node that never wrote a timestamp, and counts it", () => {
    const s = state([
      node({ name: "locate", first_seen_at: "2026-08-17T14:02:14Z" }),
      node({ name: "patch", standing: "not_reached_yet" }),
    ])
    expect(activityEntries(s).map((e) => e.name)).toEqual(["locate.ran"])
    expect(omittedCount(s)).toBe(1)
  })

  it("carries the abandon reason as the closing entry's detail", () => {
    const s = state([node({ first_seen_at: "2026-08-17T14:02:14Z" })], {
      outcome: "abandoned",
      abandon_reason: "no tier applied",
    })
    const closing = activityEntries(s).at(-1)!
    expect(closing.name).toBe("run.abandoned")
    expect(closing.detail).toBe("no tier applied")
  })

  it("emits no closing entry while the run has no outcome", () => {
    const s = state([node({ first_seen_at: "2026-08-17T14:02:14Z" })])
    expect(activityEntries(s).some((e) => e.name.startsWith("run."))).toBe(false)
  })
})

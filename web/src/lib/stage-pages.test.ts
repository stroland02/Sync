/**
 * The Overview draws every door a workspace has, or the build says which one it dropped.
 *
 * A page added to the registry and forgotten here is a screen nothing links to from the one
 * place a reader starts — reachable by typed URL and by nothing else.
 */

import { describe, expect, it } from "vitest"

import { WORKFLOW_STAGES } from "@/lib/routes"
import { LOOP_PREREQUISITES, SETTING_GROUPS } from "@/features/settings/groups"
import { PIPELINE_HOME, pagesByStage, stageOf, workspacePages } from "@/lib/stage-pages"

describe("the pipeline's pages", () => {
  it("gives every page a workspace can reach exactly one stage", () => {
    const staged = pagesByStage().flatMap((group) => group.pages.map((route) => route.path))

    expect(new Set(staged).size).toBe(staged.length)
    expect([...staged].sort()).toEqual(workspacePages().map((route) => route.path).sort())
  })

  it("names a stage the vocabulary holds, for each of them", () => {
    for (const route of workspacePages()) {
      expect(WORKFLOW_STAGES).toContain(stageOf(route))
    }
  })

  it("leaves the Overview itself out, since it is the screen the pipeline is drawn on", () => {
    expect(workspacePages().map((route) => route.path)).not.toContain(PIPELINE_HOME)
  })

  it("puts a page in every stage, so no stage draws as an empty door", () => {
    for (const group of pagesByStage()) {
      expect(group.pages.length).toBeGreaterThan(0)
    }
  })
})

describe("the Settings card on the stage grid", () => {
  it("names only groups the Settings screen declares", () => {
    // A group renamed or dropped there would otherwise make a row vanish from the Overview
    // silently, which is the drift that made this card worth generating rather than writing.
    for (const prerequisite of LOOP_PREREQUISITES) {
      expect(SETTING_GROUPS.map((group) => group.id)).toContain(prerequisite.id)
    }
  })
})
